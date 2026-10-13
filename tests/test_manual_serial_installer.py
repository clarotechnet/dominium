from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('manual_serial_installer', ROOT / 'integrations/desc_review_bot/install_manual_serial.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ManualSerialInstallerTests(unittest.TestCase):
    def test_surgical_server_patch_preserves_history_routes_store_options_and_existing_code(self):
        source = """const PREFIX='/desc-review';
  const store=createReviewStore({directory,groups,technicians,now,retentionDays:7});
const untouchedHistory = 'history remains';
    if(req.method==='GET'&&url.pathname===PREFIX+'/state'){json(res,200,{...status,csrf:session.csrf,batches:store.current()});}
    if(req.method==='GET'&&url.pathname===PREFIX+'/history'){archiveRead();}
    if(req.method==='POST'&&url.pathname===PREFIX+'/decision'){decision();}
"""
        patched = MODULE.patch_server(source)
        self.assertIn('retentionDays:7', patched)
        self.assertIn("const untouchedHistory = 'history remains';", patched)
        self.assertIn("PREFIX+'/history'){archiveRead();}", patched)
        self.assertIn('capabilities:{manual_serial:true}', patched)
        self.assertIn('operator_session:d.review_session', patched)
        self.assertEqual(MODULE.patch_server(patched), patched)

    def test_private_proxy_allowlist_preserves_history_and_refuses_unknown_templates(self):
        source = "allowed = {'GET': {'state', 'history', 'report.xlsx'}, 'POST': {'decision', 'refresh', 'technician', 'manual'}}"
        patched = MODULE.patch_proxy(source)
        self.assertIn("'GET': {'state', 'history', 'report.xlsx'}", patched)
        self.assertIn("'serial-lookup', 'serial-apply'", patched)
        self.assertEqual(MODULE.patch_proxy(patched), patched)
        with self.assertRaises(ValueError):
            MODULE.patch_proxy("allowed = {'POST': {'execute'}}")

    def test_incomplete_install_is_rejected_and_crlf_is_preserved(self):
        with self.assertRaises(ValueError):
            MODULE.patch_server('const createManualSerialReview = partial;')
        self.assertEqual(MODULE.preserved_bytes(b'old\r\n', 'new\n'), b'new\r\n')
