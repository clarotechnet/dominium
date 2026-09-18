# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - protocolo, baixa, estoque ou operacao do Imperium.
#
# TOA
# - NAO - este arquivo nao consulta nem automatiza o TOA.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas quando necessario ao fluxo Imperium.
#
# Categoria deste arquivo: IMPERIUM.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import datetime as dt
import hashlib
import json
import re
from typing import Any

from imperium_http_api import build_close_payload
from material_matching import toa_material_ignore_reason
def _value(source: Any, field: str, default: Any = "") -> Any:
    if isinstance(source, dict):
        return source.get(field, default)
    return getattr(source, field, default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"A lista {field} e invalida")
    if len(value) > 300:
        raise ValueError(f"A lista {field} excede o limite de 300 itens")
    return value


def build_manual_official_plan(
    *,
    order: Any,
    scheduled_date: dt.date | str,
    technician_code: str,
    close_code: str,
    close_description: str,
    productive: bool,
    body: dict[str, Any],
    removed_type_codes: dict[str, str],
) -> dict[str, Any]:
    installed_source = _items(body.get("installed_equipment"), "installed_equipment")
    removed_source = _items(body.get("removed_equipment"), "removed_equipment")
    material_source = _items(body.get("materials"), "materials")

    legacy_installed = _text(body.get("installed_serial"))
    if legacy_installed and not installed_source:
        installed_source = [{"serial": legacy_installed, "type": "auto"}]
    legacy_removed = _text(body.get("removed_serial"))
    if legacy_removed and not removed_source:
        removed_source = [
            {"serial": legacy_removed, "type": _text(body.get("removed_type"))}
        ]

    if not productive and (installed_source or removed_source or material_source):
        raise ValueError("Codigo improdutivo nao aceita movimentacao de estoque")
    if close_code == "430" and (installed_source or material_source):
        raise ValueError("O codigo 430 aceita somente equipamento retirado")
    if close_code == "706" and (removed_source or material_source):
        raise ValueError("O codigo 706 aceita somente equipamento instalado")

    installed = []
    seen_installed: set[str] = set()
    for item in installed_source:
        serial = _text(item.get("serial")).upper()
        if not serial:
            raise ValueError("Informe o serial do equipamento instalado")
        if serial in seen_installed:
            raise ValueError(f"Serial instalado duplicado: {serial}")
        seen_installed.add(serial)
        installed.append({"serialnumber": serial})

    removed = []
    seen_removed: set[str] = set()
    for item in removed_source:
        serial = _text(item.get("serial")).upper()
        equipment_type = _text(item.get("type")).lower()
        if equipment_type in {"", "auto"}:
            installed_types = [
                _text(inst.get("type")).lower()
                for inst in installed_source
                if _text(inst.get("type")).lower() in removed_type_codes
            ]
            if installed_types:
                equipment_type = installed_types[0]
            elif re.fullmatch(r"[0-9A-F]{12}", serial, re.IGNORECASE):
                equipment_type = "emta"
            elif serial.isdigit():
                equipment_type = "decoder"
            else:
                service_norm = _text(_value(order, "service")).upper()
                if any(x in service_norm for x in ["STREAM", "DECODER", "TV"]):
                    equipment_type = "decoder"
                else:
                    equipment_type = "emta"
        code = _text(removed_type_codes.get(equipment_type))
        if not serial:
            raise ValueError("Informe o serial do equipamento retirado")
        if not code:
            raise ValueError(
                f"Tipo do equipamento retirado nao suportado: {equipment_type or '-'}"
            )
        if serial in seen_removed:
            raise ValueError(f"Serial retirado duplicado: {serial}")
        seen_removed.add(serial)
        removed.append({"codigoequipamento": code, "serialnumber": serial})

    materials = []
    ignored_materials = []
    for item in material_source:
        code = _text(item.get("code"))
        description = _text(item.get("description") or item.get("name"))
        ignore_reason = toa_material_ignore_reason(description, code)
        if ignore_reason:
            ignored_materials.append(
                {
                    "code": code,
                    "description": description,
                    "quantity": item.get("quantity"),
                    "ignore_reason": ignore_reason,
                }
            )
            continue
        materials.append(
            {
                "codigoequipamento": code,
                "qtd": item.get("quantity"),
            }
        )

    date_text = (
        scheduled_date.isoformat()
        if isinstance(scheduled_date, dt.date)
        else _text(scheduled_date)
    )
    payload = build_close_payload(
        number=_value(order, "num_os"),
        scheduled_date=date_text,
        technician_code=technician_code,
        close_code=close_code,
        installed_serials=installed,
        installed_materials=materials,
        removed_serials=removed,
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    normalized = payload["ordemservico"]
    return {
        "payload": payload,
        "fingerprint": fingerprint,
        "installed_count": len(normalized["instaladosserializados"]),
        "removed_count": len(normalized["removidosserializados"]),
        "material_count": len(normalized["instaladosmiscelaneas"]),
        "ignored_material_count": len(ignored_materials),
        "ignored_materials": ignored_materials,
        "close_description": _text(close_description),
    }
