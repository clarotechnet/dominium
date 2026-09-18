import unittest
from decimal import Decimal
from unittest.mock import patch

from imperium_api import ImperiumAPI, Order
from material_matching import (
    distribute_by_group,
    extract_material_code,
    normalize_material_name,
    resolve_material_requests,
    toa_material_ignore_reason,
)


def stock(code: str, name: str, quantity: int, unit: str = "UN") -> dict:
    return {
        "code": code,
        "name": name,
        "stock_quantity": quantity,
        "unit": unit,
        "group_id": 0,
        "group": "",
    }


def stock_with_group(
    code: str,
    name: str,
    quantity: object,
    group_id: int,
    group: str,
    unit: str = "UN",
) -> dict:
    return {
        "code": code,
        "name": name,
        "stock_quantity": quantity,
        "unit": unit,
        "group_id": group_id,
        "group": group,
    }


def request(code: str, description: str, quantity: int) -> dict:
    return {
        "code": code,
        "description": description,
        "quantity": quantity,
        "point": "",
    }


class MaterialMatchingTests(unittest.TestCase):
    def test_non_postable_accessories_are_identified_without_broad_cable_match(
        self,
    ) -> None:
        self.assertEqual(
            toa_material_ignore_reason("FONTE CX DIG HD DCR74X1 LITEON", "22057705"),
            "fonte",
        )
        self.assertEqual(
            toa_material_ignore_reason("CABO DE FORCA 250V 2.5A 2MT", "22026096"),
            "cabo_de_forca",
        )
        self.assertEqual(toa_material_ignore_reason("CABO HDMI 2M"), "hdmi")
        self.assertEqual(toa_material_ignore_reason("PILHAS ALCALINAS AA"), "pilha")
        self.assertEqual(toa_material_ignore_reason("CABO COAXIAL RG6"), "")
        self.assertEqual(toa_material_ignore_reason("CABO DROP PRECON 150M"), "")
        self.assertEqual(toa_material_ignore_reason("CABO UTP CAT5E"), "")

    def test_non_postable_accessories_are_audited_but_not_resolved(self) -> None:
        requests = [
            request("22057705", "FONTE CX DIG HD DCR74X1 LITEON", 1),
            request("22026096", "CABO FORCA 250V 2.5A 2MT", 1),
            request("22090001", "CABO HDMI 2M", 1),
            request("22090002", "PILHA ALCALINA AA", 2),
            request("22090003", "CABO COAXIAL RG6", 3),
            request("22090004", "CABO DROP PRECON 150M", 4),
            request("22090005", "CABO UTP CAT5E", 5),
        ]
        original = [item.copy() for item in requests]

        result = resolve_material_requests(
            requests,
            [
                stock("22090003", "CABO COAXIAL RG6", 30, "M"),
                stock("22090004", "CABO DROP PRECON 150M", 30, "M"),
                stock("22090005", "CABO UTP CAT5E", 30, "M"),
            ],
        )

        self.assertEqual(requests, original)
        self.assertEqual(
            [item["code"] for item in result["materials"]],
            ["22090003", "22090004", "22090005"],
        )
        self.assertEqual(
            [item["code"] for item in result["ignored_materials"]],
            ["22057705", "22026096", "22090001", "22090002"],
        )
        self.assertEqual(result["validation"]["request_count"], 7)
        self.assertEqual(result["validation"]["actionable_count"], 3)
        self.assertEqual(result["validation"]["ignored_count"], 4)
        self.assertTrue(result["validation"]["can_close"])

    def test_normalizes_code_prefix_and_punctuation(self) -> None:
        self.assertEqual(
            normalize_material_name(
                "22069613_CONECTOR FO CAMPO FAST SC/APC",
                "22069613",
            ),
            "CONECTOR FO CAMPO FAST SC APC",
        )

    def test_extracts_concrete_code_from_toa_description(self) -> None:
        self.assertEqual(
            extract_material_code(
                "",
                "22069613_CONECTOR FO CAMPO FAST SC/APC",
            ),
            "22069613",
        )

    def test_conflicting_concrete_codes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Codigo concreto diverge"):
            resolve_material_requests(
                [
                    request(
                        "22069613",
                        "22057620_CONECTOR FO CAMPO FAST SC/APC",
                        1,
                    )
                ],
                [stock("22069613", "CONECTOR FO CAMPO FAST SC APC", 14)],
            )

    def test_real_connector_matches_exact_code_despite_punctuation(self) -> None:
        result = resolve_material_requests(
            [
                request(
                    "22069613",
                    "22069613_CONECTOR FO CAMPO FAST SC/APC",
                    2,
                )
            ],
            [stock("22069613", "CONECTOR FO CAMPO FAST SC APC", 14)],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22069613")
        self.assertEqual(material["quantity"], 2)
        self.assertEqual(material["match_type"], "exact")
        self.assertFalse(material["requires_confirmation"])
        self.assertTrue(material["source_items"][0]["description_matches_stock"])

    def test_description_alone_does_not_match_another_code(self) -> None:
        result = resolve_material_requests(
            [request("22011111", "CONECTOR FO CAMPO FAST SC/APC", 1)],
            [stock("22022222", "CONECTOR FO CAMPO FAST SC APC", 14)],
        )

        self.assertEqual(result["materials"][0]["status"], "unresolved")
        self.assertFalse(result["validation"]["can_close"])

    def test_cable_equivalence_group_matches_imperium_stock(self) -> None:
        result = resolve_material_requests(
            [
                request(
                    "22066907",
                    "22066907_CABO COAXIAL RG6 TRISH SEM MENSAG BRANCO",
                    12,
                )
            ],
            [stock("22026219", "CABO COAXIAL RG6 TRISH SEM MENSAG BRANCO", 100, "M")],
        )
        material = result["materials"][0]
        self.assertEqual(material["code"], "22026219")
        self.assertEqual(material["quantity"], 12)
        self.assertEqual(material["match_type"], "equivalent")

    def test_exact_code_is_kept_when_available(self) -> None:
        result = resolve_material_requests(
            [request("22025139", "FIXADOR FIO BR RG6 CIRCUL 7MM", 20)],
            [
                stock("22025139", "FIXADOR FIO BR RG6 CIRCUL 7MM", 172),
                stock("22057635", "FIXADOR FIO PT RG6", 68),
            ],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22025139")
        self.assertEqual(material["status"], "available")
        self.assertFalse(material["requires_confirmation"])

    def test_same_description_resolves_slash_variant(self) -> None:
        result = resolve_material_requests(
            [
                request(
                    "22057620",
                    "CONECTOR FO CAMPO FAST SC/APC",
                    1,
                )
            ],
            [stock("22069613", "CONECTOR FO CAMPO FAST SC APC", 103)],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22069613")
        self.assertEqual(material["status"], "equivalent")
        self.assertEqual(material["source_codes"], ["22057620"])
        self.assertTrue(result["validation"]["requires_confirmation"])

    def test_approved_connector_codes_are_aggregated(self) -> None:
        result = resolve_material_requests(
            [
                request("22057620", "CONECTOR FO CAMPO FAST SC/APC", 1),
                request("22065513", "CONECTOR FO CAMPO CPO SC APC FRKW", 1),
            ],
            [stock("22069613", "CONECTOR FO CAMPO FAST SC APC", 103)],
        )

        self.assertEqual(len(result["materials"]), 1)
        material = result["materials"][0]
        self.assertEqual(material["code"], "22069613")
        self.assertEqual(material["quantity"], 2)
        self.assertEqual(material["source_codes"], ["22057620", "22065513"])
        self.assertTrue(result["validation"]["can_close"])

    def test_fixador_uses_confirmed_fallback_only_when_exact_is_absent(self) -> None:
        result = resolve_material_requests(
            [request("22025139", "FIXADOR FIO BR RG6 CIRCUL 7MM", 20)],
            [stock("22057635", "FIXADOR FIO PT RG6", 68)],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22057635")
        self.assertEqual(material["quantity"], 20)
        self.assertTrue(material["requires_confirmation"])

    def test_isolating_tape_is_replaced_by_approved_equivalence(self) -> None:
        result = resolve_material_requests(
            [request("22025072", "FITA ISOLANTE 3M 33+", 1)],
            [stock("22064608", "FITA ISOLANTE 3M HIGHLAND 19MM X 20M", 5, "M")],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22064608")
        self.assertEqual(material["match_type"], "equivalent")
        self.assertTrue(result["validation"]["can_close"])

    def test_marker_numbers_are_never_inferred_as_equivalent(self) -> None:
        result = resolve_material_requests(
            [request("22065723", "MARCADOR CASA PRETO NR 5", 1)],
            [stock("22065726", "MARCADOR CASA PRETO NR 8", 10)],
        )

        material = result["materials"][0]
        self.assertEqual(material["code"], "22065723")
        self.assertEqual(material["status"], "unresolved")
        self.assertFalse(result["validation"]["can_close"])

    def test_shortage_blocks_the_resolution(self) -> None:
        result = resolve_material_requests(
            [request("22057659", "ESTICADOR CUNHA P/DROP FO SDA1 DPR", 8)],
            [stock("22057659", "ESTICADOR CUNHA P/DROP FO SDA1 DPR", 5)],
        )

        self.assertEqual(result["materials"][0]["status"], "shortage")
        self.assertEqual(result["validation"]["shortage_count"], 1)
        self.assertFalse(result["validation"]["can_close"])

    def test_productive_close_rejects_unconfirmed_equivalence(self) -> None:
        api = ImperiumAPI()
        order = Order(1, "2600000001", "412773828", 10, "INSTALACAO")

        with self.assertRaisesRegex(ValueError, "Confirme a substituicao"):
            api.close_productive(
                order,
                "409",
                installed_equipment=[{"serial": "ABC1234", "type": "emta"}],
                materials=[
                    {
                        "code": "22069613",
                        "description": "CONECTOR FO CAMPO FAST SC APC",
                        "quantity": 2,
                        "requires_confirmation": True,
                        "equivalence_confirmed": False,
                    }
                ],
            )

    def test_productive_close_strips_non_postable_materials_before_preparation(
        self,
    ) -> None:
        api = ImperiumAPI()
        order = Order(1, "2600000001", "412773828", 10, "INSTALACAO")

        with patch.object(
            api,
            "_close_order_with_builder",
            return_value={"success": True},
        ) as close:
            result = api.close_productive(
                order,
                "409",
                installed_equipment=[{"serial": "ABC1234", "type": "emta"}],
                materials=[
                    request("22057705", "FONTE CX DIG HD DCR74X1 LITEON", 1),
                    request("22026096", "CABO FORCA 250V 2.5A 2MT", 1),
                ],
            )

        self.assertEqual(result["materials"], [])
        self.assertEqual(close.call_args.kwargs["apply_timeout"], 10.0)


class GroupDistributionTests(unittest.TestCase):
    def test_preferred_concrete_code_is_consumed_before_group_siblings(self) -> None:
        inventory = [
            stock_with_group(
                "22024800", "Z WEATHER SEAL", 4, 309, "ANEL DE VEDACAO"
            ),
            stock_with_group(
                "22025321", "A PLASTICA PORTA F", 6, 309, "ANEL DE VEDACAO"
            ),
        ]

        result = distribute_by_group(
            inventory,
            group_id=309,
            requested_quantity=10,
            preferred_code="22024800",
        )

        self.assertEqual(
            [(item["code"], item["quantity"]) for item in result],
            [
                ("22024800", Decimal("4")),
                ("22025321", Decimal("6")),
            ],
        )

    def test_distributes_4_units_across_5_items_of_quantity_1(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", 1, 100, "DIVISOR DC 9"),
            stock_with_group("102", "BRAVO", 1, 100, "DIVISOR DC 9"),
            stock_with_group("103", "CHARLIE", 1, 100, "DIVISOR DC 9"),
            stock_with_group("104", "DELTA", 1, 100, "DIVISOR DC 9"),
            stock_with_group("105", "ECHO", 1, 100, "DIVISOR DC 9"),
        ]

        result = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=4)

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["code"], "101")
        self.assertEqual(result[0]["quantity"], Decimal("1"))
        self.assertEqual(result[1]["code"], "102")
        self.assertEqual(result[1]["quantity"], Decimal("1"))
        self.assertEqual(result[2]["code"], "103")
        self.assertEqual(result[2]["quantity"], Decimal("1"))
        self.assertEqual(result[3]["code"], "104")
        self.assertEqual(result[3]["quantity"], Decimal("1"))

    def test_first_item_with_quantity_3_and_total_request_4(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", 3, 100, "DIVISOR DC 9"),
            stock_with_group("102", "BRAVO", 2, 100, "DIVISOR DC 9"),
        ]

        result = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=4)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["code"], "101")
        self.assertEqual(result[0]["quantity"], Decimal("3"))
        self.assertEqual(result[1]["code"], "102")
        self.assertEqual(result[1]["quantity"], Decimal("1"))

    def test_decimal_quantities_are_preserved_exactly(self) -> None:
        inventory = [
            stock_with_group("900", "ALFA", "60.25", 100, "DIVISOR DC 9", "M"),
            stock_with_group(
                "100",
                "BRAVO",
                Decimal("50.50"),
                100,
                "DIVISOR DC 9",
                "M",
            ),
        ]

        result = distribute_by_group(
            inventory,
            group_name="DIVISOR DC 9",
            requested_quantity="100.5",
        )

        self.assertEqual(
            result,
            [
                {
                    "code": "900",
                    "name": "ALFA",
                    "quantity": Decimal("60.25"),
                    "unit": "M",
                    "group_id": 100,
                    "group": "DIVISOR DC 9",
                },
                {
                    "code": "100",
                    "name": "BRAVO",
                    "quantity": Decimal("40.25"),
                    "unit": "M",
                    "group_id": 100,
                    "group": "DIVISOR DC 9",
                },
            ],
        )

    def test_insufficient_stock_blocks_without_partial_result(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", "1.25", 100, "DIVISOR DC 9"),
            stock_with_group("102", "BRAVO", "1.25", 100, "DIVISOR DC 9"),
        ]

        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            distribute_by_group(
                inventory,
                group_name="DIVISOR DC 9",
                requested_quantity="2.51",
            )

    def test_zero_and_negative_requested_quantities_are_rejected(self) -> None:
        inventory = [stock_with_group("101", "ALFA", 10, 100, "DIVISOR DC 9")]

        for quantity in (0, "0.0", -1, "-0.01"):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "deve ser maior que zero"):
                    distribute_by_group(
                        inventory,
                        group_name="DIVISOR DC 9",
                        requested_quantity=quantity,
                    )

    def test_divisor_dc_9_does_not_confuse_with_divisor_dc_10(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", 1, 100, "DIVISOR DC 9"),
            stock_with_group("102", "BRAVO", 1, 101, "DIVISOR DC 10"),
            stock_with_group("103", "CHARLIE", 1, 102, "DIVISOR DC 9 EXTRA"),
        ]

        result = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "101")
        self.assertEqual(result[0]["group"], "DIVISOR DC 9")

    def test_group_id_has_priority_over_name(self) -> None:
        inventory = [
            stock_with_group("900", "ZULU", 1, 100, "GRUPO PELO ID"),
            stock_with_group("100", "ALFA", 1, 200, "NOME CONFLITANTE"),
        ]

        result = distribute_by_group(
            inventory,
            group_id=100,
            group_name="NOME CONFLITANTE",
            requested_quantity=1,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "900")
        self.assertEqual(result[0]["group_id"], 100)

    def test_concrete_codes_are_preserved(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", 1, 100, "DIVISOR DC 9"),
            stock_with_group("102", "BRAVO", 1, 100, "DIVISOR DC 9"),
        ]

        result = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=2)

        self.assertEqual(result[0]["code"], "101")
        self.assertEqual(result[1]["code"], "102")
        self.assertNotEqual(result[0]["code"], "DIVISOR DC 9")
        self.assertNotEqual(result[1]["code"], "DIVISOR DC 9")

    def test_input_list_is_not_modified(self) -> None:
        inventory = [
            stock_with_group("101", "ALFA", "1.5", 100, "DIVISOR DC 9"),
        ]
        original_inventory = [item.copy() for item in inventory]

        distribute_by_group(
            inventory,
            group_name="DIVISOR DC 9",
            requested_quantity="1.25",
        )

        self.assertEqual(inventory, original_inventory)

    def test_result_order_is_deterministic(self) -> None:
        inventory = [
            stock_with_group("100", "ZULU", 1, 100, "DIVISOR DC 9"),
            stock_with_group("300", "ALFA", 1, 100, "DIVISOR DC 9"),
            stock_with_group("200", "MIKE", 1, 100, "DIVISOR DC 9"),
        ]

        result1 = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=3)
        result2 = distribute_by_group(inventory, group_name="DIVISOR DC 9", requested_quantity=3)

        self.assertEqual(result1, result2)
        self.assertEqual([item["code"] for item in result1], ["300", "200", "100"])


if __name__ == "__main__":
    unittest.main()
