import unittest
from http import HTTPStatus
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

from app import PanelHandler
from desc_review_proxy import ProxyResponse


class DisconnectionAccessTests(unittest.TestCase):
    def handler(self, user):
        proxy = Mock()
        proxy.forward.return_value = ProxyResponse(200, 'application/json', b'{"mode":"test"}')
        return SimpleNamespace(
            _current_user=lambda: user, _json=Mock(), server=SimpleNamespace(desc_review_proxy=proxy),
            _body=lambda: {'id': 'one', 'actor': 'forged'}, _auth_audit=Mock(),
            send_response=Mock(), send_header=Mock(), end_headers=Mock(), wfile=BytesIO(),
        )

    def test_anonymous_and_viewer_cannot_read_state_or_photos(self):
        for user in [None, {'role': 'viewer', 'username': 'reader'}]:
            for path in ['/api/disconnection/state', '/api/disconnection/photo/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg']:
                handler = self.handler(user)
                PanelHandler._desc_request(handler, 'GET', path)
                self.assertEqual(handler._json.call_args.args[0], HTTPStatus.FORBIDDEN)
                handler.server.desc_review_proxy.forward.assert_not_called()

    def test_controller_identity_and_audit_come_from_session(self):
        handler = self.handler({'role': 'controller', 'display_name': 'Dalton'})
        PanelHandler._desc_request(handler, 'POST', '/api/disconnection/decision')
        self.assertEqual(handler.server.desc_review_proxy.forward.call_args.kwargs['actor'], 'Dalton')
        handler._auth_audit.assert_called_once_with('desc_review', '200', target='one')
        self.assertEqual(handler.wfile.getvalue(), b'{"mode":"test"}')

    def test_manual_query_session_binding_is_trusted_and_changes_on_login(self):
        bindings = []
        for token_hash in ('1' * 64, '2' * 64):
            handler = self.handler({'id': 42, 'role': 'controller', 'display_name': 'Dalton'})
            handler._auth_session = lambda: {'token_hash': token_hash}
            handler._body = lambda: {'id': 'one', 'review_session': 'forged'}
            PanelHandler._desc_request(handler, 'POST', '/api/disconnection/serial-lookup')
            bindings.append(handler.server.desc_review_proxy.forward.call_args.args[2]['review_session'])
        self.assertRegex(bindings[0], r'^[a-f0-9]{64}$')
        self.assertNotEqual(bindings[0], bindings[1])
        self.assertNotEqual(bindings[0], 'forged')

    def test_session_endpoint_is_not_publicly_exposed(self):
        handler = self.handler({'role': 'admin', 'username': 'admin'})
        PanelHandler._desc_request(handler, 'POST', '/api/disconnection/session')
        self.assertEqual(handler._json.call_args.args[0], HTTPStatus.BAD_REQUEST)
        handler.server.desc_review_proxy.forward.assert_not_called()
