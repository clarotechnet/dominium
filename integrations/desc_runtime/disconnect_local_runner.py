"""Executa um único job de desconexão recebido do BotDMV no PC local.

O job chega em JSON pela entrada padrão. A consulta ao TOA continua sendo
feita pela extensão do BotDMV; este processo recebe somente o snapshot tipado
da atividade e usa exclusivamente o protocolo direto já implementado no
projeto OLLAMA.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from desc_only_scope import is_disconnection_service
from disconnect_contracts import (
    DisconnectBlocked,
    DisconnectJob,
    DisconnectMessageEvent,
    MovementDirection,
    TOADisconnectSnapshot,
    TOAEquipment,
)
from disconnect_pilot import (
    DirectExecutionPacer,
    DisconnectWorker,
    classify_job,
    job_from_dict,
)
from dominium_disconnect_gateway import ImperiumDominiumDirectGateway
from imperium_api import ImperiumAPI
from operation_scope import ProjectIdentity
from toa_adm_task_splitter import ADMTaskEvidence, find_latest_adm_tasks, validate_adm_task_identity
from adm_allocation import AllocationBlocked, single_os_allocation
from toa_import import TOAOrder, TOAPreview
from toa_live import TOALiveSession
from whatsapp_auto_close import AUTOMATION_PROFILE_RULES, build_automatic_disconnect_plan


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "whatsapp_disconnect_groups.json"
AUDIT_PATH = ROOT / "logs" / "disconnect_local_runner.jsonl"
TECHCAP_RETRY_BLOCKERS = frozenset(
    {
        "toa_snapshot_incomplete",
        "equipment_identity_mismatch",
        "close_409_without_incoming_equipment",
        "close_430_without_outgoing_equipment",
        "equipment_direction_mismatch",
    }
)
WHATSAPP_TECHNICIAN_MAP_PATH = ROOT / "config" / "whatsapp_technicians.json"
PROFILE_RUNTIME = {
    "natal": {
        "port": 212,
        "company": "NATAL / PARNAMIRIM",
        "controller_id": 362032,
        "log_dir": "",
    },
    "fortaleza": {
        "port": 596,
        "company": "FORTALEZA",
        "controller_id": 90321,
        "log_dir": "fortaleza",
    },
    "mossoro": {
        "port": 579,
        "company": "MOSSORÓ",
        "controller_id": 22722,
        "log_dir": "mossoro",
    },
    "recife": {
        "port": 599,
        "company": "RECIFE",
        "controller_id": 15787,
        "log_dir": "recife",
    },
}
PROFILE_LOCATIONS = {
    "natal": ("NATAL", "RN", "59000000"),
    "fortaleza": ("FORTALEZA", "CE", "60000000"),
    "mossoro": ("MOSSORO", "RN", "59600000"),
    "recife": ("RECIFE", "PE", "50000000"),
}


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("direct_protocol_only") is not True:
        raise RuntimeError("direct_protocol_only precisa estar habilitado")
    if float(config.get("minimum_seconds_between_closes", 0)) < 6:
        raise RuntimeError("O intervalo minimo entre baixas deve ser de 6 segundos")
    return config


def health() -> dict[str, Any]:
    config = load_config()
    return {
        "ok": True,
        "transport": "local_windows_runner",
        "project_id": "IMPERIUM_OLLAMA",
        "profile_key": "natal",
        "city": "NATAL",
        "direct_protocol_only": True,
        "minimum_seconds_between_closes": float(
            config["minimum_seconds_between_closes"]
        ),
        "execution_enabled": config.get("external_execution_enabled") is True,
        "auto_create_missing_os": config.get("auto_create_missing_os") is True,
        "auto_create_missing_os_profiles": list(
            config.get("auto_create_missing_os_profiles") or ()
        ),
        "credentials_present": (ROOT / "config" / "credentials.dat").is_file(),
    }


def _append_audit(job: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    snapshot = job.get("toa_snapshot")
    if not isinstance(snapshot, Mapping):
        snapshot = {}

    def serials(field: str) -> list[str]:
        values = snapshot.get(field)
        if not isinstance(values, list):
            return []
        return [
            str(item.get("serial") or "").strip().upper()
            for item in values
            if isinstance(item, Mapping) and str(item.get("serial") or "").strip()
        ]

    record = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "job_id": str(job.get("job_id") or ""),
        "message_id": str(job.get("message_id") or ""),
        "contract": str(job.get("contract") or ""),
        "requested_close_code": str(job.get("requested_close_code") or ""),
        "profile_key": str(job.get("profile_key") or ""),
        "city": str(job.get("city") or ""),
        "activity_id": str(job.get("activity_id") or ""),
        "direction_source": str(snapshot.get("direction_source") or ""),
        "incoming_serials": serials("installed_equipments")
        + serials("added_equipments"),
        "outgoing_serials": serials("removed_equipments"),
        "result_equipment": result.get("equipment"),
        "state": str(result.get("state") or ""),
        "blockers": list(result.get("blockers") or ()),
        "write_calls": int(result.get("write_calls") or 0),
        "os_numbers": list(result.get("os_numbers") or ()),
        "batch": list(result.get("batch") or ()),
    }
    with AUDIT_PATH.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def _disarm_after_write(job_id: str, state: str) -> None:
    config = load_config()
    if config.get("pause_after_job") is not True:
        return
    config["external_execution_enabled"] = False
    config["worker_autostart"] = False
    config["last_worker_job_id"] = job_id
    config["last_worker_state"] = state
    config["last_worker_finished_at"] = dt.datetime.now(
        dt.timezone.utc
    ).isoformat()
    temporary = CONFIG_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, CONFIG_PATH)


def _job_from_techcap(job: DisconnectJob) -> DisconnectJob:
    """Refresh an incomplete extension snapshot with a read-only Techcap lookup."""
    live_session = TOALiveSession(ROOT)
    lookup = live_session.lookup_contract(job.contract)
    plan = build_automatic_disconnect_plan(
        job.contract,
        lookup,
        profile_key=job.profile_key,
    )
    expected_city = str(AUTOMATION_PROFILE_RULES[plan.profile_key]["city"])
    if plan.profile_key != job.profile_key or expected_city != job.city:
        raise DisconnectBlocked(
            ("profile_scope_mismatch", "city_scope_mismatch"),
            stage="techcap_fallback",
        )

    event = DisconnectMessageEvent(
        message_id=job.message_id,
        chat_id=job.chat_id,
        sender_id=job.sender_id,
        received_at=job.received_at,
        raw_text="",
        contract=plan.contract,
        requested_close_code=plan.close_code,
        import_origin=plan.import_origin,
        city=expected_city,
        profile_key=plan.profile_key,
        observation=job.observation,
    )
    installed = tuple(
        TOAEquipment(
            serial=item["serial"],
            equipment_type=item["type"],
            direction=MovementDirection.INCOMING,
        )
        for item in plan.installed_equipment
    )
    removed = tuple(
        TOAEquipment(
            serial=item["serial"],
            equipment_type=item["type"],
            direction=MovementDirection.OUTGOING,
        )
        for item in plan.removed_equipment
    )
    snapshot = TOADisconnectSnapshot.create(
        profile_key=plan.profile_key,
        city=expected_city,
        contract=plan.contract,
        activity_id=plan.activity_id,
        activity_type=plan.activity_type,
        activity_status=plan.activity_status,
        installed_equipments=installed,
        removed_equipments=removed,
        materials=plan.blocking_materials,
        current_close_code=None,
        source_reference="techcap_live:exact_activity",
        job_id=job.job_id,
        message_id=job.message_id,
        group_id=job.chat_id,
        processing_id=job.message_id,
        direction_source="techcap_exact_activity_install_deinstall",
    )
    return DisconnectJob.create(event, snapshot, job_id=job.job_id, ttl_seconds=300)


def _refresh_incomplete_snapshot(job: DisconnectJob) -> DisconnectJob:
    blockers = set(classify_job(job))
    if not blockers.intersection(TECHCAP_RETRY_BLOCKERS):
        return job
    # Nunca substitua a direcao/serial capturados na atividade exata por uma
    # segunda leitura. O fallback Techcap pode enxergar o equipamento atual do
    # cliente e confundi-lo com o item de DESINSTALACAO. Se o snapshot tipado
    # estiver incompleto, a fila persistente consulta a atividade novamente.
    raise DisconnectBlocked(
        tuple(sorted(blockers | {"typed_toa_snapshot_required", "operation_blocked"})),
        stage="typed_toa_snapshot_required",
    )


def _normalized_name(value: object) -> str:
    return " ".join(
        unicodedata.normalize("NFD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
        .split()
    )


def _normalized_whatsapp_id(value: object) -> str:
    return re.sub(r":\d+(?=@)", "", str(value or "").strip()).lower()


def _mapped_whatsapp_entry(job: DisconnectJob) -> dict[str, Any]:
    try:
        payload = json.loads(
            WHATSAPP_TECHNICIAN_MAP_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    sender_id = _normalized_whatsapp_id(getattr(job, "sender_id", ""))
    if not sender_id:
        return {}
    for item in payload.get("technicians", ()):
        if not isinstance(item, Mapping):
            continue
        identifiers = {
            _normalized_whatsapp_id(value)
            for value in (
                list(item.get("whatsapp_ids") or ())
                + [item.get("whatsapp_id")]
            )
            if _normalized_whatsapp_id(value)
        }
        profiles = {
            str(value).strip().lower()
            for value in item.get("profiles", ())
            if str(value).strip()
        }
        if sender_id not in identifiers or (
            profiles and job.profile_key not in profiles
        ):
            continue
        return dict(item)
    return {}


def _assert_desc_group_scope(job: DisconnectJob) -> None:
    """Use the authorized group, not the OS service label, as DESC scope."""
    rule = AUTOMATION_PROFILE_RULES.get(
        str(getattr(job, "profile_key", "") or "").strip().lower()
    )
    if not rule or str(getattr(job, "chat_id", "") or "") not in rule["chat_ids"]:
        raise DisconnectBlocked(
            ("desc_group_not_authorized", "operation_blocked"),
            stage="desc_sector_scope",
        )
    if str(getattr(job, "city", "") or "").strip().upper() != rule["city"]:
        raise DisconnectBlocked(
            ("city_scope_mismatch", "operation_blocked"),
            stage="desc_sector_scope",
        )


def _assert_desc_technician_sector(job: DisconnectJob) -> None:
    """Fail closed for actual writes by technicians not verified as DESC.

    The group alone does not prove that an arbitrary sender belongs to DESC.
    An explicit department/sector flag or the registered DESC technician
    suffix establishes membership. Unknown senders require human mapping.
    """
    _assert_desc_group_scope(job)
    # The exact TOA provider bucket must match the DESC sector before ANY
    # DataSnap write; e.g. NTL-DMV (Adesao) is NOT NTL-DMV_ADM.
    buckets = {
        'natal': {'NTL-DMV_ADM', 'PWM-DMV_ADM'},
        'fortaleza': {'FTZ-DMV_ADM'},
        'recife': {'JCR-DMV_ADM'},
        'mossoro': {'MRO-DMV'},
    }
    reference = str(getattr(job.toa_snapshot, 'source_reference', '') or '')
    match = re.search(r'(?:^|[|])bucket=([A-Z0-9_-]+)(?:[|]|$)', reference)
    bucket = match.group(1) if match else ''
    if bucket not in buckets.get(job.profile_key, set()):
        raise DisconnectBlocked(
            ('toa_bucket_not_confirmed_as_desc', 'operation_blocked'),
            stage='desc_sector_scope',
        )
    mapped = _mapped_whatsapp_entry(job)
    label = " ".join(str(mapped.get("name") or "").upper().split())
    department = " ".join(
        str(mapped.get("department") or mapped.get("sector") or "").upper().split()
    )
    if department not in ("DESC", "DESCONEXAO", "DESCONEXÃO") and not label.endswith(" DESC"):
        raise DisconnectBlocked(
            ("desc_sector_technician_not_verified", "operation_blocked"),
            stage="desc_sector_scope",
        )
    if not mapped.get("installer_id") and not mapped.get("imperium_technician_id"):
        raise DisconnectBlocked(
            ("desc_sector_installer_id_missing", "operation_blocked"),
            stage="desc_sector_scope",
        )


def _mapped_whatsapp_technician(job: DisconnectJob) -> tuple[str, str, int]:
    item = _mapped_whatsapp_entry(job)
    try:
        installer_id = max(
            0,
            int(
                item.get("installer_id")
                or item.get("imperium_technician_id")
                or 0
            ),
        )
    except (TypeError, ValueError):
        installer_id = 0
    return (
        str(item.get("login") or "").strip().upper(),
        " ".join(str(item.get("name") or "").split()).upper(),
        installer_id,
    )


def _mapped_creation_service(job: DisconnectJob) -> str:
    item = _mapped_whatsapp_entry(job)
    return " ".join(str(item.get("creation_service") or "").split()).upper()


def _technician_hints(job: DisconnectJob) -> tuple[str, str]:
    login = str(job.toa_snapshot.technician_login).strip().upper()
    name = " ".join(job.toa_snapshot.technician_name.split()).upper()
    if login and name:
        return login, name
    mapped_login, mapped_name, _mapped_installer_id = (
        _mapped_whatsapp_technician(job)
    )
    return login or mapped_login, name or mapped_name


def _name_tokens(value: object) -> frozenset[str]:
    ignored = {"DA", "DAS", "DE", "DO", "DOS", "E", "DESC"}
    return frozenset(
        token for token in _normalized_name(value).split() if token not in ignored
    )


def _native_technician_score(wanted: str, candidate: str) -> int:
    normalized_candidate = _normalized_name(candidate)
    if "DESC" not in normalized_candidate.split():
        return 0
    wanted_tokens = _name_tokens(wanted)
    candidate_tokens = _name_tokens(candidate)
    if len(wanted_tokens) < 2 or len(candidate_tokens) < 2:
        return 0
    if wanted_tokens == candidate_tokens:
        return 1000 + len(candidate_tokens)
    if candidate_tokens.issubset(wanted_tokens):
        return 500 + len(candidate_tokens)
    if wanted_tokens.issubset(candidate_tokens):
        return 400 + len(wanted_tokens)
    return 0



def _message_technician_name(job: DisconnectJob) -> str:
    observation = str(getattr(job, "observation", "") or "")
    if not observation:
        return ""
    match = re.search(
        r"(?i)\bT[EÉ]CNICO\s*:\s*(.+?)(?=\s+(?:CONTRATO|NOME|END|ENDERECO|ENDEREÇO|AGENDA|TEL|TELEFONE|OBS|OBSERVACAO|OBSERVAÇÃO)\s*:|$)",
        observation,
    )
    if not match:
        return ""
    return " ".join(match.group(1).split()).strip()


def _unique_native_technician_match(
    wanted: str,
    stock_technicians: list[Mapping[str, Any]],
) -> dict[str, Any] | None:
    wanted = " ".join(str(wanted or "").split()).strip()
    if not wanted:
        return None

    def distinct_by_installer(items: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[int, dict[str, Any]] = {}
        for item in items:
            try:
                installer_id = int(item.get("installer_id") or 0)
            except (TypeError, ValueError):
                installer_id = 0
            if installer_id <= 0:
                continue
            unique.setdefault(installer_id, dict(item))
        return list(unique.values())

    exact = distinct_by_installer(
        [
            item
            for item in stock_technicians
            if _normalized_name(item.get("technician_name"))
            == _normalized_name(wanted)
        ]
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None

    scored: list[tuple[int, Mapping[str, Any]]] = []
    for item in stock_technicians:
        candidate_name = str(item.get("technician_name") or "").strip()
        score = _native_technician_score(wanted, candidate_name)
        if score > 0:
            scored.append((score, item))
    if not scored:
        return None
    best_score = max(score for score, _item in scored)
    best = distinct_by_installer(
        [item for score, item in scored if score == best_score]
    )
    return best[0] if len(best) == 1 else None


def _persist_auto_whatsapp_mapping(
    job: DisconnectJob,
    technician: Mapping[str, Any],
) -> bool:
    sender_id = _normalized_whatsapp_id(getattr(job, "sender_id", ""))
    profile_key = str(getattr(job, "profile_key", "") or "").strip().lower()
    technician_name = " ".join(
        str(technician.get("technician_name") or "").split()
    ).upper()
    try:
        installer_id = int(technician.get("installer_id") or 0)
    except (TypeError, ValueError):
        installer_id = 0
    if not sender_id or not profile_key or installer_id <= 0 or not technician_name:
        return False

    try:
        payload = json.loads(
            WHATSAPP_TECHNICIAN_MAP_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        payload = {"schema_version": 1, "technicians": []}
    if not isinstance(payload, dict):
        payload = {"schema_version": 1, "technicians": []}
    technicians = payload.get("technicians")
    if not isinstance(technicians, list):
        technicians = []
        payload["technicians"] = technicians
    payload.setdefault("schema_version", 1)

    target: dict[str, Any] | None = None
    for item in technicians:
        if not isinstance(item, dict):
            continue
        ids = {
            _normalized_whatsapp_id(value)
            for value in (
                list(item.get("whatsapp_ids") or ())
                + [item.get("whatsapp_id")]
            )
            if _normalized_whatsapp_id(value)
        }
        try:
            current_installer_id = int(
                item.get("installer_id")
                or item.get("imperium_technician_id")
                or 0
            )
        except (TypeError, ValueError):
            current_installer_id = 0
        if sender_id in ids:
            if current_installer_id not in (0, installer_id):
                return False
            target = item
            break
        if current_installer_id == installer_id and target is None:
            target = item

    if target is None:
        target = {
            "whatsapp_ids": [],
            "name": technician_name,
            "installer_id": installer_id,
            "profiles": [],
            "auto_mapped": True,
        }
        technicians.append(target)

    ids = [
        _normalized_whatsapp_id(value)
        for value in (
            list(target.get("whatsapp_ids") or ())
            + [target.get("whatsapp_id")]
        )
        if _normalized_whatsapp_id(value)
    ]
    if sender_id not in ids:
        ids.append(sender_id)
    target["whatsapp_ids"] = list(dict.fromkeys(ids))
    target.pop("whatsapp_id", None)
    target["name"] = technician_name
    target["installer_id"] = installer_id
    profiles = [
        str(value).strip().lower()
        for value in target.get("profiles", ())
        if str(value).strip()
    ]
    if profile_key not in profiles:
        profiles.append(profile_key)
    target["profiles"] = list(dict.fromkeys(profiles))
    target["auto_mapped"] = bool(target.get("auto_mapped", True))

    WHATSAPP_TECHNICIAN_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = WHATSAPP_TECHNICIAN_MAP_PATH.with_name(
        WHATSAPP_TECHNICIAN_MAP_PATH.name + ".tmp"
    )
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, WHATSAPP_TECHNICIAN_MAP_PATH)
    return True


def _resolve_native_technician(
    api: ImperiumAPI,
    job: DisconnectJob,
) -> dict[str, Any]:
    stock_technicians = api.list_stock_technicians()

    # 1. Prioridade: Tecnico mapeado do remetente do WhatsApp
    _mapped_login, mapped_name, mapped_installer_id = (
        _mapped_whatsapp_technician(job)
    )
    if mapped_name:
        if mapped_installer_id:
            for item in stock_technicians:
                if int(item.get("installer_id") or 0) == mapped_installer_id:
                    return dict(item)
        best_match = None
        best_score = 0
        for item in stock_technicians:
            candidate_name = str(item.get("technician_name") or "").strip()
            score = _native_technician_score(mapped_name, candidate_name)
            if score > best_score:
                best_score = score
                best_match = item
        if best_match:
            return dict(best_match)

    # 2. Auto-vinculo: remetente desconhecido + "Tecnico: NOME" na mensagem.
    # So persiste quando existe um unico installer_id compativel naquela base.
    message_name = _message_technician_name(job)
    if message_name:
        auto_match = _unique_native_technician_match(
            message_name,
            stock_technicians,
        )
        if auto_match:
            _persist_auto_whatsapp_mapping(job, auto_match)
            return dict(auto_match)

    # 3. Fallback: Tecnico identificado no TOA (se o remetente nao estiver mapeado)
    toa_name = str(getattr(job.toa_snapshot, "technician_name", "") or "").strip()
    if toa_name:
        toa_match = _unique_native_technician_match(
            toa_name,
            stock_technicians,
        )
        if toa_match:
            return dict(toa_match)

    raise DisconnectBlocked(
        (
            "whatsapp_sender_technician_not_mapped",
            "operation_blocked",
        ),
        stage="create_missing_os",
    )


def _auto_create_enabled(config: Mapping[str, Any], profile_key: str) -> bool:
    if config.get("auto_create_missing_os") is not True:
        return False
    profiles = {
        str(value).strip().lower()
        for value in config.get("auto_create_missing_os_profiles", ())
        if str(value).strip()
    }
    return not profiles or str(profile_key).strip().lower() in profiles


def _missing_order_service(job: DisconnectJob) -> str:
    if job.requested_close_code == "409":
        return "43 - ADESAO - INSTALAR PONTO VIRTUA"
    if job.requested_close_code == "706":
        return "ENVIO DE CHIP VIA TECNICO"
    if job.requested_close_code == "430":
        outgoing = job.toa_snapshot.removed_equipments
        normalized_types = {
            ImperiumDominiumDirectGateway._normalized(item.equipment_type)
            for item in outgoing
        }
        if normalized_types and all(
            any(marker in value for marker in ("EMTA", "MODEM", "DOCSIS", "GPON"))
            for value in normalized_types
        ):
            return "87 - RETIRAR EMTA"
        return "5 - RETIRAR EQUIPAMENTO"
    raise DisconnectBlocked(
        ("dominium_os_creation_service_unsupported", "operation_blocked"),
        stage="create_missing_os",
    )


def _native_creation_service(job: DisconnectJob) -> str:
    mapped_service = _mapped_creation_service(job)
    if mapped_service:
        expected_service = {
            "430": "RETIRADA FORA TOA",
            "409": "RETIRADA FORA TOA",
            "706": "ENVIO DE CHIP VIA TECNICO",
        }.get(job.requested_close_code, "")
        if mapped_service != expected_service:
            raise DisconnectBlocked(
                (
                    "dominium_os_creation_service_code_mismatch",
                    "operation_blocked",
                ),
                stage="create_missing_os",
            )
        return mapped_service
    if job.requested_close_code == "706":
        return "ENVIO DE CHIP VIA TECNICO"
    if job.requested_close_code in ("430", "409"):
        return "RETIRADA FORA TOA"
    raise DisconnectBlocked(
        ("dominium_os_creation_service_unsupported", "operation_blocked"),
        stage="create_missing_os",
    )


def _automatic_os_number(job: DisconnectJob) -> str:
    identity = "|".join(
        (
            job.profile_key,
            job.contract,
            job.activity_id,
            job.requested_close_code,
        )
    ).encode("ascii", errors="strict")
    numeric = int(hashlib.sha256(identity).hexdigest()[:16], 16) % 1_000_000_000
    return f"9{numeric:09d}"


def _build_order_preview(
    job: DisconnectJob,
    *,
    technician: str,
    technician_name: str,
    service_name: str,
) -> tuple[TOAPreview, str]:
    task_numbers = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in job.toa_snapshot.task_os_numbers
            if str(value).strip().isdigit()
        )
    )
    technician = str(technician).strip().upper()
    technician_name = " ".join(str(technician_name).split()).upper()
    if not task_numbers or not technician or not technician_name:
        raise DisconnectBlocked(
            ("dominium_os_creation_data_missing", "operation_blocked"),
            stage="create_missing_os",
        )
    try:
        city, state, zip_code = PROFILE_LOCATIONS[job.profile_key]
    except KeyError as exc:
        raise DisconnectBlocked(
            ("profile_scope_mismatch", "operation_blocked"),
            stage="create_missing_os",
        ) from exc
    target_os_number = _automatic_os_number(job)
    order_date = dt.date.today()
    order = TOAOrder(
        date=order_date.strftime("%d/%m/%Y"),
        technician=technician,
        activity_status="AGENDADA",
        address="CADASTRO AUTOMATICO TOA",
        address_complement="",
        district="ADMINISTRATIVO",
        zip_code=zip_code,
        time_window="IMEDIATA",
        city=city,
        state=state,
        contract=job.contract,
        work_order=job.activity_id,
        node="",
        os_number=target_os_number,
        point="",
        os_status="",
        os_type=service_name,
        close_code=job.requested_close_code,
        workzone_key="",
        activity_type=job.toa_snapshot.activity_type,
        technician_name=technician_name,
        activity_id=job.activity_id,
    )
    return (
        TOAPreview(
            filename=(
                f"baixa-automatica-{job.profile_key}-{job.contract}-"
                f"{order_date:%Y%m%d}.csv"
            ),
            source_rows=1,
            orders=(order,),
        ),
        target_os_number,
    )


def _build_missing_order_preview(job: DisconnectJob) -> tuple[TOAPreview, str]:
    technician, technician_name = _technician_hints(job)
    return _build_order_preview(
        job,
        technician=technician,
        technician_name=technician_name,
        service_name=_missing_order_service(job),
    )


def _build_native_missing_order_preview(
    job: DisconnectJob,
    technician_name: str,
    service_name: str,
) -> tuple[TOAPreview, str]:
    return _build_order_preview(
        job,
        technician=technician_name,
        technician_name=technician_name,
        service_name=service_name,
    )


def _create_missing_order(
    api: ImperiumAPI,
    job: DisconnectJob,
    *,
    client_mode: str = "registered",
) -> dict[str, Any]:
    native_service = _native_creation_service(job)
    native_creation = (
        bool(native_service)
        and api.native_creation_enabled
        and native_service in api.native_creation_services()
    )
    if native_creation:
        technician = _resolve_native_technician(api, job)
        technician_name = str(technician["technician_name"]).strip()
        preview, target_os_number = _build_native_missing_order_preview(
            job,
            technician_name,
            native_service,
        )
        result = api.create_native_orders(
            preview,
            int(technician["installer_id"]),
            technician_name,
            client_mode=client_mode,
        )
        creation_method = f"native_{client_mode}"
    else:
        preview, target_os_number = _build_missing_order_preview(job)
        result = api.import_toa(preview)
        creation_method = "toa_import"
    gateway = ImperiumDominiumDirectGateway(
        api,
        clock=lambda: dt.datetime.now(dt.timezone.utc),
        target_os_number=target_os_number,
    )
    if not gateway.find_orders(job):
        raise DisconnectBlocked(
            ("dominium_os_import_not_confirmed", "operation_blocked"),
            stage="create_missing_os",
        )
    return {
        "target_os_number": target_os_number,
        "service": preview.orders[0].service_name,
        "technician": preview.orders[0].technician,
        "technician_name": preview.orders[0].technician_name,
        "source_task_os_numbers": list(job.toa_snapshot.task_os_numbers),
        "creation_method": creation_method,
        "import_result": result,
    }


def _adm_evidence_day(job: DisconnectJob) -> dt.date:
    csv_date = re.search(r"adm_csv_date=(\d{4}-\d{2}-\d{2})", job.toa_snapshot.source_reference)
    try:
        day = (dt.date.fromisoformat(csv_date.group(1)) if csv_date else
               dt.datetime.fromisoformat(job.received_at.replace("Z", "+00:00")).date())
    except ValueError as exc:
        raise DisconnectBlocked(("adm_evidence_date_invalid",), stage="adm_task_split") from exc
    return day


def _load_adm_tasks(job: DisconnectJob) -> tuple[ADMTaskEvidence, ...]:

    return find_latest_adm_tasks(
        ROOT, contract=job.contract, activity_id=job.activity_id,
        when=_adm_evidence_day(job), allowed_routes=(job.import_origin,),
    )


def _adm_child_jobs(
    job: DisconnectJob,
    *, tasks: tuple[ADMTaskEvidence, ...] | None = None,
) -> tuple[tuple[ADMTaskEvidence, DisconnectJob], ...]:
    if (job.requested_close_code not in {"409", "430"}
            or job.toa_snapshot.direction_source != "toa_csv_validation_baixa_exact_task"):
        return ()
    if tasks is None:
        tasks = _load_adm_tasks(job)
    day = _adm_evidence_day(job)
    if not tasks:
        raise DisconnectBlocked(("adm_task_evidence_missing",), stage="adm_task_split")
    try:
        validate_adm_task_identity(tasks)
    except ValueError as exc:
        raise DisconnectBlocked((str(exc),), stage="adm_task_split") from exc

    requested = tuple(
        task for task in tasks
        if task.close_code == job.requested_close_code
    )
    if not requested:
        raise DisconnectBlocked(
            ("toa_requested_code_not_in_adm_tasks", "operation_blocked"),
            stage="adm_task_split",
        )

    if (
        job.toa_snapshot.direction_source
        == "toa_csv_validation_baixa_exact_task"
    ):
        declared = {
            re.sub(r"\D", "", str(value or ""))
            for value in job.toa_snapshot.task_os_numbers
            if re.sub(r"\D", "", str(value or ""))
        }
        requested_os = {task.os_number for task in requested}
        if declared != requested_os:
            raise DisconnectBlocked(
                ("adm_parent_task_scope_mismatch", "operation_blocked"),
                stage="adm_task_split",
            )

    if job.toa_snapshot.materials:
        raise DisconnectBlocked(
            ("disconnect_contains_miscellaneous", "operation_blocked"),
            stage="adm_task_split",
        )

    equipment_types: dict[str, str] = {}
    for item in (
        job.toa_snapshot.installed_equipments
        + job.toa_snapshot.added_equipments
        + job.toa_snapshot.removed_equipments
        + job.toa_snapshot.unknown_equipments
    ):
        previous_type = equipment_types.get(item.serial)
        if previous_type and previous_type != item.equipment_type:
            raise DisconnectBlocked(("task_equipment_type_conflict",), stage="adm_task_split")
        equipment_types[item.serial] = item.equipment_type

    children: list[tuple[ADMTaskEvidence, DisconnectJob]] = []
    for task in requested:
        missing = [
            serial
            for serial in task.installed_serials + task.removed_serials
            if serial not in equipment_types
        ]
        if missing:
            raise DisconnectBlocked(
                ("task_equipment_type_missing", "toa_snapshot_incomplete"),
                stage="adm_task_split",
            )

        installed = tuple(
            TOAEquipment(
                serial=serial,
                equipment_type=equipment_types[serial],
                direction=MovementDirection.INCOMING,
            )
            for serial in task.installed_serials
        )
        removed = tuple(
            TOAEquipment(
                serial=serial,
                equipment_type=equipment_types[serial],
                direction=MovementDirection.OUTGOING,
            )
            for serial in task.removed_serials
        )

        # Some ADM exports identify the exact OS/code but leave the
        # "Validacao Baixa" serial list empty. When this code has a single
        # task, the live TOA activity is unambiguous, so inherit its equipment
        # snapshot. For multi-task batches we still require explicit per-task
        # serial mapping to avoid routing equipment to the wrong OS.
        if len(tasks) == 1 and len(requested) == 1:
            installed = tuple({item.serial: item for item in (
                installed + job.toa_snapshot.installed_equipments
                + job.toa_snapshot.added_equipments
            )}.values())
            removed = tuple({item.serial: item for item in (
                removed + job.toa_snapshot.removed_equipments
            )}.values())
        if len(requested) == 1 and task.close_code == "430" and not removed:
            raise DisconnectBlocked(
                ("close_430_without_outgoing_equipment",),
                stage="adm_task_split",
            )
        if len(requested) == 1 and task.close_code == "409" and not installed:
            raise DisconnectBlocked(
                ("close_409_without_incoming_equipment",),
                stage="adm_task_split",
            )

        child_job_id = f"{job.job_id}:adm:{task.index}:{task.os_number}"
        child_message_id = (
            f"{job.message_id}:adm:{task.index}:{task.os_number}"
        )
        event = DisconnectMessageEvent(
            message_id=child_message_id,
            chat_id=job.chat_id,
            sender_id=job.sender_id,
            received_at=job.received_at,
            raw_text=f"{job.contract} {task.close_code}",
            contract=job.contract,
            requested_close_code=task.close_code,
            import_origin=job.import_origin,
            city=job.city,
            profile_key=job.profile_key,
            observation=job.observation,
        )
        snapshot = TOADisconnectSnapshot.create(
            profile_key=job.profile_key,
            city=job.city,
            contract=job.contract,
            activity_id=job.activity_id,
            activity_type=task.service or job.toa_snapshot.activity_type,
            activity_status=job.toa_snapshot.activity_status,
            installed_equipments=installed,
            removed_equipments=removed,
            added_equipments=(),
            materials=(),
            installer_id=job.toa_snapshot.installer_id,
            current_close_code=None,
            observation=job.toa_snapshot.observation,
            source_reference=f"{task.source_file}#task={task.index}&point={task.point}&adm_csv_date={day.isoformat()}",
            job_id=child_job_id,
            message_id=child_message_id,
            group_id=job.chat_id,
            processing_id=child_message_id,
            unknown_equipments=(),
            materials_complete=True,
            direction_source="toa_csv_validation_baixa_exact_task",
            task_os_numbers=(task.os_number,),
            technician_name=job.toa_snapshot.technician_name,
            technician_login=job.toa_snapshot.technician_login,
        )
        child = DisconnectJob.create(
            event,
            snapshot,
            job_id=child_job_id,
            ttl_seconds=900,
        )
        children.append((task, child))
    return tuple(children)


def _confirm_completed_adm_task(
    api: ImperiumAPI, job: DisconnectJob, task: ADMTaskEvidence,
    *, orders: tuple[Any, ...] | None = None,
) -> bool:
    """Read-only confirmation: stock or code alone never proves this task."""
    if orders is None:
        orders = tuple(api.list_orders(dt.date.today(), status="completed", service_type="all"))
    matches = [order for order in orders if order.contract == job.contract
               and re.sub(r"\D", "", str(order.num_os or "")) == task.os_number]
    if not matches:
        return False
    if len(matches) != 1:
        raise DisconnectBlocked(("closed_os_identity_ambiguous",), stage="adm_task_split")
    order = matches[0]
    detail = api._fetch_detail(order.id_os, timeout=15.0)
    context = api._detail_context(detail)
    if (int(context.id_os) != int(order.id_os) or str(context.contract) != job.contract
            or (job.toa_snapshot.installer_id and str(context.installer_id) != job.toa_snapshot.installer_id)):
        raise DisconnectBlocked(("closed_os_detail_identity_mismatch",), stage="adm_task_split")
    codes = {code.code for code in api._detect_applied_close_codes(order, detail)}
    if codes != {task.close_code}:
        raise DisconnectBlocked(("already_closed_with_different_code", "operation_blocked"), stage="adm_task_split")
    movements = api.read_detail_equipment_movements(detail)
    expected_installed = {e.serial for e in job.toa_snapshot.installed_equipments + job.toa_snapshot.added_equipments}
    expected_removed = {e.serial for e in job.toa_snapshot.removed_equipments}
    if (set(e.serial for e in movements.installed) != expected_installed
            or set(e.serial for e in movements.removed) != expected_removed
            or movements.materials_present):
        raise DisconnectBlocked(("closed_os_equipment_confirmation_pending", "operation_blocked"), stage="adm_task_split")
    return True


def run_job(
    raw_job: Mapping[str, Any],
    *,
    force_dry_run: bool = False,
) -> dict[str, Any]:
    config = load_config()
    ProjectIdentity.load(ROOT)
    creation_only = raw_job.get("creation_only") is True
    if creation_only:
        raise DisconnectBlocked(("synthetic_os_creation_disabled", "operation_blocked"), stage="desc_scope")
    job = job_from_dict(raw_job)
    # DESC is the sender's sector and authenticated WhatsApp group, NOT
    # a service-name prefix on the OS. Validate source/sector below.
    _assert_desc_group_scope(job)
    # Split exact DMV_ADM task evidence before classifying the aggregate TOA
    # snapshot. Otherwise a neighboring 409 task can contaminate a requested
    # 430 with incoming equipment (or vice versa).
    evidence = raw_job.get("adm_task_evidence")
    frozen_tasks = None
    if evidence is not None:
        if (not isinstance(evidence, dict) or evidence.get("contract") != job.contract
                or evidence.get("activity_id") != job.activity_id):
            raise DisconnectBlocked(("adm_evidence_identity_mismatch",), stage="adm_task_split")
        try:
            frozen_tasks = tuple(ADMTaskEvidence(
                index=int(value["index"]), os_number=str(value["os_number"]),
                close_code=str(value["close_code"]), service=str(value["service"]),
                point=str(value["point"]), installed_serials=tuple(value["installed_serials"]),
                removed_serials=tuple(value["removed_serials"]), source_file=str(value["source_file"]),
            ) for value in evidence["tasks"])
        except (TypeError, KeyError, ValueError) as exc:
            raise DisconnectBlocked(("adm_evidence_invalid",), stage="adm_task_split") from exc
    if (frozen_tasks is None and job.requested_close_code in {"409", "430"}
            and job.toa_snapshot.direction_source == "toa_csv_validation_baixa_exact_task"):
        frozen_tasks = _load_adm_tasks(job)
    adm_children = _adm_child_jobs(job, tasks=frozen_tasks) if not creation_only else ()
    if not creation_only and not adm_children:
        job = _refresh_incomplete_snapshot(job)
    execution_enabled = (
        config.get("external_execution_enabled") is True
        and not force_dry_run
    )
    if execution_enabled:
        _assert_desc_technician_sector(job)
    runtime = PROFILE_RUNTIME.get(job.profile_key)
    rule = AUTOMATION_PROFILE_RULES.get(job.profile_key)
    if runtime is None or rule is None:
        raise DisconnectBlocked(
            ("profile_scope_mismatch", "operation_blocked"),
            stage="local_runner_scope",
        )
    log_root = ROOT / "logs"
    if runtime["log_dir"]:
        log_root /= str(runtime["log_dir"])
    api = ImperiumAPI(
        ROOT,
        port=int(runtime["port"]),
        company=str(runtime["company"]),
        profile_key=job.profile_key,
        controller_id=int(runtime["controller_id"]),
        log_root=log_root,
    )
    pacer = DirectExecutionPacer(
        ROOT / "config" / "disconnect_runtime",
        minimum_interval_seconds=float(config["minimum_seconds_between_closes"]),
    )

    def process_one(
        current_job: DisconnectJob,
        *,
        target_os_number: object = "",
    ) -> dict[str, Any]:
        gateway = ImperiumDominiumDirectGateway(
            api,
            clock=lambda: dt.datetime.now(dt.timezone.utc),
            stage3_write_enabled=execution_enabled,
            target_os_number=target_os_number,
        )
        worker = DisconnectWorker(
            gateway,
            execution_enabled=execution_enabled,
            execution_pacer=pacer,
            allowed_chat_ids=rule["chat_ids"],
            expected_profile_key=current_job.profile_key,
            expected_city=current_job.city,
        )
        return worker.process(current_job, dry_run=not execution_enabled)

    if adm_children:
        # Do not distribute ten equipments among ten different OS.
        # Preview a single deterministic target. The other OS still require
        # a separate close-only protocol; block writes until that protocol
        # supports them without repeating stock movement.
        try:
            allocation = single_os_allocation(
                frozen_tasks,
                job.requested_close_code,
                toa_installed=[
                    item.serial for item in (
                        job.toa_snapshot.installed_equipments
                        + job.toa_snapshot.added_equipments
                    )
                ],
                toa_removed=[
                    item.serial for item in job.toa_snapshot.removed_equipments
                ],
            )
            plan = {
                "equipment_os": allocation.target_os,
                "code": allocation.close_code,
                "installed_serials": list(allocation.installed_serials),
                "removed_serials": list(allocation.removed_serials),
                "other_os": list(allocation.other_os),
                "miscellaneous": [],  # DESC never emits misc.
            }
            blockers = (["multi_os_single_equipment_os_requires_close_only_protocol"]
                        if len(adm_children) > 1 else [])
        except AllocationBlocked as exc:
            plan = None
            blockers = [str(exc)]
        if blockers:
            result = {
                "state": "operation_blocked",
                "job_id": job.job_id,
                "write_calls": 0,
                "write_attempted": False,
                "blockers": blockers,
                "aggregation_plan": plan,
                "os_numbers": [task.os_number for task, _ in adm_children],
                "operational_payload": None,
            }
            _append_audit(raw_job, result)
            return result

    if adm_children:
        batch: list[dict[str, Any]] = []
        write_calls = 0
        completed_cache: tuple[Any, ...] | None = None

        def already_completed(task: ADMTaskEvidence) -> bool:
            nonlocal completed_cache
            if completed_cache is None:
                completed_cache = tuple(
                    api.list_orders(
                        dt.date.today(),
                        status="completed",
                        service_type="all",
                    )
                )
            child = next(child for evidence, child in adm_children if evidence.os_number == task.os_number)
            return _confirm_completed_adm_task(api, child, task, orders=completed_cache)

        def failed_batch(exc: Exception, *, read_only: bool = False) -> dict[str, Any]:
            attempted = getattr(exc, "write_attempted", None)
            if read_only:
                attempted = False
            uncertain_writes = int(getattr(exc, "write_calls", 0) or 0)
            if attempted is True and not uncertain_writes:
                uncertain_writes = 1
            total = write_calls + uncertain_writes
            retryable = (total == 0 and attempted is False and
                         any(marker in str(exc).casefold() for marker in ("busy", "ocupad", "locked")))
            result = {
                "state": "awaiting_confirmation" if total or attempted is not False else "operation_blocked",
                "write_calls": total, "write_attempted": bool(total) or attempted is not False,
                "retryable": retryable, "blockers": ["datasnap_busy"] if retryable else [str(exc)],
                "os_numbers": [task.os_number for task, _child in adm_children],
                "batch": list(batch), "error_type": type(exc).__name__,
            }
            _append_audit(raw_job, result)
            return result

        for task, child_job in adm_children:
            exact_selector = ImperiumDominiumDirectGateway(
                api,
                clock=lambda: dt.datetime.now(dt.timezone.utc),
                target_os_number=task.os_number,
            )
            try:
                open_matches = exact_selector.find_orders(child_job)
                confirmed_closed = already_completed(task) if not open_matches else False
            except Exception as exc:
                return failed_batch(exc, read_only=True)
            if not open_matches:
                if confirmed_closed:
                    batch.append(
                        {
                            "os_number": task.os_number,
                            "close_code": task.close_code,
                            "state": "already_closed",
                            "write_calls": 0,
                        }
                    )
                    continue
                raise DisconnectBlocked(
                    ("toa_task_os_not_found", "operation_blocked"),
                    stage="adm_task_split",
                )

            try:
                child_result = process_one(child_job, target_os_number=task.os_number)
            except Exception as exc:
                return failed_batch(exc)
            child_writes = int(child_result.get("write_calls") or 0)
            write_calls += child_writes
            batch.append(
                {
                    "os_number": task.os_number,
                    "close_code": task.close_code,
                    "state": child_result.get("state"),
                    "write_calls": child_writes,
                    "result": child_result,
                }
            )
            if child_result.get("state") not in {
                "completed",
                "dry_run_completed",
            }:
                result = {
                    **child_result,
                    "write_calls": write_calls,
                    "os_numbers": [item[0].os_number for item in adm_children],
                    "batch": batch,
                }
                _append_audit(raw_job, result)
                if write_calls > 0:
                    _disarm_after_write(
                        job.job_id,
                        str(result.get("state") or "unknown"),
                    )
                return result

        result = {
            "state": "completed" if execution_enabled else "dry_run_completed",
            "job_id": job.job_id,
            "blockers": [],
            "write_calls": write_calls,
            "os_numbers": [task.os_number for task, _child in adm_children],
            "batch": batch,
            "operational_payload": None,
            "close_code": job.requested_close_code,
            "os_confirmed": execution_enabled,
            "equipments_confirmed": execution_enabled,
            "adm_task_split": True,
        }
        _append_audit(raw_job, result)
        if write_calls > 0:
            _disarm_after_write(job.job_id, result["state"])
        return result

    selector = ImperiumDominiumDirectGateway(
        api,
        clock=lambda: dt.datetime.now(dt.timezone.utc),
    )
    matches = selector.find_orders(job) if not creation_only else ()

    # A TOA snapshot that names concrete OS numbers is authoritative. Never
    # synthesize RETIRADA FORA TOA while one of those task OS is the intended
    # target. Multi-task snapshots carry aggregate equipment movements and
    # must be split per task before any productive close is attempted.
    source_task_os_numbers = tuple(
        dict.fromkeys(
            re.sub(r"\D", "", str(value or ""))
            for value in job.toa_snapshot.task_os_numbers
            if re.sub(r"\D", "", str(value or ""))
        )
    )
    if source_task_os_numbers and not creation_only:
        source_set = set(source_task_os_numbers)
        exact_matches = tuple(
            order
            for order in matches
            if re.sub(r"\D", "", str(order.num_os or "")) in source_set
        )
        if len(source_task_os_numbers) > 1:
            raise DisconnectBlocked(
                ("multiple_toa_tasks_require_split", "operation_blocked"),
                stage="select_os",
            )
        if not exact_matches:
            raise DisconnectBlocked(
                ("toa_task_os_not_found", "operation_blocked"),
                stage="select_os",
            )
        matches = exact_matches

    creation: dict[str, Any] | None = None
    if creation_only:
        expected_manual_os = _automatic_os_number(job)
        manual_selector = ImperiumDominiumDirectGateway(
            api,
            clock=lambda: dt.datetime.now(dt.timezone.utc),
            target_os_number=expected_manual_os,
        )
        manual_matches = manual_selector.find_orders(job)
        if manual_matches:
            target_os_number = manual_selector._find_order(job).num_os
            result = {
                "state": "os_already_open",
                "job_id": job.job_id,
                "blockers": [],
                "write_calls": 0,
                "os_confirmed": True,
                "equipments_confirmed": False,
                "os_numbers": [target_os_number],
                "operational_payload": None,
            }
        elif execution_enabled and _auto_create_enabled(config, job.profile_key):
            creation = _create_missing_order(
                api,
                job,
                client_mode="captured_profile",
            )
            result = {
                "state": "os_created",
                "job_id": job.job_id,
                "blockers": [],
                "write_calls": 1,
                "os_confirmed": True,
                "equipments_confirmed": False,
                "os_numbers": [creation["target_os_number"]],
                "batch": [
                    {
                        "action": "created_from_whatsapp_sender",
                        "os_number": creation["target_os_number"],
                        "service": creation["service"],
                        "technician": creation["technician"],
                        "technician_name": creation["technician_name"],
                        "creation_method": creation["creation_method"],
                    }
                ],
                "operational_payload": None,
            }
        else:
            raise DisconnectBlocked(
                ("dominium_os_creation_disabled", "operation_blocked"),
                stage="create_missing_os",
            )
        _append_audit(raw_job, result)
        if int(result.get("write_calls") or 0) > 0:
            _disarm_after_write(job.job_id, str(result.get("state") or "unknown"))
        return result
    if matches:
        target_os_number = selector._find_order(job).num_os
    elif execution_enabled and _auto_create_enabled(config, job.profile_key):
        creation = _create_missing_order(
            api,
            job,
            client_mode="captured_profile",
        )
        target_os_number = creation["target_os_number"]
    else:
        target_os_number = ""

    result = process_one(job, target_os_number=target_os_number)
    if creation is not None:
        result = {
            **result,
            "write_calls": int(result.get("write_calls") or 0) + 1,
            "os_numbers": [creation["target_os_number"]],
            "batch": [
                {
                    "action": "created_from_toa_snapshot",
                    "os_number": creation["target_os_number"],
                    "service": creation["service"],
                    "technician": creation["technician"],
                    "technician_name": creation["technician_name"],
                    "source_task_os_numbers": creation["source_task_os_numbers"],
                    "creation_method": creation["creation_method"],
                }
            ],
        }
    _append_audit(raw_job, result)
    if int(result.get("write_calls") or 0) > 0:
        _disarm_after_write(job.job_id, str(result.get("state") or "unknown"))
    return result


def _blocked_result(raw_job: Mapping[str, Any], exc: BaseException) -> dict[str, Any]:
    blockers = (
        list(exc.blockers)
        if isinstance(exc, DisconnectBlocked)
        else ["local_runner_failed", "operation_blocked"]
    )
    return {
        "state": "operation_blocked",
        "job_id": str(raw_job.get("job_id") or ""),
        "blockers": blockers,
        "error_type": type(exc).__name__,
        "write_calls": 0,
        "operational_payload": None,
    }


def _read_stdin_job() -> Mapping[str, Any]:
    value = json.loads(sys.stdin.read())
    if isinstance(value, dict) and isinstance(value.get("job"), dict):
        return value["job"]
    if isinstance(value, dict):
        return value
    raise ValueError("Payload do job invalido")


def main() -> int:
    parser = argparse.ArgumentParser(description="Executor local BotDMV -> OLLAMA")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.health:
        print(json.dumps(health(), ensure_ascii=True, sort_keys=True), flush=True)
        return 0

    raw_job: Mapping[str, Any] = {}
    try:
        raw_job = _read_stdin_job()
        # Bibliotecas legadas podem imprimir diagnóstico em stdout. Mantemos
        # stdout reservado para a única resposta JSON consumida pelo Node.
        with contextlib.redirect_stdout(sys.stderr):
            result = run_job(raw_job, force_dry_run=args.dry_run)
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr)
        result = _blocked_result(raw_job, exc)
        try:
            _append_audit(raw_job, result)
        except OSError:
            pass
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
