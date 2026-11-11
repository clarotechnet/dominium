"""Synthetic end-to-end tests for recorded macro transformations (no customer rows)."""
import io
import unittest
import xml.etree.ElementTree as ET
import zipfile

from integrations.serial_consult import order_reports as reports

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class TreatedOrderReportsTests(unittest.TestCase):
    def test_supervisor_layout_and_dedup_before_code_filter(self):
        self.assertEqual(
            [column[0] for column in reports.ALL_TREATED_COLUMNS],
            ["Data", "Núm. Contrato", "Bairro", "Endereco", "Numero",
             "Complemento", "Serviço", "Instalador", "Cód. Baixa",
             "Desc. Cód. Baixa", "Observação Baixa"],
        )
        rows = [
            {"NumeroContrato": "0001", "CodigoBaixa": "205", "Servico": "A"},
            {"NumeroContrato": "0001", "CodigoBaixa": "108", "Servico": "B"},
            {"NumeroContrato": "0002", "CodigoBaixa": "430", "Servico": "C"},
            {"NumeroContrato": "0003", "CodigoBaixa": 303, "Servico": "D"},
            {"NumeroContrato": "0004", "CodigoBaixa": "110", "Servico": "E"},
        ]
        filtered = reports.treat_rows(rows, "all")
        self.assertEqual([row["NumeroContrato"] for row in filtered], ["0001", "0003", "0004"])
        data = reports.export_xlsx(filtered, reports.ALL_TREATED_COLUMNS, autofit=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            rows_xml = sheet.findall("s:sheetData/s:row", NS)
            self.assertEqual(len(rows_xml), 4)
            self.assertEqual(len(rows_xml[0]), 11)
            self.assertEqual(sheet.find("s:autoFilter", NS).get("ref"), "A1:K4")
            self.assertEqual(len(sheet.findall("s:cols/s:col", NS)), 11)

    def test_maintenance_excludes_macro_selected_services_and_keeps_visits(self):
        # The real VBA-treated sample has 77 rows, not three: its selected
        # TROCA DE EQUIPAMENTO STREAMING rows were deleted by the macro.
        rows = [
            {"NumeroWO": f"WO-{idx}", "Servico": "VISITA TECNICA - VIRTUA"}
            for idx in range(50)
        ]
        rows += [{"NumeroWO": f"WO-S-{idx}", "Servico": "MANUTENCAO PREVENTIVA INDOOR I"}
                 for idx in range(16)]
        rows += [{"NumeroWO": f"WO-D-{idx}", "Servico": "VISITA TECNICA DIGITAL"}
                 for idx in range(6)]
        rows += [{"NumeroWO": f"WO-T-{idx}", "Servico": "VISITA TECNICA STREAMING"}
                 for idx in range(4)]
        rows += [{"NumeroWO": "WO-MESH", "Servico": "VISITA TECNICA WIFI MESH"}]
        rows += [{"NumeroWO": f"WO-X-{idx}", "Servico": "TROCA DE EQUIPAMENTO STREAMING"}
                 for idx in range(3)]
        self.assertEqual(len(rows), 80)
        treated = reports.treat_rows(rows, "maintenance")
        self.assertEqual(len(treated), 77)
        self.assertTrue(all(r["Servico"] != "TROCA DE EQUIPAMENTO STREAMING" for r in treated))
        self.assertEqual(len(reports.treat_rows([], "maintenance")), 0)
        self.assertEqual(len(reports.COLUMNS), 42)

    def test_maintenance_filters_blank_wo_and_each_six_services(self):
        rows = [{"NumeroWO": idx + 1, "Servico": name}
                for idx, name in enumerate(sorted(reports.MAINTENANCE_SERVICES))]
        rows += [
            {"NumeroWO": "", "Servico": "VISITA TECNICA DIGITAL"},
            {"NumeroWO": " ", "Servico": "VISITA TECNICA DIGITAL"},
            {"NumeroWO": "123", "Servico": "VISITA TECNICA DIGITAL"},
        ]
        result = reports.treat_rows(rows, "maintenance")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["NumeroWO"], "123")

    def test_raw_is_preserved_and_treated_is_distinct(self):
        rows = [{"NumeroContrato": "00012", "CodigoBaixa": 108,
                 "NumeroWO": 1, "Servico": "MANUTENCAO CORRETIVA - MDU"}]
        service = reports.OrderReportService(fetcher=lambda *args: rows)
        url = "/api/order-reports/export.xlsx?profile=natal&start=2026-01-01&end=2026-01-02&type=all"
        raw = reports.parse_route("GET", url)
        treated = reports.parse_route("GET", url + "&variant=treated")
        self.assertIsNotNone(raw)
        self.assertIsNotNone(treated)
        self.assertIsNone(reports.parse_route("POST", url + "&variant=treated"))
        self.assertIsNone(reports.parse_route("GET", url + "&variant=raw"))
        self.assertIsNone(reports.parse_route("GET", url + "&variant=treated&extra=1"))
        raw_bytes, raw_name, raw_n = service.download(raw)
        treated_bytes, treated_name, treated_n = service.download(treated)
        self.assertEqual((raw_n, treated_n), (1, 1))
        self.assertNotIn("Tratado", raw_name)
        self.assertIn("Tratado", treated_name)
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as a, zipfile.ZipFile(io.BytesIO(treated_bytes)) as b:
            ra = ET.fromstring(a.read("xl/worksheets/sheet1.xml"))
            rb = ET.fromstring(b.read("xl/worksheets/sheet1.xml"))
            self.assertEqual(len(ra.findall("s:sheetData/s:row", NS)[0]), 42)
            self.assertEqual(len(rb.findall("s:sheetData/s:row", NS)[0]), 11)

    def test_empty_treated_files_have_correct_headers(self):
        for report_type, columns in [("all", reports.ALL_TREATED_COLUMNS),
                                     ("maintenance", reports.COLUMNS)]:
            self.assertEqual(reports.treat_rows([], report_type), [])
            data = reports.export_xlsx([], columns, autofit=True)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                self.assertEqual(len(sheet.findall("s:sheetData/s:row", NS)), 1)
                self.assertEqual(len(sheet.findall("s:sheetData/s:row", NS)[0]), len(columns))


if __name__ == "__main__":
    unittest.main()
