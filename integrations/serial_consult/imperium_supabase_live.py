"""Live Imperium -> normalized, versioned Supabase snapshots; zero Excel dependency.

A user clicking Consultar periodo invokes this server-only workflow:
- Check operational Supabase schema (fail closed if migration absent).
- Fetch DspConsolidadoEquip + DspConsolidadoOS directly over DataSnap.
- Normalize identified serials; no unverified Atlas/Nomes/Assinantes fields.
- Persist all original and normalized rows in bounded JSONB batches.
- Commit snapshot to 'concluido' ONLY after every batch is acknowledged.
- Read snapshot history / previews directly from Supabase.

This code NEVER changes equipment, warehouse stock, or OS in Imperium.
No service key is sent to the web browser or logs.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from threading import Lock
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen

from equipment_video_transform import is_chip, serial_key
from used_equipment_live_datasnap import fetch_read_only
from used_equipment_report import normalize_range

LOG=logging.getLogger(__name__)
EXPECTED_URL="https://haqzzxpocwzntyudrbch.supabase.co"
ALLOWED_PROFILES={"natal":1,"mossoro":1,"recife":1}
CITY_RECOGNITION={
    "natal":{"NATAL","PARNAMIRIM"},
    "mossoro":{"MOSSORO","MOSSORÓ"},
    "recife":{"RECIFE"},
}
SOURCES=("consolidado","por_os","seriais_tratados")
RUNS="dominium_imperium_consultas"
BATCHES="dominium_imperium_consulta_lotes"
CHUNK_ROWS=180
MAX_DATASET_ROWS=60000
MAX_JSON_BYTES=48_000_000
RUN_PATTERN=r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
DATE_PATTERN=r"\d{4}-\d{2}-\d{2}"
ROUTE_ROOT="/api/stock/analyses/imperium/live"


class LiveSyncError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status=status
        self.code=code


def route_for(method: str,target: str):
    if method not in ("GET","POST") or not isinstance(target,str) or len(target)>230 or any(
        c in target for c in ("#","%","//")
    ):return None
    u=urlsplit(target)
    if u.scheme or u.netloc or u.fragment:return None
    if method=="POST":
        return ("sync",None) if u.path==ROUTE_ROOT and not u.query else None
    if u.path==ROUTE_ROOT:
        try:q=parse_qs(u.query,strict_parsing=True)
        except ValueError:return None
        if set(q)!={"city","start","end"} or any(len(v)!=1 for v in q.values()):return None
        city,start,end=q["city"][0],q["start"][0],q["end"][0]
        if city not in set(ALLOWED_PROFILES)|{"fortaleza"}:return None
        if not re.fullmatch(DATE_PATTERN,start) or not re.fullmatch(DATE_PATTERN,end):return None
        return "history",(city,start,end)
    match=re.fullmatch(rf"{re.escape(ROUTE_ROOT)}/({RUN_PATTERN})/data",u.path)
    if not match:return None
    try:q=parse_qs(u.query,strict_parsing=True)
    except ValueError:return None
    if set(q)!={"city","category","page"} or any(len(v)!=1 for v in q.values()):return None
    city,category,page=q["city"][0],q["category"][0],q["page"][0]
    if city not in set(ALLOWED_PROFILES)|{"fortaleza"} or category not in SOURCES:return None
    if not re.fullmatch(r"[1-9][0-9]{0,2}",page):return None
    return "preview",(match.group(1),city,category,int(page))


def _jsonable(data):
    try:
        return json.loads(json.dumps(data,ensure_ascii=False,default=str,allow_nan=False))
    except (TypeError,ValueError,OverflowError) as exc:
        raise LiveSyncError(502,"bad_source_data","Dados inconsistentes recebidos do Imperium") from exc


def _treated_serials(rows):
    identified={}
    for row in rows:
        serial=serial_key(row.get("SerialNumber"))
        if not serial:continue
        if len(serial)>100:raise LiveSyncError(502,"invalid_serial","O Imperium retornou um serial inválido")
        if serial in identified:continue
        identified[serial]={
            "serial":serial,
            "codigo_equipamento":str(row.get("CodigoEquipamento") or "").strip(),
            "equipamento":str(row.get("Equipamento") or "").strip(),
            "grupo":str(row.get("Grupo") or "").strip(),
            "classificacao":"chip" if is_chip(row.get("Grupo"),row.get("Equipamento")) else "equipamento",
            "numero_wo":str(row.get("NumeroWO") or "").strip(),
            "numero_os":str(row.get("NumOs") or "").strip(),
            "contrato":str(row.get("Contrato") or "").strip(),
            "data_baixa_origem":str(row.get("DataBaixa") or "").strip(),
            "responsavel_os_origem":str(row.get("NomeAbreviado") or "").strip(),
            "cidade":str(row.get("Cidade") or "").strip(),
            # It is NOT the verified video 'DATA' or a current warehouse state.
            "data_modelo_video_verificada":False,
            "estoque_fisico_confirmado":False,
        }
    return list(identified.values())


def prepare_snapshot(raw: dict, city: str):
    if city not in ALLOWED_PROFILES or not isinstance(raw,dict) or set(raw)!=set(SOURCES[:2]):
        raise LiveSyncError(502,"unexpected_source","Datasets do Imperium incompletos")
    expected=CITY_RECOGNITION[city]
    normalized={}
    for kind in SOURCES[:2]:
        rows=raw[kind]
        if not isinstance(rows,list) or len(rows)>MAX_DATASET_ROWS:
            raise LiveSyncError(502,"unexpected_source","Quantidade de registros fora dos limites")
        if any(not isinstance(row,dict) for row in rows):
            raise LiveSyncError(502,"unexpected_source","Formato de registro do Imperium inválido")
        normalized[kind]=_jsonable(rows)
    for item in normalized["por_os"]:
        value=str(item.get("Cidade") or "").strip().upper()
        if value not in expected:
            raise LiveSyncError(502,"city_mismatch","A consulta do Imperium retornou cidade diferente do perfil selecionado")
    serials=_treated_serials(normalized["por_os"])
    normalized["seriais_tratados"]=serials
    if not isinstance(normalized["consolidado"],list):
        raise LiveSyncError(502,"unexpected_source","Consolidado inválido")
    summary={
        "consolidado":len(normalized["consolidado"]),
        "por_os":len(normalized["por_os"]),
        "seriais_tratados":len(serials),
        "equipamentos":sum(1 for x in serials if x["classificacao"]=="equipamento"),
        "chips":sum(1 for x in serials if x["classificacao"]=="chip"),
        "sem_serial":sum(1 for row in normalized["por_os"] if not serial_key(row.get("SerialNumber"))),
    }
    encoded=json.dumps(normalized,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    if len(encoded)>MAX_JSON_BYTES:
        raise LiveSyncError(413,"dataset_too_large","Consulta muito grande; use um período menor")
    digest=hashlib.sha256(encoded).hexdigest()
    return normalized,summary,digest


class SupabasePeriodStore:
    """Private service-role Data API access to the *operational* Dominium project."""
    def __init__(self, env_file: str | Path | None=None, requester=None):
        self._requester=requester
        if requester is not None:
            self.url=EXPECTED_URL+"/rest/v1/"
            self.key="FAKE_TEST_KEY"
            return
        path=Path(env_file or os.getenv("DOMINIUM_QUALITY_ENV_FILE")
                  or r"C:\DominiumMain\.env")
        try:
            source=path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise LiveSyncError(503,"supabase_config","Credenciais privadas do Supabase operacional indisponíveis") from exc
        values={}
        for line in source.splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key,value=line.split("=",1)
                values[key.strip()]=value.strip().strip('"').strip("'")
        url=values.get("SUPABASE_URL","").rstrip("/")
        key=values.get("SUPABASE_SECRET_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY")
        if url!=EXPECTED_URL or not key:
            raise LiveSyncError(503,"supabase_config","Projeto Supabase operacional incorreto ou credencial ausente")
        self.url=url+"/rest/v1/"
        self.key=key

    def call(self,table,method="GET",*,query=None,body=None,upsert=False):
        if table not in (RUNS,BATCHES,"dominium_imperium_tratamento_itens"):
            raise LiveSyncError(500,"internal_table","Tabela de destino não autorizada")
        if self._requester is not None:
            return self._requester(table,method,query,body)
        address=self.url+table+("?"+urlencode(query) if query else "")
        raw=json.dumps(body,ensure_ascii=False,default=str,allow_nan=False).encode() if body is not None else None
        if raw is not None and len(raw)>3_000_000:
            raise LiveSyncError(413,"batch_too_large","Lote de dados acima do limite seguro")
        headers={"apikey":self.key,"Authorization":"Bearer "+self.key,
                 "Accept":"application/json","Prefer":"return=representation"+(
                     ",resolution=merge-duplicates" if upsert and method=="POST" else "")}
        if raw is not None:headers["Content-Type"]="application/json"
        req=Request(address,data=raw,method=method,headers=headers)
        try:
            with urlopen(req,timeout=25) as res:
                payload=res.read(3_000_001)
                if len(payload)>3_000_000:
                    raise LiveSyncError(502,"response_too_large","Resposta Supabase acima do limite")
                return json.loads(payload or b"[]")
        except HTTPError as exc:
            code=exc.code
            if code in (404,406):
                raise LiveSyncError(503,"supabase_migration_missing",
                    "As tabelas da análise Imperium ainda não foram instaladas no Supabase operacional") from None
            if code in (401,403):
                raise LiveSyncError(503,"supabase_auth",
                    "Acesso privado ao Supabase operacional não autorizado") from None
            if code in (409,422):
                raise LiveSyncError(409,"supabase_conflict",
                    "Conflito ao persistir análise no Supabase") from None
            raise LiveSyncError(502,"supabase_http",
                "Falha de gravação no Supabase operacional") from None
        except (URLError,TimeoutError,ValueError) as exc:
            raise LiveSyncError(502,"supabase_network",
                "Conexão ao Supabase operacional indisponível") from exc

    def ensure_ready(self):
        for table,field in ((RUNS,"id"),(BATCHES,"consulta_id")):
            value=self.call(table,query={"select":field,"limit":"0"})
            if not isinstance(value,list):
                raise LiveSyncError(503,"supabase_schema","Estrutura de análise inválida no Supabase")

    @staticmethod
    def _public(run:dict):
        if run.get("estado")!="concluido":
            raise LiveSyncError(503,"incomplete_run","Consulta Supabase ainda não concluída")
        notes=run.get("observacoes") or {}
        counts=notes.get("contagens") or {}
        return {"id":run["id"],"city":run["cidade"],"start":run["data_inicio"],
                "end":run["data_fim"],"created_at":run["criado_em"],
                "checked_at":notes.get("ultima_verificacao_em") or run["criado_em"],
                "counts":counts,"status":"concluido","storage":"supabase",
                "source":"imperium_datasnap","complete_six_tab_analysis":False}

    def find_duplicate(self,city,start,end,digest):
        rows=self.call(RUNS,query={
            "select":"id,cidade,data_inicio,data_fim,criado_em,estado,observacoes",
            "cidade":"eq."+city,"data_inicio":"eq."+start,
            "data_fim":"eq."+end,"hash_conteudo":"eq."+digest,
            "estado":"eq.concluido","order":"criado_em.desc","limit":"1",
        })
        if not isinstance(rows,list):
            raise LiveSyncError(502,"supabase_response","Histórico Supabase inválido")
        return rows[0] if rows else None

    def store(self,city,start,end,actor,data,counts,digest):
        duplicate=self.find_duplicate(city,start,end,digest)
        checked_at=datetime.now(timezone.utc).isoformat()
        if duplicate:
            # A fresh DataSnap query happened even when contents are identical.
            # Keep the same immutable data batches, but record the new check.
            notes=dict(duplicate.get("observacoes") or {})
            notes["ultima_verificacao_em"]=checked_at
            notes["ultima_consulta_por"]=actor
            verified=self.call(RUNS,"PATCH",query={
                "id":"eq."+duplicate["id"],"estado":"eq.concluido",
            },body={"observacoes":notes})
            if not isinstance(verified,list) or len(verified)!=1:
                raise LiveSyncError(502,"supabase_write",
                                    "Supabase não confirmou a atualização da consulta")
            return {"ok":True,"reused":True,"selected":self._public(verified[0])}
        run_id=str(uuid.uuid4())
        summary={"contagens":counts,"etapa":"seriais_coletados",
                 "ultima_verificacao_em":checked_at,
                 "ultima_consulta_por":actor,
                 "pendencias_analise_final":["Atlas","Assinantes","Nomes.","data_modelo_video","nomes_modelos"]}
        starting={
            "id":run_id,"cidade":city,"data_inicio":start,"data_fim":end,
            "solicitado_por":actor,"estado":"processando",
            "observacoes":summary,
            "hash_conteudo":digest,
            "seis_abas_completas":False,
        }
        created=self.call(RUNS,"POST",body=starting)
        if not isinstance(created,list) or len(created)!=1 or created[0].get("id")!=run_id:
            raise LiveSyncError(502,"supabase_write","Supabase não confirmou a criação da consulta")
        try:
            for category in SOURCES:
                source=data[category]
                for index,at in enumerate(range(0,len(source),CHUNK_ROWS)):
                    chunk=source[at:at+CHUNK_ROWS]
                    row={"consulta_id":run_id,"categoria":category,"indice_lote":index,
                         "quantidade":len(chunk),"registros":chunk}
                    result=self.call(BATCHES,"POST",body=row)
                    if not isinstance(result,list) or len(result)!=1 or result[0].get("quantidade")!=len(chunk):
                        raise LiveSyncError(502,"supabase_write","Supabase não confirmou todos os registros do lote")
            updated=self.call(RUNS,"PATCH",query={"id":"eq."+run_id,"estado":"eq.processando"},body={
                "estado":"concluido","concluido_em":datetime.now(timezone.utc).isoformat(),
                "total_consolidado":counts["consolidado"],
                "total_os":counts["por_os"],
                "total_seriais":counts["seriais_tratados"],
            })
            if not isinstance(updated,list) or len(updated)!=1 or updated[0].get("estado")!="concluido":
                raise LiveSyncError(502,"supabase_write","Supabase não confirmou o fechamento da consulta")
            return {"ok":True,"reused":False,"selected":self._public(updated[0])}
        except Exception:
            try:
                self.call(RUNS,"PATCH",query={"id":"eq."+run_id,"estado":"eq.processando"},
                          body={"estado":"falhou","observacoes":{
                              "contagens":counts,"etapa":"gravacao_interrompida",
                              "seis_abas_completas":False}})
            except Exception:
                LOG.warning("Failed marking Dominium Imperium snapshot as failed")
            raise

    def history(self,city,start,end):
        rows=self.call(RUNS,query={
            "select":"id,cidade,data_inicio,data_fim,criado_em,estado,observacoes",
            "cidade":"eq."+city,"data_inicio":"eq."+start,"data_fim":"eq."+end,
            "estado":"eq.concluido","order":"criado_em.desc","limit":"30",
        })
        if not isinstance(rows,list):raise LiveSyncError(502,"supabase_response","Histórico inválido")
        return [self._public(row) for row in rows]

    def preview(self,run_id,city,category,page):
        rows=self.call(RUNS,query={
            "select":"id,cidade,data_inicio,data_fim,criado_em,estado,observacoes",
            "id":"eq."+run_id,"cidade":"eq."+city,
            "estado":"eq.concluido","limit":"1",
        })
        if not isinstance(rows,list) or not rows:
            raise LiveSyncError(404,"run_not_found","Consulta não encontrada nesta praça")
        meta=self._public(rows[0])
        records=self.call(BATCHES,query={
            "select":"quantidade,registros","consulta_id":"eq."+run_id,
            "categoria":"eq."+category,"indice_lote":"eq."+str(page-1),"limit":"1",
        })
        if not isinstance(records,list):
            raise LiveSyncError(502,"supabase_response","Lote de dados inválido")
        listing=records[0]["registros"] if records else []
        total=meta["counts"].get(category,0)
        return {"ok":True,"selected":meta,"category":category,"page":page,
                "rows":listing,"total":total,
                "page_count":(total+CHUNK_ROWS-1)//CHUNK_ROWS,
                "complete_six_tab_analysis":False}


class ImperiumLiveSyncService:
    """Relay target; authenticated caller permissions are enforced upstream."""
    def __init__(self,fetcher=None,repository_factory=None):
        self.fetcher=fetcher or fetch_read_only
        self.repository_factory=repository_factory or SupabasePeriodStore
        self.busy=Lock()

    def handle(self,method,target,actor,body=None):
        route=route_for(method,target)
        if route is None:
            return 404,{"ok":False,"error":"Rota de análise não permitida"},None
        if not re.fullmatch(r"user-[1-9][0-9]{0,18}",actor or ""):
            return 403,{"ok":False,"error":"Operador inválido"},None
        action,args=route
        try:
            if action=="sync":
                return self._sync(actor,body)
            repo=self.repository_factory()
            if action=="history":
                city,start,end=args
                normalize_range(start,end)
                return 200,{"ok":True,"history":repo.history(city,start,end),
                            "source":"supabase","complete_six_tab_analysis":False},None
            if action=="preview":
                run_id,city,category,page=args
                return 200,repo.preview(run_id,city,category,page),None
        except LiveSyncError as err:
            return err.status,{"ok":False,"code":err.code,"error":str(err)},None
        except ValueError as err:
            return 400,{"ok":False,"code":"invalid_date","error":str(err)},None
        except Exception as err:
            LOG.warning("Imperium Supabase sync error=%s",type(err).__name__)
            return 503,{"ok":False,"code":"unexpected_error",
                        "error":"Não foi possível completar a sincronização com o Supabase"},None
        return 404,{"ok":False,"error":"Rota não encontrada"},None

    def _sync(self,actor,body):
        if not isinstance(body,dict) or set(body)!={"city","start","end"}:
            return 400,{"ok":False,"code":"invalid_parameters",
                        "error":"Informe cidade, data inicial e final"},None
        city,start,end=body.get("city"),body.get("start"),body.get("end")
        if city not in ALLOWED_PROFILES:
            return 409,{"ok":False,"code":"city_not_homologated",
                        "error":"Consulta DataSnap ainda não homologada nesta praça"},None
        normalize_range(start,end)
        if not self.busy.acquire(blocking=False):
            return 409,{"ok":False,"code":"imperium_busy",
                        "error":"Já existe uma consulta DataSnap em andamento"},None
        try:
            repo=self.repository_factory()
            # Fail before expensive DataSnap query when the Supabase schema is missing.
            repo.ensure_ready()
            data=self.fetcher(start,end,profile=city,partner_id=ALLOWED_PROFILES[city],
                              credential_path=Path(r"C:\DominiumMain\config\credentials.dat"))
            structured,counts,digest=prepare_snapshot(data,city)
            result=repo.store(city,start,end,actor,structured,counts,digest)
            return (200 if result["reused"] else 201),result,None
        finally:
            self.busy.release()
