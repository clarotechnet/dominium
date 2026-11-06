"""Second, explicit stage of daily Imperium equipment workflow: read-only serial treatment.

Stage 1 is a selected-period TDtmOrdemServico AS_GetRecords snapshot in Supabase.
Stage 2 is triggered by a SEPARATE button; one serial is processed per POST
and persisted before the next request, so pause/retry/browser reload are safe.

The existing TDtmMovEstoque serial history protocol is validated for 12-character
serials in Natal only. Longer ICCIDs are NOT interpreted as missing inventory.
Historical movement is not proof of current physical stock/custody.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from imperium_supabase_live import (
    RUNS, BATCHES, LiveSyncError, SupabasePeriodStore,
)
from stock_report_enrichment import normalize_entry

LOG=logging.getLogger(__name__)
ROOT="/api/stock/analyses/imperium/serial-treatment"
TREATMENTS="dominium_imperium_tratamento_itens"
SUPPORTED_CITY="natal"   # verified 12-character serial protocol; other ports NOT homologated
SERIAL12=re.compile(r"[A-Z0-9]{12}\Z")
RUN_ID=re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z")
RESULT_STATES={"historico_verificado","sem_movimentos","erro_consulta","formato_nao_suportado"}
MAX_SERIALS=1000
MAX_RETRIES=3
XLSX_TYPE="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Serialize writes to shared Supabase treatment evidence across the Imperium
# and Atlas read-only stages in this worker process.
SERIAL_WRITE_LOCK=Lock()


def route_for(method:str,target:str):
    if method not in ("POST","GET") or not isinstance(target,str) or len(target)>210 or any(
        value in target for value in ("#","%","//")
    ):return None
    uri=urlsplit(target)
    if uri.scheme or uri.netloc or uri.fragment:return None
    if method=="POST":
        return ("next",None) if uri.path==ROOT+"/next" and not uri.query else None
    if uri.path not in (ROOT+"/status",ROOT+"/export"):return None
    try:q=parse_qs(uri.query,strict_parsing=True)
    except ValueError:return None
    if set(q)!={"city","run"} or any(len(v)!=1 for v in q.values()):return None
    city,run=q["city"][0],q["run"][0]
    if city not in ("natal","mossoro","recife") or not RUN_ID.fullmatch(run):return None
    return ("status" if uri.path.endswith("/status") else "export"),(city,run)


def _txt(value,maxlength=200):
    return str(value if value is not None else "").strip()[:maxlength]


class SerialTreatmentService:
    def __init__(self,repository_factory=None,consult=None):
        self.repository_factory=repository_factory or SupabasePeriodStore
        # Avoid importing the live DataSnap client until a user starts treatment.
        self.consult=consult
        self.lock=SERIAL_WRITE_LOCK

    def handle(self,method,target,actor,body=None):
        route=route_for(method,target)
        if route is None:return 404,{"ok":False,"error":"Rota de tratativa não permitida"},None
        if not re.fullmatch(r"user-[1-9][0-9]{0,18}",actor or ""):
            return 403,{"ok":False,"error":"Operador inválido"},None
        action,args=route
        try:
            repo=self.repository_factory()
            self._ensure_ready(repo)
            if action=="next":
                return 200,self._next(repo,actor,body),None
            city,run_id=args
            source=self._load_source(repo,city,run_id)
            if action=="status":
                return 200,self._status(repo,source),None
            if action=="export":
                data=self._export(repo,source)
                return 200,data,XLSX_TYPE
        except LiveSyncError as exc:
            return exc.status,{"ok":False,"code":exc.code,"error":str(exc)},None
        except Exception as exc:
            LOG.warning("Erro em tratativa de seriais: %s",type(exc).__name__)
            return 503,{"ok":False,"code":"treatment_unavailable",
                        "error":"Tratativa de seriais temporariamente indisponível"},None
        return 404,{"ok":False,"error":"Rota não encontrada"},None

    @staticmethod
    def _ensure_ready(repo):
        repo.ensure_ready()
        result=repo.call(TREATMENTS,query={"select":"consulta_id","limit":"0"})
        if not isinstance(result,list):
            raise LiveSyncError(503,"missing_treatment_table","Tabela de tratativa não instalada no Supabase")

    @staticmethod
    def _load_source(repo,city,run_id):
        if city not in ("natal","mossoro","recife") or not RUN_ID.fullmatch(str(run_id)):
            raise LiveSyncError(400,"invalid_period","Identificador ou cidade inválidos")
        source=repo.call(RUNS,query={
            "select":"id,cidade,estado,total_seriais,data_inicio,data_fim,criado_em",
            "id":"eq."+run_id,"cidade":"eq."+city,"estado":"eq.concluido","limit":"1",
        })
        if not isinstance(source,list) or len(source)!=1:
            raise LiveSyncError(404,"source_missing","A coleta não está concluída nesta praça")
        meta=source[0]
        declared=int(meta.get("total_seriais") or 0)
        if declared>MAX_SERIALS:
            raise LiveSyncError(413,"too_many_serials",
                "Coleta com mais de 1000 seriais; selecione um período menor")
        batches=repo.call(BATCHES,query={
            "select":"indice_lote,quantidade,registros",
            "consulta_id":"eq."+run_id,"categoria":"eq.seriais_tratados",
            "order":"indice_lote.asc","limit":"1000",
        })
        if not isinstance(batches,list):
            raise LiveSyncError(502,"source_invalid","Lotes de seriais indisponíveis")
        serials=[]
        for index,record in enumerate(batches):
            if record.get("indice_lote")!=index or not isinstance(record.get("registros"),list) or (
                len(record["registros"])!=record.get("quantidade")
            ):
                raise LiveSyncError(502,"source_invalid","Sequência de lotes inconsistente")
            serials.extend(record["registros"])
        if len(serials)!=declared or any(not isinstance(row,dict) for row in serials):
            raise LiveSyncError(502,"source_invalid","Quantidade de seriais da coleta divergente")
        known=set()
        for item in serials:
            serial=_txt(item.get("serial"),100).upper()
            if not serial or serial in known:
                raise LiveSyncError(502,"source_invalid","Seriais inválidos ou repetidos na coleta")
            known.add(serial)
        return {"city":city,"run":run_id,"meta":meta,"serials":serials}

    @staticmethod
    def _saved(repo,run_id):
        results=repo.call(TREATMENTS,query={
            "select":"serial,situacao,evidencia,tentativas,tratado_em",
            "consulta_id":"eq."+run_id,"order":"serial.asc","limit":"1000",
        })
        if not isinstance(results,list):
            raise LiveSyncError(502,"supabase_response","Respostas da tratativa inválidas")
        out={}
        for row in results:
            serial=str(row.get("serial") or "").strip().upper()
            if not serial or serial in out or row.get("situacao") not in RESULT_STATES:
                raise LiveSyncError(502,"supabase_response","Dados inconsistentes na tratativa")
            out[serial]=row
        return out

    @staticmethod
    def _summary(source,saved):
        data=source["serials"]
        valid={row["serial"] for row in data}
        if any(s not in valid for s in saved):
            raise LiveSyncError(502,"treatment_mismatch",
                "A tratativa contém seriais que não pertencem a esta coleta")
        total=len(data)
        done=len(saved)
        counts={
            "total":total,"processados":done,"restantes":total-done,
            "historico_verificado":sum(x["situacao"]=="historico_verificado" for x in saved.values()),
            "sem_movimentos":sum(x["situacao"]=="sem_movimentos" for x in saved.values()),
            "erro_consulta":sum(x["situacao"]=="erro_consulta" for x in saved.values()),
            "formato_nao_suportado":sum(x["situacao"]=="formato_nao_suportado" for x in saved.values()),
        }
        completed=total>0 and done==total
        pending=counts["erro_consulta"]+counts["formato_nao_suportado"]
        return {
            "counts":counts,
            "complete":completed,
            "status":("concluido_com_pendencias" if pending else "concluido") if completed
                     else ("em_tratamento" if done else "nao_iniciado"),
            "download_enabled":completed,
            "six_tab_analysis_complete":False,
        }

    @classmethod
    def _status(cls,repo,source):
        saved=cls._saved(repo,source["run"])
        state=cls._summary(source,saved)
        rows=[]
        for item in source["serials"]:
            serial=item["serial"]
            hit=saved.get(serial)
            evidence=hit.get("evidencia") if hit and isinstance(hit.get("evidencia"),dict) else {}
            rows.append({
                "serial":serial,
                "equipamento":_txt(item.get("equipamento")),
                "grupo":_txt(item.get("grupo"),120),
                "numero_wo":_txt(item.get("numero_wo"),80),
                "contrato":_txt(item.get("contrato"),80),
                "situacao":hit["situacao"] if hit else "aguardando",
                "historico_confirmado":evidence.get("history_verified") is True if hit else None,
                "quantidade_movimentos":evidence.get("movement_count"),
                "ultima_movimentacao":_txt(evidence.get("last_movement"),120),
                "ultimo_estoque_historico":_txt(evidence.get("last_destination_historical"),160),
                "posse_atual_comprovada":evidence.get("current_owner_verified") is True if hit else None,
                "tecnico_atual_comprovado":_txt(evidence.get("current_owner"),160),
                "observacao":_txt(evidence.get("history_error"),160),
            })
        return {"ok":True,"city":source["city"],"run":source["run"],
                **state,"rows":rows}

    def _next(self,repo,actor,body):
        if not isinstance(body,dict) or not set(body) in (
            {"city","run"},{"city","run","retry_errors"}
        ):
            raise LiveSyncError(400,"invalid_parameters","Informe cidade e ID da coleta")
        city,run=body.get("city"),body.get("run")
        if city!=SUPPORTED_CITY:
            raise LiveSyncError(409,"serial_protocol_not_validated",
                "Tratativa individual homologada somente para Natal; as demais praças seguem coletando seriais")
        retry_errors=body.get("retry_errors",False)
        if not isinstance(retry_errors,bool):
            raise LiveSyncError(400,"invalid_parameters","Opção de repetição inválida")
        if not self.lock.acquire(blocking=False):
            raise LiveSyncError(409,"serial_treatment_busy","Outra consulta de serial está em andamento")
        try:
            source=self._load_source(repo,city,run)
            saved=self._saved(repo,run)
            selected=next((row for row in source["serials"]
                           if row["serial"] not in saved),None)
            if selected is None and retry_errors:
                selected=next((row for row in source["serials"]
                               if (current:=saved.get(row["serial"])) is not None and
                               current["situacao"]=="erro_consulta" and
                               int(current.get("tentativas") or 1)<MAX_RETRIES),None)
            if selected is None:
                return self._status(repo,source)
            serial=selected["serial"]
            prior=saved.get(serial)
            attempts=int(prior.get("tentativas") or 0)+1 if prior else 1
            if not SERIAL12.fullmatch(serial):
                situation="formato_nao_suportado"
                evidence={
                    "history_verified":False,"current_owner_verified":False,
                    "history_error":"Este tipo de serial/ICCID não é suportado pela consulta individual de 12 caracteres; não equivale a não encontrado",
                    "source":"imperium_serial_format_unsupported",
                }
            else:
                try:
                    if self.consult is None:
                        from serial_service import consult_serials
                        self.consult=consult_serials
                    fetched=self.consult(([serial],"analitico",city))
                    if not isinstance(fetched,dict) or fetched.get("ok") is not True:
                        raise ValueError("DataSnap sem confirmação")
                    matches=[row for row in fetched.get("results",[]) if
                             isinstance(row,dict) and _txt(row.get("serial"),100).upper()==serial]
                    if len(matches)!=1:
                        raise ValueError("Serial diverge da consulta")
                    evidence=normalize_entry(matches[0])
                    if evidence.get("history_verified") is True:
                        situation=("historico_verificado" if
                                   int(evidence.get("movement_count") or 0)>0 else "sem_movimentos")
                    else:
                        situation="erro_consulta"
                        evidence["history_error"]=_txt(evidence.get("history_error") or
                                                        "Consulta DataSnap não confirmada",160)
                except Exception as exc:
                    LOG.warning("Falha consulta serial (%s)",type(exc).__name__)
                    situation="erro_consulta"
                    evidence={"history_verified":False,"current_owner_verified":False,
                              "history_error":"Consulta individual ao Imperium falhou; não significa serial inexistente",
                              "source":"imperium_datasnap_unconfirmed"}
            # A retry of Imperium historical records must never erase a confirmed
            # Atlas lookup stored in the same JSONB evidence field.
            prior_evidence=(prior or {}).get("evidencia")
            if isinstance(prior_evidence,dict) and isinstance(prior_evidence.get("atlas_video"),dict):
                evidence["atlas_video"]=prior_evidence["atlas_video"]
            row={
                "consulta_id":run,"serial":serial,"situacao":situation,
                "evidencia":evidence,"tentativas":min(attempts,MAX_RETRIES),
                "tratado_por":actor,
                "tratado_em":datetime.now(timezone.utc).isoformat(),
            }
            created=repo.call(TREATMENTS,"POST",body=row,upsert=True)
            if not isinstance(created,list) or len(created)!=1 or created[0].get("situacao")!=situation:
                raise LiveSyncError(502,"treatment_write_failed",
                    "Supabase não confirmou a tratativa deste serial")
            response=self._status(repo,source)
            response["updated"]={"serial":serial,"situacao":situation}
            return response
        finally:
            self.lock.release()

    @classmethod
    def _export(cls,repo,source):
        status=cls._status(repo,source)
        if not status["download_enabled"]:
            raise LiveSyncError(409,"treatment_incomplete",
                "Conclua ou pause/retome todas as consultas individuais antes de exportar")
        records=status["rows"]
        header=[
            "Serial","Equipamento","Grupo","Número W.O","Contrato","Situação",
            "Histórico Confirmado","Qtd. Movimentações","Última Movimentação",
            "Último Estoque Histórico (não confirmado como atual)",
            "Posse Atual Comprovada","Técnico Atual Comprovado","Observação",
        ]
        data=[header]
        pending=[[header[i] for i in range(len(header))]]
        for row in records:
            values=[
                row["serial"],row["equipamento"],row["grupo"],row["numero_wo"],
                row["contrato"],row["situacao"],
                "SIM" if row["historico_confirmado"] is True else "NÃO",
                row["quantidade_movimentos"],row["ultima_movimentacao"],
                row["ultimo_estoque_historico"],
                "SIM" if row["posse_atual_comprovada"] is True else "NÃO CONFIRMADA",
                row["tecnico_atual_comprovado"],row["observacao"],
            ]
            data.append(values)
            if row["situacao"] in ("erro_consulta","formato_nao_suportado"):
                pending.append(values)
        # Third-stage evidence is independent from Imperium movements.
        # Include real Atlas responses when they exist and mark every missing
        # response explicitly. This is NOT the six-tab video final report.
        saved=cls._saved(repo,source["run"])
        atlas_header=[
            "Serial","Equipamento no Imperium","Status de conferência Atlas",
            "Estado Atlas","Operação Atlas","Tipo de localização Atlas",
            "Localização informada Atlas","Data de alteração Atlas",
            "Contrato Atlas","Modelo Atlas","Estoque físico comprovado",
            "Observação / pendência",
        ]
        atlas_data=[atlas_header]
        atlas_pending=[list(atlas_header)]
        for original in records:
            serial=original["serial"]
            item=saved.get(serial,{})
            evid=item.get("evidencia") if isinstance(item,dict) else {}
            atlas=evid.get("atlas_video") if isinstance(evid,dict) else None
            if not isinstance(atlas,dict):
                atlas={}
            state=_txt(atlas.get("status") or "aguardando",50)
            record=[
                serial,original["equipamento"],state,
                _txt(atlas.get("estado")),_txt(atlas.get("operacao")),
                _txt(atlas.get("tipo_localizacao")),
                _txt(atlas.get("localizacao")),
                _txt(atlas.get("data_alteracao")),
                _txt(atlas.get("numero_contrato")),
                _txt(atlas.get("modelo_equipamento")),
                "NÃO VERIFICADO",
                _txt(atlas.get("observacao") or
                    "Aguardando consulta Atlas por equipamento",200),
            ]
            atlas_data.append(record)
            if state!="verificado":
                atlas_pending.append(record)
        # Import lazily: stock_analysis_http imports this module.
        from stock_analysis_http import xlsx
        return xlsx([
            ("Seriais Tratados",data),
            ("Pendencias",pending),
            ("Conferencia Atlas",atlas_data),
            ("Pendencias Atlas",atlas_pending),
        ])
