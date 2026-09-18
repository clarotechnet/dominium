from pathlib import Path

p = Path('app.py')
s = p.read_text(encoding='utf-8')
bak = Path('app.py.bak_remote_toa_20260915')
if not bak.exists():
    bak.write_text(s, encoding='utf-8')

old_import = 'from urllib.parse import parse_qs, urlparse\n'
new_import = (
    'from urllib.error import HTTPError, URLError\n'
    'from urllib.parse import parse_qs, urlparse\n'
    'from urllib.request import Request, urlopen\n'
)
assert old_import in s, 'urllib import anchor ausente'
if 'from urllib.request import Request, urlopen' not in s:
    s = s.replace(old_import, new_import, 1)

anchor = 'TOA_AUTOMATION = TOAAutomation(ROOT, _automatic_toa_import, logger=LOGGER)\n\n'
assert anchor in s, 'TOA_AUTOMATION anchor ausente'
helper = '''REMOTE_TOA_AUTOMATION_BASE = os.getenv(
    "DOMINIUM_TOA_AUTOMATION_REMOTE", "http://192.168.0.6:8787"
).rstrip("/")
REMOTE_TOA_AUTOMATION_CLIENT = socket.gethostname().strip().upper()


def _remote_toa_automation_request(path: str, method: str = "GET") -> dict:
    request = Request(
        f"{REMOTE_TOA_AUTOMATION_BASE}{path}",
        data=b"{}" if method == "POST" else None,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Dominium-Client": REMOTE_TOA_AUTOMATION_CLIENT,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Servidor TOA respondeu HTTP {exc.code}: {detail[:240]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Servidor TOA indisponivel: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Servidor TOA retornou resposta invalida")
    payload["remote_server"] = True
    return payload

'''
if 'REMOTE_TOA_AUTOMATION_BASE =' not in s:
    s = s.replace(anchor, anchor + helper, 1)
old_get = '''            if parsed.path == "/api/toa-automation":
                self._json(HTTPStatus.OK, TOA_AUTOMATION.public_state())
                return
'''
new_get = '''            if parsed.path == "/api/toa-automation":
                try:
                    state = _remote_toa_automation_request("/toa/import-status")
                except Exception as exc:
                    state = TOA_AUTOMATION.public_state()
                    state.update({
                        "ok": False,
                        "remote_server": True,
                        "running": False,
                        "error": str(exc),
                    })
                self._json(HTTPStatus.OK, state)
                return
'''
assert old_get in s, 'GET toa-automation antigo nao encontrado'
s = s.replace(old_get, new_get, 1)

old_post = '''        if parsed.path == "/api/toa-automation/run":
            if not TOA_AUTOMATION.credentials_path.is_file():
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "Credencial TOA nao configurada"},
                )
                return
            if not TOA_AUTOMATION.trigger("manual"):
                self._json(
                    HTTPStatus.CONFLICT,
                    {"ok": False, "error": "A importacao TOA ja esta em andamento"},
                )
                return
            self._json(HTTPStatus.ACCEPTED, TOA_AUTOMATION.public_state())
            return
'''
new_post = '''        if parsed.path == "/api/toa-automation/run":
            try:
                state = _remote_toa_automation_request("/toa/import", method="POST")
            except Exception as exc:
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "remote_server": True, "error": str(exc)},
                )
                return
            self._json(HTTPStatus.ACCEPTED, state)
            return
'''
assert old_post in s, 'POST toa-automation antigo nao encontrado'
s = s.replace(old_post, new_post, 1)

old_start = '    TOA_AUTOMATION.start()\n    TOA_LIVE.start()\n'
new_start = '''    if os.getenv("DOMINIUM_LOCAL_TOA_AUTOMATION", "0") == "1":
        TOA_AUTOMATION.start()
    else:
        LOGGER.info("TOA automatico local desativado; servidor remoto e a fonte oficial")
    TOA_LIVE.start()
'''
assert old_start in s, 'startup TOA_AUTOMATION nao encontrado'
s = s.replace(old_start, new_start, 1)

p.write_text(s, encoding='utf-8')
print('patch aplicado')
