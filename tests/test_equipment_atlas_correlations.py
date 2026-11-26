import unittest
from dataclasses import replace

from imperium_api import StockMaterial

from integrations.desc_runtime.equipment_atlas_correlations import (
    EquipmentAtlasCorrelationError,
    parse_code_group,
    parse_code_record,
    parse_stock_atlas_record,
    stocked_return_group_codes,
)


def record(code: str, description: str, *, leading_nul: bool = True) -> bytes:
    name = b"MATERIAL CADASTRADO"
    raw = description.encode("latin1")
    return (
        b"\x08" + code.encode("ascii") + bytes([len(name)]) + name
        + len(raw).to_bytes(2 if leading_nul else 1, "little") + raw
    )


class EquipmentAtlasCorrelationsTests(unittest.TestCase):
    def test_exact_record_may_list_only_an_alias(self):
        payload = record("22024800", "22025321_ANEL VEDACAO PLASTICA P PORTA F")
        self.assertEqual(parse_code_group(payload, "22024800"), ("22024800", "22025321"))

    def test_group_label_contributes_no_code_and_aliases_keep_their_order(self):
        payload = record(
            "22065719",
            "MARCADOR CASA PTO NR 1 | 22056343_MARCADOR CASA PTO NR 1 | "
            "22065719_MARCADOR CASA PRETO NR 1 | 22066615_MARCADOR CASA PRETO NR 1",
        )
        self.assertEqual(
            parse_code_group(payload, "22065719"), ("22065719", "22056343", "22066615"),
        )

    def test_standard_record_and_optional_nul(self):
        original = "22066906_CABO TRISH | 22026223_CABO COAXIAL | 22026223_CABO COAXIAL"
        for leading_nul in (False, True):
            with self.subTest(leading_nul=leading_nul):
                payload = record("22066906", original, leading_nul=leading_nul)
                self.assertEqual(parse_code_group(payload, "22066906"), ("22066906", "22026223"))

    def test_reads_midas_separator_before_the_atlas_underscore(self):
        payload = record(
            "22065723", "22026331\x1f_MARCADOR CASA PTO NR 5 | "
            "22065723_MARCADOR CASA PRETO NR 5 | 22066611_MARCADOR CASA PRETO NR 5",
        ) + b"\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00\x02UN"
        result = parse_code_record(payload, "22065723")
        self.assertEqual(result.codes, ("22065723", "22026331", "22066611"))
        self.assertEqual(result.unit, "UN")
        for invalid in (b"22026331\x1e_", b"22026331_\x1f", b"22026331\x1f\x1f_"):
            with self.assertRaises(EquipmentAtlasCorrelationError):
                parse_code_record(payload.replace(b"22026331\x1f_", invalid), "22065723")

    def test_reads_the_unit_from_the_exact_record(self):
        payload = record("22066906", "22026223_CABO COAXIAL")
        group_and_unit_id = b"\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00"
        result = parse_code_record(payload + group_and_unit_id + b"\x01M", "22066906")
        self.assertEqual(result.codes, ("22066906", "22026223"))
        self.assertEqual(result.unit, "M")
        self.assertEqual(parse_code_record(payload + group_and_unit_id + b"\x02M", "22066906").unit, "")

    def test_reads_long_midas_atlas_description_and_exact_trailer(self):
        description = " | ".join((
            "22056394_ISOLADOR CASA SURGE PROTEC 1G NET",
            "22056126_ISOLADOR CASA SURGE PROTEC 1G",
            "22056691_ISOLADOR CASA SURGE PROTEC 1G NET",
            "22066517_ISOLADOR CASA SURGE PROTEC LOW COST",
            "22025985_ISOLADOR CASA SURGE PROTECTOR",
            "22026041_ISOLADOR COAX QUADRADO CISP-HR",
            "22056366_ISOLADOR COAXIAL QUADRADO - CISP-HR",
            "22056689_ISOLADOR COAXIAL QUADRADO - CISP-HR",
        ))
        self.assertEqual(len(description), 352)
        trailer = b"\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00\x02UN"
        encoded = record("22056394", description)
        result = parse_code_record(encoded + trailer, "22056394")
        self.assertEqual(result.codes, tuple(item.split("_")[0] for item in description.split(" | ")))
        self.assertEqual(result.unit, "UN")
        for malformed in (encoded, encoded + trailer[:-1], encoded.replace(b"\x60\x01", b"\x61\x01") + trailer):
            with self.assertRaisesRegex(EquipmentAtlasCorrelationError, "22056394"):
                parse_code_record(malformed, "22056394")

        exactly_256 = "22056394_" + "A" * 119 + " | 22056689_" + "B" * 116
        self.assertEqual(len(exactly_256), 256)
        self.assertEqual(
            parse_code_record(record("22056394", exactly_256) + trailer, "22056394").codes,
            ("22056394", "22056689"),
        )

    def test_unusable_or_ambiguous_exact_records_are_rejected(self):
        valid = record("22024800", "22025321_ANEL VEDACAO PLASTICA")
        for payload in (
            record("22024801", "22024800_ANEL VEDACAO PLASTICA"),
            record("22024800", "ANEL VEDACAO PLASTICA"),
            record("22024800", "2202532_ANEL VEDACAO | 22024800_ANEL VEDACAO"),
            record("22024800", "22025321_ANEL VEDACAO | ITEM SEM CODIGO"),
            record("22024800", "22025321_ANEL\x00VEDACAO"),
            valid[:-1],
            valid + record("22024800", "22025322_OUTRO ANEL VEDACAO"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(EquipmentAtlasCorrelationError, "22024800"):
                    parse_code_group(payload, "22024800")


    def test_confirmed_connector_without_atlas_description(self):
        def empty(code, name, unit):
            raw = name.encode("ascii")
            return (b"\x08" + code.encode("ascii") + bytes([len(raw)]) + raw
                    + b"\x00\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00"
                    + bytes([len(unit)]) + unit.encode("ascii"))
        good = empty("22026266", "CONECTOR FO CAMPO FAST SC APC", "UN")
        parsed = parse_code_record(good, "22026266")
        self.assertEqual(parsed.unit, "UN")
        self.assertEqual(parsed.codes[0], "22026266")
        self.assertIn("22056396", parsed.codes)
        for bad in (
            empty("22025102", "CONECTOR FO CAMPO FAST SC APC", "UN"),
            empty("22026266", "OUTRO MATERIAL", "UN"),
            empty("22026266", "CONECTOR FO CAMPO FAST SC APC", "M"),
            good + good,
        ):
            with self.assertRaises(EquipmentAtlasCorrelationError):
                parse_code_record(bad, "22026266")

    def test_live_empty_atlas_field_with_extra_nul(self):
        record = b"\x0822025349\x1bFIXA FIO CABO DROP FO CHATO\x00\x00\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00\x02UN"
        self.assertEqual(parse_code_record(record, "22025349").codes, ("22025349",))
        self.assertEqual(parse_code_record(record, "22025349").unit, "UN")
        connector = b"\x0822026266\x1dCONECTOR FO CAMPO FAST SC APC\x00\x00\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00\x02UN"
        self.assertIn("22065513", parse_code_record(connector, "22026266").codes)
        for bad in (record + record, record[:-1], record.replace(b"DIVERSOS", b"INVALIDO")):
            with self.assertRaises(EquipmentAtlasCorrelationError):
                parse_code_record(bad, "22025349")

    def test_return_group_requires_full_catalogue_identity_and_fresh_balance(self):
        name = "FIXADOR FIO BR RG6 CIRCUL 7MM"
        reference = StockMaterial(1, "22060738", name, 0, 12, "UN", 2, "N",
                                  id_group=36, group="FIXADOR BR")
        equivalent = replace(reference, code="22025139", id_equipment=2, stock_quantity=24)
        wrong_items = [
            replace(equivalent, code="22025091", group="FIXADOR PT", id_group=37),
            replace(equivalent, code="22057635", name=name.replace("7MM", "6MM")),
            replace(equivalent, code="22025349", unit="M"),
            replace(equivalent, code="22025350", identified="S"),
        ]
        inventory = {item.code: item for item in [reference, equivalent, *wrong_items]}
        balances = {item.code: item.stock_quantity for item in inventory.values()}
        self.assertEqual(stocked_return_group_codes(reference, f"22060738_{name}", inventory, balances),
                         (equivalent.code,))
        self.assertEqual(stocked_return_group_codes(reference, "FIXADOR", inventory, balances), ())
        self.assertEqual(stocked_return_group_codes(None, name, inventory, balances), ())
        balances[equivalent.code] = 0
        self.assertEqual(stocked_return_group_codes(reference, name, inventory, balances), ())

    def test_stock_lookup_distinguishes_confirmed_empty_from_invalid_or_ambiguous(self):
        empty = b'\xc0\xc0\x60\xc0\xc0\xc0\x10\x00\x05\x02\x00\x00' + bytes(1108)
        self.assertEqual(parse_stock_atlas_record(empty, '22066630').codes, ())
        duplicate = record('22066630', '22066630_ACOPLADOR VERTICAL') * 2
        for invalid in (empty[:-1], empty.replace(b'\x60', b'\x61', 1), duplicate):
            with self.assertRaises(EquipmentAtlasCorrelationError):
                parse_stock_atlas_record(invalid, '22066630')
