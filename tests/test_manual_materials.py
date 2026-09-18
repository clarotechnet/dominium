import hashlib
import struct
import unittest
from decimal import Decimal

from datasnap_client import DataSnapError
from imperium_api import DetailContext, ImperiumAPI, StockMaterial
from manual_materials import (
    AppliedManualMaterial,
    ManualMaterial,
    decode_fmtdbcd,
    parse_applied_manual_materials,
    parse_manual_material_catalog,
)


def short_text(value: str) -> bytes:
    encoded = value.encode("cp1252")
    return bytes((len(encoded),)) + encoded


def fmtdbcd(value: str, precision: int = 16, scale: int = 2) -> bytes:
    decimal = Decimal(value).scaleb(scale)
    digits = f"{int(decimal):0{precision}d}"
    packed = bytes(int(digits[index : index + 2], 16) for index in range(0, precision, 2))
    return bytes((precision, scale)) + packed + bytes(18 - 2 - len(packed))


def manual_record(
    *,
    stock_id: int,
    equipment_id: int,
    code: str,
    name: str,
    unit: str,
    quantity: str,
    group_id: int,
    group: str,
    business_unit_id: int = 1,
) -> bytes:
    return b"".join(
        (
            struct.pack("<II", stock_id, equipment_id),
            short_text(code),
            short_text(name),
            short_text("N"),
            struct.pack("<I", 6),
            short_text(unit),
            fmtdbcd(quantity),
            struct.pack("<II", business_unit_id, group_id),
            short_text(group),
            bytes(4),
        )
    )


class ManualMaterialParserTests(unittest.TestCase):
    def test_decodes_the_bcd_balance_used_by_recife(self) -> None:
        self.assertEqual(decode_fmtdbcd(fmtdbcd("55")), Decimal("55.00"))
        self.assertEqual(decode_fmtdbcd(fmtdbcd("2")), Decimal("2.00"))

    def test_parses_manual_picker_records(self) -> None:
        payload = b"metadata" + manual_record(
            stock_id=27,
            equipment_id=5292,
            code="22069613",
            name="CONECTOR FO CAMPO FAST SC APC",
            unit="UN",
            quantity="16",
            group_id=10016,
            group="CONECTOR FIBRA",
        ) + manual_record(
            stock_id=27,
            equipment_id=5040,
            code="22064608",
            name="FITA ISOLANTE 3M HIGHLAND 19MM X 20M",
            unit="M",
            quantity="13",
            group_id=10006,
            group="FITA ISOLANTE",
        )

        materials = parse_manual_material_catalog(payload)

        by_code = {item.code: item for item in materials}
        self.assertEqual(len(by_code), 2)
        self.assertEqual(by_code["22069613"].quantity, Decimal("16.00"))
        self.assertEqual(by_code["22069613"].stock_id, 27)
        self.assertEqual(by_code["22069613"].equipment_id, 5292)
        self.assertEqual(by_code["22064608"].unit, "M")

    def test_rejects_payload_without_manual_material_records(self) -> None:
        with self.assertRaises(DataSnapError):
            parse_manual_material_catalog(b"empty dataset")

    def test_preserves_same_code_in_different_business_units(self) -> None:
        payload = b"metadata" + manual_record(
            stock_id=260,
            equipment_id=289,
            code="22056365",
            name="PROTETOR P/MINI ISOLADOR",
            unit="UN",
            quantity="9",
            group_id=288,
            group="PROTETOR P/MINI",
            business_unit_id=2,
        ) + manual_record(
            stock_id=260,
            equipment_id=289,
            code="22056365",
            name="PROTETOR P/MINI ISOLADOR",
            unit="UN",
            quantity="0",
            group_id=288,
            group="PROTETOR P/MINI",
            business_unit_id=1,
        )

        materials = parse_manual_material_catalog(payload)

        self.assertEqual(len(materials), 2)
        self.assertEqual(
            {(item.business_unit_id, item.quantity) for item in materials},
            {(1, Decimal("0.00")), (2, Decimal("9.00"))},
        )

    def test_parses_the_material_row_written_in_apply_updates(self) -> None:
        context = DetailContext(26344, "412773879", 1517, "CESAR LEONARDO")
        material = StockMaterial(
            id_equipment=395,
            code="22057635",
            name="FIXADOR FIO PT RG6",
            stock_quantity=68,
            id_stock=28,
            unit="UN",
            id_unit=1,
            identified="N",
            requested_quantity=32,
        )
        payload = ImperiumAPI._material_row(context, material, -2, False)

        rows = parse_applied_manual_materials(payload)

        self.assertEqual(
            rows,
            [
                AppliedManualMaterial(
                    id_os=26344,
                    equipment_id=395,
                    stock_id=28,
                    temporary_id=-2,
                    name="FIXADOR FIO PT RG6",
                    unit="UN",
                    identified="N",
                    quantity=32,
                    code="22057635",
                    business_unit_id=1,
                )
            ],
        )


class ManualMaterialProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI()

    def test_rebuilds_the_recife_manual_picker_requests(self) -> None:
        query = self.api._manual_material_picker_query(1517)

        self.assertEqual(query, self.api.manual_material_picker_template)
        self.assertEqual(len(query), 332)
        self.assertEqual(
            hashlib.sha256(query).hexdigest(),
            "64918ace7112d11a68714625404a2aaf084b1613314bccff27bacabc73d57b0c",
        )
        self.assertEqual(
            hashlib.sha256(self.api._provider_close_query(query)).hexdigest(),
            "8a223990af52ef5397110458663e0e7abcb38da885c3b5efb9ffbbf60b41597a",
        )

    def test_reconciles_picker_balance_without_losing_unit_id(self) -> None:
        stock = StockMaterial(
            id_equipment=1,
            code="22069613",
            name="INCOMPLETO",
            stock_quantity=0,
            id_stock=1,
            unit="UN",
            id_unit=1,
            identified="N",
        )
        picker = ManualMaterial(
            stock_id=27,
            equipment_id=5292,
            code="22069613",
            name="CONECTOR FO CAMPO FAST SC APC",
            identified="N",
            brand_id=6,
            unit="UN",
            quantity=Decimal("16.00"),
            business_unit_id=1,
            group_id=10016,
            group="CONECTOR FIBRA",
        )

        result = self.api._reconcile_manual_materials([stock], [picker])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id_equipment, 5292)
        self.assertEqual(result[0].id_stock, 27)
        self.assertEqual(result[0].stock_quantity, 16)
        self.assertEqual(result[0].id_unit, 1)
        self.assertEqual(result[0].id_group, 10016)
        self.assertEqual(result[0].group, "CONECTOR FIBRA")

    def test_reconcile_prefers_net_balance_over_claro_duplicate(self) -> None:
        stock = StockMaterial(
            289, "22056365", "PROTETOR", 9, 260, "UN", 1, "N"
        )
        claro = ManualMaterial(
            260, 289, "22056365", "PROTETOR", "N", 6, "UN",
            Decimal("9"), 2, 288, "PROTETOR P/MINI",
        )
        net = ManualMaterial(
            260, 289, "22056365", "PROTETOR", "N", 6, "UN",
            Decimal("0"), 1, 288, "PROTETOR P/MINI",
        )

        result = self.api._reconcile_manual_materials([stock], [claro, net])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].stock_quantity, 0)
        self.assertEqual(result[0].business_unit_id, 1)


if __name__ == "__main__":
    unittest.main()
