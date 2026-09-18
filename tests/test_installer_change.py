import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from datasnap_client import DataSnapError
from imperium_api import ImperiumAPI, Order
from installer_change import InstallerChangeProtocol


ROOT = Path(__file__).resolve().parents[1]


class InstallerChangeProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = InstallerChangeProtocol(
            ROOT / "installer_change_protocol_templates.json"
        )

    def test_replaces_only_the_three_captured_identifiers(self) -> None:
        query = self.protocol.build_query(3857, 313101, 1837422)

        self.assertEqual(len(query), len(self.protocol.template))
        self.assertEqual(
            struct.unpack_from("<I", query, self.protocol.installer_id_offset)[0],
            3857,
        )
        self.assertEqual(
            struct.unpack_from("<I", query, self.protocol.controller_id_offset)[0],
            313101,
        )
        self.assertEqual(
            struct.unpack_from("<I", query, self.protocol.order_id_offset)[0],
            1837422,
        )

    def test_recognizes_the_captured_success_blob_recursively(self) -> None:
        response = {
            "result": [0, {"data": [0, self.protocol.success_response]}]
        }

        self.assertTrue(self.protocol.confirmed(response))
        self.assertFalse(self.protocol.confirmed({"result": [0]}))

    def test_rejects_non_positive_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "positivos"):
            self.protocol.build_query(0, 313101, 1837422)


class InstallerChangeAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = ImperiumAPI(ROOT, profile_key="natal")

    def test_sends_one_explicit_order_and_requires_success_response(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.return_value = {
            "result": [
                0,
                {"data": [0, self.api.installer_change_protocol.success_response]},
            ]
        }
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_handle", return_value=77),
            patch.object(self.api, "_fetch_detail", return_value=b"detail"),
            patch.object(
                self.api,
                "_detail_context",
                return_value=SimpleNamespace(
                    id_os=1837422,
                    contract="9009408",
                    installer_id=3857,
                    installer_name="TECNICO DESTINO",
                ),
            ),
        ):
            result = self.api.change_order_installer(1837422, 3857)

        self.assertTrue(result["ok"])
        sent_query = client.request.call_args.args[1][1]
        protocol = self.api.installer_change_protocol
        self.assertEqual(
            struct.unpack_from("<I", sent_query, protocol.order_id_offset)[0],
            1837422,
        )
        self.assertEqual(
            struct.unpack_from("<I", sent_query, protocol.installer_id_offset)[0],
            3857,
        )

    def test_rejects_a_success_blob_when_the_installer_did_not_change(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.return_value = {
            "result": [
                0,
                {"data": [0, self.api.installer_change_protocol.success_response]},
            ]
        }
        unchanged = SimpleNamespace(
            id_os=1837422,
            contract="9009408",
            installer_id=1111,
            installer_name="TECNICO ORIGINAL",
        )
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_handle", return_value=77),
            patch.object(self.api, "_fetch_detail", return_value=b"detail"),
            patch.object(self.api, "_detail_context", return_value=unchanged),
            patch("imperium_api.time.sleep"),
            self.assertRaisesRegex(DataSnapError, "permanece com TECNICO ORIGINAL"),
        ):
            self.api.change_order_installer(1837422, 3857)

    def test_reads_the_authoritative_installer_from_the_order_detail(self) -> None:
        order = Order(1837422, "77303106940", "9009408", 10, "SERVICO")
        context = SimpleNamespace(
            id_os=order.id_os,
            contract=order.contract,
            installer_id=3857,
            installer_name="ADRIANO COSTA",
        )
        with (
            patch.object(
                self.api,
                "_fetch_detail",
                return_value=b"detail:" + order.num_os.encode("ascii"),
            ),
            patch.object(self.api, "_detail_context", return_value=context),
        ):
            result = self.api.order_installer(order)

        self.assertEqual(result["installer_name"], "ADRIANO COSTA")
        self.assertEqual(result["source"], "imperium_detail")

    def test_does_not_accept_an_unconfirmed_write(self) -> None:
        client = MagicMock()
        client.__enter__.return_value = client
        client.request.return_value = {"result": [0]}
        with (
            patch.object(self.api, "_client", return_value=client),
            patch.object(self.api, "_handle", return_value=77),
            self.assertRaisesRegex(DataSnapError, "nao confirmou"),
        ):
            self.api.change_order_installer(1837422, 3857)


if __name__ == "__main__":
    unittest.main()
