import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from backlog_sidecar import build_handler, read_bridge_token

TOKEN="Z"*52

class FakeService:
    def __init__(self): self.calls=[]
    def snapshot(self): return {"ok":True,"running":False}
    def start(self,**kw):
        self.calls.append(("start",kw))
        return {"ok":True,"mode":kw["mode"],"tasks":1}
    def cancel(self): return {"ok":True}
    def compare(self,**kw): return {"ok":True,"rows":[]}
    def fora_rota(self,**kw): return {"ok":True,"candidates":[]}
    def list_sent(self): return {"ok":True,"rows":[]}
    def mark_sent(self,body):return {"ok":True}
    def import_route_files(self,files):return {"ok":True,"files":[]}

class SidecarHttpContract(unittest.TestCase):
    def setUp(self):
        self.service=FakeService()
        self.patched=patch.dict(os.environ,{"DOMINIUM_BACKLOG_BRIDGE_TOKEN":TOKEN},
                                clear=False)
        self.patched.start()
        os.environ.pop("DOMINIUM_BACKLOG_YEAR_ENABLE",None)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),build_handler(self.service))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.patched.stop()
    def request(self,method,path,body=None,role="controller",authorization=None):
        headers={"Authorization":authorization if authorization is not None else "Bearer "+TOKEN,
                 "X-Dominium-Role":role,"X-Dominium-Actor":"user-7"}
        if method=="POST":headers["Content-Type"]="application/json"
        req=Request("http://127.0.0.1:"+str(self.server.server_port)+path,
                    method=method,headers=headers,
                    data=json.dumps(body or {}).encode() if method=="POST" else None)
        try:
            with urlopen(req,timeout=5) as res:
                return res.status,json.loads(res.read())
        except HTTPError as ex:
            try:return ex.code,json.loads(ex.read())
            finally:ex.close()
    def test_authenticated_status_and_compare(self):
        self.assertEqual(self.request("GET","/api/backlog/year/status")[0],200)
        self.assertEqual(self.request("GET","/api/backlog/year/compare?limit=100")[0],200)
    def test_no_token_or_viewer_rejected(self):
        self.assertEqual(self.request("GET","/api/backlog/year/status",authorization="Bearer invalid")[0],401)
        self.assertEqual(self.request("GET","/api/backlog/year/status",role="viewer")[0],401)
        self.assertEqual(self.service.calls,[])
    def test_probe_allowed_but_annual_locked_by_default(self):
        self.assertEqual(self.request("POST","/api/backlog/year/start",{"mode":"batch"})[0],423)
        self.assertEqual(self.service.calls,[])
        code,_=self.request("POST","/api/backlog/year/start",{"mode":"probe","profile":"natal"})
        self.assertEqual(code,202)
        self.assertEqual(self.service.calls[0][0],"start")
    def test_only_exact_routes_accept_json(self):
        self.assertNotEqual(self.request("POST","/api/orders/123/close",{})[0],200)
        self.assertNotEqual(self.request("POST","/api/backlog/year/unknown",{})[0],200)
    def test_secret_loader_validates_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            import pathlib
            path=pathlib.Path(tmp)/"token.txt"
            path.write_text("short",encoding="utf8")
            with self.assertRaises(ValueError):read_bridge_token(path)
            path.write_text(TOKEN+"\n",encoding="utf8")
            self.assertEqual(read_bridge_token(path),TOKEN)

if __name__=="__main__":unittest.main()
