# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - protocolo, baixa, estoque ou operacao do Imperium.
#
# TOA
# - NAO - este arquivo nao consulta nem automatiza o TOA.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas quando necessario ao fluxo Imperium.
#
# Categoria deste arquivo: IMPERIUM.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import secrets
import threading
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from api_security import (
    LOCAL_RATE_LIMITER,
    SECURITY_HEADERS,
    redact_log_text,
    validate_local_request,
)
from flow_reader.analyzer import MAX_CAPTURE_BYTES, CaptureFormatError, analyze_capture


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
LOGGER = logging.getLogger("flowscope")


class FlowReaderServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


class FlowReaderHandler(BaseHTTPRequestHandler):
    server_version = "DOMINIUM"
    sys_version = ""

    def version_string(self) -> str:
        return "DOMINIUM"

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.send_header("X-Request-ID", getattr(self, "_request_id", secrets.token_hex(8)))
        super().end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), redact_log_text(fmt % args))

    def _trusted(self, method: str) -> bool:
        self._request_id = secrets.token_hex(8)
        decision = validate_local_request(self.headers, method, require_json=False)
        if not decision.allowed:
            self._json(decision.status, {"ok": False, "error": decision.reason})
            return False
        return True

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        data = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, requested: str) -> None:
        relative = "index.html" if requested in ("", "/") else requested.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._trusted("GET"):
            return
        if parsed.path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "name": "DOMINIUM FlowScope",
                    "version": "1.0.0",
                    "mode": "read_only",
                    "pid": os.getpid(),
                },
            )
            return
        self._static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._trusted("POST"):
            return
        client = self.client_address[0]
        if not LOCAL_RATE_LIMITER.allow(f"{client}:flowscope-analyze", 8, 60.0):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False, "error": "Muitas analises; aguarde um minuto"})
            return
        if parsed.path != "/api/analyze":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Rota inexistente"})
            return
        try:
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length:
                raise CaptureFormatError("O navegador nao informou o tamanho do arquivo")
            length = int(raw_length)
            if length <= 0:
                raise CaptureFormatError("O arquivo esta vazio")
            if length > MAX_CAPTURE_BYTES:
                raise CaptureFormatError("O arquivo ultrapassa o limite de 256 MB")
            filename = Path(unquote(self.headers.get("X-Filename", "captura.pcapng"))).name[:240]
            content = self.rfile.read(length)
            if len(content) != length:
                raise CaptureFormatError("O envio do arquivo foi interrompido")
            result = analyze_capture(content, filename)
            self._json(HTTPStatus.OK, result)
        except (CaptureFormatError, ValueError, zipfile.BadZipFile) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - final local boundary
            LOGGER.exception("Falha inesperada ao analisar captura")
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"Falha interna: {exc}"},
            )
def main() -> None:
    parser = argparse.ArgumentParser(description="DOMINIUM FlowScope")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    url = f"http://127.0.0.1:{args.port}"
    try:
        server = FlowReaderServer(("127.0.0.1", args.port), FlowReaderHandler)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048:
            webbrowser.open(url)
            return
        raise
    LOGGER.info("DOMINIUM FlowScope iniciado em %s (PID %s)", url, os.getpid())
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
