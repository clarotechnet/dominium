"""Bounded read-only DataSnap enrichment for stock XLSX reports.

Uses the existing Dominium serial consultation, not a new Imperium protocol.
Evidence is stored per serial so an interrupted job can resume without querying
already confirmed serials again. A movement is NEVER evidence of current custody.
"""
from __future__ import annotations
import json
import re
import sqlite3
import time
from pathlib import Path
from contextlib import closing
from typing import Callable

SUPPORTED = re.compile(r"[A-Z0-9]{12}\Z")
SUSPICIOUS = {"SUSPEITO", "ANALISE DE INVENTARIO"}
MAX_BATCH = 20


def target_serials(kind: str, rows: list[dict]) -> list[str]:
    from stock_analysis_http import _normalized_state
    selected = []
    seen = set()
    for row in rows:
        if kind == "suspeitos" and _normalized_state(row) not in SUSPICIOUS:
            continue
        main = str(row.get("numero_serie") or "").strip().upper()
        mac = str(row.get("enderecavel_principal") or "").strip().upper()
        serial = next((candidate for candidate in (main, mac)
                       if SUPPORTED.fullmatch(candidate)), None)
        if serial and serial not in seen:
            seen.add(serial)
            selected.append(serial)
    return selected


def normalize_entry(item: dict) -> dict:
    """Retain just provenance, bounded historical evidence, and verified custody."""
    movement = item.get("datasnap") if isinstance(item.get("datasnap"), dict) else {}
    live = item.get("live") if isinstance(item.get("live"), dict) else {}
    last = item.get("last_destination") if isinstance(item.get("last_destination"), dict) else {}
    owner = live.get("owner") if isinstance(live.get("owner"), dict) else {}
    events = movement.get("movements") if isinstance(movement.get("movements"), list) else []
    last_event = max((e for e in events if isinstance(e,dict)),
                    key=lambda e: int(e.get("Id") or 0),default={})
    verified_history = movement.get("verified") is True
    current_verified = live.get("verified") is True and live.get("found") is True
    return {
        "serial":str(item.get("serial") or "").upper(),
        "history_verified":verified_history,
        "movement_count":len(events) if verified_history else None,
        "last_movement":str(last.get("movement") or "")[:120],
        "last_movement_date":str(last.get("date") or "")[:80],
        "last_destination_historical":str(last.get("stock_name") or "")[:180],
        "last_contract_historical":str(last_event.get("Contrato") or "")[:80],
        "current_owner_verified":current_verified,
        "current_owner":str(owner.get("technician_name") or "")[:160] if current_verified else "",
        "history_error":str(item.get("history_error") or "")[:180],
        "source":"imperium_datasnap_live" if verified_history else "imperium_datasnap_unconfirmed",
    }


def collect(job_id: str, city: str, kind: str, rows: list[dict], *,
            db_path: Path, consult: Callable | None = None,
            progress: Callable[[dict],None] | None = None,
            max_records: int = 2000) -> tuple[list[dict],dict]:
    if not re.fullmatch("[a-f0-9]{32}",str(job_id)) or not 1<=max_records<=2000:
        raise ValueError("Identificador ou limite invalido")
    if kind not in ("suspeitos","equipamentos"):
        return [],{"datasnap_checked":0,"datasnap_total":0,"datasnap_failed":0}
    targets=target_serials(kind,rows)
    selected=targets[:max_records]
    with closing(sqlite3.connect(db_path,timeout=25)) as con, con:
        con.execute("""CREATE TABLE IF NOT EXISTS report_evidence (
          job_id TEXT NOT NULL, serial TEXT NOT NULL, evidence_json TEXT NOT NULL,
          PRIMARY KEY(job_id, serial))""")
        cached={serial:json.loads(data) for serial,data in
                con.execute("SELECT serial,evidence_json FROM report_evidence WHERE job_id=?",(job_id,))}
    todo=[s for s in selected if s not in cached]
    if consult is None:
        from serial_service import consult_serials
        consult=consult_serials
    failures=sum(not v.get("history_verified") for v in cached.values())
    for at in range(0,len(todo),MAX_BATCH):
        batch=todo[at:at+MAX_BATCH]
        try:
            result=consult((batch,"analitico",city))
            if not isinstance(result,dict) or result.get("ok") is not True:
                raise RuntimeError("Imperium nao confirmou a consulta")
            found={str(item.get("serial") or "").upper():item
                   for item in result.get("results",[]) if isinstance(item,dict)}
        except Exception as error:
            found={}
        with closing(sqlite3.connect(db_path,timeout=25)) as con, con:
            for serial in batch:
                item=found.get(serial,{"serial":serial,"history_error":"DataSnap indisponivel ou consulta nao confirmada"})
                normalized=normalize_entry(item)
                if not normalized["history_verified"]:failures+=1
                cached[serial]=normalized
                con.execute("""INSERT OR REPLACE INTO report_evidence(job_id,serial,evidence_json)
                    VALUES(?,?,?)""",(job_id,serial,json.dumps(normalized,ensure_ascii=False)))
        if progress:
            progress({"datasnap_checked":len(cached),"datasnap_total":len(targets),
                      "datasnap_failed":failures})
        time.sleep(0.05)  # Avoid tight loops against private operational bridge.
    return [cached[serial] for serial in selected if serial in cached],{
        "datasnap_checked":len(selected),"datasnap_total":len(targets),
        "datasnap_failed":failures,"datasnap_unchecked":max(0,len(targets)-len(selected)),
    }
