"""Regression contracts for the browser's miscellaneous-stock submit guard."""
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1] / "static" / "app.js"
SOURCE = APP.read_text(encoding="utf-8")

def segment(begin: str, end: str) -> str:
    start = SOURCE.index(begin)
    stop = SOURCE.index(end, start + len(begin))
    return SOURCE[start:stop]

class MaterialSelectionGuardTests(unittest.TestCase):
    def test_original_quantity_is_not_truncated(self):
        body = segment("function materialValues()", "\nfunction expectedEquipmentType(")
        self.assertNotIn("Math.min(quantity, totalAvail)", body)
        self.assertNotIn("return null", body)
        self.assertNotIn(".filter(Boolean)", body)
        self.assertIn("quantity,", body)
        self.assertIn("selectedMaterialIssues()", body)

    def test_missing_balance_never_discards_required_material(self):
        body = segment("function selectedMaterialIssues(", "\nfunction refreshMaterialControls(")
        self.assertIn("quantity > available", body)
        self.assertIn("const missing = quantity - available", body)
        self.assertIn("RETORNO nao consultado", body)
        self.assertIn("tecnico + RETORNO insuficientes", body)
        self.assertIn("material.status === \"unresolved\"", body)

    def test_only_validated_natal_return_balance_is_added(self):
        body = segment("function selectedMaterialIssues(", "\nfunction refreshMaterialControls(")
        self.assertIn('state.profile === "natal" && hasReturnStock', body)
        self.assertIn("Number.isFinite(returnStock)", body)
        self.assertIn("Number.isSafeInteger(quantity)", body)

    def test_material_duplicates_are_blocked(self):
        body = segment("function selectedMaterialIssues(", "\nfunction refreshMaterialControls(")
        self.assertIn("seen.has(code)", body)
        self.assertIn("material duplicado", body)

    def test_shortage_disables_confirmation(self):
        body = segment("function refreshMaterialControls(", "\nfunction updateMaterialStock(")
        self.assertIn("materialIssues.length > 0", body)
        self.assertIn("elements.equipmentConfirm.disabled", body)
        self.assertIn("Baixa bloqueada:", body)

    def test_submission_is_cancelled_if_validation_fails(self):
        body = segment(
            'elements.equipmentDialog.addEventListener("submit",',
            '\nelements.equipmentDialog.addEventListener("close",',
        )
        self.assertIn("selectedMaterialIssues()", body)
        self.assertIn("event.preventDefault()", body)
        self.assertIn("materialError || issues.length", body)

    def test_preview_no_longer_promises_discard(self):
        body = segment("function updateMaterialStock(", "\nfunction addMaterialRow(")
        self.assertIn("Sem saldo (baixa bloqueada)", body)
        self.assertIn("RETORNO nao consultado (baixa bloqueada)", body)
        self.assertNotIn("sera descartado da baixa", body)

if __name__ == "__main__":
    unittest.main()
