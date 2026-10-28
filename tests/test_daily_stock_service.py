"""Testes isolados sem gravação externa."""
import unittest
from unittest.mock import Mock
from integrations.import_bridge.daily_stock_service import DailyStockService, DailyStockError

class DailyStockTests(unittest.TestCase):
    def create(self):
        obj=DailyStockService.__new__(DailyStockService)
        obj._call=Mock(return_value={"ok":True,"repetido":False,"materiais":1,
                                     "quantidade_total":2})
        return obj
    def payload(self):
        return {"data_estoque":"2026-10-28","nome_arquivo":"SAP.xlsx",
                "hash_arquivo":"a"*64,"linhas_origem":3,
                "items":[{"material":"22025245","descricao_material":"Marcador",
                          "quantidade_livre":"2.000"}]}
    def test_import_rpc_and_server_actor(self):
        service=self.create()
        result=service.store(self.payload(),"gestor")
        self.assertTrue(result["ok"])
        args=service._call.call_args
        self.assertEqual(args.args,("rpc/registrar_estoque_diario",))
        self.assertEqual(args.kwargs["body"]["p_operador"],"gestor")
        self.assertEqual(args.kwargs["body"]["p_linhas"],3)
        self.assertEqual(args.kwargs["method"],"POST")
    def test_duplicate_refused_before_database(self):
        svc=self.create()
        payload=self.payload()
        payload["items"].append(dict(payload["items"][0]))
        with self.assertRaises(DailyStockError) as caught: svc.store(payload,"gestor")
        self.assertEqual(caught.exception.status,400)
        svc._call.assert_not_called()
    def test_invalid_code_and_quantity(self):
        for m,q in [("000+220","3"),("22025245","-5"),("22025245","NaN")]:
            svc=self.create()
            p=self.payload()
            p["items"][0]["material"]=m
            p["items"][0]["quantidade_livre"]=q
            with self.assertRaises(DailyStockError):svc.store(p,"gestor")
            svc._call.assert_not_called()
    def test_empty_history(self):
        svc=DailyStockService.__new__(DailyStockService)
        svc._call=Mock(return_value=[])
        result=svc.view()
        self.assertEqual(result["items"],[])
        self.assertIsNone(result["snapshot"])
        svc._call.assert_called_once()
if __name__=="__main__":unittest.main()
