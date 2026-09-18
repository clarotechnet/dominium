from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datasnap_client import save_credentials

DATASNAP_PATH = ROOT / "config" / "credentials.dat"
HTTP_PATH = ROOT / "config" / "imperium_http_credentials.dat"


def configure(
    username: str,
    password: str,
    *,
    datasnap: bool = True,
    http: bool = True,
) -> list[Path]:
    username = username.strip()
    if not username:
        raise ValueError("Usuario Imperium obrigatorio")
    if not password:
        raise ValueError("Senha Imperium obrigatoria")
    written: list[Path] = []
    if datasnap:
        save_credentials(DATASNAP_PATH, username, password)
        written.append(DATASNAP_PATH)
    if http:
        save_credentials(HTTP_PATH, username, password)
        written.append(HTTP_PATH)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configura credenciais Imperium protegidas pelo Windows DPAPI."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--datasnap-only", action="store_true")
    group.add_argument("--http-only", action="store_true")
    args = parser.parse_args()

    username = input("Usuario Imperium: ").strip()
    password = getpass.getpass("Senha Imperium: ")
    confirm = getpass.getpass("Confirme a senha: ")
    if password != confirm:
        raise SystemExit("As senhas nao conferem")

    written = configure(
        username,
        password,
        datasnap=not args.http_only,
        http=not args.datasnap_only,
    )
    for path in written:
        print(f"Credencial protegida criada: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
