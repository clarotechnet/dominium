import unittest
from unittest.mock import Mock
from quality_control import QualityControlStore, validate_quality_item


class QualityControlTests(unittest.TestCase):
    def test_numeric_and_textual_quantities_are_preserved(self):
        for quantity in ("0", "2", "menor que 4", "variável"):
            result = validate_quality_item({
                "material": "22026210", "descricao_material": "Cabo HDMI",
                "qtd_controle_qualidade": quantity,
            })
            self.assertEqual(result["qtd_controle_qualidade"], quantity)

    def test_rejects_invalid_material_or_empty_rule(self):
        with self.assertRaises(ValueError):
            validate_quality_item({"material": "a b", "descricao_material": "Cabo", "qtd_controle_qualidade": "2"})
        with self.assertRaises(ValueError):
            validate_quality_item({"material": "123", "descricao_material": "Cabo", "qtd_controle_qualidade": ""})

    def test_update_uses_id_not_material_as_primary_key(self):
        response = Mock()
        response.data = [{"id": 7, "material": "123", "descricao_material": "Novo", "qtd_controle_qualidade": "4"}]
        client = Mock()
        client.table.return_value.update.return_value.eq.return_value.execute.return_value = response
        row = QualityControlStore(client).save_item({
            "id": 7, "material": "123", "descricao_material": "Novo",
            "qtd_controle_qualidade": "4",
        }, user="operador")
        self.assertEqual(row["id"], 7)
        client.table.assert_called_once_with("controle_qualidade_materiais")
        self.assertEqual(client.table.return_value.update.call_args.args[0]["atualizado_por"], "operador")
        client.table.return_value.update.return_value.eq.assert_called_once_with("id", 7)


if __name__ == "__main__":
    unittest.main()
