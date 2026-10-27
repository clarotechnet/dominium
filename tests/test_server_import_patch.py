import datetime as dt
import ast
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy/server-import-all'))
from toa_import_scope import validate_import_route

from install import build_changes


SNAPSHOT = Path(os.environ.get('DOMINIUM_IMPORT_SOURCE', '/workspace/scratch/940fb3ab71f6/import_all_source'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(SNAPSHOT.exists(), 'Requires a private source-only runtime snapshot')
class ServerPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SNAPSHOT))
        from desc_only_scope import DESC_ALLOWED_ROUTES
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        for item in SNAPSHOT.glob('*'):
            if item.is_file():
                shutil.copy2(item, cls.root / item.name)
        # The private snapshot contains the real import functions, not the full app.
        # Add only the unchanged surrounding import/factory anchors for patch checks.
        (cls.root / 'app.py').write_text(
            (cls.root / 'app_functions.py').read_text() + '\n'
            'from desc_only_scope import DESC_ALLOWED_ROUTES, filter_desc_preview\n'
            'from toa_bucket_collector import TOABucketCollector, TOADisconnectionExporter\n'
            'factory = lambda: TOADisconnectionExporter(ROOT, download_root)\n', encoding='utf-8')
        cls.original_app = (cls.root / 'app.py').read_text()
        cls.changes = build_changes(cls.root)
        for name, text in cls.changes.items():
            (cls.root / name).write_text(text, encoding='utf-8')
        sys.path.insert(0, str(cls.root))
        tree = ast.parse((cls.root / 'toa_session_gateway.py').read_text())
        request = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'request_expression')
        namespace = {'dt': dt, 'json': json, 'DESC_ALLOWED_ROUTES': DESC_ALLOWED_ROUTES,
                     'validate_import_route': validate_import_route}
        exec(compile(ast.Module(body=[request], type_ignores=[]), 'gateway', 'exec'), namespace)
        cls.gateway = SimpleNamespace(request_expression=namespace['request_expression'])
        cls.automation = load('automation_import_test', cls.root / 'toa_automation.py')

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(cls.root))
        sys.path.remove(str(SNAPSHOT))
        cls.tmp.cleanup()

    def test_general_gateway_accepts_only_current_day_known_routes(self):
        query = {'route': ['NTL-DMV_VT'], 'date': [dt.date.today().isoformat()]}
        expression = self.gateway.request_expression('/toa/import-export', query)
        self.assertIn('exportRoute("NTL-DMV_VT"', expression)
        with self.assertRaises(ValueError):
            self.gateway.request_expression('/toa/import-export', {**query, 'date': ['2020-01-01']})
        with self.assertRaises(ValueError):
            self.gateway.request_expression('/toa/import-export', {**query, 'route': ['OTHER-DMV']})

    def test_desc_gateway_still_rejects_general_bucket(self):
        with self.assertRaises(ValueError):
            self.gateway.request_expression('/toa/export', {'route': ['NTL-DMV'], 'date': [dt.date.today().isoformat()]})

    def test_scheduler_visits_all_buckets_without_unknown_routes(self):
        module = self.automation
        visited = []
        root = self.root / 'run-test'
        root.mkdir(exist_ok=True)
        class Exporter:
            def __init__(self, _credentials, download_root, **_kwargs):
                self.root = download_root
                self.root.mkdir(parents=True, exist_ok=True)
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def available_routes(self):
                return (*module.DEFAULT_ROUTES, {'route': 'OTHER-DMV', 'target': 'rn', 'label': 'invalid'})
            def export_route(self, route):
                path = self.root / (route + '.csv')
                path.write_text('fixture')
                return path
        def import_callback(route, _path):
            visited.append(route['route'])
            return {'status': 'concluida', 'imported': 1, 'not_imported': 0}
        automation = module.TOAAutomation(root, import_callback, exporter_factory=Exporter,
                                         logger=logging.getLogger('test'), export_spacing_seconds=0)
        automation._run('test')
        self.assertEqual(set(visited), module.IMPORT_ALLOWED_ROUTES)
        self.assertEqual(len(visited), 13)
        self.assertTrue(automation.last_run['ok'])

    def test_patch_keeps_city_validation_and_existing_reconciliation(self):
        app = self.changes['app.py']
        self.assertIn('scope.validate_target(profile.key, order.city)', app)
        self.assertIn('preexisting_keys=preexisting_keys', app)
        self.assertIn('_remember_confirmed_toa_orders(profile, path, result)', app)
        self.assertIn('filter_import_preview(preview, route=route["route"])', app)

    def test_adhesion_reaches_importer_without_calling_close(self):
        from tests.test_server_import_scope import Order, Preview
        from toa_import_scope import filter_import_preview
        tree = ast.parse(self.changes['app.py'])
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_automatic_toa_import')
        calls = []
        class API:
            def import_toa(self, preview, **kwargs):
                calls.append((preview, kwargs))
                return {'imported': 1}
        profile = SimpleNamespace(api=API(), close_enabled=True, label='Natal')
        namespace = {
            'Path': Path, 'time': time, 'IMPORT_ALLOWED_ROUTES': self.automation.IMPORT_ALLOWED_ROUTES,
            'IMPORT_TARGET_BY_KEY': {'rn': {'profile': 'natal'}}, 'PROFILES': {'natal': profile},
            'LOGGER': logging.getLogger('test'), 'OPERATION_GATE': threading.Lock(),
            '_scoped_import_preview': lambda *_args: Preview((Order(import_date=dt.date.today().strftime('%d/%m/%Y')),)),
            'filter_import_preview': filter_import_preview,
            '_toa_existing_orders_for_run': lambda *_args: set(),
            '_remember_confirmed_toa_orders': lambda *_args: None,
            '_safe_append_import_audit': lambda *_args, **_kwargs: None,
            '_safe_record_import_contracts': lambda *_args: None,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'app_import', 'exec'), namespace)
        path = self.root / 'fixture.csv'
        path.write_text('fixture')
        result = namespace['_automatic_toa_import']({'route': 'NTL-DMV', 'target': 'rn'}, path)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0].orders[0].os_type, 'Adesao Ponto Virtua')

    def test_unexpected_source_is_rejected_before_mutation(self):
        path = self.root / 'toa_secondary_bucket_export.mjs'
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            build_changes(self.root)
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
