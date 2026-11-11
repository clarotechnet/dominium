"""Native OS report contract; synthetic rows only, no customer/credential fixtures."""
import base64
import datetime as dt
import io
import json
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch
from integrations.serial_consult import order_reports as report

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
TEMPLATES = json.loads((ROOT / "deploy/hostinger-web/protocol_templates.json").read_text(encoding="ascii"))


class OrderReportsTests(unittest.TestCase):
    def test_exact_export_layout(self):
        expected = ["V.I.", "Log", "Ouv.", "Int.", "Retorno", "Data", "Turno", "Início", "Término",
                    "Núm. Contrato", "Número W.O", "Núm. OS", "Cliente", "Endereco", "Node", "Bairro",
                    "Cidade", "Serviço", "Instalador", "Observacao", "Parceria", "Status", "Data da Baixa",
                    "Controlador", "Cód. Baixa", "Desc. Cód. Baixa", "Observação Baixa", "Níveis de Sinal",
                    "Numero", "Complemento", "CEP", "TelRes", "TelOutros", "TelComercial", "TelCelular",
                    "Data Receb. OS", "Produto", "Data Agend. Sistema", "Data Baixa Sistema",
                    "Usuário Baixa Sistema", "Usuário Cad. OS", "Dt. Importação"]
        self.assertEqual([x[0] for x in report.COLUMNS], expected)

    def test_query_all_statuses_real_maintenance_category_and_net(self):
        for typ, service in [("all", "%"), ("maintenance", "2")]:
            query = report.build_query("2026-07-14", "2026-07-15", typ, TEMPLATES)
            for field, value in [("Status", "%"), ("IdTipoServico", service), ("IdParceria", "1")]:
                self.assertIn(field.encode("utf-16le") + struct.pack("<II", 8, 1) + value.encode("ascii"), query)
            self.assertIn(report._automation_date(dt.date(2026, 7, 14)), query)
            self.assertIn(report._automation_date(dt.date(2026, 7, 15), True), query)
            self.assertEqual(query[:9], b"(DspGetOs")

    def test_range_and_query_are_fail_closed(self):
        for a, b in [("2026-02-30", "2026-03-01"), ("2026-03-02", "2026-03-01"),
                     ("2999-01-01", "2999-01-01"), ("2026-01-01", "2026-02-01")]:
            with self.assertRaises(ValueError):
                report.build_query(a, b, "all", TEMPLATES)
        malformed = {**TEMPLATES, "main_query": base64.b64encode(b"not a query").decode()}
        with self.assertRaises(ValueError):
            report.build_query("2026-01-01", "2026-01-01", "all", malformed)

    def test_only_two_read_only_routes(self):
        url = "/api/order-reports/export.xlsx?profile=natal&start=2026-01-01&end=2026-01-02&type=maintenance"
        self.assertIsNotNone(report.parse_route("GET", url))
        for method, target in [("POST", url), ("GET", url + "&status=1"), ("GET", url + "\n"),
                               ("GET", url.replace("natal", "all")), ("GET", url.replace("maintenance", "technical"))]:
            self.assertIsNone(report.parse_route(method, target))

    def test_native_dates_times_codes_and_precision(self):
        self.assertEqual(report.excel_value(739930, "date"), (46336, 1))
        self.assertEqual(report.excel_value(28800000, "time"), (1/3, 2))
        self.assertEqual(report.excel_value("2026-11-10T12:00:00", "datetime"), (46336.5, 3))
        self.assertEqual(report.excel_value("004", "code"), (4, 0))
        self.assertEqual(report.excel_value("0012345", "number"), ("0012345", 0))
        self.assertEqual(report.excel_value("12345678901234567890", "number"), ("12345678901234567890", 0))
        self.assertEqual(report.excel_value(" first\r\nsecond ", "text"), ("first | second", 0))

    def test_valid_xlsx_nulls_formula_as_text_and_42_headers(self):
        row = {"NumOs": "12345678901234567890", "NumeroContrato": "0012345", "Status": 4,
               "Data": 739930, "HoraIni": 28800000, "Cliente": "=1+1 & <synthetic>",
               "ObservacaoBaixa": "first\r\nsecond", "CodigoBaixa": "004"}
        data = report.export_xlsx([row])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            rows = sheet.findall("s:sheetData/s:row", NS)
            self.assertEqual(len(rows[0]), 42)
            cells = {c.attrib["r"]: c for c in rows[1]}
            self.assertEqual(cells["L2"].attrib["t"], "inlineStr")
            self.assertEqual(cells["J2"].attrib["t"], "inlineStr")
            self.assertEqual("".join(cells["M2"].itertext()), "=1+1 & <synthetic>")
            self.assertIsNone(cells["M2"].find("s:f", NS))
            self.assertEqual(cells["F2"].find("s:v", NS).text, "46336")
            self.assertEqual(cells["Y2"].find("s:v", NS).text, "4")
            self.assertNotIn("W2", cells)
            self.assertEqual(sheet.find("s:autoFilter", NS).get("ref"), "A1:AP2")

    def test_empty_excel_is_valid_with_header(self):
        with zipfile.ZipFile(io.BytesIO(report.export_xlsx([]))) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            self.assertEqual(len(sheet.findall("s:sheetData/s:row", NS)), 1)

    def test_busy_city_does_not_start_duplicate_download(self):
        service = report.OrderReportService(fetcher=lambda *args: [])
        route = report.parse_route("GET", "/api/order-reports/export.xlsx?profile=natal&start=2026-01-01&end=2026-01-02&type=all")
        service.locks["natal"].acquire()
        with self.assertRaises(ValueError):
            service.download(route)
        service.locks["natal"].release()
        data, filename, count = service.download(route)
        self.assertEqual(count, 0)
        self.assertTrue(data.startswith(b"PK"))
        self.assertIn("Todos_natal_2026-01-01_2026-01-02", filename)

    def test_complete_fragments_only_and_safe_requests(self):
        raw = bytearray(100)
        raw[:3] = b"\xc0\xc0\x62"
        struct.pack_into("<I", raw, 20, len(raw)-28)
        sent = []
        class Client:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def request(self, method, params):
                sent.append((method, params))
                if method == "prepare": return {"result": [{"handle": [42]}]}
                if method == "execute": return {"result": [None, {"data": [30, bytes(raw[:30])]}]}
                return {"result": [{"data": [70, bytes(raw[30:])]}]}
        rows = [{**{key: None for _, key, _ in report.COLUMNS}, "IdOs": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "protocol_templates.json").write_text(json.dumps(TEMPLATES))
            with patch("datasnap_client.load_credentials", return_value={"username": "synthetic", "password": "synthetic"}):
                with patch.object(report, "decode_dataset", return_value=rows) as decode:
                    result = report.fetch_rows("natal", "2026-01-01", "2026-01-01", "all", runtime=Path(tmp), client_factory=Client)
                    self.assertEqual(result, rows)
                    self.assertEqual(decode.call_args.args[0], bytes(raw))
                self.assertEqual([x[0] for x in sent], ["prepare", "execute", "more_blob"])
                self.assertEqual(sent[0][1][-1], "TDtmOrdemServico.AS_GetRecords")
                class Broken(Client):
                    def request(self, method, params):
                        if method == "more_blob": return {"result": [{"data": [0, b""]}]}
                        return super().request(method, params)
                with self.assertRaises(RuntimeError):
                    report.fetch_rows("natal", "2026-01-01", "2026-01-01", "all", runtime=Path(tmp), client_factory=Broken)


if __name__ == "__main__":
    unittest.main()
