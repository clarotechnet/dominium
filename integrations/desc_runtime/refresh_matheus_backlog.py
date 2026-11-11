"""Update four native TODOS/TODOS snapshots, read-only, in an isolated SQLite DB.

Run on DOMINIUM Windows server. No XLSX generated and no Imperium writes.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),r"C:\DominiumRuntime\DescRelay-20261010",
                r"C:\DominiumRuntime\BacklogLab-20261030\app",
                r"C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA"]
from backlog_matheus_current import MatheusCurrentSnapshot, PROFILES
from backlog_read_guard import OperationalReadGate
from order_reports import fetch_rows

DEFAULT_DB=Path(r"C:\DominiumRuntime\BacklogLab-20261030\data\imperium_current_todos.sqlite3")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=DEFAULT_DB)
    ap.add_argument("--profile",choices=PROFILES)
    ap.add_argument("--day")
    args=ap.parse_args()
    collector=MatheusCurrentSnapshot(args.db,fetch=fetch_rows,
             gate=OperationalReadGate())
    success=[]
    errors={}
    for profile in ((args.profile,) if args.profile else PROFILES):
        try:
            row=collector.refresh(profile,args.day)
            print(json.dumps({"result":"ok","profile":profile,"day":row["day"],
                "count":row["count"],"cities":row["cities"],
                "statuses":row["statuses"]},ensure_ascii=False),flush=True)
            success.append(profile)
        except Exception as exc:
            errors[profile]=type(exc).__name__+": "+str(exc)[:180]
            print(json.dumps({"result":"failed","profile":profile,
                              "reason":errors[profile]},ensure_ascii=False),flush=True)
    print(json.dumps({"successful_profiles":success,"failed_profiles":errors,
                      "total":sum(s["count"] for s in collector.summary()
                                  if s["profile"] in success and
                                     (not args.day or s["day"]==args.day))},
                     ensure_ascii=False),flush=True)
    return 0 if not errors else 1
if __name__=="__main__":
    raise SystemExit(main())
