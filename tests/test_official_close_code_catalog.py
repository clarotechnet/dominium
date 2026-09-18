import ast
import json
import unittest
from pathlib import Path

from official_close_code_catalog import (
    CloseCodeCatalogError,
    build_close_code_catalog,
)


def row(
    code: str = "104",
    *,
    description: str = "Falta de Material",
    usage_rule: str = (
        "Quando o tecnico vai ate a residencia do cliente e nao consegue "
        "executar o servico devido a falta de material ou equipamento."
    ),
    communication: str | None = "Comunique o cliente.",
    page: int = 4,
) -> dict:
    return {
        "code": code,
        "category": "IMPRODUTIVOS",
        "description": description,
        "usage_rule": usage_rule,
        "customer_communication": communication,
        "page": page,
    }


def build(rows: list[dict]) -> dict:
    return build_close_code_catalog(
        rows,
        source_file_name="Tabela_codigo_baixa0711.pdf",
        source_sha256="a" * 64,
        page_count=44,
    )


class OfficialCloseCodeCatalogTests(unittest.TestCase):
    def test_valid_entry_preserves_all_operational_fields(self) -> None:
        catalog = build([row()])
        entry = catalog["entries"][0]

        self.assertEqual(entry["code"], "104")
        self.assertEqual(entry["category"], "IMPRODUTIVOS")
        self.assertEqual(entry["description"], "Falta de Material")
        self.assertTrue(entry["usage_rule"])
        self.assertEqual(entry["customer_communication"], "Comunique o cliente.")
        self.assertEqual(entry["source_pages"], [4])

    def test_identical_duplicate_is_warning_without_correction(self) -> None:
        catalog = build([row(), row()])

        self.assertEqual(catalog["unique_code_count"], 1)
        self.assertEqual(catalog["entries"][0]["status"], "valid")
        self.assertEqual(
            catalog["warnings"][0]["type"],
            "duplicate_code_identical",
        )
        self.assertFalse(
            catalog["warnings"][0]["automatic_correction"]
        )

    def test_inconsistent_duplicate_keeps_variants_and_no_selection(self) -> None:
        catalog = build(
            [
                row(),
                row(description="Outra descricao"),
            ]
        )
        entry = catalog["entries"][0]

        self.assertEqual(entry["status"], "inconsistent")
        self.assertIsNone(entry["description"])
        self.assertEqual(len(entry["variants"]), 2)
        self.assertEqual(
            catalog["warnings"][0]["type"],
            "duplicate_code_inconsistent",
        )

    def test_missing_required_field_is_blocked(self) -> None:
        with self.assertRaisesRegex(
            CloseCodeCatalogError,
            "Campos obrigatorios ausentes",
        ):
            build([row(usage_rule="")])

    def test_catalog_never_creates_alias_or_payload(self) -> None:
        catalog = build([row()])
        serialized = json.dumps(catalog, sort_keys=True).casefold()

        self.assertEqual(catalog["aliases_created"], [])
        self.assertEqual(catalog["equivalences_authorized"], [])
        self.assertFalse(catalog["payload_generated"])
        self.assertNotIn("ordemservico", serialized)

    def test_import_has_no_network_or_operational_client(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "official_close_code_catalog.py"
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


if __name__ == "__main__":
    unittest.main()
