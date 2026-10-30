"""Daily equipment workbooks are by date and city, never the Atlas QUERY."""
import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from equipment_daily_catalog import DailyEquipmentCatalog,TABS,parse_route,previous_day,_xlsx_rows
from stock_analysis_http import xlsx,StockAnalysisService

class DailyEquipmentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.c=DailyEquipmentCatalog(Path(self.temp.name))
  self.actor="user-123"
  self.sheets=[(name,[["Serial","Data","Usuario"],["ABCDEF123456","46000","TECNICO A"]])
                for name in TABS]
  self.raw=xlsx(self.sheets)
  self.body={"city":"natal","date":"2026-10-28","filename":"ANALISES NATAL 28.10.2026.xlsx",
             "content_base64":base64.b64encode(self.raw).decode()}
 def test_import_six_sheets_shared_between_users(self):
  code,created,_=self.c.handle("POST","/api/stock/analyses/daily/import",self.actor,self.body)
  self.assertEqual(code,201,created)
  self.assertEqual(created["selected"]["date"],"2026-10-28")
  self.assertEqual(len(created["selected"]["counts"]),6)
  run=created["selected"]["id"]
  code,data,_=self.c.handle("GET","/api/stock/analyses/daily?city=natal","user-999")
  self.assertEqual(code,200)
  self.assertEqual(data["latest"]["id"],run)
  code,tab,_=self.c.handle("GET",f"/api/stock/analyses/daily/{run}/sheets/2","user-999")
  self.assertEqual(code,200)
  self.assertEqual(tab["name"],"IMPERIUM")
  self.assertEqual(tab["rows"][0][0],"ABCDEF123456")
  code,blob,mime=self.c.handle("GET",f"/api/stock/analyses/daily/{run}/export","user-999")
  self.assertEqual(blob,self.raw)
  self.assertIn("sheet",mime)
  self.assertEqual(self.c.handle("POST","/api/stock/analyses/daily/import","user-999",self.body)[1]["reused"],True)
 def test_date_and_city_are_strict(self):
  self.assertIsNone(parse_route("GET","/api/stock/analyses/daily?city=all"))
  self.assertIsNone(parse_route("GET","/api/stock/analyses/daily?city=natal&date=2026-15-40"))
  self.assertIsNone(parse_route("DELETE","/api/stock/analyses/daily/import"))
  self.assertEqual(self.c.handle("GET","/api/stock/analyses/daily?city=recife",self.actor)[1]["latest"],None)
  self.assertEqual(self.c.handle("POST","/api/stock/analyses/daily/import",self.actor,{**self.body,"city":"all"})[0],400)
  self.assertIsNotNone(previous_day())
 def test_old_report_not_regenerated_from_atlas(self):
  with tempfile.TemporaryDirectory() as d:
   service=StockAnalysisService(root=Path(d)/"reports",atlas_db=Path(d)/"noatlas.sqlite",start_worker=False)
   try:
    code,result,_=service.handle("POST","/api/stock/analyses/jobs",self.actor,{"city":"natal","kind":"equipamentos"})
    self.assertEqual(code,409)
    self.assertIn("Imperium",result["error"])
   finally:service.close()
 def test_reject_invalid_and_fake_xlsx(self):
  payload={**self.body,"content_base64":base64.b64encode(b"PK\x03\x04not excel").decode()}
  self.assertEqual(self.c.handle("POST","/api/stock/analyses/daily/import",self.actor,payload)[0],503)
  payload={**self.body,"filename":"archive.exe"}
  self.assertEqual(self.c.handle("POST","/api/stock/analyses/daily/import",self.actor,payload)[0],400)

if __name__=="__main__":unittest.main()
