import csv
import io
import unittest

from toa_agenda import parse_agenda


class TOAAgendaTests(unittest.TestCase):
    @staticmethod
    def csv_bytes(rows: list[list[object]]) -> bytes:
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=";")
        writer.writerows(rows)
        return stream.getvalue().encode("utf-8")

    def test_blank_contracts_are_ignored_without_fixed_start_row(self) -> None:
        header = [""] * 23
        header[1] = "Data"
        header[9] = "Intervalo de Tempo"
        header[22] = "Contrato"
        blank = [""] * 23
        blank[1] = "26/08/26"
        blank[9] = "08:00 - 09:00"
        valid = [""] * 23
        valid[1] = "26/08/26"
        valid[9] = "08:00 - 11:00"
        valid[22] = "4267711"

        result = parse_agenda(
            self.csv_bytes([header, blank, valid]),
            "Atividades-NTL-DMV_26_08_26.csv",
            fallback_date="2026-08-26",
        )

        self.assertEqual(result["stats"]["blank_or_invalid_contract"], 1)
        self.assertEqual(result["contracts"][0]["contract"], "4267711")
        self.assertEqual(result["contracts"][0]["window"], "08:00 - 11:00")

    def test_contracts_are_deduplicated_and_sorted_by_window_end(self) -> None:
        header = [""] * 23
        header[1] = "Data"
        header[9] = "Intervalo de Tempo"
        header[22] = "Contrato"

        def row(contract: str, window: str) -> list[str]:
            values = [""] * 23
            values[1] = "26/08/26"
            values[9] = window
            values[22] = contract
            return values

        result = parse_agenda(
            self.csv_bytes([
                header,
                row("30003", "08:00 - 12:00"),
                row("30001", "08:00 - 10:00"),
                row("30002", "08:00 - 11:00"),
                row("30003", "08:00 - 09:00"),
            ]),
            "agenda.csv",
            fallback_date="2026-08-26",
        )

        self.assertEqual(
            [item["contract"] for item in result["contracts"]],
            ["30003", "30001", "30002"],
        )
        self.assertEqual(result["contracts"][0]["window"], "08:00 - 09:00")
        self.assertEqual(result["stats"]["duplicate_contract_rows"], 1)


if __name__ == "__main__":
    unittest.main()
