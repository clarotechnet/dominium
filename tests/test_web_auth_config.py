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


if __name__ == "__main__":
    unittest.main()
