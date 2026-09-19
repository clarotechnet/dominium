# =============================================================================
# DOMINIUM COMPARTILHADO | AUTENTICACAO, SESSOES E AUDITORIA DO OPERADOR
#
# IMPERIUM
# - Mantem apenas o vinculo de identidade do operador; nunca armazena a senha
#   do Imperium nesta base.
#
# TOA
# - Nao acessa nem persiste credenciais do TOA.
# =============================================================================
"""Autenticacao local do DOMINIUM.

As contas desta base identificam quem operou o painel. Elas nao substituem a
identidade externa usada pelo Imperium e nao guardam senhas do TOA/Imperium.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any


USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,47}$")
VALID_ROLES = frozenset({"admin", "controller", "viewer"})
SESSION_IDLE_SECONDS = 8 * 60 * 60
SESSION_ABSOLUTE_SECONDS = 12 * 60 * 60
LOCK_AFTER_FAILURES = 5
LOCK_SECONDS = 5 * 60
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 3


class AuthError(ValueError):
    """Erro seguro e apresentavel do fluxo de autenticacao."""


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


def _decode_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def normalize_username(value: object) -> str:
    username = str(value or "").strip().casefold()
    if not USERNAME_RE.fullmatch(username):
        raise AuthError(
            "Use de 3 a 48 caracteres: letras, numeros, ponto, hifen ou sublinhado"
        )
    return username


def validate_password(password: object, username: str = "") -> str:
    value = str(password or "")
    if len(value) < 12 or len(value) > 128:
        raise AuthError("A senha do DOMINIUM deve ter entre 12 e 128 caracteres")
    if username and value.casefold() == username.casefold():
        raise AuthError("A senha nao pode ser igual ao usuario")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
        maxmem=256 * 1024 * 1024,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_n, raw_r, raw_p, raw_salt, raw_digest = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        expected = base64.urlsafe_b64decode(raw_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(raw_salt.encode("ascii")),
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected),
            maxmem=256 * 1024 * 1024,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 20000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'controller', 'viewer')),
                    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'disabled', 'rejected')),
                    contact_email TEXT,
                    imperium_username TEXT NOT NULL DEFAULT '',
                    imperium_controller_id INTEGER,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by INTEGER REFERENCES users(id),
                    rejected_at TEXT,
                    rejected_by INTEGER REFERENCES users(id),
                    rejection_reason TEXT,
                    last_login_at TEXT,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    csrf_token TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    user_agent_hash TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS imperium_identities (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    profile_key TEXT NOT NULL,
                    imperium_username TEXT NOT NULL,
                    controller_id INTEGER NOT NULL,
                    verified_at TEXT NOT NULL,
                    verified_by INTEGER REFERENCES users(id),
                    PRIMARY KEY (user_id, profile_key)
                );
                CREATE TABLE IF NOT EXISTS operator_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    target TEXT NOT NULL,
                    technician TEXT NOT NULL,
                    external_actor TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_created ON operator_audit(created_at DESC);
                """
            )
            # Runtime migrations for pre-existing databases (idempotent)
            user_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(users)")
            }
            session_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if "csrf_token" not in session_columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN csrf_token TEXT NOT NULL DEFAULT ''"
                )
            if "contact_email" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN contact_email TEXT")
            if "rejected_at" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN rejected_at TEXT")
            if "rejected_by" not in user_columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN rejected_by INTEGER REFERENCES users(id)"
                )
            if "rejection_reason" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN rejection_reason TEXT")

    def has_users(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
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
            raw_email = str(contact_email).strip()
            if raw_email:
                if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,253}", raw_email) or len(raw_email) > 320:
                    raise AuthError("Formato de e-mail de contato invalido")
                safe_email = raw_email
        secret = validate_password(password, normalized)
        encoded = hash_password(secret)
        with self._lock, self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            bootstrap = total == 0 and allow_bootstrap
            role = "admin" if bootstrap else "viewer"
            status = "active" if bootstrap else "pending"
            now = _iso()
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        username, display_name, password_hash, role, status,
                        contact_email, created_at, approved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (normalized, name, encoded, role, status, safe_email, now, now if bootstrap else None),
                )
            except sqlite3.IntegrityError as exc:
                raise AuthError("Este usuario ja foi cadastrado") from exc
            user_id = int(cursor.lastrowid)
        return self.get_user(user_id)

    def get_user(self, user_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, display_name, role, status, contact_email,
                       imperium_username, imperium_controller_id,
                       created_at, approved_at, rejected_at, rejection_reason, last_login_at
                FROM users WHERE id = ?
                """,
                (int(user_id),),
            ).fetchone()
        if row is None:
            raise AuthError("Usuario nao encontrado")
        return self._with_identities(self._public_user(row))

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict[str, Any]:
        controller_id = row["imperium_controller_id"]
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "status": str(row["status"]),
            "contact_email": str(row["contact_email"]) if row["contact_email"] else "",
            "imperium_identity": {
                "linked": bool(row["imperium_username"] and controller_id),
                "username": str(row["imperium_username"] or ""),
                "controller_id": int(controller_id) if controller_id else None,
            },
            "created_at": str(row["created_at"] or ""),
            "approved_at": str(row["approved_at"] or ""),
            "rejected_at": str(row["rejected_at"] or ""),
            "rejection_reason": str(row["rejection_reason"] or ""),
            "last_login_at": str(row["last_login_at"] or ""),
        }

    def _identities_for_user(self, user_id: int) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT profile_key, imperium_username, controller_id, verified_at
                FROM imperium_identities WHERE user_id = ? ORDER BY profile_key
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

    def _with_identities(self, user: dict[str, Any]) -> dict[str, Any]:
        identities = self._identities_for_user(int(user["id"]))
        user["imperium_identities"] = identities
        user["imperium_identity"] = {
            "linked": bool(identities),
            "profiles": sorted(identities),
        }
        return user

    def authenticate(self, username: object, password: object) -> dict[str, Any]:
        try:
            normalized = normalize_username(username)
        except AuthError:
            normalized = str(username or "").strip().casefold()[:48]
        supplied = str(password or "")
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (normalized,)).fetchone()
            # Executa um hash mesmo para usuario inexistente para reduzir diferenca de tempo.
            encoded = row["password_hash"] if row is not None else hash_password(secrets.token_urlsafe(24))
            valid = verify_password(supplied, encoded)
            now = _utc_now()
            locked_until = _decode_time(row["locked_until"]) if row is not None else None
            active = bool(row is not None and row["status"] == "active")
            denied = not (
                row is not None
                and valid
                and active
                and (locked_until is None or locked_until <= now)
            )
            if denied and row is not None:
                failures = int(row["failed_attempts"] or 0) + 1
                lock_value = _iso(now + dt.timedelta(seconds=LOCK_SECONDS)) if failures >= LOCK_AFTER_FAILURES else None
                connection.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (failures, lock_value, int(row["id"])),
                )
            elif not denied:
                connection.execute(
                    """
                    UPDATE users
                    SET failed_attempts = 0, locked_until = NULL, last_login_at = ?
                    WHERE id = ?
                    """,
                    (_iso(now), int(row["id"])),
                )
                refreshed = connection.execute("SELECT * FROM users WHERE id = ?", (int(row["id"]),)).fetchone()
        if denied:
            raise AuthError("Usuario ou senha invalidos, ou cadastro ainda nao aprovado")
        return self._with_identities(self._public_user(refreshed))

    def create_session(self, user_id: int, user_agent: str = "") -> tuple[str, str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _utc_now()
        idle = now + dt.timedelta(seconds=SESSION_IDLE_SECONDS)
        absolute = now + dt.timedelta(seconds=SESSION_ABSOLUTE_SECONDS)
        user_agent_hash = hashlib.sha256(user_agent.encode("utf-8", "ignore")).hexdigest() if user_agent else ""
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE absolute_expires_at <= ?", (_iso(now),))
            connection.execute(
                """
                INSERT INTO sessions (
                    token_hash, user_id, csrf_hash, csrf_token, created_at, last_seen_at,
                    expires_at, absolute_expires_at, user_agent_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hashlib.sha256(token.encode("ascii")).hexdigest(),
                    int(user_id),
                    hashlib.sha256(csrf.encode("ascii")).hexdigest(),
                    csrf,
                    _iso(now),
                    _iso(now),
                    _iso(idle),
                    _iso(absolute),
                    user_agent_hash,
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
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.*, u.username, u.display_name, u.role, u.status,
                       u.imperium_username, u.imperium_controller_id,
                       u.created_at AS user_created_at, u.approved_at, u.last_login_at
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
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
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
            if touch:
                refreshed = min(absolute, now + dt.timedelta(seconds=SESSION_IDLE_SECONDS))
                connection.execute(
                    "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                    (_iso(now), _iso(refreshed), token_hash),
                )
        public_user = self._with_identities({
                "id": int(row["user_id"]),
                "username": str(row["username"]),
                "display_name": str(row["display_name"]),
                "role": str(row["role"]),
                "status": str(row["status"]),
                "created_at": str(row["user_created_at"] or ""),
                "approved_at": str(row["approved_at"] or ""),
                "last_login_at": str(row["last_login_at"] or ""),
            })
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
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
            )

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, display_name, role, status, contact_email,
                       imperium_username, imperium_controller_id,
                       created_at, approved_at, rejected_at, rejection_reason, last_login_at
                FROM users ORDER BY created_at, id
                """
            ).fetchall()
        return [self._with_identities(self._public_user(row)) for row in rows]

    def approve(self, user_id: int, *, role: str, approved_by: int) -> dict[str, Any]:
        selected_role = str(role or "controller").strip().lower()
        if selected_role not in VALID_ROLES:
            raise AuthError("Papel de usuario invalido")
        now = _iso()
        with self._lock, self._connect() as connection:
            current = connection.execute(
                "SELECT status FROM users WHERE id = ?", (int(user_id),)
            ).fetchone()
            if current is None:
                raise AuthError("Usuario nao encontrado")
            if current["status"] != "pending":
                raise AuthError("Apenas contas com status 'pendente' podem ser aprovadas")
            cursor = connection.execute(
                """
                UPDATE users SET status = 'active', role = ?, approved_at = ?, approved_by = ?
                WHERE id = ?
                """,
                (selected_role, now, int(approved_by), int(user_id)),
            )
            if cursor.rowcount != 1:
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
        with self._lock, self._connect() as connection:
            current = connection.execute(
                "SELECT status FROM users WHERE id = ?", (int(user_id),)
            ).fetchone()
            if current is None:
                raise AuthError("Usuario nao encontrado")
            if current["status"] != "pending":
                raise AuthError("Apenas contas com status 'pendente' podem ser recusadas")
            cursor = connection.execute(
                """
                UPDATE users SET status = 'rejected', rejected_at = ?, rejected_by = ?,
                                 rejection_reason = ?
                WHERE id = ?
                """,
                (now, int(rejected_by), safe_reason or None, int(user_id)),
            )
            if cursor.rowcount != 1:
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
        with self._lock, self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if exists is None:
                raise AuthError("Usuario nao encontrado")
            connection.execute(
                """
                INSERT INTO imperium_identities (
                    user_id, profile_key, imperium_username, controller_id,
                    verified_at, verified_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, profile_key) DO UPDATE SET
                    imperium_username = excluded.imperium_username,
                    controller_id = excluded.controller_id,
                    verified_at = excluded.verified_at,
                    verified_by = excluded.verified_by
                """,
                (
                    int(user_id), profile, external_username, external_id,
                    _iso(), int(verified_by),
                ),
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
        safe_metadata = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))[:12000]
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO operator_audit (
                    created_at, user_id, username, action, result, request_id,
                    channel, target, technician, external_actor, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _iso(),
                    int(user["id"]) if user else None,
                    str(user.get("username") or "system") if user else "system",
                    str(action)[:100],
                    str(result)[:40],
                    str(request_id)[:80],
                    str(channel)[:80],
                    str(target)[:160],
                    str(technician)[:160],
                    str(external_actor)[:160],
                    safe_metadata,
                ),
            )
