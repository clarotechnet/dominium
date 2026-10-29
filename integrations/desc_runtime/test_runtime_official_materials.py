import unittest
import threading
from unittest.mock import MagicMock, patch
from imperium_api import ImperiumAPI, Order, DetailContext, StockMaterial


class LegacyMaterialCompletenessTests(unittest.TestCase):
    def test_partial_or_discarded_materials_block_before_transfer(self):
        # This method's I/O boundaries are mocked; protocol files are unrelated.
        api = ImperiumAPI.__new__(ImperiumAPI)
        api._operation_lock = threading.RLock()
        api.material_transfer_source_stock_id = 2
        order = Order(123, '2663000001', '4000001', 10, 'ADESAO - INSTALAR PONTO VIRTUA')
        context = DetailContext(order.id_os, order.contract, 313363, 'TECNICO TESTE')
        client = MagicMock()
        client.__enter__.return_value = client
        for partial, discarded, count in [([{'code':'433135'}],[],1),
                                           ([],[{'code':'433135'}],1),([],[],1)]:
            with self.subTest(partial=partial,discarded=discarded):
                material=StockMaterial(1,'433135','ITEM TESTE',0,260,'UN',2,'N',requested_quantity=3)
                allocation={'transfers':[material], 'partial_shortfalls':partial,
                            'discarded_shortfalls':discarded,'missing_distinct_count':count,
                            'concrete_rows':[], 'groups':[]}
                with (
                    patch.object(api,'_client',return_value=client),
                    patch.object(api,'_fetch_detail_on',return_value=order.num_os.encode()),
                    patch.object(api,'_detail_context',return_value=context),
                    patch.object(api,'_allocate_requested_material_groups_on',return_value=allocation),
                    patch.object(api,'_transfer_material_shortfalls') as transfer,
                ):
                    with self.assertRaisesRegex(ValueError,'Todos os itens do TOA'):
                        api.prepare_official_materials(order,[{'code':'433135','quantity':4}],
                                                       expected_installer_id=313363)
                    transfer.assert_not_called()
