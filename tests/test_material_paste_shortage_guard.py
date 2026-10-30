"""TOA paste keeps requested quantities and audits stock-bounded allocations."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"static"/"app.js").read_text(encoding="utf-8")
START=SOURCE.index("async function processMaterialPaste()")
END=SOURCE.index("async function loadMaterialInventory(",START)
BODY=SOURCE[START:END]

class MaterialPasteStockAdjustmentTests(unittest.TestCase):
    def test_shortfall_is_not_automatic_block(self):
        self.assertIn("const blocked = unresolved > 0 || validation.can_close === false",BODY)
        self.assertNotIn("const blockingShortage = shortage > 0",BODY)

    def test_audit_contains_original_quantity_and_missing(self):
        self.assertIn("state.materialPasteReconciliation",BODY)
        self.assertIn("requested_quantity: Number(group.requested_quantity || 0)",BODY)
        self.assertIn("posted_quantity: Number(group.allocated_quantity || 0)",BODY)
        self.assertIn("missing_quantity: Number(group.missing_quantity || 0)",BODY)

    def test_partial_makes_warning_not_success_or_error(self):
        self.assertIn('missingDetails.length ? "warning" : "success"',BODY)
        self.assertIn("lancar ${item.posted_quantity}/${item.requested_quantity}",BODY)

    def test_previous_false_success_message_removed(self):
        self.assertNotIn("com complemento do estoque virtual RETORNO",BODY)
        self.assertIn("sem saldo completo apos tecnico + RETORNO",BODY)

if __name__=="__main__":
    unittest.main()
