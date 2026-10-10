"""Authenticated relay for DESC review and private read-only Imperium checks.

Dominium validates its operator session/CSRF before forwarding. The independent
relay credential and Bot review PIN stay on servers, never in browser code.
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

# The relay runs beside its private connection file, outside the Imperium checkout.
_runtime_root = Path(os.environ.get('DOMINIUM_IMPERIUM_RUNTIME_ROOT', r'C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA'))
if _runtime_root.is_dir():
    sys.path.append(str(_runtime_root))

from desc_order_verifier import DEFAULT_RUNTIME_ROOT, DescOrderVerifier, OrderCheckError
from desc_review_proxy import DescReviewProxy, ProxyError


class DescRelayHandler(BaseHTTPRequestHandler):
    server_version = 'DominiumDesc'

    def log_message(self, *_args):
        pass

    def _json(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self):
        supplied = str(self.headers.get('Authorization', ''))
        if not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + self.server.relay_token).encode('utf-8')):
            self._json(401, {'ok': False, 'error': 'Conexão interna não autorizada'})
            return
        actor = unquote(self.headers.get('X-Dominium-Actor', ''))[:100]
        if not actor:
            self._json(400, {'ok': False, 'error': 'Operador não identificado'})
            return
        try:
            order_check = self.command == 'POST' and self.path == '/internal/order-check'
            if not order_check:
                DescReviewProxy.route(self.command, self.path)
            body = None
            if self.command == 'POST':
                body = self._read_json()
            if order_check:
                verifier = getattr(self.server, 'order_verifier', None)
                if verifier is None:
                    self._json(503, {'ok': False, 'code': 'imperium_unavailable',
                                     'error': 'Consulta Imperium indisponível; OS não confirmadas'})
                    return
                result = verifier.check(body)
                self._json(200, {'ok': True, **result})
                return
            response = self.server.review_proxy.forward(self.command, self.path, body, actor=actor)
            self.send_response(response.status)
            self.send_header('Content-Type', response.content_type)
            self.send_header('Content-Length', str(len(response.body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(response.body)
        except OrderCheckError as error:
            self._json(error.status, {'ok': False, 'code': error.code, 'error': str(error)})
        except (ProxyError, ValueError) as error:
            self._json(503 if isinstance(error, ProxyError) else 400, {'ok': False, 'error': str(error)})
        except OSError:
            logging.warning('Cliente DESC encerrou conexão')

    def _read_json(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 64 * 1024 or self.headers.get_content_type() != 'application/json':
                raise ValueError
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
            return body
        except (ValueError, UnicodeError) as error:
            raise ValueError('Corpo da consulta inválido') from error

    do_GET = _dispatch
    do_POST = _dispatch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8793)
    parser.add_argument('--token-file', type=Path, default=Path(__file__).parent / 'state' / 'relay-token.txt')
    args = parser.parse_args()
    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    if not args.token_file.exists():
        args.token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
        os.chmod(args.token_file, 0o600)
    token = args.token_file.read_text(encoding='utf-8').strip()
    if len(token) < 43:
        raise SystemExit('Credencial interna inválida')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), DescRelayHandler)
    server.relay_token = token
    server.review_proxy = DescReviewProxy()
    server.order_verifier = DescOrderVerifier(Path(os.environ.get('DOMINIUM_IMPERIUM_RUNTIME_ROOT', str(DEFAULT_RUNTIME_ROOT))))
    server.serve_forever()


if __name__ == '__main__':
    main()
