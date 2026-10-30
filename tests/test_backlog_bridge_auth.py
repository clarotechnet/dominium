import os
import unittest
from unittest.mock import patch
from backlog_bridge_auth import _authorized_backlog_bridge

TOKEN = "A" * 52

class BacklogBackendBridgeTests(unittest.TestCase):
    def headers(self, role="controller", token=TOKEN):
        return {
            "Authorization": "Bearer " + token,
            "X-Dominium-Role": role,
            "X-Dominium-Actor": "user-7",
            "Host": "127.0.0.1:8765",
        }

    def test_missing_secret_disables_entire_bridge(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(), "GET", "/api/backlog/year/status", "127.0.0.1"))

    def test_exact_read_allowlist_and_role(self):
        with patch.dict(os.environ, {"DOMINIUM_BACKLOG_BRIDGE_TOKEN": TOKEN}, clear=False):
            self.assertTrue(_authorized_backlog_bridge(
                self.headers(), "GET", "/api/backlog/year/status", "127.0.0.1"))
            for role in ("viewer", "anonymous"):
                self.assertFalse(_authorized_backlog_bridge(
                    self.headers(role), "GET", "/api/backlog/year/status", "127.0.0.1"))
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(), "GET", "/api/backlog/year/secret", "127.0.0.1"))

    def test_post_does_not_authorize_other_mutations(self):
        with patch.dict(os.environ, {"DOMINIUM_BACKLOG_BRIDGE_TOKEN": TOKEN}, clear=False):
            self.assertTrue(_authorized_backlog_bridge(
                self.headers(), "POST", "/api/backlog/year/start", "127.0.0.1"))
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(), "POST", "/api/backlog/year/status", "127.0.0.1"))
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(), "POST", "/api/orders/123/close", "127.0.0.1"))

    def test_no_remote_bypass_even_with_correct_token(self):
        with patch.dict(os.environ, {"DOMINIUM_BACKLOG_BRIDGE_TOKEN": TOKEN}, clear=False):
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(), "GET", "/api/backlog/year/status", "10.0.0.9"))
            self.assertFalse(_authorized_backlog_bridge(
                self.headers(token="B"*52), "GET", "/api/backlog/year/status", "127.0.0.1"))
            incomplete=self.headers()
            incomplete.pop("X-Dominium-Actor")
            self.assertFalse(_authorized_backlog_bridge(
                incomplete, "GET", "/api/backlog/year/status", "127.0.0.1"))

if __name__ == "__main__":
    unittest.main()
