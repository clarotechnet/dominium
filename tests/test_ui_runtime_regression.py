from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class UIRuntimeRegressionTests(unittest.TestCase):
    def test_impeccable_theme_is_loaded(self):
        index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/impeccable.css"', index)
        self.assertTrue((ROOT / "static" / "impeccable.css").is_file())

    def test_registration_ui_keeps_six_character_minimum(self):
        index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="authRegisterPassword" type="password" autocomplete="new-password" required minlength="6"', index)
        self.assertIn("De 6 a 128 caracteres", index)

    def test_hostinger_runtime_exposes_registration_through_operational_backend(self):
        server = (ROOT / "deploy" / "hostinger-web" / "server.js").read_text(encoding="utf-8")
        self.assertIn("registration_enabled: true", server)
        self.assertIn('app.post("/api/auth/register", async (req, res) => {', server)
        self.assertIn('edgeAuthAction("register", req.body || {})', server)
        self.assertIn("registrationRateLimited(req)", server)
        self.assertNotIn("Cadastro publico desabilitado", server)

if __name__ == "__main__":
    unittest.main()
