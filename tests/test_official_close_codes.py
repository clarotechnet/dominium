import unittest

from app import (
    OFFICIAL_CLOSE_CODES,
    _merged_close_code_metadata,
    _resolve_close_definition,
)
from imperium_api import CloseCode


class _FakeAPI:
    def __init__(self):
        self.close_codes = {
            "404": CloseCode(
                code="404",
                wire_code="404",
                description="BAIXA COM OBSERVACAO",
                id_code=44,
                suffixes=(b"404",),
                productive=False,
                requires_observation=True,
            )
        }

    def close_code(self, code):
        try:
            return self.close_codes[str(code)]
        except KeyError as exc:
            raise ValueError(f"Codigo de baixa nao suportado: {code}") from exc


class _FakeProfile:
    def __init__(self):
        self.api = _FakeAPI()


class OfficialCloseCodeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.profile = _FakeProfile()

    def test_catalog_exposes_code_312_with_repaired_text(self):
        definition = OFFICIAL_CLOSE_CODES["312"]
        self.assertFalse(definition.productive)
        self.assertNotIn("Ã", definition.description)

    def test_official_transport_accepts_catalog_code(self):
        definition = _resolve_close_definition(
            self.profile,
            "312",
            "official_http",
        )
        self.assertEqual(definition.code, "312")

    def test_datasnap_rejects_catalog_only_code(self):
        with self.assertRaisesRegex(ValueError, "nao suportado"):
            _resolve_close_definition(self.profile, "312", "datasnap")

    def test_static_definition_overrides_catalog_metadata(self):
        metadata = {
            item["code"]: item
            for item in _merged_close_code_metadata(self.profile)
        }
        self.assertTrue(metadata["404"]["requires_observation"])
        self.assertEqual(metadata["404"]["description"], "BAIXA COM OBSERVACAO")

    def test_merged_metadata_contains_each_code_once(self):
        metadata = _merged_close_code_metadata(self.profile)
        codes = [item["code"] for item in metadata]
        self.assertIn("312", codes)
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
