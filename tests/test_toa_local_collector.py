import unittest

from toa_local_collector import TOALocalCollector, _clean_description, _clock, _service_window


class FakeLive:
    def public_state(self):
        return {"authenticated": True}

    def execute_readonly_script(self, _script):
        return {
            "bucket": "NTL-DMV",
            "activities": [{
                "activity_id": "a_196000001",
                "technician_id": "4117",
                "technician_name": "TECNICO TESTE",
                "status": "started",
                "scheduled_date": "2026-08-12",
                "start_min": "480",
                "duration_min": "60",
                "eta_min": "495",
                "activity_type": "regular",
                "work_type_id": "9",
                "description": "Visita Tecnica activity",
            }],
        }


class FakeDatalake:
    SCHEMA = "dominium.toa.datalake.v1"

    def __init__(self):
        self.payload = None

    def ingest(self, payload):
        self.payload = payload
        return {"ok": True}


class TOALocalCollectorTests(unittest.TestCase):
    def test_clock_and_window(self):
        self.assertEqual(_clock(495), "08:15")
        self.assertEqual(_service_window(480, 60), "08:00 - 09:00")

    def test_description_discards_customer_and_address(self):
        self.assertEqual(
            _clean_description("Visita Tecnica, CLIENTE EXEMPLO, RUA EXEMPLO 123 activity"),
            "Visita Tecnica",
        )

    def test_collects_sanitized_operational_snapshot(self):
        store = FakeDatalake()
        collector = TOALocalCollector(FakeLive(), store)
        result = collector.collect_now()
        self.assertEqual(result["activity_count"], 1)
        row = store.payload["activities"][0]
        self.assertEqual(row["activity_id"], "196000001")
        self.assertEqual(row["technician_name"], "TECNICO TESTE")
        self.assertEqual(row["service_window"], "08:00 - 09:00")
        self.assertEqual(row["start_time"], "08:15")
        self.assertEqual(row["description"], "Visita Tecnica")


if __name__ == "__main__":
    unittest.main()
