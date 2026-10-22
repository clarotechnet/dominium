"""Tests for the real BotDMV Atlas HTTP queue contract (synthetic only)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from atlas_bridge_client import AtlasBridgeClient, AtlasBridgeError


SERIAL = "TEST00000001"
REQUEST = "abcdef-1234"


class FakeBridge:
    def __init__(self, *, mode="ok"):
        self.mode = mode
        self.calls = []
        self.polls = 0

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/atlas/extension-status":
            return {"ok": True, "online": self.mode != "offline", "pendingQueries": 0}
        if path == "/atlas/queue-query":
            return {"ok": True, "queued": True, "requestId": REQUEST,
                    "serials": body["serials"]}
        if path == "/atlas/query-result/" + REQUEST:
            self.polls += 1
            if self.mode == "timeout" or self.polls == 1:
                return {"ok": True, "ready": False, "result": None}
            if self.mode == "wrong_request":
                return {"ok": True, "ready": True,
                        "result": {"ok": True, "requestId": "other-request",
                                   "serial": SERIAL}}
            if self.mode == "wrong_serial":
                return {"ok": True, "ready": True,
                        "result": {"ok": True, "requestId": REQUEST,
                                   "serial": "OTHER0000001"}}
            if self.mode == "failed":
                return {"ok": True, "ready": True,
                        "result": {"ok": False, "requestId": REQUEST,
                                   "serial": SERIAL, "error": "empty"}}
            data = {
                "ok": True, "serial_consultado": SERIAL,
                "serial_encontrado": True, "estado": "INICIALIZADO",
                "numero_contrato": "1234567", "historico": []
            }
            if self.mode == "wrong_payload":
                data["serial_consultado"] = "OTHER0000001"
            return {"ok": True, "ready": True,
                    "result": {"requestId": REQUEST, "serial": SERIAL,
                               "ok": True, "resultado": data}}
        raise AssertionError((method,path,body))


class AtlasBridgeClientTests(unittest.TestCase):
    def client(self, mode="ok", *, timeout_clock=False):
        fake = FakeBridge(mode=mode)
        ticking = [0.0]
        def clock():
            return ticking[0]
        def sleep(seconds):
            ticking[0] += seconds
        return AtlasBridgeClient(http=fake, clock=clock, sleep=sleep), fake

    def test_uses_existing_queue_once_and_checks_request_id(self):
        client, fake = self.client()
        response = client.query(SERIAL)
        self.assertTrue(response["ok"])
        self.assertEqual(response["resultado"]["estado"], "INICIALIZADO")
        self.assertEqual([x[1] for x in fake.calls],
                         ["/atlas/extension-status", "/atlas/queue-query",
                          "/atlas/query-result/" + REQUEST, "/atlas/query-result/" + REQUEST])
        self.assertEqual(fake.calls[1][2]["serials"], [SERIAL])

    def test_offline_does_not_enqueue(self):
        client, fake = self.client("offline")
        with self.assertRaises(AtlasBridgeError):
            client.query(SERIAL)
        self.assertEqual(len(fake.calls), 1)

    def test_invalid_serial_does_not_access_bridge(self):
        client, fake = self.client()
        result = client.query("abc")
        self.assertFalse(result["ok"])
        self.assertEqual(fake.calls, [])

    def test_wrong_request_rejected(self):
        client, _ = self.client("wrong_request")
        with self.assertRaisesRegex(AtlasBridgeError, "outra requisicao"):
            client.query(SERIAL)

    def test_wrong_serial_rejected(self):
        client, _ = self.client("wrong_serial")
        with self.assertRaisesRegex(AtlasBridgeError, "outro serial"):
            client.query(SERIAL)

    def test_wrong_payload_rejected(self):
        client, _ = self.client("wrong_payload")
        with self.assertRaisesRegex(AtlasBridgeError, "Correlacao"):
            client.query(SERIAL)

    def test_queued_failure_is_not_reported_as_absence(self):
        client, _ = self.client("failed")
        response = client.query(SERIAL)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "atlas_consulta_nao_confirmada")

    def test_no_automatic_retry_when_queue_result_times_out(self):
        client, fake = self.client("timeout")
        with self.assertRaisesRegex(AtlasBridgeError, "pendente"):
            client.query(SERIAL, timeout=5, poll_interval=2)
        self.assertEqual(len([x for x in fake.calls if x[1] == "/atlas/queue-query"]), 1)

    def test_reject_non_loopback_host(self):
        with self.assertRaises(ValueError):
            AtlasBridgeClient(base_url="http://0.0.0.0:8787")


if __name__ == "__main__":
    unittest.main()
