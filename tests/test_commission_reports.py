"""Synthetic read-only test suite for four-base Imperium commissions."""
from __future__ import annotations
import io
import sys
import threading
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"integrations"/"serial_consult"),str(ROOT)]
from commission_reports import (
    build_query, parse_route, export_xlsx, CommissionReportService,
    SHEETS, DATASETS, _dataset_bytes,
)

def sample():
    return {
        DATASETS[0]: [{"IdInstalador":2,"NomeAbreviado":"TESTE SERVIÇOS",
           "Valor":23.5,"ValorInstalador":10,"ValorAuxiliar":4,
           "ValorDeslocamento":0}],
        DATASETS[1]: [{"IdInstalador":2,"NomeAbreviado":"TESTE SERVIÇOS",
           "IdComissionamento":6,"Produto":"TESTE DE SERVIÇO",
           "QtdContrato":1,"QtdOs":2,"Valor":23.5,
           "ValorInstalador":10,"ValorAuxiliar":4}],
        DATASETS[2]: [{"IdComissionamento":6,"Produto":"TESTE DE SERVIÇO",
           "IdInstalador":2,"Contrato":1234567,"DataAgendamento":"2026-11-02",
           "DataBaixa":"2026-11-02","QtdOS":2,"Valor":23.5,
           "ValorInstalador":10,"ValorAuxiliar":4}],
    }

class TestCommissionReports(unittest.TestCase):
    def test_only_exact_get_route_and_profiles(self):
        route="/api/commission-reports/export.xlsx?profile=recife&start=2026-11-01&end=2026-11-11"
        self.assertEqual(parse_route("GET",route).groups(),("recife","2026-11-01","2026-11-11"))
        for invalid in (route+"&extra=1",route.replace("recife","all"),route.replace("start=","date=")):
            self.assertIsNone(parse_route("GET",invalid))
        self.assertIsNone(parse_route("POST",route))
    def test_templates_are_read_only_and_dynamic_by_date(self):
        for name in DATASETS:
            data=build_query(name,"2026-11-03","2026-11-09")
            self.assertIn("03/11/2026".encode("utf-16le"),data)
            self.assertIn("09/11/2026 23:59:59".encode("utf-16le"),data)
            self.assertNotIn("01/11/2026".encode("utf-16le"),data)
        with self.assertRaises(ValueError):
            build_query(DATASETS[0],"2026-01-01","2026-11-11")
        with self.assertRaises(ValueError):
            build_query("DspGetOs","2026-11-01","2026-11-11")
    def test_multi_sheet_excel_and_correct_columns(self):
        workbook=export_xlsx(sample())
        self.assertTrue(workbook.startswith(b"PK\x03\x04"))
        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            names=archive.namelist()
            for idx in (1,2,3):
                self.assertIn(f"xl/worksheets/sheet{idx}.xml",names)
            root=ET.fromstring(archive.read("xl/workbook.xml"))
            ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheets=root.findall(".//m:sheet",ns)
            self.assertEqual([sheet.attrib["name"] for sheet in sheets],
                             [part[0] for part in SHEETS])
            for index,(_,dataset,columns) in enumerate(SHEETS,1):
                root=ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
                row=root.findall(".//m:sheetData/m:row",ns)
                self.assertEqual(len(row),2)
                texts=[''.join(cell.itertext()) for cell in row[0]]
                for caption,_,_ in columns:
                    self.assertIn(caption,texts)
            self.assertIn(b"Comiss",archive.read("xl/workbook.xml"))
    def test_reject_partial_export(self):
        data=sample()
        del data[DATASETS[2]]
        with self.assertRaises(ValueError):
            export_xlsx(data)
    def test_service_uses_only_one_city_and_no_implicit_all(self):
        calls=[]
        def fetch(profile,start,end):
            calls.append((profile,start,end))
            return sample()
        service=CommissionReportService(fetcher=fetch)
        route=parse_route("GET","/api/commission-reports/export.xlsx?profile=natal&start=2026-11-01&end=2026-11-11")
        content,filename,counts=service.download(route)
        self.assertEqual(calls,[("natal","2026-11-01","2026-11-11")])
        self.assertIn("natal",filename)
        self.assertEqual(counts[DATASETS[2]],1)
        self.assertGreater(len(content),500)
    def test_busy_lock_fails_closed(self):
        service=CommissionReportService(fetcher=lambda *args:sample())
        route=parse_route("GET","/api/commission-reports/export.xlsx?profile=natal&start=2026-11-01&end=2026-11-11")
        self.assertTrue(service.locks["natal"].acquire(False))
        try:
            with self.assertRaises(ValueError):
                service.download(route)
        finally:
            service.locks["natal"].release()

if __name__=="__main__":
    unittest.main()
