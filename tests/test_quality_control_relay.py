import unittest
from unittest.mock import Mock
from integrations.import_bridge.quality_control_relay import QualityControlService, QualityControlError

class QualityRelayTests(unittest.TestCase):
    def test_textual_quantity_and_update(self):
        service=QualityControlService.__new__(QualityControlService)
        service._request=Mock(return_value=[{'id':4,'material':'0123','descricao_material':'Roteador','qtd_controle_qualidade':'variável'}])
        result=service.save_item({'id':4,'material':'0123','descricao_material':'Roteador','qtd_controle_qualidade':'variável'},'gestor')
        self.assertEqual(result['item']['material'],'0123')
        args=service._request.call_args
        self.assertEqual(args.args[0],'PATCH')
        self.assertEqual(args.kwargs['query']['id'],'eq.4')
        self.assertEqual(args.kwargs['payload']['atualizado_por'],'gestor')
    def test_role_independent_input_sanitization(self):
        service=QualityControlService.__new__(QualityControlService)
        service._request=Mock()
        for item in [{'material':'ABC','descricao_material':'R','qtd_controle_qualidade':''},{'material':'../hack','descricao_material':'R','qtd_controle_qualidade':'2'}]:
            with self.assertRaises(QualityControlError):
                service.save_item(item,'operador')
        service._request.assert_not_called()
    def test_update_missing_conflict(self):
        service=QualityControlService.__new__(QualityControlService)
        service._request=Mock(return_value=[])
        with self.assertRaises(QualityControlError) as raised:
            service.save_item({'id':7,'material':'123','descricao_material':'Cabo','qtd_controle_qualidade':'2'},'operador')
        self.assertEqual(raised.exception.status,409)

if __name__=='__main__':unittest.main()
