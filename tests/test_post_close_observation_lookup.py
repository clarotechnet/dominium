"""Lookup of completed Natal OS for post-close observation; no real network."""
import datetime as dt
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import app

class ObservationLookupTests(unittest.TestCase):
 def handler(self,profile="natal",role="admin",day=None):
  day = day or (dt.date.today() - dt.timedelta(days=1)).isoformat()
  h=app.PanelHandler.__new__(app.PanelHandler)
  h.path="/api/observations/resolve?profile="+profile
  h._security_preflight=lambda *a:True
  h._current_user=lambda:{"role":role}
  h._body=lambda **kw:{"date":day,"contract":"4332297","os_number":"2664945723"}
  out=[]
  h._json=lambda status,payload:out.append((int(status),payload))
  return h,out
 @staticmethod
 def fake_profile(key="natal",rows=None):
  return SimpleNamespace(key=key,api=SimpleNamespace(list_orders=lambda *a,**k: rows if rows is not None else []))
 def test_resolves_exact_closed_os(self):
  h,out=self.handler()
  rows=[
   SimpleNamespace(id_os=2239585,contract="4332297",num_os="2664945723",service="Ponto Virtua"),
   SimpleNamespace(id_os=2239584,contract="4332297",num_os="2664945712",service="Inst Assinatura"),
  ]
  with patch.object(app,"_profile_from_query",return_value=self.fake_profile(rows=rows)):
   h.do_POST()
  self.assertEqual(out[0][0],200)
  self.assertEqual(out[0][1]["id_os"],2239585)
  self.assertEqual(out[0][1]["next"],"preview_observation")
 def test_no_match(self):
  h,out=self.handler()
  with patch.object(app,"_profile_from_query",return_value=self.fake_profile()):
   h.do_POST()
  self.assertEqual(out[0][0],404)
 def test_duplicate_fails_closed(self):
  h,out=self.handler()
  row=SimpleNamespace(id_os=2239585,contract="4332297",num_os="2664945723",service="Ponto Virtua")
  with patch.object(app,"_profile_from_query",return_value=self.fake_profile(rows=[row,row])):
   h.do_POST()
  self.assertEqual(out[0][0],404)
 def test_wrong_profile_forbidden(self):
  h,out=self.handler(profile="fortaleza")
  with patch.object(app,"_profile_from_query",return_value=self.fake_profile(key="fortaleza")):
   h.do_POST()
  self.assertEqual(out[0][0],403)
 def test_date_too_old_does_not_query(self):
  h,out=self.handler(day="2025-01-01")
  api=SimpleNamespace(list_orders=lambda *a,**k: (_ for _ in ()).throw(AssertionError("must_not_call")))
  with patch.object(app,"_profile_from_query",return_value=SimpleNamespace(key="natal",api=api)):
   h.do_POST()
  self.assertEqual(out[0][0],400)
 def test_role_non_operational_denied(self):
  h,out=self.handler(role="reader")
  with patch.object(app,"_profile_from_query",return_value=self.fake_profile()):
   h.do_POST()
  self.assertEqual(out[0][0],403)

if __name__=="__main__":unittest.main()
