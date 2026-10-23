"""NetTask 404 handling: no duplicate report generation or insecure URLs."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"
sys.path.insert(0,str(ROOT))
from atlas_query_report import claim_job,save_queue,read_job
import atlas_query_pipeline as pipeline


class FakeChrome:
    created=0
    requests=[]
    def __init__(self):
        FakeChrome.created+=1
        self.tab="fake-tab"
    def open(self,*args,**kwargs):pass
    def call(self,ws,method,params,timeout=12):
        FakeChrome.requests.append(method)
        if method=="Page.getFrameTree":
            return {"frameTree":{"frame":{"id":"frame-a"}}}
        if method=="Network.loadNetworkResource":
            return {"resource":{"success":False,"httpStatusCode":404,"netError":-379}}
        raise AssertionError(method)
    def close(self):pass


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"jobs.sqlite3"
        self.job,_=claim_job("mossoro","empreiteira",self.db,timestamp=100000)
        save_queue(self.job,"276841868",self.db)
        pipeline.upgrade_db(self.db)
        FakeChrome.created=0
        FakeChrome.requests=[]

    def ready(self,when=100):
        pipeline.update_job(self.job,self.db,
            state="attachment_wait",completed_at=when,
            attachment_url="https://batatlas.netservicos.com.br/app-1//RELATORIOS/261023/Relatorio_Equipamentos_Analitico_2345.xls")

    def test_restrict_report_download_urls(self):
        good="https://batatlas.netservicos.com.br/app-1//RELATORIOS/261023/Relatorio_Equipamentos_Analitico_2345.xls"
        self.assertTrue(pipeline.valid_report_url(good))
        for malicious in (
            "https://evil.example/app-1//RELATORIOS/261023/file.xls",
            "http://batatlas.netservicos.com.br/app-1//RELATORIOS/261023/file.xls",
            "https://batatlas.netservicos.com.br.evil.example/app-1//RELATORIOS/261023/file.xls",
            "https://batatlas.netservicos.com.br/app-1//RELATORIOS/../../secret.xls",
            good+"?cookie=abc",
            "https://x@batatlas.netservicos.com.br/app-1//RELATORIOS/261023/file.xls",
        ):
            self.assertFalse(pipeline.valid_report_url(malicious),malicious)

    def test_404_schedules_retry_for_same_queue_without_new_atlas_report(self):
        self.ready()
        first=pipeline.fetch_file(self.job,self.db,chrome_factory=FakeChrome,clock=lambda:200)
        self.assertEqual(first["state"],"attachment_wait")
        self.assertEqual(first["http_code"],404)
        self.assertEqual(first["retry_after"],30)
        second=pipeline.fetch_file(self.job,self.db,chrome_factory=FakeChrome,clock=lambda:220)
        self.assertEqual(second["state"],"retry_scheduled")
        self.assertEqual(FakeChrome.created,1)
        self.assertEqual(read_job(self.job,self.db)["remote_queue_id"],"276841868")

    def test_enforce_30_seconds_after_completed(self):
        self.ready(when=100)
        response=pipeline.fetch_file(self.job,self.db,chrome_factory=FakeChrome,clock=lambda:115)
        self.assertEqual(response["state"],"waiting_30_seconds")
        self.assertEqual(FakeChrome.created,0)

    def test_successful_read_after_reauthentication_clears_session_error(self):
        from unittest.mock import patch
        pipeline.update_job(self.job,self.db,error_code='atlas_auth_required')
        with patch.object(pipeline,'evaluate_query',return_value={'state':'processing'}):
            result=pipeline.poll_report(self.job,self.db,browser_factory=FakeChrome)
        self.assertEqual(result['state'],'processing')
        self.assertEqual(read_job(self.job,self.db)['error_code'],'')
        self.assertEqual(result['remote_queue_id'],'276841868')

    def test_unknown_report_and_missing_link_are_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.fetch_file("0"*32,self.db,chrome_factory=FakeChrome)
        with self.assertRaises(ValueError):
            pipeline.fetch_file(self.job,self.db,chrome_factory=FakeChrome)


if __name__=="__main__":
    unittest.main()
