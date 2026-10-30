"""Independent localhost-only Backlog HTTP service.

Does not import or replace the operational app.py. All DataSnap requests
are read-only. Network access requires the existing private Relay bearer
and an operational role. The full-year importer is disabled by default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from backlog_bridge_auth import _authorized_backlog_bridge
from backlog_imperium_service import BacklogHistoryService

_BACKLOG_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
_PROFILES = {
    "natal": (212, "NATAL / PARNAMIRIM", 362032),
    "fortaleza": (596, "FORTALEZA", 90321),
    "mossoro": (579, "MOSSORO", 22722),
    "recife": (599, "RECIFE", 15787),
}

def read_bridge_token(path: str | Path) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not _BACKLOG_TOKEN_RE.fullmatch(value):
        raise ValueError("Token privado ausente ou invalido")
    return value

def build_handler(service: BacklogHistoryService):
    class BacklogHandler(BaseHTTPRequestHandler):
        server_version = "DOMINIUM-Backlog/1"
        sys_version = ""
        def log_message(self, format, *args):
            # Never log Authorization, request bodies, contracts or service tokens.
            return

        def _send(self, status, payload):
            data=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            try:self.wfile.write(data)
            except (ConnectionError,OSError):pass

        def _authorized(self):
            path=urlparse(self.path).path
            if not _authorized_backlog_bridge(self.headers,self.command,path,self.client_address[0]):
                self._send(HTTPStatus.UNAUTHORIZED,{"ok":False,"error":"Credencial ou rota nao autorizada"})
                return False
            return True

        def _query(self):
            query=urlparse(self.path).query
            values=parse_qs(query,keep_blank_values=True,max_num_fields=8)
            if any(len(items)!=1 for items in values.values()):
                raise ValueError("Parametro repetido")
            return {key:items[0] for key,items in values.items()}

        def do_GET(self):
            if not self._authorized():return
            path=urlparse(self.path).path
            try:
                params=self._query()
                if path=="/api/backlog/year/status":
                    if params:raise ValueError("Parametros inesperados")
                    result=service.snapshot()
                elif path=="/api/backlog/year/compare":
                    if set(params)-{"limit","codes"}:raise ValueError("Parametro invalido")
                    limit=int(params.get("limit","300"))
                    if limit<1 or limit>1000:raise ValueError("Limite invalido")
                    codes=params.get("codes","101,306,404,430").split(",")
                    if len(codes)>10 or any(not re.fullmatch(r"[0-9]{3}",x) for x in codes):
                        raise ValueError("Codigos invalidos")
                    result=service.compare(limit=limit,selected_codes=codes)
                elif path=="/api/backlog/year/fora-rota":
                    if set(params)-{"limit","profile"}:raise ValueError("Parametro invalido")
                    limit=int(params.get("limit","150"))
                    if limit<1 or limit>300:raise ValueError("Limite invalido")
                    result=service.fora_rota(profile=params.get("profile","natal"),limit=limit)
                elif path=="/api/backlog/year/sent":
                    if params:raise ValueError("Parametros inesperados")
                    result=service.list_sent()
                else:
                    self._send(HTTPStatus.NOT_FOUND,{"ok":False,"error":"Rota invalida"})
                    return
                self._send(HTTPStatus.OK,result)
            except (ValueError,TypeError) as err:
                self._send(HTTPStatus.BAD_REQUEST,{"ok":False,"error":str(err)[:120]})
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR,{"ok":False,"error":"Falha na consulta do Backlog"})

        def do_POST(self):
            if not self._authorized():return
            path=urlparse(self.path).path
            if urlparse(self.path).query:
                self._send(HTTPStatus.BAD_REQUEST,{"ok":False,"error":"Nao use parametros no POST"})
                return
            if self.headers.get("Content-Type","").split(";",1)[0].strip().lower()!="application/json":
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE,{"ok":False,"error":"Envie JSON"})
                return
            try:
                n=int(self.headers.get("Content-Length","-1"))
            except ValueError:
                n=-1
            max_bytes=22*1024*1024 if path=="/api/backlog/year/routes" else 8192
            if n<0 or n>max_bytes:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,{"ok":False,"error":"Corpo ausente ou acima do limite"})
                return
            try:
                data=json.loads(self.rfile.read(n))
                if not isinstance(data,dict):raise ValueError("Objeto JSON necessario")
                if path=="/api/backlog/year/start":
                    mode=str(data.get("mode") or "batch")
                    if mode!="probe" and os.environ.get("DOMINIUM_BACKLOG_YEAR_ENABLE")!="1":
                        self._send(HTTPStatus.LOCKED,{"ok":False,
                            "error":"Carga anual nao homologada; use Testar ontem"})
                        return
                    result=service.start(mode=mode,days_per_profile=int(data.get("days_per_profile") or 1),
                        only_profile=data.get("profile") or None)
                    self._send(HTTPStatus.ACCEPTED,result)
                elif path=="/api/backlog/year/pause":
                    self._send(HTTPStatus.OK,service.cancel())
                elif path=="/api/backlog/year/routes":
                    self._send(HTTPStatus.OK,service.import_route_files(data.get("files")))
                elif path=="/api/backlog/year/sent":
                    self._send(HTTPStatus.OK,service.mark_sent(data))
                else:
                    self._send(HTTPStatus.NOT_FOUND,{"ok":False,"error":"Rota invalida"})
            except (ValueError,TypeError) as err:
                self._send(HTTPStatus.BAD_REQUEST,{"ok":False,"error":str(err)[:120]})
            except RuntimeError as err:
                self._send(HTTPStatus.CONFLICT,{"ok":False,"error":str(err)[:120]})
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR,{"ok":False,"error":"Falha na operacao do Backlog"})
    return BacklogHandler

def main():
    parser=argparse.ArgumentParser(description="Backlog isolado DOMINIUM - apenas localhost")
    parser.add_argument("--port",type=int,default=9342)
    parser.add_argument("--imperium-root",default=r"C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA")
    parser.add_argument("--data-dir",default=r"C:\DominiumRuntime\BacklogRuntime\data")
    parser.add_argument("--token-file",default=r"C:\DominiumRuntime\DescRelay-20261010\state\relay-token.txt")
    args=parser.parse_args()
    if args.port<=1024 or args.port>65535:raise SystemExit("Porta invalida")
    os.environ["DOMINIUM_BACKLOG_BRIDGE_TOKEN"]=read_bridge_token(args.token_file)
    src=Path(args.imperium_root)
    sys.path.insert(0,str(src))
    from imperium_api import ImperiumAPI
    data=Path(args.data_dir)
    data.mkdir(parents=True,exist_ok=True)
    profiles={
        profile:SimpleNamespace(api=ImperiumAPI(src,port=port,company=city,
            profile_key=profile,controller_id=controller,log_root=data/"log"))
        for profile,(port,city,controller) in _PROFILES.items()
    }
    service=BacklogHistoryService(data/"backlog.sqlite3",profiles,
        operation_gate=threading.RLock())
    server=ThreadingHTTPServer(("127.0.0.1",args.port),build_handler(service))
    print("BACKLOG_SERVICE_READY=127.0.0.1:"+str(args.port),flush=True)
    try:server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=="__main__":main()
