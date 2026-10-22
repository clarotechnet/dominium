"""Read-only Atlas x Imperium reconciliation. Never infer current custody from movements.

This module is intentionally independent of web authentication and Atlas transport.
Callers supply trusted read-only providers; the providers never write to either system.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable

MAX_SERIALS = 500
IMPERIUM_BATCH_SIZE = 20
SERIAL_PATTERN = re.compile(r"[A-Z0-9._/-]{4,50}\Z")
SUPPORTED_PROFILES = frozenset(("natal", "fortaleza", "mossoro", "recife"))
SUPPORTED_MODES = frozenset(("analitico", "sintetico"))


def normalize_serials(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        candidates = re.split(r"[,;\s]+", value.strip())
    elif isinstance(value, list) and all(isinstance(x, str) for x in value):
        candidates = value
    else:
        raise ValueError("Informe uma lista ou texto de seriais")
    result: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        serial = raw.strip().upper()
        if not serial:
            continue
        if not SERIAL_PATTERN.fullmatch(serial):
            raise ValueError("Serial invalido na lista")
        if serial not in seen:
            result.append(serial)
            seen.add(serial)
        if len(result) > MAX_SERIALS:
            raise ValueError("Limite de 500 seriais por trabalho")
    if not result:
        raise ValueError("Informe pelo menos um serial")
    return result


def _txt(value: Any) -> str:
    return str(value or "").strip()


def _contract(value: Any) -> str:
    candidate = _txt(value)
    return candidate if candidate.isdigit() else ""


def _current_contract(source: dict) -> str:
    """Trust ONLY explicitly verified current contract, never old movements."""
    if source.get("current_contract_verified") is True:
        return _contract(source.get("current_contract"))
    return ""


def _current_owner(source: dict) -> str:
    if source.get("current_owner_verified") is True:
        return _txt(source.get("current_owner_id")).upper()
    return ""


def classify_pair(serial: str, imperium: dict | None, atlas: dict | None) -> dict:
    """Return conservative results: insufficient evidence cannot become a mismatch."""
    result = {
        "serial": serial,
        "situacao": "inconclusivo",
        "motivos": [],
        "atlas": None,
        "imperium": None,
        "evidencias": [],
        "alertas": [],
    }
    if not isinstance(imperium, dict):
        result["motivos"].append("imperium_sem_resposta")
        return result

    ds = imperium.get("datasnap")
    live = imperium.get("live") or {}
    result["imperium"] = {
        "movimentacoes": (ds or {}).get("count") if isinstance(ds, dict) else None,
        "ultima_localizacao_nao_confirmada": (imperium.get("last_destination") or {}).get("stock_name"),
        "posse_atual_confirmada": live.get("verified") is True and live.get("found") is True,
        "tecnico": (live.get("owner") or {}).get("technician_name") if isinstance(live.get("owner"), dict) else None,
    }
    if not isinstance(atlas, dict):
        result["motivos"].append("atlas_nao_consultado")
        return result

    record = atlas.get("resultado") if isinstance(atlas.get("resultado"), dict) else atlas
    ok = record.get("ok", atlas.get("ok"))
    result["atlas"] = {
        "estado": record.get("estado"),
        "localizacao": record.get("localizacao"),
        "contrato_historico": record.get("numero_contrato"),
        "ultima_alteracao": record.get("data_alteracao"),
        "parcial": record.get("partial") is True,
    }

    if ok is False:
        result["motivos"].append("atlas_consulta_falhou")
        return result
    if not isinstance(ds, dict) or ds.get("verified") is not True:
        result["motivos"].append("imperium_historico_nao_confirmado")
        return result
    if record.get("partial") is True:
        result["motivos"].append("atlas_historico_parcial")
        return result
    if record.get("serial_encontrado") is False:
        result["motivos"].append("atlas_identidade_nao_confirmada")
        return result

    # Historical discrepancies are REVIEW SIGNALS, never custody evidence.
    atlas_contract = _contract(record.get("numero_contrato"))
    moves = ds.get("movements", [])
    if isinstance(moves, list) and moves:
        candidates = [row for row in moves if isinstance(row, dict)]
        if candidates:
            def movement_id(row):
                try:
                    return int(row.get("Id") or 0)
                except (TypeError, ValueError):
                    return 0
            last = max(candidates, key=movement_id)
            movement_contract = _contract(last.get("Contrato"))
            if atlas_contract and movement_contract and atlas_contract != movement_contract:
                result["alertas"].append("contratos_historicos_diferentes_revisar_datas")
    if _txt(record.get("estado")).upper() == "SUSPEITO":
        result["alertas"].append("atlas_sinaliza_suspeito_exige_analise_humana")

    # Only comparable values with explicit current verification can assert a match.
    ic, ac = _current_contract(imperium), _current_contract(record)
    io, ao = _current_owner(imperium), _current_owner(record)
    if ic and ac:
        same = ic == ac
        result["evidencias"].append({"campo": "contrato_atual_confirmado", "coincide": same})
        if not same:
            result["situacao"] = "divergente"
            result["motivos"].append("contratos_atuais_confirmados_divergentes")
    if io and ao:
        same = io == ao
        result["evidencias"].append({"campo": "responsavel_atual_confirmado", "coincide": same})
        if not same:
            result["situacao"] = "divergente"
            result["motivos"].append("responsaveis_atuais_confirmados_divergentes")
    if result["situacao"] != "divergente" and result["evidencias"]:
        result["situacao"] = "convergente"
        result["motivos"].append("fontes_atuais_confirmadas_coincidem")
    if not result["evidencias"]:
        result["motivos"].append("sem_campos_atuais_equivalentes_confirmados")
    if result["alertas"] and result["situacao"] != "divergente":
        result["situacao"] = "revisao"
    return result


def run_confront(
    serials: str | list[str],
    *,
    profile: str,
    mode: str,
    imperium_query: Callable[[tuple], dict],
    atlas_query: Callable[[str], dict] | None = None,
) -> dict:
    """Execute bounded read-only batches, retaining partial results and failures."""
    if profile not in SUPPORTED_PROFILES:
        raise ValueError("Praca invalida")
    if mode not in SUPPORTED_MODES:
        raise ValueError("Modo invalido")
    targets = normalize_serials(serials)
    rows = []
    for start in range(0, len(targets), IMPERIUM_BATCH_SIZE):
        group = targets[start:start + IMPERIUM_BATCH_SIZE]
        try:
            reply = imperium_query((group, mode, profile))
            if not isinstance(reply, dict) or reply.get("ok") is not True:
                raise ValueError("Consulta Imperium nao confirmada")
            fetched = {
                _txt(item.get("serial")).upper(): item
                for item in reply.get("results", [])
                if isinstance(item, dict) and _txt(item.get("serial")).upper() in group
            }
        except Exception:  # Isolate a provider failure from remaining read-only batches.
            fetched = {}

        for serial in group:
            atlas = None
            if atlas_query is not None:
                try:
                    atlas = atlas_query(serial)
                except Exception:  # One failed Atlas serial must not abort all others.
                    atlas = {"ok": False, "error": "consulta_atlas_indisponivel"}
            rows.append(classify_pair(serial, fetched.get(serial), atlas))
    counts = Counter(row["situacao"] for row in rows)
    return {
        "ok": True,
        "profile": profile,
        "mode": mode,
        "total": len(rows),
        "atlas_integrado": atlas_query is not None,
        "resumo": {k: counts.get(k, 0) for k in ("convergente", "divergente", "revisao", "inconclusivo")},
        "resultados": rows,
        "somente_leitura": True,
    }
