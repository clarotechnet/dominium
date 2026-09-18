import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from toa_connector import TOAConnector


def _live_result(contract: str = "4252617") -> dict:
    return {
        "ok": True,
        "session": {"last_lookup_at": "2026-08-12T09:30:00-03:00"},
        "results": [{
            "found": True,
            "aid": "196603398",
            "contract": contract,
            "appointment_number": "01695|739920099",
            "scheduled_date": "2026-08-12",
            "service_window": "12 - 15",
            "start_time": "2026-08-12 13:50:00",
            "end_time": "2026-08-12 15:30:00",
            "city": "NATAL",
            "work_type": "Instalação",
            "activity_status": "complete",
            "technician_observation": "Instalação realizada com sucesso.",
            "assigned_technician": {
                "id": "31146",
                "external_id": "Z581722",
                "name": "ROBERTO TESTE",
                "email": "nao-pode-vazar@example.com",
            },
            "tasks": [
                {"index": "1", "os_number": "2650569922", "status": "E", "close_code": "409"},
                {"index": "2", "os_number": "2650569933", "status": "E", "close_code": "409"},
            ],
            "installed_equipment": [{
                "invid": "1", "kind": "equipment", "pool": "install",
                "type": "3 - EMTA", "serial": "C412EC773DBC", "quantity": "1",
            }],
            "removed_equipment": [],
            "customer_equipment": [],
            "materials": [{
                "invid": "2", "kind": "material", "pool": "install",
                "material_code": "22056332", "type": "FITA AUTO-FUSAO", "quantity": "1",
            }],
            "operational_classification": "produtiva",
            "decision": "candidate_after_validation",
            "validation_errors": [],
            "validation_warnings": [],
            "decision_reasons": [],
            "customer_name": "NAO PODE VAZAR",
            "address": "NAO PODE VAZAR",
        }],
    }


class TOAConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.live = MagicMock()
        self.live.public_state.return_value = {
            "connected": True,
            "authenticated": True,
            "busy": False,
        }
        self.connector = TOAConnector(self.root, self.live)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_live_lookup_is_sanitized_and_cached(self) -> None:
        self.live.lookup_contract.return_value = _live_result()

        result = self.connector.lookup("4252617")

        self.assertEqual(result["source"], "toa_live")
        self.assertEqual(result["summary"]["os_count"], 2)
        self.assertEqual(result["activities"][0]["service_window"], "12 - 15")
        self.assertEqual(result["activities"][0]["technician"]["login"], "Z581722")
        self.assertEqual(result["activities"][0]["materials"][0]["material_code"], "22056332")
        serialized = json.dumps(result)
        self.assertNotIn("NAO PODE VAZAR", serialized)
        self.assertNotIn("nao-pode-vazar@example.com", serialized)
        self.assertTrue((self.connector.cache_root / "4252617.json").is_file())

    def test_live_failure_falls_back_to_sanitized_cache(self) -> None:
        self.live.lookup_contract.return_value = _live_result()
        self.connector.lookup("4252617")
        self.live.lookup_contract.side_effect = RuntimeError("Login TOA necessario")

        result = self.connector.lookup("4252617", refresh=True, allow_stale=True)

        self.assertEqual(result["source"], "toa_cache")
        self.assertTrue(result["freshness"]["stale"])
        self.assertIn("Login TOA necessario", result["freshness"]["warning"])

    def test_stale_can_be_refused(self) -> None:
        self.live.lookup_contract.side_effect = RuntimeError("Login TOA necessario")

        with self.assertRaisesRegex(RuntimeError, "Login TOA necessario"):
            self.connector.lookup("4252617", allow_stale=False)

    def test_rejects_invalid_contract_before_live_access(self) -> None:
        with self.assertRaisesRegex(ValueError, "5 a 18"):
            self.connector.lookup("abc")
        self.live.lookup_contract.assert_not_called()

    def test_cloud_bridge_is_preferred_and_preserves_inventory(self) -> None:
        cloud = MagicMock()
        cloud.configured = True
        cloud.public_state.return_value = {
            "configured": True,
            "base_url": "https://bridge.example.test",
            "last_error": "",
            "last_success_at": "",
        }
        cloud.lookup_contract.return_value = {
            "contract": "4252617",
            "activity_id": "196603398",
            "activity_type": "Instalacao",
            "status": "complete",
            "scheduled_date": "2026-08-20",
            "service_window": "12 - 15",
            "technician": {
                "id": "31146", "login": "Z581722", "name": "ROBERTO TESTE"
            },
            "technician_observation": "Instalacao realizada.",
            "tasks": [
                {"index": "1", "os_number": "2650569922", "status": "E", "close_code": "409"}
            ],
            "equipment": {
                "installed": [{"serial": "C412EC773DBC", "description": "EMTA"}],
                "removed": [],
                "customer": [],
            },
            "materials": [
                {"material_code": "22056332", "description": "FITA AUTO-FUSAO", "quantity": "1"}
            ],
            "validation": {"errors": [], "warnings": [], "reasons": []},
            "captured_at": "2026-08-20T10:00:00-03:00",
            "customer_name": "NAO PODE VAZAR",
        }
        connector = TOAConnector(self.root, self.live, cloud)

        result = connector.lookup("4252617")

        self.assertEqual(result["source"], "toa_cloud")
        self.assertEqual(result["activities"][0]["equipment"]["installed"][0]["serial"], "C412EC773DBC")
        self.assertEqual(result["activities"][0]["materials"][0]["material_code"], "22056332")
        self.assertNotIn("NAO PODE VAZAR", json.dumps(result))
        self.live.lookup_contract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
