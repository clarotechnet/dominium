"""Stage 3: verified read-only Atlas lookups, resumable in Dominium Supabase.

Uses the existing authorized localhost BotDMV queue and the per-serial
'treatment_items.evidencia.atlas_video' JSONB field, so no new migration.

Never interpret Atlas history, an old location or DataSnap movements as
proof of current physical stock. A pending/uncertain Atlas queue must never
be submitted again automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from imperium_supabase_live import LiveSyncError, SupabasePeriodStore
from imperium_serial_treatment import (
    RUN_ID, SerialTreatmentService, TREATMENTS, SERIAL_WRITE_LOCK,
)

LOG = logging.getLogger(__name__)
ROOT = "/api/stock/analyses/imperium/atlas-video"
CITY = "natal"  # bridge validated only for Natal in this workflow
TERMINAL = frozenset(("verificado", "parcial", "nao_confirmado",
                      "formato_nao_suportado", "erro_consulta"))
ATLAS_FIELDS = (
    "estado", "operacao", "tipo_localizacao", "localizacao",
    "data_alteracao", "numero_contrato", "modelo_equipamento",
)


def route_for(method: str, target: str):
    if method not in ("GET", "POST") or not isinstance(target, str) or len(target) > 215:
        return None
    if any(value in target for value in ("#", "%", "//")):
        return None
    url = urlsplit(target)
    if url.scheme or url.netloc or url.fragment:
        return None
    if method == "POST":
        return ("next", None) if url.path == ROOT + "/next" and not url.query else None
    if url.path != ROOT + "/status":
        return None
    try:
        q = parse_qs(url.query, strict_parsing=True)
    except ValueError:
        return None
    if set(q) != {"city", "run"} or any(len(v) != 1 for v in q.values()):
        return None
    city, run = q["city"][0], q["run"][0]
    if city not in ("natal", "mossoro", "recife") or not RUN_ID.fullmatch(run):
        return None
    return ("status", (city, run))


def _clean_text(value, max_length=160) -> str:
    return str(value if value is not None else "").strip()[:max_length]


def _utc_time() -> str:
    return datetime.now(timezone.utc).isoformat()


class AtlasVideoService:
    def __init__(self, repository_factory=None, bridge_factory=None):
        self.repository_factory = repository_factory or SupabasePeriodStore
        if bridge_factory is None:
            from atlas_bridge_client import AtlasBridgeClient
            bridge_factory = AtlasBridgeClient
        self.bridge_factory = bridge_factory
        self.lock = SERIAL_WRITE_LOCK

    def handle(self, method, target, actor, body=None):
        route = route_for(method, target)
        if route is None:
            return 404, {"ok": False, "error": "Rota Atlas não permitida"}, None
        if not re.fullmatch(r"user-[1-9][0-9]{0,18}", actor or ""):
            return 403, {"ok": False, "error": "Operador não identificado"}, None
        action, args = route
        try:
            repo = self.repository_factory()
            repo.ensure_ready()
            if action == "status":
                city, run = args
                source = SerialTreatmentService._load_source(repo, city, run)
                saved = SerialTreatmentService._saved(repo, run)
                return 200, self._status(source, saved), None
            if action == "next":
                return 200, self._next(repo, actor, body), None
        except LiveSyncError as error:
            return error.status, {"ok": False, "code": error.code, "error": str(error)}, None
        except Exception as error:
            LOG.warning("Atlas video reconciliation failed type=%s", type(error).__name__)
            return 503, {"ok": False, "code": "atlas_unavailable",
                         "error": "Consulta Atlas indisponível, nenhum resultado foi inferido"}, None
        return 404, {"ok": False, "error": "Rota não encontrada"}, None

    @staticmethod
    def _atlas_of(saved_item):
        evidence = saved_item.get("evidencia") if isinstance(saved_item, dict) else None
        atlas = evidence.get("atlas_video") if isinstance(evidence, dict) else None
        return atlas if isinstance(atlas, dict) else {}

    @classmethod
    def _status(cls, source, saved):
        counts = {
            "total": len(source["serials"]),
            "tratados_imperium": sum(x["serial"] in saved for x in source["serials"]),
            "atlas_verificados": 0, "atlas_parciais": 0,
            "atlas_nao_confirmados": 0, "atlas_aguardando": 0,
            "atlas_fila": 0, "atlas_submissao_incerta": 0,
            "atlas_erros": 0, "atlas_formatos_pendentes": 0,
            "aguardando_tratativa_imperium": 0,
        }
        out = []
        for row in source["serials"]:
            serial = row["serial"]
            existing = saved.get(serial)
            evidence = cls._atlas_of(existing)
            state = evidence.get("status") or ("aguardando" if existing
                                                else "aguardando_tratativa")
            increment = {
                "verificado": "atlas_verificados",
                "parcial": "atlas_parciais",
                "nao_confirmado": "atlas_nao_confirmados",
                "aguardando": "atlas_aguardando",
                "queued": "atlas_fila",
                "submitting": "atlas_submissao_incerta",
                "submission_uncertain": "atlas_submissao_incerta",
                "erro_consulta": "atlas_erros",
                "formato_nao_suportado": "atlas_formatos_pendentes",
                "aguardando_tratativa": "aguardando_tratativa_imperium",
            }.get(state)
            if increment:
                counts[increment] += 1
            out.append({
                "serial": serial,
                "modelo_imperium": _clean_text(row.get("equipamento")),
                "estado_atlas": _clean_text(evidence.get("estado")),
                "operacao_atlas": _clean_text(evidence.get("operacao")),
                "tipo_localizacao_atlas": _clean_text(evidence.get("tipo_localizacao")),
                "localizacao_atlas": _clean_text(evidence.get("localizacao")),
                "contrato_atlas": _clean_text(evidence.get("numero_contrato")),
                "data_alteracao_atlas": _clean_text(evidence.get("data_alteracao")),
                "situacao_atlas": state,
                "fonte": "Atlas via ponte local autenticada" if evidence else "Aguardando",
                "localizacao_atual_comprovada": False,
                "observacao": _clean_text(evidence.get("observacao")),
            })
        done = (counts["atlas_verificados"] + counts["atlas_parciais"] +
                counts["atlas_nao_confirmados"] + counts["atlas_erros"] +
                counts["atlas_formatos_pendentes"])
        return {
            "ok": True, "city": source["city"], "run": source["run"],
            "counts": counts, "atlas_finalizados": done,
            "atlas_pendentes": counts["total"] - done,
            "atlas_protocolo_homologado": source["city"] == CITY,
            "analise_video_seis_abas_completa": False,
            "aviso": "A posição informada pelo Atlas é uma evidência histórica/operacional; não comprova por si só estoque físico ou baixa",
            "rows": out,
        }

    @staticmethod
    def _save(repo, run, serial, original, atlas):
        evidence = dict(original.get("evidencia") or {})
        evidence["atlas_video"] = atlas
        patched = repo.call(TREATMENTS, "PATCH", query={
            "consulta_id": "eq." + run, "serial": "eq." + serial,
        }, body={"evidencia": evidence})
        if (not isinstance(patched, list) or len(patched) != 1 or
                patched[0].get("serial") != serial):
            raise LiveSyncError(502, "atlas_write_not_confirmed",
                                "Supabase não confirmou a evidência Atlas")
        return dict(patched[0])

    @staticmethod
    def _capture_result(data, expected_serial):
        if not isinstance(data, dict) or data.get("ok") is not True:
            return {
                "status": "erro_consulta",
                "observacao": "Consulta Atlas não foi confirmada; não equivale a serial ausente",
            }
        result = data.get("resultado") or {}
        if not isinstance(result, dict):
            raise LiveSyncError(502, "atlas_result_invalid", "Atlas retornou dados inválidos")
        # Defense in depth: even a faulty bridge stub must never associate the
        # Atlas location or contract of a different serial with this record.
        delivered = _clean_text(result.get("serial_consultado"), 100).upper()
        if delivered != expected_serial:
            raise LiveSyncError(502, "atlas_serial_mismatch",
                                "Atlas retornou evidência de outro serial; nenhum dado foi salvo")
        envelope_serial = _clean_text(data.get("serial"), 100).upper()
        if envelope_serial and envelope_serial != expected_serial:
            raise LiveSyncError(502, "atlas_serial_mismatch",
                                "Identificador Atlas divergente; nenhum dado foi salvo")
        status = ("parcial" if result.get("partial") is True else
                  "nao_confirmado" if result.get("serial_encontrado") is not True else "verificado")
        evidence = {
            "status": status,
            "confirmado_em": _utc_time(),
            "serial_encontrado": result.get("serial_encontrado") is True,
            "resposta_parcial": result.get("partial") is True,
            "observacao": (
                "Resultado parcial; requer conferência" if status == "parcial" else
                "Identidade não comprovada no Atlas" if status == "nao_confirmado" else
                "Consulta Atlas por serial confirmada; estoque físico não verificado"
            ),
        }
        for field in ATLAS_FIELDS:
            evidence[field] = _clean_text(result.get(field))
        return evidence

    def _next(self, repo, actor, body):
        if not isinstance(body, dict) or set(body) != {"city", "run"}:
            raise LiveSyncError(400, "atlas_parameters", "Informe cidade e execução salva")
        city, run = body["city"], body["run"]
        if city != CITY:
            raise LiveSyncError(409, "atlas_city_unverified",
                                "Conferência Atlas desta etapa está homologada apenas para Natal")
        if not RUN_ID.fullmatch(str(run)):
            raise LiveSyncError(400, "atlas_run_invalid", "Execução inválida")
        if not self.lock.acquire(blocking=False):
            raise LiveSyncError(409, "atlas_busy", "Outra tratativa de serial está em andamento")
        try:
            source = SerialTreatmentService._load_source(repo, city, run)
            saved = SerialTreatmentService._saved(repo, run)
            atlas_client = self.bridge_factory()
            # Always resume known queued work before submitting more.
            selected = next((row for row in source["serials"]
                if row["serial"] in saved and
                self._atlas_of(saved[row["serial"]]).get("status") == "queued"), None)
            if selected is not None:
                serial = selected["serial"]
                original = saved[serial]
                atlas = self._atlas_of(original)
                request_id = _clean_text(atlas.get("request_id"), 100)
                if not request_id:
                    raise LiveSyncError(409, "atlas_queue_uncertain",
                                        "Identificador de fila Atlas ausente; requer auditoria manual")
                try:
                    result = atlas_client.poll_result(request_id, serial)
                except Exception as error:
                    LOG.warning("Atlas queued poll type=%s", type(error).__name__)
                    raise LiveSyncError(503, "atlas_queue_pending",
                        "Consulta Atlas não confirmou o resultado; fila preservada para retomar") from error
                if result is None:
                    state = self._status(source, saved)
                    state["updated"] = {"situacao": "aguardando_atlas"}
                    return state
                final = {**atlas, **self._capture_result(result, serial)}
                self._save(repo, run, serial, original, final)
                saved = SerialTreatmentService._saved(repo, run)
                state = self._status(source, saved)
                state["updated"] = {"situacao": final["status"]}
                return state

            selected = next((row for row in source["serials"] if row["serial"] in saved
                             and not self._atlas_of(saved[row["serial"]]).get("status")), None)
            if selected is None:
                return self._status(source, saved)
            serial = selected["serial"]
            original = saved[serial]
            if not atlas_client.valid_serial(serial):
                self._save(repo, run, serial, original, {
                    "status": "formato_nao_suportado", "confirmado_em": _utc_time(),
                    "observacao": "Formato do serial não aceito pela ponte Atlas; não significa equipamento ausente",
                })
                state = self._status(source, SerialTreatmentService._saved(repo, run))
                state["updated"] = {"situacao": "formato_nao_suportado"}
                return state
            try:
                online = atlas_client.status().get("online") is True
            except Exception:
                online = False
            if not online:
                raise LiveSyncError(503, "atlas_offline",
                                    "Ponte Atlas offline; nenhum serial foi enfileirado")
            self._save(repo, run, serial, original, {
                "status": "submitting", "iniciado_em": _utc_time(),
                "observacao": "Submissão Atlas iniciada; não reenfileirar automaticamente após perda de confirmação",
            })
            try:
                request_id = atlas_client.enqueue(serial)
            except Exception as error:
                LOG.warning("Atlas enqueue uncertain type=%s", type(error).__name__)
                raise LiveSyncError(503, "atlas_submission_uncertain",
                    "Envio à fila Atlas sem confirmação; requer verificar fila antes de qualquer nova tentativa") from error
            new_original = SerialTreatmentService._saved(repo, run)[serial]
            self._save(repo, run, serial, new_original, {
                "status": "queued", "iniciado_em": _utc_time(),
                "request_id": request_id,
                "observacao": "Consulta submetida ao Atlas; aguardando resposta do mesmo requestId",
            })
            state = self._status(source, SerialTreatmentService._saved(repo, run))
            state["updated"] = {"situacao": "aguardando_atlas"}
            return state
        finally:
            self.lock.release()
