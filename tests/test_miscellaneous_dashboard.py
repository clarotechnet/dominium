"""Quantity and service rules use all material rows from the saved Imperium period."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from miscellaneous_dashboard import ROOT, analyze_usage, route_for
from stock_analysis_http import StockAnalysisService


DAY = "2026-11-16"
RUN = "550e8400-e29b-41d4-a716-446655440000"
TARGET = f"{ROOT}?city=natal&start={DAY}&end={DAY}"
SOURCE = {
    "NumOs": "00123", "Contrato": "70", "Qtd": "1,5", "CodigoEquipamento": "022026218",
    "CodigoServico": "VT", "NomeAbreviado": "Técnico A", "Controlador": "Controlador B",
    "DataBaixa": "2026-11-16T11:10:00", "DataBaixaMiscelanea": "2026-11-17T08:30:00",
}
LIMIT = {"material": "22026218", "qtd_controle_qualidade": "menor que 3"}
ALLOWED = {"service": " VT ", "codes": ["22026219"]}
ACTOR = "user-123"


class UsageTests(unittest.TestCase):
    def test_aggregates_before_checking_and_uses_service_rule(self):
        items, pending = analyze_usage([SOURCE, SOURCE, {
            **SOURCE, "SerialNumber": "SERIAL", "Qtd": 50,
        }], [LIMIT], [ALLOWED])
        self.assertEqual(pending, 0)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual((item["os"], item["code"], item["quantity"], item["quantityCheck"]),
                         ("00123", "22026218", "3.0", "above"))
        row = item["rows"][0]
        self.assertEqual(row["codeCheck"], "different")
        self.assertEqual(row["closedDay"], DAY)
        self.assertTrue(row["postedAt"].startswith("2026-11-17"))
        self.assertEqual((row["technician"], row["controller"]), ("Técnico A", "Controlador B"))

    def test_inclusive_rules_and_indeterminate_quantities(self):
        items, pending = analyze_usage([
            {**SOURCE, "Qtd": 3},
            {**SOURCE, "NumOs": "4", "Qtd": "XX"},
            {**SOURCE, "NumOs": "5", "Qtd": "4", "Unidade": "UN"},
            {**SOURCE, "NumOs": "5", "Unidade": "M"},
            {**SOURCE, "NumOs": "6", "CodigoEquipamento": "019"},
            {**SOURCE, "NumOs": "", "NumeroWO": "6", "CodigoEquipamento": "019"},
            {**SOURCE, "CodigoEquipamento": "??"},
        ], [{**LIMIT, "qtd_controle_qualidade": "3"}, {
            "material": "19", "qtd_controle_qualidade": "Variável",
        }], [ALLOWED])
        by_os = {item["os"]: item for item in items}
        self.assertEqual(by_os["00123"]["quantityCheck"], "within")
        for os in ("4", "5", "6", "WO 6"):
            self.assertEqual(by_os[os]["quantityCheck"], "review")
        self.assertIsNone(by_os["5"]["quantity"])
        self.assertEqual(pending, 1)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.service = StockAnalysisService(root=root / "jobs", atlas_db=root / "atlas.db", start_worker=False)
        self.dashboard = self.service.misc_dashboard
        self.body = {"city": "natal", "day": DAY, "filename": "rel.xlsx", "version": 0,
                     "dateBasis": "scheduled", "records": [{"os": "00123", "controller": "Pessoa B"}]}

    def handle(self, method, url, body=None):
        return self.service.handle(method, url, ACTOR, body)[:2]

    def test_distinguishes_missing_report_from_empty_and_preserves_versions(self):
        status, report = self.handle("GET", TARGET)
        self.assertEqual(status, 200)
        self.assertIsNone(report["usage"])
        self.assertEqual(report["missingReports"], [])
        self.assertEqual(self.handle("POST", ROOT + "/missing", self.body)[0], 200)
        status, result = self.handle("POST", ROOT + "/missing", self.body)
        self.assertEqual((status, result["reused"], result["version"]), (200, True, 1))
        self.assertEqual(self.handle("POST", ROOT + "/missing", {**self.body, "records": []})[0], 409)
        status, result = self.handle("POST", ROOT + "/missing", {**self.body, "records": [], "version": 1})
        self.assertEqual((status, result["count"], result["version"]), (200, 0, 2))
        report = self.handle("GET", TARGET)[1]
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["missingReports"][0]["dateBasis"], "scheduled")
        self.assertEqual(self.handle("GET", TARGET.replace("natal", "recife"))[1]["missingReports"], [])
        self.assertEqual(self.handle("POST", ROOT + "/missing", {**self.body, "dateBasis": ""})[0], 400)

    def test_rules_are_editable_versioned_and_scoped(self):
        body = {"city": "natal", "service": "Visita Técnica", "codes": ["0012", "12"], "revision": 0}
        status, rule = self.handle("POST", ROOT + "/rules", body)
        self.assertEqual((status, rule["codes"], rule["revision"]), (200, ["12"], 1))
        self.assertEqual(self.handle("POST", ROOT + "/rules", {**body, "service": "VISITA TECNICA"})[0], 409)
        self.assertEqual(self.handle("GET", TARGET.replace("natal", "mossoro"))[1]["rules"], [])
        self.assertEqual(self.handle("POST", ROOT + "/rules", {**body, "codes": [], "revision": 1})[0], 200)
        self.assertEqual(self.handle("GET", TARGET)[1]["rules"][0]["codes"], [])

    def test_report_reads_only_the_exact_run_period_and_category(self):
        class Repository:
            def read_category(self, run, city, category, start, end):
                if (run, city, category, start, end) != (RUN, "natal", "por_os", DAY, DAY):
                    raise AssertionError("wrong scope")
                return {"id": run}, [SOURCE, SOURCE]

            def quality_limits(self):
                return [LIMIT]

        self.dashboard.repository_factory = Repository
        status, report = self.handle("GET", TARGET + "&run=" + RUN)
        self.assertEqual(status, 200)
        self.assertEqual(report["usage"]["id"], RUN)
        self.assertEqual(report["items"][0]["quantityCheck"], "above")
        self.assertIsNone(route_for("GET", TARGET.replace("natal", "all")))
        self.assertIsNone(route_for("GET", TARGET + "&run=bad"))


if __name__ == "__main__":
    unittest.main()
