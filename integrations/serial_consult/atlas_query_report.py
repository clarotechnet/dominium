"""Atlas read-only equipment report generator in a dedicated managed Chrome tab.

One-time POST is never retried automatically after uncertainty.
Persistent job state and actor isolation live outside the Git repo.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import re
import sqlite3
import time
import uuid
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
import websocket

ROOT = Path(r"C:\DominiumRuntime\ManagedAtlasTOA-20261022")
DB = Path(r"C:\DominiumRuntime\AtlasQueryData\query_jobs.sqlite3")
CITY = {"natal":"179","mossoro":"592","fortaleza":"198","recife":"57"}
LOCATION = {"empreiteira":"5"}
ATLAS_URL = "https://atlas.netservicos.com.br/nethome/equipamento/relatorioEquipamentos.do?acao=prepareSearch"
ID_RE = re.compile(r"identificador\s+para\s+consulta\s*:\s*(\d{5,15})", re.I)


@contextmanager
def connect_db(db_path=DB):
    db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(db_path,timeout=10)
    try:
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS query_jobs (
          id TEXT PRIMARY KEY,city TEXT NOT NULL,location TEXT NOT NULL,
          state TEXT NOT NULL,remote_queue_id TEXT,
          created_at REAL NOT NULL,updated_at REAL NOT NULL,
          error_code TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL DEFAULT ''
        )""")
        existing={row["name"] for row in db.execute("PRAGMA table_info(query_jobs)")}
        if "created_by" not in existing:
            db.execute("ALTER TABLE query_jobs ADD COLUMN created_by TEXT NOT NULL DEFAULT ''")
        db.execute("CREATE INDEX IF NOT EXISTS idx_query_actor ON query_jobs(created_by,city,location,created_at)")
        db.commit()
        with db:yield db
    finally:db.close()


def claim_job(city,location,db_path=DB,*,timestamp=None,created_by=""):
    if city not in CITY or location not in LOCATION:
        raise ValueError("Praca ou localizacao nao permitida")
    now=time.time() if timestamp is None else timestamp
    with connect_db(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        # An Atlas submission without a confirmed ID must remain locked even
        # after the regular 8-hour reuse window. Require explicit, audited
        # operator reconciliation before any new submission can be created.
        uncertain=db.execute("""SELECT id FROM query_jobs
            WHERE city=? AND location=? AND created_by=?
            AND state='submission_uncertain' AND remote_queue_id IS NULL
            ORDER BY created_at DESC LIMIT 1""",(city,location,created_by)).fetchone()
        if uncertain:return uncertain["id"],False
        previous=db.execute("""SELECT id FROM query_jobs WHERE city=? AND location=?
            AND created_by=? AND created_at>? AND state IN
            ('submitting','submission_uncertain','queued','processing',
             'attachment_wait','attachment_missing','download_ready','ready')
            ORDER BY created_at DESC LIMIT 1""",
            (city,location,created_by,now-8*3600)).fetchone()
        if previous:return previous["id"],False
        columns={r['name'] for r in db.execute('PRAGMA table_info(query_jobs)')}
        timed_pending=""" OR (fallback_delay_seconds=45 AND fallback_of=''
            AND NOT EXISTS(SELECT 1 FROM query_jobs c WHERE c.fallback_of=p.id))""" if 'fallback_delay_seconds' in columns else ''
        other=db.execute("""SELECT id FROM query_jobs p WHERE city=? AND location=?
           AND created_by!=? AND created_by!='' AND created_at>? AND (state IN
           ('submitting','submission_uncertain','queued','processing','attachment_wait')"""+
           timed_pending+") LIMIT 1",(city,location,created_by,now-3600)).fetchone()
        if other:raise ValueError("A mesma QUERY ja esta em andamento")
        job_id=uuid.uuid4().hex
        db.execute("""INSERT INTO query_jobs
             (id,city,location,state,created_at,updated_at,created_by)
             VALUES(?,?,?,'submission_uncertain',?,?,?)""",
             (job_id,city,location,now,now,created_by))
        return job_id,True


def save_queue(job_id,queue_id,db_path=DB,*,reserve_after=0,timestamp=None):
    if not re.fullmatch(r"\d{5,15}",str(queue_id)):
        raise ValueError("ID de fila nao confirmado")
    with connect_db(db_path) as db:
        now=time.time() if timestamp is None else timestamp
        due_sql=",fallback_due_at=?" if reserve_after else ""
        # Queue confirmation and reserve deadline are committed together.
        params=(str(queue_id),now,*((now+reserve_after,) if reserve_after else ()),job_id)
        count=db.execute("""UPDATE query_jobs SET remote_queue_id=?,state='queued',
          updated_at=?,error_code=''"""+due_sql+" WHERE id=? AND state='submission_uncertain'",
          params).rowcount
        if count!=1:raise ValueError("Estado de fila inconsistente")


def read_job(job_id,db_path=DB):
    with connect_db(db_path) as db:
        row=db.execute("SELECT * FROM query_jobs WHERE id=?",(job_id,)).fetchone()
    return dict(row) if row else None


class AtlasAuthRequired(RuntimeError):
    """Atlas navigation requires an operator to authenticate; no report sent."""


class ChromeAtlas:
    """Use an invisible same-origin frame IN the managed Atlas watchdog tab.

    Never launch an additional Chrome tab/window or navigate the existing tab.
    The bot/extension and the user's foreground Atlas remain untouched.
    """
    def __init__(self,root=ROOT):
        portfile=root/"profile"/"DevToolsActivePort"
        port=int(portfile.read_text(encoding="utf-8").splitlines()[0])
        if not 1024<=port<=65535:raise ValueError("Porta de depuracao invalida")
        self.base=f"http://127.0.0.1:{port}"
        self.tab=None
        self.frame_id=None

    def _http(self,path):
        with urllib.request.urlopen(self.base+path,timeout=5) as response:
            return json.load(response)

    @staticmethod
    def call(ws,method,params,timeout=12):
        request_id=int(time.monotonic_ns()%99999999)+1
        ws.settimeout(timeout)
        ws.send(json.dumps({"id":request_id,"method":method,"params":params}))
        while True:
            response=json.loads(ws.recv())
            if response.get("id")!=request_id:continue
            if "error" in response:raise RuntimeError(method+" falhou no Chrome")
            return response.get("result") or {}

    def open(self,url=ATLAS_URL,*,form_id="RelatorioEquipamentosV2Form",
             require_generator=True):
        uri=urlsplit(url)
        if uri.hostname!="atlas.netservicos.com.br" or uri.scheme!="https":
            raise ValueError("Origem Atlas nao permitida")
        candidates=[page for page in self._http("/json/list")
            if page.get("type")=="page" and
            urlsplit(page.get("url") or "").hostname=="atlas.netservicos.com.br"]
        if not candidates:
            raise AtlasAuthRequired("A aba Atlas do watchdog nao esta aberta")
        source=next((p for p in candidates
                     if urlsplit(p.get("url") or "").path.startswith("/nethome")),candidates[0])
        self.tab=websocket.create_connection(source["webSocketDebuggerUrl"],
                                             timeout=12,suppress_origin=True)
        self.frame_id="dominium-query-"+uuid.uuid4().hex
        fid=json.dumps(self.frame_id)
        expression="""(async function(){
          const parent=globalThis.document.querySelector('frame[name=principal]')?.contentDocument
            || globalThis.document;
          const host=parent.body||parent.documentElement;
          if(!host) return {error:'atlas_frame_missing'};
          const frame=parent.createElement('iframe');
          frame.id=%s;
          frame.style.cssText='display:none!important;width:0;height:0;border:0';
          frame.setAttribute('aria-hidden','true');
          const result=await new Promise(function(resolve){
            let finished=false;
            function finish(){
              if(finished)return;
              finished=true;
              let doc=null,frameHost='',pathname='',login=false,ready=false,generator=false;
              try{
                doc=frame.contentDocument;
                frameHost=frame.contentWindow.location.hostname;
                pathname=frame.contentWindow.location.pathname;
                login=!!doc?.querySelector('input[type=password]');
                ready=!!doc?.getElementById(%s);
                // NetTask expiry may show no password field or query form.
                if(!ready && doc?.body &&
                   /sess.{0,12}expirou|sess.{0,12}expirada|session expired/i.test(doc.body.innerText||'')){
                  login=true;
                }
                generator=typeof frame.contentWindow.gerarRelatorio==='function';
              }catch(err){frameHost='cross-origin';}
              resolve({host:frameHost,path:pathname,login:login,
                       ready:ready,generator:generator});
            }
            frame.addEventListener('load',function(){
              let path='';try{path=frame.contentWindow.location.pathname}
              catch(err){path='cross-origin'}
              if(path==='cross-origin')finish();
              else if(path && path!=='blank'){
                try{
                  if(frame.contentDocument.getElementById(%s)
                     ||frame.contentDocument.querySelector('input[type=password]'))finish();
                }catch(err){finish();}
              }
            });
            frame.src=%s;
            host.appendChild(frame);
            setTimeout(finish,15000);
          });
          return result;
        })()"""%(fid,json.dumps(form_id),json.dumps(form_id),json.dumps(url))
        outcome=self.call(self.tab,"Runtime.evaluate",{
             "expression":expression,"returnByValue":True,"awaitPromise":True},timeout=26)
        if outcome.get("exceptionDetails"):
            raise RuntimeError("Falha ao carregar quadro Atlas")
        summary=(outcome.get("result") or {}).get("value") or {}
        if (summary.get("host")!="atlas.netservicos.com.br" or summary.get("login")):
            raise AtlasAuthRequired("Sessao Atlas precisa de login")
        if not summary.get("ready") or (require_generator and not summary.get("generator")):
            raise RuntimeError("Formulario Atlas nao carregou no navegador existente")

    def eval(self,expression,timeout=12):
        if not self.tab or not self.frame_id:
            raise RuntimeError("Atlas nao conectado")
        # Scope existing expressions to our hidden same-origin report frame.
        wrapped="""(() => {
          const host=globalThis.document.querySelector('frame[name=principal]')?.contentDocument
            || globalThis.document;
          const target=host.getElementById(%s);
          if(!target||!target.contentDocument)throw new Error('Atlas frame missing');
          const window=target.contentWindow;
          const document=target.contentDocument;
          const location=window.location;
          const gerarRelatorio=window.gerarRelatorio?.bind(window);
          const BaseDWR=window.BaseDWR;
          const addOptionListFila=window.addOptionListFila?.bind(window);
          const buscarFilasTipoConsultaId=window.buscarFilasTipoConsultaId?.bind(window);
          const abreDetalhesFila=window.abreDetalhesFila?.bind(window);
          const selecionarTab=window.selecionarTab?.bind(window);
          return (%s);
        })()"""%(json.dumps(self.frame_id),expression)
        result=self.call(self.tab,"Runtime.evaluate",
             {"expression":wrapped,"returnByValue":True,"awaitPromise":False},
             timeout=timeout)
        if result.get("exceptionDetails"):
            raise RuntimeError("Falha JS no quadro Atlas")
        return (result.get("result") or {}).get("value")

    def inspect_parameters(self,city,location):
        js="""(() => {const city=%s,loc=%s;
           const c=document.querySelector('#idOperacao');
           const l=document.querySelector('#idTipoLocalizacao');
           return {form:!!document.getElementById('RelatorioEquipamentosV2Form'),
             cityMatch:!!c&&[...c.options].some(o=>o.value===city),
             localMatch:!!l&&[...l.options].some(o=>o.value===loc),
             generator:typeof gerarRelatorio==='function',
             reportService:typeof BaseDWR?.executeService==='function'}
        })()"""%(json.dumps(CITY[city]),json.dumps(LOCATION[location]))
        result=self.eval(js)
        if not result or not all(result.values()):
            raise RuntimeError("Parametros Atlas nao confirmados")
        return {key:bool(value) for key,value in result.items()}

    def submit_once(self,city,location,timeout=30):
        self.inspect_parameters(city,location)
        js="""(() => {
          const city=%s,loc=%s;
          for(const o of document.querySelector('#idOperacao').options)
            o.selected=o.value===city;
          document.querySelector('#idTipoLocalizacao').value=loc;
          document.querySelector('#idLocalizacao').value='';
          for(const id of ['idTipoEquipamento','idEstadoEquipamento',
              'idSubTipoEquipamento','idClassificacao','idEmpresa']){
              const el=document.getElementById(id);if(el)el.value='';
          }
          const dam=document.querySelector('#typeDam');if(dam)dam.value='';
          gerarRelatorio();return {submitted:true}
        })()"""%(json.dumps(CITY[city]),json.dumps(LOCATION[location]))
        sent=self.eval(js)
        if not sent or not sent.get("submitted"):
            raise RuntimeError("Atlas nao confirmou acionamento")
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            msg=self.eval("""(() => ({text:
              (document.querySelector('#msgok')?.textContent||'').slice(0,250)}))()""")
            match=ID_RE.search(str((msg or {}).get("text") or ""))
            if match:return match.group(1)
            time.sleep(1.5)
        raise RuntimeError("Resposta incerta; nao reenviar automaticamente")

    def close(self):
        try:
            if self.tab and self.frame_id:
                js="""(() => {
                  const doc=globalThis.document.querySelector('frame[name=principal]')?.contentDocument
                    || globalThis.document;
                  const frame=doc.getElementById(%s);
                  if(frame)frame.remove();
                  return true;
                })()"""%json.dumps(self.frame_id)
                self.call(self.tab,"Runtime.evaluate",{"expression":js,
                    "returnByValue":True},timeout=6)
        except Exception:
            pass
        finally:
            if self.tab:self.tab.close()
            self.tab=None
            self.frame_id=None


def generate(city,location,dry_run=False,db_path=DB,chrome_factory=ChromeAtlas,
             created_by=""):
    if city not in CITY or location not in LOCATION:
        raise ValueError("Praca/localizacao invalida")
    job_id=None
    if not dry_run:
        job_id,is_new=claim_job(city,location,db_path,created_by=created_by)
        if not is_new:
            return {"id":job_id,"reused":True,"state":read_job(job_id,db_path)["state"]}
    browser=chrome_factory()
    try:
        browser.open()
        if dry_run:
            return {"dry_run":True,"city":city,"location":location,
                    "parameters":browser.inspect_parameters(city,location)}
        remote=browser.submit_once(city,location)
        save_queue(job_id,remote,db_path)
        return {"id":job_id,"state":"queued","remote_queue_id":remote}
    finally:browser.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--city",required=True,choices=sorted(CITY))
    parser.add_argument("--location",default="empreiteira",choices=sorted(LOCATION))
    parser.add_argument("--start",action="store_true")
    args=parser.parse_args()
    print(json.dumps(generate(args.city,args.location,dry_run=not args.start),
                     ensure_ascii=False))


if __name__=="__main__":main()
