import json
import tempfile
import unittest
from pathlib import Path

from operational_store import OperationalStore


class OperationalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.store = OperationalStore(root / "base.sqlite3", root / "base.json")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_combines_toa_inventory_orders_and_close_attempt(self) -> None:
        payload = {
            "metadata": {"exportedAt": "2026-08-12T15:00:00-03:00"},
            "os_list": [{
                "aid": "196745827",
                "contract": "4253923",
                "os": {
                    "activity": {
                        "contract": "4253923",
                        "date": "2026-08-12",
                        "customer_name": "CLIENTE TESTE",
                        "city": "NATAL",
                        "time_slot": "08 - 12",
                        "technician_external_id": "Z131558",
                        "technician_name": "TECNICO TESTE",
                        "status": "complete",
                    },
                    "tasks": [
                        {"os_number": "2650861523", "status": "E", "close_code": "409"},
                        {"os_number": "2650861534", "status": "E", "close_code": "409"},
                    ],
                    "inventory": [
                        {"invid": "1", "kind": "equipment", "pool": "install", "serial": "C412EC7926E2"},
                        {"invid": "2", "kind": "material", "material_code": "22069613", "quantity": "2"},
                    ],
                },
            }],
        }
        self.store.ingest_toa_capture("natal", payload)
        self.store.ingest_close_attempts("natal", [{
            "request_id": "request-1",
            "contract": "4253923",
            "num_os": "2650861534",
            "close_code": "409",
            "state": "uncertain",
            "message": "Nao confirmada",
            "updated_at": "2026-08-12T15:01:00-03:00",
        }])

        record = self.store.contract("4253923", profile="natal")

        self.assertIsNotNone(record)
        self.assertEqual(record["summary"]["os_count"], 2)
        self.assertEqual(record["summary"]["installed_count"], 1)
        self.assertEqual(record["summary"]["material_count"], 1)
        self.assertEqual(record["close_attempts"][0]["state"], "uncertain")
        self.assertEqual(self.store.list_contracts(query="C412EC7926E2")["count"], 1)

        exported = json.loads(self.store.export_json().read_text(encoding="utf-8"))
        self.assertEqual(exported["contract_count"], 1)
        self.assertEqual(exported["contracts"][0]["contract"], "4253923")


    def test_order_by_id_os_returns_only_requested_imperium_row(self) -> None:
        self.store.ingest_imperium_orders("natal", [{
            "contract": "4296304",
            "num_os": "2658396041",
            "id_os": 2214730,
            "service": "ADESAO - INSTALAR PONTO VIRTUA",
            "status": "EM CAMPO",
        }])

        row = self.store.order_by_id_os("natal", 2214730)

        self.assertIsNotNone(row)
        self.assertEqual(row["contract"], "4296304")
        self.assertEqual(row["os_number"], "2658396041")
        self.assertEqual(row["source"], "imperium")
        self.assertIsNone(
            self.store.order_by_id_os("natal", 2214730, source="monitor_csv")
        )

if __name__ == "__main__":
    unittest.main()
