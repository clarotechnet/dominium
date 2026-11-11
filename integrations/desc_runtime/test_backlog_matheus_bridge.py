"""Synthetic bridge tests. Preserve the existing sidecar import behavior."""
import datetime as dt
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backlog_imperium_service import BacklogHistoryService
from backlog_matheus_bridge import BacklogWithMatheusCurrent,LOCAL_TZ

TIME=dt.datetime(2026,11,11,15,0,tzinfo=LOCAL_TZ)
def sample(profile):
    cities={"natal":"NATAL","fortaleza":"FORTALEZA",
            "mossoro":"MOSSORO","recife":"RECIFE"}
    return [{"IdOs":100+list(cities).index(profile),"NumeroContrato":1231232,
      "NumOs":"2665340532","NumeroWO":"01695/741785997",
      "Cidade":cities[profile],"Servico":"RETIRAR EQUIPAMENTO",
      "NomeAbreviado":"TECH","CodigoBaixa":430,"Status":2}]

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.calls=[]
        self.gates=[]
        self.time=TIME
        def fetch(profile,start,end,kind):
            self.calls.append((profile,start,end,kind))
            return sample(profile)
        def gate():
            self.gates.append(True)
        self.service=BacklogWithMatheusCurrent(
            self.path/"backlog.sqlite3",{},operation_gate=threading.RLock(),
            current_db_path=self.path/"current.sqlite3",report_fetcher=fetch,
            current_gate=gate,current_now=lambda:self.time)
    def tearDown(self):
        thread=self.service._current_job_thread
        if thread:thread.join(timeout=5)
        self.tmp.cleanup()
    def test_trigger_refreshes_all_profiles_and_preserves_original_history(self):
        start=self.service.trigger_current_refresh()
        self.assertTrue(start["started"])
        self.service._current_job_thread.join(timeout=5)
        result=self.service.current_status()
        self.assertEqual(result["job"]["state"],"completed")
        self.assertEqual(len(self.calls),4)
        self.assertEqual(len(result["profiles"]),4)
        self.assertTrue(result["fresh"])
        self.assertEqual(result["routes"]["route_rows"],0)
        with closing(sqlite3.connect(self.path/"backlog.sqlite3")) as con:
            self.assertEqual(con.execute("select count(*) from history").fetchone()[0],0)
    def test_route_import_callback_starts_read_only_refresh(self):
        with patch.object(BacklogHistoryService,"import_route_files",return_value={"ok":True}) as old:
            response=self.service.import_route_files([{"synthetic":True}])
            self.assertEqual(response,{"ok":True})
            old.assert_called_once()
        self.service._current_job_thread.join(timeout=5)
        self.assertEqual(self.service.current_status()["job"]["state"],"completed")
    def test_after_21_no_unattended_data_snap_queries(self):
        self.time=TIME.replace(hour=21)
        start=self.service.trigger_current_refresh()
        self.assertFalse(start["started"])
        self.assertEqual(start["reason"],"outside_working_hours")
        self.assertFalse(self.calls)
    def test_datapsnap_gate_failure_preserves_prior_snapshot_and_route_import(self):
        self.service.trigger_current_refresh()
        self.service._current_job_thread.join(timeout=5)
        before=self.service.current_status()["profiles"]
        self.service._current.gate=lambda: (_ for _ in ()).throw(RuntimeError("busy"))
        with patch.object(BacklogHistoryService,"import_route_files",return_value={"ok":True}):
            self.assertTrue(self.service.import_route_files([{"synthetic":True}])["ok"])
        self.service._current_job_thread.join(timeout=5)
        after=self.service.current_status()
        self.assertEqual(after["job"]["state"],"failed")
        self.assertEqual(after["job"]["last_error"],"RuntimeError")
        self.assertEqual(after["profiles"],before)
if __name__=="__main__":
    unittest.main()
