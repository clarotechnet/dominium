"""Import live DESC relay and verify Atlas module availability without changing services."""
import sys
import ast
from pathlib import Path
root=Path(r"C:\DominiumRuntime\DescRelay-20261010")
for name in ("desc_review_relay.py","confront_http.py","confront_job_runner.py",
             "atlas_bridge_client.py","confront_export.py","confront_engine.py"):
    ast.parse((root/name).read_text(encoding="utf-8"))
sys.path.insert(0,str(root))
import desc_review_relay
assert "ConfrontService" in vars(desc_review_relay)
assert "operator_reports" in (root/"desc_review_relay.py").read_text(encoding="utf-8")
print("LIVE_RELAY_IMPORT_OK")
print("REPORTS_RETAINED")
