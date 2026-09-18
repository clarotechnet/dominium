import tempfile
import unittest
from pathlib import Path

from toa_datalake_store import TOADatalakeStore


class TOADatalakeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TOADatalakeStore(Path(self.temp.name) / "toa.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_incremental_detail_and_inventory(self):
        result = self.store.ingest({
            "profile": "natal",
            "activities": [{
                "id": "12345678", "contrato": "4253923", "bucket": "NTL-DMV",
                "tecnico_nome": "TECNICO TESTE", "atividade_data": "2026-08-12",
                "janela": "08:00 - 11:00", "orders": [{"id": "2650000001"}],
            }],
        })
        self.assertEqual(result["activities"], 1)
        self.assertEqual(self.store.detail_queue()["count"], 1)

        self.store.ingest({"details": [{
            "activity_id": "12345678", "contract": "4253923",
            "observation": "Sinal normalizado",
            "orders": [{"id": "2650000001", "codigo_baixa_id": "409"}],
            "installed_equipment": [{"serial": "ABC123", "description": "EMTA"}],
            "removed_equipment": [{"serial": "OLD123", "description": "DECODER"}],
            "materials": [{"code": "22056332", "description": "FITA ISOLANTE", "quantity": 1}],
        }]})
        record = self.store.record("4253923")
        self.assertTrue(record["summary"]["detail_complete"])
        self.assertEqual(record["orders"][0]["close_code"], "409")
        self.assertEqual(record["activities"][0]["observation"], "Sinal normalizado")
        self.assertEqual(record["inventory"]["installed"][0]["serial"], "ABC123")
        self.assertEqual(record["inventory"]["removed"][0]["serial"], "OLD123")
        self.assertEqual(record["inventory"]["material"][0]["code"], "22056332")

    def test_feed_preserves_profile_and_os(self):
        self.store.ingest({"activities": [{
            "id": "87654321", "contrato": "4253672", "bucket": "FTZ-DMV_01",
            "atividade_data": "2026-08-12", "orders": [{"id": "2650833229"}],
        }]})
        feed = self.store.feed(profile="fortaleza")
        self.assertEqual(feed["order_count"], 1)
        self.assertEqual(feed["orders"][0]["profile"], "fortaleza")
        self.assertEqual(feed["orders"][0]["os_number"], "2650833229")


if __name__ == "__main__":
    unittest.main()
