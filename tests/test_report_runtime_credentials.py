"""Imperium reports and serial history use the active runtime credential."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeCredentialTests(unittest.TestCase):
    def test_reports_and_serial_use_active_runtime_even_with_a_legacy_credential(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = Path(tmp) / "active Imperium"
            (active / "config").mkdir(parents=True)
            (active / "config" / "credentials.dat").write_bytes(b"synthetic active protected data")
            legacy = Path(tmp) / "legacy" / "config" / "credentials.dat"
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b"unreadable old protected data")
            shutil.copyfile(ROOT / "protocol_templates.json", active / "protocol_templates.json")
            script = r'''
import os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path("integrations/serial_consult").resolve()))
import order_reports, commission_reports, serial_datasnap
active = Path(os.environ["DOMINIUM_IMPERIUM_RUNTIME_ROOT"])
expected = active / "config" / "credentials.dat"
seen = []
class StopBeforeNetwork(Exception): pass
def load(path):
    seen.append(path)
    assert path == expected, "Report attempted the obsolete credential"
    assert path.read_bytes() == b"synthetic active protected data"
    return {"username": "synthetic", "password": "synthetic"}
class Client:
    def __init__(self, *args, **kwargs): raise StopBeforeNetwork()
with patch("datasnap_client.load_credentials", side_effect=load), patch("datasnap_client.DataSnapClient", Client):
    for operation, args in [
        (order_reports.fetch_rows, ("natal", "2026-01-01", "2026-01-01", "all")),
        (commission_reports.fetch_datasets, ("natal", "2026-01-01", "2026-01-01")),
    ]:
        try: operation(*args)
        except StopBeforeNetwork: pass
        else: raise AssertionError("Expected network boundary")
with patch.object(serial_datasnap, "load_credentials", side_effect=load), patch.object(serial_datasnap, "DataSnapClient", Client):
    try: serial_datasnap.fetch_serial_history("ZZZZZZZZZZZZ")
    except StopBeforeNetwork: pass
    else: raise AssertionError("Expected network boundary")
assert seen == [expected, expected, expected]
assert order_reports.CREDENTIALS == commission_reports.CREDENTIALS == expected
print("Report and serial clients selected the active protected credential")
'''
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=ROOT,
                env={**os.environ, "DOMINIUM_IMPERIUM_RUNTIME_ROOT": str(active)},
                capture_output=True, text=True, timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Report and serial clients selected", result.stdout)


if __name__ == "__main__":
    unittest.main()
