"""Small, authenticated HTTPS-tunnel relay; exposes only DESC review routes.

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

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
        if not hmac.compare_digest(supplied, 'Bearer ' + self.server.relay_token):
            self._json(401, {'ok': False, 'error': 'Conexão interna não autorizada'})
            return
        actor = unquote(self.headers.get('X-Dominium-Actor', ''))[:100]
        if not actor:
            self._json(400, {'ok': False, 'error': 'Operador não identificado'})
            return
        try:
            DescReviewProxy.route(self.command, self.path)
            body = None
            if self.command == 'POST':
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 64 * 1024 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Corpo da revisão inválido')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Corpo da revisão inválido')
            response = self.server.review_proxy.forward(self.command, self.path, body, actor=actor)
            self.send_response(response.status)
            self.send_header('Content-Type', response.content_type)
            self.send_header('Content-Length', str(len(response.body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(response.body)
        except (ProxyError, ValueError) as error:
            self._json(503 if isinstance(error, ProxyError) else 400, {'ok': False, 'error': str(error)})
        except OSError:
            logging.warning('Cliente DESC encerrou conexão')

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
    server.serve_forever()


if __name__ == '__main__':
    main()
