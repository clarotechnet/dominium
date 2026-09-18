import ast
import copy
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import official_close_dry_run as core_module
import official_close_toa_dry_run as bridge_module
from official_close_toa_dry_run import (
    TOAOfficialDryRunError,
    build_authorized_toa_dry_run,
    inspect_toa_contract,
)


CONTRACT = "2221170"
AID = "194650117"
DATE = "2026-07-21"
MATERIAL_OS = "2646508672"
CLOSE_ONLY_OS = "2646508683"
MATERIAL_POINT = "POINT-TASK-1"
CLOSE_ONLY_POINT = "POINT-TASK-2"
LOGIN = "Z676290"


def task(index: int, os_number: str) -> dict:
    source_fields = (
        {"os": "193", "status": "194", "close_code": "195"}
        if index == 1
        else {"os": "196", "status": "197", "close_code": "198"}
    )
    return {
        "index": index,
        "os_number": os_number,
        "status": "E",
        "close_code": "409",
        "source_fields": source_fields,
    }


def inventory(
    invid: str,
    *,
    kind: str,
    point: str = MATERIAL_POINT,
    pool: str = "install",
    serial: str = "",
    material_code: str = "",
    quantity: str = "1",
    available_stock: str = "39",
) -> dict:
    return {
        "invid": invid,
        "activity_id": AID,
        "provider_id": "TECH-1",
        "pool": pool,
        "kind": kind,
        "serial": serial,
        "material_code": material_code,
        "description": material_code,
        "point": point,
        "used_quantity": quantity,
        "available_stock": available_stock,
        "available_stock_source": "imperium_quantity_stock",
        "quantity": quantity,
    }


def default_inventory() -> list[dict]:
    return [
        inventory("INV-IN", kind="equipment", serial="2CD8AE5D436F"),
        inventory(
            "INV-OUT",
            kind="equipment",
            pool="deinstall",
            serial="B4F26757B818",
            material_code="41001620",
        ),
        inventory(
            "INV-MAT",
            kind="material",
            material_code="22069613",
            quantity="100.5",
        ),
    ]


def capture_payload(
    *,
    activity_status: str = "complete",
    assigned_name: str = "DENNIS TESTE",
    route_name: str = "DENNIS TESTE",
    assigned_login: str = LOGIN,
    route_login: str = LOGIN,
    inventory_items: list[dict] | None = None,
) -> dict:
    items = default_inventory() if inventory_items is None else inventory_items
    entry = {
        "aid": AID,
        "contract": CONTRACT,
        "os": {
            "activity": {
                "aid": AID,
                "contract": CONTRACT,
                "city": "NATAL",
                "status": activity_status,
                "work_type": "Instalacao",
                "start_time": f"{DATE} 08:00:00",
                "technician_id": "TECH-1",
            },
            "route": {"aid": AID},
            "tasks": [task(1, MATERIAL_OS), task(2, CLOSE_ONLY_OS)],
            "inventory": copy.deepcopy(items),
            "forms": [],
            "responsibility": {
                "assigned_technician": {
                    "id": "TECH-1",
                    "external_id": assigned_login,
                    "name": assigned_name,
                },
                "route_provider": {
                    "id": "TECH-1",
                    "external_id": route_login,
                    "name": route_name,
                },
                "inventory_providers": [
                    {
                        "id": "TECH-1",
                        "external_id": assigned_login,
                        "name": assigned_name,
                    }
                ],
                "form_submitters": [],
            },
        },
        "classification": {"category": "produtiva", "codes": ["409"]},
        "automation": {
            "decision": "candidate_after_validation",
            "reasons": [],
        },
        "history": [],
    }
    return {
        "metadata": {
            "version": "5.6-queue",
            "source": "TECHCAP V5.6",
            "count": 1,
            "rejectionCount": 0,
        },
        "os_list": [entry],
        "rejections": [],
    }


def order_payload(*, technician_login: str = LOGIN) -> list[dict]:
    return [
        {
            "id_os": 2163993,
            "num_os": MATERIAL_OS,
            "contract": CONTRACT,
            "service": "MUDANCA DE PACOTE",
            "status": "EM CAMPO",
            "technician_login": technician_login,
            "technician_name": "DENNIS TESTE",
            "point": MATERIAL_POINT,
        },
        {
            "id_os": 2163994,
            "num_os": CLOSE_ONLY_OS,
            "contract": CONTRACT,
            "service": "INSTALACAO DE CABO GPON",
            "status": "EM CAMPO",
            "technician_login": technician_login,
            "technician_name": "DENNIS TESTE",
            "point": CLOSE_ONLY_POINT,
        },
    ]


class TOAOfficialCloseDryRunTests(unittest.TestCase):
    def dry_run(
        self,
        *,
        capture: dict | None = None,
        orders: list[dict] | None = None,
        authorized: str = MATERIAL_OS,
        output_dir: str | Path,
    ) -> dict:
        return build_authorized_toa_dry_run(
            capture_payload() if capture is None else capture,
            order_payload() if orders is None else orders,
            CONTRACT,
            DATE,
            authorized_material_os=authorized,
            output_dir=output_dir,
        )

    def test_inspection_preserves_tasks_slots_services_points_and_status(self) -> None:
        inspection = inspect_toa_contract(
            capture_payload(), order_payload(), CONTRACT, DATE
        )
        by_number = {order["num_os"]: order for order in inspection["orders"]}

        self.assertTrue(inspection["ok"])
        self.assertEqual(by_number[MATERIAL_OS]["capability"], "material_capable")
        self.assertEqual(by_number[CLOSE_ONLY_OS]["capability"], "close_only")
        self.assertEqual(by_number[MATERIAL_OS]["task_index"], "1")
        self.assertEqual(by_number[MATERIAL_OS]["source_fields"]["os"], "193")
        self.assertEqual(by_number[CLOSE_ONLY_OS]["task_index"], "2")
        self.assertEqual(by_number[CLOSE_ONLY_OS]["source_fields"]["os"], "196")
        self.assertEqual(by_number[MATERIAL_OS]["point"], MATERIAL_POINT)
        self.assertEqual(by_number[CLOSE_ONLY_OS]["point"], CLOSE_ONLY_POINT)
        self.assertEqual({order["close_code"] for order in by_number.values()}, {"409"})
        self.assertEqual(
            inspection["imperium_current_status"],
            {MATERIAL_OS: "EM CAMPO", CLOSE_ONLY_OS: "EM CAMPO"},
        )

    def test_material_capable_receives_swap_and_materials(self) -> None:
        inspection = inspect_toa_contract(
            capture_payload(), order_payload(), CONTRACT, DATE
        )
        material = next(
            order
            for order in inspection["orders"]
            if order["capability"] == "material_capable"
        )

        self.assertEqual(
            [item["serial"] for item in material["installed_equipment"]],
            ["2CD8AE5D436F"],
        )
        self.assertEqual(
            [item["serial"] for item in material["removed_equipment"]],
            ["B4F26757B818"],
        )
        self.assertEqual(material["removed_equipment"][0]["equipment_code"], "41001620")
        self.assertEqual(material["materials"][0]["equipment_code"], "22069613")
        self.assertEqual(material["materials"][0]["used_quantity"], "100.5")
        self.assertEqual(material["materials"][0]["available_stock"], "39")

    def test_payload_uses_used_quantity_and_never_available_stock(self) -> None:
        capture = capture_payload()
        material = capture["os_list"][0]["os"]["inventory"][2]
        material["used_quantity"] = "1"
        material["quantity"] = "1"
        material["available_stock"] = "39"

        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(capture=capture, output_dir=directory)

        payload_materials = result["official_payload"]["ordemservico"][
            "instaladosmiscelaneas"
        ]
        self.assertEqual(payload_materials, [{"codigoequipamento": "22069613", "qtd": "1"}])
        self.assertNotIn("39", json.dumps(result["official_payload"]))

    def test_non_postable_accessories_remain_audited_but_leave_the_payload(
        self,
    ) -> None:
        items = default_inventory()
        ignored = [
            inventory(
                "INV-FONTE",
                kind="material",
                material_code="22057705",
                quantity="1",
            ),
            inventory(
                "INV-FORCA",
                kind="material",
                material_code="22026096",
                quantity="1",
            ),
            inventory(
                "INV-HDMI",
                kind="material",
                material_code="22090001",
                quantity="1",
            ),
            inventory(
                "INV-PILHA",
                kind="material",
                material_code="22090002",
                quantity="2",
            ),
        ]
        ignored[0]["description"] = "FONTE CX DIG HD DCR74X1 LITEON"
        ignored[1]["description"] = "CABO DE FORCA 250V 2.5A 2MT"
        ignored[2]["description"] = "CABO HDMI 2M"
        ignored[3]["description"] = "PILHA ALCALINA AA"
        items.extend(ignored)
        capture = capture_payload(inventory_items=items)

        inspection = inspect_toa_contract(capture, order_payload(), CONTRACT, DATE)
        self.assertTrue(inspection["ok"])
        self.assertEqual(
            [item["invid"] for item in inspection["ignored_materials"]],
            ["INV-FONTE", "INV-FORCA", "INV-HDMI", "INV-PILHA"],
        )
        material_order = next(
            order
            for order in inspection["orders"]
            if order["capability"] == "material_capable"
        )
        self.assertEqual(
            [item["equipment_code"] for item in material_order["materials"]],
            ["22069613"],
        )

        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(
                capture=capture,
                output_dir=directory,
            )

        self.assertEqual(
            result["official_payload"]["ordemservico"]["instaladosmiscelaneas"],
            [{"codigoequipamento": "22069613", "qtd": "100.5"}],
        )
        self.assertEqual(
            len(result["inspection"]["ignored_materials"]),
            4,
        )

    def test_inventory_quantity_is_used_quantity_not_available_stock(self) -> None:
        capture = capture_payload()
        material = capture["os_list"][0]["os"]["inventory"][2]
        material["used_quantity"] = "1"
        material["available_stock"] = "39"
        material.pop("available_stock_source")
        material["quantity"] = "39"

        inspection = inspect_toa_contract(capture, order_payload(), CONTRACT, DATE)
        routed_material = next(
            order for order in inspection["orders"] if order["capability"] == "material_capable"
        )["materials"][0]

        self.assertTrue(inspection["ok"])
        self.assertEqual(routed_material["used_quantity"], "39")
        self.assertEqual(routed_material["available_stock"], "")

        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(capture=capture, output_dir=directory)
        self.assertEqual(
            result["official_payload"]["ordemservico"]["instaladosmiscelaneas"],
            [{"codigoequipamento": "22069613", "qtd": "39"}],
        )

    def test_close_only_generates_three_empty_inventory_lists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(output_dir=directory)
        companion = result["inspection"]["orders"][1]
        close_payload = result["summary"]["close_only_payloads"][0]["ordemservico"]

        self.assertEqual(companion["capability"], "close_only")
        self.assertEqual(companion["installed_equipment"], [])
        self.assertEqual(companion["removed_equipment"], [])
        self.assertEqual(companion["materials"], [])
        self.assertEqual(close_payload["instaladosserializados"], [])
        self.assertEqual(close_payload["instaladosmiscelaneas"], [])
        self.assertEqual(close_payload["removidosserializados"], [])

    def test_inverted_order_list_does_not_change_routing(self) -> None:
        normal = inspect_toa_contract(capture_payload(), order_payload(), CONTRACT, DATE)
        inverted = inspect_toa_contract(
            capture_payload(), list(reversed(order_payload())), CONTRACT, DATE
        )

        self.assertEqual(normal["orders"], inverted["orders"])

    def test_toa_complete_and_imperium_em_campo_permits_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(output_dir=directory)

        self.assertTrue(result["dry_run_only"])
        self.assertEqual(
            result["summary"]["imperium_current_status"][MATERIAL_OS],
            "EM CAMPO",
        )

    def test_toa_already_processed_marker_does_not_override_imperium(self) -> None:
        capture = capture_payload()
        capture["os_list"][0]["automation"]["reasons"] = ["already_processed"]
        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(capture=capture, output_dir=directory)

        self.assertEqual(
            result["summary"]["imperium_current_status"][MATERIAL_OS],
            "EM CAMPO",
        )

    def test_toa_executed_text_and_imperium_em_campo_permits_dry_run(self) -> None:
        capture = capture_payload(activity_status="Executada")
        with tempfile.TemporaryDirectory() as directory:
            result = self.dry_run(capture=capture, output_dir=directory)

        self.assertEqual(result["inspection"]["activity_status"], "Executada")
        self.assertTrue(result["dry_run_only"])

    def test_toa_complete_and_imperium_finalized_blocks(self) -> None:
        orders = order_payload()
        orders[0]["status"] = "FINALIZADA"
        inspection = inspect_toa_contract(capture_payload(), orders, CONTRACT, DATE)

        self.assertIn(f"already_processed:{MATERIAL_OS}", inspection["blockers"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TOAOfficialDryRunError, "already_processed"):
                self.dry_run(orders=orders, output_dir=directory)

    def test_equipment_routed_to_close_only_blocks(self) -> None:
        items = default_inventory()
        items[0]["point"] = CLOSE_ONLY_POINT
        inspection = inspect_toa_contract(
            capture_payload(inventory_items=items), order_payload(), CONTRACT, DATE
        )

        self.assertIn("equipment_assigned_to_close_only:INV-IN", inspection["blockers"])

    def test_material_routed_to_close_only_blocks(self) -> None:
        items = default_inventory()
        items[2]["point"] = CLOSE_ONLY_POINT
        inspection = inspect_toa_contract(
            capture_payload(inventory_items=items), order_payload(), CONTRACT, DATE
        )

        self.assertIn("material_assigned_to_close_only:INV-MAT", inspection["blockers"])

    def test_two_material_capable_orders_block(self) -> None:
        orders = order_payload()
        orders[1]["service"] = "MUDANCA DE PACOTE"
        inspection = inspect_toa_contract(capture_payload(), orders, CONTRACT, DATE)

        self.assertIn("material_capable_order_count_invalid", inspection["blockers"])

    def test_unknown_service_blocks(self) -> None:
        orders = order_payload()
        orders[0]["service"] = "SERVICO DESCONHECIDO"
        inspection = inspect_toa_contract(capture_payload(), orders, CONTRACT, DATE)

        self.assertIn(f"service_capability_unmapped:{MATERIAL_OS}", inspection["blockers"])

    def test_authorized_material_os_must_match_detected_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TOAOfficialDryRunError, "authorized_material_os"):
                self.dry_run(authorized=CLOSE_ONLY_OS, output_dir=directory)

    def test_missing_order_point_blocks(self) -> None:
        orders = order_payload()
        orders[0]["point"] = ""
        inspection = inspect_toa_contract(capture_payload(), orders, CONTRACT, DATE)

        self.assertIn(f"order_point_missing:{MATERIAL_OS}", inspection["blockers"])

    def test_ambiguous_duplicate_points_block(self) -> None:
        orders = order_payload()
        orders[1]["point"] = MATERIAL_POINT
        inspection = inspect_toa_contract(capture_payload(), orders, CONTRACT, DATE)

        self.assertIn("order_points_duplicate", inspection["blockers"])

    def test_task_number_must_match_indexed_order(self) -> None:
        capture = capture_payload()
        capture["os_list"][0]["os"]["tasks"][0]["os_number"] = "9999999999"
        inspection = inspect_toa_contract(capture, order_payload(), CONTRACT, DATE)

        self.assertIn("task_order_not_found:9999999999", inspection["blockers"])

    def test_task_point_must_match_order_point(self) -> None:
        capture = capture_payload()
        capture["os_list"][0]["os"]["tasks"][0]["point"] = CLOSE_ONLY_POINT
        inspection = inspect_toa_contract(capture, order_payload(), CONTRACT, DATE)

        self.assertIn(
            f"task_order_point_mismatch:{MATERIAL_OS}", inspection["blockers"]
        )

    def test_inventory_aid_must_match_activity(self) -> None:
        items = default_inventory()
        items[0]["activity_id"] = "OTHER-AID"
        inspection = inspect_toa_contract(
            capture_payload(inventory_items=items), order_payload(), CONTRACT, DATE
        )

        self.assertTrue(
            any("inventory_activity_id_conflict" in value for value in inspection["blockers"])
        )

    def test_removed_equipment_without_code_blocks(self) -> None:
        items = default_inventory()
        items[1]["material_code"] = ""
        inspection = inspect_toa_contract(
            capture_payload(inventory_items=items), order_payload(), CONTRACT, DATE
        )

        self.assertIn("removed_equipment_code_missing:INV-OUT", inspection["blockers"])

    def test_name_spelling_difference_with_same_login_warns_and_passes(self) -> None:
        capture = capture_payload(assigned_name="DENNIS TESTE", route_name="DENIS TESTE")
        orders = order_payload()
        for order in orders:
            order["technician_name"] = "DENIS TESTE"
        inspection = inspect_toa_contract(capture, orders, CONTRACT, DATE)

        self.assertTrue(inspection["ok"])
        self.assertTrue(
            any(value.startswith("technician_name_spelling_diff") for value in inspection["alerts"])
        )

    def test_same_name_with_different_login_blocks(self) -> None:
        inspection = inspect_toa_contract(
            capture_payload(), order_payload(technician_login="Z999999"), CONTRACT, DATE
        )

        self.assertFalse(inspection["ok"])
        self.assertIn(
            f"order_technician_login_mismatch:{MATERIAL_OS}",
            inspection["blockers"],
        )

    def test_fingerprint_and_file_are_exact_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = self.dry_run(output_dir=directory)
            second = self.dry_run(output_dir=directory)
            saved = json.loads(Path(first["output_path"]).read_text(encoding="utf-8"))

        self.assertEqual(first["fingerprint_sha256"], second["fingerprint_sha256"])
        self.assertEqual(
            first["fingerprint_sha256"],
            hashlib.sha256(first["official_json"].encode("utf-8")).hexdigest(),
        )
        self.assertEqual(set(saved), {"ordemservico"})
        self.assertEqual(saved, first["official_payload"])

    def test_input_data_is_not_modified(self) -> None:
        capture = capture_payload()
        orders = order_payload()
        original_capture = copy.deepcopy(capture)
        original_orders = copy.deepcopy(orders)
        with tempfile.TemporaryDirectory() as directory:
            self.dry_run(capture=capture, orders=orders, output_dir=directory)

        self.assertEqual(capture, original_capture)
        self.assertEqual(orders, original_orders)

    def test_modules_have_no_send_capability(self) -> None:
        for module in (bridge_module, core_module):
            tree = ast.parse(inspect.getsource(module))
            imported_roots: set[str] = set()
            function_names: set[str] = set()
            called_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".")[0])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_names.add(node.name.casefold())
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        called_names.add(node.func.id.casefold())
                    elif isinstance(node.func, ast.Attribute):
                        called_names.add(node.func.attr.casefold())

            self.assertTrue(
                {"requests", "urllib", "httpx", "socket", "datasnap_client"}.isdisjoint(
                    imported_roots
                )
            )
            self.assertTrue({"post", "send", "request", "retry"}.isdisjoint(function_names))
            self.assertTrue({"post", "send", "request"}.isdisjoint(called_names))


if __name__ == "__main__":
    unittest.main()
