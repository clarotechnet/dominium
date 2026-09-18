import inspect
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

import official_close_dry_run as dry_run_module
from official_close_dry_run import (
    ControlledDryRunError,
    build_controlled_official_dry_run,
)


CONTRACT = "2221170"
MATERIAL_OS = "2646508672"
CLOSE_ONLY_OS = "2646508683"
MATERIAL_POINT = "POINT-TASK-1"
CLOSE_ONLY_POINT = "POINT-TASK-2"
LOGIN = "Z676290"
DATE = "2026-07-21"


def review_fixture() -> dict:
    return {
        "aid": "194650117",
        "contract": CONTRACT,
        "activity_status": "complete",
        "tasks": [
            {"index": 1, "os_number": MATERIAL_OS, "close_code": "409"},
            {"index": 2, "os_number": CLOSE_ONLY_OS, "close_code": "409"},
        ],
        "installed_equipment": [
            {"invid": "INV-IN", "serial": "2CD8AE5D436F", "point": MATERIAL_POINT}
        ],
        "removed_equipment": [
            {
                "invid": "INV-OUT",
                "equipment_code": "41001620",
                "serial": "B4F26757B818",
                "point": MATERIAL_POINT,
            }
        ],
        "materials": [
            {
                "invid": "INV-MAT",
                "material_code": "22069613",
                "quantity": "100.5",
                "point": MATERIAL_POINT,
            }
        ],
        "assigned_technician": {"external_id": LOGIN},
        "route_provider": {
            "id": "62632",
            "external_id": LOGIN,
            "name": "TECNICO TESTE",
        },
        "inventory_providers": [{"external_id": LOGIN}],
        "validation_errors": [],
        "decision": "candidate_after_validation",
        "decision_reasons": [],
    }


def order_fixtures() -> list[dict]:
    return [
        {
            "id_os": 2163993,
            "num_os": MATERIAL_OS,
            "contract": CONTRACT,
            "service": "MUDANCA DE PACOTE",
            "capability": "material_capable",
            "status": "EM CAMPO",
            "imperium_current_status": "EM CAMPO",
            "technician_login": LOGIN,
            "point": MATERIAL_POINT,
        },
        {
            "id_os": 2163994,
            "num_os": CLOSE_ONLY_OS,
            "contract": CONTRACT,
            "service": "INSTALACAO DE CABO GPON",
            "capability": "close_only",
            "status": "EM CAMPO",
            "imperium_current_status": "EM CAMPO",
            "technician_login": LOGIN,
            "point": CLOSE_ONLY_POINT,
        },
    ]


class ControlledOfficialDryRunTests(unittest.TestCase):
    def build(
        self,
        review: dict | None = None,
        orders: list[dict] | None = None,
        authorized_material_os: str = MATERIAL_OS,
    ) -> dict:
        return build_controlled_official_dry_run(
            review_fixture() if review is None else review,
            order_fixtures() if orders is None else orders,
            DATE,
            authorized_material_os=authorized_material_os,
        )

    def test_real_capabilities_produce_expected_payloads(self) -> None:
        result = self.build()
        material = result["official_payload_before_post"]["ordemservico"]
        close_only = result["close_only_companions"][0]["payload"]["ordemservico"]

        self.assertEqual(material["numero"], MATERIAL_OS)
        self.assertEqual(material["codigobaixa"], 409)
        self.assertEqual(
            material["instaladosserializados"],
            [{"serialnumber": "2CD8AE5D436F"}],
        )
        self.assertEqual(
            material["removidosserializados"],
            [{"codigoequipamento": "41001620", "serialnumber": "B4F26757B818"}],
        )
        self.assertEqual(
            material["instaladosmiscelaneas"],
            [{"codigoequipamento": "22069613", "qtd": "100.5"}],
        )
        self.assertEqual(close_only["numero"], CLOSE_ONLY_OS)
        self.assertEqual(close_only["codigobaixa"], 409)
        self.assertEqual(close_only["instaladosserializados"], [])
        self.assertEqual(close_only["instaladosmiscelaneas"], [])
        self.assertEqual(close_only["removidosserializados"], [])

    def test_inverted_order_does_not_change_result(self) -> None:
        normal = self.build()
        inverted = self.build(orders=list(reversed(order_fixtures())))

        self.assertEqual(
            normal["official_payload_before_post"],
            inverted["official_payload_before_post"],
        )
        self.assertEqual(
            normal["close_only_companions"],
            inverted["close_only_companions"],
        )

    def test_toa_complete_and_imperium_em_campo_is_allowed(self) -> None:
        result = self.build()

        self.assertEqual(
            result["imperium_current_status"],
            {MATERIAL_OS: "EM CAMPO", CLOSE_ONLY_OS: "EM CAMPO"},
        )
        self.assertTrue(result["dry_run_only"])

    def test_toa_already_processed_marker_does_not_override_imperium(self) -> None:
        review = review_fixture()
        review["decision_reasons"] = ["already_processed"]
        review["validation_errors"] = ["toa_already_processed"]

        result = self.build(review=review)

        self.assertTrue(result["dry_run_only"])

    def test_toa_complete_and_imperium_finalized_is_blocked(self) -> None:
        orders = order_fixtures()
        orders[0]["imperium_current_status"] = "FINALIZADA"

        with self.assertRaisesRegex(ControlledDryRunError, "already_processed"):
            self.build(orders=orders)

    def test_both_tasks_keep_visible_code_409(self) -> None:
        plans = dry_run_module.build_contract_official_plans(
            review_fixture(), order_fixtures(), DATE
        )

        self.assertEqual({plan["close_code"] for plan in plans}, {"409"})
        self.assertEqual(
            {plan["payload"]["ordemservico"]["codigobaixa"] for plan in plans},
            {409},
        )

    def test_equipment_on_close_only_is_blocked(self) -> None:
        review = review_fixture()
        review["installed_equipment"][0]["point"] = CLOSE_ONLY_POINT

        with self.assertRaisesRegex(
            ControlledDryRunError, "inventory_assigned_to_close_only"
        ):
            self.build(review=review)

    def test_material_on_close_only_is_blocked(self) -> None:
        review = review_fixture()
        review["materials"][0]["point"] = CLOSE_ONLY_POINT

        with self.assertRaisesRegex(
            ControlledDryRunError, "inventory_assigned_to_close_only"
        ):
            self.build(review=review)

    def test_two_material_capable_orders_are_blocked(self) -> None:
        orders = order_fixtures()
        orders[1]["service"] = "MUDANCA DE PACOTE"
        orders[1]["capability"] = "material_capable"

        with self.assertRaisesRegex(ControlledDryRunError, "exatamente uma"):
            self.build(orders=orders)

    def test_no_material_capable_order_is_blocked(self) -> None:
        orders = order_fixtures()
        orders[0]["service"] = "INSTALACAO DE CABO GPON"
        orders[0]["capability"] = "close_only"

        with self.assertRaisesRegex(ControlledDryRunError, "exatamente uma"):
            self.build(orders=orders)

    def test_unknown_service_is_blocked(self) -> None:
        orders = order_fixtures()
        orders[0]["service"] = "SERVICO DESCONHECIDO"

        with self.assertRaisesRegex(ControlledDryRunError, "capacidade"):
            self.build(orders=orders)

    def test_authorized_close_only_order_is_blocked(self) -> None:
        with self.assertRaisesRegex(ControlledDryRunError, "material_capable"):
            self.build(authorized_material_os=CLOSE_ONLY_OS)

    def test_duplicate_os_number_is_blocked(self) -> None:
        orders = order_fixtures()
        orders[1]["num_os"] = MATERIAL_OS

        with self.assertRaisesRegex(ControlledDryRunError, "duplicado"):
            self.build(orders=orders)

    def test_missing_inventory_point_is_blocked(self) -> None:
        review = review_fixture()
        review["materials"][0]["point"] = ""

        with self.assertRaisesRegex(
            ControlledDryRunError, "inventory_assignment_incomplete"
        ):
            self.build(review=review)

    def test_missing_route_is_blocked(self) -> None:
        review = review_fixture()
        review["route_provider"] = {}

        with self.assertRaisesRegex(ControlledDryRunError, "rota"):
            self.build(review=review)

    def test_removed_equipment_without_code_is_blocked(self) -> None:
        review = review_fixture()
        review["removed_equipment"][0]["equipment_code"] = ""

        with self.assertRaisesRegex(
            ControlledDryRunError, "removed_equipment_code_missing"
        ):
            self.build(review=review)

    def test_planner_omitting_close_only_order_is_blocked(self) -> None:
        plans = dry_run_module.build_contract_official_plans(
            review_fixture(), order_fixtures(), DATE
        )
        plans = [plan for plan in plans if plan["num_os"] == MATERIAL_OS]

        with patch(
            "official_close_dry_run.build_contract_official_plans",
            return_value=plans,
        ):
            with self.assertRaisesRegex(ControlledDryRunError, "omitiu"):
                self.build()

    def test_planner_cannot_change_payload_number(self) -> None:
        plans = dry_run_module.build_contract_official_plans(
            review_fixture(), order_fixtures(), DATE
        )
        plans[0]["payload"]["ordemservico"]["numero"] = "9999999999"

        with patch(
            "official_close_dry_run.build_contract_official_plans",
            return_value=plans,
        ):
            with self.assertRaisesRegex(ControlledDryRunError, "num_os do plano"):
                self.build()

    def test_decimal_quantity_remains_a_string(self) -> None:
        payload = self.build()["official_payload_before_post"]["ordemservico"]

        self.assertEqual(payload["instaladosmiscelaneas"][0]["qtd"], "100.5")
        self.assertIsInstance(payload["instaladosmiscelaneas"][0]["qtd"], str)

    def test_input_data_is_not_modified(self) -> None:
        review = review_fixture()
        orders = order_fixtures()
        original_review = deepcopy(review)
        original_orders = deepcopy(orders)

        self.build(review=review, orders=orders)

        self.assertEqual(review, original_review)
        self.assertEqual(orders, original_orders)

    def test_output_has_no_send_capability(self) -> None:
        result = self.build()
        source = inspect.getsource(dry_run_module)

        self.assertFalse(result["send_enabled"])
        self.assertEqual(result["requests_sent"], 0)
        self.assertFalse(result["retry_enabled"])
        self.assertFalse(result["datasnap_fallback_enabled"])
        self.assertNotRegex(source, r"(?m)^\s*import\s+(?:requests|urllib)\b")
        self.assertNotRegex(source, r"(?m)^\s*from\s+(?:requests|urllib)\b")
        self.assertNotRegex(source, r"(?m)^\s*def\s+(?:post|send)\s*\(")

    def test_official_json_is_only_the_material_payload(self) -> None:
        result = self.build()
        decoded = json.loads(result["official_json_before_post"])

        self.assertEqual(decoded, result["official_payload_before_post"])
        self.assertEqual(set(decoded), {"ordemservico"})


if __name__ == "__main__":
    unittest.main()
