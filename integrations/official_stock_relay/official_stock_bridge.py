"""Read-only official Imperium inventory for the authenticated private DESC relay.

No stock transfers, order closures, or user passwords are accepted by this service.
"""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

APP_ROOT = Path(r"C:\DominiumMain")
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from datasnap_client import load_credentials
from imperium_http_api import ImperiumHTTPClient

CATALOG_ROUTE = "/api/imperium-official/stocks"
ITEMS_ROUTE = re.compile(r"^/api/imperium-official/stocks/([1-9][0-9]{0,9})/items$")
PROFILES = frozenset({"natal", "fortaleza"})
CREDENTIALS_FILE = APP_ROOT / "config" / "imperium_http_credentials.dat"


def parse_route(method: str, target: str):
    if len(target) > 1024 or not target.startswith("/") or target.startswith("//"):
        return None
    parsed = urlsplit(target)
    match = ITEMS_ROUTE.fullmatch(parsed.path)
    if parsed.path != CATALOG_ROUTE and not match:
        return None
    if method != "GET" or parsed.fragment:
        raise ValueError("Metodo ou URL nao permitidos")
    try:
        params = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=False)
    except ValueError as exc:
        raise ValueError("Parametros invalidos") from exc
    allowed_params = {"profile"} if match else {"profile", "installer_id"}
    if any(key not in allowed_params or len(values) != 1 for key, values in params.items()):
        raise ValueError("Parametros nao permitidos")
    profile = params.get("profile", ["natal"])[0]
    if profile not in PROFILES:
        raise ValueError("Praca nao autorizada")
    stock_id = int(match.group(1)) if match else None
    if stock_id is not None and stock_id > 2147483647:
        raise ValueError("ID do estoque invalido")
    installer_id = params.get("installer_id", [None])[0]
    if installer_id is not None and (not installer_id.isdigit() or not 0 < int(installer_id) <= 2147483647):
        raise ValueError("ID do instalador invalido")
    return profile, stock_id, installer_id


class OfficialStockBridge:
    def __init__(self, credentials_file=CREDENTIALS_FILE):
        self._credentials_file = Path(credentials_file)
        self._clients = {}
        self._lock = threading.RLock()

    def _client(self, profile):
        with self._lock:
            if profile not in self._clients:
                credentials = load_credentials(self._credentials_file)
                self._clients[profile] = ImperiumHTTPClient(
                    credentials["username"], credentials["password"],
                    tenant=profile, timeout=45
                )
            return self._clients[profile]

    def read(self, parsed):
        profile, stock_id, installer_id = parsed
        client = self._client(profile)
        if stock_id is None:
            records = client.stock_catalog(installer_id)
            return {
                "ok": True, "source": "imperium_official_http",
                "credential_scope": "server_integration", "profile": profile,
                "installer_id": int(installer_id) if installer_id else None,
                "count": len(records), "stocks": records
            }
        records = client.stock_items(stock_id)
        return {
            "ok": True, "source": "imperium_official_http",
            "credential_scope": "server_integration", "profile": profile,
            "stock_id": stock_id, "count": len(records), "items": records
        }
