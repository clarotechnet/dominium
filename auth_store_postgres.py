"""Backend PostgreSQL para identidade, sessao e auditoria do DOMINIUM."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import secrets
from contextlib import contextmanager
from typing import Any

from auth_store import (
    AuthError,
    AuthStore,
    LOCK_AFTER_FAILURES,
    LOCK_SECONDS,
    SESSION_ABSOLUTE_SECONDS,
    SESSION_IDLE_SECONDS,
    VALID_ROLES,
    _decode_time,
    _iso,
    _utc_now,
    hash_password,
    normalize_username,
    validate_password,
    verify_password,
)


class PostgresAuthStore(AuthStore):
    def __init__(self, database_url: str) -> None:
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Instale psycopg[binary] para usar DOMINIUM_DATABASE_URL"
            ) from exc
        self.database_url = str(database_url or "").strip()
        if not self.database_url:
            raise RuntimeError("DOMINIUM_DATABASE_URL vazio")
        self._initialize()

    @contextmanager
    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=10,
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dominium_users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin','controller','viewer')),
                    status TEXT NOT NULL CHECK (status IN ('pending','active','disabled','rejected')),
                    imperium_username TEXT NOT NULL DEFAULT '',
                    imperium_controller_id BIGINT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by BIGINT REFERENCES dominium_users(id),
                    last_login_at TEXT,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    contact_email TEXT,
                    rejected_at TEXT,
                    rejected_by BIGINT REFERENCES dominium_users(id),
                    rejection_reason TEXT
                )
                """
            )
            # Runtime migrations for existing databases (idempotent)
            existing_cols = {
                row["column_name"]
                for row in connection.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'dominium_users'
                    """
                ).fetchall()
            }
            if "contact_email" not in existing_cols:
                connection.execute("ALTER TABLE dominium_users ADD COLUMN IF NOT EXISTS contact_email TEXT")
            if "rejected_at" not in existing_cols:
                connection.execute("ALTER TABLE dominium_users ADD COLUMN IF NOT EXISTS rejected_at TEXT")
            if "rejected_by" not in existing_cols:
                connection.execute(
                    "ALTER TABLE dominium_users ADD COLUMN IF NOT EXISTS rejected_by BIGINT REFERENCES dominium_users(id)"
                )
            if "rejection_reason" not in existing_cols:
                connection.execute("ALTER TABLE dominium_users ADD COLUMN IF NOT EXISTS rejection_reason TEXT")
            # Ensure status CHECK constraint includes 'rejected' (drop & recreate if old)
            old_check = connection.execute(
                """
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'dominium_users'
                  AND constraint_type = 'CHECK'
                  AND constraint_name LIKE '%status%'
                """
            ).fetchone()
            if old_check:
                # Recreate only when the constraint doesn't already permit 'rejected'
                check_def = connection.execute(
                    """
                    SELECT check_clause FROM information_schema.check_constraints
                    WHERE constraint_name = %s
                    """,
                    (old_check["constraint_name"],),
                ).fetchone()
                if check_def and "rejected" not in (check_def["check_clause"] or ""):
                    connection.execute(
                        f"ALTER TABLE dominium_users DROP CONSTRAINT IF EXISTS {old_check['constraint_name']}"
                    )
                    connection.execute(
                        "ALTER TABLE dominium_users ADD CONSTRAINT dominium_users_status_check "
                        "CHECK (status IN ('pending','active','disabled','rejected'))"
                    )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dominium_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES dominium_users(id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    csrf_token TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    user_agent_hash TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dominium_imperium_identities (
                    user_id BIGINT NOT NULL REFERENCES dominium_users(id) ON DELETE CASCADE,
                    profile_key TEXT NOT NULL,
                    imperium_username TEXT NOT NULL,
                    controller_id BIGINT NOT NULL,
                    verified_at TEXT NOT NULL,
                    verified_by BIGINT REFERENCES dominium_users(id),
                    PRIMARY KEY (user_id, profile_key)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dominium_operator_audit (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_id BIGINT,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    target TEXT NOT NULL,
                    technician TEXT NOT NULL,
                    external_actor TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_dominium_sessions_user ON dominium_sessions(user_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_dominium_audit_created ON dominium_operator_audit(created_at DESC)")

    def has_users(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM dominium_users"
            ).fetchone()
        return bool(row and int(row["total"]) > 0)

    def register(
        self,
        username: object,
        display_name: object,
        password: object,
        *,
        allow_bootstrap: bool,
        contact_email: object = None,
    ) -> dict[str, Any]:
        normalized = normalize_username(username)
        name = " ".join(str(display_name or "").strip().split())
        if len(name) < 3 or len(name) > 80:
            raise AuthError("Informe o nome do operador, entre 3 e 80 caracteres")
        # Validate contact_email format if supplied (metadata only, never an auth credential)
        safe_email: str | None = None
        if contact_email:
            import re as _re
            raw_email = str(contact_email).strip()
            if raw_email:
                if not _re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,253}", raw_email) or len(raw_email) > 320:
                    raise AuthError("Formato de e-mail de contato invalido")
                safe_email = raw_email
        encoded = hash_password(validate_password(password, normalized))
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(73662401)")
            total = int(connection.execute("SELECT COUNT(*) AS total FROM dominium_users").fetchone()["total"])
            bootstrap = total == 0 and allow_bootstrap
            role = "admin" if bootstrap else "viewer"
            status = "active" if bootstrap else "pending"
            now = _iso()
            try:
                row = connection.execute(
                    """
                    INSERT INTO dominium_users (
                        username, display_name, password_hash, role, status,
                        contact_email, created_at, approved_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (normalized, name, encoded, role, status, safe_email, now, now if bootstrap else None),
                ).fetchone()
            except Exception as exc:
                if exc.__class__.__name__ == "UniqueViolation":
                    raise AuthError("Este usuario ja foi cadastrado") from exc
                raise
            user_id = int(row["id"])
        return self.get_user(user_id)

    def get_user(self, user_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, display_name, role, status, contact_email,
                       imperium_username, imperium_controller_id,
                       created_at, approved_at, rejected_at, rejection_reason, last_login_at
                FROM dominium_users WHERE id = %s
                """,
                (int(user_id),),
            ).fetchone()
        if row is None:
            raise AuthError("Usuario nao encontrado")
        return self._with_identities(self._public_user(row))

    def _identities_for_user(self, user_id: int) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT profile_key, imperium_username, controller_id, verified_at
                FROM dominium_imperium_identities
                WHERE user_id = %s ORDER BY profile_key
                """,
                (int(user_id),),
            ).fetchall()
        return {
            str(row["profile_key"]): {
                "linked": True,
                "username": str(row["imperium_username"]),
                "controller_id": int(row["controller_id"]),
                "verified_at": str(row["verified_at"]),
            }
            for row in rows
        }

    def authenticate(self, username: object, password: object) -> dict[str, Any]:
        try:
            normalized = normalize_username(username)
        except AuthError:
            normalized = str(username or "").strip().casefold()[:48]
        supplied = str(password or "")
        now = _utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM dominium_users WHERE username = %s FOR UPDATE",
                (normalized,),
            ).fetchone()
            encoded = row["password_hash"] if row is not None else hash_password(secrets.token_urlsafe(24))
            valid = verify_password(supplied, encoded)
            locked_until = _decode_time(row["locked_until"]) if row is not None else None
            active = bool(row is not None and row["status"] == "active")
            allowed = bool(row is not None and valid and active and (locked_until is None or locked_until <= now))
            denied = not allowed
            user_id = int(row["id"]) if row is not None else 0
            if denied and row is not None:
                failures = int(row["failed_attempts"] or 0) + 1
                lock_value = _iso(
                    now + dt.timedelta(seconds=LOCK_SECONDS)
                ) if failures >= LOCK_AFTER_FAILURES else None
                connection.execute(
                    "UPDATE dominium_users SET failed_attempts = %s, locked_until = %s WHERE id = %s",
                    (failures, lock_value, user_id),
                )
            elif not denied:
                connection.execute(
                    """
                    UPDATE dominium_users
                    SET failed_attempts = 0, locked_until = NULL, last_login_at = %s
                    WHERE id = %s
                    """,
                    (_iso(now), user_id),
                )
        if denied:
            raise AuthError("Usuario ou senha invalidos, ou cadastro ainda nao aprovado")
        return self.get_user(user_id)

    def create_session(self, user_id: int, user_agent: str = "") -> tuple[str, str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _utc_now()
        idle = now + dt.timedelta(seconds=SESSION_IDLE_SECONDS)
        absolute = now + dt.timedelta(seconds=SESSION_ABSOLUTE_SECONDS)
        ua_hash = hashlib.sha256(user_agent.encode("utf-8", "ignore")).hexdigest() if user_agent else ""
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM dominium_sessions WHERE absolute_expires_at <= %s",
                (_iso(now),),
            )
            connection.execute(
                """
                INSERT INTO dominium_sessions (
                    token_hash, user_id, csrf_hash, csrf_token, created_at,
                    last_seen_at, expires_at, absolute_expires_at, user_agent_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    hashlib.sha256(token.encode("ascii")).hexdigest(), int(user_id),
                    hashlib.sha256(csrf.encode("ascii")).hexdigest(), csrf,
                    _iso(now), _iso(now), _iso(idle), _iso(absolute), ua_hash,
                ),
            )
        return token, csrf, self.get_user(user_id)

    def session(
        self,
        token: str,
        *,
        user_agent: str = "",
        touch: bool = True,
    ) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = _utc_now()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.*, u.username, u.display_name, u.role, u.status,
                       u.imperium_username, u.imperium_controller_id,
                       u.created_at AS user_created_at, u.approved_at, u.last_login_at
                FROM dominium_sessions s
                JOIN dominium_users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            expires = _decode_time(row["expires_at"])
            absolute = _decode_time(row["absolute_expires_at"])
            stored_user_agent = str(row["user_agent_hash"] or "")
            supplied_user_agent = (
                hashlib.sha256(str(user_agent or "").encode("utf-8", "ignore")).hexdigest()
                if user_agent
                else ""
            )
            user_agent_mismatch = bool(
                stored_user_agent
                and not hmac.compare_digest(stored_user_agent, supplied_user_agent)
            )
            if (
                row["status"] != "active"
                or not expires
                or not absolute
                or now >= expires
                or now >= absolute
                or user_agent_mismatch
            ):
                connection.execute("DELETE FROM dominium_sessions WHERE token_hash = %s", (token_hash,))
                return None
            if touch:
                refreshed = min(absolute, now + dt.timedelta(seconds=SESSION_IDLE_SECONDS))
                connection.execute(
                    "UPDATE dominium_sessions SET last_seen_at = %s, expires_at = %s WHERE token_hash = %s",
                    (_iso(now), _iso(refreshed), token_hash),
                )
        public_user = self._with_identities(
            {
                "id": int(row["user_id"]),
                "username": str(row["username"]),
                "display_name": str(row["display_name"]),
                "role": str(row["role"]),
                "status": str(row["status"]),
                "created_at": str(row["user_created_at"] or ""),
                "approved_at": str(row["approved_at"] or ""),
                "last_login_at": str(row["last_login_at"] or ""),
            }
        )
        return {
            "token_hash": token_hash,
            "csrf_hash": str(row["csrf_hash"]),
            "csrf_token": str(row["csrf_token"]),
            "user": public_user,
        }

    @staticmethod
    def validate_csrf(session: dict[str, Any], supplied: str) -> bool:
        actual = hashlib.sha256(str(supplied or "").encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, str(session.get("csrf_hash") or ""))

    def revoke_session(self, token: str) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM dominium_sessions WHERE token_hash = %s",
                (token_hash,),
            )

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, display_name, role, status, contact_email,
                       imperium_username, imperium_controller_id,
                       created_at, approved_at, rejected_at, rejection_reason, last_login_at
                FROM dominium_users ORDER BY created_at, id
                """
            ).fetchall()
        return [self._with_identities(self._public_user(row)) for row in rows]

    def approve(self, user_id: int, *, role: str, approved_by: int) -> dict[str, Any]:
        selected_role = str(role or "controller").strip().lower()
        if selected_role not in VALID_ROLES:
            raise AuthError("Papel de usuario invalido")
        now = _iso()
        with self._connect() as connection:
            current = connection.execute(
                "SELECT status FROM dominium_users WHERE id = %s FOR UPDATE",
                (int(user_id),),
            ).fetchone()
            if current is None:
                raise AuthError("Usuario nao encontrado")
            if current["status"] != "pending":
                raise AuthError("Apenas contas com status 'pendente' podem ser aprovadas")
            row = connection.execute(
                """
                UPDATE dominium_users
                SET status = 'active', role = %s, approved_at = %s, approved_by = %s
                WHERE id = %s
                RETURNING id
                """,
                (selected_role, now, int(approved_by), int(user_id)),
            ).fetchone()
            if row is None:
                raise AuthError("Usuario nao encontrado")
        return self.get_user(user_id)

    def reject(
        self,
        user_id: int,
        *,
        rejected_by: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Mark a pending account as rejected; rejected accounts cannot login."""
        safe_reason = str(reason or "").strip()[:500]
        now = _iso()
        with self._connect() as connection:
            current = connection.execute(
                "SELECT status FROM dominium_users WHERE id = %s FOR UPDATE",
                (int(user_id),),
            ).fetchone()
            if current is None:
                raise AuthError("Usuario nao encontrado")
            if current["status"] != "pending":
                raise AuthError("Apenas contas com status 'pendente' podem ser recusadas")
            row = connection.execute(
                """
                UPDATE dominium_users
                SET status = 'rejected', rejected_at = %s, rejected_by = %s, rejection_reason = %s
                WHERE id = %s
                RETURNING id
                """,
                (now, int(rejected_by), safe_reason or None, int(user_id)),
            ).fetchone()
            if row is None:
                raise AuthError("Usuario nao encontrado")
        return self.get_user(user_id)

    def set_imperium_identity(
        self,
        user_id: int,
        *,
        profile_key: object,
        imperium_username: object,
        controller_id: object,
        verified_by: int,
    ) -> dict[str, Any]:
        import re

        profile = str(profile_key or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{2,32}", profile):
            raise AuthError("Base Imperium invalida")
        external_username = str(imperium_username or "").strip().upper()
        try:
            external_id = int(controller_id)
        except (TypeError, ValueError) as exc:
            raise AuthError("ID de controlador Imperium invalido") from exc
        if not re.fullmatch(r"[A-Z0-9._ -]{2,80}", external_username) or external_id <= 0:
            raise AuthError("Identidade Imperium invalida")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM dominium_users WHERE id = %s",
                (int(user_id),),
            ).fetchone()
            if exists is None:
                raise AuthError("Usuario nao encontrado")
            connection.execute(
                """
                INSERT INTO dominium_imperium_identities (
                    user_id, profile_key, imperium_username, controller_id,
                    verified_at, verified_by
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(user_id, profile_key) DO UPDATE SET
                    imperium_username = EXCLUDED.imperium_username,
                    controller_id = EXCLUDED.controller_id,
                    verified_at = EXCLUDED.verified_at,
                    verified_by = EXCLUDED.verified_by
                """,
                (int(user_id), profile, external_username, external_id, _iso(), int(verified_by)),
            )
        return self.get_user(user_id)

    def audit(
        self,
        *,
        user: dict[str, Any] | None,
        action: str,
        result: str,
        request_id: str = "",
        channel: str = "dominium",
        target: str = "",
        technician: str = "",
        external_actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_metadata = json.dumps(
            metadata or {}, ensure_ascii=False, separators=(",", ":")
        )[:12000]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dominium_operator_audit (
                    created_at, user_id, username, action, result, request_id,
                    channel, target, technician, external_actor, metadata_json
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    _iso(), int(user["id"]) if user else None,
                    str(user.get("username") or "system") if user else "system",
                    str(action)[:100], str(result)[:40], str(request_id)[:80],
                    str(channel)[:80], str(target)[:160], str(technician)[:160],
                    str(external_actor)[:160], safe_metadata,
                ),
            )
