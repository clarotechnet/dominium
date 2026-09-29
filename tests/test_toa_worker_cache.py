import datetime as dt
import unittest
from unittest.mock import Mock, patch

import app


class TOAWorkerCacheTests(unittest.TestCase):
    def test_due_minute_respects_current_window(self):
        now = dt.datetime(2026, 9, 29, 9, 20).astimezone()

        self.assertEqual(
            app._toa_record_due_minute({"windows": ["08:00 - 11:00"]}, now),
            8 * 60,
        )
        self.assertIsNone(
            app._toa_record_due_minute({"windows": ["11:00 - 14:00"]}, now)
        )

    def test_worker_reuses_fresh_cache_without_live_lookup(self):
        cached = {
            "freshness": {"observed_at": dt.datetime.now().astimezone().isoformat()},
            "activities": [{"scheduled_date": "2026-09-29", "status": "complete"}],
        }
        connector = Mock()
        connector.lookup.return_value = cached

        with patch.object(app, "TOA_CONNECTOR", connector), patch.object(
            app, "_toa_connector_cache_is_fresh", return_value=True
        ):
            document, refreshed = app._toa_worker_document(
                "1000001",
                expected_date="2026-09-29",
            )

        self.assertIs(document, cached)
        self.assertFalse(refreshed)
        connector.lookup.assert_called_once_with(
            "1000001", refresh=False, allow_stale=True
        )


if __name__ == "__main__":
    unittest.main()
