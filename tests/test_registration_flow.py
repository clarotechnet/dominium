"""
test_registration_flow.py
=========================
24+ cenários cobrindo o fluxo completo de cadastro/aprovação/rejeição no DOMINIUM.

Usa o backend SQLite (AuthStore) para isolamento — sem dependência de Supabase.
Execute com:
    .\\venv\\Scripts\\python.exe -m unittest test_registration_flow -v
"""
import atexit
import os
import re
import tempfile
import unittest
from auth_store import AuthStore, AuthError


_TEMP_DBS: list[str] = []


def _cleanup_temp_dbs() -> None:
    for path in _TEMP_DBS:
        try:
            os.remove(path)
        except OSError:
            pass


atexit.register(_cleanup_temp_dbs)


def _make_store() -> AuthStore:
    """Cria um AuthStore SQLite isolado em arquivo temporario."""
    fd, path = tempfile.mkstemp(prefix="dominium-auth-test-", suffix=".db")
    os.close(fd)
    _TEMP_DBS.append(path)
    return AuthStore(path)


def _bootstrap_admin(store: AuthStore) -> dict:
    """Cria o primeiro admin (bootstrap) e retorna o usuário."""
    return store.register(
        "admin",
        "Admin Dominium",
        "adminpassword01",
        allow_bootstrap=True,
    )


class TestRegisterBasic(unittest.TestCase):
    """Registro básico de novos usuários."""

    def setUp(self):
        self.store = _make_store()
        self.admin = _bootstrap_admin(self.store)

    # 1. Bootstrap admin cria conta active
    def test_bootstrap_creates_active_admin(self):
        self.assertEqual(self.admin["status"], "active")
        self.assertEqual(self.admin["role"], "admin")

    # 2. Registro regular cria conta pending
    def test_regular_register_pending(self):
        user = self.store.register(
            "joao", "Joao Silva", "senha12345678", allow_bootstrap=False
        )
        self.assertEqual(user["status"], "pending")
        self.assertEqual(user["role"], "viewer")

    # 3. display_name composto de nome + sobrenome (via app.py — aqui testamos direto)
    def test_register_display_name(self):
        user = self.store.register(
            "maria", "Maria Santos", "senha12345678", allow_bootstrap=False
        )
        self.assertEqual(user["display_name"], "Maria Santos")

    # 4. contact_email salvo sem ser credencial
    def test_register_contact_email_stored(self):
        user = self.store.register(
            "pedro", "Pedro Lima", "senha12345678", allow_bootstrap=False,
            contact_email="pedro@example.com"
        )
        self.assertEqual(user.get("contact_email"), "pedro@example.com")

    # 5. contact_email inválido é rejeitado
    def test_register_invalid_email_rejected(self):
        with self.assertRaises(AuthError):
            self.store.register(
                "lucia", "Lucia Rocha", "senha12345678", allow_bootstrap=False,
                contact_email="nao-e-um-email"
            )

    # 6. contact_email None/vazio não levanta erro
    def test_register_no_email_ok(self):
        user = self.store.register(
            "carlos", "Carlos Melo", "senha12345678", allow_bootstrap=False,
            contact_email=None
        )
        # Nenhum email: retorna None ou string vazia — não deve ser uma credencial
        self.assertFalse(user.get("contact_email"))  # None ou "" são ambos falsy

    # 7. Username duplicado é rejeitado
    def test_register_duplicate_username(self):
        self.store.register("dup", "Dup User", "senha12345678", allow_bootstrap=False)
        with self.assertRaises(AuthError):
            self.store.register("dup", "Dup User 2", "senha12345678", allow_bootstrap=False)

    # 8. Username muito curto é rejeitado
    def test_register_short_username(self):
        with self.assertRaises(AuthError):
            self.store.register("ab", "Nome Valido", "senha12345678", allow_bootstrap=False)

    # 9. Senha muito curta é rejeitada
    def test_register_short_password(self):
        with self.assertRaises(AuthError):
            self.store.register("validuser", "Nome Valido", "abc", allow_bootstrap=False)

    # 10. display_name muito curto é rejeitado
    def test_register_short_display_name(self):
        with self.assertRaises(AuthError):
            self.store.register("validuser2", "X", "senha12345678", allow_bootstrap=False)


class TestLoginBlocking(unittest.TestCase):
    """Usuários pendentes e rejeitados não podem fazer login."""

    def setUp(self):
        self.store = _make_store()
        _bootstrap_admin(self.store)
        self.pending_user = self.store.register(
            "pendente", "Usuario Pendente", "senha12345678", allow_bootstrap=False
        )

    def _get_admin(self):
        users = self.store.list_users()
        return next(u for u in users if u["username"] == "admin")

    # 11. Usuário pendente não consegue autenticar
    def test_pending_user_cannot_login(self):
        with self.assertRaises(AuthError):
            self.store.authenticate("pendente", "senha12345678")

    # 12. Usuário rejeitado não consegue autenticar
    def test_rejected_user_cannot_login(self):
        admin = self._get_admin()
        self.store.reject(self.pending_user["id"], rejected_by=admin["id"], reason="Teste")
        with self.assertRaises(AuthError):
            self.store.authenticate("pendente", "senha12345678")

    # 13. Admin (active) consegue autenticar
    def test_active_admin_can_login(self):
        user = self.store.authenticate("admin", "adminpassword01")
        self.assertEqual(user["status"], "active")


class TestApproveFlow(unittest.TestCase):
    """Fluxo de aprovação de cadastros pendentes."""

    def setUp(self):
        self.store = _make_store()
        self.admin = _bootstrap_admin(self.store)
        self.pending = self.store.register(
            "novo", "Novo Usuario", "senha12345678", allow_bootstrap=False
        )

    # 14. Aprovação com papel viewer
    def test_approve_as_viewer(self):
        approved = self.store.approve(
            self.pending["id"], role="viewer", approved_by=self.admin["id"]
        )
        self.assertEqual(approved["status"], "active")
        self.assertEqual(approved["role"], "viewer")
        self.assertIsNotNone(approved.get("approved_at"))

    # 15. Aprovação com papel controller
    def test_approve_as_controller(self):
        approved = self.store.approve(
            self.pending["id"], role="controller", approved_by=self.admin["id"]
        )
        self.assertEqual(approved["role"], "controller")

    # 16. Aprovação com papel admin
    def test_approve_as_admin(self):
        approved = self.store.approve(
            self.pending["id"], role="admin", approved_by=self.admin["id"]
        )
        self.assertEqual(approved["role"], "admin")

    # 17. Tentar aprovar usuário já aprovado retorna erro (pending guard)
    def test_double_approve_raises_error(self):
        self.store.approve(self.pending["id"], role="viewer", approved_by=self.admin["id"])
        with self.assertRaises(AuthError):
            self.store.approve(self.pending["id"], role="viewer", approved_by=self.admin["id"])

    # 18. Papel inválido é rejeitado
    def test_approve_invalid_role(self):
        with self.assertRaises(AuthError):
            self.store.approve(self.pending["id"], role="superuser", approved_by=self.admin["id"])

    # 19. approved_by é registrado corretamente
    def test_approve_records_approved_by(self):
        approved = self.store.approve(
            self.pending["id"], role="viewer", approved_by=self.admin["id"]
        )
        # Consulta direta para verificar approved_by (coluna interna não exposta no public_user)
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT approved_by FROM users WHERE id = ?", (approved["id"],)
            ).fetchone()
        self.assertEqual(row["approved_by"], self.admin["id"])

    # 20. Usuário aprovado pode fazer login
    def test_approved_user_can_login(self):
        self.store.approve(self.pending["id"], role="viewer", approved_by=self.admin["id"])
        user = self.store.authenticate("novo", "senha12345678")
        self.assertEqual(user["status"], "active")


class TestRejectFlow(unittest.TestCase):
    """Fluxo de rejeição de cadastros pendentes."""

    def setUp(self):
        self.store = _make_store()
        self.admin = _bootstrap_admin(self.store)
        self.pending = self.store.register(
            "recusado", "Usuario Recusado", "senha12345678", allow_bootstrap=False
        )

    # 21. Rejeição sem motivo funciona
    def test_reject_no_reason(self):
        rejected = self.store.reject(self.pending["id"], rejected_by=self.admin["id"])
        self.assertEqual(rejected["status"], "rejected")
        self.assertIsNotNone(rejected.get("rejected_at"))

    # 22. Rejeição com motivo armazena o texto
    def test_reject_with_reason(self):
        rejected = self.store.reject(
            self.pending["id"], rejected_by=self.admin["id"], reason="Dados insuficientes"
        )
        self.assertEqual(rejected.get("rejection_reason"), "Dados insuficientes")

    # 23. Tentar rejeitar usuário já rejeitado retorna erro
    def test_double_reject_raises_error(self):
        self.store.reject(self.pending["id"], rejected_by=self.admin["id"])
        with self.assertRaises(AuthError):
            self.store.reject(self.pending["id"], rejected_by=self.admin["id"])

    # 24. Tentar rejeitar usuário ativo retorna erro
    def test_reject_active_user_raises_error(self):
        self.store.approve(self.pending["id"], role="viewer", approved_by=self.admin["id"])
        with self.assertRaises(AuthError):
            self.store.reject(self.pending["id"], rejected_by=self.admin["id"])

    # 25. Motivo longo é truncado a 500 chars
    def test_reject_reason_truncated(self):
        long_reason = "x" * 600
        rejected = self.store.reject(
            self.pending["id"], rejected_by=self.admin["id"], reason=long_reason
        )
        self.assertLessEqual(len(rejected.get("rejection_reason") or ""), 500)

    # 26. list_users mostra usuário com status rejected
    def test_rejected_user_in_list(self):
        self.store.reject(self.pending["id"], rejected_by=self.admin["id"])
        users = self.store.list_users()
        statuses = [u["status"] for u in users]
        self.assertIn("rejected", statuses)

    # 27. rejected_at é uma string ISO
    def test_rejected_at_is_iso(self):
        rejected = self.store.reject(self.pending["id"], rejected_by=self.admin["id"])
        ts = rejected.get("rejected_at") or ""
        # Deve ser algo como 2026-09-18T00:00:00+00:00
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}T")


class TestContactEmail(unittest.TestCase):
    """Garantias extras sobre contact_email."""

    def setUp(self):
        self.store = _make_store()
        _bootstrap_admin(self.store)

    # 28. contact_email não vaza como credencial de auth (sintético interno)
    def test_contact_email_not_auth_credential(self):
        """O contact_email nunca deve coincidir com o email interno sintético usado pelo Supabase."""
        user = self.store.register(
            "teste", "Teste Dominium", "senha12345678", allow_bootstrap=False,
            contact_email="teste@example.com"
        )
        # O email interno sintético seria teste@auth.dominium.invalid — diferente de contact_email
        self.assertNotEqual(user.get("contact_email"), "teste@auth.dominium.invalid")
        self.assertEqual(user.get("contact_email"), "teste@example.com")

    # 29. contact_email com espaços ao redor é aceito (stripped internamente)
    def test_contact_email_stripped(self):
        user = self.store.register(
            "espaco", "Espaco User", "senha12345678", allow_bootstrap=False,
            contact_email="  espaco@example.com  "
        )
        # O valor armazenado deve ser sem espaços
        stored = user.get("contact_email") or ""
        self.assertFalse(stored.startswith(" ") or stored.endswith(" "))


if __name__ == "__main__":
    unittest.main(verbosity=2)
