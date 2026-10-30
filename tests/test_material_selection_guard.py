"""Regression contracts for quantity-limited miscellaneous POSTs."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
def segment(start,end):
    a=SOURCE.index(start)
    b=SOURCE.index(end,a+len(start))
    return SOURCE[a:b]

class MaterialSelectionGuardTests(unittest.TestCase):
    def test_material_values_never_post_more_than_confirmed_stock(self):
        text=segment("function materialValues()", "\nfunction expectedEquipmentType(")
        self.assertIn("selectedMaterialAdjustments()", text)
        self.assertIn("item.posted_quantity > 0", text)
        self.assertIn("quantity: item.posted_quantity", text)
        self.assertIn("requested_quantity: item.requested_quantity", text)

    def test_adjustment_is_explicit_and_auditable(self):
        text=segment("function selectedMaterialAdjustments(", "\nfunction refreshMaterialControls(")
        self.assertIn("Math.min(requested, available)",text)
        self.assertIn("missing_quantity: requested - posted",text)
        self.assertIn("technician_available",text)
        self.assertIn("return_available",text)

    def test_unqueried_return_and_invalid_code_remain_blocking(self):
        text=segment("function selectedMaterialIssues(", "\nfunction selectedMaterialAdjustments(")
        self.assertIn("!hasReturnStock && quantity > technicianStock",text)
        self.assertIn("RETORNO nao consultado",text)
        self.assertIn("material.status === \"unresolved\"",text)
        self.assertIn("Number.isSafeInteger(quantity)",text)

    def test_duplicate_materials_remain_blocked(self):
        text=segment("function selectedMaterialIssues(", "\nfunction selectedMaterialAdjustments(")
        self.assertIn("seen.has(code)",text)
        self.assertIn("material duplicado",text)

    def test_visible_preview_shows_posted_requested_and_missing(self):
        text=segment("function refreshMaterialControls(", "\nfunction updateMaterialStock(")
        self.assertIn("lancar ${item.posted_quantity}/${item.requested_quantity}",text)
        self.assertIn("faltam ${item.missing_quantity}",text)
        self.assertIn("materialIssues.length > 0",text)

    def test_submit_still_cancels_real_validation_errors(self):
        text=segment('elements.equipmentDialog.addEventListener("submit",','\nelements.equipmentDialog.addEventListener("close",')
        self.assertIn("selectedMaterialIssues()",text)
        self.assertIn("event.preventDefault()",text)

    def test_zero_stock_is_marked_omitted_not_falsely_sufficient(self):
        text=segment("function updateMaterialStock(", "\nfunction addMaterialRow(")
        self.assertIn("Sem saldo:",text)
        self.assertIn("nao serao lancadas",text)
        self.assertIn("RETORNO nao consultado",text)

if __name__ == "__main__":
    unittest.main()
