import struct
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from imperium_api import DetailContext, ImperiumAPI, Order, StockMaterial


def build_synthetic_dsploc_record(
    *,
    id_equipment: int = 4950,
    code: str = "22023400",
    equipment: str = "ABRACADEIRA NYLON 203X4,9X1,3MM T50R",
    descricao: str = "22023400_ABRACADEIRA NYLON T50R 20CM PRETA | 22056346_ABRACADEIRA HELLERMANN T50R-PT NET | 22025242_ABRACADEIRA NYLON T18R 10CM PRETA",
    id_marca: int = 6,
    marca: str = "DIVERSOS",
    id_unidade: int = 2,
    unidade: str = "UN",
    id_contrato: int = 1,
    contrato: str = "NET",
    identificado: str = "N",
    ncm: str = "39269090",
    cst: str = "041",
    gtin: str = "SEM GTIN",
    id_aux: str = "",
    status: str = "ATIVO",
) -> bytes:
    def short_text(s: str) -> bytes:
        enc = s.encode("cp1252")
        return bytes([len(enc)]) + enc

    desc_enc = descricao.encode("cp1252")
    desc_bytes = struct.pack("<H", len(desc_enc)) + desc_enc
    valor_bcd = bytes(18)

    return b"".join(
        [
            b"\x00\x00\x00\x00",  # prefix header
            struct.pack("<I", id_equipment),
            short_text(code),
            short_text(equipment),
            desc_bytes,
            struct.pack("<I", id_marca),
            short_text(marca),
            struct.pack("<I", id_unidade),
            short_text(unidade),
            valor_bcd,
            struct.pack("<I", id_contrato),
            short_text(contrato),
            short_text(identificado),
            short_text(ncm),
            short_text(cst),
            short_text(gtin),
            short_text(id_aux),
            short_text(status),
        ]
    )


class EquipmentGroupMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI()
        self.captured_payload_path = (
            Path(__file__).resolve().parents[1] / "data" / "payload_dsploc_22023400.bin"
        )

    def test_dsploc_query_builder_structure(self) -> None:
        query = self.api._build_dsploc_equipment_query("22023400")
        self.assertIn(b"DspLoc", query)
        self.assertIn(b"!\x01`a\x01", query)
        self.assertIn("CodigoEquipamento".encode("utf-16le"), query)
        self.assertIn("22023400%".encode("utf-16le"), query)
        self.assertIn("Equipamento".encode("utf-16le"), query)
        self.assertIn("DESCRICAO".encode("utf-16le"), query)
        self.assertIn("STATUS".encode("utf-16le"), query)

        # Test query close transformation
        closed = self.api._provider_close_query(query)
        self.assertNotIn(b"!\x01`a\x01", closed)
        self.assertIn(b"``a\x02", closed)

    def test_parse_real_captured_dsploc_payload(self) -> None:
        if not self.captured_payload_path.exists():
            self.skipTest("Captured DspLoc payload file not found")

        payload = self.captured_payload_path.read_bytes()
        record = self.api._parse_dsploc_equipment_record(payload, "22023400")
        self.assertIsNotNone(record)
        self.assertEqual(record["requested_code"], "22023400")
        self.assertEqual(record["group"], "ABRACADEIRA")
        self.assertEqual(record["id_equipment"], 4950)
        self.assertEqual(record["unit"], "UN")
        self.assertEqual(record["identificado"], "N")
        self.assertEqual(record["status"], "ATIVO")

        expected_equivalents = [
            "22023400",
            "22056346",
            "22025242",
            "22025247",
            "22025251",
        ]
        self.assertEqual(record["equivalents"], expected_equivalents)
        self.assertEqual(len(record["items"]), 5)
        self.assertEqual(
            record["items"][0]["description"],
            "ABRACADEIRA NYLON T50R 20CM PRETA",
        )
        self.assertEqual(
            record["items"][1]["description"],
            "ABRACADEIRA HELLERMANN T50R-PT NET",
        )

    def test_parse_dsploc_accepts_status_before_final_flag(self) -> None:
        payload = build_synthetic_dsploc_record(
            id_equipment=309,
            code="22025321",
            equipment="ANEL VEDACAO PLASTICA P PORTA F",
            descricao=(
                "22025321_ANEL VEDACAO PLASTICA P PORTA F | "
                "22056757_ANEL VEDACAO PLAST. P/ PORTA F"
            ),
            gtin="",
            id_aux="ATIVO",
            status="N",
        )
        record = self.api._parse_dsploc_equipment_record(payload, "22025321")
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "ATIVO")
        self.assertEqual(record["group"], "ANEL VEDACAO")
        self.assertEqual(record["equivalents"], ["22025321", "22056757"])

    def test_parse_dsploc_inactive_status_rejected(self) -> None:
        payload = build_synthetic_dsploc_record(status="INATIVO")
        record = self.api._parse_dsploc_equipment_record(payload, "22023400")
        self.assertIsNone(record)

    def test_parse_dsploc_serialized_item_rejected(self) -> None:
        payload = build_synthetic_dsploc_record(identificado="S")
        record = self.api._parse_dsploc_equipment_record(payload, "22023400")
        self.assertIsNone(record)

    def test_parse_dsploc_nonexistent_code(self) -> None:
        payload = build_synthetic_dsploc_record(code="22023400")
        record = self.api._parse_dsploc_equipment_record(payload, "99999999")
        self.assertIsNone(record)

    def test_lookup_equipment_group_by_code_caching(self) -> None:
        fake_record = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = fake_record

        # Standalone lookup returns cached object without calling network
        result = self.api.lookup_equipment_group_by_code("22023400")
        self.assertEqual(result, fake_record)

    def _mock_order_context(self) -> tuple[Order, DetailContext, MagicMock]:
        order = Order(
            2162769,
            "2646000001",
            "4231016",
            10,
            "ADESAO - INSTALAR PONTO VIRTUA",
        )
        context = DetailContext(order.id_os, order.contract, 313363, "JANDERSON")
        client = MagicMock()
        client.__enter__.return_value = client
        return order, context, client

    def test_official_materials_exact_code_with_sufficient_balance(self) -> None:
        """Rule 1: Exact code with stock balance has priority and is used directly."""
        order, context, client = self._mock_order_context()
        exact_mat = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA NYLON 20CM",
            5,
            260,
            "UN",
            2,
            "N",
        )

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[exact_mat],
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "2"}],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(result["source"], "technician_stock")
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22023400", "qtd": "2"}],
        )
        self.assertEqual(result["group_distributions"], [])
        transfer.assert_not_called()

    def test_official_materials_substitutes_equivalent_when_exact_lacks_balance(
        self,
    ) -> None:
        """Rule 2: When exact code has 0 balance, consumes equivalent with stock from DspLoc."""
        order, context, client = self._mock_order_context()
        exact_mat = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA NYLON 20CM",
            0,
            260,
            "UN",
            2,
            "N",
        )
        eq_mat = StockMaterial(
            4951,
            "22056346",
            "ABRACADEIRA HELLERMANN T50R-PT",
            5,
            260,
            "UN",
            2,
            "N",
        )

        dsploc_group = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346", "22025242"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON 20CM",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = dsploc_group

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[exact_mat, eq_mat],
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "2"}],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(result["source"], "technician_stock")
        # Payload uses the concrete consumed equivalent code
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22056346", "qtd": "2"}],
        )
        # Audit records requested original code and used equivalent
        self.assertEqual(len(result["group_distributions"]), 1)
        self.assertEqual(result["group_distributions"][0]["requested_code"], "22023400")
        self.assertEqual(result["group_distributions"][0]["group"], "ABRACADEIRA")
        self.assertEqual(
            result["group_distributions"][0]["allocations"],
            [{"code": "22056346", "quantity": "2"}],
        )
        transfer.assert_not_called()

    def test_official_materials_uses_atlas_when_requested_code_missing_from_catalog(self) -> None:
        order, context, client = self._mock_order_context()
        sibling = StockMaterial(
            4270, "22056757", "ANEL VEDACAO PLAST. P/ PORTA F",
            6, 260, "UN", 2, "N",
        )
        self.api._equipment_group_cache["22025321"] = {
            "requested_code": "22025321",
            "group": "ANEL VEDACAO",
            "equivalents": ["22025321", "22056757"],
            "id_equipment": 309,
            "equipment": "ANEL VEDACAO PLASTICA P PORTA F",
            "unit": "UN", "id_unit": 2, "status": "ATIVO",
            "identificado": "N", "items": [],
        }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=b"detail:" + order.num_os.encode("ascii")),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(self.api, "_combined_material_catalog_on", return_value=[sibling]),
            patch.object(self.api, "_lookup_material_by_code_on", return_value=None),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22025321", "description": "ANEL VEDACAO PLASTICA P PORTA F", "quantity": "1"}],
                expected_installer_id=context.installer_id,
            )
        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22056757", "qtd": "1"}],
        )
        self.assertEqual(result["group_distributions"][0]["requested_code"], "22025321")
        self.assertEqual(result["group_distributions"][0]["group"], "ANEL VEDACAO")
        transfer.assert_not_called()

    def test_official_materials_multi_item_split_across_exact_and_equivalents(
        self,
    ) -> None:
        """Rule 2 multi-split: requested 10, exact has 3, eq1 has 5, eq2 has 8 -> 3 + 5 + 2 = 10."""
        order, context, client = self._mock_order_context()
        exact_mat = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA NYLON 20CM",
            3,
            260,
            "UN",
            2,
            "N",
        )
        eq1_mat = StockMaterial(
            4951,
            "22056346",
            "ABRACADEIRA HELLERMANN T50R-PT",
            5,
            260,
            "UN",
            2,
            "N",
        )
        eq2_mat = StockMaterial(
            4952,
            "22025242",
            "ABRACADEIRA NYLON T18R 10CM",
            8,
            260,
            "UN",
            2,
            "N",
        )

        dsploc_group = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346", "22025242"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON 20CM",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = dsploc_group

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[exact_mat, eq1_mat, eq2_mat],
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "10"}],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(
            result["resolved_materials"],
            [
                {"codigoequipamento": "22023400", "qtd": "3"},
                {"codigoequipamento": "22056346", "qtd": "5"},
                {"codigoequipamento": "22025242", "qtd": "2"},
            ],
        )
        self.assertEqual(len(result["group_distributions"]), 1)
        self.assertEqual(result["group_distributions"][0]["requested_code"], "22023400")
        self.assertEqual(
            result["group_distributions"][0]["allocations"],
            [
                {"code": "22023400", "quantity": "3"},
                {"code": "22056346", "quantity": "5"},
                {"code": "22025242", "quantity": "2"},
            ],
        )
        transfer.assert_not_called()

    def test_official_materials_uses_sibling_code_from_retorno_for_mini_isolador(self) -> None:
        order, context, client = self._mock_order_context()
        requested = StockMaterial(
            5041, "22067384", "MINI ISOLADOR CPE CABLE MODEM E DECODER",
            0, 260, "UN", 2, "N",
        )
        sibling = StockMaterial(
            290, "22056364", "MINI ISOLADOR CPE P/CM DECODER",
            0, 260, "UN", 2, "N",
        )
        self.api._equipment_group_cache["22067384"] = {
            "requested_code": "22067384",
            "group": "MINI ISOLADOR CPE",
            "equivalents": ["22067384", "22056364"],
            "id_equipment": 5041,
            "equipment": requested.name,
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api, "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api, "_combined_material_catalog_on",
                return_value=[requested, sibling],
            ),
            patch.object(
                self.api, "_material_virtual_stock_quantities_on",
                return_value={"22067384": Decimal("0"), "22056364": Decimal("2")},
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22067384", "description": requested.name, "quantity": "2"}],
                expected_installer_id=context.installer_id,
            )
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22056364", "qtd": "2"}],
        )
        self.assertEqual(result["shortfalls"][0]["requested_code"], "22067384")
        self.assertEqual(result["shortfalls"][0]["code"], "22056364")
        transferred = transfer.call_args.args[2]
        self.assertEqual([(item.code, item.requested_quantity) for item in transferred], [("22056364", 2)])

    def test_official_materials_uses_approved_group_when_dsploc_has_no_group(self) -> None:
        order, context, client = self._mock_order_context()
        requested = StockMaterial(
            5030, "22066906", "CABO COAXIAL RG6 TRISH COM MENSAG PRETO",
            0, context.installer_id, "M", 1, "N",
        )
        sibling = StockMaterial(
            5030, "22026223", "CABO COAXIAL RG6 TRISH COM MENSAG PRETO",
            0, context.installer_id, "M", 1, "N",
        )
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api, "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api, "_combined_material_catalog_on",
                return_value=[requested, sibling],
            ),
            patch.object(
                self.api, "_lookup_equipment_group_by_code_on",
                return_value=None,
            ),
            patch.object(
                self.api, "_material_virtual_stock_quantities_on",
                return_value={"22066906": Decimal("0"), "22026223": Decimal("23")},
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{
                    "code": "22066906",
                    "description": requested.name,
                    "quantity": "23",
                }],
                expected_installer_id=context.installer_id,
            )

        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22026223", "qtd": "23"}],
        )
        self.assertEqual(result["shortfalls"][0]["requested_code"], "22066906")
        self.assertEqual(result["shortfalls"][0]["code"], "22026223")
        self.assertEqual(result["group_distributions"][0]["requested_code"], "22066906")
        self.assertEqual(result["group_distributions"][0]["group"], "Cabo Coaxial RG6 Trish Com Mensag Preto")
        transferred = transfer.call_args.args[2]
        self.assertEqual(
            [(item.code, item.requested_quantity) for item in transferred],
            [("22026223", 23)],
        )

    def test_official_materials_ignores_textually_similar_item_not_in_atlas(
        self,
    ) -> None:
        """Rule 3: Textually similar items outside Descrição Atlas must NEVER be used."""
        order, context, client = self._mock_order_context()
        exact_mat = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA NYLON 20CM",
            0,
            260,
            "UN",
            2,
            "N",
        )
        # Similar name, but code 99999999 is NOT in DspLoc equivalents!
        similar_mat = StockMaterial(
            9999,
            "99999999",
            "ABRACADEIRA NYLON 20CM SIMILAR",
            50,
            260,
            "UN",
            2,
            "N",
        )

        dsploc_group = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON 20CM",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = dsploc_group

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[exact_mat, similar_mat],
            ),
            patch.object(
                self.api,
                "_material_virtual_stock_quantities_on",
                return_value={"22023400": Decimal("2")},
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "2"}],
                expected_installer_id=context.installer_id,
            )

        # 99999999 was NOT used; shortfall for 22023400 was transferred
        self.assertTrue(result["transferred"])
        self.assertEqual(result["source"], "RETORNO")
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22023400", "qtd": "2"}],
        )
        self.assertEqual(
            result["shortfalls"],
            [
                {
                    "code": "22023400",
                    "requested_code": "22023400",
                    "requested_quantity": "2",
                    "technician_available": 0,
                    "transfer_quantity": 2,
                    "group": "ABRACADEIRA",
                }
            ],
        )
        transfer.assert_called_once()

    def test_official_materials_insufficient_group_balance_falls_back_to_shortfall(
        self,
    ) -> None:
        """Rule 3/shortfall: When group has only partial balance, transfers deficit."""
        order, context, client = self._mock_order_context()
        exact_mat = StockMaterial(
            4950,
            "22023400",
            "ABRACADEIRA NYLON 20CM",
            2,
            260,
            "UN",
            2,
            "N",
        )
        eq_mat = StockMaterial(
            4951,
            "22056346",
            "ABRACADEIRA HELLERMANN T50R-PT",
            3,
            260,
            "UN",
            2,
            "N",
        )

        dsploc_group = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON 20CM",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = dsploc_group

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[exact_mat, eq_mat],
            ),
            patch.object(
                self.api,
                "_material_virtual_stock_quantities_on",
                return_value={"22023400": Decimal("5")},
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            # Requested 10: exact has 2, eq has 3 (total in group = 5). Deficit = 5.
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "10"}],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["transferred"])
        self.assertEqual(result["source"], "RETORNO")
        self.assertEqual(
            result["shortfalls"],
            [
                {
                    "code": "22023400",
                    "requested_code": "22023400",
                    "requested_quantity": "10",
                    "technician_available": 2,
                    "transfer_quantity": 5,
                    "group": "ABRACADEIRA",
                }
            ],
        )
        # 22023400 has 2 (from stock) + 5 (transferred) = 7; 22056346 has 3. Total = 10.
        self.assertEqual(
            result["resolved_materials"],
            [
                {"codigoequipamento": "22023400", "qtd": "7"},
                {"codigoequipamento": "22056346", "qtd": "3"},
            ],
        )
        transfer.assert_called_once()

    def test_official_materials_requested_not_in_technician_stock_substitutes_equivalent(
        self,
    ) -> None:
        """When requested item is not even in technician stock list, but equivalent is in stock."""
        order, context, client = self._mock_order_context()
        eq_mat = StockMaterial(
            4951,
            "22056346",
            "ABRACADEIRA HELLERMANN T50R-PT",
            4,
            260,
            "UN",
            2,
            "N",
        )

        dsploc_group = {
            "requested_code": "22023400",
            "group": "ABRACADEIRA",
            "equivalents": ["22023400", "22056346"],
            "id_equipment": 4950,
            "equipment": "ABRACADEIRA NYLON 20CM",
            "unit": "UN",
            "id_unit": 2,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        self.api._equipment_group_cache["22023400"] = dsploc_group

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[eq_mat],  # 22023400 is not in catalog at all
            ),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": "22023400", "description": "ABRACADEIRA", "quantity": "4"}],
                expected_installer_id=context.installer_id,
            )

        self.assertTrue(result["prepared"])
        self.assertFalse(result["transferred"])
        self.assertEqual(
            result["resolved_materials"],
            [{"codigoequipamento": "22056346", "qtd": "4"}],
        )
        self.assertEqual(
            result["group_distributions"][0]["allocations"],
            [{"code": "22056346", "quantity": "4"}],
        )
        transfer.assert_not_called()

    def test_official_materials_tolerates_one_missing_misc_even_with_large_quantity(self) -> None:
        order, context, client = self._mock_order_context()
        cable = StockMaterial(6001, "22066906", "CABO COAXIAL RG6 PRETO", 0, 260, "M", 1, "N")
        self.api._equipment_group_cache[cable.code] = {
            "requested_code": cable.code,
            "group": "CABO RG6 PRETO",
            "equivalents": [cable.code],
            "id_equipment": cable.id_equipment,
            "equipment": cable.name,
            "unit": "M",
            "id_unit": 1,
            "status": "ATIVO",
            "identificado": "N",
            "items": [],
        }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=b"detail:" + order.num_os.encode("ascii")),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(self.api, "_combined_material_catalog_on", return_value=[cable]),
            patch.object(self.api, "_material_virtual_stock_quantities_on", return_value={}),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [{"code": cable.code, "description": cable.name, "quantity": "23"}],
                expected_installer_id=context.installer_id,
            )
        self.assertEqual(result["resolved_materials"], [])
        self.assertEqual(result["tolerated_shortfall_count"], 1)
        self.assertEqual(result["tolerated_shortfalls"][0]["missing_quantity"], "23")
        transfer.assert_not_called()

    def test_official_materials_tolerates_four_distinct_missing_misc(self) -> None:
        order, context, client = self._mock_order_context()
        codes = ["22065718", "22065719", "22065720", "22065721"]
        materials = [
            StockMaterial(6100 + index, code, f"MATERIAL {index}", 0, 260, "UN", 2, "N")
            for index, code in enumerate(codes, start=1)
        ]
        for material in materials:
            self.api._equipment_group_cache[material.code] = {
                "requested_code": material.code,
                "group": material.name,
                "equivalents": [material.code],
                "id_equipment": material.id_equipment,
                "equipment": material.name,
                "unit": "UN",
                "id_unit": 2,
                "status": "ATIVO",
                "identificado": "N",
                "items": [],
            }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=b"detail:" + order.num_os.encode("ascii")),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(self.api, "_combined_material_catalog_on", return_value=materials),
            patch.object(self.api, "_material_virtual_stock_quantities_on", return_value={}),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            result = self.api.prepare_official_materials(
                order,
                [
                    {"code": material.code, "description": material.name, "quantity": str(index * 10)}
                    for index, material in enumerate(materials, start=1)
                ],
                expected_installer_id=context.installer_id,
            )
        self.assertEqual(result["tolerated_shortfall_count"], 4)
        self.assertEqual(len(result["tolerated_shortfalls"]), 4)
        transfer.assert_not_called()

    def test_official_materials_blocks_when_five_distinct_misc_are_missing(self) -> None:
        order, context, client = self._mock_order_context()
        codes = ["22065718", "22065719", "22065720", "22065721", "22065722"]
        materials = [
            StockMaterial(6200 + index, code, f"MATERIAL {index}", 0, 260, "UN", 2, "N")
            for index, code in enumerate(codes, start=1)
        ]
        for material in materials:
            self.api._equipment_group_cache[material.code] = {
                "requested_code": material.code,
                "group": material.name,
                "equivalents": [material.code],
                "id_equipment": material.id_equipment,
                "equipment": material.name,
                "unit": "UN",
                "id_unit": 2,
                "status": "ATIVO",
                "identificado": "N",
                "items": [],
            }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_fetch_detail_on", return_value=b"detail:" + order.num_os.encode("ascii")),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(self.api, "_combined_material_catalog_on", return_value=materials),
            patch.object(self.api, "_material_virtual_stock_quantities_on", return_value={}),
            patch.object(self.api, "_transfer_material_shortfalls") as transfer,
        ):
            with self.assertRaisesRegex(ValueError, "faltam 5 miscelaneas sem cobertura"):
                self.api.prepare_official_materials(
                    order,
                    [{"code": material.code, "description": material.name, "quantity": "50"} for material in materials],
                    expected_installer_id=context.installer_id,
                )
        transfer.assert_not_called()

    def test_official_materials_unknown_code_blocks_when_dsploc_has_no_match(
        self,
    ) -> None:
        """When code is not in stock, not in manual picker, and not in DspLoc, it raises ValueError."""
        order, context, client = self._mock_order_context()
        self.api._equipment_group_cache["99999999"] = None

        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(
                self.api,
                "_fetch_detail_on",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
            patch.object(
                self.api,
                "_combined_material_catalog_on",
                return_value=[],
            ),
            patch.object(self.api, "_lookup_material_by_code_on", return_value=None),
        ):
            with self.assertRaises(ValueError) as ctx:
                self.api.prepare_official_materials(
                    order,
                    [{"code": "99999999", "description": "DESCONHECIDO", "quantity": "1"}],
                    expected_installer_id=context.installer_id,
                )
            self.assertIn("nao existe no estoque do instalador", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
