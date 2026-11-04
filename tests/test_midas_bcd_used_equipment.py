"""Synthetic-only regression: MIDAS BCD fields observed in Imperium used equipment."""
import json
import struct
import unittest

from integrations.serial_consult.midas_reader import PacketError, _decode_bcd, decode_dataset


def bcd(digits: str, *, scale: int = 2, negative: bool = False) -> bytes:
    """Build a fixed 18-byte legacy TBcd containing 16 significant decimal nibbles."""
    assert len(digits) == 16 and digits.isdecimal()
    return bytes([16, scale | (0x80 if negative else 0)]) + bytes.fromhex(digits + "0" * 16)


def packet(*rows: bytes) -> bytes:
    """One BCD column with misleading metadata size=10; each value uses 18 bytes."""
    header = struct.pack("<IiiHIiH", 0xBDE01996, 1, 18, 1, len(rows), 3, 0)
    field = b"\x03Qtd" + struct.pack("<HHHH", 10, 5, 0, 0)
    return header + field + struct.pack("<H", 0) + b"".join(b"\0\0" + cell for cell in rows)


class BCDTests(unittest.TestCase):
    def test_exact_decimal_string_and_json(self):
        value = _decode_bcd(bcd("0000000000001234"))
        self.assertEqual(value, "12.34")
        self.assertEqual(json.loads(json.dumps({"Qtd":value}))["Qtd"], "12.34")

    def test_negative_and_zero(self):
        self.assertEqual(_decode_bcd(bcd("0000000000000010",negative=True)), "-0.10")
        self.assertEqual(_decode_bcd(bcd("0000000000000000")), "0.00")

    def test_special_blank_returns_none(self):
        self.assertIsNone(_decode_bcd(bytes([0,0x40])+bytes(16)))

    def test_rejects_malformed_decimal_nibbles_and_scale(self):
        for raw in (
            b"\0"*17,
            bytes([0,2])+bytes(16),
            bytes([2,3])+bytes(16),
            bytes([16,2,0xFA])+bytes(15),
        ):
            with self.subTest(raw=raw[:3]), self.assertRaises(PacketError):
                _decode_bcd(raw)

    def test_mid_as_reads_all_records_even_if_declared_size_is_10(self):
        blob = packet(bcd("0000000000001234"), bcd("0000000000000500"))
        rows = decode_dataset(blob)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows, [{"Qtd":"12.34"},{"Qtd":"5.00"}])

    def test_mid_as_rejects_truncated_bcd(self):
        with self.assertRaises(PacketError):
            decode_dataset(packet(bcd("0000000000001234"))[:-4])


if __name__ == "__main__":
    unittest.main()
