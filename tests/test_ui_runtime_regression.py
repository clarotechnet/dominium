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

    def test_operation_orbs_are_bound_to_real_frontend_states(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        motion = (ROOT / "static" / "motion-ui.js").read_text(encoding="utf-8")
        styles = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('CustomEvent("dominium:operation-state"', app)
        self.assertIn("Montando Central Inteligente", app)
        self.assertIn("Consultando ordens no Imperium", app)
        self.assertIn("Buscando ${query} no TOA", app)
        self.assertIn("Validando estoque e miscelâneas", app)
        self.assertIn("Executando lote de ${orders.length} baixas", app)
        self.assertIn("operationOrbHud", motion)
        self.assertIn("hud.dataset.phase = phase", motion)
        self.assertIn('"busy"', motion)
        self.assertIn('"Imperium ocupado"', app)
        self.assertIn(".operation-orb-hud", styles)
        self.assertIn('[data-phase="busy"]', styles)
        self.assertIn('[data-phase="success"]', styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)

    def test_animated_toast_keeps_accessibility_controls(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("dismissToast", app)
        self.assertIn('close.setAttribute("aria-label", "Fechar notificação")', app)
        self.assertIn('toast.setAttribute("aria-live"', app)
        self.assertIn(".toast-progress", styles)

    def test_login_success_animation_runs_after_real_authentication(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        login_response = app.index('const payload = await authApi("/api/auth/login"')
        success_motion = app.index("await playAuthSuccess()", login_response)
        hide_gate = app.index("hideAuthGate();", success_motion)
        self.assertLess(login_response, success_motion)
        self.assertLess(success_motion, hide_gate)
        self.assertIn('gate.classList.add("auth-success")', app)
        self.assertIn("#authLoginSubmit.auth-confirmed", styles)
        self.assertIn("@keyframes auth-success-card", styles)
        self.assertIn(".auth-gate.auth-exit", styles)

    def test_created_orders_use_server_confirmation_and_refresh_silently(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function mergeConfirmedCreatedOrders", app)
        self.assertIn("function reconcileCreatedOrders", app)
        self.assertIn("row.recognized = true", app)
        self.assertIn("id_os: idOs", app)
        self.assertIn("const reconciliation = reconcileCreatedOrders(result)", app)
        self.assertIn("scheduleCreatedOrderReconciliation(result)", app)
        self.assertIn("const delays = [0, 1200, 2800, 5500]", app)
        self.assertIn(
            'await loadOrders({ preserveSelection: true, quiet: true, visual: false })',
            app,
        )
        self.assertIn('"Criando OS no Imperium"', app)
        self.assertIn('"OS reconhecida no Dominium"', app)
        self.assertNotIn('"Confirmando OS no Imperium"', app)

    def test_hostinger_runtime_exposes_registration_through_operational_backend(self):
        server = (ROOT / "deploy" / "hostinger-web" / "server.js").read_text(encoding="utf-8")
        self.assertIn("registration_enabled: true", server)
        self.assertIn('app.post("/api/auth/register", async (req, res) => {', server)
        self.assertIn('edgeAuthAction("register", req.body || {})', server)
        self.assertIn("registrationRateLimited(req)", server)
        self.assertNotIn("Cadastro publico desabilitado", server)

if __name__ == "__main__":
    unittest.main()
