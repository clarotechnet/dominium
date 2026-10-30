import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from monitor_snapshot_relay import read_monitor_snapshot

class MonitorSnapshotRelayTests(unittest.TestCase):
 def test_absent_snapshot_returns_normal_empty_state(self):
  with tempfile.TemporaryDirectory() as d:
   data=read_monitor_snapshot("/api/monitor/snapshot?profile=natal",root=Path(d))
   self.assertEqual(data,{"ok":True,"active":False,"snapshot":None})
 def test_read_saved_snapshot_without_guessing(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/"natal.json").write_text(json.dumps({"profile":"natal","orders":[{"num_os":"10"}]}),encoding="utf-8")
   data=read_monitor_snapshot("/api/monitor/snapshot?profile=natal",root=Path(d))
   self.assertTrue(data["active"])
   self.assertEqual(data["snapshot"]["orders"][0]["num_os"],"10")
 def test_no_path_traversal_or_other_city(self):
  with tempfile.TemporaryDirectory() as d:
   for target in ("/api/monitor/snapshot?profile=../recife",
                  "/api/monitor/snapshot?profile=all",
                  "/api/monitor/snapshot?profile=natal&profile=recife",
                  "/api/monitor/snapshot?profile=recife&debug=1"):
    with self.assertRaises(ValueError):
     read_monitor_snapshot(target,root=Path(d))

if __name__=="__main__":
 unittest.main()
