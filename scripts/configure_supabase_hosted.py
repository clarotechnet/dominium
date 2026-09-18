from __future__ import annotations

import argparse
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API_ROOT = "https://api.supabase.com/v1"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aplica configuracao segura do Supabase Auth do DOMINIUM"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--site-url", default=os.environ.get("DOMINIUM_PUBLIC_ORIGIN", ""))
    args = parser.parse_args()

    project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if not project_ref:
        raise SystemExit("SUPABASE_PROJECT_REF nao foi definido")

    payload = {"disable_signup": True, "password_min_length": 10}
    if args.site_url:
        payload["site_url"] = args.site_url.rstrip("/")
    safe_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if not args.apply:
        print(f"Projeto: {project_ref}")
        print(f"Configuracao planejada: {safe_payload}")
        print("DRY_RUN=1")
        return
    if not token:
        raise SystemExit("SUPABASE_ACCESS_TOKEN nao foi definido")

    request = Request(
        f"{API_ROOT}/projects/{project_ref}/config/auth",
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        raise SystemExit(f"Falha ao configurar Auth ({exc.code}): {body}") from exc
    print("SUPABASE_AUTH_CONFIGURED=1")


if __name__ == "__main__":
    main()
