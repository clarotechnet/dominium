"""Read-only packet tests; do not connect to production."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"integrations"/"serial_consult"))
from used_equipment_datasnap import packet_for,captured_records,PROVIDERS,PARAM

class UsedEquipmentProtocolTests(unittest.TestCase):
 def test_provider_names_and_exact_parameter_set(self):
  for mode,provider in PROVIDERS.items():
   pkt=packet_for(dt.date(2026,10,28),dt.date(2026,10,28),mode=mode,root=ROOT)
   self.assertTrue(pkt.startswith(bytes([len(provider)+32])+provider))
   parsed=captured_records(pkt)
   self.assertEqual(set(parsed),{
     "@RETURN_VALUE","@DataIni","@DataFim","@IdParceiro",
     "@IdTipoServico","@IdGrupoEquipamento"})
   self.assertEqual(len(parsed),6)
 def test_period_rejected_if_invalid(self):
  with self.assertRaises(ValueError):
   packet_for(dt.date(2026,10,30),dt.date(2026,10,29),root=ROOT)
  with self.assertRaises(ValueError):
   packet_for(dt.date(2026,1,1),dt.date(2026,2,28),root=ROOT)
  with self.assertRaises(ValueError):
   packet_for(dt.date(2099,1,1),dt.date(2099,1,1),root=ROOT)
  with self.assertRaises(ValueError):
   packet_for(dt.date(2026,10,28),dt.date(2026,10,28),mode="write",root=ROOT)
 def test_no_material_write_methods(self):
  from used_equipment_datasnap import METHOD
  self.assertEqual(METHOD,"TDtmOrdemServico.AS_GetRecords")

if __name__=="__main__":
 unittest.main()
