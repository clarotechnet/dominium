import re
import unittest

from stock_pdf import build_stock_pdf, safe_pdf_filename


class StockPDFTests(unittest.TestCase):
    @staticmethod
    def stock(name: str = "Técnico Ágil") -> dict:
        return {
            "technician": {
                "technician_name": name,
                "stock_name": f"ESTOQUE {name}",
                "stock_id": 5,
            },
            "summary": {
                "positive_item_count": 1,
                "quantity_total": "2",
                "serial_count": 1,
                "group_count": 1,
            },
            "items": [
                {
                    "group": "DECODER",
                    "code": "EQ-POSITIVO",
                    "equipment": "Decoder de teste",
                    "brand": "DIVERSOS",
                    "quantity": "2",
                    "quantity_label": "2 UN",
                    "serials": [{"serial": "123456789012", "smart": ""}],
                },
                {
                    "group": "MODEM",
                    "code": "EQ-ZERADO",
                    "equipment": "Modem sem saldo",
                    "brand": "DIVERSOS",
                    "quantity": "0",
                    "quantity_label": "0 UN",
                    "serials": [],
                },
            ],
        }

    def test_generates_valid_pdf_with_one_page_per_technician(self) -> None:
        data = build_stock_pdf(
            [self.stock("Técnico 1"), self.stock("Técnico 2")],
            company="NATAL / PARNAMIRIM",
        )
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertEqual(len(re.findall(rb"/Type /Page ", data)), 2)

    def test_zero_items_are_optional(self) -> None:
        without_zero = build_stock_pdf([self.stock()], company="NATAL")
        with_zero = build_stock_pdf(
            [self.stock()], company="NATAL", include_zero=True
        )
        self.assertNotIn(b"EQ-ZERADO", without_zero)
        self.assertIn(b"EQ-ZERADO", with_zero)

    def test_filename_is_safe_for_download(self) -> None:
        self.assertEqual(
            safe_pdf_filename("Estoque - João / Técnico"),
            "Estoque-Joao-Tecnico.pdf",
        )


if __name__ == "__main__":
    unittest.main()
