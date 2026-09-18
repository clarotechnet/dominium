import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from disconnect_automation import DisconnectAutomation, normalize_window


def record(
    contract: str,
    window: str,
    source: str = "Atividades-NTL-DMV_ADM_29_07_26.csv",
) -> dict:
    return {
        "profile": "natal",
        "target": "rn",
        "date": "2026-07-29",
        "contract": contract,
        "windows": [window],
        "source_files": [source],
        "os_numbers": [f"2648{contract}"],
        "technicians": ["TECNICO"],
    }


class DisconnectAutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "state.json"
        self.automation = DisconnectAutomation(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def moment(hour: int, minute: int = 0) -> dt.datetime:
        return dt.datetime(2026, 7, 29, hour, minute)

    def prepare(self, records: list[dict]) -> dict:
        return self.automation.prepare(
            records,
            date="2026-07-29",
            profile="natal",
            target="rn",
            now=self.moment(7),
        )

    def test_normalizes_supported_windows(self) -> None:
        self.assertEqual(normalize_window("08:00 - 11:00"), "08:00-11:00")
        self.assertEqual(normalize_window("8 - 22"), "08:00-22:00")
        self.assertEqual(normalize_window("09:00 - 13:00"), "")

    def test_accepts_only_ntl_or_pwm_adm_sources(self) -> None:
        state = self.prepare([
            record("1", "08:00 - 11:00"),
            record("2", "08:00 - 12:00", "Atividades-PWM-DMV_ADM_29_07_26.csv"),
            record("3", "08:00 - 22:00", "Atividades-FTZ-DMV_ADM_29_07_26.csv"),
            record("4", "08:00 - 22:00", "Atividades-NTL-DMV_29_07_26.csv"),
            record("5", "08:00 - 22:00", "Atividades-PWM-DMV_VT_29_07_26.csv"),
        ])
        statuses = {item["contract"]: item["status"] for item in state["items"]}
        self.assertEqual(statuses["1"], "pending")
        self.assertEqual(statuses["2"], "pending")
        self.assertNotIn("3", statuses)
        self.assertNotIn("4", statuses)
        self.assertNotIn("5", statuses)
        self.assertEqual(state["ignored_records"], 3)

    def test_mixed_adm_and_vt_sources_are_excluded(self) -> None:
        mixed = record("6", "08:00 - 11:00")
        mixed["source_files"].append("Atividades-NTL-DMV_VT_29_07_26.csv")

        state = self.prepare([mixed])

        self.assertEqual(state["items"], [])
        self.assertEqual(state["ignored_records"], 1)

    def test_prepare_reopens_only_transient_legacy_manual_reviews(self) -> None:
        self.prepare([
            record("1", "08:00 - 11:00"),
            record("2", "08:00 - 11:00"),
        ])
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload["items"]["1"].update(
            status="manual_review",
            last_error="A sessao TOA nao esta autenticada",
            reasons=["legacy_authentication_failure"],
        )
        payload["items"]["2"].update(
            status="manual_review",
            last_error="close_code_requires_observation:404",
            reasons=["close_code_requires_observation:404"],
        )
        self.path.write_text(json.dumps(payload), encoding="utf-8")

        state = self.prepare([
            record("1", "08:00 - 11:00"),
            record("2", "08:00 - 11:00"),
        ])
        statuses = {item["contract"]: item["status"] for item in state["items"]}

        self.assertEqual(statuses["1"], "pending")
        self.assertEqual(statuses["2"], "manual_review")

    def test_0811_is_claimed_before_0812_and_0822(self) -> None:
        self.prepare([
            record("22", "08:00 - 22:00"),
            record("12", "08:00 - 12:00"),
            record("11", "08:00 - 11:00"),
        ])
        self.automation.action("start", now=self.moment(8))
        claimed = self.automation.claim(now=self.moment(8))
        self.assertEqual(claimed["item"]["contract"], "11")

    def test_0812_waits_until_all_0811_are_terminal(self) -> None:
        self.prepare([
            record("11", "08:00 - 11:00"),
            record("12", "08:00 - 12:00"),
        ])
        self.automation.action("start", now=self.moment(8))
        first = self.automation.claim(now=self.moment(8))
        self.automation.update(
            "11", first["lease_token"], "waiting_toa", now=self.moment(8)
        )
        no_claim = self.automation.claim(
            now=dt.datetime(2026, 7, 29, 8, 0, 15)
        )
        self.assertFalse(no_claim["claimed"])
        waiting = self.automation.claim(now=self.moment(8, 1))
        self.automation.update(
            "11", waiting["lease_token"], "manual_review", now=self.moment(8, 1)
        )
        second = self.automation.claim(now=self.moment(8, 1))
        self.assertEqual(second["item"]["contract"], "12")

    def test_0812_can_start_after_0811_is_awaiting_confirmation(self) -> None:
        self.prepare([
            record("11", "08:00 - 11:00"),
            record("12", "08:00 - 12:00"),
        ])
        self.automation.action("start", now=self.moment(8))
        first = self.automation.claim(now=self.moment(8))
        self.automation.update(
            "11", first["lease_token"], "submitting", now=self.moment(8)
        )
        self.automation.update(
            "11",
            first["lease_token"],
            "awaiting_confirmation",
            now=self.moment(8),
        )
        second = self.automation.claim(now=self.moment(8))
        self.assertTrue(second["claimed"])
        self.assertEqual(second["item"]["contract"], "12")

    def test_0822_is_filler_while_tighter_window_waits(self) -> None:
        self.prepare([
            record("11", "08:00 - 11:00"),
            record("22", "08:00 - 22:00"),
        ])
        self.automation.action("start", now=self.moment(8))
        first = self.automation.claim(now=self.moment(8))
        self.automation.update(
            "11", first["lease_token"], "waiting_toa", now=self.moment(8)
        )
        filler = self.automation.claim(
            now=dt.datetime(2026, 7, 29, 8, 0, 15)
        )
        self.assertEqual(filler["item"]["contract"], "22")

    def test_1114_never_starts_before_11(self) -> None:
        self.prepare([record("14", "11:00 - 14:00")])
        self.automation.action("start", now=self.moment(10, 59))
        self.assertFalse(self.automation.claim(now=self.moment(10, 59))["claimed"])
        self.assertTrue(self.automation.claim(now=self.moment(11))["claimed"])

    def test_pauses_and_preserves_progress_after_restart(self) -> None:
        self.prepare([record("11", "08:00 - 11:00")])
        self.automation.action("start", now=self.moment(8))
        self.automation.claim(now=self.moment(8))
        restarted = DisconnectAutomation(self.path)
        state = restarted.public_state(now=self.moment(8, 1))
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["items"][0]["status"], "pending")

    def test_completed_and_awaiting_items_are_never_reclaimed(self) -> None:
        self.prepare([
            record("1", "08:00 - 11:00"),
            record("2", "08:00 - 11:00"),
        ])
        self.automation.action("start", now=self.moment(8))
        first = self.automation.claim(now=self.moment(8))
        self.automation.update(
            first["item"]["contract"],
            first["lease_token"],
            "completed",
            now=self.moment(8),
        )
        second = self.automation.claim(now=self.moment(8))
        self.automation.update(
            second["item"]["contract"],
            second["lease_token"],
            "awaiting_confirmation",
            now=self.moment(8),
        )
        state = self.automation.public_state(now=self.moment(8, 1))
        self.assertEqual(state["status"], "completed")
        self.assertFalse(self.automation.claim(now=self.moment(8, 1))["claimed"])

    def test_submitting_can_record_one_final_result_with_same_lease(self) -> None:
        self.prepare([record("1", "08:00 - 11:00")])
        self.automation.action("start", now=self.moment(8))
        claimed = self.automation.claim(now=self.moment(8))
        token = claimed["lease_token"]
        self.automation.update(
            "1", token, "submitting", now=self.moment(8)
        )
        state = self.automation.update(
            "1",
            token,
            "awaiting_confirmation",
            result={"pending": True},
            now=self.moment(8, 1),
        )
        self.assertEqual(state["items"][0]["status"], "awaiting_confirmation")
        with self.assertRaises(ValueError):
            self.automation.update(
                "1", token, "completed", now=self.moment(8, 2)
            )

    def test_submitting_can_persist_progress_for_multiple_orders(self) -> None:
        self.prepare([record("1", "08:00 - 11:00")])
        self.automation.action("start", now=self.moment(8))
        claimed = self.automation.claim(now=self.moment(8))
        token = claimed["lease_token"]
        first = self.automation.update(
            "1",
            token,
            "submitting",
            result={"submitted_os": ["100"], "current_os": "101"},
            now=self.moment(8),
        )
        second = self.automation.update(
            "1",
            token,
            "submitting",
            result={"submitted_os": ["100", "101"], "current_os": ""},
            now=self.moment(8, 1),
        )
        self.assertEqual(first["items"][0]["result"]["submitted_os"], ["100"])
        self.assertEqual(
            second["items"][0]["result"]["submitted_os"], ["100", "101"]
        )
        self.assertEqual(second["current_contract"], "1")

    def test_window_accepts_en_dash(self) -> None:
        self.assertEqual(normalize_window("08:00 \u2013 11:00"), "08:00-11:00")

    def test_state_is_valid_json_after_each_atomic_write(self) -> None:
        self.prepare([record("1", "08:00 - 11:00")])
        self.automation.action("start", now=self.moment(8))
        json.loads(self.path.read_text(encoding="utf-8"))

    def test_wrong_profile_or_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.automation.prepare(
                [],
                date="2026-07-29",
                profile="fortaleza",
                target="ftz",
            )


if __name__ == "__main__":
    unittest.main()
