"""Source-specific Imperium used-equipment period extraction with local history.

This is NOT the completed six-tab Atlas/Imperium reconciliation. Preserve a
separate 2-tab source workbook (Consolidado, Por Ordem de Serviço) and expose
it only through the authenticated operational relay.

Natal was validated against ClientVCL captures; Mossoro and Recife additionally
passed live read-only DataSnap tests with partner ID 1 on their distinct profile
ports, including verification of the 'Cidade' field in every returned row.
Fortaleza has not passed a real extraction and remains disabled.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from used_equipment_live_datasnap import fetch_read_only
from used_equipment_report import normalize_range

LOGGER = logging.getLogger(__name__)
CONFIRMED_PARTNERS = {"natal": 1, "mossoro": 1, "recife": 1}
CONFIRMED_CITIES = {"mossoro": {"MOSSORO", "MOSSORÓ"}, "recife": {"RECIFE"}}
SHEETS = ("Consolidado Imperium", "Por OS Imperium")
REQUIRED = {
    "consolidado": frozenset(("Grupo","CodigoEquipamento","Equipamento","Qtd","Identificado")),
    "por_os": frozenset(("DataBaixa","NumOs","NumeroWO","CodigoEquipamento","Qtd","Equipamento")),
}
COLS_IF_EMPTY = {
    "consolidado": ("Grupo","CodigoEquipamento","Equipamento","Qtd","Identificado"),
    "por_os": ("DataBaixa","DataBaixaMiscelanea","Contrato","NumOs","CodigoServico",
               "NomeAbreviado","CodigoEquipamento","Qtd","SerialNumber","Identificado",
               "Cidade","TipoServico","Equipamento","Grupo","NumeroWO","CODIBGE",
               "CodParceiraSAP","Controlador","Smart"),
}
ROOT=Path(r"C:\DominiumRuntime\StockAnalysisData\imperium_source")
CREDENTIALS=Path(r"C:\DominiumMain\config\credentials.dat")
MAX_ROWS=60000
MAX_FILE_BYTES=35_000_000
RUN_PATTERN=re.compile(r"[0-9a-f]{32}\Z")
DATE_PATTERN=r"\d{4}-\d{2}-\d{2}"


def source_route(method: str, target: str):
    """Strict route allowlist: caller still needs relay auth + admin role."""
    if method not in ("GET","POST") or len(target)>180 or any(c in target for c in ("#","%","//")):
        return None
    u=urlsplit(target)
    if u.scheme or u.netloc or u.fragment: return None
    if method=="POST" and u.path=="/api/stock/analyses/imperium/extract" and not u.query:
        return "extract",None
    if method!="GET":return None
    if u.path=="/api/stock/analyses/imperium/runs":
        try:q=parse_qs(u.query, strict_parsing=True)
        except ValueError:return None
        if set(q)!={"city","start","end"} or any(len(v)!=1 for v in q.values()):
            return None
        city,start,end=q["city"][0],q["start"][0],q["end"][0]
        if city not in ("natal","mossoro","fortaleza","recife") or not all(
            re.fullmatch(DATE_PATTERN,x) for x in (start,end)
        ):return None
        return "list",(city,start,end)
    if u.query:return None
    m=re.fullmatch(r"/api/stock/analyses/imperium/runs/([a-f0-9]{32})/export",u.path)
    if m:return "export",m.group(1)
    m=re.fullmatch(r"/api/stock/analyses/imperium/runs/([a-f0-9]{32})/sheets/([01])",u.path)
    if m:return "sheet",(m.group(1),int(m.group(2)))
    return None


class ImperiumSourceCatalog:
    def __init__(self, *, root=ROOT, credential_path=CREDENTIALS, fetcher=None, workbook=None):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/"source.sqlite3"
        self.credentials=Path(os.environ.get("DOMINIUM_DATASNAP_CREDENTIALS_FILE",str(credential_path)))
        self.fetcher=fetcher or fetch_read_only
        self.workbook=workbook  # default lazy import avoids stock_analysis_http cycle
        self.busy=threading.Lock()
        with closing(sqlite3.connect(self.db, timeout=20)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS source_runs (
              id TEXT PRIMARY KEY,city TEXT NOT NULL,start_date TEXT NOT NULL,
              end_date TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,
              filename TEXT NOT NULL, sha256 TEXT NOT NULL, counts_json TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS source_sheets (
              run_id TEXT NOT NULL,sheet_index INTEGER NOT NULL,
              header_json TEXT NOT NULL,rows_json TEXT NOT NULL,
              PRIMARY KEY(run_id,sheet_index))""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_source_city_dates
                          ON source_runs(city,start_date,end_date,created_at DESC)""")

    @staticmethod
    def _public(row):
        return {"id":row["id"],"city":row["city"],"start":row["start_date"],"end":row["end_date"],
                "created_at":row["created_at"],"filename":row["filename"],
                "counts":json.loads(row["counts_json"]),"origin":"imperium_datasnap_real_2_abas",
                "complete_six_tab_analysis":False}

    def handle(self,method,target,actor,body=None):
        parsed=source_route(method,target)
        if parsed is None:return 404,{"ok":False,"error":"Rota indisponível"},None
        action,args=parsed
        if not re.fullmatch(r"user-[1-9][0-9]{0,18}", actor or ""):
            return 403,{"ok":False,"error":"Operador inválido"},None
        try:
            if action=="extract":
                return self._extract(actor,body)
            with closing(sqlite3.connect(self.db, timeout=20)) as db, db:
                db.row_factory=sqlite3.Row
                if action=="list":
                    city,start,end=args
                    try:normalize_range(start,end)
                    except ValueError as e:return 400,{"ok":False,"error":str(e)},None
                    runs=db.execute("""SELECT * FROM source_runs
                        WHERE city=? AND start_date=? AND end_date=?
                        ORDER BY created_at DESC LIMIT 50""",(city,start,end)).fetchall()
                    return 200,{"ok":True,"history":[self._public(r) for r in runs],
                                "extraction_enabled":city in CONFIRMED_PARTNERS,
                                "source_only":True},None
                if action=="export":
                    record=db.execute("SELECT id FROM source_runs WHERE id=?",(args,)).fetchone()
                    if not record:return 404,{"ok":False,"error":"Extração não encontrada"},None
                    file=self.root/(args+".xlsx")
                    if not file.is_file():return 503,{"ok":False,"error":"XLSX indisponível"},None
                    raw=file.read_bytes()
                    if len(raw)>MAX_FILE_BYTES:return 413,{"ok":False,"error":"XLSX acima do limite"},None
                    return 200,raw,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if action=="sheet":
                    run_id,index=args
                    row=db.execute("""SELECT header_json,rows_json FROM source_sheets
                        WHERE run_id=? AND sheet_index=?""",(run_id,index)).fetchone()
                    if not row:return 404,{"ok":False,"error":"Aba não encontrada"},None
                    rows=json.loads(row["rows_json"])
                    return 200,{"ok":True,"name":SHEETS[index],
                                "header":json.loads(row["header_json"]),
                                "rows":rows[:200],"total":len(rows),
                                "preview_limited":len(rows)>200},None
        except (OSError,sqlite3.Error,ValueError) as exc:
            LOGGER.warning("Imperium source catalog error=%s",type(exc).__name__)
            return 503,{"ok":False,"error":"Histórico Imperium indisponível"},None
        return 404,{"ok":False,"error":"Rota não encontrada"},None

    def _extract(self, actor, body):
        if not isinstance(body,dict) or set(body)!={"city","start","end"}:
            return 400,{"ok":False,"error":"Informe cidade, data inicial e final"},None
        city,start,end=body["city"],body["start"],body["end"]
        if city not in ("natal","mossoro","fortaleza","recife"):
            return 400,{"ok":False,"error":"Selecione uma única praça válida"},None
        if city not in CONFIRMED_PARTNERS:
            return 409,{"ok":False,"code":"city_not_homologated",
                        "error":"Extração DataSnap ainda não homologada em "+city.upper()+
                        ". O parceiro/resultado de outra cidade não será utilizado."},None
        try:normalize_range(start,end)
        except (TypeError,ValueError) as error:
            return 400,{"ok":False,"error":str(error)},None
        if not self.busy.acquire(blocking=False):
            return 409,{"ok":False,"code":"imperium_busy",
                        "error":"Outra extração do Imperium está em andamento"},None
        try:
            data=self.fetcher(start,end,profile=city,
                              partner_id=CONFIRMED_PARTNERS[city],
                              credential_path=self.credentials)
            if not isinstance(data,dict) or set(data)!=set(REQUIRED):
                raise ValueError("Datasets incompletos")
            # Every row for a homologated independent unit must be scoped to
            # that unit; never save Natal data under Mossoro/Recife.
            expected_cities=CONFIRMED_CITIES.get(city)
            if expected_cities and any(
                str(row.get("Cidade") or "").strip().upper() not in expected_cities
                for row in data["por_os"]
            ):
                raise ValueError("Cidade do dataset DataSnap divergente do perfil")
            converted=[]
            counts={}
            for index,mode in enumerate(("consolidado","por_os")):
                rows=data[mode]
                if not isinstance(rows,list) or len(rows)>MAX_ROWS or any(
                    not isinstance(row,dict) for row in rows
                ):raise ValueError("Registros inconsistentes")
                if rows and not REQUIRED[mode].issubset(rows[0]):
                    raise ValueError("Colunas do Imperium divergentes")
                header=list(rows[0]) if rows else list(COLS_IF_EMPTY[mode])
                if len(header)>60:raise ValueError("Colunas excessivas")
                matrix=[[row.get(c) if row.get(c) is not None else "" for c in header] for row in rows]
                converted.append((SHEETS[index],[header,*matrix]))
                counts[SHEETS[index]]=len(rows)
            if self.workbook is None:
                from stock_analysis_http import xlsx
                writer=xlsx
            else:writer=self.workbook
            blob=writer(converted)
            if not blob.startswith(b"PK\x03\x04") or len(blob)>MAX_FILE_BYTES:
                raise ValueError("XLSX inválido")
            digest=hashlib.sha256(blob).hexdigest()
            with closing(sqlite3.connect(self.db,timeout=20)) as db, db:
                db.row_factory=sqlite3.Row
                prior=db.execute("""SELECT * FROM source_runs WHERE city=? AND start_date=?
                    AND end_date=? AND sha256=? ORDER BY created_at DESC LIMIT 1""",
                    (city,start,end,digest)).fetchone()
                if prior and (self.root/(prior["id"]+".xlsx")).is_file():
                    return 200,{"ok":True,"reused":True,"selected":self._public(prior)},None
                run=uuid.uuid4().hex
                target=self.root/(run+".xlsx")
                temporary=self.root/(run+".tmp")
                temporary.write_bytes(blob)
                temporary.replace(target)
                stamp=datetime.now(timezone.utc).isoformat(timespec="seconds")
                file_name="FONTE-IMPERIUM-"+city.upper()+"-"+start+"-a-"+end+".xlsx"
                record=(run,city,start,end,actor,stamp,file_name,digest,json.dumps(counts))
                with db:
                    db.execute("INSERT INTO source_runs VALUES (?,?,?,?,?,?,?,?,?)",record)
                    db.executemany("INSERT INTO source_sheets VALUES (?,?,?,?)",
                        [(run,i,json.dumps(converted[i][1][0],ensure_ascii=False),
                          json.dumps(converted[i][1][1:],ensure_ascii=False,default=str))
                         for i in range(2)])
                latest=db.execute("SELECT * FROM source_runs WHERE id=?",(run,)).fetchone()
                return 201,{"ok":True,"reused":False,"selected":self._public(latest)},None
        except Exception as exc:
            LOGGER.warning("Read-only Imperium extraction failed: %s",type(exc).__name__)
            return 503,{"ok":False,"code":"imperium_source_error",
                        "error":"Não foi possível obter os dados diretamente do Imperium. "
                        "Nenhum relatório incompleto foi salvo."},None
        finally:
            self.busy.release()
