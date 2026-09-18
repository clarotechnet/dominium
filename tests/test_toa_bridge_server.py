import json
import unittest
import urllib.request
import urllib.error

from toa_bridge_server import (
    ToaBridgeServer,
    _convert_equipment_item,
    _sync_payload_to_ingest,
)


class FakeDatalake:
    def __init__(self):
        self.payloads = []
        self.queue_items = []

    def ingest(self, payload):
        self.payloads.append(payload)
        return {
            "ok": True,
            "activities": len(payload.get("activities", [])),
            "orders": len(payload.get("orders", [])),
            "details": len(payload.get("details", [])),
            "changed": 1,
        }

    def detail_queue(self, limit=100):
        return {"ok": True, "items": self.queue_items[:limit]}


class ToaBridgeServerTests(unittest.TestCase):
    def test_convert_equipment_item(self):
        item = {
            "inventory_id": "12345",
            "material_code": "22069613",
            "description": "CONECTOR FIBRA",
            "serial": "sn123abc",
            "quantity": "2",
            "pool": "install",
        }
        converted = _convert_equipment_item(item)
        self.assertEqual(converted["inventory_id"], "12345")
        self.assertEqual(converted["code"], "22069613")
        self.assertEqual(converted["description"], "CONECTOR FIBRA")
        self.assertEqual(converted["serial"], "SN123ABC")
        self.assertEqual(converted["quantity"], "2")
        self.assertEqual(converted["pool"], "install")

    def test_sync_payload_to_ingest_single_activity(self):
        payload = {
            "schema_version": "dominium-toa-v1",
            "contract": "4269358",
            "activity_id": "196000001",
            "activity_type": "INSTALACAO",
            "status": "started",
            "scheduled_date": "2026-08-27",
            "service_window": "08:00 - 12:00",
            "city": "NATAL",
            "technician": {"id": "4117", "login": "Z12345", "name": "TECNICO FULANO"},
            "technician_observation": "Cliente presente",
            "tasks": [
                {"os_number": "2653166029", "service": "ADESAO STREAMING", "status": "pending", "close_code": "409"}
            ],
            "equipment": {
                "installed": [{"inventory_id": "inv1", "serial": "dec123", "material_code": "mat1"}],
                "removed": [],
                "customer": [],
            },
            "materials": [
                {"inventory_id": "inv2", "material_code": "22069613", "description": "CONECTOR", "quantity": "3"}
            ],
            "source": "toa-extension-direct",
        }
        ingest = _sync_payload_to_ingest(payload)
        self.assertEqual(ingest["source"], "toa-extension-direct")
        self.assertEqual(len(ingest["details"]), 1)
        detail = ingest["details"][0]
        self.assertEqual(detail["contract"], "4269358")
        self.assertEqual(detail["activity_id"], "196000001")
        self.assertEqual(detail["technician_name"], "TECNICO FULANO")
        self.assertEqual(len(detail["orders"]), 1)
        self.assertEqual(detail["orders"][0]["os_number"], "2653166029")
        self.assertEqual(detail["orders"][0]["close_code"], "409")
        self.assertEqual(len(detail["installed_equipment"]), 1)
        self.assertEqual(detail["installed_equipment"][0]["serial"], "DEC123")
        self.assertEqual(len(detail["materials"]), 1)
        self.assertEqual(detail["materials"][0]["code"], "22069613")

    def test_sync_payload_to_ingest_batch(self):
        payload = {
            "source": "toa-extension-batch",
            "entries": [
                {"contrato": "4269358", "aid": "196000001", "tecnico": "TECNICO A", "janela": "08:00 - 12:00", "cidade": "NATAL"},
                {"contrato": "4269359", "aid": "196000002", "tecnico": "TECNICO B", "janela": "13:00 - 18:00", "cidade": "FORTALEZA"},
            ],
        }
        ingest = _sync_payload_to_ingest(payload)
        self.assertEqual(ingest["source"], "toa-extension-batch")
        self.assertEqual(len(ingest["activities"]), 2)
        self.assertEqual(ingest["activities"][0]["contract"], "4269358")
        self.assertEqual(ingest["activities"][1]["city"], "FORTALEZA")

    def test_server_http_lifecycle_and_endpoints(self):
        datalake = FakeDatalake()
        datalake.queue_items.append({
            "contract": "4269358",
            "activity_id": "196000001",
            "scheduled_date": "2026-08-27",
        })

        # Use port 0 or higher unused test port
        server = ToaBridgeServer(datalake, port=18787, host="127.0.0.1")
        server.start()
        self.assertTrue(server.is_running)

        try:
            base_url = "http://127.0.0.1:18787"

            # 1. GET /toa/health
            req = urllib.request.Request(f"{base_url}/toa/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data.get("ok"))
                self.assertEqual(data.get("status"), "online")

            # 2. GET /toa/pending-lookup
            req = urllib.request.Request(f"{base_url}/toa/pending-lookup")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data.get("ok"))
                self.assertEqual(data.get("contrato"), "4269358")
                self.assertEqual(data.get("activity_id"), "196000001")

            # 3. POST /toa/sync (single)
            sync_payload = {
                "schema_version": "dominium-toa-v1",
                "contract": "4269358",
                "activity_id": "196000001",
                "materials": [{"material_code": "22069613", "quantity": "1"}],
            }
            body = json.dumps(sync_payload).encode()
            req = urllib.request.Request(f"{base_url}/toa/sync", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data.get("ok"))
                self.assertEqual(len(datalake.payloads), 1)

            # 4. POST /toa/ack-lookup
            ack_payload = {"contrato": "4269358", "activity_id": "196000001"}
            body = json.dumps(ack_payload).encode()
            req = urllib.request.Request(f"{base_url}/toa/ack-lookup", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertTrue(data.get("ok"))

            # 5. POST /toa/ping & /atlas/ping
            for ping_path in ["/toa/ping", "/atlas/ping"]:
                req = urllib.request.Request(f"{base_url}{ping_path}", data=b"{}", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode())
                    self.assertTrue(data.get("ok"))

        finally:
            server.stop()
            self.assertFalse(server.is_running)


if __name__ == "__main__":
    unittest.main()
