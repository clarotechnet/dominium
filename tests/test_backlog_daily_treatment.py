"""Daily route status and existing five-bucket TOA export safety regression."""
import base64
import datetime as dt
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from backlog_daily_treatment import classify_route_activity
from backlog_toa_route import TOADailyRouteExporter, TOA_ROUTES
from backlog_imperium_service import BacklogHistoryService


class TreatmentTests(unittest.TestCase):
    def test_pending_never_improductive(self):
        for st in ("pendente","em rota","iniciado"):
            label,code=classify_route_activity(st,"")
            self.assertNotIn("IMPRODUTIVA",label)
            self.assertIsNone(code)
        self.assertEqual(classify_route_activity("pendente","306 - NAO RESIDE")[0],
                         "DIVERGENCIA: CODIGO COM STATUS EM ABERTO")

    def test_improductive_requires_completed_and_verified_code(self):
        self.assertEqual(classify_route_activity("concluído","106 - AUSENTE"),
                         ("IMPRODUTIVA CONFIRMADA","106"))
        self.assertEqual(classify_route_activity("concluído","404 - CLIENTE RECUSA"),
                         ("IMPRODUTIVA CONFIRMADA","404"))
        self.assertEqual(classify_route_activity("concluído","101 - ENDERECO NAO LOCALIZADO"),
                         ("IMPRODUTIVA CONFIRMADA","101"))
        self.assertEqual(classify_route_activity("concluído","306 - NAO RESIDE"),
                         ("IMPRODUTIVA CONFIRMADA","306"))
        self.assertEqual(classify_route_activity("concluído","430 - EQUIPAMENTO RETIRADO"),
                         ("PRODUTIVA CONFIRMADA","430"))
        self.assertEqual(classify_route_activity("concluído","706 - NAO DEFINIDO")[0],
                         "BAIXADA - VALIDAR CODIGO")
        self.assertEqual(classify_route_activity("concluído","")[0],
                         "CONCLUIDA SEM CODIGO")

    def test_import_preserves_daily_status(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=BacklogHistoryService(Path(folder)/"test.sqlite",{},clock=lambda:dt.date.today())
            csv_text="Recurso,Data,Status da Atividade,Cidade,Contrato,Número da WO,Cód de Baixa 1\n"
            csv_text+="A,03/11/26,pendente,MOSSORO,1234567,101,\n"
            csv_text+="A,03/11/26,pendente,MOSSORO,1234568,102,306 - NAO RESIDE\n"
            csv_text+="B,03/11/26,concluído,MOSSORO,1234569,103,106 - AUSENTE\n"
            item={"name":"Atividades-MRO-DMV_03_11_26.csv",
                  "base64":base64.b64encode(csv_text.encode()).decode()}
            svc.import_route_files([item])
            report=svc.daily_treatment()
            self.assertEqual(report["counts"]["PENDENTE"],1)
            self.assertEqual(report["counts"]["IMPRODUTIVA CONFIRMADA"],1)
            self.assertEqual(report["counts"]["DIVERGENCIA: CODIGO COM STATUS EM ABERTO"],1)
            self.assertEqual(len(report["sources"]),1)
            self.assertEqual(report["total"],3)
            self.assertTrue(all(x["activity_date"]=="03/11/26" for x in report["rows"]))


class FakeResult:
    def __init__(self,payload,returncode=0):
        self.stdout=json.dumps(payload)
        self.stderr=""
        self.returncode=returncode


class ExportTests(unittest.TestCase):
    def test_five_exports_only_from_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            helper=Path(folder)/"toa_secondary_bucket_export.mjs"
            helper.write_text("// mocked")
            commands=[]
            def fake_run(argv,**kw):
                commands.append(argv)
                if argv[2]=="list":
                    return FakeResult({"ok":True,"buckets":[{"name":route} for route in TOA_ROUTES]})
                return FakeResult({"ok":True,"result":{"format":"csv","filename":"ignored",
                    "csv":"Login do Técnico,Cidade,Contrato\nA,MOSSORO,1234567\n"}})
            exporter=TOADailyRouteExporter(helper,runner=fake_run)
            files=exporter.fetch(dt.date.today())
            self.assertEqual(len(files),5)
            self.assertEqual([cmd[2] for cmd in commands],["list"]+["export"]*5)
            self.assertEqual([cmd[3] for cmd in commands[1:]],list(TOA_ROUTES))
            self.assertEqual([file["name"].split("_")[0] for file in files],
                             ["Atividades-"+x.split("_")[0] for x in TOA_ROUTES])
            self.assertTrue(all(base64.b64decode(x["base64"]).startswith(b"\xef\xbb\xbf") for x in files))

    def test_missing_bucket_rejects_everything(self):
        with tempfile.TemporaryDirectory() as folder:
            helper=Path(folder)/"toa_secondary_bucket_export.mjs"
            helper.write_text("// mocked")
            def fake_run(argv,**kw):
                return FakeResult({"ok":True,"buckets":[{"name":"MRO-DMV"}]})
            exporter=TOADailyRouteExporter(helper,runner=fake_run)
            with self.assertRaisesRegex(RuntimeError,"Buckets DMV indisponiveis"):
                exporter.fetch(dt.date.today())

if __name__=="__main__":
    unittest.main()
