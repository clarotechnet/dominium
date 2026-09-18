import datetime as dt
import unittest

from bulk_orders import build_bulk_preview, normalize_contracts


class BulkOrdersTests(unittest.TestCase):
    def test_normalizes_separators_and_removes_duplicates(self) -> None:
        self.assertEqual(
            normalize_contracts("3185231\n4228619, 3185231;2615003"),
            ("3185231", "4228619", "2615003"),
        )

    def test_rejects_invalid_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "Contrato invalido"):
            normalize_contracts("3185231\nABC")

    def test_builds_the_manual_order_pattern_for_natal(self) -> None:
        preview = build_bulk_preview(
            ["3185231", "4228619"],
            "ALLAN JAYVERSON DESC",
            "natal",
            today=dt.date(2026, 7, 17),
        )

        self.assertEqual(preview.source_rows, 2)
        first = preview.orders[0]
        self.assertEqual(first.contract, "3185231")
        self.assertEqual(first.os_number, "3185231 3185231")
        self.assertEqual(first.os_type, "RETIRADA FORA TOA")
        self.assertEqual(first.technician, "ALLAN JAYVERSON DESC")
        self.assertEqual(first.date, "17/07/2026")
        self.assertEqual((first.city, first.state), ("NATAL", "RN"))
        self.assertEqual(first.activity_status, "AGENDADA")
        self.assertEqual(first.time_window, "IMEDIATA")

    def test_uses_the_profile_location(self) -> None:
        preview = build_bulk_preview(
            "3619320",
            "TECNICO FTZ",
            "fortaleza",
            today=dt.date(2026, 7, 17),
        )
        order = preview.orders[0]
        self.assertEqual((order.city, order.state, order.zip_code), (
            "FORTALEZA", "CE", "60000000"
        ))

    def test_accepts_a_manual_service_name(self) -> None:
        preview = build_bulk_preview(
            "3619320",
            "TECNICO NATAL",
            "natal",
            service="correcao estoque",
            today=dt.date(2026, 7, 17),
        )
        self.assertEqual(preview.orders[0].os_type, "CORRECAO ESTOQUE")


if __name__ == "__main__":
    unittest.main()
