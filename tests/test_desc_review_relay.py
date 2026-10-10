import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from desc_review_proxy import ProxyResponse
from desc_review_relay import DescRelayHandler


class DescRelayTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), DescRelayHandler)
        self.server.relay_token = 'private-fixture-token'
        self.server.review_proxy = Mock()
        self.server.review_proxy.forward.return_value = ProxyResponse(200, 'application/json', b'{"mode":"test"}')
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
