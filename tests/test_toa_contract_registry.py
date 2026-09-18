import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from toa_contract_registry import (
    DEFAULT_REVIEW_TIMES,
    TOAContractRegistry,
    review_slot_for_window,
)


@dataclass
class FakeOrder:
    contract: str
    date: str
    city: str
    technician: str
    technician_name: str
    time_window: str
    service_window: str
    os_number: str
    technician_login: str = ""
    activity_status: str = "complete"
    activity_id: str = ""
    os_type: str = ""
    workzone_key: str = ""
    os_status: str = ""
    close_code: str = ""


@dataclass
class FakePreview:
    orders: tuple[FakeOrder, ...]


class TOAContractRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "registry.json"
        self.registry = TOAContractRegistry(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_windows_are_assigned_to_the_next_review_slot(self) -> None:
        self.assertEqual(review_slot_for_window("08:00 - 11:00"), "09:00")
        self.assertEqual(review_slot_for_window("11:00 - 14:00"), "14:00")
        self.assertEqual(review_slot_for_window("15:00 - 18:00"), "17:20")
        self.assertEqual(review_slot_for_window("IMEDIATA"), "sem_janela")

    def test_preview_is_persisted_and_deduplicated_by_contract_and_date(self) -> None:
        preview = FakePreview((
            FakeOrder(
                "123", "20/07/2026", "NATAL", "Z1", "TECNICO UM",
                "08:00 - 11:00", "07:45 - 08:45", "9001",
            ),
            FakeOrder(
                "123", "20/07/2026", "NATAL", "Z1", "TECNICO UM",
                "08:00 - 11:00", "07:45 - 08:45", "9002",
            ),
            FakeOrder(
                "456", "20/07/2026", "NATAL", "Z2", "TECNICO DOIS",
                "11:00 - 14:00", "10:45 - 11:45", "9003",
            ),
        ))

        result = self.registry.record_preview(
            preview, profile="natal", target="rn", source="Atividades-NTL.csv",
            seen_at="2026-07-20T09:10:00",
        )
        state = self.registry.public_state(profile="natal")

        self.assertEqual(result["recorded"], 2)
        self.assertEqual(state["count"], 2)
        first = next(item for item in state["records"] if item["contract"] == "123")
        self.assertEqual(first["os_numbers"], ["9001", "9002"])
        self.assertEqual(
            [item["os_number"] for item in first["orders"]],
            ["9001", "9002"],
        )
        self.assertEqual(first["orders"][0]["time_window"], "08:00 - 11:00")
        self.assertEqual(first["orders"][0]["service_window"], "07:45 - 08:45")
        self.assertEqual(first["orders"][0]["source_file"], "Atividades-NTL.csv")
        self.assertEqual(first["orders"][0]["os_status"], "")
        self.assertEqual(first["orders"][0]["close_code"], "")
        self.assertEqual(first["date"], "2026-07-20")
        self.assertEqual(first["review_slots"], ["09:00"])
        self.assertEqual(state["counts_by_slot"]["14:00"], 1)
        self.assertEqual(tuple(state["review_times"]), DEFAULT_REVIEW_TIMES)
        self.assertEqual(json.loads(self.path.read_text())["version"], 1)

    def test_two_digit_csv_date_is_preserved(self) -> None:
        preview = FakePreview((
            FakeOrder(
                "789", "25/08/26", "NATAL", "Z3", "TECNICO TRES",
                "08:00 - 10:00", "", "9010",
            ),
        ))

        self.registry.record_preview(
            preview, profile="natal", target="rn", seen_at="2026-08-26T01:00:00",
        )

        state = self.registry.public_state(profile="natal", date="2026-08-25")
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["records"][0]["date"], "2026-08-25")

    def test_registry_can_filter_by_review_slot(self) -> None:
        preview = FakePreview((
            FakeOrder("1", "2026-07-20", "NATAL", "Z1", "UM", "08:00 - 11:00", "", "1"),
            FakeOrder("2", "2026-07-20", "NATAL", "Z2", "DOIS", "15:00 - 18:00", "", "2"),
        ))
        self.registry.record_preview(preview, profile="natal", target="rn")

        state = self.registry.public_state(profile="natal", slot="17:20")

        self.assertEqual(state["count"], 1)
        self.assertEqual(state["records"][0]["contract"], "2")

    def test_agenda_replacement_preserves_complete_toa_records(self) -> None:
        preview = FakePreview((
            FakeOrder(
                "12345", "2026-08-26", "NATAL", "Z1", "TECNICO UM",
                "08:00 - 11:00", "", "9001",
            ),
        ))
        self.registry.record_preview(
            preview, profile="natal", target="rn", source="fotografia.csv",
        )

        first = self.registry.replace_agenda(
            [{
                "contract": "12345",
                "date": "2026-08-26",
                "window": "08:00 - 10:00",
                "window_start": 480,
                "window_end": 600,
                "source_rows": [61],
            }],
            profile="natal", target="natal", date="2026-08-26",
            source="agenda-1.xlsx",
        )
        second = self.registry.replace_agenda(
            [{
                "contract": "67890",
                "date": "2026-08-26",
                "window": "11:00 - 14:00",
                "window_start": 660,
                "window_end": 840,
                "source_rows": [70],
            }],
            profile="natal", target="natal", date="2026-08-26",
            source="agenda-2.xlsx",
        )

        state = self.registry.public_state(profile="natal", date="2026-08-26")
        complete = [item for item in state["records"] if not item.get("agenda_only")]
        agenda = [item for item in state["records"] if item.get("agenda_only")]
        self.assertEqual(first["recorded"], 1)
        self.assertEqual(second["recorded"], 1)
        self.assertEqual([item["contract"] for item in complete], ["12345"])
        self.assertEqual(complete[0]["os_numbers"], ["9001"])
        self.assertEqual([item["contract"] for item in agenda], ["67890"])


if __name__ == "__main__":
    unittest.main()
