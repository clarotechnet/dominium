import unittest
from unittest.mock import patch

import toa_discovery_browser


class TOADiscoveryBrowserTests(unittest.TestCase):
    def test_paths_are_isolated_and_manifest_exists(self):
        self.assertTrue((toa_discovery_browser.EXTENSION_PATH / "manifest.json").is_file())
        self.assertEqual(toa_discovery_browser.DEBUG_PORT, 9341)
        self.assertIn("toa-discovery", str(toa_discovery_browser.EXTENSION_PATH))

    @patch("toa_discovery_browser._targets")
    def test_reuses_existing_discovery_browser(self, targets):
        targets.return_value = [
            {"url": "chrome-extension://abc/service-worker.js"},
            {"url": "https://clarobrasil.etadirect.com/"},
        ]
        result = toa_discovery_browser.launch()
        self.assertTrue(result["extension_loaded"])
        self.assertEqual(result["extension_targets"], 1)
        self.assertEqual(result["toa_targets"], 1)


if __name__ == "__main__":
    unittest.main()
