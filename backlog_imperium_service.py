"""Read-only annual Imperium history loader for the DOMINIUM backlog panel.

DO NOT invoke the operational write/close DataSnap methods here.
The source query is per day; every completed OS requires a detail read for close code.
Persist day and checkpoint in one SQLite transaction to support safe resumptions.
"""
from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import io
import itertools
import unicodedata
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from contextlib import contextmanager

from backlog_imperium_year import PROFILES, plan_days, year_window, valid_close_code, normalize_city

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;
CREATE TABLE IF NOT EXISTS history (
 profile TEXT NOT NULL, id_os INTEGER NOT NULL, activity_date TEXT NOT NULL,
 os_number TEXT NOT NULL, contract TEXT NOT NULL, service TEXT NOT NULL,
 code TEXT, verification TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DESCONHECIDO', captured_at TEXT NOT NULL,
 PRIMARY KEY(profile,id_os,activity_date)
);
CREATE INDEX IF NOT EXISTS idx_history_contract ON history(contract,activity_date DESC);
CREATE INDEX IF NOT EXISTS idx_history_code ON history(profile,code,activity_date DESC);
CREATE TABLE IF NOT EXISTS checkpoint (
 profile TEXT PRIMARY KEY, date TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_runs (
 id TEXT PRIMARY KEY, mode TEXT NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL, total_tasks INTEGER NOT NULL,
 done_tasks INTEGER NOT NULL DEFAULT 0, imported INTEGER NOT NULL DEFAULT 0,
 unconfirmed INTEGER NOT NULL DEFAULT 0, error TEXT
);
CREATE TABLE IF NOT EXISTS route_rows (
 route_hash TEXT NOT NULL, row_num INTEGER NOT NULL,
 contract TEXT NOT NULL, city TEXT NOT NULL, technician TEXT,
 bairro TEXT, window TEXT, os_number TEXT, route_code TEXT,
 PRIMARY KEY(route_hash,row_num)
);
CREATE INDEX IF NOT EXISTS idx_route_contract ON route_rows(contract);
CREATE TABLE IF NOT EXISTS route_batches (
 route_hash TEXT PRIMARY KEY, filename TEXT NOT NULL, rows_count INTEGER NOT NULL,
 imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sent_routes (
 profile TEXT NOT NULL, contract TEXT NOT NULL,
 sent_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(profile,contract)
);
"""

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

class BacklogHistoryService:
    def __init__(self, db_path: str | Path, profiles: dict, *, clock=None, sleep=None, operation_gate=None):
        self.db_path = Path(db_path)
        self.profiles = profiles
        self.clock = clock or dt.date.today
        self.sleep = sleep or time.sleep
        self._mutex = threading.RLock()
        self.operation_gate = operation_gate
        self._stop = threading.Event()
        self._runner = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            columns={r[1] for r in conn.execute("PRAGMA table_info(history)")}
            if "status" not in columns:
                conn.execute("ALTER TABLE history ADD COLUMN status TEXT NOT NULL DEFAULT 'DESCONHECIDO'")
            conn.execute("UPDATE sync_runs SET status='interrupted', finished_at=?, error=? WHERE status='running'",
                         (utcnow(),"Processo reiniciado; cursor preservado"))
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def snapshot(self):
        with self._connect() as conn:
            checkpoints = {r["profile"]:r["date"] for r in conn.execute("SELECT profile,date FROM checkpoint")}
            run = conn.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            counts = conn.execute("SELECT verification,count(*) as n FROM history GROUP BY verification").fetchall()
            routes = conn.execute("SELECT coalesce(sum(rows_count),0) FROM route_batches").fetchone()[0]
            return {
                "ok":True,"window_start":year_window(self.clock()).start.isoformat(),
                "window_end":year_window(self.clock()).end.isoformat(),
                "checkpoints":checkpoints,"running":bool(self._runner and self._runner.is_alive()),
                "run":dict(run) if run else None,
                "history":{r["verification"]:r["n"] for r in counts},
                "route_rows":routes
            }

    def start(self, *, mode="batch", days_per_profile=1, only_profile=None, probe_date=None):
        if mode not in ("batch","probe"): raise ValueError("Modo invalido")
        if only_profile and only_profile not in PROFILES: raise ValueError("Perfil invalido")
        if not isinstance(days_per_profile,int) or not 1 <= days_per_profile <= 7:
            raise ValueError("O limite por lote e de 1 a 7 dias por perfil")
        with self._mutex:
            if self._runner and self._runner.is_alive():
                raise RuntimeError("Ja existe uma sincronizacao em andamento")
            self._stop.clear()
            if mode == "probe":
                day = dt.date.fromisoformat(probe_date) if probe_date else self.clock()-dt.timedelta(days=1)
                if day < year_window(self.clock()).start or day >= self.clock():
                    raise ValueError("Data de teste fora do periodo permitido")
                if not only_profile: raise ValueError("Teste exige um perfil")
                tasks = [(only_profile,day)]
            else:
                with self._connect() as conn:
                    checkpoints = {r["profile"]:dt.date.fromisoformat(r["date"]) for r in conn.execute("SELECT profile,date FROM checkpoint")}
                days = plan_days(today=self.clock(),checkpoints=checkpoints,max_days_per_profile=days_per_profile)
                tasks = [(t.profile,t.date) for t in days if not only_profile or t.profile == only_profile]
            run_id = uuid.uuid4().hex
            with self._connect() as conn:
                conn.execute("""INSERT INTO sync_runs(id,mode,started_at,status,total_tasks) VALUES(?,?,?,'running',?)""",
                             (run_id,mode,utcnow(),len(tasks)))
                conn.commit()
            runner = threading.Thread(target=self._work,args=(run_id,mode,tasks),daemon=True,name="dominium-backlog-reader")
            self._runner=runner
            runner.start()
            return {"ok":True,"run_id":run_id,"tasks":len(tasks),"mode":mode}

    def cancel(self):
        self._stop.set()
        return {"ok":True,"message":"Parada solicitada; dia em andamento sera finalizado antes de parar"}

    def _datasnap_read(self, method, *args, **kwargs):
        # Shared with operational close gates. Never compete with OS writes.
        if self.operation_gate is None:
            return method(*args, **kwargs)
        for _ in range(30):
            if self._stop.is_set():
                raise RuntimeError("Consulta interrompida pelo operador")
            if self.operation_gate.acquire(blocking=False):
                try:
                    return method(*args, **kwargs)
                finally:
                    self.operation_gate.release()
            self.sleep(2.0)
        raise RuntimeError("DataSnap ocupado; lote nao iniciado para evitar conflito")

    def _work(self,run_id,mode,tasks):
        status="completed"
        error=None
        try:
            for profile_key,day in tasks:
                if self._stop.is_set():
                    status="paused";break
                api=self.profiles[profile_key].api
                # Read-only status: no close, no stock changes and no TOA bridge.
                # O conjunto TODOS/TODOS e a fonte oficial.
                # As quatro consultas por status sao somente anotacoes:
                # o DataSnap pode retornar OS adicionais que nao pertencem
                # a nenhum dos quatro status conhecidos.
                all_payload=self._datasnap_read(
                    api._fetch_main_payload,day,status="all",service_type="all")
                all_orders=api._parse_orders(all_payload)
                if len(all_orders)>3000:
                    raise RuntimeError("Mais de 3000 OS num dia: revisar antes de processar")
                all_by_id={order.id_os:order for order in all_orders}
                if len(all_by_id)!=len(all_orders):
                    raise RuntimeError("IDs duplicados na consulta TODOS/TODOS")
                status_labels={
                    "field":"EM CAMPO","completed":"CONCLUIDA",
                    "canceled":"CANCELADA","rescheduled":"REAGENDADA"
                }
                known={}
                for status_name,status_label in status_labels.items():
                    batch=self._datasnap_read(
                        api.list_orders,day,status=status_name,service_type="all")
                    for order in batch:
                        if order.id_os not in all_by_id:
                            raise RuntimeError("OS no filtro de status ausente em TODOS/TODOS")
                        if order.id_os in known and known[order.id_os]!=status_label:
                            raise RuntimeError("DataSnap retornou OS em status conflitantes")
                        known[order.id_os]=status_label
                orders=[
                    (order,known.get(order.id_os,"DESCONHECIDO"))
                    for order in all_orders
                ]
                if len(orders)>3000:
                    raise RuntimeError("Mais de 3000 OS num dia: revisar antes de processar")
                records=[]
                for order,status_label in orders[:3] if mode == "probe" else orders:
                    if self._stop.is_set():
                        status="paused";break
                    # Existing code validates the actual IdCodigoBaixa field.
                    detail=self._datasnap_read(api._fetch_detail,order.id_os,timeout=15)
                    code=valid_close_code(api._detail_close_code(detail))
                    records.append((profile_key,order.id_os,day.isoformat(),order.num_os,order.contract,
                         order.service,code,"confirmed" if code else "missing_code",
                         status_label,utcnow()))
                    if mode != "probe":
                        self.sleep(0.10)
                if status=="paused":break
                # Pilot does not persist records or advance checkpoint.
                if mode=="probe":
                    with self._connect() as conn:
                        conn.execute("UPDATE sync_runs SET done_tasks=1, imported=?,unconfirmed=? WHERE id=?",
                         (sum(1 for r in records if r[6]),sum(1 for r in records if not r[6]),run_id))
                        conn.commit()
                    break
                # One atomic transaction: rows and checkpoint cannot diverge.
                with self._connect() as conn:
                    conn.executemany("""INSERT INTO history(
                        profile,id_os,activity_date,os_number,contract,service,code,verification,status,captured_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(profile,id_os,activity_date) DO UPDATE SET
                        os_number=excluded.os_number,contract=excluded.contract,service=excluded.service,
                        code=excluded.code,verification=excluded.verification,status=excluded.status,
                        captured_at=excluded.captured_at""",records)
                    conn.execute("""INSERT INTO checkpoint(profile,date,updated_at) VALUES(?,?,?)
                        ON CONFLICT(profile) DO UPDATE SET date=excluded.date,updated_at=excluded.updated_at""",
                        (profile_key,day.isoformat(),utcnow()))
                    conn.execute("""UPDATE sync_runs SET done_tasks=done_tasks+1,imported=imported+?,
                      unconfirmed=unconfirmed+? WHERE id=?""",
                      (sum(1 for r in records if r[6]),sum(1 for r in records if not r[6]),run_id))
                    conn.commit()
                self.sleep(0.75)
        except Exception as exc:
            status="failed"
            error=f"{type(exc).__name__}: {str(exc)[:250]}"
        finally:
            with self._connect() as conn:
                conn.execute("UPDATE sync_runs SET status=?,finished_at=?,error=? WHERE id=?",
                             (status,utcnow(),error,run_id))
                conn.commit()

    def import_route_files(self,files):
        """Manual Claro xlsx or csv upload, up to 5 files, 3 MiB each."""
        if not isinstance(files,list) or not 1 <= len(files) <= 5:
            raise ValueError("Envie de 1 a 5 arquivos")
        parsed=[]
        for item in files:
            name=str(item.get("name") or "")
            if not re.fullmatch(r"[^/\\:<>|?*\r\n]{1,120}\.(?:xlsx|csv)",name,re.I):
                raise ValueError("Nome ou formato de planilha invalido")
            raw=base64.b64decode(item.get("base64",""),validate=True)
            if not raw or len(raw)>3*1024*1024: raise ValueError("Planilha vazia ou maior que 3 MiB")
            digest=hashlib.sha256(raw).hexdigest()
            if name.lower().endswith(".xlsx"):
                from openpyxl import load_workbook
                book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
                rows=itertools.chain.from_iterable(
                    sheet.iter_rows(values_only=True) for sheet in book.worksheets)
            else:
                content=raw.decode("utf-8-sig")
                try:
                    dialect=csv.Sniffer().sniff(content[:8000],delimiters=";,\t")
                    rows=csv.reader(io.StringIO(content),dialect)
                except csv.Error:
                    separator=";" if content.partition("\n")[0].count(";") > content.partition("\n")[0].count(",") else ","
                    rows=csv.reader(io.StringIO(content),delimiter=separator)
            # Recurso/Contrato sao campos obrigatorios. Cidade pode vir do nome
            # do arquivo; planilhas multiaba usam o cabecalho de cada secao.
            aliases={
                "Contrato":("CONTRATO","NUMERO DO CONTRATO","NUMERO CONTRATO","N CONTRATO"),
                "Recurso":("RECURSO","TECNICO","NOME DO TECNICO","NOME TECNICO","NOME TOA"),
                "Cidade":("CIDADE","MUNICIPIO","LOCALIDADE"),
                "Bairro":("BAIRRO","BAIRRO CLIENTE"),
                "Janela de Serviço":("JANELA DE SERVICO","JANELA","HORARIO","HORARIO PREVISTO"),
                "Número da WO":("NUMERO DA WO","NUMERO WO","WO","NUMERO DA OS","OS"),
                "Cód de Baixa 1":("COD DE BAIXA 1","CODIGO DE BAIXA 1","COD BAIXA 1","CODIGO BAIXA"),
            }
            def normalized(raw_label):
                text=unicodedata.normalize("NFKD",str(raw_label or ""))
                text="".join(ch for ch in text if not unicodedata.combining(ch))
                return re.sub(r"[^A-Z0-9]+"," ",text.upper()).strip()
            def identify(values):
                labels=[normalized(v) for v in values]
                result={}
                for field,options in aliases.items():
                    for alias in options:
                        if alias in labels:
                            result[field]=labels.index(alias)
                            break
                return result
            city_from_filename=""
            upper=name.upper()
            for tag,city in (("NTL","NATAL"),("PWM","PARNAMIRIM"),("FTZ","FORTALEZA"),
                             ("JCR","RECIFE"),("MRO","MOSSORO"),("MOSSORO","MOSSORO")):
                if re.search(r"(?:^|[^A-Z])"+tag+r"(?:[^A-Z]|$)",upper):
                    city_from_filename=normalize_city(city)
                    break
            column={}
            valid_headers=0
            entries=[]
            for line_num,row in enumerate(rows,1):
                if line_num>25000: raise ValueError("Limite de 25000 linhas por planilha")
                values=[str(v).strip() if v is not None else "" for v in row]
                detected=identify(values)
                if "Contrato" in detected and "Recurso" in detected:
                    column=detected
                    valid_headers+=1
                    continue
                if not column:
                    continue
                def col(k):
                    ix=column.get(k,-1)
                    return values[ix] if ix>=0 and ix<len(values) else ""
                original=col("Contrato")
                if re.fullmatch(r"[0-9]+\.0+",original):
                    original=original.split(".")[0]
                contract=re.sub(r"\D","",original)
                if len(contract)<4 or len(contract)>20:
                    continue
                city=normalize_city(col("Cidade")) or city_from_filename
                if not city:
                    raise ValueError("Cidade nao identificada; informe na planilha ou no nome")
                entries.append((digest,line_num,contract,city,
                    col("Recurso")[:140],col("Bairro")[:120],col("Janela de Serviço")[:70],
                    col("Número da WO")[:70],col("Cód de Baixa 1")[:100]))
            if valid_headers==0:
                raise ValueError("Cabecalho TOA nao encontrado (Contrato e Recurso): "+name)
            if not entries:
                raise ValueError("Nenhum contrato valido na planilha: "+name)
            parsed.append((digest,name,entries))
        with self._mutex,self._connect() as conn:
            # A carga manual representa apenas as rotas atuais, nao o historico.
            conn.execute("DELETE FROM route_rows")
            conn.execute("DELETE FROM route_batches")
            for digest,name,entries in parsed:
                conn.execute("DELETE FROM route_rows WHERE route_hash=?",(digest,))
                conn.executemany("""INSERT INTO route_rows(route_hash,row_num,contract,city,technician,bairro,window,os_number,route_code)
                  VALUES(?,?,?,?,?,?,?,?,?)""",entries)
                conn.execute("""INSERT INTO route_batches(route_hash,filename,rows_count,imported_at) VALUES(?,?,?,?)
                  ON CONFLICT(route_hash) DO UPDATE SET filename=excluded.filename,rows_count=excluded.rows_count,
                  imported_at=excluded.imported_at""",(digest,name,len(entries),utcnow()))
            conn.commit()
        return {"ok":True,"files":[{"filename":n,"rows":len(x),"sha256":d} for d,n,x in parsed]}

    def compare(self,limit=300,selected_codes=None):
        limit=max(1,min(int(limit),1000))
        selected_codes=selected_codes if selected_codes is not None else ("101","306","404","430")
        selected_codes={valid_close_code(x) for x in selected_codes}
        selected_codes.discard(None)
        with self._connect() as conn:
            rows=conn.execute("""SELECT r.contract,r.city,r.technician,r.bairro,r.window,r.os_number,r.route_code
              FROM route_rows r ORDER BY r.city,r.technician,r.row_num LIMIT ?""",(limit,)).fetchall()
            output=[]
            for row in rows:
                item=dict(row)
                history=conn.execute("""SELECT code,status,activity_date,verification
                    FROM history WHERE contract=? ORDER BY activity_date DESC,id_os DESC""",
                    (item["contract"],)).fetchall()
                match=next((h for h in history if h["code"] in selected_codes),None)
                latest=history[0] if history else None
                reference=match or latest
                item.update({
                    "classification":"SEGURAR" if match else ("OUTRO HISTÓRICO" if history else "NÃO CONFIRMADO"),
                    "historical_code":reference["code"] if reference else None,
                    "historical_status":reference["status"] if reference else None,
                    "historical_date":reference["activity_date"] if reference else None,
                    "verification":reference["verification"] if reference else None,
                    "history_count":len(history),
                })
                output.append(item)
            return {"ok":True,"rows":output,
                    "snapshot":self.snapshot(),
                    "note":"Classificacao por qualquer codigo selecionado no historico. Sem registro pode significar carga parcial."}

    def fora_rota(self,profile="natal",limit=150):
        if profile not in PROFILES: raise ValueError("Perfil invalido")
        with self._connect() as conn:
            rows=conn.execute("""SELECT h.contract,h.activity_date,h.code,h.os_number,h.service
                FROM history h
                WHERE h.profile=? AND h.code='106'
                AND h.rowid=(SELECT h2.rowid FROM history h2 WHERE h2.profile=h.profile
                 AND h2.contract=h.contract ORDER BY h2.activity_date DESC,h2.id_os DESC LIMIT 1)
                AND NOT EXISTS (SELECT 1 FROM route_rows r WHERE r.contract=h.contract)
                ORDER BY h.activity_date DESC LIMIT ?""",(profile,max(1,min(int(limit),300)))).fetchall()
            return {"ok":True,"candidates":[dict(r) for r in rows],
                    "note":"Sugestoes de historico 106, nao enviadas. Verifique situacao atual no TOA/Imperium antes de encaminhar."}

    def mark_sent(self,body):
        profile=str(body.get("profile") or "").strip()
        contract=re.sub(r"\D","",str(body.get("contract") or ""))
        note=str(body.get("note") or "").strip()[:350]
        if profile not in PROFILES or not (4 <= len(contract) <= 20):
            raise ValueError("Perfil/contrato invalido")
        # Registrar envio nao executa nenhuma acao no Imperium.
        with self._connect() as conn:
            conn.execute("INSERT INTO sent_routes(profile,contract,sent_at,note) VALUES(?,?,?,?) "
              "ON CONFLICT(profile,contract) DO UPDATE SET sent_at=excluded.sent_at,note=excluded.note",
              (profile,contract,utcnow(),note))
            conn.commit()
        return {"ok":True,"message":"Envio registrado; baixa nao confirmada"}

    def list_sent(self,limit=300):
        with self._connect() as conn:
            rows=conn.execute("SELECT profile,contract,sent_at,note FROM sent_routes "
                "ORDER BY sent_at DESC LIMIT ?",(max(1,min(int(limit),500)),)).fetchall()
            return {"ok":True,"rows":[dict(x) for x in rows]}
