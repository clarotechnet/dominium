import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toa_secondary_session import (
    BUSY_RETRY_DELAYS,
    TOASecondaryBusyError,
    TOASecondarySession,
)


class TOASecondarySessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.session = TOASecondarySession(Path(self.temp.name))
        self.session.lookup_script.write_text("// test fixture", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _busy_result() -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["node", "lookup.mjs", "1234567"],
            1,
            stdout="",
            stderr="Error: toa_consulta_em_andamento",
        )

    @staticmethod
    def _ok_result() -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["node", "lookup.mjs", "1234567"],
            0,
            stdout=json.dumps({"ok": True, "contract": "1234567"}),
            stderr="",
        )

    def test_direct_lookup_retries_transient_busy_then_succeeds(self) -> None:
        results = [self._busy_result(), self._busy_result(), self._ok_result()]
        with patch(
            "toa_secondary_session.subprocess.run",
            side_effect=results,
        ) as run, patch("toa_secondary_session.time.sleep") as sleep:
            result = self.session._direct_lookup("1234567")

        self.assertTrue(result["ok"])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(BUSY_RETRY_DELAYS[:2]),
        )

    def test_direct_lookup_raises_specific_busy_after_retry_budget(self) -> None:
        with patch(
            "toa_secondary_session.subprocess.run",
            side_effect=[self._busy_result()] * (len(BUSY_RETRY_DELAYS) + 1),
        ) as run, patch("toa_secondary_session.time.sleep") as sleep:
            with self.assertRaisesRegex(
                TOASecondaryBusyError,
                "toa_consulta_em_andamento",
            ):
                self.session._direct_lookup("1234567")

        self.assertEqual(run.call_count, len(BUSY_RETRY_DELAYS) + 1)
        self.assertEqual(sleep.call_count, len(BUSY_RETRY_DELAYS))


if __name__ == "__main__":
    unittest.main()
