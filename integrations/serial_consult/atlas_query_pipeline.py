"""Private Atlas QUERY queue/attachment orchestrator (CLI foundation).

Authenticated Chrome-for-Testing performs GETs in a separate tab. Never
re-generates a report on 404. Reports and URLs remain out of Git and logs.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from atlas_query_report import ChromeAtlas, connect_db, read_job, DB

# Direct authenticated NetTask page, avoiding a new SSO login window.
QUEUE_URL = ("https://atlas.netservicos.com.br/nettask/filas/filas.do?"
             "acao=prepareSearch&tipoConsulta=consultaId&menu=yes")
DATA = Path(r"C:\DominiumRuntime\AtlasQueryData\attachments")
VALID_QUEUE = re.compile(r"\d{5,15}\Z")
FILE_URL = re.compile(r"/app-1//RELATORIOS/\d{6}/[A-Za-z0-9_-]+\.xls\Z", re.I)


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
            "download_path":"TEXT NOT NULL DEFAULT ''"
        }.items():
            if name not in existing:
                db.execute(f"ALTER TABLE query_jobs ADD COLUMN {name} {definition}")


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
                elif any(term in upper for term in ("ERRO","CANCEL","FALHA")):state="failed"
                else:state="processing"
                info={"state":state,"detail_link":row.get("detail") or ""}
                break
        if info:break
    if not info: return {"state":"not_found"}
    if info["state"]!="complete":return {"state":info["state"]}
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
        update_job(job_id,db_path,state="processing" if state=="processing" else "queued")
    row=read_job(job_id,db_path)
    return public_status(row)


def public_status(job):
    return {key:job[key] for key in (
        "id","city","location","state","remote_queue_id",
        "attachment_failures","created_at","updated_at","error_code") if key in job}


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
        chrome.open(QUEUE_URL,form_id="FilasForm",require_generator=False)
        frame=chrome.call(chrome.tab,"Page.getFrameTree",{})
        fid=frame.get("frameTree",{}).get("frame",{}).get("id")
        res=chrome.call(chrome.tab,"Network.loadNetworkResource",{
            "frameId":fid,"url":job["attachment_url"],
            "options":{"disableCache":True,"includeCredentials":True}},timeout=35)
        resource=res.get("resource") or {}
        status=resource.get("httpStatusCode")
        if status==404:
            failures=job.get("attachment_failures",0)+1
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
                    if total>30_000_000:raise ValueError("Report too large")
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
