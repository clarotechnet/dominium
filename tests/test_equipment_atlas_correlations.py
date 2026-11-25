import unittest

from integrations.desc_runtime.equipment_atlas_correlations import (
    EquipmentAtlasCorrelationError,
    parse_code_group,
    parse_code_record,
)


def record(code: str, description: str, *, leading_nul: bool = True) -> bytes:
    name = b"MATERIAL CADASTRADO"
    raw = description.encode("latin1")
    return (
        b"\x08" + code.encode("ascii") + bytes([len(name)]) + name
        + bytes([len(raw)]) + (b"\x00" if leading_nul else b"") + raw
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

    def test_reads_the_unit_from_the_exact_record(self):
        payload = record("22066906", "22026223_CABO COAXIAL")
        group_and_unit_id = b"\x06\x00\x00\x00\x08DIVERSOS\x02\x00\x00\x00"
        result = parse_code_record(payload + group_and_unit_id + b"\x01M", "22066906")
        self.assertEqual(result.codes, ("22066906", "22026223"))
        self.assertEqual(result.unit, "M")
        self.assertEqual(parse_code_record(payload + group_and_unit_id + b"\x02M", "22066906").unit, "")

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
