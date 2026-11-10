"""Offline tests: observation-only DataSnap payload builder (no network)."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from obs_datasnap_lab import (
 ObservationFormatError,decode_observation,create_note_suffix,
 make_append_preview,NOTE_MASK,NOTE_TRAILER,
)
def s(t):
 b=t.encode("cp1252");assert len(b)<256;return bytes([len(b)])+b
def memo(t):
 b=t.encode("cp1252");return struct.pack("<H",len(b))+b
def record(os="2664945723",contract="4332297",code="409",note=None,obs18=None):
 p=struct.pack("<I",2239585)+s(os)+s(contract)+struct.pack("<I",10)
 p+=s("ADS") + s("ADESAO") +struct.pack("<I",20)+s("TARDE")
 p+=bytes(8)+struct.pack("<I",44)+s(code)+s("CONCLUIDA")
 p+=bytes(16)+struct.pack("<I",900)+s("TECNICO")
 p+=struct.pack("<I",1)+s("SINGLE")
 if obs18 is not None:p+=memo(obs18)
 p+=bytes(4)+bytes(16)+bytes(16)
 p+=struct.pack("<II",0,1)+s("NET")
 if note is not None:p+=memo(note)
 p+=bytes([2])+s("")+s("CLIENTE DE TESTE")+s("RUA DE TESTE")+s("CASA")
 p+=bytes(40)
 return p
class FakeAPI:
 @staticmethod
 def _detail_parts(detail):return detail,bytes(19)
 @staticmethod
 def _packet_from_modified_record(row,mask,suffix):return b"#Dsp"+mask+row+suffix

class ObservationTests(unittest.TestCase):
 def test_initial_empty(self):
  result=decode_observation(record(),"2239585" if False else 2239585,"2664945723","4332297")
  self.assertEqual(result.note,"")
  self.assertFalse(result.present)
  self.assertEqual(result.code,"409")
 def test_existing_with_other_observation(self):
  result=decode_observation(record(note="OBS 1",obs18="TEXTO COMUM"),2239585,"2664945723","4332297")
  self.assertTrue(result.present);self.assertEqual(result.note,"OBS 1")
 def test_append_preserves_old(self):
  preview,blob=make_append_preview(FakeAPI(),record(note="OBS ANTIGA"),2239585,"2664945723","4332297","OBS NOVA")
  self.assertEqual(preview.new_length,len("OBS ANTIGA"+chr(13)+chr(10)+"OBS NOVA"))
  self.assertIn(("OBS ANTIGA"+chr(13)+chr(10)+"OBS NOVA").encode("cp1252"),blob)
  self.assertEqual(blob[-len(NOTE_TRAILER):],NOTE_TRAILER)
  self.assertIn(bytes([8])+NOTE_MASK+bytes([2]),blob)
 def test_duplicate_fail(self):
  with self.assertRaises(ObservationFormatError):make_append_preview(FakeAPI(),record(note="OBS NOVA"),2239585,"2664945723","4332297","OBS NOVA")
 def test_identity_fail(self):
  with self.assertRaises(ObservationFormatError):decode_observation(record(),2239585,"2664945712","4332297")
 def test_open_state_fail(self):
  with self.assertRaises(ObservationFormatError):make_append_preview(FakeAPI(),record(code="000"),2239585,"2664945723","4332297","NOVA")
 def test_bad_unicode_fail(self):
  with self.assertRaises(ObservationFormatError):create_note_suffix("emoji "+chr(0x1f4be))
 def test_oversize_fail(self):
  with self.assertRaises(ObservationFormatError):create_note_suffix("X"*1001)
 def test_mask_exact_field25(self):
  self.assertEqual(NOTE_MASK[6],0xa2)
  self.assertTrue(all(x==0xaa for i,x in enumerate(NOTE_MASK) if i!=6))
if __name__=="__main__":unittest.main(verbosity=2)
