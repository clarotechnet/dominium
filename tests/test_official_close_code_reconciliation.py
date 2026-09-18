import ast
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from openpyxl import Workbook

from official_close_code_reconciliation import (
    CloseCodeReconciliationError,
    build_close_code_reconciliation,
    load_registered_close_codes_xlsx,
    normalize_description,
)


def pdf_entry(
    code: str,
    description: str,
    *,
    category: str = "TESTE",
) -> dict:
    return {
        "code": code,
        "status": "valid",
        "category": category,
        "description": description,
        "usage_rule": "Regra",
        "customer_communication": None,
        "source_pages": [1],
        "occurrences": 1,
    }


def pdf_catalog(*entries: dict) -> dict:
    return {
        "source": {
            "file_name": "tabela.pdf",
            "sha256": "a" * 64,
            "page_count": 1,
        },
        "occurrence_count": len(entries),
        "unique_code_count": len(entries),
        "entries": list(entries),
        "warnings": [],
    }


def registered(*rows: dict) -> dict:
    return {
        "source": {
            "file_name": "cadastrados.xlsx",
            "sha256": "b" * 64,
            "sheet_name": "Planilha1",
            "status_legend": "2 = CONCLUIDA",
        },
        "rows": list(rows),
    }


def xlsx_row(
    code: str,
    description: str,
    *,
    row: int = 3,
    record_id: str = "1",
) -> dict:
    return {
        "row": row,
        "id": record_id,
        "code": code,
        "description": description,
        "status": 2,
        "active": "S",
    }


class CloseCodeReconciliationTests(unittest.TestCase):
    def test_normalization_ignores_accents_and_punctuation(self) -> None:
        self.assertEqual(
            normalize_description("Instalação SC/APC"),
            normalize_description("INSTALACAO SC APC"),
        )

    def test_reconciliation_separates_missing_extra_and_mismatch(self) -> None:
        report = build_close_code_reconciliation(
            pdf_catalog(
                pdf_entry("100", "Mesmo código"),
                pdf_entry("120", "Novo código"),
                pdf_entry("409", "Instalação efetuada"),
            ),
            registered(
                xlsx_row("100", "MESMO CODIGO"),
                xlsx_row("409", "INSTALAÇÃO CONCLUIDA", row=4),
                xlsx_row("706", "CHIP", row=5),
            ),
        )

        self.assertEqual(
            [item["code"] for item in report["missing_in_imperium"]],
            ["120"],
        )
        self.assertEqual(
            [item["code"] for item in report["registered_only"]],
            ["706"],
        )
        self.assertEqual(
            [item["code"] for item in report["description_mismatches"]],
            ["409"],
        )
        self.assertEqual(report["summary"]["description_match_count"], 1)

    def test_conflicting_registered_duplicate_is_reported(self) -> None:
        report = build_close_code_reconciliation(
            pdf_catalog(pdf_entry("1", "Teste")),
            registered(
                xlsx_row("1", "TESTE"),
                xlsx_row(
                    "1",
                    "REVISITA CANCELADA",
                    row=4,
                    record_id="2",
                ),
            ),
        )

        self.assertEqual(
            report["registered_duplicates"][0]["status"],
            "duplicate_conflicting",
        )

    def test_xlsx_loader_finds_header_after_legend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "codes.xlsx")
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(["2 = CONCLUIDA", None, None, None, None])
            worksheet.append(list(("Id", "Código", "Descricao", "Status", "Ativo")))
            worksheet.append([1, 104, "FALTA DE MATERIAL", 4, "S"])
            workbook.save(path)

            loaded = load_registered_close_codes_xlsx(path)

        self.assertEqual(loaded["rows"][0]["code"], "104")
        self.assertEqual(loaded["rows"][0]["status"], 4)
        self.assertEqual(loaded["source"]["status_legend"], "2 = CONCLUIDA")

    def test_xlsx_loader_rejects_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "codes.xlsx")
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(["Id", "Código", "Descricao"])
            worksheet.append([1, 104, "FALTA DE MATERIAL"])
            workbook.save(path)

            with self.assertRaisesRegex(
                CloseCodeReconciliationError,
                "Colunas invalidas",
            ):
                load_registered_close_codes_xlsx(path)

    def test_inputs_are_not_modified(self) -> None:
        pdf = pdf_catalog(pdf_entry("104", "Falta de material"))
        xlsx = registered(xlsx_row("104", "FALTA DE MATERIAL"))
        pdf_before = deepcopy(pdf)
        xlsx_before = deepcopy(xlsx)

        build_close_code_reconciliation(pdf, xlsx)

        self.assertEqual(pdf, pdf_before)
        self.assertEqual(xlsx, xlsx_before)

    def test_module_has_no_network_or_operational_import(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "official_close_code_reconciliation.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = {
            "requests",
            "urllib",
            "datasnap_client",
            "imperium_api",
            "imperium_http_api",
            "official_close_sender",
        }
        self.assertTrue(forbidden.isdisjoint(imported))

    def test_report_never_generates_registration_commands(self) -> None:
        report = build_close_code_reconciliation(
            pdf_catalog(pdf_entry("120", "Novo")),
            registered(),
        )
        serialized = json.dumps(report, sort_keys=True).casefold()

        self.assertFalse(report["registration_commands_generated"])
        self.assertFalse(report["registration_executed"])
        self.assertNotIn("ordemservico", serialized)


if __name__ == "__main__":
    unittest.main()
