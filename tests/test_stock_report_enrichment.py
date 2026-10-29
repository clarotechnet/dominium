"""DataSnap history must enrich reports without inventing physical stock or ownership."""
from __future__ import annotations
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from stock_report_enrichment import collect,target_serials,normalize_entry
from stock_analysis_http import build_sheets

class EnrichmentTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/"jobs.sqlite3"
  self.rows=[
   {"numero_serie":"ABCDEF123456","enderecavel_principal":"","estado":"SUSPEITO",
    "modelo":"ONT","numero_contrato":"1122","data_ultima_alteracao":"2026-10-15"},
   {"numero_serie":"INV@LID","enderecavel_principal":"334455667788",
    "estado":"ANÁLISE DE INVENTÁRIO","modelo":"SIM CARD","numero_contrato":"5533",
    "data_ultima_alteracao":"2026-10-18"},
   {"numero_serie":"ABCDEF123456","estado":"NORMAL","modelo":"ONT"},
  ]
 def test_real_fields_and_resume_cached_without_second_datasnap_call(self):
  calls=[]
  def consult(args):
   serials,mode,city=args
   calls.append((serials,mode,city))
   return {"ok":True,"results":[
     {"serial":serial,"datasnap":{"verified":True,"movements":[
         {"Id":2,"Contrato":"9988","Data":"2026-10-17"}]},
      "last_destination":{"stock_name":"Tecnico legado","movement":"TRANSFERENCIA","date":"17/10/2026"},
      "live":{"found":False,"verified":False}} for serial in serials]}
  job="a"*32
  evidence,summary=collect(job,"natal","suspeitos",self.rows,
                           db_path=self.path,consult=consult)
  self.assertEqual(summary["datasnap_total"],2)
  self.assertEqual(summary["datasnap_checked"],2)
  self.assertEqual(len(calls),1)
  self.assertEqual(len(evidence),2)
  self.assertFalse(evidence[0]["current_owner_verified"])
  self.assertEqual(evidence[0]["last_contract_historical"],"9988")
  sheets,analysis=build_sheets("suspeitos",self.rows,"natal","query",1,evidence)
  self.assertEqual(sheets[0][1][0][-1],"Divergencia historica")
  self.assertEqual(len(sheets[0][1][1]),len(sheets[0][1][0]))
  self.assertEqual(sheets[0][1][1][-1],"REVISAR datas")
  self.assertEqual(sheets[0][1][1][-3],"NAO CONFIRMADO")
  cached,again=collect(job,"natal","suspeitos",self.rows,db_path=self.path,consult=consult)
  self.assertEqual(len(calls),1)
  self.assertEqual(cached,evidence)
 def test_equipment_history_is_not_called_used_equipment(self):
  def consult(args):
   return {"ok":True,"results":[{"serial":s,"datasnap":{"verified":True,"movements":[]},
                                  "live":{"verified":False,"found":False}} for s in args[0]]}
  evidence,stats=collect("b"*32,"natal","equipamentos",self.rows,
                         db_path=self.path,consult=consult)
  sheets,summary=build_sheets("equipamentos",self.rows,"natal","query",1,evidence)
  self.assertEqual([x[0] for x in sheets[:6]],
                   ["Atlas","Chips Atlas","IMPERIUM","CHIP IMPERIUM","Assinantes","Nomes."])
  self.assertTrue(summary["parcial"])
  self.assertIn("NAO relatorio de equipamentos utilizados",str(sheets[2][1]))
 def test_unverified_datasnap_never_confirms_custody(self):
  entry=normalize_entry({"serial":"ABCDEF123456","datasnap":{"verified":False,"movements":[]},
                         "live":{"found":True,"verified":False,"owner":{"technician_name":"Fulano"}}})
  self.assertFalse(entry["history_verified"])
  self.assertFalse(entry["current_owner_verified"])
  self.assertEqual(entry["current_owner"],"")
 def test_source_error_is_persisted_as_unconfirmed(self):
  calls=[]
  def fail(args):
   calls.append(args)
   raise ConnectionError("offline")
  evidence,stats=collect("c"*32,"natal","suspeitos",self.rows,db_path=self.path,consult=fail)
  self.assertEqual(stats["datasnap_failed"],2)
  self.assertFalse(any(x["history_verified"] for x in evidence))
  self.assertEqual(len(calls),1)
  with closing(sqlite3.connect(self.path)) as db:
   self.assertEqual(db.execute("SELECT count(*) FROM report_evidence").fetchone()[0],2)

if __name__=="__main__":unittest.main()
