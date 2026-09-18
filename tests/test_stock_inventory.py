import struct
import unittest
from decimal import Decimal
from pathlib import Path

from stock_inventory import (
    StockProtocol,
    attach_serials,
    parse_stock_items,
    parse_stock_serials,
    parse_technicians,
)


def short(value: str) -> bytes:
    data = value.encode("cp1252")
    return bytes([len(data)]) + data


class StockInventoryTests(unittest.TestCase):
    def test_protocol_replaces_stock_id_without_changing_packet_size(self) -> None:
        protocol = StockProtocol((Path(__file__).resolve().parents[1] / "stock_protocol_templates.json"))
        query = protocol.items_query(9876)
        self.assertEqual(len(query), len(protocol.items_template))
        self.assertEqual(
            struct.unpack_from("<I", query, protocol.items_stock_offset)[0],
            9876,
        )

    def test_parse_technician_stock_mapping(self) -> None:
        row = b"".join(
            (
                b"\x01",
                struct.pack("<I", 42),
                short("TECNICO TESTE"),
                struct.pack("<I", 777),
                short("TECNICO TESTE"),
                short("N"),
                short("N"),
                short("N"),
                short("N"),
                short(""),
                b"\x00\x00",
            )
        )
        values = parse_technicians(b"HEADER PRIMARY_KEY" + b"\x00" * 8 + row)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].stock_id, 42)
        self.assertEqual(values[0].installer_id, 777)

    def test_parse_items_and_attach_serial(self) -> None:
        item = b"".join(
            (
                struct.pack("<II", 260, 1),
                short("EMTA"),
                short("41000001"),
                short("EQUIPAMENTO TESTE"),
                struct.pack("<I", 6),
                short("DIVERSOS"),
                struct.pack("<I", 2),
                short("UN"),
                short("S"),
                b"\x00" * 24,
                short("2.00 UN"),
                b"\x00" * 40,
            )
        )
        serial = b"".join(
            (
                struct.pack("<III", 260, 1, 1),
                short("ABC123456"),
                short(""),
                short("N"),
                b"\x00\x00\x00",
            )
        )
        items = parse_stock_items(item)
        serials = parse_stock_serials(serial)
        result = attach_serials(items, serials)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].quantity_number, Decimal("2"))
        self.assertEqual(result[0].serials[0].serial, "ABC123456")


if __name__ == "__main__":
    unittest.main()
