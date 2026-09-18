import hashlib
import socket
import struct
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from imperium_api import DetailContext, ImperiumAPI
from serialized_transfer import (
    SerializedTransferProtocol,
    SerializedTransferUncertainError,
)


ROOT = Path(__file__).resolve().parents[1]


def captured_values() -> dict:
    return {
        "controller_id": 313101,
        "source_stock_id": 174,
        "source_stock_name": "GABRIEL SENA  DESC",
        "source_installer_id": 188944,
        "source_technician_name": "GABRIEL LUCAS AGOSTINHO SENA",
        "target_stock_id": 219,
        "target_stock_name": "GABRIEL BRITO DESC",
        "target_installer_id": 277376,
        "target_technician_name": "GABRIEL DE MORAIS BRITO",
        "equipment_id": 5241,
        "equipment_code": "41001620",
        "equipment_name": "DECODER 4K UHD FULL IP S4KW5",
        "brand_id": 6,
        "brand": "DIVERSOS",
        "unit_id": 2,
        "unit": "UN",
        "identified": "S",
        "serial": "241786018496",
    }


class SerializedTransferProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = SerializedTransferProtocol(
            ROOT / "serialized_transfer_protocol_templates.json"
        )

    def test_reconstructs_the_official_captured_packet_exactly(self) -> None:
        packet = self.protocol.build_apply(
            captured_values(),
            timestamp=self.protocol.captured_timestamp,
        )

        self.assertEqual(packet, self.protocol.template)
        self.assertEqual(
            hashlib.sha256(packet).hexdigest(),
            "233f7484910f7091a3129927b49b39774ef56585fac216f0d6e827dbd7b675fb",
        )

    def test_resizes_strings_and_updates_all_packet_lengths(self) -> None:
        values = captured_values()
        values.update(
            {
                "source_stock_id": 101,
                "source_stock_name": "ORIGEM CURTA",
                "source_installer_id": 1001,
                "source_technician_name": "TECNICO DE ORIGEM",
                "target_stock_id": 202,
                "target_stock_name": "DESTINO COM NOME MAIOR DESC",
                "target_installer_id": 2002,
                "target_technician_name": "TECNICO RESPONSAVEL PELO DESTINO",
                "equipment_id": 321,
                "equipment_code": "41000001",
                "equipment_name": "EQUIPAMENTO DE TESTE",
                "brand_id": 4,
                "brand": "MARCA TESTE",
                "unit_id": 2,
                "serial": "ABC123456789",
            }
        )

        packet = self.protocol.build_apply(values)

        self.assertTrue(packet.startswith(b"#Dsp"))
        body = packet[4:]
        self.assertEqual(struct.unpack_from("<I", body, 4)[0], len(body) - 23)
        for text in (
            "ORIGEM CURTA",
            "DESTINO COM NOME MAIOR DESC",
            "TECNICO RESPONSAVEL PELO DESTINO",
            "EQUIPAMENTO DE TESTE",
            "ABC123456789",
        ):
            encoded = text.encode("cp1252")
            self.assertIn(bytes((len(encoded),)) + encoded, packet)

    def test_rejects_an_incomplete_transfer(self) -> None:
        values = captured_values()
        values.pop("serial")

        with self.assertRaisesRegex(ValueError, "serial"):
            self.protocol.build_apply(values)


class SerializedTransferAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI(ROOT, profile_key="natal")
        self.source = {
            "stock_id": 10,
            "stock_name": "ORIGEM DESC",
            "installer_id": 100,
            "technician_name": "TECNICO ORIGEM",
        }
        self.target = {
            "stock_id": 20,
            "stock_name": "DESTINO DESC",
            "installer_id": 200,
            "technician_name": "TECNICO DESTINO",
        }
        self.item = {
            "equipment_id": 300,
            "group_id": 4,
            "code": "41000001",
            "equipment": "DECODER TESTE",
            "brand_id": 6,
            "brand": "DIVERSOS",
            "unit_id": 2,
            "unit": "UN",
            "identified": "S",
        }
        self.stock_serial = {
            "equipment_id": 300,
            "group_id": 4,
            "business_unit_id": 1,
            "serial": "241700000001",
            "smart": "",
            "boxed": "N",
        }
        self.preview = {
            "id_os": 1234,
            "contract": "1234567",
            "requested_serial": "241700000001",
            "serial": "241700000001",
            "source": self.source,
            "target": self.target,
            "equipment": {
                "equipment_id": 300,
                "brand_id": 6,
                "unit_id": 2,
            },
            "stock_serial": self.stock_serial,
        }
        self.before = {
            "source_has_serial": True,
            "target_has_serial": False,
            "source_match": {
                "item": self.item,
                "stock_serial": self.stock_serial,
            },
            "target_match": None,
        }
        self.after = {
            "source_has_serial": False,
            "target_has_serial": True,
            "source_match": None,
            "target_match": {
                "item": self.item,
                "stock_serial": self.stock_serial,
            },
        }

    def _patch_transfer(self, states, client):
        return (
            patch.object(self.api, "_fetch_detail", return_value=b"detail"),
            patch.object(
                self.api,
                "_detail_context",
                return_value=DetailContext(1234, "1234567", 200, "TECNICO DESTINO"),
            ),
            patch.object(
                self.api,
                "list_stock_technicians",
                return_value=[self.source, self.target],
            ),
            patch.object(
                self.api,
                "_serialized_transfer_state",
                side_effect=states,
            ),
            patch.object(
                self.api.serialized_transfer_protocol,
                "build_apply",
                return_value=b"#Dsp-packet",
            ),
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_handle", side_effect=[11, 12]),
        )

    def test_sends_each_write_once_and_requires_stock_confirmation(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        patches = self._patch_transfer([self.before, self.after], client)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = self.api.transfer_serialized_equipment(self.preview)

        self.assertTrue(result["ok"])
        self.assertFalse(result["confirmed_after_error"])
        self.assertEqual(client.request.call_count, 2)
        methods = [
            call.args[0]
            for call in client.request.call_args_list
        ]
        self.assertEqual(methods, ["execute", "execute"])

    def test_timeout_is_success_only_when_the_target_stock_confirms(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.side_effect = socket.timeout("timed out")
        patches = self._patch_transfer([self.before, self.after], client)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = self.api.transfer_serialized_equipment(self.preview)

        self.assertTrue(result["ok"])
        self.assertTrue(result["confirmed_after_error"])
        self.assertEqual(client.request.call_count, 1)

    def test_unconfirmed_timeout_is_never_repeated(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.side_effect = socket.timeout("timed out")
        unchanged = dict(self.before)
        patches = self._patch_transfer(
            [self.before, unchanged, unchanged, unchanged],
            client,
        )

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch("imperium_api.time.sleep"),
            self.assertRaises(SerializedTransferUncertainError),
        ):
            self.api.transfer_serialized_equipment(self.preview)

        self.assertEqual(client.request.call_count, 1)


class Close404Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI(ROOT, profile_key="natal")

    def test_404_requires_and_embeds_a_runtime_observation(self) -> None:
        definition = self.api.close_code("404")
        self.assertTrue(definition.requires_observation)
        suffix = self.api._suffix_with_observation(
            definition.suffixes[0],
            definition,
            "Cliente recusou a devolucao durante contato.",
        )

        self.assertIn(
            "Cliente recusou a devolucao durante contato.".encode("cp1252"),
            suffix,
        )
        self.assertNotIn(definition.observation_marker.encode("ascii"), suffix)

    def test_404_rejects_an_empty_observation(self) -> None:
        definition = self.api.close_code("404")
        with self.assertRaisesRegex(ValueError, "requer uma observacao"):
            self.api._suffix_with_observation(
                definition.suffixes[0],
                definition,
                "",
            )


if __name__ == "__main__":
    unittest.main()
