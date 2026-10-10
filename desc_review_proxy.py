"""Authenticated Dominium boundary to the Bot's existing DESC review service."""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ProxyError('Redirecionamento DESC bloqueado')


class ProxyError(ValueError):
    pass


@dataclass(frozen=True)
class ProxyResponse:
    status: int
    content_type: str
    body: bytes


class DescReviewProxy:
    def __init__(self, *, origin: str | None = None, access_file: Path | None = None):
        self.origin = (origin or os.environ.get('DOMINIUM_DESC_REVIEW_ORIGIN', 'http://127.0.0.1:8787')).rstrip('/')
        parsed = urlsplit(self.origin)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ProxyError('Endereço da revisão DESC inválido')
        default = r'\\wsl.localhost\Ubuntu\home\technet\BotDMV\data\desc_review\review-access.txt'
        self.access_file = access_file or Path(os.environ.get('DOMINIUM_DESC_REVIEW_ACCESS_FILE', default))
        self._cookie = ''
        self._csrf = ''
        self._lock = threading.RLock()

    @staticmethod
    def route(method: str, path: str) -> str:
        parsed = urlsplit(path)
        prefix = '/api/disconnection/'
        if not parsed.path.startswith(prefix) or parsed.fragment:
            raise ProxyError('Rota DESC inválida')
        route = parsed.path[len(prefix):]
        query = parse_qs(parsed.query, keep_blank_values=True)
        allowed = {'GET': {'state', 'report.xlsx'}, 'POST': {'decision', 'refresh', 'technician', 'manual'}}
        photo = bool(re.fullmatch(r'photo/[a-f0-9-]{36}\.jpg', route))
        if route not in allowed.get(method, set()) and not (method == 'GET' and photo):
            raise ProxyError('Rota DESC não permitida')
        if parsed.query and (route != 'report.xlsx' or set(query) != {'month'} or len(query['month']) != 1 or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', query['month'][0])):
            raise ProxyError('Parâmetros DESC inválidos')
        return '/desc-review/' + route + (('?' + parsed.query) if parsed.query else '')

    def _request(self, method: str, route: str, data: dict | None = None, *, session: bool = False) -> tuple[ProxyResponse, str]:
        headers = {'Accept': '*/*'}
        if not session:
            headers['Cookie'] = self._cookie
            if method == 'POST':
                headers['X-Review-Csrf'] = self._csrf
        encoded = None if data is None else json.dumps(data).encode('utf-8')
        if encoded is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self.origin + route, data=encoded, headers=headers, method=method)
        try:
            try:
                response = build_opener(_NoRedirect).open(request, timeout=110 if method == 'POST' and not session else 20)
            except HTTPError as error:
                response = error
            with response:
                body = response.read(16 * 1024 * 1024 + 1)
                if len(body) > 16 * 1024 * 1024:
                    raise ProxyError('Resposta DESC excedeu o limite')
                return ProxyResponse(response.status, response.headers.get('Content-Type', 'application/json'), body), response.headers.get('Set-Cookie', '')
        except (OSError, URLError, TimeoutError) as error:
            raise ProxyError('Serviço DESCONEXÃO indisponível; dados anteriores preservados') from error

    def _authenticate(self) -> None:
        with self._lock:
            if self._cookie:
                return
            try:
                pin = self.access_file.read_text(encoding='utf-8').strip()
            except OSError as error:
                raise ProxyError('A conexão interna da DESCONEXÃO ainda não está configurada') from error
            if not re.fullmatch(r'\d{8}', pin):
                raise ProxyError('Credencial interna da DESCONEXÃO inválida')
            response, cookie = self._request('POST', '/desc-review/session', {'pin': pin}, session=True)
            if response.status != 200 or not cookie.startswith('desc_review='):
                raise ProxyError('Não foi possível autenticar a revisão DESC')
            payload = json.loads(response.body)
            if not payload.get('csrf'):
                raise ProxyError('Sessão interna DESC inválida')
            self._cookie = cookie.split(';', 1)[0]
            self._csrf = str(payload['csrf'])

    def forward(self, method: str, path: str, body: dict | None = None, *, actor: str) -> ProxyResponse:
        route = self.route(method, path)
        if not actor:
            raise ProxyError('Operador autenticado não identificado')
        self._authenticate()
        data = {**(body or {}), 'actor': actor[:100]} if method == 'POST' else None
        response, _cookie = self._request(method, route, data)
        if response.status == 401:
            with self._lock:
                self._cookie = ''
                self._csrf = ''
                self._authenticate()
            response, _cookie = self._request(method, route, data)
        if response.content_type.startswith('application/json'):
            try:
                payload = json.loads(response.body)
                if isinstance(payload, dict):
                    payload.pop('csrf', None)
                return ProxyResponse(response.status, response.content_type, json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            except (ValueError, UnicodeError) as error:
                raise ProxyError('Resposta DESC inválida') from error
        return response
