from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from supabase_auth_store import SupabaseAuthStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida conexao, schema e Auth do Supabase do DOMINIUM"
    )
    parser.add_argument("--require-empty", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url:
        raise SystemExit("SUPABASE_URL nao foi definida")
    host = urlparse(url).hostname or "desconhecido"
    print(f"Projeto Supabase: {host}")
    store = SupabaseAuthStore.from_environment()
    for table in (
        store.PROFILE_TABLE,
        store.SESSION_TABLE,
        store.IDENTITY_TABLE,
        store.AUDIT_TABLE,
    ):
        store.client.table(table).select("*").limit(1).execute()
        print(f"Tabela OK: {table}")

    auth_users = store.client.auth.admin.list_users(page=1, per_page=1)
    print("Supabase Auth admin API: OK")
    has_profiles = store.has_users()
    print(f"Perfis DOMINIUM existentes: {'sim' if has_profiles else 'nao'}")
    print(f"Usuarios Auth existentes: {'sim' if bool(auth_users) else 'nao'}")
    if args.require_empty and has_profiles:
        raise SystemExit("O backend ja possui perfis DOMINIUM; bootstrap deve ser revisado")
    print("SUPABASE_READY=1")


if __name__ == "__main__":
    main()
