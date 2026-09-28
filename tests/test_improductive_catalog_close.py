import unittest

from imperium_api import CloseCode, ImperiumAPI, Order


class ImproductiveCatalogCloseTests(unittest.TestCase):
    def sample_order(self) -> Order:
        return Order(
            id_os=123,
            num_os="2658000000",
            contract="4290000",
            id_service=43,
            service="ADESAO",
        )

    def test_unknown_improductive_uses_validated_simple_layout(self):
        api = ImperiumAPI.__new__(ImperiumAPI)
        api.close_codes = {}
        api.delta_suffix_variants = (b"simple-a", b"simple-b")
        captured = {}

        def close_order(order, code, *, observation=""):
            captured["order"] = order
            captured["code"] = code
            captured["observation"] = observation
            return {"ok": True, "code": code.code}

        api.close_order = close_order

        result = api.close_improductive_catalog(
            self.sample_order(),
            "103",
            "Chuva",
        )

        self.assertTrue(result["ok"])
        definition = captured["code"]
        self.assertEqual(definition.code, "103")
        self.assertEqual(definition.wire_code, "103")
        self.assertEqual(definition.id_code, 7)
        self.assertEqual(definition.suffixes, api.delta_suffix_variants)
        self.assertFalse(definition.productive)
        self.assertIn("103", api.close_codes)

    def test_productive_code_is_rejected(self):
        api = ImperiumAPI.__new__(ImperiumAPI)
        api.delta_suffix_variants = (b"simple",)
        api.close_codes = {
            "409": CloseCode(
                code="409",
                wire_code="409",
                description="INSTALACAO CONCLUIDA",
                id_code=44,
                suffixes=(b"productive",),
                productive=True,
            )
        }

        with self.assertRaisesRegex(ValueError, "produtivo"):
            api.close_improductive_catalog(
                self.sample_order(),
                "409",
                "INSTALACAO CONCLUIDA",
            )


if __name__ == "__main__":
    unittest.main()
