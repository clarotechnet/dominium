"""Session health must depend on a fresh queue response, not an open tab."""
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"
sys.path.insert(0, str(SOURCE))
from atlas_query_report import AtlasAuthRequired

FILE = SOURCE / "atlas_query_health.py"
health = None
if FILE.exists():
    spec = importlib.util.spec_from_file_location("atlas_query_health", FILE)
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)


class Browser:
    def close(self):
        pass


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(health, "Fresh Atlas session verification is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "query.sqlite3"
        self.output = Path(self.temp.name) / "health.json"

    def make_db(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE query_jobs(remote_queue_id TEXT, created_at REAL)")
            db.executemany("INSERT INTO query_jobs VALUES(?,?)", [
                ("276908463", 1), ("276908572", 2), ("not-an-id", 3), (None, 4)])

    def probe(self, answer):
        def read(chrome, queue_id):
            if not isinstance(chrome, Browser) or queue_id != "276908572":
                raise AssertionError("Incorrect read-only lookup")
            if isinstance(answer, Exception):
                raise answer
            return answer
        return health.inspect_session("276908572", chrome_factory=Browser, queue_reader=read)

    def test_open_tab_with_expired_service_requires_login(self):
        answer = self.probe(AtlasAuthRequired("private-login-url"))
        self.assertEqual(answer["session"], "login_required")
        self.assertIs(answer["authenticated"], False)
        self.assertNotIn("private-login-url", json.dumps(answer))

    def test_actual_queue_response_confirms_session_but_not_report(self):
        for state in ("complete", "processing", "failed"):
            answer = self.probe({"state": state, "attachment_url": "https://private/report.xls"})
            self.assertEqual(answer["session"], "authenticated")
            self.assertIs(answer["authenticated"], True)
            self.assertEqual(answer["queue_state"], state)
            self.assertEqual(answer["attachment_check"], "not_performed")
            self.assertNotIn("private", json.dumps(answer))

    def test_timeout_and_unconfirmed_response_are_not_session_success(self):
        for response in (TimeoutError("secret text"), {"state": "not_found"}, {}, None):
            answer = self.probe(response)
            self.assertEqual(answer["session"], "unknown")
            self.assertIsNone(answer["authenticated"])
            self.assertNotIn("secret text", json.dumps(answer))

    def test_browser_is_closed_even_after_authentication_failure(self):
        closed = []
        class TrackedBrowser:
            def close(self):
                closed.append(True)
        def read(chrome, queue_id):
            raise AtlasAuthRequired("expired")
        answer = health.inspect_session("276908572", chrome_factory=TrackedBrowser, queue_reader=read)
        self.assertEqual(answer["session"], "login_required")
        self.assertEqual(closed, [True])

    def test_invalid_queue_never_opens_browser(self):
        def forbidden():
            self.fail("Malformed queue must not contact Chrome")
        answer = health.inspect_session("42;anything", chrome_factory=forbidden)
        self.assertEqual(answer["session"], "unknown")

    def test_latest_valid_id_is_selected_without_database_mutation(self):
        self.make_db()
        before = self.db.read_bytes()
        self.assertEqual(health.latest_queue(self.db), "276908572")
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_database_is_not_created(self):
        answer = health.record_health(self.db, self.output)
        self.assertEqual(answer["session"], "unknown")
        self.assertEqual(answer["reason"], "no_confirmed_queue")
        self.assertFalse(self.db.exists())
        self.assertEqual(json.loads(self.output.read_text()), answer)

    def test_unreadable_database_cannot_keep_previous_success(self):
        self.db.write_text("invalid sqlite content")
        self.output.write_text('{"session":"authenticated"}')
        answer = health.record_health(self.db, self.output)
        self.assertEqual(answer["session"], "unknown")
        self.assertEqual(answer["reason"], "database_unavailable")
        self.assertEqual(json.loads(self.output.read_text()), answer)

    def test_each_run_replaces_stale_success_with_current_auth_error(self):
        self.make_db()
        before = self.db.read_bytes()
        self.output.write_text('{"session":"authenticated","checked_at":"old"}')
        with patch.object(health, "evaluate_query", side_effect=AtlasAuthRequired("private")):
            with patch.object(health, "ChromeAtlas", Browser):
                answer = health.record_health(self.db, self.output)
        self.assertEqual(answer["session"], "login_required")
        self.assertEqual(answer["remote_queue_id"], "276908572")
        self.assertNotEqual(answer["checked_at"], "old")
        self.assertEqual(json.loads(self.output.read_text()), answer)
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
