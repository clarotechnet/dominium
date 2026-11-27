import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from toa_secondary_session import (
    BUSY_RETRY_DELAYS,
    TOASecondaryBusyError,
    TOASecondarySession,
    _confirmed_adhesion_provider,
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

    def test_adhesion_scope_is_passed_only_for_explicit_lookups(self) -> None:
        with patch("toa_secondary_session.subprocess.run", return_value=self._ok_result()) as run:
            self.session._direct_lookup("1234567")
            self.session._direct_lookup("1234567", adhesion_date="2026-11-25")

        normal, adhesion = [call.args[0] for call in run.call_args_list]
        self.assertEqual(normal, ["node", str(self.session.lookup_script), "1234567"])
        self.assertEqual(adhesion, [*normal, "2026-11-25"])

    def test_adhesion_recovers_confirmed_executor_from_current_provider(self) -> None:
        day = "2026-11-26"
        provider = {"id": "75", "name": "TECNICO ATUAL", "external_id": "Z456"}
        responsibility = {
            "assigned_technician": {**provider, "id": "29", "name": "TECNICO ANTERIOR"},
            "route_provider": provider,
            "inventory_providers": [provider],
            "form_submitters": [{"provider_id": "75", "user_name": provider["name"]}],
        }
        raw = {
            "ok": True, "contrato": "1234567", "aid": 123, "pid": 75,
            "status": "complete", "date": day, "tecnico": provider["name"], "externalId": "Z456",
            "searchRow": {"pid": 75, "external_id": "Z456", "date": day, "route_name": "NTL-DMV"},
            "normalizedCapture": {"responsibility": responsibility},
        }
        with (patch("toa_secondary_session._toa_page", return_value={"url": "fixture"}),
              patch.object(self.session, "_direct_lookup", return_value=raw)):
            capture = self.session.lookup_contract("1234567", adhesion_date=day)["results"][0]
        self.assertEqual(capture["assigned_technician"], provider)
        self.assertEqual(capture["route_provider"], provider)
        current = deepcopy(raw)
        current["normalizedCapture"]["responsibility"]["assigned_technician"] = provider
        with (patch("toa_secondary_session._toa_page", return_value={"url": "fixture"}),
              patch.object(self.session, "_direct_lookup", return_value=current)):
            capture = self.session.lookup_contract("1234567", adhesion_date=day)["results"][0]
        self.assertEqual(capture["assigned_technician"], provider)
        self.assertEqual(capture["route_provider"], provider)
        self.assertIsNone(_confirmed_adhesion_provider(raw, capture, ""))
        self.assertIsNone(_confirmed_adhesion_provider(raw, capture, "2026-11-25"))
        self.assertIsNone(_confirmed_adhesion_provider(raw, {**capture, "route_name": "NTL-DMV-ADM"}, day))
        for field in ("route_provider", "inventory_providers", "form_submitters"):
            changed = deepcopy(raw)
            changed["normalizedCapture"]["responsibility"].pop(field)
            self.assertIsNone(_confirmed_adhesion_provider(changed, capture, day))
        changed = deepcopy(raw)
        changed["normalizedCapture"]["responsibility"]["form_submitters"][0]["provider_id"] = "29"
        self.assertIsNone(_confirmed_adhesion_provider(changed, capture, day))

        sparse = deepcopy(raw)
        sparse_responsibility = sparse["normalizedCapture"]["responsibility"]
        sparse_responsibility["route_provider"] = {"id": "75", "external_id": "", "name": ""}
        sparse_responsibility["inventory_providers"] = [{"id": "75", "external_id": "", "name": ""}]
        self.assertEqual(_confirmed_adhesion_provider(sparse, capture, day), provider)
        for field, expected_key, conflicting_value in (
            ("route_provider", "name", "OUTRO TECNICO"),
            ("route_provider", "external_id", "Z123"),
            ("inventory_providers", "id", "29"),
            ("inventory_providers", "external_id", "Z123"),
            ("form_submitters", "user_name", ""),
        ):
            with self.subTest(field=field, key=expected_key):
                changed = deepcopy(sparse)
                entry = changed["normalizedCapture"]["responsibility"][field]
                (entry[0] if isinstance(entry, list) else entry)[expected_key] = conflicting_value
                self.assertIsNone(_confirmed_adhesion_provider(changed, capture, day))

        without_movements = deepcopy(raw)
        normalized = without_movements["normalizedCapture"]
        normalized.update(tasks=[{"os_number": "1234", "status": "N", "close_code": "301"}],
                          installed_equipment=[], removed_equipment=[], materials=[])
        normalized["responsibility"]["inventory_providers"] = []
        self.assertEqual(_confirmed_adhesion_provider(without_movements, capture, day), provider)
        for invalid in ({"tasks": [*normalized["tasks"], {"status": "E", "close_code": "409"}]},
                        {"tasks": [{"status": "N"}]}, {"materials": [{"material_code": "22025072"}]},
                        {"removed_equipment": [{"serial": "123"}]}, {"materials": None}):
            with self.subTest(invalid=invalid):
                changed = {**without_movements, "normalizedCapture": {**normalized, **invalid}}
                self.assertIsNone(_confirmed_adhesion_provider(changed, capture, day))


if __name__ == "__main__":
    unittest.main()
