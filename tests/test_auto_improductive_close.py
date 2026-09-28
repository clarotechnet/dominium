import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from auto_improductive_close import (
    AutoImproductiveCloser,
    review_record_is_due,
    toa_activity_is_complete,
)


class AutoImproductiveCloserTests(unittest.TestCase):
    def test_due_uses_review_slot_and_ignores_sem_janela(self):
        now = dt.datetime(2026, 9, 28, 14, 5)
        self.assertTrue(review_record_is_due({"review_slots": ["14:00"]}, now))
        self.assertFalse(review_record_is_due({"review_slots": ["17:20"]}, now))
        self.assertFalse(review_record_is_due({"review_slots": ["sem_janela"]}, now))

    def test_complete_statuses(self):
        for value in ("complete", "completed", "CONCLUIDA", "executado"):
            self.assertTrue(toa_activity_is_complete(value))
        self.assertFalse(toa_activity_is_complete("pending"))

    def test_enabled_and_blocked_state_survive_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            history = root / "history.jsonl"
            closer = AutoImproductiveCloser(
                state,
                history,
                lambda _controller: {"ok": True},
            )
            closer.set_enabled(True)
            closer.block("natal:123", "incerto", metadata={"os": "123"})

            reloaded = AutoImproductiveCloser(
                state,
                history,
                lambda _controller: {"ok": True},
            )
            public = reloaded.public_state()
            self.assertTrue(public["enabled"])
            self.assertEqual(public["blocked_count"], 1)
            self.assertTrue(reloaded.is_blocked("natal:123"))

    def test_run_once_persists_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closer = AutoImproductiveCloser(
                root / "state.json",
                root / "history.jsonl",
                lambda _controller: {"ok": True, "closed": 2},
            )
            closer._run_once()
            lines = (root / "history.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["closed"], 2)


if __name__ == "__main__":
    unittest.main()
