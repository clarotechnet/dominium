"""Private report store regression: never involve live log or production actions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integrations.desc_reports.operator_reports import OperatorReports, ReportError


class ReportsTest(unittest.TestCase):
    def test_durable_report_and_redacted_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "operator-reports.jsonl"
            store = OperatorReports(file)
            payload = {"kind": "erro", "severity": "alta",
                       "title": "Erro ao abrir foto", "detail": "O navegador retornou 502; password=abcde12345 ao carregar",
                       "area": "desconexao", "contract": "1234567",
                       "diagnostics": "authorization:Bearer abcxyz"}
            item = store.add(payload, "Controller Test")
            self.assertTrue(file.is_file())
            self.assertEqual(item["status"], "recebido")
            listed = OperatorReports(file).list()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], item["id"])
            self.assertNotIn("abcde12345", str(listed))
            self.assertNotIn("abcxyz", str(listed))

    def test_validation_cannot_write_untrusted_paths_or_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OperatorReports(Path(tmp) / "reports.jsonl")
            base = {"kind": "erro", "severity": "media",
                    "title": "Teste do relatório", "detail": "Ocorreu um erro com contexto suficiente"}
            for invalid in (
                {**base, "kind": "exe"},
                {**base, "contract": "../etc"},
                {**base, "detail": "curto"},
                {**base, "area": "etc", "title": ""},
                {**base, "extra": "A" * 15000},
            ):
                with self.subTest(invalid=invalid), self.assertRaises(ReportError):
                    store.add(invalid, "Controller Test")
            self.assertEqual(store.list(), [])


if __name__ == "__main__":
    unittest.main()
