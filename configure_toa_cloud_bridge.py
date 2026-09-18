# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO.
#
# TOA
# - SIM - configura apenas o transporte privado da consulta operacional.
# =============================================================================
"""Grava a credencial primaria da ponte com protecao DPAPI do Windows."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path

from datasnap_client import protect_secret


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--collector-token", default="")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "config" / "toa_cloud_bridge_credentials.dat"),
    )
    parser.add_argument(
        "--collector-output",
        default=str(Path(__file__).resolve().parent / "config" / "toa_cloud_collector_setup.dat"),
    )
    args = parser.parse_args()
    token = (
        args.token
        or os.environ.get("DOMINIUM_TOA_PRIMARY_TOKEN", "")
        or getpass.getpass("Chave primaria da ponte: ")
    )
    collector_token = args.collector_token or os.environ.get("DOMINIUM_TOA_COLLECTOR_TOKEN", "")
    if not args.url.startswith("https://") or len(token) < 32:
        raise SystemExit("Informe URL HTTPS e uma chave com pelo menos 32 caracteres")
    payload = json.dumps(
        {"base_url": args.url.rstrip("/"), "primary_token": token},
        separators=(",", ":"),
    ).encode("utf-8")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(protect_secret(payload))
    print(f"Ponte do Dominium configurada com DPAPI em {output}")
    if collector_token:
        if len(collector_token) < 32:
            raise SystemExit("A chave do coletor precisa ter pelo menos 32 caracteres")
        collector_payload = json.dumps(
            {"base_url": args.url.rstrip("/"), "collector_token": collector_token},
            separators=(",", ":"),
        ).encode("utf-8")
        collector_output = Path(args.collector_output).resolve()
        collector_output.parent.mkdir(parents=True, exist_ok=True)
        collector_output.write_bytes(protect_secret(collector_payload))
        print(f"Configuracao do coletor protegida por DPAPI em {collector_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
