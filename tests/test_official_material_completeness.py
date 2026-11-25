"""Políticas de estoque da baixa oficial, com consultas e transferências simuladas."""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from imperium_api import DetailContext, ImperiumAPI, Order, StockMaterial


class OfficialMaterialCompletenessTests(unittest.TestCase):
    def test_natal_uses_atlas_technician_stock_before_return_and_omits_unavailable(self):
        api = ImperiumAPI()
        order = Order(123, "2663000001", "4000001", 10, "ADESAO - INSTALAR PONTO VIRTUA")
        context = DetailContext(order.id_os, order.contract, 313363, "TECNICO TESTE")
        original, equivalent, missing = "22026219", "22066907", "99999999"
        catalog = [StockMaterial(1, original, "CABO A", 0, 260, "M", 2, "N"),
                   StockMaterial(2, equivalent, "CABO B", 3, 260, "M", 2, "N")]
        client = MagicMock()
        client.__enter__.return_value = client
        events = []

        def atlas(_client, code):
            events.append(("atlas", code))
            return {"group": "CABO", "equivalents": [original, equivalent]} if code == original else None

        def stocks(_client):
            events.append(("retorno", None))
            return {original: Decimal("50")}

        with (
            patch.object(api, "_client", return_value=client),
            patch.object(api, "_fetch_detail_on", return_value=order.num_os.encode()),
            patch.object(api, "_detail_context", return_value=context),
            patch.object(api, "_combined_material_catalog_on", return_value=catalog),
            patch.object(api, "_lookup_equipment_group_by_code_on", side_effect=atlas),
            patch.object(api, "_material_virtual_stock_quantities_on", side_effect=stocks),
            patch.object(api, "_transfer_material_shortfalls") as transfer,
        ):
            result = api.prepare_official_materials(
                order, [{"code": original, "quantity": 3}, {"code": missing, "quantity": 1}],
                expected_installer_id=context.installer_id, omit_unavailable=True,
            )
            self.assertEqual(result["resolved_materials"], [{"codigoequipamento": equivalent, "qtd": "3"}])
            self.assertEqual(result["discarded_shortfalls"], [{"code": missing, "missing_quantity": "1"}])
            transfer.assert_not_called()
            self.assertIn(("retorno", None), events)
            self.assertLess(events.index(("atlas", missing)), events.index(("retorno", None)))

    def test_recheck_does_not_repeat_transfer_when_return_has_balance(self):
        api = ImperiumAPI()
        order = Order(123, "2663000001", "4000001", 10, "ADESAO - INSTALAR PONTO VIRTUA")
        context = DetailContext(order.id_os, order.contract, 313363, "TECNICO TESTE")
        material = StockMaterial(1, "22025139", "FIXADOR", 0, 260, "UN", 2, "N")
        client = MagicMock()
        client.__enter__.return_value = client
        with (
            patch.object(api, "_client", return_value=client),
            patch.object(api, "_fetch_detail_on", return_value=order.num_os.encode()),
            patch.object(api, "_detail_context", return_value=context),
            patch.object(api, "_combined_material_catalog_on", return_value=[material]),
            patch.object(api, "_lookup_equipment_group_by_code_on", return_value=None),
            patch.object(api, "_material_virtual_stock_quantities_on", return_value={material.code: Decimal("5")}) as source,
            patch.object(api, "_transfer_material_shortfalls") as transfer,
        ):
            with self.assertRaisesRegex(ValueError, "RETORNO tem saldo para 22025139"):
                api.prepare_official_materials(order, [{"code": material.code, "quantity": 4}],
                                               expected_installer_id=context.installer_id, allow_transfer=False)
            source.return_value = {}
            result = api.prepare_official_materials(order, [{"code": material.code, "quantity": 4}],
                                                    expected_installer_id=context.installer_id, allow_transfer=False)
            transfer.assert_not_called()
            self.assertEqual(result["resolved_materials"], [])
            self.assertEqual(result["discarded_shortfalls"][0]["missing_quantity"], "4")

    def test_uncovered_material_blocks_before_transferring_other_items(self):
        api = ImperiumAPI()
        order = Order(123, "2663000001", "4000001", 10, "ADESAO - INSTALAR PONTO VIRTUA")
        context = DetailContext(order.id_os, order.contract, 313363, "TECNICO TESTE")
        catalog = [
            StockMaterial(1, "433135", "ITEM A", 1, 260, "UN", 2, "N"),
            StockMaterial(2, "433136", "ITEM B", 1, 260, "UN", 2, "N"),
        ]
        client = MagicMock()
        client.__enter__.return_value = client
        with (
            patch.object(api, "_client", return_value=client),
            patch.object(api, "_fetch_detail_on", return_value=order.num_os.encode()),
            patch.object(api, "_detail_context", return_value=context),
            patch.object(api, "_combined_material_catalog_on", return_value=catalog),
            patch.object(api, "_lookup_equipment_group_by_code_on", return_value=None),
            patch.object(api, "_material_virtual_stock_quantities_on",
                         return_value={"433135": Decimal("3")}),
            patch.object(api, "_transfer_material_shortfalls") as transfer,
        ):
            with self.assertRaisesRegex(ValueError, "433136.*3"):
                api.prepare_official_materials(
                    order,
                    [{"code": "433135", "quantity": 4}, {"code": "433136", "quantity": 4}],
                    expected_installer_id=context.installer_id,
                )
            transfer.assert_not_called()

    def test_one_missing_material_is_not_silently_omitted(self):
        api = ImperiumAPI()
        order = Order(123, "2663000001", "4000001", 10, "ADESAO - INSTALAR PONTO VIRTUA")
        context = DetailContext(order.id_os, order.contract, 313363, "TECNICO TESTE")
        material = StockMaterial(1, "433135", "ITEM A", 1, 260, "UN", 2, "N")
        client = MagicMock()
        client.__enter__.return_value = client
        with (
            patch.object(api, "_client", return_value=client),
            patch.object(api, "_fetch_detail_on", return_value=order.num_os.encode()),
            patch.object(api, "_detail_context", return_value=context),
            patch.object(api, "_combined_material_catalog_on", return_value=[material]),
            patch.object(api, "_lookup_equipment_group_by_code_on", return_value=None),
            patch.object(api, "_material_virtual_stock_quantities_on", return_value={}),
            patch.object(api, "_transfer_material_shortfalls") as transfer,
        ):
            with self.assertRaisesRegex(ValueError, "433135.*3"):
                api.prepare_official_materials(order, [{"code": "433135", "quantity": 4}],
                                               expected_installer_id=context.installer_id)
            transfer.assert_not_called()
