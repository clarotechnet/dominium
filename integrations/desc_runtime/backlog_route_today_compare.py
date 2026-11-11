"""Join today's five TOA route batches with Matheus's current native report.

Informational only: the TOA source controls close code and movements. Never
interpret an Imperium status, a cached report, or an approximate contract match
as authorization to write a DataSnap OS close.
"""
from __future__ import annotations
import datetime as dt
import re
import sqlite3
import unicodedata
from collections import Counter,defaultdict
from contextlib import closing
from pathlib import Path

PROFILES={"NATAL":"natal","PARNAMIRIM":"natal","NATAL/PARNAMIRIM":"natal",
          "FORTALEZA":"fortaleza","MOSSORO":"mossoro","RECIFE":"recife"}
EXPECTED=set(PROFILES.values())

def norm(text):
    value=unicodedata.normalize("NFKD",str(text or "").strip().upper())
    return "".join(x for x in value if not unicodedata.combining(x))

def norm_wo(value):
    raw=str(value or "").strip()
    cleaned=re.sub(r"[^0-9]","",raw)
    # Require a full Work Order number to avoid false positives (e.g. "0").
    return cleaned if 12 <= len(cleaned) <= 18 else ""

def code3(value):
    match=re.match(r"^\s*([0-9]{3})(?=\s|\b|$)",str(value or ""))
    return match.group(1) if match else ""

def readonly(path):
    # sqlite URI avoids creating a DB if an input is missing.
    value=Path(path)
    if not value.is_file():
        raise FileNotFoundError("Snapshot or backlog DB is missing")
    return sqlite3.connect(value.resolve().as_uri()+"?mode=ro",uri=True,timeout=10)

def reconcile_today(backlog_db,current_db,day:dt.date,limit:int=2500):
    if not isinstance(day,dt.date) or not 1<=limit<=2500:
        raise ValueError("Invalid comparison date/limit")
    report_day=day.isoformat()
    route_day=day.strftime("%d/%m/%y")
    with closing(readonly(current_db)) as current,closing(readonly(backlog_db)) as backlog:
        current.row_factory=sqlite3.Row
        backlog.row_factory=sqlite3.Row
        snap=current.execute("""SELECT profile,day,count,captured_at,sha256 FROM snapshots
                               WHERE day=?""",(report_day,)).fetchall()
        profiles={s["profile"] for s in snap}
        if profiles!=EXPECTED:
            raise ValueError("Today's snapshots are incomplete")
        docs=current.execute("""SELECT profile,contract,id_os,os_number,city,status,
                                       close_code,captured_at,work_order
                                 FROM current_os WHERE day=?""",(report_day,)).fetchall()
        by_contract=defaultdict(list)
        for doc in docs:
            by_contract[(doc["profile"],doc["contract"])].append(doc)
        route=backlog.execute("""SELECT r.contract,r.city,r.os_number,r.route_code,
                                       r.activity_status,r.activity_type,
                                       r.activity_date,b.filename
                                FROM route_rows r JOIN route_batches b
                                ON b.route_hash=r.route_hash
                                WHERE r.activity_date=?
                                ORDER BY r.city,r.contract,r.row_num""",(route_day,)).fetchall()
        if len(route)>25000:
            raise ValueError("Too many TOA route rows")
        results=[]
        counts=Counter()
        cities=Counter()
        discrepancies=Counter()
        for item in route:
            city=norm(item["city"])
            profile=PROFILES.get(city)
            contract=str(item["contract"] or "").strip()
            candidates=by_contract.get((profile,contract),[]) if profile else []
            # The route's so-called OS column is the Oracle Work Order (WO),
            # e.g. 01695|741785997. The Imperium NumOs is a distinct number.
            # Require BOTH contract and normalized WO for an exact match.
            os_number=str(item["os_number"] or "").strip()
            route_wo=norm_wo(os_number)
            exact=[x for x in candidates if route_wo and
                   norm_wo(x["work_order"])==route_wo]
            selected=None
            if not profile:
                state="unsupported_city"
            elif len(exact)==1:
                state="exact_wo"
                selected=exact[0]
            elif len(exact)>1:
                state="ambiguous_wo"
            elif len(candidates)==1:
                state="unique_contract_no_wo"
                selected=candidates[0]
            elif not candidates:
                state="missing_in_imperium_snapshot"
            else:
                state="ambiguous_contract"
            counts[state]+=1
            cities[city]+=1
            toa_code=code3(item["route_code"])
            imp_code=str(selected["close_code"] or "") if selected else ""
            # Even exact WO matching produces only a review signal, never
            # an instruction to change a completed code in the Imperium.
            conflict=(state=="exact_wo" and bool(toa_code and imp_code) and
                      toa_code!=imp_code)
            if conflict:
                discrepancies["code_mismatch_exact_wo"]+=1
            if (state=="exact_wo" and selected and
                    selected["status"]=="EM CAMPO" and
                    norm(item["activity_status"]) in
                    {"CONCLUIDO","CONCLUIDA","COMPLETE","COMPLETED"}):
                discrepancies["toa_complete_imperium_open"]+=1
            if len(results)<limit:
                results.append({"contract":contract,"city":city,
                    "profile":profile,"toa_os_number":os_number,
                    "toa_status":str(item["activity_status"] or ""),
                    "toa_code":toa_code,
                    "imperium_os_number":selected["os_number"] if selected else None,
                    "imperium_status":selected["status"] if selected else None,
                    "imperium_code":imp_code or None,
                    "match":state,"code_discrepancy":conflict,
                    "note":"Informational only; confirm live TOA before writing."})
        return {"ok":True,"read_only":True,"day":report_day,
                "route_rows":len(route),"snapshot_rows":len(docs),
                "snapshots":[dict(s) for s in snap],
                "matches":dict(counts),"route_cities":dict(cities),
                "discrepancies":dict(discrepancies),"rows":results,
                "warning":"Only exact_wo matches contract and WO; all statuses remain read-only evidence."}
