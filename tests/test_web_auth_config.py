import os
import unittest
from unittest.mock import Mock, patch

import app


class WebAuthConfigTests(unittest.TestCase):
    def state(self, *, has_users: bool, env: dict[str, str]):
        fake_store = Mock()
        fake_store.has_users.return_value = has_users
        with patch.object(app, "AUTH_STORE", fake_store), patch.dict(
            os.environ, env, clear=True
        ):
            return app._auth_public_state()

    def test_web_mode_disables_public_bootstrap_and_registration_by_default(self):
        state = self.state(has_users=False, env={"DOMINIUM_WEB_MODE": "1"})
        self.assertTrue(state["bootstrap_required"])
        self.assertFalse(state["bootstrap_allowed"])
        self.assertFalse(state["registration_enabled"])

    def test_web_registration_can_be_enabled_without_enabling_bootstrap(self):
        state = self.state(
            has_users=False,
            env={"DOMINIUM_WEB_MODE": "1", "DOMINIUM_ALLOW_REGISTRATION": "1"},
        )
        self.assertTrue(state["bootstrap_required"])
        self.assertFalse(state["bootstrap_allowed"])
        self.assertTrue(state["registration_enabled"])

    def test_local_mode_keeps_existing_first_user_bootstrap(self):
        state = self.state(has_users=False, env={"DOMINIUM_WEB_MODE": "0"})
        self.assertTrue(state["bootstrap_allowed"])
        self.assertTrue(state["registration_enabled"])

    def test_existing_users_never_report_bootstrap_required(self):
        state = self.state(
            has_users=True,
            env={"DOMINIUM_WEB_MODE": "1", "DOMINIUM_ALLOW_REGISTRATION": "1"},
        )
        self.assertFalse(state["bootstrap_required"])
        self.assertFalse(state["bootstrap_allowed"])
        self.assertTrue(state["registration_enabled"])

    def test_public_https_proxy_is_allowed_only_when_explicitly_trusted(self):
        handler = app.PanelHandler.__new__(app.PanelHandler)
        handler.headers = {
            "Host": "dominium.clarotechnet.com.br",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.25",
        }
        handler.client_address = ("172.20.0.2", 49152)
        responses = []
        handler._json = lambda status, payload: responses.append((int(status), payload))

        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PUBLIC_ORIGIN": "https://dominium.clarotechnet.com.br",
            },
        ):
            self.assertTrue(handler._security_preflight("GET", "/"))

        self.assertEqual(responses, [])

    def test_remote_peer_without_trusted_proxy_is_rejected(self):
        handler = app.PanelHandler.__new__(app.PanelHandler)
        handler.headers = {"Host": "dominium.clarotechnet.com.br"}
        handler.client_address = ("172.20.0.2", 49152)
        responses = []
        handler._json = lambda status, payload: responses.append((int(status), payload))

        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_TRUST_PROXY_HEADERS": "0",
                "DOMINIUM_PUBLIC_ORIGIN": "https://dominium.clarotechnet.com.br",
            },
        ):
            self.assertFalse(handler._security_preflight("GET", "/"))

        self.assertEqual(responses[0][0], 403)

    def test_trusted_proxy_context_uses_forwarded_client_ip(self):
        with patch.dict(
            os.environ,
            {"DOMINIUM_WEB_MODE": "1", "DOMINIUM_TRUST_PROXY_HEADERS": "1"},
        ):
            trusted, client = app._trusted_proxy_context(
                {
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "198.51.100.7, 172.20.0.2",
                },
                "172.20.0.2",
            )
        self.assertTrue(trusted)
        self.assertEqual(client, "198.51.100.7")


if __name__ == "__main__":
    unittest.main()
