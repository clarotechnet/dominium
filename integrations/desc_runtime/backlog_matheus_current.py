"""Read-only daily Imperium TODOS/TODOS snapshot for DOMINIUM DESC.

Reuses the original 42-column report reader. Does NOT export XLSX, mutate
an existing backlog history, infer TOA movements, or authorize OS closures.
Profiles natal (also Parnamirim), fortaleza, mossoro, recife.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import threading
import unicodedata
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

PROFILES = ("natal", "fortaleza", "mossoro", "recife")
STATUS = {"1": "EM CAMPO", "2": "CONCLUIDA", "3": "CANCELADA", "4": "REAGENDADA"}
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;
CREATE TABLE IF NOT EXISTS snapshots (
  profile TEXT NOT NULL, day TEXT NOT NULL, captured_at TEXT NOT NULL,
  source TEXT NOT NULL, count INTEGER NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY(profile,day));
CREATE TABLE IF NOT EXISTS current_os (
  profile TEXT NOT NULL, day TEXT NOT NULL, id_os INTEGER NOT NULL,
  os_number TEXT NOT NULL, contract TEXT NOT NULL, city TEXT NOT NULL,
  service TEXT NOT NULL, installer TEXT NOT NULL,
  status_code TEXT NOT NULL, status TEXT NOT NULL, close_code TEXT,
  date_closed TEXT, captured_at TEXT NOT NULL,
  work_order TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(profile,day,id_os));
CREATE INDEX IF NOT EXISTS ix_current_contract
  ON current_os(profile,contract,day);
CREATE INDEX IF NOT EXISTS ix_current_city
  ON current_os(profile,day,city,status_code);
"""

def clean(value: object) -> str:
    return str(value if value is not None else "").strip()

def city_normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value).upper())
    return "".join(x for x in text if not unicodedata.combining(x))

def nonzero_integer(value: object, field: str) -> int:
    raw = clean(value)
    if not re.fullmatch(r"[0-9]{1,15}", raw) or int(raw) <= 0:
        raise ValueError("Invalid "+field+" in Imperium report")
    return int(raw)

def text_number(value: object, field: str) -> str:
    raw = clean(value)
    if not re.fullmatch(r"[0-9]{1,18}", raw):
        raise ValueError("Invalid "+field+" in Imperium report")
    return raw

def os_number_value(value: object) -> str:
    raw = clean(value)
    # Some manual Imperium OS numbers intentionally repeat the contract;
    # Recife can carry two 9-digit blocks. Preserve original spacing/suffix.
    # These identifiers are informational and are NEVER used to send a write.
    if not (re.fullmatch(r"[0-9]{1,18}", raw) or
            re.fullmatch(r"[0-9]{6,10} {1,2}[0-9]{6,10}[A-Z]?", raw)):
        raise ValueError("Invalid NumOs in Imperium report")
    return raw

def normalize_row(profile: str, day: str, value: dict, stamp: str) -> tuple:
    if not isinstance(value, dict):
        raise ValueError("Non-object Imperium report row")
    identity = nonzero_integer(value.get("IdOs"), "IdOs")
    number = os_number_value(value.get("NumOs"))
    contract = text_number(value.get("NumeroContrato"), "NumeroContrato")
    status_code = clean(value.get("Status"))
    if status_code not in STATUS:
        raise ValueError("Unknown Imperium OS status: "+status_code[:10])
    city = city_normalize(value.get("Cidade"))
    if not city or len(city)>80:
        raise ValueError("Invalid city")
    code = clean(value.get("CodigoBaixa"))
    if code:
        if not re.fullmatch(r"[0-9]{1,3}", code):
            raise ValueError("Invalid close code")
        code = code.zfill(3)
    else:
        code = None
    # Status 2 with no code is permitted as a discrepancy, not silently fixed.
    service = clean(value.get("Servico"))[:160]
    installer = clean(value.get("NomeAbreviado"))[:180]
    date_closed = clean(value.get("DataBaixa"))[:40] or None
    work_order=clean(value.get("NumeroWO"))
    if len(work_order)>60 or any(ord(ch)<32 for ch in work_order):
        raise ValueError('Invalid NumeroWO in Imperium report')
    return (profile,day,identity,number,contract,city,service,installer,
            status_code,STATUS[status_code],code,date_closed,stamp,work_order)

class MatheusCurrentSnapshot:
    def __init__(self,db_path:Path,*,fetch,gate,clock=None):
        self.path=Path(db_path)
        self.fetch=fetch
        self.gate=gate
        self.clock=clock or (lambda: dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))))
        self.lock=threading.Lock()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._db() as conn:
            conn.executescript(SCHEMA)
            columns={row[1] for row in conn.execute('PRAGMA table_info(current_os)')}
            if 'work_order' not in columns:
                conn.execute("ALTER TABLE current_os ADD COLUMN work_order TEXT NOT NULL DEFAULT ''")
            conn.commit()

    @contextmanager
    def _db(self):
        conn=sqlite3.connect(self.path,timeout=10)
        try:
            yield conn
        finally:
            conn.close()

    def refresh(self,profile:str,day:str|None=None)->dict:
        if profile not in PROFILES:
            raise ValueError("Unknown profile")
        now=self.clock()
        local_day=now.date()
        selected=dt.date.fromisoformat(day) if day else local_day
        if not (local_day-dt.timedelta(days=7)<=selected<=local_day):
            raise ValueError("Refresh only permits recent 8-day window")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Refresh already running")
        try:
            # A failure leaves the previous complete snapshot untouched.
            self.gate()
            source=self.fetch(profile,selected.isoformat(),selected.isoformat(),"all")
            if not isinstance(source,list):
                raise ValueError("Invalid native report response")
            stamp=now.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
            rows=[normalize_row(profile,selected.isoformat(),v,stamp) for v in source]
            identifiers=[r[2] for r in rows]
            if len(identifiers)!=len(set(identifiers)):
                raise ValueError("Duplicate IdOs in report")
            if len(rows)>100000:
                raise ValueError("Exceeded native report max rows")
            canonical=json.dumps(
                [r[:-1] for r in sorted(rows,key=lambda v:v[2])],
                ensure_ascii=True,separators=(",",":"))
            digest=hashlib.sha256(canonical.encode()).hexdigest()
            with self._db() as conn:
                existing=conn.execute(
                    "SELECT count FROM snapshots WHERE profile=? AND day=?",
                    (profile,selected.isoformat())).fetchone()
                if existing and existing[0]>0 and not rows:
                    raise ValueError("Refuse to replace a non-empty snapshot with empty result")
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM current_os WHERE profile=? AND day=?",
                             (profile,selected.isoformat()))
                conn.executemany(
                    "INSERT INTO current_os VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",rows)
                conn.execute("""INSERT INTO snapshots(profile,day,captured_at,source,count,sha256)
                 VALUES(?,?,?,?,?,?) ON CONFLICT(profile,day) DO UPDATE SET
                 captured_at=excluded.captured_at,source=excluded.source,
                 count=excluded.count,sha256=excluded.sha256""",
                 (profile,selected.isoformat(),stamp,
                  "Imperium DataSnap TODOS/TODOS - native 42 columns",len(rows),digest))
                conn.commit()
            by_city=Counter(r[5] for r in rows)
            by_status=Counter(r[9] for r in rows)
            return {"ok":True,"profile":profile,"day":selected.isoformat(),
                    "count":len(rows),"captured_at":stamp,"sha256":digest,
                    "cities":dict(sorted(by_city.items())),
                    "statuses":dict(sorted(by_status.items())),
                    "noncanonical_os_numbers":sum(not r[3].isdigit() for r in rows)}
        finally:
            self.lock.release()

    def summary(self):
        with self._db() as conn:
            cursor=conn.execute("""SELECT profile,day,captured_at,count,sha256
              FROM snapshots ORDER BY day DESC,profile""")
            return [dict(zip(("profile","day","captured_at","count","sha256"),r))
                    for r in cursor.fetchall()]

    def contract(self,profile:str,contract:str,day:str):
        if profile not in PROFILES:
            raise ValueError("Unknown profile")
        contract=text_number(contract,"contract")
        dt.date.fromisoformat(day)
        with self._db() as conn:
            cursor=conn.execute("""SELECT id_os,os_number,city,service,installer,
               status,close_code,captured_at,work_order FROM current_os
               WHERE profile=? AND contract=? AND day=? ORDER BY id_os""",
               (profile,contract,day))
            rows=cursor.fetchall()
            return {"profile":profile,"contract":contract,"day":day,
              "match_count":len(rows),"ambiguous":len(rows)>1,
              "rows":[dict(zip(("id_os","os_number","city","service","installer",
                       "status","close_code","captured_at","work_order"),r)) for r in rows],
              "note":"Informational snapshot only. Never authorize an OS close."}
