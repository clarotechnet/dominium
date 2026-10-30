"""Persisted daily equipment-analysis workbook, independent of the Atlas QUERY.

A source-specific DataSnap 'Equipamentos Utilizados' period extract is NOT exposed by
the current serial/OS clients. This catalog accepts a verified reference workbook
and never substitutes the Atlas QUERY or movement history for that daily source.
Operations share records by city, reference date and source version.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import io
import json
import re
import sqlite3
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

ROOT=Path(r"C:\DominiumRuntime\StockAnalysisData\equipment_daily")
CITIES={"natal","fortaleza","mossoro","recife"}
TABS=("Atlas","Chips Atlas","IMPERIUM","CHIP IMPERIUM","Assinantes","Nomes.")
CITY_RE=re.compile(r"(natal|fortaleza|mossoro|recife)\Z")
ID_RE=re.compile(r"[a-f0-9]{32}\Z")
DATE_RE=re.compile(r"\d{4}-\d{2}-\d{2}\Z")
NS="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOCREL="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL="{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_UPLOAD=3_500_000
MAX_UNPACKED=35_000_000
MAX_ROWS_PER_TAB=60_000
MAX_COLS=60

def _date(value):
    if not isinstance(value,str) or not DATE_RE.fullmatch(value):
        raise ValueError("Data de referencia invalida")
    result=date.fromisoformat(value)
    if result>datetime.now(timezone(timedelta(hours=-3))).date():
        raise ValueError("Data futura nao permitida")
    return result

def previous_day():
    return (datetime.now(timezone(timedelta(hours=-3))).date()-timedelta(days=1)).isoformat()

def parse_route(method,target):
    if method not in {"GET","POST"} or len(target)>180 or "%" in target or "#" in target or "//" in target:
        return None
    u=urlsplit(target)
    if u.scheme or u.netloc or u.fragment:return None
    if method=="POST" and u.path=="/api/stock/analyses/daily/import" and not u.query:
        return ("import",None)
    if method!="GET":return None
    if u.path=="/api/stock/analyses/daily":
        try:q=parse_qs(u.query,strict_parsing=True)
        except ValueError:return None
        if set(q) not in ({"city"},{"city","date"},{"city","start","end"}) or any(len(v)!=1 for v in q.values()):
            return None
        city=q["city"][0]
        if city not in CITIES and city!="all":return None
        if "date" in q:
            try:_date(q["date"][0])
            except ValueError:return None
        start,end=q.get("start",[None])[0],q.get("end",[None])[0]
        if (start or end):
            try:
                if _date(start)>_date(end):return None
            except ValueError:return None
        return ("daily",(city,q.get("date",[None])[0],start,end))
    if u.query:return None
    m=re.fullmatch(r"/api/stock/analyses/daily/([a-f0-9]{32})/sheets/([0-5])",u.path)
    if m:return ("sheet",(m.group(1),int(m.group(2))))
    m=re.fullmatch(r"/api/stock/analyses/daily/([a-f0-9]{32})/export",u.path)
    if m:return ("export",m.group(1))
    return None

def _excel_cell(text,header):
    if header.strip().upper() in ("DATA","DATE"):
        try:
            n=float(text)
            if 1<n<90000:
                return (datetime(1899,12,30)+timedelta(days=n)).strftime("%d/%m/%Y %H:%M")
        except (TypeError,ValueError,OverflowError):
            pass
    return str(text or "")[:500]

def _xlsx_rows(raw:bytes):
    if not 100<len(raw)<=MAX_UPLOAD or raw[:4]!=b"PK\x03\x04":
        raise ValueError("Arquivo XLSX invalido ou acima do limite")
    result={}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist()
            if sum(i.file_size for i in infos)>MAX_UNPACKED or len(infos)>200:
                raise ValueError("Conteudo XLSX excede o limite seguro")
            if any(i.filename.startswith("/") or ".." in Path(i.filename).parts for i in infos):
                raise ValueError("Caminho XLSX inseguro")
            workbook=ET.fromstring(z.read("xl/workbook.xml"))
            relations=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            paths={}
            for rel in relations:
                if not rel.tag.startswith(PACKAGE_REL):continue
                target=rel.get("Target","")
                if target.startswith("/xl/worksheets/"):path=target.lstrip("/")
                elif target.startswith("worksheets/"):path="xl/"+target
                else:continue
                if path.startswith("xl/worksheets/") and ".." not in path:paths[rel.get("Id")]=path
            strings=[]
            if "xl/sharedStrings.xml" in z.namelist():
                shared=ET.fromstring(z.read("xl/sharedStrings.xml"))
                strings=["".join(t.text or "" for t in si.iter(NS+"t")) for si in shared.findall(NS+"si")]
            sheets=workbook.find(NS+"sheets")
            if sheets is None:raise ValueError("Pasta de trabalho sem abas")
            available={s.get("name"):paths.get(s.get(DOCREL+"id")) for s in sheets}
            if set(TABS)-set(available):raise ValueError("As seis abas do modelo nao foram encontradas")
            for name in TABS:
                filename=available[name]
                if not filename or filename not in z.namelist():raise ValueError("Aba ausente no XLSX")
                root=ET.fromstring(z.read(filename))
                entries=[]
                for row in root.iter(NS+"row"):
                    if len(entries)>MAX_ROWS_PER_TAB:raise ValueError("Numero de registros acima do limite")
                    values={}
                    for cell in row.findall(NS+"c"):
                        address=cell.get("r","")
                        letters=re.match(r"[A-Z]+",address)
                        if not letters:continue
                        index=0
                        for char in letters.group():index=index*26+ord(char)-64
                        index-=1
                        if index>=MAX_COLS:continue
                        if cell.get("t")=="inlineStr":
                            raw_value="".join(t.text or "" for t in cell.iter(NS+"t"))
                        else:
                            node=cell.find(NS+"v")
                            raw_value=node.text if node is not None and node.text is not None else ""
                            if cell.get("t")=="s":
                                try:raw_value=strings[int(raw_value)]
                                except (ValueError,IndexError):raw_value=""
                        values[index]=raw_value
                    if values:
                        width=max(values)+1
                        entries.append([str(values.get(i,""))[:500] for i in range(width)])
                if not entries:raise ValueError("Aba sem cabecalho: "+name)
                headers=entries[0]
                limit=max(len(headers),max(map(len,entries)))
                # Preserve the header names shown by the user's final workbook.
                normalized=[]
                for i,row in enumerate(entries):
                    row=row+[""]*(limit-len(row))
                    normalized.append(row if i==0 else [_excel_cell(v,headers[j] if j<len(headers) else "") for j,v in enumerate(row)])
                result[name]=normalized
    except (zipfile.BadZipFile,KeyError,ET.ParseError) as exc:
        raise ValueError("Estrutura do XLSX invalida") from exc
    return result

class DailyEquipmentCatalog:
    def __init__(self,root=ROOT):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/"daily.sqlite3"
        with closing(sqlite3.connect(self.db,timeout=15)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS daily_runs(
              id TEXT PRIMARY KEY,city TEXT NOT NULL,reference_date TEXT NOT NULL,
              origin TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,
              created_by TEXT NOT NULL,created_at TEXT NOT NULL,counts_json TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_daily_city_date ON daily_runs(city,reference_date,created_at DESC)")
            db.execute("""CREATE TABLE IF NOT EXISTS daily_sheets(
              run_id TEXT NOT NULL,sheet_index INTEGER NOT NULL,name TEXT NOT NULL,
              rows_json TEXT NOT NULL,PRIMARY KEY(run_id,sheet_index))""")
    def _public(self,row):
        return {"id":row["id"],"city":row["city"],"date":row["reference_date"],
                "origin":row["origin"],"filename":row["filename"],"created_at":row["created_at"],
                "counts":json.loads(row["counts_json"])}
    def handle(self,method,target,actor,body=None):
        route=parse_route(method,target)
        if not route:return 404,{"ok":False,"error":"Rota nao permitida"},None
        action,arg=route
        try:
            with closing(sqlite3.connect(self.db,timeout=15)) as db:
                db.row_factory=sqlite3.Row
                if action=="daily":
                    city,day,start,end=arg
                    where=[];params=[]
                    if city!="all":where.append("city=?");params.append(city)
                    if day:where.append("reference_date=?");params.append(day)
                    if start and end:where.append("reference_date BETWEEN ? AND ?");params.extend((start,end))
                    condition=" AND ".join(where) if where else "1=1"
                    history=db.execute("SELECT * FROM daily_runs WHERE "+condition+
                        " ORDER BY reference_date DESC,created_at DESC LIMIT 120",params).fetchall()
                    chosen=history[0] if history else None
                    latest=db.execute("SELECT * FROM daily_runs WHERE "+
                        ("city=?" if city!="all" else "1=1")+
                        " ORDER BY reference_date DESC,created_at DESC LIMIT 1",
                        (city,) if city!="all" else ()).fetchone()
                    return 200,{"ok":True,"selected":self._public(chosen) if chosen else None,
                                "latest":self._public(latest) if latest else None,
                                "history":[self._public(r) for r in history]},None
                if action=="sheet":
                    run_id,index=arg
                    run=db.execute("SELECT id FROM daily_runs WHERE id=?",(run_id,)).fetchone()
                    if not run:return 404,{"ok":False,"error":"Registro nao encontrado"},None
                    row=db.execute("SELECT name,rows_json FROM daily_sheets WHERE run_id=? AND sheet_index=?",(run_id,index)).fetchone()
                    if not row:return 404,{"ok":False,"error":"Aba nao encontrada"},None
                    records=json.loads(row["rows_json"])
                    return 200,{"ok":True,"name":row["name"],"header":records[0],
                                "rows":records[1:201],"total":len(records)-1,
                                "preview_limited":len(records)>201},None
                if action=="export":
                    row=db.execute("SELECT id FROM daily_runs WHERE id=?",(arg,)).fetchone()
                    if not row:return 404,{"ok":False,"error":"Registro nao encontrado"},None
                    path=self.root/(arg+".xlsx")
                    if not path.exists():return 503,{"ok":False,"error":"Arquivo indisponivel"},None
                    raw=path.read_bytes()
                    return 200,raw,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if action=="import":
                    if not isinstance(body,dict) or set(body)!={"city","date","filename","content_base64"}:
                        return 400,{"ok":False,"error":"Arquivo e periodo obrigatorios"},None
                    city=body["city"];day=body["date"]
                    if city not in CITIES:return 400,{"ok":False,"error":"Praca invalida"},None
                    try:_date(day)
                    except ValueError as ex:return 400,{"ok":False,"error":str(ex)},None
                    filename=str(body["filename"])[:120]
                    if not filename.lower().endswith(".xlsx"):
                        return 400,{"ok":False,"error":"Envie um XLSX"},None
                    if not isinstance(body["content_base64"],str):
                        return 400,{"ok":False,"error":"Conteudo do arquivo invalido"},None
                    if len(body["content_base64"])>MAX_UPLOAD*4//3+20:
                        return 413,{"ok":False,"error":"Arquivo acima do limite"},None
                    try:raw=base64.b64decode(body["content_base64"],validate=True)
                    except (binascii.Error,ValueError):return 400,{"ok":False,"error":"Base64 invalido"},None
                    sheets=_xlsx_rows(raw)
                    digest=hashlib.sha256(raw).hexdigest()
                    exists=db.execute("SELECT * FROM daily_runs WHERE city=? AND reference_date=? AND sha256=? ORDER BY created_at DESC LIMIT 1",(city,day,digest)).fetchone()
                    if exists:return 200,{"ok":True,"reused":True,"selected":self._public(exists)},None
                    id=uuid.uuid4().hex
                    counts={key:max(0,len(records)-1) for key,records in sheets.items()}
                    entry=(id,city,day,"excel_final_importado",filename,digest,actor,
                           datetime.now(timezone.utc).isoformat(timespec="seconds"),json.dumps(counts))
                    filename_on_disk=self.root/(id+".xlsx")
                    filename_on_disk.write_bytes(raw)
                    with db:
                        db.execute("INSERT INTO daily_runs VALUES(?,?,?,?,?,?,?,?,?)",entry)
                        db.executemany("INSERT INTO daily_sheets VALUES(?,?,?,?)",
                            [(id,i,name,json.dumps(sheets[name],ensure_ascii=False)) for i,name in enumerate(TABS)])
                    row=db.execute("SELECT * FROM daily_runs WHERE id=?",(id,)).fetchone()
                    return 201,{"ok":True,"reused":False,"selected":self._public(row)},None
        except (OSError,sqlite3.Error,ValueError) as error:
            return 503,{"ok":False,"error":"Arquivo diario indisponivel ou invalido: "+str(error)[:120]},None
        return 404,{"ok":False,"error":"Rota nao permitida"},None
