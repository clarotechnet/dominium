import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from selenium.common.exceptions import WebDriverException

from app import _cloud_snapshot_to_live_lookup
from toa_browser import TOA_DUO_URL, TOA_URL
from toa_capture import TOACaptureLot
from toa_live import TOALiveSession, capture_payload_from_storage


class _ScriptDriver:
    def __init__(self) -> None:
        self.calls = []

    def execute_script(self, script, *arguments):
        self.calls.append((script, arguments))


class TOALiveCaptureTests(unittest.TestCase):
    def test_monitor_is_passive_and_never_opens_browser(self) -> None:
        factory = MagicMock()
        session = TOALiveSession(
            Path.cwd(),
            driver_factory=factory,
            check_interval=5,
        )
        with patch("toa_live.debugger_running", return_value=False):
            session.start()
            time.sleep(0.05)
            session.stop()

        factory.assert_not_called()
        self.assertFalse(session.public_state()["authenticated"])

    def test_monitor_reattaches_existing_automation_browser_without_launch(self) -> None:
        driver = MagicMock()
        driver.current_url = "https://clarobrasil.etadirect.com/toa/"
        factory = MagicMock(return_value=driver)
        session = TOALiveSession(Path.cwd(), driver_factory=factory)

        with (
            patch("toa_live.debugger_running", return_value=True),
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=True),
        ):
            session._refresh_session_state_locked()

        factory.assert_called_once_with(
            headless=False,
            launch_if_missing=False,
        )
        state = session.public_state()
        self.assertTrue(state["connected"])
        self.assertTrue(state["authenticated"])

    def test_monitor_does_not_launch_when_automation_browser_is_absent(self) -> None:
        factory = MagicMock()
        session = TOALiveSession(Path.cwd(), driver_factory=factory)

        with patch("toa_live.debugger_running", return_value=False):
            session._refresh_session_state_locked()

        factory.assert_not_called()
        self.assertFalse(session.public_state()["connected"])

    def test_monitor_recovers_disconnected_driver_immediately(self) -> None:
        dead = MagicMock()
        type(dead).current_url = PropertyMock(
            side_effect=WebDriverException(
                "invalid session id: session deleted as the browser has closed the connection"
            )
        )
        replacement = MagicMock()
        replacement.current_url = "https://clarobrasil.etadirect.com/toa/"
        factory = MagicMock(return_value=replacement)
        session = TOALiveSession(Path.cwd(), driver_factory=factory)
        session._driver = dead

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=True),
        ):
            session._refresh_session_state_locked()

        factory.assert_called_once_with(headless=False, launch_if_missing=True)
        self.assertIs(session._driver, replacement)
        self.assertTrue(session.public_state()["authenticated"])
        self.assertTrue(session.public_state()["last_recovery_at"])

    def test_lookup_requires_operator_opened_session(self) -> None:
        session = TOALiveSession(Path.cwd(), driver_factory=MagicMock())

        with self.assertRaisesRegex(RuntimeError, "Abra o TOA pelo botao"):
            session.lookup_contract("412774867")

        session.driver_factory.assert_not_called()

    def test_readonly_script_recovers_disconnected_driver_once(self) -> None:
        dead = MagicMock()
        dead.current_url = "https://clarobrasil.etadirect.com/toa/"
        dead.execute_script.side_effect = WebDriverException(
            "disconnected: not connected to DevTools"
        )
        replacement = MagicMock()
        replacement.current_url = "https://clarobrasil.etadirect.com/toa/"
        replacement.execute_script.return_value = {"ok": True}
        factory = MagicMock(return_value=replacement)
        session = TOALiveSession(Path.cwd(), driver_factory=factory)
        session._driver = dead

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=True),
        ):
            result = session.execute_readonly_script("return {ok: true};")

        self.assertEqual(result, {"ok": True})
        factory.assert_called_once_with(headless=False, launch_if_missing=True)
        replacement.execute_script.assert_called_once_with("return {ok: true};")

    def test_open_session_rejects_empty_credentials_without_opening_browser(self) -> None:
        factory = MagicMock()
        session = TOALiveSession(Path.cwd(), driver_factory=factory)

        with self.assertRaisesRegex(ValueError, "usuario e senha"):
            session.open_session("", "")

        factory.assert_not_called()

    def test_open_session_uses_supplied_credentials_without_persisting_them(self) -> None:
        driver = MagicMock()
        driver.current_url = "https://clarobrasil.etadirect.com/toa/"
        driver.execute_script.return_value = True
        session = TOALiveSession(
            Path.cwd(),
            driver_factory=MagicMock(return_value=driver),
        )
        session._fill_credentials_locked = MagicMock()
        session._click_login_locked = MagicMock()
        session._wait_authenticated = MagicMock()

        with (
            patch("toa_live.authenticated", return_value=False),
            patch("toa_live.login_visible", return_value=True),
            patch("toa_live.time.sleep"),
        ):
            state = session.open_session("Z-TESTE", "senha-temporaria")

        driver.get.assert_called_once_with(TOA_URL)
        session._fill_credentials_locked.assert_called_once_with(
            "Z-TESTE",
            "senha-temporaria",
        )
        session._click_login_locked.assert_called_once_with()
        session._wait_authenticated.assert_called_once_with()
        self.assertTrue(state["authenticated"])
        self.assertFalse(state["credentials_persisted"])
        self.assertEqual(state["access_mode"], "direct")
        self.assertFalse(hasattr(session, "credentials_path"))
        self.assertNotIn("Z-TESTE", repr(session.__dict__))
        self.assertNotIn("senha-temporaria", repr(session.__dict__))

    def test_open_session_uses_duo_entrance_when_selected(self) -> None:
        driver = MagicMock()
        driver.current_url = "about:blank"
        session = TOALiveSession(
            Path.cwd(),
            driver_factory=MagicMock(return_value=driver),
        )
        session._fill_credentials_locked = MagicMock()
        session._click_login_locked = MagicMock()
        session._wait_authenticated = MagicMock()

        with (
            patch("toa_live.authenticated", return_value=False),
            patch("toa_live.login_visible", return_value=True),
            patch("toa_live.time.sleep"),
        ):
            state = session.open_session("Z-TESTE", "senha", "duo")

        driver.get.assert_called_once_with(TOA_DUO_URL)
        self.assertEqual(state["access_mode"], "duo")

    def test_open_session_rejects_unknown_access_mode(self) -> None:
        factory = MagicMock()
        session = TOALiveSession(Path.cwd(), driver_factory=factory)

        with self.assertRaisesRegex(ValueError, "acesso direto/token"):
            session.open_session("Z-TESTE", "senha", "outro")

        factory.assert_not_called()

    def test_monitor_tolerates_one_transient_authentication_miss(self) -> None:
        session = TOALiveSession(Path.cwd())
        session._driver = MagicMock()
        session._driver.current_url = "https://clarobrasil.etadirect.com/"
        session._update_state(configured=True, connected=True, authenticated=True)

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=False),
        ):
            session._refresh_session_state_locked()

        state = session.public_state()
        self.assertTrue(state["connected"])
        self.assertTrue(state["authenticated"])
        self.assertEqual(session._authentication_misses, 1)

    def test_monitor_marks_offline_after_consecutive_authentication_misses(self) -> None:
        session = TOALiveSession(Path.cwd())
        session._driver = MagicMock()
        session._driver.current_url = "https://clarobrasil.etadirect.com/"
        session._update_state(configured=True, connected=True, authenticated=True)

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=False),
        ):
            session._refresh_session_state_locked()
            session._refresh_session_state_locked()

        state = session.public_state()
        self.assertTrue(state["connected"])
        self.assertFalse(state["authenticated"])
        self.assertEqual(state["last_error"], "Login TOA necessario")

    def test_monitor_marks_visible_login_offline_immediately(self) -> None:
        session = TOALiveSession(Path.cwd())
        session._driver = MagicMock()
        session._driver.current_url = "https://clarobrasil.etadirect.com/toa/"
        session._update_state(configured=True, connected=True, authenticated=True)

        with (
            patch("toa_live.login_visible", return_value=True),
            patch("toa_live.authenticated") as auth_check,
        ):
            session._refresh_session_state_locked()

        self.assertFalse(session.public_state()["authenticated"])
        auth_check.assert_not_called()

    def test_lookup_session_rechecks_transient_page_transition(self) -> None:
        session = TOALiveSession(Path.cwd())
        session._driver = MagicMock()
        session._driver.current_url = "https://clarobrasil.etadirect.com/"

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", side_effect=[False, True]),
            patch("toa_live.time.sleep") as wait,
        ):
            session._ensure_session_locked()

        self.assertTrue(session.public_state()["authenticated"])
        wait.assert_called_once_with(0.25)

    def test_lookup_recovers_disconnect_and_retries_once(self) -> None:
        dead = MagicMock()
        dead.current_url = "https://clarobrasil.etadirect.com/toa/"
        replacement = MagicMock()
        replacement.current_url = "https://clarobrasil.etadirect.com/toa/"
        factory = MagicMock(return_value=replacement)
        session = TOALiveSession(Path.cwd(), driver_factory=factory)
        session._driver = dead
        fake_lot = MagicMock()
        fake_lot.review_contracts.return_value = []
        payload = {"os_list": [{"aid": "194000001"}]}
        capture_path = session.root / "logs" / "capture.json"
        ledger_path = session.root / "logs" / "ledger.json"

        with (
            patch("toa_live.login_visible", return_value=False),
            patch("toa_live.authenticated", return_value=True),
            patch.object(session, "_inject_collector_locked", side_effect=[
                WebDriverException("disconnected: not connected to DevTools"),
                None,
                None,
            ]),
            patch.object(session, "_start_single_lookup_locked"),
            patch.object(session, "_queue_row_locked", return_value={"status": "done"}),
            patch.object(session, "_resume_pending_queue_locked"),
            patch.object(session, "_storage_locked", return_value={}),
            patch("toa_live.capture_payload_from_storage", return_value=payload),
            patch("toa_live.TOACaptureLot.from_dict", return_value=fake_lot),
            patch.object(session, "_persist_capture", return_value=capture_path),
            patch.object(session, "_persist_inventory_ledger", return_value=ledger_path),
        ):
            result = session.lookup_contract("412774867")

        self.assertTrue(result["ok"])
        factory.assert_called_once_with(headless=False, launch_if_missing=True)
        self.assertTrue(session.public_state()["last_recovery_at"])

    def test_extracts_only_requested_contract_and_normalizes(self) -> None:
        entry = {
            "aid": "194000001",
            "contract": "4231016",
            "os": {
                "activity": {
                    "aid": "194000001",
                    "contract": "4231016",
                    "city": "NATAL",
                    "work_type": "Instalacao",
                    "status": "complete",
                    "technician_id": "99",
                    "completion_summary": "Baixa realizada com sucesso",
                },
                "route": {"aid": "194000001"},
                "tasks": [{
                    "index": 1,
                    "os_number": "2646000001",
                    "status": "E",
                    "close_code": "409",
                }],
                "inventory": [{
                    "invid": "1",
                    "activity_id": "194000001",
                    "provider_id": "99",
                    "pool": "install",
                    "kind": "equipment",
                    "type": "3 - EMTA",
                    "serial": "ABC123",
                    "quantity": "1",
                }],
                "forms": [],
                "responsibility": {
                    "assigned_technician": {"id": "99", "name": "TECNICO TESTE"},
                    "route_provider": {"id": "99", "name": "TECNICO TESTE"},
                    "inventory_providers": [{"id": "99", "name": "TECNICO TESTE"}],
                    "form_submitters": [],
                },
            },
            "classification": {"category": "produtiva", "codes": ["409"]},
            "automation": {"decision": "candidate_after_validation", "reasons": []},
        }
        other = {**entry, "aid": "194000002", "contract": "9999999"}
        other["os"] = {**entry["os"], "activity": {
            **entry["os"]["activity"], "aid": "194000002", "contract": "9999999"
        }}
        storage = {
            "order": ["194000001", "194000002"],
            "items": {"194000001": entry, "194000002": other},
        }

        payload = capture_payload_from_storage(storage, "4231016")
        self.assertEqual(payload["metadata"]["count"], 1)
        lot = TOACaptureLot.from_dict(payload)
        result = lot.review_contracts(["4231016"])[0]
        self.assertTrue(result["found"])
        self.assertEqual(result["tasks"][0]["os_number"], "2646000001")
        self.assertEqual(result["installed_equipment"][0]["serial"], "ABC123")
        self.assertTrue(result["dry_run_only"])

    def test_rejects_missing_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "nao capturou"):
            capture_payload_from_storage({"order": [], "items": {}}, "4231016")

    def test_live_lookup_clears_only_visual_queue_before_adding_contract(self) -> None:
        session = TOALiveSession(Path.cwd())
        driver = _ScriptDriver()
        session._driver = driver

        session._start_single_lookup_locked("412774867")

        script, arguments = driver.calls[0]
        self.assertEqual(arguments, ("412774867",))
        self.assertLess(script.index("clearQueue"), script.index("addContracts"))
        self.assertIn("clearQueue('APAGAR')", script)
        self.assertNotIn("clearBatch", script)


class CloudSnapshotLookupTests(unittest.TestCase):
    def test_productive_with_materials(self) -> None:
        snapshot = {
            "contract": "4252617",
            "activity_id": "123",
            "materials": [
                {"material_code": "MAT01", "quantity": "2"},
                {"material_code": "MAT02", "quantity": "5"},
            ],
            "materials_applicable": True,
            "materials_complete": True,
            "validation": {"valid": True, "errors": [], "warnings": [], "reasons": []},
            "inventory_diagnostics": {
                "inventory_count": 2,
                "materials_count": 2,
                "captured_materials_count": 0,
                "source": "toa_cloud",
            },
        }
        res = _cloud_snapshot_to_live_lookup(snapshot, 0.5)
        self.assertTrue(res["ok"])
        activity = res["results"][0]
        self.assertEqual(len(activity["materials"]), 2)
        self.assertEqual(activity["materials"][0]["material_code"], "MAT01")
        self.assertEqual(activity["materials_applicable"], True)
        self.assertEqual(activity["materials_complete"], True)
        self.assertEqual(activity["decision"], "candidate_after_validation")
        self.assertIn("TOA: inventário 2 | miscelâneas operacionais 2 | auditoria 0 | captura completa", activity["inventory_diagnostics_line"])

    def test_disconnect_materials_not_applicable(self) -> None:
        snapshot = {
            "contract": "4252617",
            "activity_id": "124",
            "materials": [],
            "captured_materials_for_audit": [
                {"material_code": "AUD01", "quantity": "1"}
            ],
            "materials_applicable": False,
            "materials_complete": True,
            "validation": {"valid": True, "errors": [], "warnings": [], "reasons": []},
        }
        res = _cloud_snapshot_to_live_lookup(snapshot, 0.5)
        activity = res["results"][0]
        self.assertEqual(len(activity["materials"]), 0)
        self.assertEqual(len(activity["captured_materials_for_audit"]), 1)
        self.assertEqual(activity["materials_applicable"], False)
        self.assertIn("Miscelâneas não aplicáveis à baixa de desconexão", activity["validation_warnings"][0])

    def test_incomplete_materials_blocks_decision(self) -> None:
        snapshot = {
            "contract": "4252617",
            "activity_id": "125",
            "materials": [],
            "materials_applicable": True,
            "materials_complete": False,
            "validation": {"valid": True, "errors": [], "warnings": [], "reasons": []},
        }
        res = _cloud_snapshot_to_live_lookup(snapshot, 0.5)
        activity = res["results"][0]
        self.assertEqual(activity["decision"], "blocked_manual_review")
        self.assertIn("Captura de materiais incompleta no TOA", activity["validation_errors"][0])


if __name__ == "__main__":
    unittest.main()
