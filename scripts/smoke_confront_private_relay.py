"""Smoke isolated pre-production local DESC relay, no serials or customer records read."""
import json
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = (Path(r"C:\DominiumRuntime\DescRelay-20261010") / "state" / "relay-token.txt").read_text().strip()
BASE = "http://127.0.0.1:8793"


def get(path, *, role="controller", authorized=True):
    headers = {"X-Dominium-Actor": "user-999999", "X-Dominium-Role": role}
    if authorized:
        headers["Authorization"] = "Bearer " + TOKEN
    request = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

assert get("/api/confront/status", authorized=False)[0] == 401
assert get("/api/confront/status", role="viewer")[0] == 403
code, data = get("/api/confront/status")
assert code == 200 and data.get("ok") is True
assert "atlas_online" in data
assert get("/api/confront/jobs")[0] == 200
assert get("/api/confront/jobs/" + "0"*32)[0] == 404
code, payload = get("/api/disconnection/reports")
assert code == 200 and payload.get("ok") is True
print("PRIVATE_CONFRONT_AUTH_OK")
print("PRIVATE_CONFRONT_ENDPOINT_OK")
print("EXISTING_DESC_REPORTS_OK")
