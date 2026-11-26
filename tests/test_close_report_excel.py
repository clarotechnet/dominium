from __future__ import annotations

import datetime as dt
import io
import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import openpyxl

from close_report_excel import (
    build_close_report_xlsx,
    format_equipment_readable,
    format_materials_readable,
)
from integrations.desc_runtime.patch_runtime_safety import patch_close_report_download


class CloseReportExcelTests(unittest.TestCase):
    def test_legacy_panel_exports_workbook_for_requested_date_and_profile(self) -> None:
        root = Path(__file__).resolve().parents[1]
        web_app = (root / "app.py").read_text(encoding="utf-8")
        start = '            if parsed.path == "/api/close-report":\n'
        export = '            if parsed.path in ("/api/close-report/export.xlsx", "/api/close-report.xlsx"):\n'
        end = '            installer_detail_match = re.fullmatch(\n'
        report_route = web_app[web_app.index(start):web_app.index(export)]
        legacy = 'def get_report(self, parsed, profile):\n    if True:\n        if True:\n' + report_route + end + '                "", "",\n            )\n'
        patched = patch_close_report_download(legacy, web_app=web_app)
        self.assertEqual(patch_close_report_download(patched, web_app=web_app), patched)
        scope = {"dt": dt, "parse_qs": parse_qs, "HTTPStatus": HTTPStatus}
        exec(patched, scope)
        outputs = []
        handler = SimpleNamespace(_binary=lambda status, data, **headers: outputs.append((status, data, headers)))
        date = dt.date.today() - dt.timedelta(days=1)
        requested = []

        def records(day):
            requested.append(day)
            return [{"contract": "0123456", "num_os": "2660000001", "state": "confirmed"}]

        profile = SimpleNamespace(key="natal", label="Natal / Parnamirim", close_report=SimpleNamespace(list=records))
        scope["get_report"](handler, urlsplit(f"/api/close-report/export.xlsx?profile=natal&date={date}"), profile)
        self.assertEqual(requested, [date])
        status, data, headers = outputs[0]
        self.assertEqual(status, 200)
        self.assertEqual(headers["filename"], f"relatorio-baixas-natal-{date:%Y%m%d}.xlsx")
        with io.BytesIO(data) as stream:
            workbook = openpyxl.load_workbook(stream, read_only=True)
            self.assertEqual(workbook.active["A5"].value, "0123456")
            self.assertEqual(workbook.active["D5"].value, "2660000001")
            workbook.close()

    def test_format_materials_readable_with_list(self) -> None:
        materials = [
            {"name": "CABO 2FO", "quantity": 100, "unit": "m"},
            {"name": "FITA ISOLANTE", "quantity": 6, "unit": "m"},
            {"name": "CONECTOR REUTILIZAVEL", "quantity": 2, "unit": "UN"},
        ]
        result = format_materials_readable(materials)
        self.assertEqual(result, "100m CABO 2FO, 6m FITA ISOLANTE, 2x CONECTOR REUTILIZAVEL")

    def test_format_materials_readable_empty(self) -> None:
        self.assertEqual(format_materials_readable([]), "-")
        self.assertEqual(format_materials_readable(None), "-")

    def test_format_equipment_readable_with_list(self) -> None:
        equipment = [
            {"name": "ONT GPON", "serial": "4857544312345678"},
            {"name": "DECODER HD", "serial": "ABC123456"},
        ]
        result = format_equipment_readable(equipment)
        self.assertEqual(result, "ONT GPON (SN: 4857544312345678), DECODER HD (SN: ABC123456)")

    def test_build_close_report_xlsx_structure(self) -> None:
        records = [
            {
                "contract": "123456",
                "technician": "FERNANDO ANTONIO",
                "scheduled_date": "2026-08-25",
                "num_os": "2652991103",
                "close_code": "409",
                "close_description": "INSTALACAO CONCLUIDA",
                "installed_equipment": [{"name": "ONT GPON", "serial": "485754431234"}],
                "materials": [
                    {"name": "CABO 2FO", "quantity": 100, "unit": "m"},
                    {"name": "FITA ISOLANTE", "quantity": 6, "unit": "m"},
                ],
                "material_count": 2,
                "confirmed_at": "2026-08-25T14:32:05-03:00",
                "transport": "official_http",
                "state": "confirmed",
                "message": "Baixa confirmada no Imperium",
            }
        ]
        today = dt.date(2026, 8, 25)
        raw_bytes = build_close_report_xlsx(records, today, "NATAL")
        self.assertGreater(len(raw_bytes), 1000)

        # Validar leitura do workbook
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes))
        ws = wb.active
        self.assertEqual(ws.title, "Baixas 25-08-2026")
        self.assertIn("DOMINIUM", str(ws["A1"].value))

        # Linha 4: Cabeçalho
        self.assertEqual(ws.cell(row=4, column=1).value, "Contrato")
        self.assertEqual(ws.cell(row=4, column=8).value, "Materiais Entrando / Usados")

        # Linha 5: Dados
        self.assertEqual(ws.cell(row=5, column=1).value, "123456")
        self.assertEqual(ws.cell(row=5, column=2).value, "FERNANDO ANTONIO")
        self.assertEqual(ws.cell(row=5, column=8).value, "100m CABO 2FO, 6m FITA ISOLANTE")
        self.assertEqual(ws.cell(row=5, column=12).value, "Baixada")


if __name__ == "__main__":
    unittest.main()
