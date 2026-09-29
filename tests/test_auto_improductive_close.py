import datetime as dt
import json
import tempfile
import unittest
from unittest.mock import patch
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

    def test_state_persistence_retries_transient_windows_permission_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            history = root / "history.jsonl"
            closer = AutoImproductiveCloser(
                state,
                history,
                lambda _controller: {"ok": True},
            )
            original_replace = Path.replace
            attempts = {"count": 0}

            def flaky_replace(path, target):
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise PermissionError(5, "Acesso negado")
                return original_replace(path, target)

            with patch.object(Path, "replace", new=flaky_replace), patch(
                "auto_improductive_close.time.sleep"
            ):
                closer.set_enabled(True)

            self.assertEqual(attempts["count"], 3)
            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertTrue(payload["enabled"])

    def test_state_persistence_falls_back_to_direct_write_when_replace_stays_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            history = root / "history.jsonl"
            closer = AutoImproductiveCloser(
                state,
                history,
                lambda _controller: {"ok": True},
            )

            with patch.object(
                Path,
                "replace",
                side_effect=PermissionError(5, "Acesso negado"),
            ), patch("auto_improductive_close.time.sleep"):
                closer.set_enabled(True)

            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertTrue(payload["enabled"])
            self.assertFalse(any(root.glob("state.json.*.tmp")))

    def test_public_state_exposes_live_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closer = AutoImproductiveCloser(
                root / "state.json",
                root / "history.jsonl",
                lambda _controller: {"ok": True},
            )
            closer.current_run = {
                "started_at": "2026-09-29T10:30:00-03:00",
                "running": True,
            }
            closer.publish_progress(
                {
                    "closed_new": 2,
                    "already_closed": 1,
                    "productive_cached": 4,
                    "details": [
                        {
                            "kind": "closed",
                            "contract": "1234567",
                            "already_closed": False,
                        }
                    ],
                },
                force=True,
            )

            public = closer.public_state()

            self.assertEqual(public["current_run"]["closed_new"], 2)
            self.assertEqual(public["current_run"]["already_closed"], 1)
            self.assertEqual(
                public["current_run"]["details"][0]["contract"],
                "1234567",
            )

    def test_history_totals_separate_new_and_already_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / "history.jsonl"
            rows = [
                {
                    "closed": 2,
                    "details": [
                        {"kind": "closed", "already_closed": False},
                        {"kind": "closed", "already_closed": True},
                    ],
                },
                {
                    "closed": 1,
                    "details": [
                        {"kind": "closed", "already_closed": False},
                    ],
                },
            ]
            history.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            closer = AutoImproductiveCloser(
                root / "state.json",
                history,
                lambda _controller: {"ok": True},
            )

            totals = closer.public_state()["totals"]

            self.assertEqual(totals["closed"], 3)
            self.assertEqual(totals["closed_new"], 2)
            self.assertEqual(totals["already_closed"], 1)

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
