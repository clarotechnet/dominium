"""QUERY Atlas table transformations and text-preserving exports."""
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'integrations'/'serial_consult'
sys.path.insert(0,str(ROOT))
from atlas_query_data import parse_report, material_no_zero, export_csv, export_xlsx, store_records, page, COLUMNS
from atlas_query_report import claim_job

class Tests(unittest.TestCase):
    def test_sap_normalization(self):
        self.assertEqual(material_no_zero('000000123400'),'123400')
        self.assertEqual(material_no_zero('000'),'0')
        self.assertEqual(material_no_zero('A0012'),'A0012')

    def test_html_xls(self):
        html='''<html><body><table><tr><th>Outros</th></tr></table><table>
        <tr><th>Numero Serie</th><th>Codigo Material SAP</th><th>Estado</th>
        <th>Operacao</th><th>Nome do Local</th></tr>
        <tr><td>000123456789</td><td>00000231450</td><td>SUSPEITO</td>
        <td>MOSSORO</td><td>EMPREITEIRA</td></tr></table></body></html>'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.xls'
            path.write_bytes(html.encode('utf8'))
            records=parse_report(path)
        self.assertEqual(records[0]['numero_serie'],'000123456789')
        self.assertEqual(records[0]['codigo_sap_normalizado'],'231450')
        self.assertEqual(records[0]['estado'],'SUSPEITO')

    def test_csv_injection_and_zeroes(self):
        row={key:'' for key,_ in COLUMNS}
        row.update(numero_serie='000123456789',modelo='=HYPERLINK("unsafe")')
        csv_data=export_csv([row]).decode('utf-8-sig')
        self.assertIn('000123456789',csv_data)
        self.assertIn("'=HYPERLINK",csv_data)

    def test_xlsx_preserves_identifiers_as_text(self):
        row={key:'' for key,_ in COLUMNS}
        row.update(numero_serie='000123456789',codigo_material_sap='000098',modelo='=2+2')
        with zipfile.ZipFile(io.BytesIO(export_xlsx([row]))) as workbook:
            text=workbook.read('xl/worksheets/sheet1.xml').decode('utf-8')
        self.assertIn('000123456789',text)
        self.assertIn('000098',text)
        self.assertNotIn('<f>',text)
        self.assertIn('autoFilter',text)

    def test_store_and_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.sqlite3'
            a,_=claim_job('mossoro','empreiteira',db,created_by='user-1')
            b,_=claim_job('natal','empreiteira',db,created_by='user-2')
            store_records(a,[{'numero_serie':'000123456789','estado':'SUSPEITO'}],db)
            store_records(b,[{'numero_serie':'000111111111','estado':'INICIALIZADO'}],db)
            self.assertEqual(page(a,db)['total'],1)
            self.assertEqual(page(b,db)['rows'][0]['numero_serie'],'000111111111')
            self.assertEqual(page(a,db)['rows'][0]['numero_serie'],'000123456789')

if __name__=='__main__':unittest.main()
