"""Strict bearer-gated VPC authorization for the DOMINIUM Backlog module.

Authentication through the Hostinger -> Cloudflare -> internal service path.
The browser never receives this secret. All other application endpoints still
use regular DOMINIUM session/CSRF protection.
"""
from __future__ import annotations

import hmac
import os
import re
from collections.abc import Mapping

_READ_PATHS=frozenset({
    "/api/backlog/year/status", "/api/backlog/year/compare",
    "/api/backlog/year/fora-rota", "/api/backlog/year/sent",
})
_WRITE_PATHS=frozenset({
    "/api/backlog/year/start", "/api/backlog/year/pause",
    "/api/backlog/year/routes", "/api/backlog/year/sent",
})
_ROLES=frozenset({"admin","controller"})
_ACTOR=re.compile(r"^[A-Za-z0-9_.%\-]{1,160}$")
_SECRET=re.compile(r"^[A-Za-z0-9_-]{43,128}$")

def _authorized_backlog_bridge(
    headers: Mapping[str,str],
    method: str,
    path: str,
    peer: str,
) -> bool:
    """Return True only for an authenticated, allowlisted local VPC request."""
    if peer not in {"127.0.0.1","::1"}:
        return False
    verb=str(method or "").upper()
    if (verb=="GET" and path not in _READ_PATHS) or (
        verb=="POST" and path not in _WRITE_PATHS
    ) or verb not in {"GET","POST"}:
        return False
    role=str(headers.get("X-Dominium-Role","")).strip()
    actor=str(headers.get("X-Dominium-Actor","")).strip()
    if role not in _ROLES or not _ACTOR.fullmatch(actor):
        return False
    expected=os.environ.get("DOMINIUM_BACKLOG_BRIDGE_TOKEN","").strip()
    if not _SECRET.fullmatch(expected):
        return False
    supplied=str(headers.get("Authorization",""))
    return hmac.compare_digest(supplied,"Bearer "+expected)
