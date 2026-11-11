"""Synthetic reconciliation tests, no real DataSnap, no live backlog writes."""
import datetime as dt
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from backlog_route_today_compare import reconcile_today

DAY=dt.date(2026,11,11)
def setup():
    tmp=tempfile.TemporaryDirectory()
    path=Path(tmp.name)
    current=path/"current.sqlite3"
    backlog=path/"backlog.sqlite3"
    with closing(sqlite3.connect(current)) as c, c:
        c.execute("CREATE TABLE snapshots(profile TEXT,day TEXT,count INTEGER,captured_at TEXT,sha256 TEXT)")
        c.execute("""CREATE TABLE current_os(profile TEXT,day TEXT,id_os INTEGER,
          os_number TEXT,contract TEXT,city TEXT,status TEXT,close_code TEXT,
          captured_at TEXT,work_order TEXT)""")
        c.executemany("INSERT INTO snapshots VALUES(?,?,?,?,?)",
                      [(p,DAY.isoformat(),1,"now","abc") for p in
                       ("natal","fortaleza","mossoro","recife")])
        c.executemany("INSERT INTO current_os VALUES(?,?,?,?,?,?,?,?,?,?)",[
            ("natal",DAY.isoformat(),1,"2661","1231232","NATAL","EM CAMPO","430","now","01695/741785997"),
            ("natal",DAY.isoformat(),2,"2662","1231233","PARNAMIRIM","CONCLUIDA","430","now","01695/741785998"),
            ("natal",DAY.isoformat(),3,"2663","1231234","NATAL","CONCLUIDA","430","now","01695/741785999"),
            ("natal",DAY.isoformat(),4,"2664","1231234","NATAL","CONCLUIDA","430","now","01695/741786000")
        ])
    with closing(sqlite3.connect(backlog)) as c, c:
        c.execute("CREATE TABLE route_batches(route_hash TEXT,filename TEXT)")
        c.execute("""CREATE TABLE route_rows(route_hash TEXT,contract TEXT,city TEXT,
          os_number TEXT,route_code TEXT,activity_status TEXT,activity_type TEXT,
          activity_date TEXT,row_num INTEGER)""")
        c.execute("CREATE TABLE history(value TEXT)")
        c.execute("INSERT INTO history VALUES('immutable')")
        c.execute("INSERT INTO route_batches VALUES('h','TOA.csv')")
        for i,contract,city,os,code,status in [
          (1,"1231232","NATAL/PARNAMIRIM","01695|741785997","106 - TEST","concluído"),
          (2,"1231233","NATAL/PARNAMIRIM","NOT_EXIST","430 - TEST","concluído"),
          (3,"1231234","NATAL/PARNAMIRIM","NOT_EXIST","430 - TEST","concluído"),
          (4,"1231235","FORTALEZA","NOT_EXIST","106 - TEST","pendente"),
          (5,"1231236","MACEIO","NOT_EXIST","430 - TEST","pendente")]:
          c.execute("INSERT INTO route_rows VALUES(?,?,?,?,?,?,?,?,?)",
                  ("h",contract,city,os,code,status,"DESC","11/11/26",i))
    return tmp,backlog,current

class Tests(unittest.TestCase):
    def test_comparison_is_read_only_and_fails_closed_on_ambiguity(self):
        tmp,backlog,current=setup()
        try:
            result=reconcile_today(backlog,current,DAY)
            self.assertEqual(result["route_rows"],5)
            self.assertEqual(result["matches"],{
              "exact_wo":1,"unique_contract_no_wo":1,
              "ambiguous_contract":1,"missing_in_imperium_snapshot":1,
              "unsupported_city":1})
            self.assertEqual(result["discrepancies"],{
              "code_mismatch_exact_wo":1,"toa_complete_imperium_open":1})
            self.assertTrue(result["read_only"])
            by_contract={x["contract"]:x for x in result["rows"]}
            self.assertEqual(by_contract["1231232"]["imperium_status"],"EM CAMPO")
            self.assertEqual(by_contract["1231234"]["match"],"ambiguous_contract")
            with closing(sqlite3.connect(backlog)) as c, c:
                self.assertEqual(c.execute("SELECT value FROM history").fetchone()[0],"immutable")
        finally:
            tmp.cleanup()
    def test_incomplete_sources_block_claims(self):
        tmp,backlog,current=setup()
        try:
            with closing(sqlite3.connect(current)) as c, c:
                c.execute("DELETE FROM snapshots WHERE profile='mossoro'")
            with self.assertRaises(ValueError):
                reconcile_today(backlog,current,DAY)
            with self.assertRaises(ValueError):
                reconcile_today(backlog,current,DAY,limit=9999)
        finally:
            tmp.cleanup()
    def test_missing_sources_never_create_empty_files(self):
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/"none.db"
            b=Path(root)/"none2.db"
            with self.assertRaises(FileNotFoundError):
                reconcile_today(a,b,DAY)
            self.assertFalse(a.exists())
            self.assertFalse(b.exists())
if __name__=="__main__":
    unittest.main()
