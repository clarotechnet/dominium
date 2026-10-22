"""Authorization, actor isolation and passive confrontation API regression tests."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "integrations" / "serial_consult"))
from confront_http import ConfrontService, parse_confront_route
from confront_job_runner import ConfrontJobStore


class FakeAtlas:
    def status(self):
        return {"ok": True, "online": True, "pendingQueries": 1}
    def valid_serial(self, value):
        return True
    def enqueue(self, serial):
        raise AssertionError("No Atlas calls should occur in these HTTP tests")


class ConfrontHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ConfrontJobStore(Path(self.temp.name) / "jobs.sqlite3")
        self.service = ConfrontService(
            store=self.store, atlas=FakeAtlas(),
            imperium=lambda _: self.fail("Imperium called without worker"),
            start_worker=False
        )

    def test_routes_only_allow_explicit_safe_paths(self):
        self.assertEqual(parse_confront_route("POST", "/api/confront/jobs"), ("create", None))
        self.assertEqual(parse_confront_route("GET", "/api/confront/jobs"), ("list", None))
        for method, path in [
            ("DELETE", "/api/confront/jobs"), ("POST", "/api/confront/status"),
            ("GET", "/api/confront/jobs?id=1"), ("GET", "/api/confront/jobs/../../env"),
            ("GET", "/api/confront/jobs/foo/export"), ("POST", "/api/orders"),
        ]:
            self.assertIsNone(parse_confront_route(method, path), (method, path))

    def test_only_own_jobs_are_readable_and_exportable(self):
        status, created, _ = self.service.handle("POST", "/api/confront/jobs", "user-1",
            {"serials": "ABCDEF123456", "profile": "natal", "mode": "analitico"})
        self.assertEqual(status, 201)
        job_id = created["job"]["job_id"]
        for path in (f"/api/confront/jobs/{job_id}", f"/api/confront/jobs/{job_id}/export"):
            response_status, _, _ = self.service.handle("GET", path, "user-2")
            self.assertEqual(response_status, 404)
        code, payload, _ = self.service.handle("GET", f"/api/confront/jobs/{job_id}", "user-1")
        self.assertEqual(code, 200)
        self.assertEqual(payload["job"]["total"], 1)

    def test_validates_actor_and_rejects_duplicate_active_jobs(self):
        code, _, _ = self.service.handle("POST", "/api/confront/jobs", "viewer",
            {"serials": "ABCDEF123456", "profile": "natal"})
        self.assertEqual(code, 400)
        first, _, _ = self.service.handle("POST", "/api/confront/jobs", "user-3",
            {"serials": "ABCDEF123456", "profile": "natal"})
        second, _, _ = self.service.handle("POST", "/api/confront/jobs", "user-3",
            {"serials": "ZZZZZZ123456", "profile": "natal"})
        self.assertEqual((first, second), (201, 409))

    def test_list_shows_only_current_actor(self):
        self.store.create("ABCDEF123456", profile="recife", mode="sintetico", created_by="user-7")
        self.store.create("ZZZZZZ123456", profile="natal", mode="analitico", created_by="user-8")
        code, payload, _ = self.service.handle("GET", "/api/confront/jobs", "user-7")
        self.assertEqual(code, 200)
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["profile"], "recife")

    def test_csv_export_only_after_completion(self):
        job_id = self.store.create("ABCDEF123456", profile="natal", mode="analitico", created_by="user-9")
        code, _, _ = self.service.handle("GET", f"/api/confront/jobs/{job_id}/export", "user-9")
        self.assertEqual(code, 409)
        with self.store._connect() as con:
            con.execute("""UPDATE job_items SET state='review_needed', error_code='manual_review',
                        updated_at=200 WHERE job_id=?""", (job_id,))
        code, data, mimetype = self.service.handle("GET", f"/api/confront/jobs/{job_id}/export", "user-9")
        self.assertEqual(code, 200)
        self.assertEqual(mimetype, "text/csv; charset=utf-8")
        self.assertIn("ABCDEF123456", data)
        self.assertIn("manual_review", data)

    def test_same_request_key_is_idempotent_even_after_completion(self):
        params = {"serials": ["TEST00000001"], "profile": "natal",
                  "mode": "sintetico", "request_key": "a" * 32}
        first, payload, _ = self.service.handle("POST", "/api/confront/jobs", "user-11", params)
        self.assertEqual(first, 201)
        job_id = payload["job"]["job_id"]
        with self.store._connect() as con:
            con.execute("UPDATE job_items SET state='complete' WHERE job_id=?", (job_id,))
        second, again, _ = self.service.handle("POST", "/api/confront/jobs", "user-11", params)
        self.assertEqual(second, 200)
        self.assertEqual(again["job"]["job_id"], job_id)
        self.assertTrue(again["reused"])
        self.assertEqual(self.store.list_jobs("user-11")[0]["id"], job_id)
        third, _, _ = self.service.handle("POST", "/api/confront/jobs", "user-12", params)
        self.assertEqual(third, 201)  # Per-user idempotency.

    def test_old_open_job_outside_recent_history_blocks_duplicate(self):
        original = self.store.create("TEST00000001", profile="recife", mode="analitico",
                                     created_by="user-13")
        for i in range(23):
            job = self.store.create(f"TEST{i:08d}", profile="natal", mode="analitico",
                                    created_by="user-13")
            with self.store._connect() as con:
                con.execute("UPDATE job_items SET state='review_needed' WHERE job_id=?", (job,))
        status, reply, _ = self.service.handle("POST", "/api/confront/jobs", "user-13",
            {"serials": "TEST99999999", "profile": "natal"})
        self.assertEqual(status, 409)
        self.assertEqual(reply["active_profile"], "recife")
        self.assertEqual(self.store.active_job("user-13")["id"], original)

    def test_status_contains_no_inventory_data(self):
        code, body, _ = self.service.handle("GET", "/api/confront/status", "user-10")
        self.assertEqual(code, 200)
        self.assertTrue(body["atlas_online"])
        self.assertNotIn("resultados", body)

    def test_atlas_offline_preserves_access_to_previous_jobs(self):
        class Offline:
            def status(self):
                raise OSError("Network unavailable")
        self.service.atlas = Offline()
        code, body, _ = self.service.handle("GET", "/api/confront/status", "user-10")
        self.assertEqual(code, 200)
        self.assertFalse(body["atlas_online"])
        listed, rows, _ = self.service.handle("GET", "/api/confront/jobs", "user-10")
        self.assertEqual(listed, 200)
        self.assertEqual(rows["jobs"], [])


if __name__ == "__main__":
    unittest.main()
