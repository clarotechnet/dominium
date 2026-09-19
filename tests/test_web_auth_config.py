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
            "X-Dominium-Proxy-Token": "proxy-test-secret",
        }
        handler.client_address = ("172.20.0.2", 49152)
        responses = []
        handler._json = lambda status, payload: responses.append((int(status), payload))

        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "proxy-test-secret",
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
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "proxy-test-secret",
            },
        ):
            trusted, client = app._trusted_proxy_context(
                {
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "198.51.100.7, 172.20.0.2",
                    "X-Dominium-Proxy-Token": "proxy-test-secret",
                },
                "172.20.0.2",
            )
        self.assertTrue(trusted)
        self.assertEqual(client, "198.51.100.7")

    def test_remote_toa_origin_rejects_non_http_schemes(self):
        for value in (
            "file:///C:/Windows/win.ini",
            "ftp://192.168.0.6:8787",
            "http://user:pass@192.168.0.6:8787",
            "http://192.168.0.6:8787/path",
        ):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                app._validated_remote_toa_automation_base(value)

        self.assertEqual(
            app._validated_remote_toa_automation_base("http://192.168.0.6:8787/"),
            "http://192.168.0.6:8787",
        )

    def test_forged_proxy_headers_without_shared_secret_are_rejected(self):
        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "real-proxy-secret",
            },
        ):
            trusted, client = app._trusted_proxy_context(
                {
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "198.51.100.9",
                    "X-Dominium-Proxy-Token": "forged",
                },
                "192.0.2.10",
            )
        self.assertFalse(trusted)
        self.assertEqual(client, "192.0.2.10")

    def test_web_security_config_requires_strong_proxy_token(self):
        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_HTTPS": "1",
                "DOMINIUM_PUBLIC_ORIGIN": "https://dominium.clarotechnet.com.br",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "short",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(SystemExit, "pelo menos 32 caracteres"):
                app._validate_web_security_config("0.0.0.0")

    def test_web_security_config_rejects_placeholder_proxy_token(self):
        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_HTTPS": "1",
                "DOMINIUM_PUBLIC_ORIGIN": "https://dominium.clarotechnet.com.br",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "COLOQUE_UM_TOKEN_ALEATORIO_FORTE_AQUI",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(SystemExit, "segredo aleatorio forte"):
                app._validate_web_security_config("0.0.0.0")

    def test_web_security_config_accepts_hardened_proxy(self):
        with patch.dict(
            os.environ,
            {
                "DOMINIUM_WEB_MODE": "1",
                "DOMINIUM_HTTPS": "1",
                "DOMINIUM_PUBLIC_ORIGIN": "https://dominium.clarotechnet.com.br",
                "DOMINIUM_TRUST_PROXY_HEADERS": "1",
                "DOMINIUM_PROXY_TOKEN": "aB3!proxy-9Zx7_Lm2#Qw8$Rt5%Yu1&Kp4*Vc6",
            },
            clear=True,
        ):
            app._validate_web_security_config("0.0.0.0")

    def test_viewer_cannot_read_internal_diagnostics(self):
        handler = app.PanelHandler.__new__(app.PanelHandler)
        handler.headers = {"Host": "127.0.0.1:8765"}
        handler.client_address = ("127.0.0.1", 49152)
        handler._auth_session = lambda: {
            "user": {"id": 7, "username": "viewer", "role": "viewer"}
        }
        responses = []
        handler._json = lambda status, payload: responses.append((int(status), payload))

        self.assertFalse(handler._security_preflight("GET", "/api/logs"))
        self.assertEqual(responses[0][0], 403)

    def test_controller_can_read_internal_diagnostics(self):
        handler = app.PanelHandler.__new__(app.PanelHandler)
        handler.headers = {"Host": "127.0.0.1:8765"}
        handler.client_address = ("127.0.0.1", 49152)
        handler._auth_session = lambda: {
            "user": {"id": 8, "username": "controller", "role": "controller"}
        }
        responses = []
        handler._json = lambda status, payload: responses.append((int(status), payload))

        self.assertTrue(handler._security_preflight("GET", "/api/logs"))
        self.assertEqual(responses, [])


if __name__ == "__main__":
    unittest.main()
