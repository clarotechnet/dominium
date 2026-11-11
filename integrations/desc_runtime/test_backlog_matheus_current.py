"""Synthetic-only regression tests: no DataSnap or production DB access."""
import datetime as dt
import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from backlog_matheus_current import MatheusCurrentSnapshot

NOW=dt.datetime(2026,11,11,15,0,0,tzinfo=dt.timezone(dt.timedelta(hours=-3)))
def row(ident=22,contract=1231232,city="NATAL",status=2,code=430):
    return {"IdOs":ident,"NumOs":2665340532+ident,
      "NumeroContrato":contract,"Cidade":city,"Status":status,
      "CodigoBaixa":code,"Servico":"RETIRAR EQUIPAMENTO",
      "NomeAbreviado":"SAULO DESC","DataBaixa":""}

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.guard_calls=[]
        self.rows=[row()]
        self.calls=[]
        def guard(): self.guard_calls.append(True)
        def fetch(*args):
            self.calls.append(args)
            return list(self.rows)
        self.snap=MatheusCurrentSnapshot(Path(self.tmp.name)/"latest.sqlite3",
            fetch=fetch,gate=guard,clock=lambda:NOW)
    def tearDown(self):
        self.tmp.cleanup()
    def test_atomic_snapshot_and_natal_parnamirim(self):
        self.rows=[row(),row(23,1231233,"PARNAMIRIM",1,None)]
        info=self.snap.refresh("natal")
        self.assertEqual(info["count"],2)
        self.assertEqual(info["cities"],{"NATAL":1,"PARNAMIRIM":1})
        self.assertEqual(self.calls,[("natal","2026-11-11","2026-11-11","all")])
        self.assertEqual(self.snap.contract("natal","1231232","2026-11-11")["rows"][0]["close_code"],"430")
        self.assertEqual(self.snap.contract("natal","1231233","2026-11-11")["rows"][0]["status"],"EM CAMPO")
        self.assertEqual(len(self.guard_calls),1)
        self.assertEqual(self.snap.summary()[0]["count"],2)
    def test_atomic_failure_does_not_replace_complete_snapshot(self):
        self.snap.refresh("natal")
        old=self.snap.summary()[0]["sha256"]
        for invalid in ([row(0)],[row(22),row(22)],[row(status=19)],
                        [row(contract="UNKNOWN")],[{"IdOs":55}], "broken"):
            self.rows=invalid
            with self.assertRaises(ValueError):
                self.snap.refresh("natal")
            self.assertEqual(self.snap.summary()[0]["sha256"],old)
            self.assertEqual(self.snap.contract("natal","1231232","2026-11-11")["match_count"],1)
    def test_manual_outside_toa_os_number_is_preserved_as_text(self):
        for number in ("1231232 1231232", "1231232  1231232",
                       "1231232 123123A", "123456789 123456789"):
            item=row()
            item["NumOs"]=number
            self.rows=[item]
            info=self.snap.refresh("natal")
            self.assertEqual(info["noncanonical_os_numbers"],1)
            self.assertEqual(self.snap.contract("natal","1231232","2026-11-11")["rows"][0]["os_number"],number)
        self.rows=[{**row(),"NumOs":"1231232 INVALID"}]
        with self.assertRaises(ValueError):
            self.snap.refresh("natal")

    def test_no_empty_clobber_of_non_empty_snapshot(self):
        self.snap.refresh("natal")
        self.rows=[]
        with self.assertRaises(ValueError):
            self.snap.refresh("natal")
        self.assertEqual(self.snap.summary()[0]["count"],1)
    def test_guard_failure_does_not_query_data(self):
        self.snap.gate=lambda: (_ for _ in ()).throw(RuntimeError("busy"))
        with self.assertRaises(RuntimeError):
            self.snap.refresh("natal")
        self.assertEqual(self.calls,[])
    def test_multios_returns_ambiguous_and_never_approves_write(self):
        self.rows=[row(),row(23,1231232)]
        self.snap.refresh("natal")
        actual=self.snap.contract("natal","1231232","2026-11-11")
        self.assertTrue(actual["ambiguous"])
        self.assertEqual(actual["match_count"],2)
        self.assertIn("Never authorize",actual["note"])
    def test_scope_dates_and_input_fail_closed(self):
        for profile,day in (("parnamirim",None),("natal","2026-12-01"),
                            ("natal","2026-10-01")):
            with self.assertRaises(ValueError):
                self.snap.refresh(profile,day)
        with self.assertRaises(ValueError):
            self.snap.contract("natal","../123","2026-11-11")
    def test_does_not_modify_existing_history_database(self):
        historic=Path(self.tmp.name)/"backlog.sqlite3"
        with closing(sqlite3.connect(historic)) as conn:
            conn.execute("CREATE TABLE history (value TEXT)")
            conn.execute("INSERT INTO history VALUES('original')")
            conn.commit()
        before=historic.read_bytes()
        self.snap.refresh("natal")
        self.assertEqual(historic.read_bytes(),before)
    def test_same_report_has_stable_sha_and_restores_after_failed_update(self):
        a=self.snap.refresh("natal")
        b=self.snap.refresh("natal")
        self.assertEqual(a["sha256"],b["sha256"])
        self.rows=[row(status=1,code=None)]
        c=self.snap.refresh("natal")
        self.assertNotEqual(c["sha256"],a["sha256"])
        self.assertEqual(self.snap.contract("natal","1231232","2026-11-11")["rows"][0]["status"],"EM CAMPO")

if __name__=="__main__":
    unittest.main()
