"""Read-only Atlas serial lookups via the existing localhost BotDMV queue.

No browser credentials, cookies, Atlas HTTP scraping or inventory writes.
The BotDMV bridge queues a read operation; the existing Chrome extension
fulfills it using its own authenticated Atlas session.

Do NOT deploy this client behind an unguarded web endpoint: the existing
BotDMV queue itself currently does not implement per-request authentication.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

BRIDGE_URL = "http://127.0.0.1:8787"
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{6,100}\Z")
SERIAL = re.compile(r"[A-Z0-9]{8,30}\Z")


class AtlasBridgeError(RuntimeError):
    """A lookup was not confirmed; do not interpret this as inventory absence."""


class AtlasBridgeClient:
    def __init__(self, *, base_url: str = BRIDGE_URL,
                 http: Callable[..., dict] | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if base_url != BRIDGE_URL:
            raise ValueError("Atlas bridge permitido somente no loopback local")
        self.base_url = base_url
        self._http = http or self._request_json
        self._clock = clock
        self._sleep = sleep

    @staticmethod
    def _request_json(method: str, path: str, body: dict | None = None) -> dict:
        if not path.startswith("/atlas/") or path.startswith("//"):
            raise AtlasBridgeError("Caminho Atlas nao permitido")
        if method not in {"GET", "POST"}:
            raise AtlasBridgeError("Metodo nao permitido")
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            request = urllib.request.Request(BRIDGE_URL + path, data=data,
                                             headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=8) as response:
                if response.status != 200:
                    raise AtlasBridgeError("Bridge nao confirmou a requisicao")
                # Do not let a compromised/malformed bridge response exhaust RAM.
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise AtlasBridgeError("Resposta Atlas excessiva")
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise AtlasBridgeError("Resposta Atlas invalida")
                return parsed
        except (OSError, ValueError, UnicodeError) as exc:
            raise AtlasBridgeError("Ponte Atlas indisponivel") from exc

    @staticmethod
    def valid_serial(serial: str) -> bool:
        value = str(serial or "").strip().upper()
        if not SERIAL.fullmatch(value) or not any(c.isdigit() for c in value):
            return False
        if value.isdigit() and not 10 <= len(value) <= 18:
            return False
        return True

    def status(self) -> dict:
        data = self._http("GET", "/atlas/extension-status")
        if data.get("ok") is not True:
            raise AtlasBridgeError("Status Atlas nao confirmado")
        return data

    def enqueue(self, serial: str) -> str:
        """Enqueue ONCE. Persist the returned ID before polling to allow resume."""
        value = str(serial or "").strip().upper()
        if not self.valid_serial(value):
            raise ValueError("Serial incompativel com Atlas")
        if self.status().get("online") is not True:
            raise AtlasBridgeError("Extensao Atlas offline")
        queued = self._http("POST", "/atlas/queue-query", {
            "serials": [value], "source": "dominium-confront-readonly",
        })
        request_id = str(queued.get("requestId") or "")
        if queued.get("ok") is not True or queued.get("queued") is not True or not REQUEST_ID.fullmatch(request_id):
            raise AtlasBridgeError("Consulta Atlas nao entrou na fila")
        if queued.get("serials") != [value]:
            raise AtlasBridgeError("Fila Atlas devolveu identificador divergente")
        return request_id

    def poll_result(self, request_id: str, serial: str) -> dict | None:
        """One non-blocking GET. None means pending, never 'not found'."""
        value = str(serial or "").strip().upper()
        if not REQUEST_ID.fullmatch(request_id) or not self.valid_serial(value):
            raise ValueError("Consulta Atlas invalida")
        result_path = "/atlas/query-result/" + urllib.parse.quote(request_id, safe="")
        response = self._http("GET", result_path)
        if response.get("ok") is not True:
            raise AtlasBridgeError("Falha ao consultar resultado Atlas")
        if response.get("ready") is not True:
            return None
        result = response.get("result")
        if not isinstance(result, dict) or result.get("requestId") != request_id:
            raise AtlasBridgeError("Resultado Atlas de outra requisicao")
        delivered_serial = str(result.get("serial") or "").strip().upper()
        if delivered_serial and delivered_serial != value:
            raise AtlasBridgeError("Resultado Atlas pertence a outro serial")
        if result.get("ok") is not True:
            return {"ok": False, "error": "atlas_consulta_nao_confirmada",
                    "serial_consultado": value}
        actual = result.get("resultado")
        if not isinstance(actual, dict):
            raise AtlasBridgeError("Atlas nao devolveu registro estruturado")
        query_serial = str(actual.get("serial_consultado") or "").strip().upper()
        if query_serial != value:
            raise AtlasBridgeError("Correlacao Atlas/serial nao confirmada")
        return {"ok": True, "resultado": actual, "serial": value, "requestId": request_id}

    def wait_result(self, request_id: str, serial: str, *, timeout: float = 90.0,
                    poll_interval: float = 1.5) -> dict:
        if not 5 <= timeout <= 300 or not 0.2 <= poll_interval <= 10:
            raise ValueError("Parametros de espera invalidos")
        deadline = self._clock() + timeout
        while True:
            result = self.poll_result(request_id, serial)
            if result is not None:
                return result
            if self._clock() >= deadline:
                raise AtlasBridgeError("Resultado Atlas pendente; consultar requestId antes de reenfileirar")
            self._sleep(min(poll_interval, max(0.0, deadline - self._clock())))

    def query(self, serial: str, *, timeout: float = 90.0,
              poll_interval: float = 1.5) -> dict:
        """Convenience API; use enqueue+poll_result for durable jobs."""
        value = str(serial or "").strip().upper()
        if not self.valid_serial(value):
            return {"ok": False, "error": "serial_incompativel_com_atlas",
                    "serial_consultado": value}
        if not 5 <= timeout <= 300 or not 0.2 <= poll_interval <= 10:
            raise ValueError("Parametros de espera invalidos")
        request_id = self.enqueue(value)
        return self.wait_result(request_id, value, timeout=timeout, poll_interval=poll_interval)
