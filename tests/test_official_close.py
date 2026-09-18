import datetime as dt
import unittest
from types import SimpleNamespace

from official_close import build_manual_official_plan


class OfficialClosePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.order = SimpleNamespace(
            num_os="2646800969",
            contract="4231199",
            service="ADESAO - INSTALAR PONTO VIRTUA",
        )
        self.removed_codes = {
            "decoder": "41001272",
            "emta": "41001518",
            "smart": "41001273",
        }

    def plan(self, body: dict, code: str = "409", productive: bool = True) -> dict:
        return build_manual_official_plan(
            order=self.order,
            scheduled_date=dt.date(2026, 7, 20),
            technician_code="Z595403",
            close_code=code,
            close_description="INSTALACAO CONCLUIDA",
            productive=productive,
            body=body,
            removed_type_codes=self.removed_codes,
        )

    def test_builds_exact_productive_payload(self) -> None:
        result = self.plan(
            {
                "installed_equipment": [{"serial": "2cd8ae5d425c", "type": "emta"}],
                "removed_equipment": [],
                "materials": [
                    {"code": "22061736", "quantity": 58},
                    {"code": "22065513", "quantity": 2},
                ],
            }
        )

        order = result["payload"]["ordemservico"]
        self.assertEqual(order["numero"], "2646800969")
        self.assertEqual(order["dataagendamento"], "2026-07-20")
        self.assertEqual(order["codigotecnico"], "Z595403")
        self.assertEqual(order["codigobaixa"], 409)
        self.assertEqual(
            order["instaladosserializados"],
            [{"serialnumber": "2CD8AE5D425C"}],
        )
        self.assertEqual(order["instaladosmiscelaneas"][0]["qtd"], "58")
        self.assertEqual(result["installed_count"], 1)
        self.assertEqual(result["material_count"], 2)
        self.assertEqual(len(result["fingerprint"]), 64)

    def test_removed_equipment_uses_captured_equipment_code(self) -> None:
        result = self.plan(
            {
                "installed_equipment": [],
                "removed_equipment": [{"serial": "241786844144", "type": "decoder"}],
                "materials": [],
            },
            code="430",
        )

        removed = result["payload"]["ordemservico"]["removidosserializados"]
        self.assertEqual(
            removed,
            [{"codigoequipamento": "41001272", "serialnumber": "241786844144"}],
        )

    def test_nonproductive_code_rejects_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "improdutivo"):
            self.plan(
                {
                    "installed_equipment": [{"serial": "2CD8AE5D425C"}],
                    "materials": [],
                },
                code="106",
                productive=False,
            )

    def test_430_rejects_installed_equipment(self) -> None:
        with self.assertRaisesRegex(ValueError, "somente equipamento retirado"):
            self.plan(
                {
                    "installed_equipment": [{"serial": "2CD8AE5D425C"}],
                    "removed_equipment": [],
                    "materials": [],
                },
                code="430",
            )

    def test_non_postable_accessories_are_not_sent(self) -> None:
        result = self.plan(
            {
                "installed_equipment": [],
                "removed_equipment": [],
                "materials": [
                    {
                        "code": "22057705",
                        "description": "FONTE CX DIG HD DCR74X1 LITEON",
                        "quantity": 1,
                    },
                    {
                        "code": "22026096",
                        "description": "CABO FORCA 250V 2.5A 2MT",
                        "quantity": 1,
                    },
                    {
                        "code": "22069613",
                        "description": "CONECTOR FO CAMPO FAST SC APC",
                        "quantity": 2,
                    },
                ],
            }
        )

        materials = result["payload"]["ordemservico"]["instaladosmiscelaneas"]
        self.assertEqual(
            materials,
            [{"codigoequipamento": "22069613", "qtd": "2"}],
        )
        self.assertEqual(result["material_count"], 1)
        self.assertEqual(result["ignored_material_count"], 2)


if __name__ == "__main__":
    unittest.main()
