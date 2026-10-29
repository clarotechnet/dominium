"""A falta de um item bloqueia antes de qualquer movimentação de RETORNO."""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from imperium_api import DetailContext, ImperiumAPI, Order, StockMaterial


class OfficialMaterialCompletenessTests(unittest.TestCase):
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
