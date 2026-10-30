import base64
import datetime as dt
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from backlog_imperium_service import BacklogHistoryService

class FakeOrder:
    id_os=101
    num_os="2600000001"
    contract="1234567"
    service="DESCONEXAO"

class FakeAPI:
    def __init__(self):self.calls=[]
    def list_orders(self,date,*,status,service_type):
        self.calls.append(("list",date,status,service_type))
        return [FakeOrder()] if status == "completed" else []
    def _fetch_main_payload(self,date,*,status,service_type):
        self.calls.append(("raw_all",status,service_type))
        return [FakeOrder()]
    def _parse_orders(self,payload):
        return payload
    def _fetch_detail(self,order_id,timeout):
        self.calls.append(("detail",order_id))
        return b"confirmed"
    def _detail_close_code(self,detail):
        return "106"

class BacklogServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.api=FakeAPI()
        self.svc=BacklogHistoryService(
            Path(self.tmp.name)/"history.sqlite",
            {key:SimpleNamespace(api=self.api) for key in ["natal","fortaleza","mossoro","recife"]},
            clock=lambda:dt.date(2026,10,30),sleep=lambda sec:None,
        )
    def join(self):
        self.svc._runner.join(4)
        self.assertFalse(self.svc._runner.is_alive())
        self.assertEqual(self.svc.snapshot()["run"]["status"],"completed")

    def test_probe_reads_but_does_not_store(self):
        self.svc.start(mode="probe",only_profile="natal")
        self.join()
        state=self.svc.snapshot()
        self.assertEqual(state["history"],{})
        self.assertEqual(state["checkpoints"],{})
        self.assertEqual(state["run"]["imported"],1)

    def test_incremental_progress_persists_and_deduplicates(self):
        self.svc.start(mode="batch",days_per_profile=1,only_profile="natal")
        self.join()
        st=self.svc.snapshot()
        self.assertEqual(st["history"]["confirmed"],1)
        self.assertEqual(st["checkpoints"]["natal"],"2025-10-30")
        self.svc.start(mode="batch",days_per_profile=1,only_profile="natal")
        self.join()
        st=self.svc.snapshot()
        self.assertEqual(st["history"]["confirmed"],2)
        self.assertEqual(st["checkpoints"]["natal"],"2025-10-31")
        new=BacklogHistoryService(Path(self.tmp.name)/"history.sqlite",
            {"natal":SimpleNamespace(api=self.api)},clock=lambda:dt.date(2026,10,30))
        self.assertEqual(new.snapshot()["checkpoints"]["natal"],"2025-10-31")
        self.assertEqual(new.fora_rota(profile="natal")["candidates"][0]["contract"],"1234567")

    def test_reject_bad_limits(self):
        with self.assertRaises(ValueError):self.svc.start(mode="batch",days_per_profile=60)

    def test_sent_does_not_close_os(self):
        self.svc.mark_sent({"profile":"natal","contract":"1234567","note":"Mensagem copiada"})
        self.assertEqual(len(self.svc.list_sent()["rows"]),1)
        self.assertEqual(self.api.calls,[])

    def test_xlsx_manual_route_import(self):
        try:from openpyxl import Workbook
        except ImportError:self.skipTest("openpyxl not installed in dev")
        wb=Workbook();sh=wb.active
        sh.append(["Recurso","Login do Técnico","Data","Cidade","Contrato","Bairro","Janela de Serviço","Número da WO"])
        sh.append(["TECNICO TESTE","Z123","30/10/26","NATAL",1234567,"PONTA NEGRA","08 - 12","12345"])
        out=io.BytesIO();wb.save(out)
        result=self.svc.import_route_files([{"name":"Atividades-NTL-DMV_30_10_26.xlsx",
           "base64":base64.b64encode(out.getvalue()).decode("ascii")}])
        self.assertEqual(result["files"][0]["rows"],1)
        self.assertEqual(self.svc.compare()["rows"][0]["contract"],"1234567")
        self.svc.start(mode="batch",days_per_profile=1,only_profile="natal");self.join()
        self.assertEqual(self.svc.compare()["rows"][0]["historical_code"],"106")

if __name__=="__main__":unittest.main()
