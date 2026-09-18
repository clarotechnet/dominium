import unittest

from toa_cloud_client import TOACloudBridgeError, TOACloudClient


class FakeCloudClient(TOACloudClient):
    def __init__(self, responses):
        super().__init__(
            "https://dominium.example.workers.dev",
            "x" * 40,
            lookup_timeout=5,
            poll_interval=0.25,
        )
        self.responses = list(responses)
        self.requests = []

    def _request(self, method, path, body=None):
        self.requests.append((method, path, body))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TOACloudClientTests(unittest.TestCase):
    def test_lookup_creates_job_and_returns_sanitized_snapshot(self):
        snapshot = {
            "contract": "4252617",
            "equipment": {"installed": [{"serial": "ABC"}]},
            "materials": [{"material_code": "22056332"}],
        }
        client = FakeCloudClient([
            {"ok": True, "job": {"id": "job-1", "status": "queued"}},
            {"ok": True, "job": {"id": "job-1", "status": "completed", "result": snapshot}},
        ])

        result = client.lookup_contract("CLIENTE - 4252617")

        self.assertEqual(result, snapshot)
        self.assertEqual(client.requests[0][0:2], ("POST", "/v1/lookups"))
        self.assertEqual(client.requests[1][0:2], ("GET", "/v1/lookups/job-1"))
        self.assertNotIn("token", str(client.public_state()).lower())

    def test_failed_job_is_reported_without_exposing_token(self):
        client = FakeCloudClient([
            {"ok": True, "job": {"id": "job-2", "status": "queued"}},
            {"ok": True, "job": {"id": "job-2", "status": "failed", "error_code": "toa_sem_sessao"}},
        ])

        with self.assertRaisesRegex(TOACloudBridgeError, "toa_sem_sessao"):
            client.lookup_contract("4252617")
        self.assertNotIn("x" * 40, client.last_error)

    def test_create_timeout_reuses_the_same_idempotency_key(self):
        snapshot = {"contract": "4252617"}
        client = FakeCloudClient([
            TOACloudBridgeError("Ponte TOA indisponivel: timed out"),
            {"ok": True, "job": {"id": "job-recovered", "status": "queued"}},
            {"ok": True, "job": {
                "id": "job-recovered", "status": "completed", "result": snapshot,
            }},
        ])

        self.assertEqual(client.lookup_contract("4252617"), snapshot)
        first = client.requests[0][2]
        second = client.requests[1][2]
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
