"""Audited, read-only stock reports from a previously validated Atlas QUERY.

Never submits an Atlas queue, changes an Imperium record, or claims physical custody.
The Imperium stock/used-equipment extract is NOT available here; historical records
are explicitly identified as history, not confirmed used equipment.
"""
from __future__ import annotations

import io
import json
import logging
import re
import sqlite3
import threading
import time
import uuid
import unicodedata
import zipfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from atlas_query_report import DB as ATLAS_DB
from atlas_query_data import COLUMNS, material_no_zero

ROOT = Path(r"C:\DominiumRuntime\StockAnalysisData")
SOURCE_DB = Path(r"C:\DominiumMain\data\dominium_operacional.sqlite3")
CITY = frozenset(("natal", "fortaleza", "mossoro", "recife"))
TYPES = frozenset(("query", "equipamentos", "suspeitos"))
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
ACTOR = re.compile(r"user-[1-9][0-9]{0,18}\Z")
STATES = frozenset(("SUSPEITO", "ANALISE DE INVENTARIO", "ANÁLISE DE INVENTÁRIO"))
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def route_for(method: str, target: str):
    if method not in ("GET", "POST") or len(target) > 180 or "%" in target or "//" in target:
        return None
    uri = urlsplit(target)
    if uri.fragment or uri.scheme or uri.netloc:
        return None
    if uri.path == "/api/stock/analyses/available" and method == "GET":
        if not re.fullmatch(r"city=(natal|fortaleza|mossoro|recife)", uri.query):
            return None
        return ("available", uri.query[5:])
    if uri.query:
        return None
    if uri.path == "/api/stock/analyses/jobs":
        return ("create" if method == "POST" else "list", None)
    m = re.fullmatch(r"/api/stock/analyses/jobs/([a-f0-9]{32})(/export)?", uri.path)
    if m and method == "GET":
        return ("export" if m.group(2) else "detail", m.group(1))
    return None


def _text(value):
    s = str(value if value is not None else "")
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        s = "'" + s
    return "".join(c for c in s[:32767] if ord(c) >= 32 or c in "\t\n\r")


def _col(n):
    result = ""
    while n:
        n, rem = divmod(n-1, 26)
        result = chr(65+rem) + result
    return result


def xlsx(sheets: list[tuple[str, list[list]]]) -> bytes:
    """Small dependency-free, safe OpenXML workbook with multiple named worksheets."""
    if not sheets or len(sheets) > 12:
        raise ValueError("Estrutura XLSX invalida")
    names = [name for name, _ in sheets]
    if len(set(names)) != len(names) or any(not 1 <= len(n) <= 31 for n in names):
        raise ValueError("Nomes das abas invalidos")
    files = io.BytesIO()
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(files, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as z:
        ct = ['<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
              '<Default Extension="xml" ContentType="application/xml"/>',
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
        for i in range(len(sheets)):
            ct.append(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        ct.append("</Types>")
        z.writestr("[Content_Types].xml","".join(ct))
        z.writestr("_rels/.rels",f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'+
            "".join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,name in enumerate(names,1))+
            "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",f'<Relationships xmlns="{rel}">'+
            "".join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+
            "</Relationships>")
        for index,(_,records) in enumerate(sheets,1):
            parts=[f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>']
            for r,row in enumerate(records,1):
                parts.append(f'<row r="{r}">')
                for c,val in enumerate(row,1):
                    safe = escape(_text(val))
                    parts.append(f'<c r="{_col(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{safe}</t></is></c>')
                parts.append("</row>")
            parts.append("</sheetData>")
            if records and records[0]:
                parts.append(f'<autoFilter ref="A1:{_col(len(records[0]))}{max(1,len(records))}"/>')
            parts.append("</worksheet>")
            z.writestr(f"xl/worksheets/sheet{index}.xml","".join(parts))
    if files.tell() > 35_000_000:
        raise ValueError("Relatorio muito grande")
    return files.getvalue()


def _key(record):
    return (str(record.get("numero_serie") or "").strip().upper()
            or str(record.get("enderecavel_principal") or "").strip().upper())


def _is_chip(row):
    return any(marker in str(row.get("modelo") or "").upper()
               for marker in ("SIM CARD", "SMART CARD", "CHIP", "ICCID"))


def _normalized_state(row):
    s = str(row.get("estado") or "").strip().upper()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def build_sheets(kind: str, records: list[dict], city: str, query_id: str, source_time: float,
                 history_rows: list[dict] | None = None):
    if kind not in TYPES:
        raise ValueError("Tipo de analise invalido")
    evidence = {str(e.get("serial") or "").upper():e for e in (history_rows or [])
                if isinstance(e,dict)}
    def evidence_for(row):
        return evidence.get(_key(row), evidence.get(str(row.get("enderecavel_principal") or "").upper(),{}))
    meta = [
        ["Fonte", "Valor"],
        ["Operacao", city.upper()],
        ["QUERY Atlas confirmada", query_id],
        ["Gerada no servidor", datetime.now(timezone.utc).isoformat(timespec="seconds")],
        ["QUERY armazenada", datetime.fromtimestamp(source_time, timezone.utc).isoformat(timespec="seconds")],
        ["Registros da QUERY", len(records)],
        ["Regra", "Dados historicos nao comprovam posse atual nem estoque fisico"],
    ]
    if kind == "query":
        matrix = [[title for _,title in COLUMNS]]
        matrix.extend([[row.get(key, "") for key,_ in COLUMNS] for row in records])
        meta.append(["Qualidade", "Codigo SAP sem zeros somente quando numerico; prefixos sao mantidos"])
        return [("QUERY Tratada", matrix), ("Fontes e criterios", meta)], {"total":len(records),"parcial":False}

    if kind == "suspeitos":
        filtered = [row for row in records if _normalized_state(row) in
                    ("SUSPEITO", "ANALISE DE INVENTARIO")]
        header = ["Serial", "Enderecavel Principal", "Modelo", "Estado Atlas",
                  "Contrato Atlas historico", "Operacao", "Data da Alteracao",
                  "Responsavel Atlas", "Codigo SAP", "Situacao", "Fonte", "Observacoes",
                  "DataSnap historico confirmado", "Qtd movimentos Imperium",
                  "Ultima movimentacao", "Ultimo destino historico",
                  "Contrato historico Imperium", "Posse atual verificada",
                  "Tecnico atual confirmado", "Divergencia historica"]
        out=[header]
        today=datetime.now(timezone(timedelta(hours=-3))).date()
        for row in filtered:
            serial = _key(row)
            when = str(row.get("data_ultima_alteracao") or "")
            if when.startswith(today.isoformat()) or when.startswith(today.strftime("%d/%m/%Y")):  # Ignore movements from the report day.
                continue
            e=evidence_for(row)
            atlas_contract=str(row.get("numero_contrato") or "").strip()
            historical_contract=str(e.get("last_contract_historical") or "").strip()
            difference="REVISAR datas" if atlas_contract and historical_contract and atlas_contract!=historical_contract else ""
            out.append([row.get("numero_serie"), row.get("enderecavel_principal"),
                row.get("modelo"), row.get("estado"),
                row.get("numero_contrato"), row.get("operacao"), when,
                row.get("responsavel"),row.get("codigo_sap_normalizado"),
                "Pendente de conferencia",
                "QUERY Atlas + DataSnap historico",
                "Posse atual/aceite/OS historica exigem confirmacao",
                "SIM" if e.get("history_verified") else "NAO CONFIRMADO",
                e.get("movement_count"),e.get("last_movement"),
                e.get("last_destination_historical"),e.get("last_contract_historical"),
                "SIM" if e.get("current_owner_verified") else "NAO CONFIRMADO",
                e.get("current_owner"),difference])
        meta.extend([["Estado incluido","SUSPEITO; ANALISE DE INVENTARIO"],
                     ["Filtro temporal","Ocorrencias do dia excluidas quando data identificada"],
                     ["DataSnap","Movimentos confirmados diferem de posse atual confirmada"],
                     ["Aviso","Aceite e OS historica do Controlador nao foram comprovados automaticamente"]])
        return [("Suspeitos",out),("Fontes e criterios",meta)], {"total":len(out)-1,"parcial":True,
           "imperium_evidence_rows":sum(bool(evidence_for(r)) for r in filtered),
           "limitation":"Os historicos DataSnap foram consultados; aceite e OS do Controlador nao foram comprovados automaticamente"}

    # Report of equipment: retain reference tabs. Do NOT fabricate Used Equipment results.
    atlas = [["Serial","Codigo","Equipamento","Data","Num. OS","Contrato","Usuario"]]
    chip_atlas=[list(atlas[0])]
    ass = [["Serial","Codigo","Equipamento","Data","Contrato","Usuario","Estoque Fisico"]]
    names = [["SERIAL","NOME"]]
    for row in records:
        serial = _key(row)
        if not serial: continue
        item = [serial,row.get("codigo_sap_normalizado"),row.get("modelo"),
                row.get("data_ultima_alteracao"),"",row.get("numero_contrato"),row.get("responsavel")]
        (chip_atlas if _is_chip(row) else atlas).append(item)
        if str(row.get("numero_contrato") or "").strip():
            ass.append([serial,row.get("codigo_sap_normalizado"),row.get("modelo"),
                row.get("data_ultima_alteracao"),row.get("numero_contrato"),
                row.get("responsavel"),"Pendente de conferencia"])
        if row.get("responsavel"):names.append([serial,row.get("responsavel")])
    # Imperium's 'Equipamentos Utilizados' isn't the same as read-only DataSnap movement history.
    imph=[["Serie / Ender. Princ.","Modelo","DATA","Contrato NETSMS","Tipo Contrato UNO",
             "Historico DataSnap","Ultima movimentacao","Ultimo destino historico",
             "Posse atual verificada","Tecnico atual confirmado","Limitacao"]]
    imp=[list(imph[0])]
    chip_imp=[list(imph[0])]
    for row in records:
        e=evidence_for(row)
        if not e.get("history_verified"):continue
        item=[_key(row),row.get("modelo"),e.get("last_movement_date"),
             e.get("last_contract_historical"),"",
             "SIM",e.get("last_movement"),e.get("last_destination_historical"),
             "SIM" if e.get("current_owner_verified") else "NAO CONFIRMADO",
             e.get("current_owner"),"Historico/DataSnap, NAO relatorio de equipamentos utilizados"]
        (chip_imp if _is_chip(row) else imp).append(item)
    meta.extend([["IMPERIUM / CHIP IMPERIUM", "Dados de historico obtidos pelo DataSnap; nao substituir Equipamentos Utilizados"],
                 ["Estoque fisico", "Pendente de conferencia (nao inferir de historico)"],
                 ["Posse atual", "Confirmada somente quando consta no estoque atual consultado"]])
    return [("Atlas",atlas),("Chips Atlas",chip_atlas),("IMPERIUM",imp),
            ("CHIP IMPERIUM",chip_imp),("Assinantes",ass),("Nomes.",names),
            ("Fontes e criterios",meta)],{"total":len(records),"parcial":True,
              "imperium_evidence_rows":len(imp)+len(chip_imp)-2,
              "limitation":"Dados DataSnap historicos integrados; consulta especifica Equipamentos Utilizados ainda nao foi comprovada"}


class StockAnalysisService:
    def __init__(self, *, root=ROOT, atlas_db=ATLAS_DB, start_worker=True, clock=time.time):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/"jobs.sqlite3"
        self.atlas_db=Path(atlas_db)
        self.clock=clock
        self._stop=threading.Event()
        self._wake=threading.Event()
        self._lock=threading.Lock()
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, actor TEXT NOT NULL, city TEXT NOT NULL,
              kind TEXT NOT NULL, query_id TEXT NOT NULL, state TEXT NOT NULL,
              created_at REAL NOT NULL, updated_at REAL NOT NULL,
              error TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '{}')""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_report_actor ON jobs(actor, created_at DESC)")
            con.execute("UPDATE jobs SET state='queued' WHERE state='processing'")
        self.thread=None
        if start_worker:
            self.thread=threading.Thread(target=self._work,daemon=True,name="stock-reports")
            self.thread.start()

    @contextmanager
    def _connect(self):
        con=sqlite3.connect(self.db,timeout=20)
        con.row_factory=sqlite3.Row
        try:
            con.execute("PRAGMA busy_timeout=20000")
            with con:yield con
        finally:con.close()

    def close(self):
        self._stop.set();self._wake.set()
        if self.thread:self.thread.join(timeout=4)

    def latest(self,actor,city):
        con=sqlite3.connect(self.atlas_db,timeout=15)
        con.row_factory=sqlite3.Row
        try:
            rows=con.execute("""SELECT q.id,q.city,q.created_at,
                (SELECT count(*) FROM query_rows r WHERE r.job_id=q.id) AS total_rows
                FROM query_jobs q WHERE q.city=? AND q.created_by=? AND q.state='ready'
                ORDER BY q.created_at DESC LIMIT 12""",(city,actor)).fetchall()
            return next((dict(r) for r in rows if r["total_rows"]>0),None)
        finally:con.close()

    def info(self,row):
        return {"id":row["id"],"city":row["city"],"kind":row["kind"],
          "query_id":row["query_id"],"state":row["state"],"created_at":row["created_at"],
          "updated_at":row["updated_at"],"error":row["error"],
          "summary":json.loads(row["summary"])}

    def handle(self,method,target,actor,body=None):
        route=route_for(method,target)
        if route is None:return 404,{"ok":False,"error":"Rota nao permitida"},None
        if not ACTOR.fullmatch(actor or ""):return 403,{"ok":False,"error":"Operador invalido"},None
        action,argument=route
        try:
            if action=="available":
                return 200,{"ok":True,"latest":self.latest(actor,argument)},None
            if action=="list":
                with self._connect() as con:
                    jobs=con.execute("SELECT * FROM jobs WHERE actor=? ORDER BY created_at DESC LIMIT 20",(actor,)).fetchall()
                return 200,{"ok":True,"jobs":[self.info(j) for j in jobs]},None
            if action=="create":
                if not isinstance(body,dict) or set(body)!={"city","kind"} or body["city"] not in CITY or body["kind"] not in TYPES:
                    return 400,{"ok":False,"error":"Selecione uma praca e tipo valido"},None
                latest=self.latest(actor,body["city"])
                if not latest:
                    return 409,{"ok":False,"error":"Nenhuma QUERY concluida e validada para esta praca e operador. Gere/recupere no Atlas Query."},None
                with self._lock:
                    with self._connect() as con:
                        prior=con.execute("""SELECT * FROM jobs WHERE actor=? AND city=? AND kind=? AND query_id=?
                                AND state IN ('queued','processing','ready')
                                ORDER BY created_at DESC LIMIT 1""",
                            (actor,body["city"],body["kind"],latest["id"])).fetchone()
                        if prior:
                            return 200,{"ok":True,"reused":True,"job":self.info(prior)},None
                        id=uuid.uuid4().hex;now=self.clock()
                        con.execute("""INSERT INTO jobs(id,actor,city,kind,query_id,state,created_at,updated_at)
                                  VALUES(?,?,?,?,?,'queued',?,?)""",
                            (id,actor,body["city"],body["kind"],latest["id"],now,now))
                        job=con.execute("SELECT * FROM jobs WHERE id=?",(id,)).fetchone()
                    self._wake.set()
                    return 202,{"ok":True,"reused":False,"job":self.info(job)},None
            with self._connect() as con:
                job=con.execute("SELECT * FROM jobs WHERE id=? AND actor=?",(argument,actor)).fetchone()
            if not job:return 404,{"ok":False,"error":"Trabalho nao encontrado"},None
            if action=="detail":return 200,{"ok":True,"job":self.info(job)},None
            if action=="export":
                if job["state"]!="ready":return 409,{"ok":False,"error":"Relatorio ainda nao concluido"},None
                filename=self.root/(job["id"]+".xlsx")
                if not filename.is_file():return 503,{"ok":False,"error":"Arquivo nao encontrado"},None
                raw=filename.read_bytes()
                if len(raw)>35_000_000:return 413,{"ok":False,"error":"Arquivo muito grande"},None
                return 200,raw,MIME_XLSX
            return 404,{"ok":False,"error":"Rota nao permitida"},None
        except (sqlite3.Error,ValueError,OSError) as error:
            logging.warning("Stock report endpoint failure %s",type(error).__name__)
            return 503,{"ok":False,"error":"Servico de relatorios temporariamente indisponivel"},None

    def _run_one(self,job):
        con=sqlite3.connect(self.atlas_db,timeout=20)
        try:
            con.row_factory=sqlite3.Row
            rows=[json.loads(r[0]) for r in con.execute(
                "SELECT data FROM query_rows WHERE job_id=? ORDER BY position",(job["query_id"],))]
            if not rows:raise ValueError("QUERY sem registros validados")
            created=con.execute("SELECT created_at FROM query_jobs WHERE id=? AND state='ready'",
                                (job["query_id"],)).fetchone()
            if not created:raise ValueError("QUERY de origem nao esta mais concluida")
            source_time=float(created[0])
        finally:con.close()
        history=[]
        enrichment_summary={}
        if job["kind"] in ("equipamentos","suspeitos"):
            from stock_report_enrichment import collect
            def update_progress(stats):
                with self._connect() as db:
                    db.execute("UPDATE jobs SET summary=?,updated_at=? WHERE id=?",
                               (json.dumps(stats),self.clock(),job["id"]))
            history,enrichment_summary=collect(
                job["id"],job["city"],job["kind"],rows,db_path=self.db,
                progress=update_progress)
        sheets,summary=build_sheets(job["kind"],rows,job["city"],job["query_id"],
                                    source_time,history_rows=history)
        summary.update(enrichment_summary)
        output=xlsx(sheets)
        target=self.root/(job["id"]+".xlsx")
        temp=self.root/(job["id"]+".tmp")
        temp.write_bytes(output);temp.replace(target)
        return summary

    def _work(self):
        while not self._stop.is_set():
            try:
                with self._connect() as con:
                    job=con.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
                    if job:
                        con.execute("UPDATE jobs SET state='processing',updated_at=? WHERE id=?",
                                    (self.clock(),job["id"]))
                if job:
                    try:
                        summary=self._run_one(job)
                        with self._connect() as con:
                            con.execute("UPDATE jobs SET state='ready',summary=?,updated_at=? WHERE id=?",
                                        (json.dumps(summary,ensure_ascii=False),self.clock(),job["id"]))
                    except Exception as error:
                        logging.exception("Stock report generation failed kind=%s",job["kind"])
                        with self._connect() as con:
                            con.execute("UPDATE jobs SET state='failed',error=?,updated_at=? WHERE id=?",
                                        ((type(error).__name__ + ": verifique a disponibilidade da QUERY")[:180],
                                         self.clock(),job["id"]))
                    continue
                self._wake.wait(timeout=5);self._wake.clear()
            except Exception as error:
                logging.warning("Stock report worker %s",type(error).__name__)
                self._stop.wait(8)
