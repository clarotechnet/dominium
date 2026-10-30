"""Regression for paste-to-OS with insufficient materials in Natal."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
START = SOURCE.index("async function processMaterialPaste()")
STOP = SOURCE.index("async function loadMaterialInventory(", START)
BODY = SOURCE[START:STOP]


class MaterialPasteShortageTests(unittest.TestCase):
    def test_any_city_blocks_shortfall(self):
        self.assertIn("const blockingShortage = shortage > 0 || validation.can_close === false", BODY)
        self.assertNotIn('shortage > 0 && state.profile !== "natal"', BODY)

    def test_backend_correlated_group_displays_missing_original_quantity(self):
        self.assertIn("payload.atlas_groups", BODY)
        self.assertIn("group.missing_quantity", BODY)
        self.assertIn("group.requested_quantity", BODY)
        self.assertIn("group.requested_code", BODY)

    def test_shortage_causes_persistent_material_error(self):
        self.assertIn("state.materialError = `Baixa bloqueada:", BODY)
        self.assertIn('blockingShortage ? state.materialError : state.materialNotice', BODY)
        self.assertIn('unresolved || blockingShortage ? "error" : "success"', BODY)

    def test_old_natal_success_message_is_gone(self):
        self.assertNotIn("com complemento do estoque virtual RETORNO", BODY)
        self.assertIn("miscelanea(s) sem saldo completo apos tecnico + RETORNO", BODY)


if __name__ == "__main__":
    unittest.main()
