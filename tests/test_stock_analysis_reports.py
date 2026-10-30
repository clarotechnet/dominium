"""Tests for safe, cached, actor-scoped stock analysis report generation."""
import json
import sqlite3
import sys
import tempfile
import time
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from stock_analysis_http import StockAnalysisService, route_for, build_sheets, xlsx

ACTOR="user-123"
ROWS=[
 {"numero_serie":"ABC123456789","codigo_material_sap":"000000000041001277",
  "codigo_sap_normalizado":"41001277","modelo":"TERMINAL GPON",
  "enderecavel_principal":"ABC123456789","estado":"SUSPEITO",
  "operacao":"NATAL","numero_contrato":"9001","data_ultima_alteracao":"2026-10-27",
  "responsavel":"TECNICO A"},
 {"numero_serie":"890000001234","codigo_material_sap":"PBL001",
  "codigo_sap_normalizado":"PBL001","modelo":"SIM CARD MOVEL",
  "enderecavel_principal":"890000001234","estado":"ANALISE DE INVENTARIO",
  "operacao":"NATAL","numero_contrato":"","data_ultima_alteracao":"2026-10-26",
  "responsavel":""}
]
class StockReportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  root=Path(self.temp.name)
  self.atlas=root/"atlas.sqlite3"
  with sqlite3.connect(self.atlas) as d:
   d.execute("CREATE TABLE query_jobs (id TEXT,city TEXT,created_by TEXT,state TEXT,created_at REAL, location TEXT)")
   d.execute("CREATE TABLE query_rows (job_id TEXT,position INTEGER,data TEXT)")
   d.execute("INSERT INTO query_jobs VALUES ('valid','natal',?,'ready',?,'empreiteira')",(ACTOR,time.time()-120))
   d.execute("INSERT INTO query_jobs VALUES ('failed','natal',?,'failed',?,'empreiteira')",(ACTOR,time.time()))
   d.execute("INSERT INTO query_jobs VALUES ('other','natal','user-999','ready',?,'empreiteira')",(time.time()+5,))
   d.executemany("INSERT INTO query_rows VALUES ('valid',?,?)",
                  [(i,json.dumps(row)) for i,row in enumerate(ROWS)])
  # sqlite3's context manager commits but does not close on Windows.
  d.close()
  self.service=StockAnalysisService(root=root/"output",atlas_db=self.atlas,start_worker=False)
  self.addCleanup(self.service.close)
 def test_routes_are_tightly_bounded(self):
  self.assertEqual(route_for("GET","/api/stock/analyses/available?city=natal"),("available","natal"))
  self.assertIsNone(route_for("DELETE","/api/stock/analyses/jobs"))
  self.assertIsNone(route_for("GET","/api/stock/analyses/available?city=all"))
  self.assertIsNone(route_for("POST","/api/stock/analyses/jobs/f"*32))
 def test_latest_valid_query_ignores_failed_newer_and_other_operator(self):
  status,data,_=self.service.handle("GET","/api/stock/analyses/available?city=natal",ACTOR)
  self.assertEqual(status,200)
  self.assertEqual(data["latest"]["id"],"valid")
  self.assertEqual(data["latest"]["total_rows"],2)
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/available?city=natal","user-555")[1]["latest"]["id"],"valid")
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/available?city=mossoro",ACTOR)[1]["latest"],None)
 def test_latest_shared_between_authorized_operators_but_never_other_locations(self):
  with sqlite3.connect(self.atlas) as db:
   db.execute("INSERT INTO query_rows VALUES ('other',0,?)",(json.dumps(ROWS[0]),))
   db.execute("INSERT INTO query_jobs VALUES ('other_location','natal','user-999','ready',?,'assinante')",(time.time()+30,))
   db.execute("INSERT INTO query_rows VALUES ('other_location',0,?)",(json.dumps(ROWS[0]),))
  db.close()
  latest=self.service.handle("GET","/api/stock/analyses/available?city=natal","user-555")[1]["latest"]
  self.assertEqual(latest["id"],"other")  # validated QUERY produced by another operator
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/available?city=recife",ACTOR)[1]["latest"],None)
  status,data,_=self.service.handle("POST","/api/stock/analyses/jobs","user-555",{"city":"natal","kind":"query"})
  self.assertEqual(status,202)
  self.assertEqual(data["job"]["query_id"],"other")
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/jobs",ACTOR)[1]["jobs"],[])

 def test_report_jobs_idempotent_and_scope_actor(self):
  status,created,_=self.service.handle("POST","/api/stock/analyses/jobs",ACTOR,
                                     {"city":"natal","kind":"query"})
  self.assertEqual(status,202)
  self.assertEqual(self.service.handle("POST","/api/stock/analyses/jobs",ACTOR,
                              {"city":"natal","kind":"query"})[1]["reused"],True)
  target=created["job"]["id"]
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/jobs/"+target,"user-999")[0],404)
  self.assertEqual(self.service.handle("GET","/api/stock/analyses/jobs/"+target+"/export",ACTOR)[0],409)
  with self.service._connect() as con:
   job=con.execute("SELECT * FROM jobs WHERE id=?",(target,)).fetchone()
  summary=self.service._run_one(job)
  self.assertFalse(summary["parcial"])
  with self.service._connect() as con:
   con.execute("UPDATE jobs SET state='ready',summary=? WHERE id=?",(json.dumps(summary),target))
  status,content,mime=self.service.handle("GET","/api/stock/analyses/jobs/"+target+"/export",ACTOR)
  self.assertEqual(status,200)
  with zipfile.ZipFile(BytesIO(content)) as z:
   self.assertIn("xl/worksheets/sheet1.xml",z.namelist())
   xml=z.read("xl/worksheets/sheet1.xml").decode()
   self.assertIn("41001277",xml)
   self.assertIn("PBL001",xml)
 def test_xlsx_has_valid_openxml_package_relationships(self):
  import xml.etree.ElementTree as ET
  raw=xlsx([("QUERY Tratada",[["Material","Serie"],["22025245","X012"]]),("Fontes e criterios",[["Fonte","Atlas"]])])
  ns="{http://schemas.openxmlformats.org/package/2006/relationships}"
  with zipfile.ZipFile(BytesIO(raw)) as z:
   self.assertIsNone(z.testzip())
   root=ET.fromstring(z.read("_rels/.rels"))
   workbook_rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
   self.assertEqual(root.tag,ns+"Relationships")
   self.assertEqual(workbook_rels.tag,ns+"Relationships")
   self.assertEqual(len(list(workbook_rels)),2)
   self.assertEqual(list(root)[0].get("Target"),"xl/workbook.xml")
   for name in z.namelist():
    if name.endswith((".xml",".rels")) or name=="[Content_Types].xml":
     ET.fromstring(z.read(name))

 def test_equipment_sheets_are_conservative(self):
  sheets,summary=build_sheets("equipamentos",ROWS,"natal","valid",time.time())
  self.assertEqual([s[0] for s in sheets[:6]],[
    "Atlas","Chips Atlas","IMPERIUM","CHIP IMPERIUM","Assinantes","Nomes."])
  self.assertEqual(len(sheets[2][1]),1)
  self.assertTrue(summary["parcial"])
  self.assertEqual(sheets[4][1][1][-1],"Pendente de conferencia")
 def test_suspects_and_formula_escape(self):
  sheets,summary=build_sheets("suspeitos",ROWS,"natal","valid",time.time())
  self.assertEqual(summary["total"],2)
  self.assertTrue(summary["parcial"])
  raw=xlsx([("Teste",[["Serial","Teste"],["ABC","=HYPERLINK()"]])])
  with zipfile.ZipFile(BytesIO(raw)) as z:
   self.assertIn("'=HYPERLINK()",z.read("xl/worksheets/sheet1.xml").decode())
 def test_no_query_means_no_new_atlas_request(self):
  code,result,_=self.service.handle("POST","/api/stock/analyses/jobs","user-456",{"city":"mossoro","kind":"query"})
  self.assertEqual(code,409)
  self.assertIn("Nenhuma QUERY",result["error"])

if __name__=="__main__":unittest.main()
