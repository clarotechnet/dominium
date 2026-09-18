import tempfile
import unittest
from pathlib import Path

from auth_store import AuthError, AuthStore


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AuthStore(Path(self.temp.name) / "auth.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_first_local_account_bootstraps_admin_and_next_is_pending(self):
        first = self.store.register(
            "dalton.control",
            "Dalton Controlador",
            "senha-1234",
            allow_bootstrap=True,
        )
        second = self.store.register(
            "outro.control",
            "Outro Controlador",
            "senha-5678",
            allow_bootstrap=True,
        )
        self.assertEqual(first["role"], "admin")
        self.assertEqual(first["status"], "active")
        self.assertEqual(second["role"], "viewer")
        self.assertEqual(second["status"], "pending")

    def test_session_stores_only_token_hash_and_validates_csrf(self):
        user = self.store.register(
            "admin.local",
            "Administrador Local",
            "senha-admin-1",
            allow_bootstrap=True,
        )
        authenticated = self.store.authenticate("ADMIN.LOCAL", "senha-admin-1")
        token, csrf, _ = self.store.create_session(authenticated["id"], "test-agent")
        session = self.store.session(token)
        self.assertIsNotNone(session)
        self.assertNotEqual(session["token_hash"], token)
        self.assertTrue(self.store.validate_csrf(session, csrf))
        self.assertFalse(self.store.validate_csrf(session, "csrf-incorreto"))
        self.store.revoke_session(token)
        self.assertIsNone(self.store.session(token))

    def test_pending_account_cannot_authenticate_until_approved(self):
        admin = self.store.register(
            "admin.local",
            "Administrador Local",
            "senha-admin-2",
            allow_bootstrap=True,
        )
        pending = self.store.register(
            "controle.dois",
            "Controle Dois",
            "senha-control-2",
            allow_bootstrap=True,
        )
        with self.assertRaises(AuthError):
            self.store.authenticate("controle.dois", "senha-control-2")
        approved = self.store.approve(
            pending["id"], role="controller", approved_by=admin["id"]
        )
        self.assertEqual(approved["status"], "active")
        self.assertEqual(
            self.store.authenticate("controle.dois", "senha-control-2")["id"],
            pending["id"],
        )

    def test_password_accepts_ten_to_128_characters(self):
        short = self.store.register(
            "admin.curto", "Administrador Curto", "1234567890", allow_bootstrap=True
        )
        self.assertEqual(
            self.store.authenticate("admin.curto", "1234567890")["id"], short["id"]
        )
        with self.assertRaisesRegex(AuthError, "entre 10 e 128"):
            self.store.register(
                "senha.pequena", "Senha Pequena", "123456789", allow_bootstrap=True
            )
        with self.assertRaisesRegex(AuthError, "entre 10 e 128"):
            self.store.register(
                "senha.grande", "Senha Grande", "x" * 129, allow_bootstrap=True
            )


if __name__ == "__main__":
    unittest.main()
