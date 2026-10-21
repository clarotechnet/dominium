import threading
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from imperium_api import ImperiumAPI


class SerialConsultTests(unittest.TestCase):
    def test_multiple_serials_only_scan_each_stock_once_and_cache(self):
        api = object.__new__(ImperiumAPI)
        api._operation_lock = threading.RLock()
        api._serial_owner_cache = {}
        api.stock_protocol = SimpleNamespace(
            technicians_method="tech",
            technicians_query=b"TECH",
            serials_method="serial",
            serials_query=lambda stock_id: ("SER" + str(stock_id)).encode(),
            items_method="items",
            items_query=lambda stock_id: ("ITEM" + str(stock_id)).encode(),
        )
        api._client = lambda timeout: nullcontext(object())
        api._handle = lambda client, method: method
        calls = []
        def dataset(client, handle, query, description):
            calls.append(query)
            return query
        api._dataset_payload = dataset

        technician = SimpleNamespace(
            stock_id=7, technician_name="Tecnico Teste",
            to_dict=lambda: {"stock_id": 7, "technician_name": "Tecnico Teste"},
        )
        records = [
            SimpleNamespace(
                serial="ABCD1234", smart="", equipment_id=1,
                to_dict=lambda: {"serial": "ABCD1234", "equipment_id": 1},
            ),
            SimpleNamespace(
                serial="EFGH5678", smart="", equipment_id=1,
                to_dict=lambda: {"serial": "EFGH5678", "equipment_id": 1},
            ),
        ]
        item = SimpleNamespace(
            equipment_id=1, group_id=8, code="ONT-1",
            equipment="ONU GPON", group="ONT", brand_id=1,
            brand="Fabricante", unit_id=1, unit="UN", identified=True,
        )
        with (
            patch("imperium_api.parse_technicians", return_value=[technician]),
            patch("imperium_api.parse_stock_serials", return_value=records),
            patch("imperium_api.parse_stock_items", return_value=[item]),
        ):
            results = api.find_serial_owners(["ABCD1234", "EFGH5678"])
            self.assertEqual([row["serial"] for row in results],
                             ["ABCD1234", "EFGH5678"])
            self.assertTrue(all(row["found"] for row in results))
            self.assertTrue(all(row["equipment"]["name"] == "ONU GPON" for row in results))
            self.assertEqual(calls, [b"TECH", b"SER7", b"ITEM7"])
            cached = api.find_serial_owners(["ABCD1234", "EFGH5678"])
            self.assertTrue(all(row["cached"] for row in cached))
            self.assertEqual(calls, [b"TECH", b"SER7", b"ITEM7"])

    def test_invalid_bulk_is_rejected_before_any_api_call(self):
        api = object.__new__(ImperiumAPI)
        with self.assertRaisesRegex(ValueError, "Serial invalido"):
            api.find_serial_owners(["invalid serial"])


if __name__ == "__main__":
    unittest.main()
