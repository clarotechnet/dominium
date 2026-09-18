from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_store import AuthStore


def build_store():
    backend = os.environ.get("DOMINIUM_AUTH_BACKEND", "").strip().lower()
    database_url = os.environ.get("DOMINIUM_DATABASE_URL", "").strip()
    if not backend:
        backend = "postgres" if database_url else "sqlite"
    if backend == "supabase":
        from supabase_auth_store import SupabaseAuthStore
        return SupabaseAuthStore.from_environment()
    if backend in {"postgres", "postgresql"}:
        if not database_url:
            raise SystemExit("DOMINIUM_DATABASE_URL nao foi definida")
        from auth_store_postgres import PostgresAuthStore
        return PostgresAuthStore(database_url)
    if backend == "sqlite":
        return AuthStore(ROOT / "data" / "dominium_auth.sqlite3")
    raise SystemExit(f"DOMINIUM_AUTH_BACKEND invalido: {backend}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria o administrador inicial do DOMINIUM")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    store = build_store()
    if store.has_users():
        raise SystemExit("O backend de autenticacao ja possui usuarios; bootstrap cancelado")

    password = getpass.getpass("Senha do administrador: ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        raise SystemExit("As senhas nao conferem")
    user = store.register(
        args.username,
        args.display_name,
        password,
        allow_bootstrap=True,
    )
    if user.get("role") != "admin" or user.get("status") != "active":
        raise SystemExit("Falha ao criar o administrador inicial")
    print(f"Administrador inicial criado: {user['username']}")


if __name__ == "__main__":
    main()
