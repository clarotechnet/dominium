import tempfile
import unittest
from pathlib import Path

from whatsapp_bridge_service import (
    WHATSAPP_ALLOWED_GROUPS,
    WhatsAppBridgeError,
    WhatsAppBridgeService,
)


class WhatsAppBridgeServiceTests(unittest.TestCase):
    def test_recife_inbox_preserves_nine_digit_contracts(self):
        service = WhatsAppBridgeService(Path('.'),request=lambda *_: {
            'ok':True,'messages':[
                {'id':'RECIFE','chat_jid':'120363425385335332@g.us','contracts':['900000001']},
                {'id':'PHONE','chat_jid':'120363425385335332@g.us','contracts':['5581999999999']},
                {'id':'OTHER','chat_jid':'other@g.us','contracts':['900000001']},
            ]})
        self.assertEqual([m['id'] for m in service.messages(profile='recife')['messages']],['RECIFE'])

    def test_automation_is_enabled_for_official_and_test_natal_groups(self):
        self.assertEqual(
            WHATSAPP_ALLOWED_GROUPS["natal"]["automation_jids"],
            [
                "120363028547806621@g.us",
                "120363423496684075@g.us",
            ],
        )

    def test_natal_inbox_accepts_official_and_test_groups(self):
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: {
                "ok": True,
                "messages": [
                    {
                        "id": "OFFICIAL",
                        "chat_jid": "120363028547806621@g.us",
                        "contracts": ["3993346"],
                    },
                    {
                        "id": "TEST",
                        "chat_jid": "120363423496684075@g.us",
                        "contracts": ["3993346"],
                    },
                    {
                        "id": "OTHER",
                        "chat_jid": "other@g.us",
                        "contracts": ["3993346"],
                    },
                ],
            },
        )

        result = service.messages(profile="natal")

        self.assertEqual(
            [message["id"] for message in result["messages"]],
            ["OFFICIAL", "TEST"],
        )

    def test_offline_connector_returns_empty_inbox_instead_of_raising(self):
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda *_args: (_ for _ in ()).throw(
                WhatsAppBridgeError("connection refused")
            ),
        )

        result = service.messages(profile="natal")

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "offline")
        self.assertEqual(result["messages"], [])

    def test_offline_connector_returns_disabled_automation_status(self):
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda *_args: (_ for _ in ()).throw(
                WhatsAppBridgeError("connection refused")
            ),
        )

        result = service.automation_status("natal")

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "offline")
        self.assertFalse(result["enabled"])
        self.assertTrue(result["pilot_available"])

    def test_reaction_is_blocked_before_confirmation(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True},
        )
        result = service.react_confirmed(
            "natal",
            {"state": "pending", "num_os": "2647378599", "contract": "4234309"},
        )
        self.assertFalse(result["reacted"])
        self.assertEqual(calls, [])

    def test_confirmed_record_uses_exact_identity(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True, "reacted": True},
        )
        result = service.react_confirmed(
            "natal",
            {
                "state": "confirmed",
                "num_os": "2647378599",
                "contract": "4234309",
            },
        )
        self.assertTrue(result["reacted"])
        self.assertEqual(
            calls,
            [
                (
                    "POST",
                    "/react-confirmed",
                    {
                        "profile": "natal",
                        "contract": "4234309",
                        "num_os": "2647378599",
                    },
                )
            ],
        )

    def test_missing_identity_never_calls_connector(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True},
        )
        result = service.react_confirmed("natal", {"state": "confirmed"})
        self.assertEqual(result["reason"], "identity_incomplete")
        self.assertEqual(calls, [])

    def test_missing_dependencies_are_reported_without_starting_process(self):
        with tempfile.TemporaryDirectory() as directory:
            service = WhatsAppBridgeService(Path(directory))
            result = service.start_process()
        self.assertEqual(result["state"], "setup_required")
        self.assertFalse(result["connected"])

    def test_automation_status_uses_selected_profile(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True, "enabled": False},
        )

        result = service.automation_status("natal")

        self.assertFalse(result["enabled"])
        self.assertEqual(calls, [("GET", "/automation?profile=natal", None)])

    def test_automation_toggle_sends_explicit_boolean(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True, "enabled": payload["enabled"]},
        )

        enabled = service.set_automation("natal", True)
        disabled = service.set_automation("natal", False)

        self.assertTrue(enabled["enabled"])
        self.assertFalse(disabled["enabled"])
        self.assertEqual(
            calls,
            [
                (
                    "POST",
                    "/automation/toggle",
                    {"profile": "natal", "enabled": True},
                ),
                (
                    "POST",
                    "/automation/toggle",
                    {"profile": "natal", "enabled": False},
                ),
            ],
        )

    def test_toa_inspection_is_persisted_by_message_identity(self):
        calls = []
        service = WhatsAppBridgeService(
            Path("."),
            request=lambda method, path, payload: calls.append(
                (method, path, payload)
            )
            or {"ok": True},
        )
        payload = {
            "message_id": "M1",
            "chat_jid": "120363028547806621@g.us",
            "contract": "4236115",
            "inspection": {
                "contract": "4236115",
                "write_enabled": False,
            },
        }
        service.record_toa_inspection(payload)
        self.assertEqual(calls, [("POST", "/toa-inspection", payload)])


if __name__ == "__main__":
    unittest.main()
