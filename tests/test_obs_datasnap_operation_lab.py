"""No-network integration tests for guarded note update. Synthetic fixtures only."""
import contextlib,hashlib,json,struct,tempfile,threading,unittest,uuid
from pathlib import Path
from test_obs_datasnap_lab import record
from obs_datasnap_operation_lab import (
 append_once,preview_readonly,fields_unchanged,ObservationConflict,ObservationResultUncertain,
)
from obs_datasnap_lab import make_append_preview

class FakeClient:
 def __init__(self,api):self.api=api
 def __enter__(self):return self
 def __exit__(self,*args):return None
 def request(self,action,params):
  self.api.calls+=1
  if self.api.fail_on_apply:
   raise TimeoutError("synthetic response timeout")
  if action=="execute" and len(params)==2:
   self.api.detail=record(note=self.api.applied_note)
  return {"result":[None,{"data":[0,self.api.apply_success]}]}

class FakeAPI:
 def __init__(self,old="PREVIA",after="PREVIA"+chr(13)+chr(10)+"NOVA",fail=False):
  self.detail=record(note=old)
  self.applied_note=after
  self.fail_on_apply=fail
  self.calls=0
  self._operation_lock=threading.Lock()
  self.apply_success=b"OK_SYNTHETIC"
 @staticmethod
 def _detail_parts(detail):return detail,bytes(19)
 @staticmethod
 def _detail_context(detail):
  return type("Ctx",(),{"id_os":2239585,"contract":"4332297"})()
 @staticmethod
 def _packet_from_modified_record(row,mask,suffix):
  return b"#Dsp"+mask+row+suffix
 def _client(self,timeout=7):return FakeClient(self)
 @staticmethod
 def _fetch_detail_on(client,id_os):return client.api.detail
 @staticmethod
 def _handle(client,method):assert method=="TDtmOrdemServico.AS_ApplyUpdates";return 15

def base_call(api,tmp,expected_hash=None,key=None,enable=True):
 if expected_hash is None:expected_hash=hashlib.sha256(api.detail).hexdigest()
 return append_once(api,2239585,"2664945723","4332297","NOVA",
     expected_hash,key or str(uuid.uuid4()),Path(tmp),enable_live=enable)

class OperationTests(unittest.TestCase):
 def test_live_disabled_default(self):
  with tempfile.TemporaryDirectory() as d:
   a=FakeAPI()
   with self.assertRaises(ObservationConflict):
    base_call(a,d,enable=False)
   self.assertEqual(a.calls,0)
 def test_preview_readonly(self):
  a=FakeAPI()
  result=preview_readonly(a,2239585,"2664945723","4332297","NOVA")
  self.assertTrue(result["preview_only"]);self.assertEqual(a.calls,0)
 def test_stale_snapshot_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   a=FakeAPI()
   with self.assertRaises(ObservationConflict):
    base_call(a,d,expected_hash="f"*64)
   self.assertEqual(a.calls,0)
 def test_append_once_and_confirm(self):
  with tempfile.TemporaryDirectory() as d:
   a=FakeAPI()
   key=str(uuid.uuid4())
   result=base_call(a,d,key=key)
   self.assertTrue(result["confirmed"])
   self.assertEqual(a.calls,1)
   rows=list(Path(d).glob("OBS_*.json"))
   self.assertEqual(len(rows),1)
   self.assertEqual(json.loads(rows[0].read_text())["state"],"CONFIRMED_READBACK")
 def test_duplicate_intent_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   a=FakeAPI();key=str(uuid.uuid4())
   original=hashlib.sha256(a.detail).hexdigest()
   result=base_call(a,d,expected_hash=original,key=key)
   self.assertTrue(result["confirmed"])
   with self.assertRaises(ObservationConflict):
    base_call(a,d,expected_hash=original,key=key)
   self.assertEqual(a.calls,1)
 def test_timeout_no_retry(self):
  with tempfile.TemporaryDirectory() as d:
   a=FakeAPI(fail=True)
   with self.assertRaises(ObservationResultUncertain):
    base_call(a,d)
   self.assertEqual(a.calls,1)
   self.assertEqual(len(list(Path(d).glob("OBS_*.json"))),1)
 def test_unrelated_field_changed_detection(self):
  a=FakeAPI()
  before=record(note="PREVIA")
  after=record(note="PREVIA"+chr(13)+chr(10)+"NOVA")
  self.assertTrue(fields_unchanged(a,before,after,2239585,"2664945723","4332297"))
  self.assertFalse(fields_unchanged(a,before,record(note="NOVA",contract="8888888"),2239585,"2664945723","4332297"))
if __name__=="__main__":unittest.main(verbosity=2)
