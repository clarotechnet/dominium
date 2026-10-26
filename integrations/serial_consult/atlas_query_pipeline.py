"""Private Atlas QUERY queue/attachment orchestrator (CLI foundation).

Authenticated Chrome-for-Testing performs GETs in a separate tab. Never
re-generates a report on 404. Reports and URLs remain out of Git and logs.
"""
from __future__ import annotations

import argparse
import base64
import html
import logging
import tempfile
import shutil
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from websocket import WebSocketTimeoutException

from atlas_query_report import AtlasAuthRequired, ChromeAtlas, connect_db, read_job, DB

# Reuse the official NetHome -> Administração de Processos -> Filas -> Consulta por Id
# SSO entry point. Opening /nettask/filas/filas.do directly can report
# 'session expired' even while NetHome is authenticated.
# This URL only authenticates the read-only queue view; it never generates QUERY.
QUEUE_URL = ("https://atlas.netservicos.com.br:443/nettask/singleSignOn.do?"
             "j_url=filas/filas.do?acao=prepareSearch&tipoConsulta=consultaId&menu=yes")
DATA = Path(r"C:\DominiumRuntime\AtlasQueryData\attachments")
VALID_QUEUE = re.compile(r"\d{5,15}\Z")
FILE_URL = re.compile(r"/app-[123]//RELATORIOS/\d{6}/[A-Za-z0-9_-]+\.xls\Z", re.I)


def valid_report_url(value):
    try:
        uri=urlsplit(str(value))
    except ValueError:
        return False
    return (uri.scheme=="https" and uri.hostname=="batatlas.netservicos.com.br"
            and not uri.username and not uri.password and not uri.port and not uri.query
            and not uri.fragment and bool(FILE_URL.fullmatch(uri.path)))


def upgrade_db(db_path=DB):
    with connect_db(db_path) as db:
        existing={row["name"] for row in db.execute("PRAGMA table_info(query_jobs)")}
        for name,definition in {
            "completed_at":"REAL NOT NULL DEFAULT 0",
            "next_attachment_check":"REAL NOT NULL DEFAULT 0",
            "attachment_failures":"INTEGER NOT NULL DEFAULT 0",
            "attachment_url":"TEXT NOT NULL DEFAULT ''",
            "download_path":"TEXT NOT NULL DEFAULT ''",
            "fallback_of":"TEXT NOT NULL DEFAULT ''",
            "retry_of":"TEXT NOT NULL DEFAULT ''",
            "fallback_enabled":"INTEGER NOT NULL DEFAULT 0",
            "fallback_delay_seconds":"INTEGER NOT NULL DEFAULT 0",
            "fallback_due_at":"REAL NOT NULL DEFAULT 0"
        }.items():
            if name not in existing:
                db.execute(f"ALTER TABLE query_jobs ADD COLUMN {name} {definition}")
        # At most one persisted reserve attempt per main QUERY.
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_query_one_fallback
            ON query_jobs(fallback_of) WHERE fallback_of!=''""")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_query_one_retry
            ON query_jobs(retry_of) WHERE retry_of!=''""")


def update_job(job_id, db_path=DB, **fields):
    allowed={"state","error_code","remote_queue_id","completed_at",
             "next_attachment_check","attachment_failures","attachment_url",
             "download_path"}
    if not fields or not set(fields).issubset(allowed):
        raise ValueError("Unknown job update")
    upgrade_db(db_path)
    fields["updated_at"]=time.time()
    with connect_db(db_path) as db:
        values=list(fields)
        count=db.execute("UPDATE query_jobs SET "+",".join(name+"=?" for name in values)+
                  " WHERE id=?",(*[fields[name] for name in values],job_id)).rowcount
        if count!=1:raise ValueError("Unknown report")


def read_process_state(chrome, remote_id):
    """Read the official yellow/green process view without opening a popup.

    Require an identified equipment task and one unambiguous state. Never
    retain or log the private HTML response, and never submit a report.
    """
    if not isinstance(remote_id, str) or not VALID_QUEUE.fullmatch(remote_id):
        raise ValueError("Queue ID invalid")
    frame=chrome.call(chrome.tab,"Page.getFrameTree",{})
    resource=chrome.call(chrome.tab,"Network.loadNetworkResource",{
        "frameId":frame["frameTree"]["frame"]["id"],
        "url":"https://atlas.netservicos.com.br/nettask/filas/processos.do?idFila="+remote_id,
        "options":{"disableCache":True,"includeCredentials":True}},timeout=20).get("resource") or {}
    stream=resource.get("stream")
    try:
        if resource.get("httpStatusCode")==401:
            raise AtlasAuthRequired("Sessao de processos Atlas precisa de login")
        if resource.get("httpStatusCode")!=200 or not stream:return "unknown"
        raw=bytearray()
        while True:
            chunk=chrome.call(chrome.tab,"IO.read",{"handle":stream,"size":65536})
            raw.extend(base64.b64decode(chunk.get("data") or "")
                if chunk.get("base64Encoded") else (chunk.get("data") or "").encode("utf-8"))
            if len(raw)>512_000:return "unknown"
            if chunk.get("eof"):break
        text=raw.decode("utf-8",errors="replace")
        if re.search(r"<input\b[^>]*\btype\s*=\s*['\"]?password\b",text,re.I):
            raise AtlasAuthRequired("Sessao de processos Atlas precisa de login")
        text=re.sub(r"<(script|style)\b.*?</\1\s*>","",text,flags=re.I|re.S)
        text=html.unescape(re.sub(r"<[^>]+>"," ",text))
        if (not re.search(r"(?<!\d)"+re.escape(remote_id)+r"(?!\d)",text)
                or "RELATORIO_EQUIPAMENTOS" not in text.upper()):return "unknown"
        states=set(re.findall(r"\bstatus\.fila\.([a-z_]+)\b",text.casefold()))
        if len(states)!=1:return "unknown"
        state=states.pop()
        if state=="completo":return "complete"
        if state in ("falhou","falha","erro","cancelado","cancelada"):return "failed"
        if state in ("nova","novo","processando","aguardando","agendada"):return "processing"
        return "unknown"
    finally:
        if stream:chrome.call(chrome.tab,"IO.close",{"handle":stream})


def evaluate_query(chrome, remote_id):
    """Perform only read-only queue search; report source is checked by ID."""
    if not VALID_QUEUE.fullmatch(remote_id):
        raise ValueError("Queue ID invalid")
    chrome.open(QUEUE_URL,form_id="FilasForm",require_generator=False)
    script="""(() => {
      const id=%s;
      if(typeof addOptionListFila!=='function'||typeof buscarFilasTipoConsultaId!=='function')
        return {error:'queue_controls_missing'};
      document.querySelector('#filaId').value=id;
      addOptionListFila();
      if(![...document.querySelector('#listIdFilas').options].some(o=>o.value===id))
        return {error:'queue_selection_failed'};
      buscarFilasTipoConsultaId('/nettask','divFilas');
      return {started:true}
    })()"""%json.dumps(remote_id)
    submitted=chrome.eval(script)
    if not submitted or submitted.get("started") is not True:
        raise RuntimeError("Atlas queue lookup did not start")
    info=None
    for _ in range(10):
        time.sleep(1.5)
        rows=chrome.eval("""(() => {
          const root=document.querySelector('#divFilas');
          return [...(root?.querySelectorAll('tr')||[])].map(tr=>({
           text:(tr.innerText||'').replace(/\\s+/g,' ').slice(0,280),
           detail:(tr.querySelector('a[onclick*="abreDetalhesFila"]')?.getAttribute('onclick')||'').slice(0,140)
          })).slice(0,40)
        })()""") or []
        for row in rows:
            text=str(row.get("text") or "")
            if remote_id in text and "RELATORIO_EQUIPAMENTOS" in text.upper():
                # A row must contain this exact submitted queue ID.
                if not re.search(r"(?<!\d)"+re.escape(remote_id)+r"(?!\d)",text):
                    continue
                upper=text.upper()
                if "COMPLETO" in upper:state="complete"
                elif any(term in upper for term in ("ERRO","CANCEL","FALHA","FALHOU")):state="failed"
                else:state="processing"
                info={"state":state,"detail_link":row.get("detail") or ""}
                break
        if info:break
    if not info: return {"state":"not_found"}
    if info["state"]=="failed":return {"state":"failed"}
    process=read_process_state(chrome,remote_id)
    if process=="failed":return {"state":"failed"}
    if process!="complete":
        return {"state":"processing",**({"error_code":"process_status_unconfirmed"}
                if process=="unknown" else {})}
    action=info["detail_link"]
    if ("abreDetalhesFila(" not in action or remote_id not in action):
        raise RuntimeError("Queue detail action not verified")
    details="""(() => {
       const id=%s;
       if(typeof abreDetalhesFila!=='function')return {error:'detail_controls_missing'};
       abreDetalhesFila('/nettask',id,'3','false');
       return {ok:true}
    })()"""%json.dumps(remote_id)
    if not (chrome.eval(details) or {}).get("ok"):
        raise RuntimeError("Could not open queue details")
    for _ in range(12):
        time.sleep(0.8)
        view=chrome.eval("""(() => ({
            ready:location.pathname.includes('/filas/detalhes.do'),
            tab:typeof selecionarTab==='function'
        }))()""")
        if view and view.get("ready") and view.get("tab"):break
    else:raise RuntimeError("Queue details page did not load")
    switch="""(() => {
      selecionarTab('/nettask','anexos',%s,'no');
      return true
    })()"""%json.dumps(remote_id)
    chrome.eval(switch)
    for _ in range(12):
        time.sleep(1)
        links=chrome.eval("""(() => [...document.querySelectorAll('a[href]')].filter(
          a=>/Relatorio_Equipamentos_Analitico/i.test(a.getAttribute('href')||'')
        ).map(a=>a.href).slice(0,4))()""") or []
        urls=[u for u in links if valid_report_url(u)]
        if urls:return {"state":"complete","attachment_url":urls[0]}
    return {"state":"complete","attachment_url":""}


def poll_report(job_id,db_path=DB,browser_factory=ChromeAtlas,clock=time.time):
    upgrade_db(db_path)
    job=read_job(job_id,db_path)
    if not job or not VALID_QUEUE.fullmatch(job.get("remote_queue_id") or ""):
        raise ValueError("Report not confirmed")
    chrome=browser_factory()
    try:
        found=evaluate_query(chrome,job["remote_queue_id"])
    finally:chrome.close()
    state=found["state"]
    if state=="complete":
        when=job.get("completed_at") or clock()
        url=found.get("attachment_url") or ""
        update_job(job_id,db_path,completed_at=when,attachment_url=url,
                   state="attachment_wait" if url else "attachment_missing",
                   error_code="" if url else "attachment_not_listed")
    elif state=="failed":
        update_job(job_id,db_path,state="failed",error_code="remote_queue_failed")
    else:
        update_job(job_id,db_path,state="processing" if state=="processing" else "queued",
                   error_code="process_status_unconfirmed"
                   if found.get("error_code")=="process_status_unconfirmed" else "")
    row=read_job(job_id,db_path)
    return public_status(row)


def public_status(job):
    return {key:job[key] for key in (
        "id","city","location","state","remote_queue_id",
        "attachment_failures","created_at","updated_at","error_code",
        "fallback_of","fallback_enabled","retry_of","fallback_delay_seconds","fallback_due_at") if key in job}



def download_native_browser(job_id,attachment_url,chrome_factory=ChromeAtlas,timeout=55):
    """Use authenticated Chromium download when CDP network streaming times out.

    The fallback opens ONE temporary browser tab, navigates a hidden iframe to
    the already validated BatAtlas XLS and accepts only a completed .xls file.
    It cannot submit any report or fetch an untrusted URL.
    """
    if not re.fullmatch(r"[0-9a-f]{32}",str(job_id)) or not valid_report_url(attachment_url):
        raise ValueError("Invalid job/attachment")
    DATA.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="batatlas-file-",dir=DATA) as tempdir:
        browser=chrome_factory()
        enabled=False
        try:
            browser.open(QUEUE_URL,form_id="FilasForm",require_generator=False)
            browser.call(browser.tab,"Page.setDownloadBehavior",
                         {"behavior":"allow","downloadPath":tempdir},timeout=10)
            enabled=True
            initiated=browser.eval("""(() => {
                const anchor=document.createElement('iframe');
                anchor.id='dominium-temporary-report-download';
                anchor.style.cssText='display:none!important;width:0;height:0;border:0';
                anchor.src=%s;
                document.body.appendChild(anchor);
                return Boolean(document.getElementById(anchor.id));
            })()"""%json.dumps(attachment_url))
            if initiated is not True:
                raise RuntimeError("Browser report navigation not confirmed")
            expires=time.monotonic()+timeout
            last_size=-1
            stable=0
            while time.monotonic()<expires:
                files=list(Path(tempdir).iterdir())
                if len(files)>2 or any(not f.is_file() for f in files):
                    raise ValueError("Unexpected browser download output")
                if any(f.stat().st_size>60_000_000 for f in files):
                    raise ValueError("Report too large")
                ready=[f for f in files if f.suffix.lower()==".xls"]
                downloading=any(f.name.lower().endswith(".crdownload") for f in files)
                if len(ready)==1 and not downloading:
                    size=ready[0].stat().st_size
                    if size>1024 and size==last_size:stable+=1
                    else:stable=0
                    last_size=size
                    if stable>=1:
                        with ready[0].open("rb") as src:signature=src.read(8)
                        if not (signature.startswith(bytes.fromhex("d0cf11e0"))
                                or signature.startswith(b"PK")
                                or signature.lstrip().startswith(b"<")):
                            raise ValueError("Unknown report signature")
                        destination=DATA/(job_id+".xls")
                        shutil.move(str(ready[0]),str(destination))
                        return destination,size
                time.sleep(.7)
            raise TimeoutError("Browser report download exceeded deadline")
        finally:
            try:
                browser.eval("""(() => {
                    document.getElementById('dominium-temporary-report-download')?.remove();
                    return true;
                })()""")
            except Exception:pass
            if enabled:
                try:browser.call(browser.tab,"Page.setDownloadBehavior",
                                 {"behavior":"default"},timeout=7)
                except Exception:pass
            browser.close()


def fetch_file(job_id,db_path=DB,chrome_factory=ChromeAtlas,clock=time.time):
    upgrade_db(db_path)
    job=read_job(job_id,db_path)
    if not job or not valid_report_url(job.get("attachment_url")):
        raise ValueError("No confirmed Atlas report attachment")
    when=clock()
    if job.get("download_path"):
        return {"state":"download_ready","already_downloaded":True}
    if when<job["completed_at"]+30:
        return {"state":"waiting_30_seconds"}
    if when<job["next_attachment_check"]:
        return {"state":"retry_scheduled","retry_after":int(job["next_attachment_check"]-when)}
    chrome=chrome_factory()
    try:
        attachment_url=job["attachment_url"]
        failures=job.get("attachment_failures",0)
        if failures>=3:
            # Recheck only the same confirmed queue: the link may change later.
            refreshed=evaluate_query(chrome,job["remote_queue_id"])
            if refreshed.get("state")=="failed":
                update_job(job_id,db_path,state="failed",error_code="remote_queue_failed")
                return {"state":"failed","error_code":"remote_queue_failed"}
            if refreshed.get("state")!="complete":
                error="process_status_unconfirmed" if refreshed.get("error_code")=="process_status_unconfirmed" else ""
                update_job(job_id,db_path,state="processing",completed_at=0,
                           next_attachment_check=0,attachment_url="",error_code=error)
                return {"state":"processing","error_code":error}
            candidate=(refreshed.get("attachment_url") or "") if refreshed.get("state")=="complete" else ""
            if valid_report_url(candidate) and candidate!=attachment_url:
                update_job(job_id,db_path,attachment_url=candidate,
                           attachment_failures=0,next_attachment_check=0,error_code="")
                attachment_url=candidate
                failures=0
        else:
            chrome.open(QUEUE_URL,form_id="FilasForm",require_generator=False)
        frame=chrome.call(chrome.tab,"Page.getFrameTree",{})
        fid=frame.get("frameTree",{}).get("frame",{}).get("id")
        res=chrome.call(chrome.tab,"Network.loadNetworkResource",{
            "frameId":fid,"url":attachment_url,
            "options":{"disableCache":True,"includeCredentials":True}},timeout=35)
        resource=res.get("resource") or {}
        status=resource.get("httpStatusCode")
        if status==404:
            failures+=1
            # Retry THIS SAME FILE, never generate a new Atlas report automatically.
            delay=min(900,30*(2**min(5,failures-1)))
            update_job(job_id,db_path,state="attachment_wait",
                       attachment_failures=failures,
                       next_attachment_check=when+delay,
                       error_code="attachment_http_404")
            return {"state":"attachment_wait","http_code":404,"retry_after":delay}
        if status!=200 or not resource.get("success") or not resource.get("stream"):
            raise RuntimeError("Attachment download not confirmed")
        stream=resource["stream"]
        DATA.mkdir(parents=True,exist_ok=True)
        dest=DATA/(job_id+".xls")
        total=0;magic=b""
        try:
            with dest.open("wb") as file:
                while True:
                    chunk=chrome.call(chrome.tab,"IO.read",{"handle":stream,"size":65536})
                    data=(base64.b64decode(chunk.get("data") or "")
                          if chunk.get("base64Encoded") else
                          (chunk.get("data") or "").encode("latin1"))
                    if not magic:magic=data[:8]
                    total+=len(data)
                    if total>60_000_000:raise ValueError("Report too large")
                    file.write(data)
                    if chunk.get("eof"):break
        except:
            dest.unlink(missing_ok=True)
            raise
        finally:
            chrome.call(chrome.tab,"IO.close",{"handle":stream})
        if not (magic.startswith(bytes.fromhex("d0cf11e0")) or magic.startswith(b"PK")
                or magic.lstrip().startswith(b"<")):
            dest.unlink(missing_ok=True)
            raise ValueError("Unknown report content signature")
        update_job(job_id,db_path,state="download_ready",download_path=str(dest),error_code="")
        return {"state":"download_ready","bytes":total}
    except WebSocketTimeoutException:
        # A large XLS may be served normally by Chrome even when its CDP
        # Network.loadNetworkResource times out. Use only the original URL.
        try:
            file_path,size=download_native_browser(job_id,attachment_url,
                                                    chrome_factory=chrome_factory)
            update_job(job_id,db_path,state="download_ready",
                       download_path=str(file_path),error_code="")
            return {"state":"download_ready","bytes":size,"browser_native":True}
        except Exception as err:
            logging.warning("Atlas QUERY native download unsuccessful type=%s",
                            type(err).__name__)
        # Never turn a transport timeout into a false HTTP 404 or another ID.
        retry_after=90
        update_job(job_id,db_path,state="attachment_wait",
                   next_attachment_check=when+retry_after,
                   error_code="attachment_transport_timeout")
        return {"state":"attachment_wait","retry_after":retry_after,
                "error_code":"attachment_transport_timeout"}
    finally:chrome.close()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--job",required=True)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status",action="store_true")
    mode.add_argument("--fetch",action="store_true")
    args=ap.parse_args()
    output=poll_report(args.job) if args.status else fetch_file(args.job)
    print(json.dumps(output,ensure_ascii=False))


if __name__=="__main__":main()
