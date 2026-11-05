"""Source-only, permission-safe Imperium extraction for an authorized Natal profile."""
import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from imperium_source_http import ImperiumSourceCatalog,source_route
from stock_analysis_http import StockAnalysisService,xlsx
from equipment_daily_catalog import _xlsx_rows

URL="/api/stock/analyses/imperium"
QUERY=URL+"/runs?city=natal&start=2026-11-03&end=2026-11-03"
DATA={
 "consolidado":[{"Grupo":"A","CodigoEquipamento":"01234","Equipamento":"TEST ITEM",
                 "Qtd":"5.00","Identificado":"S"}],
 "por_os":[{"DataBaixa":"2026-11-03T11:00:00","NumOs":"42",
            "NumeroWO":"00123","CodigoEquipamento":"01234",
            "Equipamento":"TEST ITEM","Qtd":"5.00","SerialNumber":"SECRET-SAMPLE"}]
}

class TestSource(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory()
  self.addCleanup(self.d.cleanup)
  self.fetcher=Mock(return_value=DATA)
  self.s=ImperiumSourceCatalog(root=Path(self.d.name), fetcher=self.fetcher,workbook=xlsx)
  self.body={"city":"natal","start":"2026-11-03","end":"2026-11-03"}
  self.actor="user-123"
 def extract(self, body=None, actor=None):
  return self.s.handle("POST",URL+"/extract",actor or self.actor,body or self.body)
 def test_routes_strict(self):
  self.assertEqual(source_route("POST",URL+"/extract"),("extract",None))
  self.assertEqual(source_route("GET",QUERY)[0],"list")
  self.assertIsNone(source_route("POST",URL+"/extract?city=natal"))
  self.assertIsNone(source_route("GET",URL+"/runs?city=all&start=2026-11-03&end=2026-11-03"))
  self.assertIsNone(source_route("DELETE",URL+"/extract"))
  self.assertIsNone(source_route("GET",URL+"/runs/foo/export"))
 def test_extract_and_persist_two_actual_source_tabs(self):
  status,response,mime=self.extract()
  self.assertEqual(status,201,response)
  self.assertTrue(response["ok"])
  self.assertFalse(response["selected"]["complete_six_tab_analysis"])
  self.assertEqual(response["selected"]["counts"]["Consolidado Imperium"],1)
  self.assertEqual(response["selected"]["counts"]["Por OS Imperium"],1)
  self.fetcher.assert_called_once()
  self.assertEqual(self.fetcher.call_args.kwargs["partner_id"],1)
  self.assertEqual(self.fetcher.call_args.kwargs["profile"],"natal")
  run=response["selected"]["id"]
  code,listing,_=self.s.handle("GET",QUERY,self.actor)
  self.assertEqual(code,200)
  self.assertEqual(listing["history"][0]["id"],run)
  self.assertTrue(listing["extraction_enabled"])
  code,preview,_=self.s.handle("GET",URL+"/runs/"+run+"/sheets/1",self.actor)
  self.assertEqual(code,200)
  self.assertEqual(preview["total"],1)
  self.assertEqual(preview["rows"][0][preview["header"].index("NumeroWO")],"00123")
  code,raw,mime=self.s.handle("GET",URL+"/runs/"+run+"/export",self.actor)
  self.assertEqual(code,200)
  self.assertTrue(raw.startswith(b"PK\x03\x04"))
  # Six-tab reference parser must refuse this source-only file.
  with self.assertRaises(ValueError):
   _xlsx_rows(raw)
 def test_duplicate_run_reused(self):
  one=self.extract()[1]["selected"]["id"]
  code,second,_=self.extract()
  self.assertEqual(code,200,second)
  self.assertTrue(second["reused"])
  self.assertEqual(second["selected"]["id"],one)
 def test_mossoro_never_uses_natal_partner(self):
  code,resp,_=self.extract({"city":"mossoro","start":"2026-11-03","end":"2026-11-03"})
  self.assertEqual(code,409)
  self.assertEqual(resp["code"],"city_not_homologated")
  self.fetcher.assert_not_called()
  code,resp,_=self.s.handle("GET",URL+"/runs?city=mossoro&start=2026-11-03&end=2026-11-03",self.actor)
  self.assertEqual(code,200)
  self.assertFalse(resp["extraction_enabled"])
 def test_reject_all_and_invalid_period_and_actor(self):
  self.assertEqual(self.extract({"city":"all","start":"2026-11-03","end":"2026-11-03"})[0],400)
  self.assertEqual(self.extract({"city":"natal","start":"2026-11-05","end":"2026-11-03"})[0],400)
  self.assertEqual(self.extract(actor="viewer")[0],403)
  self.fetcher.assert_not_called()
 def test_no_partial_on_network_failure(self):
  self.fetcher.side_effect=TimeoutError("secret credentials should never appear")
  status,result,_=self.extract()
  self.assertEqual(status,503)
  self.assertNotIn("secret credentials",result["error"])
  self.assertEqual(self.s.handle("GET",QUERY,self.actor)[1]["history"],[])
 def test_concurrent_extract_returns_explicit_busy(self):
  self.s.busy.acquire()
  try:self.assertEqual(self.extract()[1]["code"],"imperium_busy")
  finally:self.s.busy.release()
  self.fetcher.assert_not_called()
 def test_stock_service_routes_to_source_without_atlas_queue(self):
  reports=StockAnalysisService(root=Path(self.d.name)/"report",atlas_db=Path(self.d.name)/"missing.sqlite",start_worker=False)
  try:
   reports.imperium_source.fetcher=self.fetcher
   code,result,_=reports.handle("POST",URL+"/extract",self.actor,self.body)
   self.assertEqual(code,201,result)
   code,history,_=reports.handle("GET",QUERY,self.actor)
   self.assertEqual(code,200)
   self.assertEqual(len(history["history"]),1)
  finally:reports.close()

if __name__=="__main__":unittest.main()
