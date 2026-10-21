"""Read-only official inventory bridge policy and response contracts."""
import unittest

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
