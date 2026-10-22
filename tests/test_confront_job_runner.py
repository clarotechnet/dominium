"""Durability, idempotency and recovery tests; synthetic providers only."""
import sys
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from confront_job_runner import ConfrontJobStore


class StubAtlas:
    def __init__(self):
        self.online = True
        self.busy = False
        self.calls = 0
        self.results = {}
        self.raise_enqueue = False
        self.response_ready = False

    def valid_serial(self, serial):
        return len(serial) == 12 and serial.isalnum()

    def status(self):
        return {"ok": True, "online": self.online,
                "pendingQueries": 1 if self.busy else 0}

    def enqueue(self, serial):
        self.calls += 1
        if self.raise_enqueue:
            raise TimeoutError()
        return f"request-{self.calls}"

    def poll_result(self, request_id, serial):
        if not self.response_ready:
            return None
        return {"ok": True, "requestId": request_id, "resultado": {
            "serial_consultado": serial, "estado": "SUSPEITO",
            "numero_contrato": "1111111", "serial_encontrado": True
        }}


class ConfrontDurableJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jobs.sqlite3"
        self.store = ConfrontJobStore(self.path)
        self.atlas = StubAtlas()
        self.calls = 0

    def imp(self, payload):
        self.calls += 1
        serial = payload[0][0]
        return {"ok": True, "results": [{
            "serial": serial,
            "datasnap": {"verified": True, "count": 1, "movements": []},
            "last_destination": {"stock_name": "Estoque antigo"},
            "live": {"verified": False, "found": False},
        }]}

    def test_progress_survives_reopen_without_repeating_queue(self):
        job = self.store.create("TEST00000001,TEST00000002", profile="natal", mode="analitico")
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000), "imperium_consulted")
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000), "atlas_enqueued")
        self.assertEqual(self.atlas.calls, 1)
        reopened = ConfrontJobStore(self.path)
        self.assertEqual(reopened.progress(job)["total"], 2)
        self.assertEqual(reopened.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1003), "atlas_waiting")
        self.assertEqual(self.atlas.calls, 1)
        self.atlas.response_ready = True
        self.assertEqual(reopened.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1008), "serial_complete")
        self.assertEqual(self.atlas.calls, 1)
        self.assertEqual(reopened.progress(job)["done"], 1)
        self.assertEqual(reopened.progress(job, include_rows=True)["rows"][0]["resultado"]["situacao"], "revisao")

    def test_existing_bot_queue_is_not_disrupted(self):
        job = self.store.create("TEST00000001", profile="recife", mode="sintetico")
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000)
        self.atlas.busy = True
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1001), "atlas_busy")
        self.assertEqual(self.atlas.calls, 0)
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1004), "idle")
        self.atlas.busy = False
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1010), "atlas_enqueued")

    def test_uncertain_post_never_requeues_automatically(self):
        job = self.store.create("TEST00000001", profile="mossoro", mode="analitico")
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000)
        self.atlas.raise_enqueue = True
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1001),
                         "atlas_submit_uncertain")
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1400),
                         "idle")
        self.assertEqual(self.atlas.calls, 1)
        self.assertEqual(self.store.progress(job)["states"], {"review_needed": 1})

    def test_expired_result_never_resubmitted(self):
        job = self.store.create("TEST00000001", profile="natal", mode="analitico")
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000)
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1001)
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=2000),
                         "atlas_result_expired")
        self.assertEqual(self.atlas.calls, 1)
        self.assertEqual(self.store.progress(job)["states"], {"review_needed": 1})

    def test_unsupported_atlas_serial_not_enqueued(self):
        job = self.store.create("ABCD12", profile="natal", mode="analitico")
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1000)
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1001),
                         "serial_not_supported")
        self.assertEqual(self.store.progress(job)["done"], 1)
        self.assertEqual(self.atlas.calls, 0)

    def test_orphaned_submitting_state_requires_manual_review(self):
        job = self.store.create("TEST00000001", profile="natal", mode="analitico")
        with closing(sqlite3.connect(self.path)) as con:
            with con:
                con.execute("UPDATE job_items SET state='submitting_atlas',updated_at=100 WHERE job_id=?", (job,))
        self.assertEqual(self.store.recover_uncertain(job, now=200), 0)
        self.assertEqual(self.store.recover_uncertain(job, now=300), 1)
        self.assertEqual(self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=300),
                         "idle")
        self.assertEqual(self.store.progress(job)["states"], {"review_needed": 1})
        self.assertEqual(self.atlas.calls, 0)

    def test_concurrent_retries_create_one_job(self):
        def create(_):
            return self.store.create("TEST00000001", profile="natal",
                                     mode="analitico", created_by="user-17",
                                     request_key="c" * 32)
        with ThreadPoolExecutor(max_workers=3) as pool:
            ids = list(pool.map(create, range(3)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.store.list_jobs("user-17")), 1)

    def test_legacy_job_database_is_migrated_without_losing_jobs(self):
        legacy = Path(self.tmp.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy)) as con:
            with con:
                con.execute("""CREATE TABLE jobs (id TEXT PRIMARY KEY, profile TEXT NOT NULL,
                            mode TEXT NOT NULL, created_at REAL NOT NULL,
                            created_by TEXT NOT NULL DEFAULT '')""")
                con.execute("INSERT INTO jobs VALUES ('old','natal','analitico',1,'user-19')")
        migrated = ConfrontJobStore(legacy)
        self.assertTrue(migrated.owned("old", "user-19"))
        with migrated._connect() as con:
            columns = {row["name"] for row in con.execute("PRAGMA table_info(jobs)")}
        self.assertIn("request_key", columns)

    def test_invalid_job_parameters(self):
        with self.assertRaises(ValueError):
            self.store.create("TEST00000001", profile="invalid", mode="analitico")
        with self.assertRaises(ValueError):
            self.store.progress("not-existent")

    def test_provider_failure_remains_inconclusive(self):
        job = self.store.create("TEST00000001", profile="natal", mode="analitico")
        def err(_):
            raise RuntimeError()
        self.store.step(job, imperium_query=err, atlas_client=self.atlas, now=1000)
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1001)
        self.atlas.response_ready = True
        self.store.step(job, imperium_query=self.imp, atlas_client=self.atlas, now=1005)
        result = self.store.progress(job, include_rows=True)["rows"][0]["resultado"]
        self.assertEqual(result["situacao"], "inconclusivo")


if __name__ == "__main__":
    unittest.main()
