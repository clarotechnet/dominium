"""Isolated authenticated HTTP smoke tests, no production listeners."""
import json,os,threading,unittest,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
from backlog_sidecar_matheus_stage import build_handler

class FakeService:
    def snapshot(self):return {"ok":True,"history":{"confirmed":7}}
    def route_import_state(self):return {"running":False}
    def daily_treatment(self):return {"total":412}
    def current_status(self):return {"ok":True,"fresh":True,"routes":{"route_rows":412,"matches":{"exact_wo":344}}}

class Tests(unittest.TestCase):
    def setUp(self):
        self.old=os.environ.get("DOMINIUM_BACKLOG_BRIDGE_TOKEN")
        os.environ["DOMINIUM_BACKLOG_BRIDGE_TOKEN"]="x"*43
        self.server=ThreadingHTTPServer(("127.0.0.1",0),build_handler(FakeService()))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_address[1])+"/api/backlog/year/status"
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.old is None:os.environ.pop("DOMINIUM_BACKLOG_BRIDGE_TOKEN",None)
        else:os.environ["DOMINIUM_BACKLOG_BRIDGE_TOKEN"]=self.old
    def test_existing_status_shape_and_matheus_summary(self):
        request=urllib.request.Request(self.url,headers={
            "Authorization":"Bearer "+"x"*43,
            "X-Dominium-Role":"admin",
            "X-Dominium-Actor":"synthetic_tester"})
        with urllib.request.urlopen(request,timeout=3) as reply:
            self.assertEqual(reply.status,200)
            result=json.loads(reply.read())
        self.assertEqual(result["history"]["confirmed"],7)
        self.assertEqual(result["daily_treatment"]["total"],412)
        self.assertEqual(result["imperium_today"]["routes"]["matches"]["exact_wo"],344)
        self.assertNotIn("token",result)
    def test_unauthorized_still_rejected(self):
        request=urllib.request.Request(self.url)
        with self.assertRaises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request,timeout=3)
        self.assertEqual(exc.exception.code,401)
if __name__=="__main__":unittest.main()
