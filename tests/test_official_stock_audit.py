import copy
import ast
import inspect
import unittest

import official_stock_audit
from official_material_catalog import CatalogRecord, OfficialMaterialCatalog
from official_stock_audit import (
    CAPTURE_SCHEMA,
    DEFAULT_CODES,
    StockAuditError,
    build_stock_audit_report,
    collect_read_capture,
)


CATALOG_ROWS = {
    "22061736": "CABO DROP 1FO LOW F FIG8 LOW CINZA",
    "22069613": "CONECTOR FO CAMPO FAST SC APC",
    "22025072": "FITA ISOLANTE 3M 33+",
    "22064608": "FITA ISOLANTE 3M HIGHLAND 19MM X 20M",
    "22056332": "FITA AUTO-FUSAO 23LB 19X10MM 3M NET",
    "22056343": "MARCADOR CASA PTO NR 1",
    "22056341": "MARCADOR CASA PTO NR 7",
    "22056344": "MARCADOR CASA PTO NR 2",
    "22057659": "ESTICADOR CUNHA P/DROP FO SDA1 DPR",
    "22065719": "MARCADOR CASA PRETO NR 1",
    "22065725": "MARCADOR CASA PRETO NR 7",
    "22065720": "MARCADOR CASA PRETO NR 2",
}


def make_catalog(*, unrelated_conflict: bool = False) -> OfficialMaterialCatalog:
    records = [
        CatalogRecord(str(index), code, description, index + 1)
        for index, (code, description) in enumerate(CATALOG_ROWS.items(), 1)
    ]
    if unrelated_conflict:
        records.extend(
            [
                CatalogRecord("9001", "22055857", "MATERIAL UM", 9001),
                CatalogRecord("9002", "22055857", "MATERIAL DOIS", 9002),
            ]
        )
    return OfficialMaterialCatalog(
        source_name="catalog.xlsx",
        source_sha256="a" * 64,
        imported_at="2026-07-23T10:00:00-03:00",
        records=records,
    )


def make_capture(items: list[dict]) -> dict:
    technician = {
        "stock_id": 77,
        "stock_name": "DENIS NUNES",
        "installer_id": 328898,
        "technician_name": "DENIS NUNES",
    }
    return {
        "schema": CAPTURE_SCHEMA,
        "profile": "TECHNET NATAL",
        "installer_id": 328898,
        "read_at": "2026-07-23T10:30:00-03:00",
        "technicians": [technician],
        "stock": {
            "ok": True,
            "technician": technician,
            "items": items,
        },
    }


def stock_item(
    code: str,
    *,
    quantity: str = "5",
    equipment: str | None = None,
    equipment_id: int = 100,
    unit: str = "UN",
) -> dict:
    return {
        "equipment_id": equipment_id,
        "code": code,
        "equipment": equipment or CATALOG_ROWS[code],
        "quantity": quantity,
        "unit": unit,
    }


class FakeReadAPI:
    def __init__(self, technician: dict, stock: dict) -> None:
        self.technician = technician
        self.stock = stock
        self.calls = []

    def list_stock_technicians(self) -> list[dict]:
        self.calls.append("DspConEst1")
        return [copy.deepcopy(self.technician)]

    def technician_stock(self, stock_id: int) -> dict:
        self.calls.append(("DspListaEquiEstoque", stock_id))
        return copy.deepcopy(self.stock)


class OfficialStockAuditTests(unittest.TestCase):
    def test_exact_installer_and_stock_are_required(self) -> None:
        item = stock_item("22069613")
        capture = make_capture([item])
        capture["technicians"][0]["installer_id"] = 1

        with self.assertRaisesRegex(
            StockAuditError,
            "exatamente um estoque",
        ):
            build_stock_audit_report(
                make_catalog(),
                capture,
                requested_codes=["22069613"],
            )

    def test_positive_zero_absent_and_divergent_statuses(self) -> None:
        items = [
            stock_item("22069613", quantity="14", equipment_id=10),
            stock_item("22025072", quantity="0", equipment_id=11),
            stock_item(
                "22064608",
                quantity="2",
                equipment="DESCRICAO DIFERENTE",
                equipment_id=12,
                unit="M",
            ),
        ]

        report = build_stock_audit_report(
            make_catalog(),
            make_capture(items),
            requested_codes=[
                "22069613",
                "22025072",
                "22061736",
                "22064608",
            ],
        )
        statuses = {
            row["code"]: row["status"] for row in report["materials"]
        }

        self.assertEqual(statuses["22069613"], "encontrado")
        self.assertEqual(statuses["22025072"], "sem saldo")
        self.assertEqual(statuses["22061736"], "ausente")
        self.assertEqual(statuses["22064608"], "divergente")

    def test_report_preserves_required_read_evidence(self) -> None:
        report = build_stock_audit_report(
            make_catalog(),
            make_capture(
                [
                    stock_item(
                        "22061736",
                        quantity="39.5",
                        equipment_id=501,
                        unit="M",
                    )
                ]
            ),
            requested_codes=["22061736"],
        )
        row = report["materials"][0]

        self.assertEqual(row["equipment_id"], 501)
        self.assertEqual(row["installer_id"], 328898)
        self.assertEqual(row["stock_id"], 77)
        self.assertEqual(row["available_quantity"], "39.5")
        self.assertEqual(row["unit"], "M")
        self.assertEqual(row["profile"], "TECHNET NATAL")
        self.assertIn("DspListaEquiEstoque", row["source"])
        self.assertEqual(row["read_at"], "2026-07-23T10:30:00-03:00")
        self.assertFalse(report["payload_generated"])

    def test_22025072_and_22064608_are_never_aliased(self) -> None:
        report = build_stock_audit_report(
            make_catalog(),
            make_capture(
                [
                    stock_item("22064608", equipment_id=601, unit="M"),
                ]
            ),
            requested_codes=["22025072", "22064608"],
        )
        by_code = {row["code"]: row for row in report["materials"]}

        self.assertEqual(by_code["22025072"]["status"], "ausente")
        self.assertEqual(by_code["22064608"]["status"], "encontrado")
        self.assertEqual(report["aliases_created"], [])

    def test_unrelated_catalog_conflict_is_warning_not_blocker(self) -> None:
        report = build_stock_audit_report(
            make_catalog(unrelated_conflict=True),
            make_capture([stock_item("22069613")]),
            requested_codes=["22069613"],
        )

        self.assertEqual(report["blockers"], [])
        self.assertIn(
            "unrelated_official_catalog_critical_errors:1",
            report["warnings"],
        )

    def test_duplicate_stock_rows_for_code_are_divergent(self) -> None:
        report = build_stock_audit_report(
            make_catalog(),
            make_capture(
                [
                    stock_item("22069613", equipment_id=1),
                    stock_item("22069613", equipment_id=2),
                ]
            ),
            requested_codes=["22069613"],
        )

        self.assertEqual(report["materials"][0]["status"], "divergente")

    def test_capture_uses_only_exact_installer_id_then_stock_id(self) -> None:
        technician = {
            "stock_id": 77,
            "stock_name": "DENIS NUNES",
            "installer_id": 328898,
            "technician_name": "DENIS NUNES",
        }
        api = FakeReadAPI(
            technician,
            {
                "ok": True,
                "technician": technician,
                "items": [],
            },
        )

        capture = collect_read_capture(
            api,
            installer_id=328898,
            profile="TECHNET NATAL",
            read_at="2026-07-23T11:00:00-03:00",
        )

        self.assertEqual(
            api.calls,
            ["DspConEst1", ("DspListaEquiEstoque", 77)],
        )
        self.assertEqual(capture["stock"]["technician"]["stock_id"], 77)

    def test_capture_never_falls_back_to_technician_name(self) -> None:
        technician = {
            "stock_id": 77,
            "stock_name": "DENIS NUNES",
            "installer_id": 999,
            "technician_name": "DENIS NUNES",
        }
        api = FakeReadAPI(technician, {})

        with self.assertRaisesRegex(
            StockAuditError,
            "exatamente um estoque",
        ):
            collect_read_capture(
                api,
                installer_id=328898,
                profile="TECHNET NATAL",
            )
        self.assertEqual(api.calls, ["DspConEst1"])

    def test_input_capture_is_not_modified(self) -> None:
        capture = make_capture([stock_item("22069613")])
        original = copy.deepcopy(capture)

        build_stock_audit_report(
            make_catalog(),
            capture,
            requested_codes=["22069613"],
        )

        self.assertEqual(capture, original)

    def test_default_code_set_is_exact(self) -> None:
        self.assertEqual(
            DEFAULT_CODES,
            (
                "22061736",
                "22069613",
                "22025072",
                "22064608",
                "22056332",
                "22056343",
                "22056341",
                "22056344",
                "22057659",
                "22065719",
                "22065725",
                "22065720",
            ),
        )

    def test_import_has_no_network_or_write_side_effect(self) -> None:
        source = inspect.getsource(official_stock_audit)
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        call_names = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }

        self.assertNotIn("ApplyUpdates", source)
        self.assertTrue(
            {"requests", "urllib", "http.client"}.isdisjoint(
                imported_modules
            )
        )
        self.assertTrue(
            {"post", "request", "send", "execute"}.isdisjoint(call_names)
        )
        self.assertFalse(hasattr(official_stock_audit, "payload"))


if __name__ == "__main__":
    unittest.main()
