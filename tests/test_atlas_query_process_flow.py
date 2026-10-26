"""Use the official process state before trusting an advertised attachment."""
import base64
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'serial_consult'))
import atlas_query_pipeline as pipeline
from atlas_query_report import AtlasAuthRequired, claim_job, save_queue, read_job

QUEUE = '276922323'
REPORT = 'https://batatlas.netservicos.com.br/app-3//RELATORIOS/261026/Relatorio_Equipamentos_Analitico_demo.xls'


def process_page(status, queue=QUEUE):
    return f'<html><table><tr><td>{queue}</td><td>RELATORIO_EQUIPAMENTOS</td></tr></table><span>status.fila.{status}</span></html>'


class ProcessChrome:
    def __init__(self, body, status=200):
        self.body, self.status = body, status
        self.tab = object()
        self.closed_streams = []
        self.attachment_opened = False

    def open(self, *args, **kwargs):
        pass

    def call(self, tab, method, params, timeout=12):
        if method == 'Page.getFrameTree':
            return {'frameTree': {'frame': {'id': 'test-frame'}}}
        if method == 'Network.loadNetworkResource':
            assert params['url'] == f'https://atlas.netservicos.com.br/nettask/filas/processos.do?idFila={QUEUE}'
            assert params['options']['includeCredentials'] is True
            return {'resource': {'httpStatusCode': self.status, 'stream': 'process-stream'}}
        if method == 'IO.read':
            return {'data': base64.b64encode(self.body.encode()).decode(), 'base64Encoded': True, 'eof': True}
        if method == 'IO.close':
            self.closed_streams.append(params['handle'])
            return {}
        raise AssertionError(method)

    def eval(self, expression):
        if "buscarFilasTipoConsultaId('/nettask'" in expression:
            return {'started': True}
        if "querySelector('#divFilas')" in expression:
            return [{'text': f'{QUEUE} RELATORIO_EQUIPAMENTOS COMPLETO',
                     'detail': f"abreDetalhesFila('/nettask','{QUEUE}','3','false')"}]
        if "abreDetalhesFila('/nettask',id" in expression:
            return {'ok': True}
        if "ready:location.pathname" in expression:
            return {'ready': True, 'tab': True}
        if "selecionarTab('/nettask','anexos'" in expression:
            self.attachment_opened = True
            return True
        if "Relatorio_Equipamentos_Analitico/i" in expression:
            return [REPORT]
        raise AssertionError('Unexpected Atlas action')

    def close(self):
        pass


class ProcessTests(unittest.TestCase):
    def read(self, chrome):
        reader = getattr(pipeline, 'read_process_state', None)
        self.assertTrue(callable(reader), 'Official process-state reader is missing')
        return reader(chrome, QUEUE)

    def test_official_process_state_is_id_bound_and_stream_is_closed(self):
        for label, expected in [('completo', 'complete'), ('processando', 'processing'),
                                ('nova', 'processing'), ('falhou', 'failed')]:
            with self.subTest(label=label):
                chrome = ProcessChrome(process_page(label))
                self.assertEqual(self.read(chrome), expected)
                self.assertEqual(chrome.closed_streams, ['process-stream'])

    def test_unconfirmed_process_cannot_be_complete(self):
        for body in [process_page('completo', '276999999'), '<html>status.fila.completo</html>',
                     process_page('unknown'), process_page('completo') + '<span>status.fila.processando</span>']:
            self.assertEqual(self.read(ProcessChrome(body)), 'unknown')

    def test_process_login_is_not_terminal_report_failure(self):
        for body, status in [('<html>Login</html>', 401), ('<input type="password">', 200)]:
            chrome = ProcessChrome(body, status)
            reader = getattr(pipeline, 'read_process_state', None)
            self.assertTrue(callable(reader), 'Official process-state reader is missing')
            with self.assertRaises(AtlasAuthRequired):
                reader(chrome, QUEUE)
            self.assertEqual(chrome.closed_streams, ['process-stream'])

    def test_unavailable_or_excessive_process_response_stays_unknown(self):
        for chrome in [ProcessChrome('unavailable', 404), ProcessChrome('x' * 600_000)]:
            self.assertEqual(self.read(chrome), 'unknown')
            self.assertEqual(chrome.closed_streams, ['process-stream'])

    def test_complete_table_does_not_open_attachments_while_process_is_yellow(self):
        chrome = ProcessChrome(process_page('processando'))
        with patch.object(pipeline.time, 'sleep'):
            result = pipeline.evaluate_query(chrome, QUEUE)
        self.assertEqual(result['state'], 'processing')
        self.assertFalse(chrome.attachment_opened)

    def test_complete_process_unlocks_attachment_and_failure_stops_it(self):
        for label, expected in [('completo', 'complete'), ('falhou', 'failed')]:
            chrome = ProcessChrome(process_page(label))
            with patch.object(pipeline.time, 'sleep'):
                result = pipeline.evaluate_query(chrome, QUEUE)
            self.assertEqual(result['state'], expected)
            self.assertEqual(chrome.attachment_opened, expected == 'complete')

    def test_unknown_process_has_explicit_wait_reason(self):
        chrome = ProcessChrome('<html>not confirmed</html>')
        with patch.object(pipeline.time, 'sleep'):
            result = pipeline.evaluate_query(chrome, QUEUE)
        self.assertEqual(result['state'], 'processing')
        self.assertEqual(result['error_code'], 'process_status_unconfirmed')
        self.assertFalse(chrome.attachment_opened)

    def test_recheck_failure_preserves_id_and_never_downloads_old_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'jobs.sqlite3'
            job, _ = claim_job('natal', 'empreiteira', db, created_by='user-1')
            save_queue(job, QUEUE, db)
            pipeline.upgrade_db(db)
            for process_state in ['failed', 'processing']:
                pipeline.update_job(job, db, state='attachment_wait', completed_at=100,
                                    attachment_url=REPORT, attachment_failures=3, next_attachment_check=0)
                with patch.object(pipeline, 'evaluate_query', return_value={'state': process_state}):
                    chrome = ProcessChrome('unused')
                    # This fake rejects every download URL except the process view.
                    result = pipeline.fetch_file(job, db, chrome_factory=lambda: chrome, clock=lambda: 200)
                self.assertEqual(result['state'], process_state)
                self.assertEqual(read_job(job, db)['remote_queue_id'], QUEUE)
                self.assertEqual(read_job(job, db)['state'], process_state)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute('select count(*) from query_jobs').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
