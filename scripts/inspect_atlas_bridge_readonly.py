"""Inspect only Atlas local bridge health and safely redacted metadata."""
import urllib.request
import urllib.error
import json

SENSITIVE = ("token", "cookie", "password", "secret", "serial", "contract",
             "client", "name", "url", "host", "session", "result", "request",
             "bearer", "authorization", "header", "owner", "person", "technician")

def summarize(obj, depth=0):
    if depth >= 3:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {key: summarize(value, depth+1) for key, value in obj.items()
                if not any(word in key.lower() for word in SENSITIVE)}
    if isinstance(obj, list):
        return {"size": len(obj)}
    if isinstance(obj, bool) or isinstance(obj, (int,float)):
        return obj
    return type(obj).__name__

for path in ("/toa/health", "/atlas/extension-status"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787" + path, timeout=3) as r:
            response = json.load(r)
            print(path, r.status, json.dumps(summarize(response),ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        print(path, exc.code)
    except (OSError, ValueError):
        print(path, "unavailable")
