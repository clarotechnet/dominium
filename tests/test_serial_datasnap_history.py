"""Safe synthetic tests: no actual serials, credentials or captured client rows."""
import os
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"
sys.path.insert(0, str(ROOT))
from midas_reader import decode_dataset, PacketError
from serial_datasnap import prepare_queries
from serial_service import parse_route, consult_serials


def sample_packet():
    fields = [("Serial", 1, 0x49), ("Id", 4, 0x01), ("Data", 16, 0x11)]
    packet = bytearray(struct.pack("<IiiHIiH", 0xBDE01996, 2, 24, 3, 1, 3, 0))
    for name, size, kind in fields:
        raw = name.encode("ascii")
        packet += bytes([len(raw)]) + raw + struct.pack("<HHHH", size, kind, 0, 0)
    packet += struct.pack("<H", 0)  # packet props
    packet += b"\x04\x00"  # inserted row, 1 status byte
    packet += b"\x0c" + b"SERIAL000000"
    packet += struct.pack("<i", 67)
    packet += struct.pack("<8H", 2026, 10, 21, 14, 15, 16, 0, 0)
    return bytes(packet)


class SerialHistoryTests(unittest.TestCase):
    def test_midas_packet_decodes_full_schema_and_date(self):
        row = decode_dataset(sample_packet())[0]
        self.assertEqual(row["Serial"], "SERIAL000000")
        self.assertEqual(row["Id"], 67)
        self.assertEqual(row["Data"], "2026-10-21T14:15:16")

    def test_invalid_packet_rejected(self):
        with self.assertRaises(PacketError):
            decode_dataset(b"not-mid")
        with self.assertRaises(PacketError):
            decode_dataset(sample_packet()[:-4])

    def test_templates_are_mode_specific_and_placeholder_free(self):
        a, boxa = prepare_queries("SERIAL000000", "analitico")
        s, boxs = prepare_queries("SERIAL000000", "sintetico")
        self.assertEqual((len(a), len(boxa)), (572, 219))
        self.assertEqual((a[169], s[169], boxa[174], boxs[174]), (65, 83, 65, 83))
        self.assertNotIn(b"SERIAL000000", a)
        self.assertIn("SERIAL000000".encode("utf-16le"), a)
        self.assertEqual(a[:169], s[:169])
        with self.assertRaises(ValueError):
            prepare_queries("DROP TABLE", "analitico")

    def test_route_restricts_to_read_only(self):
        self.assertEqual(parse_route("GET", "/api/serials/consult?serials=SERIAL000000&mode=analitico&profile=natal"),
                         (["SERIAL000000"], "analitico", "natal"))
        self.assertIsNone(parse_route("POST", "/api/serials/consult?serials=SERIAL000000"))
        with self.assertRaises(ValueError):
            parse_route("GET", "/api/serials/consult?serials=SERIAL000000&profile=natal&profile=recife")

    def test_no_false_current_possession_or_fake_movements(self):
        mock_hist = {"count": 1, "movements": [{
            "Id": 42, "Data": "2026-10-20T13:15:00", "IdEstoqueDestino": 0,
            "EstDestino": "Ultimo destino", "Movimento": "TRANSFERENCIA"
        }], "boxes": [], "mode": "analitico"}
        with patch("serial_service.fetch_serial_history", return_value=mock_hist), patch(
            "serial_service.local_references", return_value=[]
        ):
            response = consult_serials((["SERIAL000000"], "analitico", "natal"))
        entry = response["results"][0]
        self.assertFalse(entry["live"]["verified"])
        self.assertFalse(entry["live"]["found"])
        self.assertEqual(entry["datasnap"]["count"], 1)
        self.assertEqual(entry["last_destination"]["stock_name"], "Ultimo destino")


if __name__ == "__main__":
    unittest.main()
