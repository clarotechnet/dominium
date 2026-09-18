from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import threading
from typing import Any

from auth_store import (
    AuthError,
    LOCK_AFTER_FAILURES,
    LOCK_SECONDS,
    SESSION_ABSOLUTE_SECONDS,
    SESSION_IDLE_SECONDS,
    VALID_ROLES,
    normalize_username,
    validate_password,
)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="seconds")


def _parse_time(value: object) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _data(response: Any) -> Any:
    if response is None:
        return None
    if isinstance(response, dict):
        return response.get("data", response)
    return getattr(response, "data", None)


def _auth_user_id(response: Any) -> str:
    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user")
    if isinstance(user, dict):
        return str(user.get("id") or "")
    return str(getattr(user, "id", "") or "")


class SupabaseAuthStore:
    """DOMINIUM auth backend backed by Supabase Auth + Postgres.

    Passwords are owned by Supabase Auth. DOMINIUM keeps only profile, role,
    session and audit metadata in public tables accessed by the server secret.
    """

    PROFILE_TABLE = "dominium_profiles"
    SESSION_TABLE = "dominium_sessions"
    IDENTITY_TABLE = "dominium_imperium_identities"
    AUDIT_TABLE = "dominium_operator_audit"

    def __init__(self, url: str, secret_key: str, *, email_domain: str = "") -> None:
        try:
            from supabase import create_client
            try:
                from supabase.lib.client_options import SyncClientOptions as ClientOptions
            except ImportError:
                from supabase.lib.client_options import ClientOptions
        except ImportError as exc:
            raise RuntimeError(
                "Backend Supabase selecionado, mas o pacote 'supabase' nao esta instalado"
            ) from exc
        self.url = str(url or "").strip().rstrip("/")
        self.secret_key = str(secret_key or "").strip()
        if not self.url.startswith("https://") or not self.secret_key:
            raise RuntimeError("SUPABASE_URL e SUPABASE_SECRET_KEY sao obrigatorios")
        options = ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        )
        self._create_client = create_client
        self._client_options = options
        self.client = create_client(self.url, self.secret_key, options=options)
        self.email_domain = (
            str(email_domain or "").strip().lower()
            or os.environ.get("DOMINIUM_AUTH_EMAIL_DOMAIN", "").strip().lower()
            or "auth.dominium.invalid"
        )
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}|auth\.dominium\.invalid", self.email_domain):
            raise RuntimeError("DOMINIUM_AUTH_EMAIL_DOMAIN invalido")
        self._lock = threading.RLock()

    @classmethod
    def from_environment(cls) -> "SupabaseAuthStore":
        secret = (
            os.environ.get("SUPABASE_SECRET_KEY", "").strip()
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        )
        return cls(
            os.environ.get("SUPABASE_URL", ""),
            secret,
            email_domain=os.environ.get("DOMINIUM_AUTH_EMAIL_DOMAIN", ""),
        )

    def _email(self, username: str) -> str:
        return f"{normalize_username(username)}@{self.email_domain}"

    def _fresh_auth_client(self):
        return self._create_client(
            self.url,
            self.secret_key,
            options=self._client_options,
        )

    def _profile_row(self, user_id: int) -> dict[str, Any]:
        response = (
            self.client.table(self.PROFILE_TABLE)
            .select("*")
            .eq("id", int(user_id))
            .limit(1)
            .execute()
        )
        rows = _data(response) or []
        if not rows:
            raise AuthError("Usuario nao encontrado")
        return dict(rows[0])

    def _profile_by_username(self, username: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.PROFILE_TABLE)
            .select("*")
            .eq("username", username)
            .limit(1)
            .execute()
        )
        rows = _data(response) or []
        return dict(rows[0]) if rows else None

    def _identities_for_user(self, user_id: int) -> dict[str, dict[str, Any]]:
        response = (
            self.client.table(self.IDENTITY_TABLE)
            .select("profile_key,imperium_username,controller_id,verified_at")
            .eq("user_id", int(user_id))
            .execute()
        )
        rows = _data(response) or []
        return {
            str(row["profile_key"]): {
                "linked": True,
                "username": str(row["imperium_username"]),
                "controller_id": int(row["controller_id"]),
                "verified_at": str(row.get("verified_at") or ""),
            }
            for row in rows
        }

    def _public_user(self, row: dict[str, Any]) -> dict[str, Any]:
        user_id = int(row["id"])
        identities = self._identities_for_user(user_id)
        return {
            "id": user_id,
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "status": str(row["status"]),
            "contact_email": str(row["contact_email"]) if row.get("contact_email") else "",
            "imperium_identities": identities,
            "imperium_identity": {
                "linked": bool(identities),
                "profiles": sorted(identities),
            },
            "created_at": str(row.get("created_at") or ""),
            "approved_at": str(row.get("approved_at") or ""),
            "rejected_at": str(row.get("rejected_at") or ""),
            "rejection_reason": str(row.get("rejection_reason") or ""),
            "last_login_at": str(row.get("last_login_at") or ""),
        }

    def has_users(self) -> bool:
        response = self.client.table(self.PROFILE_TABLE).select("id").limit(1).execute()
        return bool(_data(response) or [])

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
        # Validate contact_email format if supplied (it is metadata only, never an auth credential)
        safe_email: str | None = None
        if contact_email:
            raw_email = str(contact_email).strip()
            if raw_email:
                import re as _re
                if not _re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,253}", raw_email) or len(raw_email) > 320:
                    raise AuthError("Formato de e-mail de contato invalido")
                safe_email = raw_email
        secret = validate_password(password, normalized)
        with self._lock:
            if self._profile_by_username(normalized) is not None:
                raise AuthError("Este usuario ja foi cadastrado")
            bootstrap = bool(allow_bootstrap and not self.has_users())
            role = "admin" if bootstrap else "viewer"
            status = "active" if bootstrap else "pending"
            created_auth_id = ""
            try:
                auth_response = self.client.auth.admin.create_user(
                    {
                        "email": self._email(normalized),
                        "password": secret,
                        "email_confirm": True,
                        "user_metadata": {
                            "dominium_username": normalized,
                            "display_name": name,
                        },
                    }
                )
                created_auth_id = _auth_user_id(auth_response)
                if not created_auth_id:
                    raise RuntimeError("Supabase nao retornou o id do usuario")
                now = _iso()
                insert = (
                    self.client.table(self.PROFILE_TABLE)
                    .insert(
                        {
                            "auth_user_id": created_auth_id,
                            "username": normalized,
                            "display_name": name,
                            "role": role,
                            "status": status,
                            "contact_email": safe_email,
                            "created_at": now,
                            "approved_at": now if bootstrap else None,
                        }
                    )
                    .execute()
                )
                rows = _data(insert) or []
                if not rows:
                    raise RuntimeError("Perfil DOMINIUM nao foi criado")
                return self._public_user(dict(rows[0]))
            except AuthError:
                raise
            except Exception as exc:
                if created_auth_id:
                    try:
                        self.client.auth.admin.delete_user(created_auth_id)
                    except Exception:
                        pass
                message = str(exc).casefold()
                if "already" in message or "duplicate" in message or "unique" in message:
                    raise AuthError("Este usuario ja foi cadastrado") from exc
                raise AuthError("Nao foi possivel criar o usuario agora") from exc

    def get_user(self, user_id: int) -> dict[str, Any]:
        return self._public_user(self._profile_row(int(user_id)))

    def _record_failed_login(self, row: dict[str, Any]) -> None:
        failures = int(row.get("failed_attempts") or 0) + 1
        locked_until = None
        if failures >= LOCK_AFTER_FAILURES:
            locked_until = _iso(_utc_now() + dt.timedelta(seconds=LOCK_SECONDS))
        (
            self.client.table(self.PROFILE_TABLE)
            .update({"failed_attempts": failures, "locked_until": locked_until})
            .eq("id", int(row["id"]))
            .execute()
        )

    def authenticate(self, username: object, password: object) -> dict[str, Any]:
        try:
            normalized = normalize_username(username)
        except AuthError:
            normalized = str(username or "").strip().casefold()[:48]
        supplied = str(password or "")
        with self._lock:
            row = self._profile_by_username(normalized)
            now = _utc_now()
            locked_until = _parse_time(row.get("locked_until")) if row else None
            allowed = bool(
                row
                and row.get("status") == "active"
                and (locked_until is None or locked_until <= now)
            )
            if not allowed:
                if row:
                    self._record_failed_login(row)
                raise AuthError("Usuario ou senha invalidos, ou cadastro ainda nao aprovado")
            try:
                auth_client = self._fresh_auth_client()
                auth_client.auth.sign_in_with_password(
                    {"email": self._email(normalized), "password": supplied}
                )
            except Exception as exc:
                self._record_failed_login(row)
                raise AuthError(
                    "Usuario ou senha invalidos, ou cadastro ainda nao aprovado"
                ) from exc
            (
                self.client.table(self.PROFILE_TABLE)
                .update(
                    {
                        "failed_attempts": 0,
                        "locked_until": None,
                        "last_login_at": _iso(now),
                    }
                )
                .eq("id", int(row["id"]))
                .execute()
            )
            return self.get_user(int(row["id"]))

    def create_session(
        self, user_id: int, user_agent: str = ""
    ) -> tuple[str, str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _utc_now()
        idle = now + dt.timedelta(seconds=SESSION_IDLE_SECONDS)
        absolute = now + dt.timedelta(seconds=SESSION_ABSOLUTE_SECONDS)
        payload = {
            "token_hash": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "user_id": int(user_id),
            "csrf_hash": hashlib.sha256(csrf.encode("ascii")).hexdigest(),
            "csrf_token": csrf,
            "created_at": _iso(now),
            "last_seen_at": _iso(now),
            "expires_at": _iso(idle),
            "absolute_expires_at": _iso(absolute),
            "user_agent_hash": hashlib.sha256(
                str(user_agent or "").encode("utf-8", "ignore")
            ).hexdigest()
            if user_agent
            else "",
        }
        with self._lock:
            (
                self.client.table(self.SESSION_TABLE)
                .delete()
                .lte("absolute_expires_at", _iso(now))
                .execute()
            )
            self.client.table(self.SESSION_TABLE).insert(payload).execute()
        return token, csrf, self.get_user(int(user_id))

    def session(self, token: str, *, touch: bool = True) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        response = (
            self.client.table(self.SESSION_TABLE)
            .select("*")
            .eq("token_hash", token_hash)
            .limit(1)
            .execute()
        )
        rows = _data(response) or []
        if not rows:
            return None
        row = dict(rows[0])
        now = _utc_now()
        expires = _parse_time(row.get("expires_at"))
        absolute = _parse_time(row.get("absolute_expires_at"))
        try:
            user = self.get_user(int(row["user_id"]))
        except AuthError:
            user = None
        if (
            user is None
            or user.get("status") != "active"
            or expires is None
            or absolute is None
            or now >= expires
            or now >= absolute
        ):
            self.client.table(self.SESSION_TABLE).delete().eq(
                "token_hash", token_hash
            ).execute()
            return None
        if touch:
            refreshed = min(
                absolute, now + dt.timedelta(seconds=SESSION_IDLE_SECONDS)
            )
            (
                self.client.table(self.SESSION_TABLE)
                .update({"last_seen_at": _iso(now), "expires_at": _iso(refreshed)})
                .eq("token_hash", token_hash)
                .execute()
            )
        return {
            "token_hash": token_hash,
            "csrf_hash": str(row.get("csrf_hash") or ""),
            "csrf_token": str(row.get("csrf_token") or ""),
            "user": user,
        }

    @staticmethod
    def validate_csrf(session: dict[str, Any], supplied: str) -> bool:
        actual = hashlib.sha256(str(supplied or "").encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, str(session.get("csrf_hash") or ""))

    def revoke_session(self, token: str) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.client.table(self.SESSION_TABLE).delete().eq(
            "token_hash", token_hash
        ).execute()

    def list_users(self) -> list[dict[str, Any]]:
        response = (
            self.client.table(self.PROFILE_TABLE)
            .select("*")
            .order("created_at")
            .order("id")
            .execute()
        )
        return [self._public_user(dict(row)) for row in (_data(response) or [])]

    def approve(self, user_id: int, *, role: str, approved_by: int) -> dict[str, Any]:
        selected_role = str(role or "controller").strip().lower()
        if selected_role not in VALID_ROLES:
            raise AuthError("Papel de usuario invalido")
        # Validate that user is currently pending before approving
        current = self._profile_row(int(user_id))
        if current.get("status") != "pending":
            raise AuthError("Apenas contas com status 'pendente' podem ser aprovadas")
        response = (
            self.client.table(self.PROFILE_TABLE)
            .update(
                {
                    "status": "active",
                    "role": selected_role,
                    "approved_at": _iso(),
                    "approved_by": int(approved_by),
                }
            )
            .eq("id", int(user_id))
            .execute()
        )
        if not (_data(response) or []):
            raise AuthError("Usuario nao encontrado")
        return self.get_user(int(user_id))

    def reject(
        self,
        user_id: int,
        *,
        rejected_by: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Mark a pending account as rejected; rejected accounts cannot login."""
        # Validate that user is currently pending before rejecting
        current = self._profile_row(int(user_id))
        if current.get("status") != "pending":
            raise AuthError("Apenas contas com status 'pendente' podem ser recusadas")
        safe_reason = str(reason or "").strip()[:500]
        response = (
            self.client.table(self.PROFILE_TABLE)
            .update(
                {
                    "status": "rejected",
                    "rejected_at": _iso(),
                    "rejected_by": int(rejected_by),
                    "rejection_reason": safe_reason or None,
                }
            )
            .eq("id", int(user_id))
            .execute()
        )
        if not (_data(response) or []):
            raise AuthError("Usuario nao encontrado")
        return self.get_user(int(user_id))

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
        if (
            not re.fullmatch(r"[A-Z0-9._ -]{2,80}", external_username)
            or external_id <= 0
        ):
            raise AuthError("Identidade Imperium invalida")
        self.get_user(int(user_id))
        payload = {
            "user_id": int(user_id),
            "profile_key": profile,
            "imperium_username": external_username,
            "controller_id": external_id,
            "verified_at": _iso(),
            "verified_by": int(verified_by),
        }
        (
            self.client.table(self.IDENTITY_TABLE)
            .upsert(payload, on_conflict="user_id,profile_key")
            .execute()
        )
        return self.get_user(int(user_id))

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
        import json

        payload = {
            "created_at": _iso(),
            "user_id": int(user["id"]) if user else None,
            "username": str(user.get("username") or "system") if user else "system",
            "action": str(action)[:100],
            "result": str(result)[:40],
            "request_id": str(request_id)[:80],
            "channel": str(channel)[:80],
            "target": str(target)[:160],
            "technician": str(technician)[:160],
            "external_actor": str(external_actor)[:160],
            "metadata_json": json.dumps(
                metadata or {}, ensure_ascii=False, separators=(",", ":")
            )[:12000],
        }
        self.client.table(self.AUDIT_TABLE).insert(payload).execute()
