import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from desc_review_proxy import ProxyResponse
from desc_review_relay import DescRelayHandler
from desc_order_verifier import DescOrderVerifier
from imperium_api import Order
from tests.test_desc_order_verifier import ReadOnlyAPI


class DescRelayTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), DescRelayHandler)
        self.server.relay_token = 'private-fixture-token'
        self.server.review_proxy = Mock()
        self.server.review_proxy.forward.return_value = ProxyResponse(200, 'application/json', b'{"mode":"test"}')
        self.imperium = ReadOnlyAPI([Order(11, '123456', '1234567', 7, 'DESC')])
        self.server.order_verifier = DescOrderVerifier(api_factory=lambda *args, **kwargs: self.imperium)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_public_request_is_denied_without_internal_credential(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(f'http://127.0.0.1:{self.server.server_port}/api/disconnection/state')
        self.assertEqual(error.exception.code, 401)
        self.server.review_proxy.forward.assert_not_called()

    def test_authenticated_relay_preserves_operator_identity(self):
        request = Request(f'http://127.0.0.1:{self.server.server_port}/api/disconnection/decision',
                          data=json.dumps({'id': 'one', 'actor': 'forged'}).encode(),
                          headers={'Authorization': 'Bearer private-fixture-token',
                                   'X-Dominium-Actor': 'Jos%C3%A9', 'Content-Type': 'application/json'})
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)['mode'], 'test')
        self.assertEqual(self.server.review_proxy.forward.call_args.kwargs['actor'], 'José')

    def order_request(self, *, payload=None, data=None, headers=None, path='/internal/order-check', method='POST'):
        if data is None:
            data = json.dumps(payload or {'profile_key': 'natal', 'contract': '1234567',
                                         'date': '2026-10-10', 'os_numbers': ['123456']}).encode()
        request_headers = {'Authorization': 'Bearer private-fixture-token',
                           'X-Dominium-Actor': 'Bot DESC', 'Content-Type': 'application/json'}
        request_headers.update(headers or {})
        request = Request(f'http://127.0.0.1:{self.server.server_port}{path}',
                          data=data, headers=request_headers, method=method)
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_internal_order_check_returns_real_detail_without_forwarding_to_review_proxy(self):
        status, result = self.order_request()
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'])
        self.assertTrue(result['confirmed'])
        self.assertEqual(result['source'], 'imperium_detail')
        self.assertEqual(result['orders'][0]['installer_id'], 892)
        self.server.review_proxy.forward.assert_not_called()
        self.assertEqual([item[0] for item in self.imperium.reads], ['list_orders', 'order_installer'])

    def test_internal_order_check_requires_same_bearer_and_actor(self):
        for headers, expected in [({'Authorization': ''}, 401),
                                  ({'Authorization': 'Bearer incorrect'}, 401),
                                  ({'Authorization': 'Bearer é'}, 401),
                                  ({'X-Dominium-Actor': ''}, 400)]:
            with self.subTest(headers=headers):
                status, result = self.order_request(headers=headers)
                self.assertEqual(status, expected)
                self.assertFalse(result['ok'])
        self.assertEqual(self.imperium.reads, [])
        self.server.review_proxy.forward.assert_not_called()

    def test_internal_order_check_rejects_malformed_body_before_reading_imperium(self):
        for data, headers in [(b'{', {}), (b'[]', {}), (b'\xff', {}), (b'', {}),
                              (b'x' * (64 * 1024 + 1), {}),
                              (b'{}', {'Content-Type': 'text/plain'}),
                              (b'{}', {'Content-Length': 'invalid'})]:
            with self.subTest(size=len(data), headers=headers):
                status, result = self.order_request(data=data, headers=headers)
                self.assertEqual(status, 400)
                self.assertFalse(result['ok'])
        self.assertEqual(self.imperium.reads, [])

    def test_internal_order_check_schema_cannot_supply_executor_or_actor(self):
        status, result = self.order_request(payload={'profile_key': 'natal', 'contract': '1234567',
                                                   'os_numbers': ['123456'], 'actor': 'forged',
                                                   'execute': True})
        self.assertEqual(status, 400)
        self.assertFalse(result['ok'])
        self.assertEqual(self.imperium.reads, [])

    def test_internal_order_check_missing_requested_order_never_assumes_success(self):
        status, result = self.order_request(payload={'profile_key': 'natal', 'contract': '1234567',
                                                   'os_numbers': ['999999']})
        self.assertEqual(status, 409)
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'], 'imperium_unconfirmed')

    def test_internal_order_check_empty_selection_can_report_completed_no_match_search(self):
        status, result = self.order_request(payload={'profile_key': 'natal', 'contract': '7654321',
                                                   'os_numbers': []})
        self.assertEqual(status, 200)
        self.assertTrue(result['searched'])
        self.assertEqual(result['source'], 'open_orders_no_match')
        self.assertEqual(result['orders'], [])

    def test_internal_order_check_backend_failure_does_not_leak_exception(self):
        self.imperium.error = OSError('credential=private-fixture-secret')
        status, result = self.order_request()
        self.assertEqual(status, 503)
        self.assertFalse(result['ok'])
        self.assertEqual(result.get('code'), 'imperium_unavailable')
        self.assertNotIn('private-fixture-secret', json.dumps(result))

    def test_internal_order_check_route_is_exact_and_post_only(self):
        for path, method in [('/internal/order-check?execute=true', 'POST'),
                             ('/internal/order-check/', 'POST'),
                             ('/internal/order-check', 'GET'),
                             ('/api/disconnection/order-check', 'POST')]:
            with self.subTest(path=path, method=method):
                status, result = self.order_request(path=path, method=method)
                self.assertNotEqual(status, 200)
                self.assertFalse(result['ok'])
        self.assertEqual(self.imperium.reads, [])
        self.server.review_proxy.forward.assert_not_called()
