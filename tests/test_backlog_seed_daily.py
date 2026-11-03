"""Regression tests for the isolated DESC history bootstrap and 22h scheduler."""
import datetime as dt
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from contextlib import contextmanager, closing
from xml.sax.saxutils import escape

from backlog_daily_scheduler import DailyHistoryScheduler, LOCAL_TZ
from backlog_seed_xlsx import ingest

def make_xlsx(path):
    headers = ["Data", "Núm. Contrato", "Núm. OS", "Serviço", "Instalador",
               "Cidade", "Status", "Data da Baixa", "Cód. Baixa", "Desc. Cód. Baixa"]
    rows = [
        headers,
        ["46000", "1234567", "260000001", "RETIRAR EQUIPAMENTO", "TESTE",
         "NATAL", "2", "46000", "106", "CLIENTE AUSENTE"],
        ["46001", "1234567", "260000001", "RETIRAR EQUIPAMENTO", "TESTE",
         "NATAL", "4", "46001", "430", "EQUIPAMENTO RETIRADO"],
        ["46001", "1234567", "260000001  260000002", "RETIRAR EQUIPAMENTO", "TESTE",
         "NATAL", "2", "46001", "106", "DUAS OS NO CAMPO"],
        ["46001", "RUA EXEMPLO", "RUA EXEMPLO", "RETIRAR EQUIPAMENTO", "TESTE",
         "NATAL", "4", "46001", "106", "INVALIDO"],
    ]
    body = []
    for index, values in enumerate(rows, 1):
        cells = []
        for col, value in enumerate(values):
            letter = chr(65 + col)
            cells.append(f'<c r="{letter}{index}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        body.append(f'<row r="{index}">{"".join(cells)}</row>')
    xml = ('<?xml version="1.0" encoding="utf-8"?>'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<sheetData>' + "".join(body) + '</sheetData></worksheet>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/worksheets/sheet1.xml', xml)

class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.database = self.root / 'seed.sqlite'
        self.xlsx = self.root / 'backlog 1 ano NTL 03.11.xlsx'
        make_xlsx(self.xlsx)

    def test_seed_preserves_separate_os_occurrences_and_checkpoint(self):
        result = ingest(self.database, self.xlsx)
        self.assertEqual(result['rows'], 3)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['profile'], 'natal')
        self.assertTrue(ingest(self.database, self.xlsx)['already_imported'])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM history_seed_rows').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT count(*) FROM history_seed_rejections').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM history').fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT count(*) FROM history WHERE verification='xlsx_seed_ambiguous_os'").fetchone()[0],1)
            self.assertEqual({x[0] for x in db.execute('SELECT code FROM history')}, {'106','430'})
            self.assertEqual(db.execute('SELECT date FROM checkpoint WHERE profile=?',('natal',)).fetchone()[0],
                             (dt.date(1899,12,30)+dt.timedelta(days=46001)).isoformat())

    def test_bad_archive_rolls_back(self):
        bad = self.root / 'backlog 1 ano FTZ 03.11.xlsx'
        bad.write_bytes(b'badzip')
        with self.assertRaises(zipfile.BadZipFile):
            ingest(self.database, bad)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM history_seed_rows').fetchone()[0], 0)

class DummyService:
    def __init__(self, path):
        self.db = path
        self.busy = False
        self.runs = []
    @contextmanager
    def _connect(self):
        connection=sqlite3.connect(self.db)
        try: yield connection
        finally: connection.close()
    def route_import_state(self):
        return {"running":False}
    def snapshot(self):
        return {'running': self.busy}
    def start(self, **kw):
        self.runs.append(kw)
        return {'run_id': 'run'+str(len(self.runs))}

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = DummyService(Path(self.tmp.name)/'schedule.sqlite')
        self.current = dt.datetime(2026,11,3,21,59,tzinfo=LOCAL_TZ)
        self.scheduler = DailyHistoryScheduler(self.svc,now=lambda: self.current)
    def test_one_launch_at_22h_and_next_day(self):
        self.assertEqual(self.scheduler.tick(),'outside_window')
        self.current = self.current.replace(hour=22,minute=0)
        self.assertEqual(self.scheduler.tick(),'started')
        self.assertEqual(self.scheduler.tick(),'already_started')
        self.assertEqual(self.svc.runs[0]['days_per_profile'], 7)
        self.assertIs(self.svc.runs[0]['include_today'], True)
        self.current += dt.timedelta(days=1)
        self.assertEqual(self.scheduler.tick(),'started')
        self.assertEqual(len(self.svc.runs),2)
    def test_busy_and_cutoff(self):
        self.current = self.current.replace(hour=22,minute=0)
        self.svc.busy=True
        self.assertEqual(self.scheduler.tick(),'reader_busy')
        self.svc.busy=False
        self.assertEqual(self.scheduler.tick(),'started')
        self.current+=dt.timedelta(days=1, minutes=46)
        self.assertEqual(self.scheduler.tick(),'outside_window')

if __name__=='__main__':
    unittest.main()
