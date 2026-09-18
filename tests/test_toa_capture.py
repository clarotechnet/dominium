import ast
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from toa_capture import (
    CaptureSchemaError,
    TOACaptureLot,
    main,
    parse_contracts,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "references" / "techcap-v5.6"
FIXTURE_PATH = REFERENCE_ROOT / "techcap-automation-fixtures.json"
REAL_LOT_PATH = (
    REFERENCE_ROOT
    / "technet-toa-lote-526-os-clarobrasil.etadirect.com-2026-07-20T03-21-34-811Z.json"
)


def fixture_cases() -> list[dict]:
    if not FIXTURE_PATH.is_file():
        raise unittest.SkipTest("Fixture TECHCAP v5.6 nao disponivel neste checkout")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


def entry_from_case(case: dict) -> dict:
    inventory = [
        *copy.deepcopy(case.get("installed_equipment", [])),
        *copy.deepcopy(case.get("removed_equipment", [])),
        *copy.deepcopy(case.get("customer_equipment", [])),
        *copy.deepcopy(case.get("materials_misc", [])),
    ]
    expected = case["expected_decision"]
    if expected in {"candidate_after_validation", "blocked_manual_review"}:
        category = "produtiva"
    elif expected == "no_inventory_movement":
        category = "improdutiva"
    else:
        category = "sem-codigo"
    codes = []
    for task in case.get("tasks", []):
        code = str(task.get("close_code", "")).strip()
        if code and code not in codes:
            codes.append(code)
    activity = {
        "aid": case["aid"],
        "contract": case["contract"],
        "city": case.get("city", ""),
        "completion_summary": case.get("completion_summary", ""),
        **copy.deepcopy(case.get("activity", {})),
    }
    return {
        "aid": case["aid"],
        "contract": case["contract"],
        "classification": {"category": category, "codes": codes},
        "automation": {"decision": expected, "reasons": []},
        "history": [],
        "os": {
            "route": copy.deepcopy(case.get("route", {})),
            "activity": activity,
            "responsibility": copy.deepcopy(case.get("responsibility", {})),
            "tasks": copy.deepcopy(case.get("tasks", [])),
            "inventory": inventory,
            "equipment": [item for item in inventory if item.get("kind") == "equipment"],
            "materials": [item for item in inventory if item.get("kind") == "material"],
            "forms": [],
        },
    }


def lot_payload(entries: list[dict]) -> dict:
    return {
        "metadata": {
            "version": "5.6-queue",
            "source": "TECHCAP V5.6 fluxo OS para OS",
            "count": len(entries),
            "rejectionCount": 0,
        },
        "summary": {},
        "rejections": [],
        "os_list": entries,
    }


class TOACaptureFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = fixture_cases()

    def test_all_six_approved_cases_keep_the_expected_decision(self) -> None:
        lot = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case) for case in self.cases])
        )

        self.assertEqual(len(lot.orders), 6)
        for case in self.cases:
            with self.subTest(case=case["case_type"]):
                order = lot.find_aid(case["aid"])
                self.assertIsNotNone(order)
                expected = (
                    "manual_review"
                    if case["case_type"] == "desconexao_produtiva_bloqueada"
                    else case["expected_decision"]
                )
                self.assertEqual(order.decision, expected)
                self.assertTrue(order.dry_run_only)

    def test_productive_installation_separates_equipment_and_materials(self) -> None:
        case = self.cases[0]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual(order.operational_classification, "produtiva")
        self.assertEqual(len(order.installed_equipment), 2)
        self.assertEqual(len(order.removed_equipment), 0)
        self.assertEqual(len(order.materials), 7)
        self.assertEqual(order.pools, ["install"])
        self.assertEqual(order.decision, "candidate_after_validation")

    def test_swap_separates_install_deinstall_and_customer(self) -> None:
        case = self.cases[1]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual(len(order.installed_equipment), 1)
        self.assertEqual(len(order.removed_equipment), 1)
        self.assertEqual(len(order.customer_equipment), 1)
        self.assertEqual(order.pools, ["install", "deinstall", "customer"])

    def test_material_quantities_are_preserved_exactly(self) -> None:
        case = self.cases[2]
        expected = [item["quantity"] for item in case["materials_misc"]]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual([item["quantity"] for item in order.materials], expected)
        self.assertIn("34", expected)
        self.assertEqual(order.decision, "candidate_after_validation")

    def test_improductive_case_never_moves_inventory(self) -> None:
        case = self.cases[3]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual(order.operational_classification, "improdutiva")
        self.assertFalse(order.installed_equipment)
        self.assertFalse(order.removed_equipment)
        self.assertFalse(order.materials)
        self.assertEqual(order.decision, "no_inventory_movement")

    def test_productive_disconnection_is_not_blocked_only_by_its_type(self) -> None:
        case = self.cases[4]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual(order.operational_classification, "produtiva")
        self.assertEqual(order.close_codes, ["430"])
        self.assertEqual(order.decision, "manual_review")
        self.assertIn(
            "disconnection_policy_allows_validation", order.decision_reasons
        )
        self.assertIn("route_not_confirmed", order.decision_reasons)
        self.assertNotIn("disconnection_automation_blocked", order.decision_reasons)

    def test_incomplete_case_requires_manual_review(self) -> None:
        case = self.cases[5]
        order = TOACaptureLot.from_dict(
            lot_payload([entry_from_case(case)])
        ).orders[0]

        self.assertEqual(order.decision, "manual_review")
        self.assertIn("activity_work_type_missing", order.validation_errors)
        self.assertIn("activity_not_complete", order.validation_errors)
        self.assertIn("close_code_missing", order.decision_reasons)


class TOACaptureConflictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = entry_from_case(fixture_cases()[0])

    def normalize(self, entry: dict):
        return TOACaptureLot.from_dict(lot_payload([entry])).orders[0]

    def test_aid_conflict_forces_manual_review(self) -> None:
        entry = copy.deepcopy(self.entry)
        entry["os"]["activity"]["aid"] = "OTHER-AID"

        order = self.normalize(entry)

        self.assertIn("activity_aid_conflict", order.validation_errors)
        self.assertEqual(order.decision, "manual_review")

    def test_contract_conflict_forces_manual_review(self) -> None:
        entry = copy.deepcopy(self.entry)
        entry["os"]["activity"]["contract"] = "9999999"

        order = self.normalize(entry)

        self.assertIn("activity_contract_conflict", order.validation_errors)
        self.assertEqual(order.decision, "manual_review")

    def test_foreign_inventory_is_rejected_and_not_normalized(self) -> None:
        entry = copy.deepcopy(self.entry)
        entry["os"]["inventory"][0]["activity_id"] = "OTHER-AID"
        original_count = len(entry["os"]["inventory"])

        order = self.normalize(entry)

        self.assertIn("inventory_activity_id_conflict:0", order.validation_errors)
        normalized_count = (
            len(order.installed_equipment)
            + len(order.removed_equipment)
            + len(order.customer_equipment)
            + len(order.materials)
        )
        self.assertEqual(normalized_count, original_count - 1)
        self.assertEqual(order.decision, "manual_review")

    def test_foreign_form_forces_manual_review(self) -> None:
        entry = copy.deepcopy(self.entry)
        entry["os"]["forms"] = [
            {
                "form_data_id": "FORM-FOREIGN",
                "activity_id": "OTHER-AID",
                "label": "Checklist",
            }
        ]

        order = self.normalize(entry)

        self.assertIn("form_activity_id_conflict:0", order.validation_errors)
        self.assertEqual(order.decision, "manual_review")

    def test_integration_error_in_summary_forces_manual_review(self) -> None:
        entry = copy.deepcopy(self.entry)
        entry["os"]["activity"]["completion_summary"] = (
            "Erro de integracao: o servidor nao confirmou o resultado"
        )

        order = self.normalize(entry)

        self.assertIn("integration_error_in_summary", order.validation_errors)
        self.assertEqual(order.decision, "manual_review")
        self.assertIn("integration_error_in_summary", order.decision_reasons)

    def test_duplicate_aid_is_refused_at_lot_boundary(self) -> None:
        with self.assertRaisesRegex(CaptureSchemaError, "AID duplicado"):
            TOACaptureLot.from_dict(lot_payload([self.entry, copy.deepcopy(self.entry)]))

    def test_bad_version_is_refused(self) -> None:
        payload = lot_payload([self.entry])
        payload["metadata"]["version"] = "5.5-queue"

        with self.assertRaisesRegex(CaptureSchemaError, "Versao TECHCAP"):
            TOACaptureLot.from_dict(payload)

    def test_tasks_are_keyed_by_index_and_os_number(self) -> None:
        entry = copy.deepcopy(self.entry)
        first = copy.deepcopy(entry["os"]["tasks"][0])
        second = copy.deepcopy(first)
        second["index"] = 99
        entry["os"]["tasks"] = [first, second]

        order = self.normalize(entry)

        self.assertEqual(len(order.tasks), 2)
        self.assertEqual(
            [(str(task["index"]), task["os_number"]) for task in order.tasks],
            [(str(first["index"]), first["os_number"]), ("99", first["os_number"])],
        )


class TOACaptureScheduledDateTests(unittest.TestCase):
    """Verify that scheduled_date is extracted correctly from activity timestamps."""

    def _make_entry(self, activity_extra: dict) -> dict:
        """Build a minimal valid lot entry with the given activity fields."""
        aid = "AID-DATE-TEST-001"
        contract = "999000001"
        base_activity = {
            "aid": aid,
            "contract": contract,
            "work_type": "ADESAO - INSTALACAO DE ASSINATURA",
            "status": "complete",
            "technician_id": "TECH1",
        }
        base_activity.update(activity_extra)
        return {
            "aid": aid,
            "contract": contract,
            "classification": {"category": "produtiva", "codes": ["409"]},
            "automation": {"decision": "manual_review", "reasons": []},
            "history": [],
            "os": {
                "route": {"aid": aid},
                "activity": base_activity,
                "responsibility": {
                    "assigned_technician": {"id": "TECH1", "name": "Tecnico Teste"},
                    "route_provider": {},
                    "inventory_providers": [],
                    "form_submitters": [],
                },
                "tasks": [
                    {
                        "index": "1",
                        "os_number": "2601323320",
                        "status": "E",
                        "close_code": "409",
                    }
                ],
                "inventory": [],
                "equipment": [],
                "materials": [],
                "forms": [],
            },
        }

    def _normalize(self, activity_extra: dict):
        from toa_capture import normalize_entry
        return normalize_entry(self._make_entry(activity_extra))

    def test_scheduled_date_extracted_from_start_time(self) -> None:
        order = self._normalize({"start_time": "2026-07-20 17:51:00"})
        self.assertEqual(order.scheduled_date, "2026-07-20")

    def test_scheduled_date_fallback_to_end_time_when_no_start_time(self) -> None:
        order = self._normalize({"end_time": "2026-07-20 19:50:00"})
        self.assertEqual(order.scheduled_date, "2026-07-20")

    def test_scheduled_date_empty_when_no_date_field_present(self) -> None:
        order = self._normalize({})
        self.assertEqual(order.scheduled_date, "")

    def test_technician_observation_is_preserved_from_toa_activity(self) -> None:
        order = self._normalize({"observation": "  Cliente pediu retorno apos 18h.  "})
        self.assertEqual(
            order.technician_observation,
            "Cliente pediu retorno apos 18h.",
        )


class TOACaptureIntegrationTests(unittest.TestCase):
    def test_contract_parser_normalizes_separators_and_duplicates(self) -> None:
        self.assertEqual(
            parse_contracts("123, 456;123\n789 | 456"),
            ["123", "456", "789"],
        )

    def test_indexes_by_aid_and_contract(self) -> None:
        entries = [entry_from_case(case) for case in fixture_cases()[:2]]
        lot = TOACaptureLot.from_dict(lot_payload(entries))

        self.assertIsNotNone(lot.find_aid(entries[0]["aid"]))
        self.assertEqual(len(lot.find_contract(entries[0]["contract"])), 1)
        self.assertEqual(lot.find_contract("NOT-FOUND"), ())

    def test_cli_prints_sanitized_dry_run_and_missing_contract(self) -> None:
        entry = entry_from_case(fixture_cases()[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lot.json"
            path.write_text(
                json.dumps(lot_payload([entry]), ensure_ascii=False),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        str(path),
                        "--contracts",
                        f"{entry['contract']},0000000",
                    ]
                )

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("Escrita no Imperium: DESABILITADA", text)
        self.assertIn("candidate_after_validation", text)
        self.assertIn("Contrato 0000000: NAO ENCONTRADO", text)
        self.assertIn("Dry-run: CONFIRMADO", text)

    def test_real_526_aid_lot_is_read_without_identity_contamination(self) -> None:
        if not REAL_LOT_PATH.is_file():
            self.skipTest("Lote TECHCAP real de 526 AIDs nao disponivel neste checkout")
        lot = TOACaptureLot.from_path(REAL_LOT_PATH)

        self.assertEqual(len(lot.orders), 526)
        self.assertEqual(len(lot.by_aid), 526)
        self.assertEqual(lot.metadata["rejectionCount"], 0)
        for order in lot.orders:
            self.assertTrue(order.dry_run_only)
            self.assertFalse(
                any(
                    error.startswith((
                        "activity_aid_conflict",
                        "activity_contract_conflict",
                        "route_aid_conflict",
                        "inventory_activity_id_conflict",
                        "form_activity_id_conflict",
                    ))
                    for error in order.validation_errors
                ),
                msg=f"AID {order.aid}: {order.validation_errors}",
            )
            if order.decision == "candidate_after_validation":
                self.assertFalse(order.validation_errors)

    def test_module_imports_only_standard_library_read_side_dependencies(self) -> None:
        source = (ROOT / "toa_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {
            "app",
            "datasnap_client",
            "imperium_api",
            "socket",
            "requests",
            "toa_import",
        }
        self.assertFalse(imported & forbidden)


if __name__ == "__main__":
    unittest.main()
