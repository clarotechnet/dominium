"""Smoke Cloudflare -> DESC private service; never prints keys or customer records."""
import json
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = (Path(r"C:\DominiumRuntime\DescRelay-20261010") / "state" / "relay-token.txt").read_text().strip()
BASE = "https://dominium-import-bridge.jogador743.workers.dev"

def get(path, *, authorized=True, role="controller"):
    h = {"X-Dominium-Actor":"user-999999", "X-Dominium-Role":role}
    if authorized: h["Authorization"]="Bearer "+TOKEN
    q=urllib.request.Request(BASE+path,headers=h)
    try:
        with urllib.request.urlopen(q,timeout=15) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        raw=e.read(640)
        print("http_error_content_type",e.headers.get("content-type"))
        print("http_error_server",e.headers.get("server"))
        if not raw.lstrip().startswith((b"{",b"[")):
            print("http_error_body_prefix",raw.decode("utf-8","replace")[:250].replace("\n"," "))
            return e.code,{}
        try: return e.code,json.loads(raw)
        except ValueError: return e.code,{}

status, result = get("/api/confront/status")
print("cloudflare_confront_status_http", status)
print("safe_error_message", str(result.get("error") or "")[:120])
print("private_relay_reached", status == 200 and result.get("ok") is True)
print("atlas_flag_returned", isinstance(result.get("atlas_online"), bool))
print("unauthorized_blocked", get("/api/confront/status",authorized=False)[0]==401)
print("viewer_blocked", get("/api/confront/status",role="viewer")[0]==403)
print("jobs_listing_http",get("/api/confront/jobs")[0])
print("unknown_job_http",get("/api/confront/jobs/"+"0"*32)[0])
