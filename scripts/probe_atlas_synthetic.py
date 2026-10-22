"""Synthetic Atlas queue smoke test. NEVER prints records, tokens or request IDs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from atlas_bridge_client import AtlasBridgeClient, AtlasBridgeError

client = AtlasBridgeClient()
try:
    status = client.status()
    print("atlas_extension_online:", status.get("online") is True)
    print("atlas_pending_before:", status.get("pendingQueries"))
    if status.get("online") is not True:
        raise SystemExit(2)
    if int(status.get("pendingQueries") or 0) != 0:
        print("smoke_test_skipped_existing_queue")
        raise SystemExit(0)
    result = client.query("TEST00000001", timeout=50.0, poll_interval=1.5)
    print("synthetic_query_ok:", result.get("ok") is True)
    if result.get("ok") is True:
        value=result["resultado"]
        print("serial_matched:", value.get("serial_consultado")=="TEST00000001")
        print("records_present:", bool(value.get("historico")))
        print("atlas_report_partial:", value.get("partial") is True)
    else:
        print("synthetic_query_error_code:",result.get("error"))
except AtlasBridgeError as error:
    print("synthetic_query_unavailable:",str(error))
    raise SystemExit(3)
