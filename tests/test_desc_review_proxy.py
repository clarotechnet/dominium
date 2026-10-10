import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from desc_review_proxy import DescReviewProxy, ProxyError
except ModuleNotFoundError:
    DescReviewProxy = None
    ProxyError = ValueError


class ReviewBackend(BaseHTTPRequestHandler):
    received = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.received.append((self.path, data, dict(self.headers)))
        if self.path == '/desc-review/session':
            self.send_response(200)
            self.send_header('Set-Cookie', 'desc_review=private-session; HttpOnly')
            payload = {'csrf': 'private-csrf'}
        else:
            self.send_response(200)
            payload = {'ok': True, 'actor': data['actor']}
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        self.received.append((self.path, {}, dict(self.headers)))
        if getattr(self.server, 'redirect_state', False):
            self.send_response(302)
            self.send_header('Location', '/outside-review')
            self.end_headers()
            return
        self.send_response(200)
        if self.path.startswith('/desc-review/photo/'):
            self.send_header('Content-Type', 'image/jpeg')
            payload = b'photo-content'
        else:
            self.send_header('Content-Type', 'application/json')
            payload = json.dumps({'mode': 'test', 'csrf': 'private-csrf', 'batches': []}).encode()
        self.end_headers()
        self.wfile.write(payload)


class DescProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ThreadingHTTPServer(('127.0.0.1', 0), ReviewBackend)
        cls.thread = threading.Thread(target=cls.backend.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.backend.shutdown()
        cls.backend.server_close()
        cls.thread.join()

    def setUp(self):
        self.assertIsNotNone(DescReviewProxy, 'proxy not implemented')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        access = Path(self.directory.name) / 'access.txt'
        access.write_text('12345678')
        self.proxy = DescReviewProxy(origin=f'http://127.0.0.1:{self.backend.server_port}', access_file=access)
        ReviewBackend.received.clear()

    def test_state_keeps_private_session_and_csrf_on_backend(self):
        response = self.proxy.forward('GET', '/api/disconnection/state', actor='Dalton')
        self.assertEqual(response.status, 200)
        self.assertNotIn('private-', response.body.decode())
        self.assertEqual(json.loads(response.body)['mode'], 'test')
        self.assertEqual(ReviewBackend.received[-1][2]['Cookie'], 'desc_review=private-session')

    def test_decision_identity_comes_from_authenticated_actor(self):
        response = self.proxy.forward('POST', '/api/disconnection/decision', {'id': 'batch', 'revision': 3, 'actor': 'forged'}, actor='Dalton')
        self.assertEqual(json.loads(response.body)['actor'], 'Dalton')
        self.assertEqual(ReviewBackend.received[-1][2]['X-Review-Csrf'], 'private-csrf')

    def test_photos_are_bytes_and_no_arbitrary_upstream_path_is_allowed(self):
        response = self.proxy.forward('GET', '/api/disconnection/photo/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg', actor='Dalton')
        self.assertEqual(response.content_type, 'image/jpeg')
        self.assertEqual(response.body, b'photo-content')
        for path in ['/api/disconnection/../session', '/api/disconnection/session', '/api/disconnection/photo/%2e%2e/file', '/api/disconnection/state?url=http://attacker']:
            with self.assertRaises(ProxyError):
                self.proxy.forward('GET', path, actor='Dalton')

    def test_missing_server_credentials_report_unavailability(self):
        self.proxy.access_file = Path(self.directory.name) / 'missing'
        with self.assertRaises(ProxyError):
            self.proxy.forward('GET', '/api/disconnection/state', actor='Dalton')

    def test_redirect_cannot_forward_private_session_to_another_endpoint(self):
        self.proxy._authenticate()
        self.backend.redirect_state = True
        self.addCleanup(setattr, self.backend, 'redirect_state', False)
        with self.assertRaises(ProxyError):
            self.proxy.forward('GET', '/api/disconnection/state', actor='Dalton')
        self.assertNotIn('/outside-review', [row[0] for row in ReviewBackend.received])

    def test_origin_rejects_query_and_fragment(self):
        for suffix in ['?next=http://other', '#fragment']:
            with self.assertRaises(ProxyError):
                DescReviewProxy(origin=self.proxy.origin + suffix)

