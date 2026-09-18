import hashlib
import struct
import unittest
from unittest.mock import Mock
from decimal import Decimal
from pathlib import Path

from datasnap_client import DataSnapError
from imperium_api import DetailContext, ImperiumAPI, Order, normalize_text


ROOT = Path(__file__).resolve().parents[1]


class MaterialWriteoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api = ImperiumAPI(ROOT, controller_id=313101)

    def test_quantity_one_matches_captured_bcd(self) -> None:
        self.assertEqual(
            self.api._encode_material_quantity("1").hex(),
            "100200000000000001000000000000000000",
        )

    def test_quantity_with_decimals_uses_two_decimal_places(self) -> None:
        self.assertEqual(
            self.api._encode_material_quantity(Decimal("448.00")).hex(),
            "100200000000000448000000000000000000",
        )
        self.assertEqual(
            self.api._encode_material_quantity("0,25").hex(),
            "100200000000000000250000000000000000",
        )


    def test_delta_record_transforms_match_the_official_material_layout(self) -> None:
        tail = (
            self.api._short_text("750")
            + b"\x00"
            + self.api._short_text("LAGOA AZUL")
            + self.api._short_text("RN")
            + b"\x00"
            + self.api._short_text("59135000")
            + b"\x00\x00\x00\x00\x01"
            + b"RESTO"
            + b"\x00" * 20
        )
        record = (
            b"CAB"
            + self.api.material_header_old
            + b"Q"
            + self.api.material_quantity_old
            + b"V"
            + self.api.material_values_old
            + tail
        )
        modified = self.api._prepare_material_delta_record(record)
        self.assertEqual(len(modified), len(record) + 6)
        self.assertIn(self.api.material_header_new, modified)
        self.assertIn(self.api.material_quantity_new, modified)
        self.assertIn(self.api.material_values_new, modified)
        self.assertIn(
            self.api._short_text("750")
            + b"\x01\x00"
            + self.api._short_text("LAGOA AZUL")
            + self.api._short_text("RN")
            + b"\x01\x00"
            + self.api._short_text("59135000")
            + b"\x01\x00\x01\x00\x01\x00\x01\x00\x01",
            modified,
        )

    def test_material_row_matches_the_validated_capture(self) -> None:
        context = DetailContext(
            id_os=2162618,
            contract="",
            installer_id=3360,
            installer_name="JOSE AUGUSTO MDU",
        )
        material = {
            "stock_id": 258,
            "equipment_id": 5137,
            "equipment": "CABO DROP 1FO LOW F FIG8 LOW CINZA",
            "unit": "M",
            "identified": "N",
            "code": "22061736",
            "business_unit_id": 1,
            "quantity": "1.00",
        }
        expected = bytes.fromhex(
            "0400a8a00aa002"
            "baff2000"
            "11140000"
            "02010000"
            "ffffffff"
            "224341424f2044524f502031464f204c4f5720462046494738204c4f572043494e5a41"
            "014d"
            "014e"
            "100200000000000001000000000000000000"
            "083232303631373336"
            "01000000"
            "014e"
        )
        self.assertEqual(
            self.api._writeoff_material_row(context, material, -1), expected
        )

    def test_material_suffix_preserves_captured_productive_controller(self) -> None:
        self.assertIn(struct.pack("<I", 325722), self.api.material_close_suffix)
        self.assertNotIn(struct.pack("<I", 313101), self.api.material_close_suffix)
        self.assertEqual(self.api.material_controller_id, 325722)
        self.assertIn(b"400", self.api.material_close_suffix)
        self.assertIn("CORREÇÃO DE CADASTRO".encode("cp1252"), self.api.material_close_suffix)
        self.assertIn(b"BAIXA", self.api.material_close_suffix)

    def test_multiple_material_rows_match_captured_nested_layout(self) -> None:
        context = DetailContext(2163340, "32131231232", 3606, "ELIZEU")
        materials = [
            {
                "stock_id": 240,
                "equipment_id": 5136,
                "equipment": "CABO FO CFOA SM DROP FIG8 8FO",
                "unit": "UN",
                "identified": "N",
                "code": "22012583",
                "business_unit_id": 1,
                "quantity": "120",
            },
            {
                "stock_id": 240,
                "equipment_id": 485,
                "equipment": "ABRACADEIRA HELLERMANN T50R-PT",
                "unit": "UN",
                "identified": "N",
                "code": "22055828",
                "business_unit_id": 1,
                "quantity": "15",
            },
            {
                "stock_id": 240,
                "equipment_id": 3378,
                "equipment": "KIT TUBO DERIVACAO FOSC 30/8- CS2280-000",
                "unit": "UN",
                "identified": "N",
                "code": "22056444",
                "business_unit_id": 1,
                "quantity": "1",
            },
            {
                "stock_id": 240,
                "equipment_id": 5126,
                "equipment": "CAIXA DIO NAP MDU PS DIV 1:8 4 PIGTAIL",
                "unit": "UN",
                "identified": "N",
                "code": "22068044",
                "business_unit_id": 1,
                "quantity": "2",
            },
            {
                "stock_id": 240,
                "equipment_id": 5021,
                "equipment": "PROTETOR_FO TERMOCONTR. 45MM",
                "unit": "UN",
                "identified": "N",
                "code": "30033493",
                "business_unit_id": 1,
                "quantity": "5",
            },
        ]
        rows = b"".join(
            self.api._writeoff_material_row(
                context,
                material,
                -index,
                followed_by_row=index < len(materials),
            )
            for index, material in enumerate(materials, start=1)
        )
        captured_layout = struct.pack("<I", len(materials)) + rows

        self.assertEqual(captured_layout.count(self.api.material_row_prefix), 5)
        self.assertEqual(
            hashlib.sha256(captured_layout).hexdigest(),
            "e98a29e71ea1d9ee843d05073c28c02d94c365658432a355acb6a25b8b74d838",
        )

    def test_material_preflight_patches_installer_in_three_call_sequence(self) -> None:
        reset_before, query, reset_after = self.api._material_preflight_for(3660)

        self.assertEqual(reset_before, reset_after)
        self.assertEqual(
            struct.unpack_from(
                "<I",
                reset_before,
                self.api.material_preflight_reset_offset,
            )[0],
            3660,
        )
        self.assertEqual(
            struct.unpack_from(
                "<I",
                query,
                self.api.material_preflight_query_offset,
            )[0],
            3660,
        )
        self.assertIn(b"DspBaixarMiscelaneasRomaneio", reset_before)
        self.assertIn(b"DspBaixarMiscelaneasRomaneio", query)
        self.assertNotEqual(reset_before, query)

    def test_material_preflight_uses_one_handle_for_reset_query_reset(self) -> None:
        api = ImperiumAPI(ROOT, controller_id=313101)
        client = Mock()
        api._handle = Mock(return_value=7)
        api._dataset_payload = Mock(return_value=b"dataset")

        api._run_material_preflight(client, 3660)

        api._handle.assert_called_once_with(client, api.material_preflight_method)
        calls = api._dataset_payload.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call.args[1] == 7 for call in calls))
        self.assertEqual(calls[0].args[2], calls[2].args[2])
        self.assertNotEqual(calls[0].args[2], calls[1].args[2])

    def test_normalize_text_preserves_accented_names(self) -> None:
        self.assertEqual(normalize_text("JOSÉ ÁUGUSTO MDU"), "JOSE AUGUSTO MDU")

    def test_invalid_or_serial_material_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.api._encode_material_quantity("0")
        context = DetailContext(1, "", 1, "TECNICO")
        material = {
            "stock_id": 1,
            "equipment_id": 2,
            "equipment": "MODEM",
            "unit": "UN",
            "identified": "S",
            "code": "ABC",
            "quantity": "1",
        }
        with self.assertRaises(ValueError):
            self.api._writeoff_material_row(context, material, -1)

    def test_quick_writeoff_validates_stock_and_confirms_new_balance(self) -> None:
        api = ImperiumAPI(ROOT, controller_id=313101)
        before = {
            "technician": {
                "stock_id": 258,
                "installer_id": 3360,
                "technician_name": "JOSE AUGUSTO MDU",
            },
            "items": [
                {
                    "equipment_id": 5137,
                    "code": "22061736",
                    "equipment": "CABO DROP",
                    "group": "CABOS",
                    "brand": "",
                    "unit": "M",
                    "identified": "N",
                    "quantity": "10",
                    "quantity_label": "10 M",
                    "serials": [],
                }
            ],
            "summary": {},
        }
        after = {
            **before,
            "items": [{**before["items"][0], "quantity": "8", "quantity_label": "8 M"}],
        }
        api.technician_stock = Mock(side_effect=[before, after])
        api._create_correction_order = Mock(
            return_value=Order(2162618, "213213131", "23213123", 1, "CORRECAO ESTOQUE")
        )
        api._apply_materials = Mock(
            return_value={"ok": True, "apply_confirmed": True, "apply_after_timeout": False}
        )
        api._append_material_audit = Mock()

        result = api.quick_material_writeoff(
            258, [{"equipment_id": 5137, "quantity": "2"}]
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["stock_confirmed"])
        self.assertEqual(result["num_os"], "213213131")
        self.assertEqual(result["materials"][0]["quantity_after"], "8")
        api._create_correction_order.assert_called_once_with("JOSE AUGUSTO MDU")
        api._apply_materials.assert_called_once()
        api._append_material_audit.assert_called_once()


    def test_stock_balance_confirms_writeoff_after_apply_timeout(self) -> None:
        api = ImperiumAPI(ROOT, controller_id=313101)
        item = {
            "equipment_id": 5137,
            "code": "22061736",
            "equipment": "CABO DROP",
            "group": "CABOS",
            "brand": "",
            "unit": "M",
            "identified": "N",
            "quantity": "10",
            "quantity_label": "10 M",
            "serials": [],
        }
        before = {
            "technician": {
                "stock_id": 258,
                "installer_id": 3360,
                "technician_name": "JOSE AUGUSTO MDU",
            },
            "items": [item],
            "summary": {},
        }
        after = {**before, "items": [{**item, "quantity": "9", "quantity_label": "9 M"}]}
        api.technician_stock = Mock(side_effect=[before, after])
        api._create_correction_order = Mock(
            return_value=Order(2162618, "213213131", "23213123", 1, "CORRECAO ESTOQUE")
        )
        api._apply_materials = Mock(
            side_effect=DataSnapError(
                "A OS 213213131 foi criada, mas o servidor nao confirmou a baixa do material"
            )
        )
        api._append_material_audit = Mock()

        result = api.quick_material_writeoff(
            258, [{"equipment_id": 5137, "quantity": "1"}]
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["stock_confirmed"])
        self.assertFalse(result["apply_confirmed"])
        self.assertTrue(result["apply_after_timeout"])

    def test_correction_order_uses_fixed_service_and_selected_technician(self) -> None:
        api = ImperiumAPI(ROOT, controller_id=313101)
        created = Order(90, "900123456", "80123456", 1, "CORRECAO ESTOQUE")
        api.import_toa = Mock(
            return_value={
                "orders": [{"imported": True, "import_status": "Importado"}]
            }
        )
        api.list_orders = Mock(return_value=[created])
        api._correction_identifiers = Mock(return_value=(created.num_os, created.contract))

        result = api._create_correction_order("JOSE AUGUSTO MDU")

        self.assertEqual(result, created)
        preview = api.import_toa.call_args.args[0]
        order = preview.orders[0]
        self.assertEqual(order.technician, "JOSE AUGUSTO MDU")
        self.assertEqual(order.os_type, "CORRECAO ESTOQUE")
        self.assertEqual(order.time_window, "VT - PRIORIDADE")
        self.assertEqual(order.os_number, created.num_os)

    def test_correction_order_confirms_creation_after_import_timeout(self) -> None:
        api = ImperiumAPI(ROOT, controller_id=313101)
        created = Order(90, "900123456", "80123456", 1, "CORRECAO ESTOQUE")
        api.import_toa = Mock(side_effect=DataSnapError("timed out"))
        api.list_orders = Mock(return_value=[created])
        api._correction_identifiers = Mock(
            return_value=(created.num_os, created.contract)
        )

        result = api._create_correction_order("JOSE AUGUSTO MDU")

        self.assertEqual(result, created)
        api.import_toa.assert_called_once()
        api.list_orders.assert_called_once()



if __name__ == "__main__":
    unittest.main()
