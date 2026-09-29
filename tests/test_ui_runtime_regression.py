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

    def test_auto_improductive_audit_drilldown_is_present(self):
        index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="autoImproductiveClosedTotal"', index)
        self.assertIn('data-auto-audit="blocked"', index)
        self.assertIn('id="autoImproductiveAuditDialog"', index)
        self.assertIn("autoImproductiveAuditItems", app)
        self.assertIn("autoImproductiveBlockReason", app)
        self.assertIn("recent_closed", app)
        self.assertIn("current_run", app)

    def test_auto_improductive_worker_only_scans_current_day(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("scan_dates = (now.date(),)", source)
        self.assertNotIn(
            "scan_dates = (now.date() - dt.timedelta(days=1), now.date())",
            source,
        )
        self.assertIn(
            'f"{profile.key}:{today_text}:{order.id_os}:{code}"',
            source,
        )
        self.assertIn(
            "AUTO_IMPRODUCTIVE_CLOSER.prune_blocked_for_date(dt.date.today())",
            source,
        )

    def test_blocked_audit_does_not_claim_closed_from_code_alone(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn(
            "A OS saiu de campo com outro codigo no Imperium",
            app,
        )
        self.assertNotIn(
            "Ja estava baixada no Imperium com outro codigo",
            app,
        )

    def test_hostinger_runtime_exposes_registration_through_operational_backend(self):
        server = (ROOT / "deploy" / "hostinger-web" / "server.js").read_text(encoding="utf-8")
        self.assertIn("registration_enabled: true", server)
        self.assertIn('app.post("/api/auth/register", async (req, res) => {', server)
        self.assertIn('edgeAuthAction("register", req.body || {})', server)
        self.assertIn("registrationRateLimited(req)", server)
        self.assertNotIn("Cadastro publico desabilitado", server)

if __name__ == "__main__":
    unittest.main()
