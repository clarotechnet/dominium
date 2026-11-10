"""Controlled HTTP routes for observations after a 409 close.
Mocked backend: never opens DataSnap and never changes a real O.S.
"""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import app


class PostCloseObservationRouteTests(unittest.TestCase):
    def make_handler(self, *, action="preview", role="admin", profile="natal"):
        handler=app.PanelHandler.__new__(app.PanelHandler)
        handler.path=f"/api/orders/2239585/observation/{action}?profile={profile}"
        handler._security_preflight=lambda method,path:True
        handler._current_user=lambda:{"id":1,"role":role}
        handler._auth_audit=lambda *a,**k:None
        handler._body=lambda **k:{
            "contract":"4332297","os_number":"2664945723",
            "text":"Observacao de teste, sem escrita real",
            "snapshot_sha256":"1"*64,
            "idempotency_key":"5731a135-a408-4084-bac3-900966b8b997",
        }
        responses=[]
        handler._json=lambda code,data:responses.append((int(code),data))
        return handler,responses

    def test_preview_calls_only_safe_reader(self):
        handler,responses=self.make_handler()
        profile=SimpleNamespace(key="natal",api=object())
        with patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"preview_closed_observation",return_value={
                "preview_only":True,"code":"409","snapshot_sha256":"1"*64
             }) as preview, \
             patch.object(app,"append_closed_observation_once") as write:
            handler.do_POST()
        self.assertEqual(responses[0][0],200)
        self.assertTrue(responses[0][1]["preview_only"])
        preview.assert_called_once()
        write.assert_not_called()

    def test_write_disabled_by_default(self):
        handler,responses=self.make_handler(action="append")
        profile=SimpleNamespace(key="natal",api=object())
        with patch.dict(os.environ,{"DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS":"0"}), \
             patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"append_closed_observation_once") as writer:
            handler.do_POST()
        self.assertEqual(responses[0][0],403)
        writer.assert_not_called()

    def test_controller_cannot_write_even_with_flag(self):
        handler,responses=self.make_handler(action="append",role="controller")
        profile=SimpleNamespace(key="natal",api=object())
        with patch.dict(os.environ,{"DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS":"1"}), \
             patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"append_closed_observation_once") as writer:
            handler.do_POST()
        self.assertEqual(responses[0][0],403)
        writer.assert_not_called()

    def test_other_profile_not_authorized(self):
        handler,responses=self.make_handler(profile="fortaleza")
        profile=SimpleNamespace(key="fortaleza",api=object())
        with patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"preview_closed_observation") as preview:
            handler.do_POST()
        self.assertEqual(responses[0][0],403)
        preview.assert_not_called()

    def test_write_once_with_flag_and_admin(self):
        handler,responses=self.make_handler(action="append")
        profile=SimpleNamespace(key="natal",api=object())
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ,{"DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS":"1"}), \
             patch.object(app,"LOG_ROOT",Path(tmp)), \
             patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"append_closed_observation_once",
                return_value={"ok":True,"confirmed":True,"code":"409"}
             ) as writer:
            handler.do_POST()
            writer.assert_called_once()
            self.assertTrue(writer.call_args.kwargs["enable_live"])
        self.assertEqual(responses[0][0],200)
        self.assertTrue(responses[0][1]["confirmed"])

    def test_busy_gate_does_not_write(self):
        handler,responses=self.make_handler()
        profile=SimpleNamespace(key="natal",api=object())
        acquired=app.OPERATION_GATE.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            with patch.object(app,"_profile_from_query",return_value=profile), \
                 patch.object(app,"preview_closed_observation") as preview:
                handler.do_POST()
            preview.assert_not_called()
            self.assertEqual(responses[0][0],409)
        finally:
            app.OPERATION_GATE.release()

    def test_invalid_identity_denied_before_imperium(self):
        handler,responses=self.make_handler()
        handler._body=lambda **kwargs:{"contract":"bad","os_number":"2664945723","text":"teste"}
        profile=SimpleNamespace(key="natal",api=object())
        with patch.object(app,"_profile_from_query",return_value=profile), \
             patch.object(app,"preview_closed_observation") as preview:
            handler.do_POST()
        self.assertEqual(responses[0][0],400)
        preview.assert_not_called()

    def test_get_capability_read_only_admin(self):
        handler,responses=self.make_handler()
        handler.path="/api/observations/capabilities?profile=natal"
        with patch.dict(os.environ,{"DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS":"0"}), \
             patch.object(app,"_profile_from_query",return_value=SimpleNamespace(key="natal")):
            handler.do_GET()
        self.assertEqual(responses[0][0],200)
        self.assertFalse(responses[0][1]["write_enabled"])
        self.assertTrue(responses[0][1]["preview_enabled"])


if __name__=="__main__":
    unittest.main()
