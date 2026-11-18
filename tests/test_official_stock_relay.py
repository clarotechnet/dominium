"""Read-only official inventory bridge policy and response contracts."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from integrations.official_stock_relay import official_stock_bridge
from integrations.official_stock_relay.official_stock_bridge import (
    OfficialStockBridge, parse_route,
)


class FakeClient:
    def stock_catalog(self, installer_id):
        return [{"stock_id": 123, "name": "TESTE"}]

    def stock_items(self, stock_id):
        return [{"code": "12345", "quantity": 2}]


class OfficialStockRelayTests(unittest.TestCase):
    def test_strict_allowed_routes(self):
        self.assertEqual(parse_route("GET", "/api/imperium-official/stocks?profile=natal"), ("natal", None, None))
        self.assertEqual(parse_route("GET", "/api/imperium-official/stocks/123/items?profile=fortaleza"), ("fortaleza", 123, None))
        self.assertIsNone(parse_route("GET", "/api/stock/writeoff"))
        self.assertIsNone(parse_route("GET", "/api/imperium-official/stocks/123/commit"))
        self.assertIsNone(parse_route("GET", "/api/imperium-official/stocks/0/items"))
        self.assertIsNone(parse_route("POST", "/api/orders"))
        for target in (
            "/api/imperium-official/stocks?profile=recife",
            "/api/imperium-official/stocks?profile=natal&profile=fortaleza",
            "/api/imperium-official/stocks?profile=natal&origin=evil",
            "/api/imperium-official/stocks/2147483648/items",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                parse_route("GET", target)
        with self.assertRaises(ValueError):
            parse_route("POST", "/api/imperium-official/stocks")

    def test_relay_can_have_a_private_credential_without_changing_the_application(self):
        with tempfile.TemporaryDirectory() as folder:
            legacy = Path(folder) / "legacy.dat"
            dedicated = Path(folder) / "relay.dat"
            with patch.object(official_stock_bridge, "CREDENTIALS_FILE", legacy), patch.object(
                official_stock_bridge, "RELAY_CREDENTIALS_FILE", dedicated
            ):
                self.assertEqual(OfficialStockBridge()._credentials_file, legacy)
                dedicated.touch()
                self.assertEqual(OfficialStockBridge()._credentials_file, dedicated)
                self.assertEqual(OfficialStockBridge(credentials_file=legacy)._credentials_file, legacy)

    def test_only_read_only_contracts_are_exposed(self):
        bridge = OfficialStockBridge(credentials_file="not-accessed.fixture")
        bridge._clients["natal"] = FakeClient()
        stocks = bridge.read(("natal", None, None))
        self.assertEqual(stocks["source"], "imperium_official_http")
        self.assertEqual(stocks["count"], 1)
        self.assertEqual(stocks["stocks"][0]["stock_id"], 123)
        items = bridge.read(("natal", 123, None))
        self.assertEqual(items["count"], 1)
        self.assertEqual(items["items"][0]["quantity"], 2)


if __name__ == "__main__":
    unittest.main()
