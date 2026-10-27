"""Contratos de frontend da Visão Claro incorporada ao DOMINIUM."""

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.scripts = []
        self.iframe = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids[a["id"]] = (tag, a)
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])


class DescAnalyticsFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.app = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.css = (STATIC / "styles.css").read_text(encoding="utf-8")
        cls.dashboard = (STATIC / "desc-analytics.html").read_text(encoding="utf-8")
        cls.index_html = Elements()
        cls.index_html.feed(cls.index)
        cls.dashboard_html = Elements()
        cls.dashboard_html.feed(cls.dashboard)

    def test_navigation_keeps_existing_desc_reviewer(self):
        ids = self.index_html.ids
        self.assertEqual(ids["disconnectionGroupToggle"][1]["aria-controls"], "disconnectionNavChildren")
        self.assertIn("disconnectionModule", ids)
        self.assertIn("descAnalyticsModule", ids)
        self.assertIn("stockGroupToggle", ids)
        self.assertEqual(ids["disconnectionNavChildren"][1].get("hidden"), None)

    def test_analytics_module_is_separate_and_lazy(self):
        ids = self.index_html.ids
        self.assertIn("descAnalyticsWorkspace", ids)
        self.assertEqual(ids["descAnalyticsFrame"][1]["data-src"], "/desc-analytics.html")
        self.assertNotIn("src", ids["descAnalyticsFrame"][1])
        self.assertIn('state.activeModule !== "disconnection"', self.app)
        self.assertIn('state.activeModule !== "descAnalytics"', self.app)
        self.assertIn('setModule("descAnalytics")', self.app)
        self.assertIn('window.location.hash === "#desconexao-indicadores"', self.app)

    def test_dashboard_assets_are_local_and_present(self):
        scripts = self.dashboard_html.scripts
        self.assertIn("/desc-analytics-xlsx.js", scripts)
        self.assertIn("/desc-analytics-html2canvas.js", scripts)
        for url in scripts:
            self.assertTrue((STATIC / url.lstrip("/")).is_file(), url)
        self.assertIn("html2canvas", (STATIC / "desc-analytics-html2canvas.js").read_text(encoding="utf-8")[:1000])
        self.assertIn("xlsx.js", (STATIC / "desc-analytics-xlsx.js").read_text(encoding="utf-8")[:1000])

    def test_frame_does_not_change_global_clickjacking_header(self):
        self.assertIn("frame.srcdoc = html", self.app)
        self.assertNotIn('frame.setAttribute("src", frame.dataset.src)', self.app)

    def test_stock_tabs_have_rounded_corners(self):
        self.assertIn(".stock-workspace > .quality-tabs", self.css)
        self.assertIn("border-radius: 14px", self.css)

    def test_dashboard_original_feature_hooks_remain(self):
        for text in ("Atualizar pasta", "Escolher arquivos", "Visão geral", "Produtividade"):
            self.assertIn(text, self.dashboard)


if __name__ == "__main__":
    unittest.main()
