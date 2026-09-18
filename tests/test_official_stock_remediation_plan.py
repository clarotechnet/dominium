import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path

from official_stock_remediation_plan import (
    EXPECTED_CODES,
    StockRemediationPlanError,
    build_stock_remediation_plan,
    load_json_object,
)


MATERIALS = {
    "22025072": {
        "invid": "497450948",
        "id": "4898",
        "description": "FITA ISOLANTE 3M 33+",
        "state": "sem_saldo",
        "available": "0",
        "unit": "M",
    },
    "22056343": {
        "invid": "497450950",
        "id": "300",
        "description": "MARCADOR CASA PTO NR 1",
        "state": "ausente",
        "available": None,
        "unit": None,
    },
    "22056341": {
        "invid": "497450951",
        "id": "354",
        "description": "MARCADOR CASA PTO NR 7",
        "state": "ausente",
        "available": None,
        "unit": None,
    },
    "22056344": {
        "invid": "497450952",
        "id": "324",
        "description": "MARCADOR CASA PTO NR 2",
        "state": "ausente",
        "available": None,
        "unit": None,
    },
}


def fixture():
    inspection_materials = []
    toa_inventory = []
    catalog_materials = []
    stock_materials = []
    reviews = []
    audit_blockers = []
    review_blockers = []
    for code in EXPECTED_CODES:
        material = MATERIALS[code]
        inspection_materials.append(
            {
                "equipment_code": code,
                "used_quantity": "1",
                "invid": material["invid"],
                "inv_aid": "194300555",
            }
        )
        toa_inventory.append(
            {
                "kind": "material",
                "material_code": code,
                "quantity": "1",
                "invid": material["invid"],
                "activity_id": "194300555",
                "description": f"{code}_{material['description']}",
            }
        )
        catalog_materials.append(
            {
                "toa": {
                    "code": code,
                    "description": f"{code}_{material['description']}",
                },
                "official": {
                    "code_entry": {
                        "code": code,
                        "ids": [material["id"]],
                        "descriptions": [material["description"]],
                    },
                    "description": material["description"],
                },
            }
        )
        stock_materials.append(
            {
                "code": code,
                "equipment_id": (
                    int(material["id"])
                    if material["state"] == "sem_saldo"
                    else None
                ),
                "installer_id": 328898,
                "stock_id": 276,
                "available_quantity": material["available"],
                "unit": material["unit"],
                "status": material["state"].replace("_", " "),
                "source": "offline fixture",
                "read_at": "2026-07-23T16:40:39-03:00",
            }
        )
        source_state = material["state"].replace("_", " ")
        audit_blockers.append(f"stock_audit_{source_state}:{code}")
        review_blockers.append(f"stock_audit_{material['state']}:{code}")
        reviews.append(
            {
                "code": code,
                "canonical_state": material["state"],
                "origin": {
                    "invid": material["invid"],
                    "used_quantity": "1",
                },
                "official_catalog": {
                    "ids": [material["id"]],
                    "descriptions": [material["description"]],
                },
                "stock_evidence": {
                    "available_quantity": material["available"],
                    "unit": material["unit"],
                },
                "unit_evidence": {
                    "toa_unit": None,
                    "stock_unit": material["unit"],
                },
                "matching": {"matching_incorreto": False},
                "candidates": [
                    {
                        "code": f"CANDIDATO-{code}",
                        "sources": ["context_only"],
                        "equivalence_authorized": False,
                    }
                ],
                "decision": {
                    "keep_blocked": True,
                    "automatic_alias_created": False,
                    "automatic_substitution_authorized": False,
                },
            }
        )

    inspection = {
        "contract": "2221170",
        "routing_evidence": {"effective_material_os": "2646508672"},
        "inventory": {"materials": inspection_materials},
        "technician_identity_evidence": {
            "imperium_orders": {"installer_id": 328898}
        },
        "safety": {},
    }
    toa_capture = {
        "os_list": [
            {
                "os": {
                    "activity": {
                        "contract": "2221170",
                        "aid": "194300555",
                    },
                    "inventory": toa_inventory,
                }
            }
        ]
    }
    catalog_report = {
        "contract": "2221170",
        "materials": catalog_materials,
        "payload_generated": False,
        "safety": {},
    }
    stock_report = {
        "installer_id": 328898,
        "stock_id": 276,
        "profile": "TECHNET NATAL",
        "read_at": "2026-07-23T16:40:39-03:00",
        "materials": stock_materials,
        "blockers": audit_blockers,
        "payload_generated": False,
        "safety": {},
    }
    blocker_review = {
        "contract": "2221170",
        "activity_aid": "194300555",
        "material_os": "2646508672",
        "installer_id": 328898,
        "reviews": reviews,
        "blockers_remaining": review_blockers,
        "blockers_removable": [],
        "payload_generated": False,
        "safety": {},
    }
    close_code_catalog = {
        "schema": "dominium_official_close_code_catalog_v1",
        "source": {
            "file_name": "Tabela_codigo_baixa0711.pdf",
            "sha256": "a" * 64,
            "page_count": 44,
        },
        "entries": [
            {
                "code": "104",
                "status": "valid",
                "category": "IMPRODUTIVOS",
                "description": "Falta de Material",
                "usage_rule": (
                    "Quando o técnico vai até a residência do cliente e não "
                    "consegue executar o serviço, devido à falta de material "
                    "ou equipamento."
                ),
                "customer_communication": "Comunique o cliente.",
                "source_pages": [4],
                "occurrences": 1,
            }
        ],
        "warnings": [],
        "payload_generated": False,
        "safety": {
            "network_used": False,
            "post_executed": False,
            "datasnap_read_executed": False,
            "datasnap_write_executed": False,
            "stock_movement_executed": False,
            "close_executed": False,
            "payload_generated": False,
        },
    }
    return (
        inspection,
        toa_capture,
        catalog_report,
        stock_report,
        blocker_review,
        close_code_catalog,
    )


class OfficialStockRemediationPlanTests(unittest.TestCase):
    def test_zero_balance_calculates_exact_deficit(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        material = plan["materials"][0]

        self.assertEqual(material["code"], "22025072")
        self.assertEqual(material["required_quantity"], "1")
        self.assertEqual(material["available_quantity"], "0")
        self.assertEqual(material["deficit_quantity"], "1")
        self.assertEqual(
            material["actions"]["external_action"],
            "repor_saldo",
        )
        self.assertTrue(material["blocker_active"])

    def test_absent_material_preserves_null_and_minimum_deficit(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        material = plan["materials"][1]

        self.assertEqual(material["current_state"], "ausente")
        self.assertIsNone(material["available_quantity"])
        self.assertEqual(material["deficit_quantity"], "1")
        self.assertEqual(
            material["actions"]["external_action"],
            "cadastrar_ou_disponibilizar_no_estoque",
        )

    def test_unknown_unit_is_preserved_without_conversion(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        absent = plan["materials"][1]["unit_evidence"]
        zero_balance = plan["materials"][0]["unit_evidence"]

        self.assertIsNone(absent["unit"])
        self.assertIsNone(absent["unit_source"])
        self.assertEqual(absent["status"], "unidade_nao_comprovada")
        self.assertEqual(zero_balance["unit"], "M")
        self.assertEqual(
            zero_balance["unit_source"],
            "official_stock_audit.stock_row",
        )
        self.assertEqual(
            zero_balance["status"],
            "unidade_nao_comprovada",
        )

    def test_candidate_substitution_is_rejected(self) -> None:
        documents = list(fixture())
        documents[4]["reviews"][0]["candidates"][0][
            "equivalence_authorized"
        ] = True

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Candidato foi autorizado",
        ):
            build_stock_remediation_plan(*documents)

    def test_contract_divergence_is_rejected(self) -> None:
        documents = list(fixture())
        documents[2]["contract"] = "999"

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Contrato divergente no catalogo",
        ):
            build_stock_remediation_plan(*documents)

    def test_installer_divergence_is_rejected(self) -> None:
        documents = list(fixture())
        documents[3]["installer_id"] = 999

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Installer ID divergente na auditoria",
        ):
            build_stock_remediation_plan(*documents)

    def test_review_and_audit_divergence_is_rejected(self) -> None:
        documents = list(fixture())
        documents[4]["blockers_remaining"][0] = (
            "stock_audit_ausente:22025072"
        )

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Estado diverge entre auditoria e revisao",
        ):
            build_stock_remediation_plan(*documents)

    def test_capture_and_inspection_quantity_divergence_is_rejected(
        self,
    ) -> None:
        documents = list(fixture())
        documents[0]["inventory"]["materials"][0]["used_quantity"] = "2"

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Quantidade diverge",
        ):
            build_stock_remediation_plan(*documents)

    def test_catalog_and_review_identifier_divergence_is_rejected(
        self,
    ) -> None:
        documents = list(fixture())
        documents[4]["reviews"][0]["official_catalog"]["ids"] = ["999"]

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Identificador oficial diverge",
        ):
            build_stock_remediation_plan(*documents)

    def test_missing_or_invalid_input_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(
                StockRemediationPlanError,
                "Nao foi possivel ler",
            ):
                load_json_object(missing)

            invalid = Path(directory) / "invalid.json"
            invalid.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(
                StockRemediationPlanError,
                "JSON invalido",
            ):
                load_json_object(invalid)

    def test_output_is_deterministic(self) -> None:
        first = build_stock_remediation_plan(*fixture())
        second = build_stock_remediation_plan(*fixture())

        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_inputs_are_not_modified(self) -> None:
        documents = fixture()
        before = copy.deepcopy(documents)

        build_stock_remediation_plan(*documents)

        self.assertEqual(documents, before)

    def test_all_four_blockers_stay_active(self) -> None:
        plan = build_stock_remediation_plan(*fixture())

        self.assertEqual(len(plan["materials"]), 4)
        self.assertEqual(
            plan["blockers_active"],
            [
                "stock_audit_sem_saldo:22025072",
                "stock_audit_ausente:22056343",
                "stock_audit_ausente:22056341",
                "stock_audit_ausente:22056344",
            ],
        )
        self.assertEqual(plan["blockers_removable"], [])

    def test_code_104_is_context_only_and_never_authorized(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        context = plan["operational_close_code_context"]

        self.assertEqual(context["code"], "104")
        self.assertEqual(context["description"], "Falta de Material")
        self.assertEqual(context["source"]["page"], 4)
        self.assertFalse(context["selection_authorized"])
        self.assertFalse(context["application_authorized"])
        self.assertFalse(context["stock_blocker_alone_authorizes_code"])
        self.assertFalse(context["payload_generated"])
        self.assertFalse(context["close_executed"])
        self.assertIn(
            "visita_ao_cliente_confirmada",
            context["conditions_required"],
        )

    def test_unrelated_pdf_duplicate_warnings_do_not_block_plan(self) -> None:
        documents = list(fixture())
        documents[5]["warnings"] = [
            {
                "type": "duplicate_code_identical",
                "code": "466",
                "source_pages": [44],
                "automatic_correction": False,
            }
        ]

        plan = build_stock_remediation_plan(*documents)

        self.assertEqual(
            plan["operational_close_code_context"][
                "catalog_warnings_unrelated"
            ][0]["code"],
            "466",
        )

    def test_missing_code_104_blocks_context_registration(self) -> None:
        documents = list(fixture())
        documents[5]["entries"] = []

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Codigo contextual 104 ausente",
        ):
            build_stock_remediation_plan(*documents)

    def test_inconsistent_code_104_blocks_context_registration(self) -> None:
        documents = list(fixture())
        documents[5]["entries"][0]["status"] = "inconsistent"

        with self.assertRaisesRegex(
            StockRemediationPlanError,
            "Codigo contextual 104 inconsistente",
        ):
            build_stock_remediation_plan(*documents)

    def test_stock_blockers_never_select_code_104(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        serialized_materials = json.dumps(
            plan["materials"],
            sort_keys=True,
        )

        self.assertNotIn('"104"', serialized_materials)
        self.assertEqual(plan["blockers_removable"], [])
        self.assertFalse(
            plan["operational_close_code_context"][
                "stock_blocker_alone_authorizes_code"
            ]
        )

    def test_no_operational_payload_is_produced(self) -> None:
        plan = build_stock_remediation_plan(*fixture())
        serialized = json.dumps(plan, sort_keys=True).casefold()

        self.assertFalse(plan["payload_generated"])
        self.assertFalse(plan["safety"]["datasnap_read_executed"])
        self.assertFalse(plan["safety"]["datasnap_write_executed"])
        self.assertFalse(plan["safety"]["post_executed"])
        self.assertFalse(plan["safety"]["stock_movement_executed"])
        self.assertFalse(plan["safety"]["close_executed"])
        self.assertNotIn("ordemservico", serialized)
        self.assertNotIn("authorization", serialized)

    def test_module_imports_no_integration_or_write_client(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "official_stock_remediation_plan.py"
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
            "material_matching",
        }
        self.assertTrue(forbidden.isdisjoint(imported))


if __name__ == "__main__":
    unittest.main()
