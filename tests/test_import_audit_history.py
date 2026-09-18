import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import app


class ImportAuditHistoryTests(unittest.TestCase):
    def test_reads_newest_entries_and_skips_malformed_lines(self):
        day = dt.date(2026, 9, 11)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "importacoes-20260911.jsonl"
            rows = [
                {"at": "2026-09-11T09:00:00", "count": 2, "imported": 2},
                {"at": "2026-09-11T10:00:00", "count": 3, "imported": 3},
                {"at": "2026-09-11T11:00:00", "count": 4, "imported": 4},
            ]
            path.write_text(
                "\n".join([json.dumps(rows[0]), "{broken", json.dumps(rows[1]), json.dumps(rows[2])]) + "\n",
                encoding="utf-8",
            )
            profile = SimpleNamespace(key="natal", label="NATAL", log_root=root)
            payload = app._read_import_audit_history(profile, audit_date=day, limit=2)
            self.assertEqual(payload["count"], 2)
            self.assertEqual(payload["items"][0]["at"], "2026-09-11T11:00:00")
            self.assertEqual(payload["items"][1]["at"], "2026-09-11T10:00:00")
            self.assertEqual(payload["malformed"], 0)

    def test_missing_file_returns_empty_payload(self):
        day = dt.date(2026, 9, 10)
        with tempfile.TemporaryDirectory() as tmp:
            profile = SimpleNamespace(
                key="natal",
                label="NATAL",
                log_root=Path(tmp),
            )
            payload = app._read_import_audit_history(
                profile,
                audit_date=day,
                limit=80,
            )
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["date"], "2026-09-10")
            self.assertEqual(payload["count"], 0)
            self.assertEqual(payload["items"], [])


if __name__ == "__main__":
    unittest.main()
