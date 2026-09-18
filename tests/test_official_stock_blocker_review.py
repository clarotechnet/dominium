import ast
import copy
import inspect
import unittest

import official_stock_blocker_review
from official_stock_blocker_review import (
    BlockerReviewError,
    build_blocker_review,
)


def raw_material(
    code: str,
    *,
    invid: str,
    quantity: str = "1",
    description: str | None = None,
    unit: str | None = None,
) -> dict:
    value = {
        "kind": "material",
        "activity_id": "194300555",
        "invid": invid,
        "material_code": code,
        "description": description or f"{code}_MATERIAL {code}",
        "quantity": quantity,
    }
    if unit is not None:
        value["unit"] = unit
    return value


def inspection_material(
    code: str,
    *,
    invid: str,
    quantity: str = "1",
    unit: str | None = None,
) -> dict:
    value = {
        "equipment_code": code,
        "used_quantity": quantity,
        "invid": invid,
        "inv_aid": "194300555",
        "point_335": None,
    }
    if unit is not None:
        value["unit"] = unit
    return value


def catalog_material(
    code: str,
    description: str,
    *,
    official_code: str | None = None,
    candidates: list[dict] | None = None,
) -> dict:
    return {
        "toa": {"code": code, "description": f"{code}_{description}"},
        "desktop": {"code": code, "description": description},
        "official": {
            "code_entry": {
                "code": official_code or code,
                "ids": ["100"],
                "descriptions": [description],
                "rows": [2],
            },
            "description": description,
        },
        "official_candidates_by_exact_normalized_description": candidates or [],
        "desktop_candidates_by_exact_normalized_description": [],
        "status": "validado",
    }


def stock_material(
    code: str,
    description: str,
    *,
    status: str,
    quantity: str | None,
    unit: str | None,
) -> dict:
    return {
        "code": code,
        "official_description": description,
        "equipment_id": 500 if quantity is not None else None,
        "installer_id": 328898,
        "stock_id": 276,
        "available_quantity": quantity,
        "unit": unit,
        "profile": "TECHNET NATAL",
        "status": status,
        "read_at": "2026-07-23T16:40:39-03:00",
    }


def fixture(
    *,
    codes: list[str] | None = None,
    states: dict[str, str] | None = None,
) -> tuple[dict, dict, dict, dict]:
    codes = codes or ["22025072", "22056343"]
    states = states or {
        "22025072": "sem saldo",
        "22056343": "ausente",
    }
    descriptions = {
        "22025072": "FITA ISOLANTE 3M 33+",
        "22056343": "MARCADOR CASA PTO NR 1",
        "22064608": "FITA ISOLANTE 3M HIGHLAND 19MM X 20M",
    }
    raw = [
        raw_material(
            code,
            invid=str(index),
            description=f"{code}_{descriptions.get(code, 'MATERIAL')}",
        )
        for index, code in enumerate(codes, 1)
    ]
    inspected = [
        inspection_material(code, invid=str(index))
        for index, code in enumerate(codes, 1)
    ]
    catalog = [
        catalog_material(code, descriptions.get(code, "MATERIAL"))
        for code in codes
    ]
    stock = [
        stock_material(
            code,
            descriptions.get(code, "MATERIAL"),
            status=states[code],
            quantity="0" if states[code] == "sem saldo" else None,
            unit="M" if code == "22025072" else None,
        )
        for code in codes
    ]
    inspection = {
        "contract": "2221170",
        "toa": {"activity_aid": "194300555"},
        "routing_evidence": {
            "effective_material_os": "2646508672",
            "effective_material_capability": "material_capable",
        },
        "inventory": {"materials": inspected},
    }
    toa_capture = {
        "os_list": [
            {
                "os": {
                    "activity": {
                        "aid": "194300555",
                        "contract": "2221170",
                    },
                    "inventory": raw,
                }
            }
        ]
    }
    catalog_report = {
        "contract": "2221170",
        "materials": catalog,
    }
    stock_report = {
        "installer_id": 328898,
        "stock_id": 276,
        "profile": "TECHNET NATAL",
        "read_at": "2026-07-23T16:40:39-03:00",
        "materials": stock,
        "blockers": [
            f"stock_audit_{states[code]}:{code}" for code in codes
        ],
        "warnings": ["unrelated_official_catalog_critical_errors:1"],
        "unrelated_catalog_errors": [
            {
                "type": "duplicate_code_divergent_descriptions",
                "code": "22055857",
            }
        ],
        "payload_generated": False,
    }
    return inspection, toa_capture, catalog_report, stock_report


class OfficialStockBlockerReviewTests(unittest.TestCase):
    def test_exact_required_zero_balance_stays_sem_saldo(self) -> None:
        report = build_blocker_review(*fixture())
        review = report["reviews"][0]

        self.assertEqual(review["code"], "22025072")
        self.assertEqual(review["canonical_state"], "sem_saldo")
        self.assertTrue(review["contract_dependency"]["required"])
        self.assertTrue(review["official_catalog"]["exact_code_confirmed"])
        self.assertTrue(review["decision"]["keep_blocked"])

    def test_exact_required_missing_stock_stays_ausente(self) -> None:
        report = build_blocker_review(*fixture())
        review = report["reviews"][1]

        self.assertEqual(review["code"], "22056343")
        self.assertEqual(review["canonical_state"], "ausente")
        self.assertFalse(review["matching"]["matching_incorreto"])
        self.assertTrue(review["decision"]["keep_blocked"])

    def test_blocker_absent_from_both_contract_sources_is_matching_incorreto(
        self,
    ) -> None:
        inspection, toa, catalog, stock = fixture(codes=["22025072"])
        inspection["inventory"]["materials"] = []
        toa["os_list"][0]["os"]["inventory"] = []

        report = build_blocker_review(inspection, toa, catalog, stock)

        self.assertEqual(
            report["reviews"][0]["canonical_state"],
            "matching_incorreto",
        )
        self.assertTrue(report["reviews"][0]["decision"]["keep_blocked"])
        self.assertFalse(
            report["reviews"][0]["decision"]["blocker_can_be_removed"]
        )

    def test_presence_mismatch_between_sources_is_conflito(self) -> None:
        inspection, toa, catalog, stock = fixture(codes=["22025072"])
        inspection["inventory"]["materials"] = []

        report = build_blocker_review(inspection, toa, catalog, stock)

        review = report["reviews"][0]
        self.assertEqual(review["canonical_state"], "conflito")
        self.assertIn(
            "material_presence_mismatch",
            review["matching"]["origin_conflicts"],
        )
        self.assertTrue(review["decision"]["keep_blocked"])

    def test_catalog_code_conflict_stays_blocked_as_conflito(self) -> None:
        inspection, toa, catalog, stock = fixture(codes=["22025072"])
        catalog["materials"][0]["official"]["code_entry"]["code"] = "999"

        report = build_blocker_review(inspection, toa, catalog, stock)

        self.assertEqual(report["reviews"][0]["canonical_state"], "conflito")
        self.assertTrue(report["reviews"][0]["decision"]["keep_blocked"])

    def test_unit_conflict_is_preserved_separately(self) -> None:
        inspection, toa, catalog, stock = fixture(codes=["22025072"])
        toa["os_list"][0]["os"]["inventory"][0]["unit"] = "UN"
        inspection["inventory"]["materials"][0]["unit"] = "UN"

        report = build_blocker_review(inspection, toa, catalog, stock)
        review = report["reviews"][0]

        self.assertEqual(review["unit_evidence"]["status"], "conflito")
        self.assertEqual(review["canonical_state"], "conflito")

    def test_missing_origin_unit_is_not_invented_or_called_divergent(self) -> None:
        report = build_blocker_review(*fixture())
        unit = report["reviews"][0]["unit_evidence"]

        self.assertEqual(unit["stock_unit"], "M")
        self.assertIsNone(unit["toa_unit"])
        self.assertFalse(unit["divergent"])
        self.assertEqual(unit["status"], "nao_comparavel")

    def test_absent_stock_unit_remains_null(self) -> None:
        report = build_blocker_review(*fixture())
        unit = report["reviews"][1]["unit_evidence"]

        self.assertIsNone(unit["stock_unit"])
        self.assertEqual(unit["status"], "nao_comparavel")

    def test_candidates_never_authorize_alias_or_substitution(self) -> None:
        inspection, toa, catalog, stock = fixture(codes=["22025072"])
        catalog["materials"][0][
            "desktop_candidates_by_exact_normalized_description"
        ] = [
            {
                "code": "22064608",
                "descriptions": ["FITA ISOLANTE 3M HIGHLAND 19MM X 20M"],
            }
        ]
        stock["materials"].append(
            stock_material(
                "22064608",
                "FITA ISOLANTE 3M HIGHLAND 19MM X 20M",
                status="encontrado",
                quantity="6",
                unit="M",
            )
        )

        report = build_blocker_review(
            inspection,
            toa,
            catalog,
            stock,
            contextual_comparisons={"22025072": ("22064608",)},
        )
        candidates = report["reviews"][0]["candidates"]

        self.assertEqual(candidates[0]["code"], "22064608")
        self.assertEqual(candidates[0]["available_quantity"], "6")
        self.assertFalse(candidates[0]["equivalence_authorized"])
        self.assertEqual(report["conclusions"]["aliases_created"], [])

    def test_unrelated_catalog_conflict_remains_warning_only(self) -> None:
        report = build_blocker_review(*fixture())

        self.assertIn(
            "unrelated_official_catalog_critical_errors:1",
            report["warnings"],
        )
        self.assertEqual(
            report["unrelated_catalog_errors"][0]["code"],
            "22055857",
        )

    def test_warning_state_is_not_folded_into_conflict(self) -> None:
        values = fixture(
            codes=["22025072"],
            states={"22025072": "encontrado"},
        )

        report = build_blocker_review(*values)

        self.assertEqual(report["reviews"][0]["canonical_state"], "warning")
        self.assertTrue(report["reviews"][0]["decision"]["keep_blocked"])

    def test_all_real_blocker_states_are_preserved(self) -> None:
        inspection, toa, catalog, stock = fixture(
            codes=["22025072", "22056343", "22056341", "22056344"],
            states={
                "22025072": "sem saldo",
                "22056343": "ausente",
                "22056341": "ausente",
                "22056344": "ausente",
            },
        )

        report = build_blocker_review(inspection, toa, catalog, stock)

        self.assertEqual(report["states_present"], ["ausente", "sem_saldo"])
        self.assertEqual(len(report["blockers_remaining"]), 4)
        self.assertEqual(report["blockers_removable"], [])

    def test_inputs_are_not_modified(self) -> None:
        values = fixture()
        originals = copy.deepcopy(values)

        build_blocker_review(*values)

        self.assertEqual(values, originals)

    def test_wrong_contract_or_installer_is_rejected(self) -> None:
        inspection, toa, catalog, stock = fixture()
        stock["installer_id"] = 1
        with self.assertRaisesRegex(BlockerReviewError, "outro instalador"):
            build_blocker_review(inspection, toa, catalog, stock)

    def test_import_has_no_network_or_operational_side_effect(self) -> None:
        source = inspect.getsource(official_stock_blocker_review)
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }

        self.assertTrue(
            {
                "requests",
                "urllib",
                "http.client",
                "imperium_api",
                "datasnap_client",
            }.isdisjoint(imported_modules)
        )
        self.assertNotIn("ApplyUpdates", source)
        self.assertNotIn("material_matching", imported_modules)


if __name__ == "__main__":
    unittest.main()
