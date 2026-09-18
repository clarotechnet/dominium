import unittest


try:
    from supabase import create_client as _create_client  # noqa: F401
except ImportError:
    SUPABASE_AVAILABLE = False
else:
    SUPABASE_AVAILABLE = True


@unittest.skipUnless(SUPABASE_AVAILABLE, "pacote supabase nao instalado")
class SupabaseSDKCompatibilityTests(unittest.TestCase):
    def test_store_initializes_with_current_sync_client_options(self):
        from supabase_auth_store import SupabaseAuthStore

        store = SupabaseAuthStore(
            "https://example.supabase.co",
            "x" * 80,
            email_domain="auth.example.com",
        )
        self.assertTrue(hasattr(store.client.auth.admin, "create_user"))
        self.assertTrue(hasattr(store.client.auth.admin, "delete_user"))
        self.assertTrue(hasattr(store.client.auth, "sign_in_with_password"))


if __name__ == "__main__":
    unittest.main()
