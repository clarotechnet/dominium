"""Authenticated DOMINIUM QUERY Atlas service, isolated by operator.

Server-side scheduled reads of existing NetTask queue, attachment retry and
read-only report rendering. Never reissues uncertain report submissions.
"""
from __future__ import annotations
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from atlas_query_report import CITY,LOCATION,ChromeAtlas,AtlasAuthRequired,claim_job,read_job,save_queue,connect_db,DB
from atlas_query_pipeline import poll_report,fetch_file,upgrade_db,update_job,public_status
from atlas_query_data import parse_report,store_records,page,export_csv,export_xlsx,COLUMNS

JOB_RE=re.compile(r"[0-9a-f]{32}\Z")
ACTOR_RE=re.compile(r"user-[1-9][0-9]{0,18}\Z")
ROUTE_RE=re.compile(r"/api/atlas-query/jobs/([0-9a-f]{32})(?:/(rows/(0|[1-9]\d{0,5})|export\.(csv|xlsx)))?\Z")


def parse_query_route(method,target):
    if method not in ("GET","POST") or not isinstance(target,str) or len(target)>200:
        return None
    try:uri=urlsplit(target)
    except ValueError:return None
    if uri.query or uri.fragment or uri.scheme or uri.netloc or "%" in uri.path or "//" in uri.path:return None
    if uri.path=="/api/atlas-query/jobs":
        return ("create" if method=="POST" else "list",None,None)
    if method=="POST":
        reconcile=re.fullmatch(r"/api/atlas-query/jobs/([0-9a-f]{32})/reconcile",uri.path)
        return ("reconcile",reconcile.group(1),None) if reconcile else None
    match=ROUTE_RE.fullmatch(uri.path)
    if not match:return None
    if match.group(3) is not None:return ("rows",match.group(1),int(match.group(3)))
    if match.group(4):return ("export",match.group(1),match.group(4))
    return ("detail",match.group(1),None)


class AtlasQueryService:
    def __init__(self,*,db_path=DB,browser_factory=ChromeAtlas,start_worker=True,
                 clock=time.time):
        self.db_path=Path(db_path)
        self.browser_factory=browser_factory
        self.clock=clock
        self._lock=threading.Lock()
        self._wake=threading.Event()
        self._stop=threading.Event()
        self._new_jobs=[]
        upgrade_db(self.db_path)
        # A previous process may have died after recording the request but
        # before confirming the Atlas queue ID. Never reissue that POST.
        self._mark_stale_unconfirmed()
        self._thread=None
        if start_worker:
            self._thread=threading.Thread(target=self._run,daemon=True,
                                          name="dominium-query-atlas")
            self._thread.start()

    def _mark_stale_unconfirmed(self):
        cutoff=self.clock()-150
        with connect_db(self.db_path) as db:
            db.execute('''UPDATE query_jobs SET error_code='atlas_submit_unconfirmed',
                updated_at=? WHERE state='submission_uncertain'
                AND remote_queue_id IS NULL
                AND error_code='' AND created_at<?
                AND created_by LIKE 'user-%' ''',
                (self.clock(),cutoff))

    def close(self):
        self._stop.set();self._wake.set()
        if self._thread:self._thread.join(timeout=3)

    def _owned(self,job_id,actor):
        if not JOB_RE.fullmatch(job_id):return False
        row=read_job(job_id,self.db_path)
        return bool(row and row["created_by"]==actor)

    def _ensure_fallback(self,parent_id):
        """Persist exactly one reserve job for a confirmed first-file HTTP 404.

        A unique index and immediate SQLite transaction prevent duplicate IDs
        after crashes or concurrent worker instances. Never resubmit uncertain
        requests; a reserve's own id is durable before touching Atlas.
        """
        with connect_db(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            primary=db.execute("""SELECT id,city,location,created_by,state,
                remote_queue_id,attachment_failures,error_code,fallback_enabled,
                fallback_of FROM query_jobs WHERE id=?""",(parent_id,)).fetchone()
            if not primary or not (
                primary["fallback_enabled"]==1
                and not primary["fallback_of"]
                and primary["state"]=="attachment_wait"
                and primary["remote_queue_id"]
                and primary["attachment_failures"]>=1
                and primary["error_code"]=="attachment_http_404"
                and ACTOR_RE.fullmatch(primary["created_by"])
                and primary["city"] in CITY
                and primary["location"] in LOCATION
            ):
                return None
            already=db.execute("SELECT id FROM query_jobs WHERE fallback_of=?",
                               (parent_id,)).fetchone()
            if already:return None
            child_id=uuid.uuid4().hex
            now=self.clock()
            db.execute("""INSERT INTO query_jobs
                (id,city,location,created_by,state,created_at,updated_at,
                 error_code,fallback_of,fallback_enabled)
                VALUES(?,?,?,?,'submission_uncertain',?,?,'',?,0)""",
                (child_id,primary["city"],primary["location"],
                 primary["created_by"],now,now,parent_id))
            return child_id

    def _submit_existing(self,job_id):
        row=read_job(job_id,self.db_path)
        if not row or row["state"]!="submission_uncertain":return
        chrome=self.browser_factory()
        try:
            try:
                chrome.open()
            except AtlasAuthRequired:
                # No report submitted. Keep a durable, actionable failure state.
                update_job(job_id,self.db_path,state="atlas_auth_required",
                           error_code="atlas_auth_required")
                return
            remote=chrome.submit_once(row["city"],row["location"])
            save_queue(job_id,remote,self.db_path)
        finally:
            chrome.close()

    def _run(self):
        last_scanned={}
        while not self._stop.is_set():
            try:
                with self._lock:
                    new=self._new_jobs.pop(0) if self._new_jobs else None
                if new:
                    try:self._submit_existing(new)
                    except Exception as exc:
                        logging.warning("Atlas QUERY submit inconclusive: %s",type(exc).__name__)
                        # Keep the uncertain state (no retries), but surface a durable
                        # failure code in the browser instead of spinning forever.
                        try:
                            if (read_job(new,self.db_path) or {}).get("state")=="submission_uncertain":
                                update_job(new,self.db_path,error_code="atlas_submit_unconfirmed")
                        except Exception:
                            logging.exception("Atlas QUERY could not persist submit error")
                    continue
                self._mark_stale_unconfirmed()
                with connect_db(self.db_path) as db:
                    rows=db.execute("""SELECT id,state,next_attachment_check,error_code,updated_at,
                        attachment_failures,fallback_enabled,fallback_of FROM query_jobs
                        WHERE created_by LIKE 'user-%' AND state IN
                        ('queued','processing','attachment_missing','attachment_wait','download_ready')
                        ORDER BY created_at ASC LIMIT 30""").fetchall()
                now=self.clock()
                processed=False
                for row in rows:
                    if self._stop.is_set():break
                    job_id=row["id"]
                    if row["state"]=="download_ready":
                        try:
                            j=read_job(job_id,self.db_path)
                            records=parse_report(j["download_path"])
                            store_records(job_id,records,self.db_path)
                            update_job(job_id,self.db_path,state="ready",error_code="")
                        except (OSError,ValueError,ImportError) as err:
                            logging.warning("Atlas QUERY parse type=%s",type(err).__name__)
                            update_job(job_id,self.db_path,state="format_review",
                                       error_code="report_parse_not_confirmed")
                        processed=True
                        continue
                    if last_scanned.get(job_id,0)+12>now:continue
                    # Retry only reads after auth expiry; never submit another report.
                    if row["error_code"]=="atlas_auth_required" and row["updated_at"]+120>now:continue
                    # A confirmed HTTP 404 on a new workflow unlocks one and
                    # only one extra Atlas generation, for any supported city.
                    # The primary ID remains unchanged and keeps retrying.
                    if (row["state"]=="attachment_wait"
                        and row["attachment_failures"]>=1
                        and row["fallback_enabled"]==1
                        and not row["fallback_of"]):
                        reserve=self._ensure_fallback(job_id)
                        if reserve:
                            with self._lock:
                                self._new_jobs.append(reserve)
                                self._wake.set()
                            logging.info("Atlas QUERY reserved alternative queued")
                            processed=True
                            break
                    if row["next_attachment_check"] and row["next_attachment_check"]>now:continue
                    last_scanned[job_id]=now
                    try:
                        if row["state"] in ("queued","processing","attachment_missing"):
                            poll_report(job_id,self.db_path,browser_factory=self.browser_factory)
                        elif row["state"]=="attachment_wait":
                            fetch_file(job_id,self.db_path,chrome_factory=self.browser_factory)
                        processed=True
                    except AtlasAuthRequired:
                        logging.warning("Atlas QUERY NetTask session expired; existing queue kept")
                        try:update_job(job_id,self.db_path,error_code="atlas_auth_required")
                        except Exception:logging.exception("Atlas QUERY could not persist login warning")
                    except Exception as exc:
                        logging.warning("Atlas QUERY poll unavailable type=%s",type(exc).__name__)
                self._wake.wait(2 if processed else 5)
                self._wake.clear()
            except Exception as exc:
                logging.warning("Atlas QUERY supervisor type=%s",type(exc).__name__)
                self._wake.wait(10);self._wake.clear()

    def handle(self,method,target,actor,body=None):
        route=parse_query_route(method,target)
        if route is None:return 404,{"ok":False,"error":"Rota nao permitida"},None
        if not ACTOR_RE.fullmatch(actor or ""):
            return 403,{"ok":False,"error":"Identidade nao autorizada"},None
        action,job_id,param=route
        try:
            if action=="list":
                with connect_db(self.db_path) as db:
                    rows=db.execute("""SELECT id,city,location,state,remote_queue_id,
                      created_at,updated_at,error_code,fallback_of,fallback_enabled
                      FROM query_jobs
                      WHERE created_by=? ORDER BY created_at DESC LIMIT 20""",(actor,)).fetchall()
                return 200,{"ok":True,"jobs":[dict(row) for row in rows]},None
            if action=="create":
                if not isinstance(body,dict) or set(body)!={"city","location"}:
                    return 400,{"ok":False,"error":"Informe praça e localização"},None
                city,location=body["city"],body["location"]
                if city not in CITY or location not in LOCATION:
                    return 400,{"ok":False,"error":"Seleção inválida"},None
                with self._lock:
                    job_id,created=claim_job(city,location,self.db_path,created_by=actor)
                    if created:
                        # Only NEW submissions adopt the dual-ID policy. Existing
                        # historical 404s cannot silently create extra queues.
                        with connect_db(self.db_path) as db:
                            db.execute("UPDATE query_jobs SET fallback_enabled=1 WHERE id=?",
                                       (job_id,))
                        self._new_jobs.append(job_id)
                        self._wake.set()
                return (202 if created else 200),{"ok":True,
                      "job":public_status(read_job(job_id,self.db_path)),
                      "reused":not created},None
            if not self._owned(job_id,actor):
                return 404,{"ok":False,"error":"Trabalho não encontrado"},None
            current=read_job(job_id,self.db_path)
            if action=="reconcile":
                # Explicit operator acknowledgment only. This closes the local
                # uncertain record; it cannot prove whether Atlas received it.
                if body!={"atlas_checked_no_queue":True}:
                    return 400,{"ok":False,"error":"Confirme que verificou no Atlas a ausência da fila."},None
                with self._lock:
                    with connect_db(self.db_path) as db:
                        db.execute("BEGIN IMMEDIATE")
                        row=db.execute("""SELECT id,created_by,created_at,state,
                            remote_queue_id,error_code,fallback_of
                            FROM query_jobs WHERE id=?""",(job_id,)).fetchone()
                        if not row or row["created_by"]!=actor:
                            return 404,{"ok":False,"error":"Trabalho não encontrado"},None
                        if (row["state"]!="submission_uncertain"
                            or row["remote_queue_id"]
                            or row["error_code"]!="atlas_submit_unconfirmed"
                            or row["fallback_of"]):
                            return 409,{"ok":False,"error":"Esta solicitação não pode ser encerrada por reconciliação."},None
                        if self.clock()-row["created_at"]<300:
                            return 409,{"ok":False,"error":"Aguarde pelo menos cinco minutos para verificar o Atlas."},None
                        db.execute("""UPDATE query_jobs SET state='failed',
                            error_code='manually_closed_unconfirmed',updated_at=?
                            WHERE id=?""",(self.clock(),job_id))
                return 200,{"ok":True,"job":public_status(read_job(job_id,self.db_path))},None
            if action=="detail":
                status=public_status(current)
                if current["state"]=="ready":
                    with connect_db(self.db_path) as db:
                        cnt=db.execute("SELECT COUNT(*) FROM query_rows WHERE job_id=?",
                                       (job_id,)).fetchone()[0]
                    status["total_rows"]=cnt
                return 200,{"ok":True,"job":status},None
            if current["state"]!="ready":
                return 409,{"ok":False,"error":"Relatório ainda não disponível"},None
            if action=="rows":
                result=page(job_id,self.db_path,offset=param,limit=100)
                return 200,{"ok":True,**result},None
            if action=="export":
                with connect_db(self.db_path) as db:
                    records=[json.loads(r[0]) for r in db.execute(
                        "SELECT data FROM query_rows WHERE job_id=? ORDER BY position",(job_id,))]
                raw=export_csv(records) if param=="csv" else export_xlsx(records)
                if len(raw)>35_000_000:
                    return 413,{"ok":False,"error":"Arquivo muito grande para exportação"},None
                content="text/csv; charset=utf-8" if param=="csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                return 200,raw,content
            return 404,{"ok":False,"error":"Rota não permitida"},None
        except ValueError as exc:
            if action=="create" and "ja esta em andamento" in str(exc):
                return 409,{"ok":False,"error":"Esta praça já tem uma QUERY em processamento"},None
            return 400,{"ok":False,"error":"Parâmetros inválidos"},None
        except Exception as exc:
            logging.warning("Atlas QUERY endpoint type=%s",type(exc).__name__)
            return 503,{"ok":False,"error":"QUERY Atlas temporariamente indisponível"},None
