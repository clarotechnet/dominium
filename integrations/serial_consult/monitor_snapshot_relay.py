"""Read-only bridge for the existing TOA CSV monitor snapshots.

The canonical application persists snapshots to logs/monitor-snapshots/<profile>.json.
No snapshot means {active:false}; it does NOT mean an error or fabricated data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

MONITOR_ROOT=Path(os.environ.get("DOMINIUM_MONITOR_SNAPSHOT_ROOT",
                    r"C:\DominiumMain\logs\monitor-snapshots"))
PROFILES={"natal","fortaleza","mossoro","recife"}

def read_monitor_snapshot(target: str, *, root: Path=MONITOR_ROOT) -> dict:
    url=urlsplit(target)
    if url.path!="/api/monitor/snapshot" or url.scheme or url.netloc or url.fragment:
        raise ValueError("Rota de monitor invalida")
    parsed=parse_qs(url.query,strict_parsing=True)
    if set(parsed)!={"profile"} or len(parsed["profile"])!=1 or parsed["profile"][0] not in PROFILES:
        raise ValueError("Operacao do monitor invalida")
    city=parsed["profile"][0]
    filename=Path(root)/(city+".json")
    try:
        if filename.stat().st_size>16*1024*1024:
            raise ValueError("Retrato acima do limite")
        snapshot=json.loads(filename.read_text(encoding="utf-8"))
    except (FileNotFoundError,PermissionError,UnicodeError,json.JSONDecodeError,OSError):
        snapshot=None
    if not isinstance(snapshot,dict) or snapshot.get("profile")!=city or not isinstance(snapshot.get("orders"),list):
        snapshot=None
    return {"ok":True,"active":snapshot is not None,"snapshot":snapshot}
