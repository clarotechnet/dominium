import unittest

from imperium_http_plan import build_contract_official_plans


def review_fixture() -> dict:
    return {
        "aid": "194516899",
        "contract": "4231792",
        "activity_status": "complete",
        "tasks": [
            {"index": 1, "os_number": "2646888662", "close_code": "409"},
            {"index": 2, "os_number": "2646888673", "close_code": "409"},
        ],
        "installed_equipment": [
            {"serial": "2CD8AE5D3FD3", "point": "38244258"}
        ],
        "removed_equipment": [],
        "materials": [
            {"material_code": "22069613", "quantity": "2", "point": "38244258"},
            {"material_code": "22061736", "quantity": "35", "point": "38244258"},
        ],
        "assigned_technician": {"external_id": "Z676290"},
        "inventory_providers": [{"external_id": "Z676290"}],
        "validation_errors": [],
        "decision": "manual_review",
        "decision_reasons": ["route_not_confirmed"],
    }


def order_fixtures() -> list[dict]:
    return [
        {
            "id_os": 2163993,
            "num_os": "2646888662",
            "contract": "4231792",
            "service": "ADESAO - INSTALACAO DE ASSINATURA",
            "status": "EM CAMPO",
            "technician_login": "Z676290",
            "point": "38244255",
        },
        {
            "id_os": 2163994,
            "num_os": "2646888673",
            "contract": "4231792",
            "service": "ADESAO - INSTALAR PONTO VIRTUA",
            "status": "EM CAMPO",
            "technician_login": "Z676290",
            "point": "38244258",
        },
    ]


class OfficialPlanTests(unittest.TestCase):
    def test_route_missing_blocks_by_default(self) -> None:
        plans = build_contract_official_plans(
            review_fixture(), order_fixtures(), "2026-07-20"
        )
        self.assertTrue(all(not plan["ok"] for plan in plans))
        self.assertTrue(all("route_not_confirmed" in plan["blockers"] for plan in plans))

    def test_explicit_route_override_assigns_inventory_by_point(self) -> None:
        plans = build_contract_official_plans(
            review_fixture(),
            order_fixtures(),
            "2026-07-20",
            allow_route_missing=True,
        )
        signature, virtua = plans
        self.assertTrue(signature["ok"])
        self.assertEqual(signature["installed_count"], 0)
        self.assertEqual(signature["material_count"], 0)
        self.assertEqual(
            signature["payload"]["ordemservico"]["instaladosserializados"], []
        )
        self.assertTrue(virtua["ok"])
        self.assertEqual(virtua["installed_count"], 1)
        self.assertEqual(virtua["material_count"], 2)
        self.assertEqual(
            virtua["payload"]["ordemservico"]["instaladosserializados"],
            [{"serialnumber": "2CD8AE5D3FD3"}],
        )
        self.assertEqual(
            virtua["payload"]["ordemservico"]["instaladosmiscelaneas"],
            [
                {"codigoequipamento": "22069613", "qtd": "2"},
                {"codigoequipamento": "22061736", "qtd": "35"},
            ],
        )

    def test_inventory_provider_mismatch_blocks_movement_order(self) -> None:
        review = review_fixture()
        review["inventory_providers"] = [{"external_id": "Z999999"}]
        plans = build_contract_official_plans(
            review,
            order_fixtures(),
            "2026-07-20",
            allow_route_missing=True,
        )
        self.assertIn("inventory_provider_login_mismatch", plans[1]["blockers"])
        self.assertFalse(plans[1]["ok"])

    def test_unassigned_inventory_blocks_every_plan(self) -> None:
        review = review_fixture()
        review["materials"][0]["point"] = "OTHER"
        plans = build_contract_official_plans(
            review,
            order_fixtures(),
            "2026-07-20",
            allow_route_missing=True,
        )
        self.assertTrue(
            all("inventory_assignment_incomplete" in plan["blockers"] for plan in plans)
        )

    def test_removed_equipment_requires_equipment_code(self) -> None:
        review = review_fixture()
        review["removed_equipment"] = [
            {"serial": "241700000001", "point": "38244258"}
        ]
        plans = build_contract_official_plans(
            review,
            order_fixtures(),
            "2026-07-20",
            allow_route_missing=True,
        )
        self.assertIn("removed_equipment_code_missing", plans[1]["blockers"])


if __name__ == "__main__":
    unittest.main()
