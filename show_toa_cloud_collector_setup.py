# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO.
#
# TOA
# - SIM - revela localmente a configuracao do coletor para cadastro na extensao.
# =============================================================================
"""Mostra a URL e a chave do coletor protegidas pelo DPAPI deste Windows."""

from __future__ import annotations

import json
from pathlib import Path

from datasnap_client import unprotect_secret


def main() -> int:
    path = Path(__file__).resolve().parent / "config" / "toa_cloud_collector_setup.dat"
    if not path.exists():
        raise SystemExit("Configuracao do coletor ainda nao foi criada")
    payload = json.loads(unprotect_secret(path.read_bytes()).decode("utf-8"))
    print("URL da ponte:")
    print(payload["base_url"])
    print("\nChave do coletor (cole somente nas opcoes da extensao):")
    print(payload["collector_token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
