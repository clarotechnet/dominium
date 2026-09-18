# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao envia baixas ou alteracoes ao Imperium.
#
# TOA
# - SIM - transporta pedidos de consulta operacional para o coletor autenticado.
#
# DOMINIUM COMPARTILHADO
# - Usa a ponte privada Cloudflare Worker + D1 sem persistir credenciais do TOA.
# =============================================================================
"""Cliente da fila privada Cloudflare usada pelo DOMINIUM primario.

O token desta integracao deve existir apenas no ambiente do servidor. A fila
transporta contratos e retratos operacionais sanitizados; login, senha, cookies
e cabecalhos da sessao TOA nunca passam por este modulo.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class TOACloudBridgeError(RuntimeError):
    """Falha segura e identificavel na ponte remota."""


class TOACloudClient:
    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        *,
        request_timeout: float = 20.0,
        lookup_timeout: float = 120.0,
        poll_interval: float = 1.0,
        request_retries: int = 3,
    ) -> None:
        self.base_url = str(base_url or "").strip().rstrip("/")
        self._token = str(token or "").strip()
        self.request_timeout = max(2.0, float(request_timeout))
        self.lookup_timeout = max(5.0, float(lookup_timeout))
        self.poll_interval = max(0.25, float(poll_interval))
        self.request_retries = min(5, max(1, int(request_retries)))
        self.last_error = ""
        self.last_success_at = ""

    @classmethod
    def from_environment(
        cls, credentials_path: Path | None = None
    ) -> "TOACloudClient":
        if credentials_path is None:
            credentials_path = (
                Path(__file__).resolve().parent
                / "config"
                / "toa_cloud_bridge_credentials.dat"
            )
        base_url = os.environ.get("DOMINIUM_TOA_BRIDGE_URL", "")
        token = os.environ.get("DOMINIUM_TOA_PRIMARY_TOKEN", "")
        if not base_url or not token:
            try:
                from datasnap_client import unprotect_secret

                stored = json.loads(
                    unprotect_secret(credentials_path.read_bytes()).decode("utf-8")
                )
                if isinstance(stored, dict):
                    base_url = base_url or str(stored.get("base_url") or "")
                    token = token or str(stored.get("primary_token") or "")
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        return cls(
            base_url,
            token,
            request_timeout=float(
                os.environ.get("DOMINIUM_TOA_BRIDGE_REQUEST_TIMEOUT", "20")
            ),
            lookup_timeout=float(
                os.environ.get("DOMINIUM_TOA_BRIDGE_LOOKUP_TIMEOUT", "120")
            ),
            poll_interval=float(
                os.environ.get("DOMINIUM_TOA_BRIDGE_POLL_INTERVAL", "1")
            ),
        )

    @property
    def configured(self) -> bool:
        secure_remote = self.base_url.startswith("https://")
        local_development = self.base_url.startswith((
            "http://127.0.0.1:", "http://localhost:",
        ))
        return (secure_remote or local_development) and bool(self._token)

    def public_state(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "base_url": self.base_url if self.configured else "",
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
        }

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise TOACloudBridgeError("Ponte Cloudflare do TOA nao configurada")
        payload = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "DOMINIUM-TechNet/1.0 (Windows; operacao-autorizada)",
        }
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=payload,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.request_timeout
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error")
            except Exception:
                detail = ""
            raise TOACloudBridgeError(
                f"Ponte TOA respondeu HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise TOACloudBridgeError(f"Ponte TOA indisponivel: {exc}") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise TOACloudBridgeError(
                f"Resposta invalida da ponte TOA: {result.get('error', 'desconhecida') if isinstance(result, dict) else 'desconhecida'}"
            )
        return result

    def _request_with_retry(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retry the same safe/idempotent bridge request after network stalls."""
        last_error: TOACloudBridgeError | None = None
        for attempt in range(self.request_retries):
            try:
                return self._request(method, path, body)
            except TOACloudBridgeError as exc:
                last_error = exc
                if attempt + 1 >= self.request_retries:
                    raise
                time.sleep(min(2.0, 0.5 * (2 ** attempt)))
        raise last_error or TOACloudBridgeError("Ponte TOA indisponivel")

    def lookup_contract(self, contract: str) -> dict[str, Any]:
        contract_digits = "".join(character for character in str(contract) if character.isdigit())
        idempotency_key = f"dominium:{contract_digits}:{uuid.uuid4()}"
        try:
            create_body = {
                "contract": contract_digits,
                "idempotency_key": idempotency_key,
                "requested_by": "dominium-primary",
            }
            created = self._request_with_retry(
                "POST",
                "/v1/lookups",
                create_body,
            )
            job = created.get("job") if isinstance(created.get("job"), dict) else {}
            job_id = str(job.get("id") or "")
            if not job_id:
                raise TOACloudBridgeError("Ponte TOA nao retornou o identificador da consulta")

            deadline = time.monotonic() + self.lookup_timeout
            while time.monotonic() < deadline:
                current = self._request_with_retry(
                    "GET", f"/v1/lookups/{job_id}"
                )
                job = current.get("job") if isinstance(current.get("job"), dict) else {}
                status = str(job.get("status") or "")
                if status == "completed":
                    snapshot = job.get("result")
                    if not isinstance(snapshot, dict):
                        raise TOACloudBridgeError("Consulta concluida sem retrato operacional")
                    self.last_error = ""
                    self.last_success_at = time.strftime(
                        "%Y-%m-%dT%H:%M:%S%z", time.localtime()
                    )
                    return snapshot
                if status == "failed":
                    raise TOACloudBridgeError(
                        f"Coletor TOA recusou a consulta: {job.get('error_code') or 'toa_lookup_failed'}"
                    )
                time.sleep(self.poll_interval)
            raise TOACloudBridgeError(
                "Tempo esgotado aguardando o coletor TOA; a consulta permanece segura na fila"
            )
        except Exception as exc:
            self.last_error = str(exc)
            raise
