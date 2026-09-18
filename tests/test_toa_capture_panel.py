import ast
import unittest
from pathlib import Path

from toa_capture_panel import TOACaptureCatalog


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "references" / "techcap-v5.6"


class TOACaptureCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = TOACaptureCatalog(ROOT, (REFERENCE_ROOT,))

    def _state_with_reference_lot(self) -> dict:
        state = self.catalog.public_state()
        if not state["lots"]:
            self.skipTest("Fixture TECHCAP v5.6 nao disponivel neste checkout")
        return state

    def test_lists_only_valid_v56_lots(self) -> None:
        state = self._state_with_reference_lot()

        self.assertTrue(state["dry_run_only"])
        self.assertFalse(state["imperium_write_enabled"])
        self.assertFalse(state["inventory_write_enabled"])
        self.assertFalse(state["live_toa_enabled"])
        self.assertEqual(len(state["lots"]), 1)
        self.assertEqual(state["lots"][0]["aid_count"], 526)

    def test_analyze_returns_normalized_read_only_results(self) -> None:
        state = self._state_with_reference_lot()
        result = self.catalog.analyze(
            state["default_lot"], ["4230508", "999999999999"]
        )

        self.assertTrue(result["dry_run_only"])
        self.assertFalse(result["imperium_write_enabled"])
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(result["results"][0]["found"])
        self.assertEqual(
            result["results"][0]["decision"],
            "candidate_after_validation",
        )
        self.assertFalse(result["results"][1]["found"])

    def test_unknown_file_key_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "nao encontrado"):
            self.catalog.analyze("../../arquivo.json", ["123"])

    def test_panel_adapter_has_no_imperium_or_network_dependency(self) -> None:
        tree = ast.parse((ROOT / "toa_capture_panel.py").read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertFalse(imported & {
            "datasnap_client", "imperium_api", "socket", "requests", "urllib"
        })


if __name__ == "__main__":
    unittest.main()
