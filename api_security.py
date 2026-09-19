# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO DIRETO - infraestrutura comum, sem regra de negocio Imperium.
#
# TOA
# - NAO DIRETO - infraestrutura comum, sem regra de negocio TOA.
#
# DOMINIUM COMPARTILHADO
# - SIM - seguranca, interface, voz, empacotamento ou inicializacao.
#
# Categoria deste arquivo: COMPARTILHADO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
"""Controles centrais de seguranca para as integracoes do DOMINIUM.

Este modulo nao expoe politicas na interface. Ele concentra inventario,
validacao de origem, limites de requisicao e cabecalhos defensivos para que
os mesmos controles sejam aplicados a todas as rotas locais.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
JSON_CONTENT_TYPES = frozenset({"application/json", "application/problem+json"})

API_INVENTORY = (
    {
        "name": "DOMINIUM Local API",
        "transport": "HTTP loopback",
        "exposure": "127.0.0.1 only",
        "authentication": "same-origin local application",
        "writes": True,
        "controls": ("host allowlist", "origin validation", "rate limits", "body limits"),
    },
    {
        "name": "Imperium Official API (Oracle-backed)",
        "transport": "HTTPS",
        "exposure": "fixed outbound host",
        "authentication": "short-lived JWT",
        "writes": True,
        "controls": ("TLS CA validation", "destination allowlist", "timeouts", "no blind retry"),
    },
    {
        "name": "Imperium DataSnap",
        "transport": "TCP fixed profiles",
        "exposure": "outbound only",
        "authentication": "encrypted local credential file",
        "writes": True,
        "controls": ("profile allowlist", "operation gate", "scope validation", "audit trail"),
    },
    {
        "name": "DOMINIUM TOA Connector",
        "transport": "authenticated browser session / sanitized local cache",
        "exposure": "outbound TOA session and loopback API",
        "authentication": "operator-authorized isolated browser session",
        "writes": False,
        "controls": (
            "local session",
            "input limits",
            "contract validation",
            "personal-data minimization",
            "stale-data labeling",
            "read-only lookup",
        ),
    },
    {
        "name": "FlowScope",
        "transport": "HTTP loopback",
        "exposure": "127.0.0.1 only",
        "authentication": "local application",
        "writes": False,
        "controls": ("read-only", "bounded upload", "no Imperium connection", "local processing"),
    },
)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Vary": "Origin, Sec-Fetch-Site",
}

SENSITIVE_LOG_VALUE = re.compile(
    r"(?i)([?&](?:password|passwd|token|authorization|secret|serial|contract|contrato)=)[^&\s]+"
)


@dataclass(frozen=True)
class RequestDecision:
    allowed: bool
    status: int = 200
    reason: str = ""


def _host_name(raw_host: str) -> str:
    value = str(raw_host or "").strip().lower()
    if value.startswith("["):
        return value.split("]", 1)[0].lstrip("[")
    return value.split(":", 1)[0]


def _public_origin():
    raw = os.environ.get("DOMINIUM_PUBLIC_ORIGIN", "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return None
    return parsed


def validate_local_request(
    headers: Mapping[str, str],
    method: str,
    *,
    require_json: bool = True,
) -> RequestDecision:
    """Bloqueia DNS rebinding, CSRF e POSTs simples vindos de outro site."""

    target_host = str(headers.get("Host", "")).strip().lower()
    host = _host_name(target_host)
    public = _public_origin()
    local_request = host in LOCAL_HOSTS
    public_request = bool(public and target_host == public.netloc.lower())
    if not (local_request or public_request):
        return RequestDecision(False, 403, "Host nao autorizado")

    verb = str(method or "GET").upper()
    fetch_site = str(headers.get("Sec-Fetch-Site", "")).strip().lower()
    if fetch_site in {"cross-site", "same-site"} and verb not in SAFE_METHODS:
        return RequestDecision(False, 403, "Origem cruzada bloqueada")

    if verb not in SAFE_METHODS:
        origin = str(headers.get("Origin", "")).strip()
        referer = str(headers.get("Referer", "")).strip()
        source = origin or referer
        if source:
            parsed = urlparse(source)
            if local_request:
                valid_source = (
                    parsed.scheme == "http"
                    and (parsed.hostname or "").lower() in LOCAL_HOSTS
                    and parsed.netloc.lower() == target_host
                )
            else:
                valid_source = bool(
                    public
                    and parsed.scheme == public.scheme
                    and parsed.netloc.lower() == public.netloc.lower()
                    and target_host == public.netloc.lower()
                )
            if not valid_source:
                return RequestDecision(False, 403, "Origem da requisicao nao autorizada")
        content_type = str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        if require_json and content_type not in JSON_CONTENT_TYPES:
            return RequestDecision(False, 415, "A API aceita somente JSON")

    return RequestDecision(True)


def redact_log_text(value: object) -> str:
    text = str(value or "")
    return SENSITIVE_LOG_VALUE.sub(r"\1[redacted]", text).replace("\r", " ").replace("\n", " ")[:8192]


def rate_limit_for(path: str) -> tuple[int, float]:
    if path == "/api/auth/login":
        return 8, 60.0
    if path == "/api/auth/register":
        return 3, 60.0
    if path in {"/api/imports/preview", "/api/imports/commit", "/api/toa-capture/analyze"}:
        return 12, 60.0
    if path.startswith("/api/toa/v1/contracts/"):
        return 30, 60.0
    if any(part in path for part in ("/close", "/writeoff", "/bulk-create", "/move-installer", "/transfer-serial")):
        return 30, 60.0
    return 120, 60.0


class LocalRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def allow(self, key: str, limit: int, window_seconds: float, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        cutoff = current - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(current)
            if len(self._events) > 2048:
                for old_key in list(self._events)[:256]:
                    if not self._events[old_key] or self._events[old_key][-1] <= cutoff:
                        self._events.pop(old_key, None)
            return True


LOCAL_RATE_LIMITER = LocalRateLimiter()
