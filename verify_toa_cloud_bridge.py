# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO.
#
# TOA
# - SIM - verifica a fila privada com um registro sintetico, sem consultar o TOA.
# =============================================================================
"""Teste online seguro da ponte Cloudflare/D1 sem expor as chaves."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from datasnap_client import unprotect_secret


ROOT = Path(__file__).resolve().parent


def load_secret(filename: str) -> dict:
    raw = (ROOT / "config" / filename).read_bytes()
    return json.loads(unprotect_secret(raw).decode("utf-8"))


def request_json(url: str, token: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DOMINIUM-TechNet/1.0 (Windows; verificacao-autorizada)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ponte respondeu HTTP {error.code}: {detail}") from error


def main() -> int:
    primary = load_secret("toa_cloud_bridge_credentials.dat")
    collector = load_secret("toa_cloud_collector_setup.dat")
    base_url = primary["base_url"]
    created = request_json(
        f"{base_url}/v1/lookups",
        primary["primary_token"],
        method="POST",
        payload={"contract": "9999900"},
    )
    job_id = created["job"]["id"]
    leased = request_json(
        f"{base_url}/v1/collector/jobs/next?collector_id=dominium-verificacao",
        collector["collector_token"],
    )
    if (leased.get("job") or {}).get("id") != job_id:
        raise SystemExit("A fila nao entregou o job de verificacao")
    request_json(
        f"{base_url}/v1/collector/jobs/{job_id}/result",
        collector["collector_token"],
        method="POST",
        payload={
            "ok": True,
            "snapshot": {
                "contract": "9999900",
                "customer_name": "NAO DEVE SER RETIDO",
                "tasks": [{"os_number": "2650999999", "close_code": "409"}],
                "materials": [{"code": "22056332", "quantity": 1}],
                "equipment": {"installed": [{"serial": "SERIAL-TESTE"}]},
            },
        },
    )
    final = request_json(
        f"{base_url}/v1/lookups/{job_id}",
        primary["primary_token"],
    )
    snapshot = ((final.get("job") or {}).get("result") or {})
    encoded = json.dumps(snapshot, ensure_ascii=False).lower()
    if (final.get("job") or {}).get("status") != "completed" or "customer_name" in encoded:
        raise SystemExit("A verificacao de status ou privacidade falhou")
    if not snapshot.get("materials") or not snapshot.get("equipment"):
        raise SystemExit("Materiais ou equipamentos nao atravessaram a ponte")
    print("Ponte online verificada: fila, D1, privacidade, materiais e equipamentos OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
