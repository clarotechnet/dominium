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
import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

class ControlledDryRunError(ValueError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    return "".join(char for char in text if not unicodedata.combining(char)).upper()


def _external_id(provider: Any) -> str:
    if not isinstance(provider, dict):
        return ""
    return _text(provider.get("external_id")).upper()


def _item_point(item: Any) -> str:
    return _text(item.get("point")) if isinstance(item, dict) else ""


def _task_for_order(review: dict[str, Any], number: str) -> dict[str, Any] | None:
    matches = [
        task
        for task in review.get("tasks", [])
        if isinstance(task, dict) and _text(task.get("os_number")) == number
    ]
    return matches[0] if len(matches) == 1 else None


def _belongs_to_order(item: dict[str, Any], order_point: str) -> bool:
    point = _item_point(item)
    return bool(point and order_point and point == order_point)


def _quantity_text(value: Any) -> str:
    text = _text(value).replace(",", ".")
    try:
        quantity = Decimal(text)
    except InvalidOperation as error:
        raise ControlledDryRunError(f"Quantidade invalida: {value}") from error
    if not quantity.is_finite() or quantity <= 0:
        raise ControlledDryRunError(f"Quantidade deve ser positiva: {value}")
    normalized = format(quantity.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _build_close_payload(
    *,
    number: str,
    scheduled_date: str,
    technician_code: str,
    close_code: str,
    installed_serials: list[dict[str, str]],
    installed_materials: list[dict[str, str]],
    removed_serials: list[dict[str, str]],
) -> dict[str, Any]:
    materials: dict[str, Decimal] = {}
    for item in installed_materials:
        code = _text(item.get("codigoequipamento"))
        if not code:
            raise ControlledDryRunError("Codigo de miscelanea ausente")
        quantity = Decimal(_quantity_text(item.get("qtd")))
        materials[code] = materials.get(code, Decimal("0")) + quantity
    try:
        visible_close_code = int(close_code)
    except (TypeError, ValueError) as error:
        raise ControlledDryRunError("Codigo visivel de baixa invalido") from error
    return {
        "ordemservico": {
            "numero": number,
            "dataagendamento": scheduled_date,
            "codigotecnico": technician_code.upper(),
            "codigobaixa": visible_close_code,
            "instaladosserializados": copy_items(installed_serials),
            "instaladosmiscelaneas": [
                {
                    "codigoequipamento": code,
                    "qtd": _quantity_text(quantity),
                }
                for code, quantity in materials.items()
            ],
            "removidosserializados": copy_items(removed_serials),
        }
    }


def copy_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(item) for item in items]


def _build_official_close_plan(
    review: dict[str, Any],
    order: dict[str, Any],
    scheduled_date: dt.date | str,
) -> dict[str, Any]:
    number = _text(order.get("num_os"))
    contract = _text(order.get("contract"))
    point = _text(order.get("point"))
    capability = _text(order.get("capability"))
    imperium_current_status = _text(order.get("imperium_current_status") or order.get("status"))
    warnings: list[str] = []
    blockers: list[str] = []

    if _text(review.get("contract")) != contract:
        blockers.append("contract_mismatch")
    task = _task_for_order(review, number)
    if task is None:
        blockers.append("task_not_found_or_duplicated")
        task = {}
    normalized_imperium_status = _normalized(imperium_current_status)
    if normalized_imperium_status in {
        "BAIXADA",
        "BAIXADO",
        "CANCELADA",
        "CANCELADO",
        "CONCLUIDA",
        "CONCLUIDO",
        "FINALIZADA",
        "FINALIZADO",
    }:
        blockers.append("already_processed")
    elif normalized_imperium_status != "EM CAMPO":
        blockers.append("imperium_status_not_open")
    if _normalized(review.get("activity_status")) not in {
        "COMPLETE",
        "COMPLETED",
        "CONCLUIDO",
        "CONCLUIDA",
        "EXECUTADA",
        "EXECUTADO",
    }:
        blockers.append("toa_activity_not_complete")
    non_authoritative_processing_markers = {
        "already_processed",
        "activity_already_processed",
        "toa_already_processed",
    }
    capture_errors = {
        _text(value) for value in review.get("validation_errors", []) if _text(value)
    }
    if capture_errors - non_authoritative_processing_markers:
        blockers.append("capture_validation_errors")

    decision = _text(review.get("decision"))
    reasons = {
        _text(value) for value in review.get("decision_reasons", []) if _text(value)
    }
    reasons -= non_authoritative_processing_markers
    if decision == "blocked_manual_review":
        blockers.append("capture_blocked_manual_review")
    if reasons - {"route_not_confirmed"}:
        blockers.append("capture_decision_requires_review")
    if "route_not_confirmed" in reasons:
        blockers.append("route_not_confirmed")

    technician_code = _text(order.get("technician_login")).upper()
    if not technician_code:
        blockers.append("technician_login_missing")
    assigned_code = _external_id(review.get("assigned_technician"))
    if assigned_code and technician_code and assigned_code != technician_code:
        blockers.append("assigned_technician_login_mismatch")

    installed = [
        item
        for item in review.get("installed_equipment", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point)
    ]
    removed = [
        item
        for item in review.get("removed_equipment", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point)
    ]
    materials = [
        item
        for item in review.get("materials", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point)
    ]
    if capability not in {"material_capable", "close_only"}:
        blockers.append("service_capability_unmapped")
    if capability == "close_only" and (installed or removed or materials):
        blockers.append("inventory_assigned_to_close_only")
    if installed or removed or materials:
        inventory_codes = {
            _external_id(provider)
            for provider in review.get("inventory_providers", [])
            if _external_id(provider)
        }
        if not inventory_codes:
            blockers.append("inventory_provider_login_missing")
        elif technician_code not in inventory_codes:
            blockers.append("inventory_provider_login_mismatch")

    installed_serials: list[dict[str, str]] = []
    for item in installed:
        serial = _text(item.get("serial")).upper()
        if not serial:
            blockers.append("installed_serial_missing")
        else:
            installed_serials.append({"serialnumber": serial})

    installed_materials: list[dict[str, str]] = []
    for item in materials:
        code = _text(item.get("material_code"))
        quantity = _text(item.get("quantity"))
        if not code:
            blockers.append("material_code_missing")
        else:
            installed_materials.append(
                {"codigoequipamento": code, "qtd": quantity}
            )

    removed_serials: list[dict[str, str]] = []
    for item in removed:
        code = _text(
            item.get("material_code")
            or item.get("equipment_code")
            or item.get("code")
        )
        serial = _text(item.get("serial")).upper()
        if not code:
            blockers.append("removed_equipment_code_missing")
        if not serial:
            blockers.append("removed_serial_missing")
        if code and serial:
            removed_serials.append(
                {"codigoequipamento": code, "serialnumber": serial}
            )

    close_code = _text(task.get("close_code"))
    if not close_code:
        blockers.append("close_code_missing")
        close_code = "0"
    date_text = (
        scheduled_date.isoformat()
        if isinstance(scheduled_date, dt.date)
        else _text(scheduled_date)
    )
    payload = None
    if not blockers:
        try:
            payload = _build_close_payload(
                number=number,
                scheduled_date=date_text,
                technician_code=technician_code,
                close_code=close_code,
                installed_serials=installed_serials,
                installed_materials=installed_materials,
                removed_serials=removed_serials,
            )
        except ControlledDryRunError:
            blockers.append("official_payload_invalid")
    fingerprint = ""
    if payload is not None:
        fingerprint = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    return {
        "ok": not blockers,
        "dry_run_only": True,
        "aid": _text(review.get("aid")),
        "contract": contract,
        "id_os": int(order.get("id_os") or 0),
        "num_os": number,
        "service": _text(order.get("service")),
        "capability": capability,
        "point": point,
        "imperium_current_status": imperium_current_status,
        "close_code": close_code,
        "technician_code": technician_code,
        "warnings": warnings,
        "blockers": list(dict.fromkeys(blockers)),
        "installed_count": len(installed_serials),
        "removed_count": len(removed_serials),
        "material_count": len(installed_materials),
        "payload": payload,
        "fingerprint": fingerprint,
    }


def build_contract_official_plans(
    review: dict[str, Any],
    orders: list[dict[str, Any]],
    scheduled_date: dt.date | str,
) -> list[dict[str, Any]]:
    """Build local plans without loading the official HTTP transport module."""
    plans = [
        _build_official_close_plan(review, order, scheduled_date)
        for order in orders
    ]
    actual = (
        sum(plan["installed_count"] for plan in plans),
        sum(plan["removed_count"] for plan in plans),
        sum(plan["material_count"] for plan in plans),
    )
    expected = (
        len(review.get("installed_equipment", [])),
        len(review.get("removed_equipment", [])),
        len(review.get("materials", [])),
    )
    if actual != expected:
        for plan in plans:
            plan["ok"] = False
            plan["payload"] = None
            plan["fingerprint"] = ""
            if "inventory_assignment_incomplete" not in plan["blockers"]:
                plan["blockers"].append("inventory_assignment_incomplete")
    return plans


def _service_capability(service: Any) -> str:
    normalized = _normalized(service)
    capabilities = {
        "MUDANCA DE PACOTE": "material_capable",
        "INSTALACAO DE CABO GPON": "close_only",
    }
    return capabilities.get(normalized, "unmapped")


def _official_order(plan: dict[str, Any]) -> dict[str, Any]:
    payload = plan.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("ordemservico"), dict):
        raise ControlledDryRunError(
            f"A OS {_text(plan.get('num_os')) or '-'} nao gerou um JSON oficial valido"
        )
    return payload["ordemservico"]


def _validate_confirmed_route(review: dict[str, Any]) -> None:
    reasons = {
        _text(reason)
        for field in ("decision_reasons", "validation_errors")
        for reason in review.get(field, [])
        if _text(reason)
    }
    blocking_reasons = {
        "route_not_confirmed",
        "route_missing",
        "route_ambiguous",
        "route_aid_missing",
        "route_aid_mismatch",
    }
    if reasons & blocking_reasons:
        raise ControlledDryRunError(
            "A rota da atividade esta ausente, ambigua ou nao confirmada"
        )

    provider = review.get("route_provider")
    if not isinstance(provider, dict):
        raise ControlledDryRunError("A rota da atividade nao foi confirmada")
    candidates = provider.get("candidates")
    if provider.get("ambiguous") is True or (
        isinstance(candidates, list) and len(candidates) > 1
    ):
        raise ControlledDryRunError("A rota da atividade e ambigua")
    provider_id = provider.get("external_id") or provider.get("id")
    if not isinstance(provider_id, (str, int)) or not _text(provider_id):
        raise ControlledDryRunError("A rota da atividade nao foi confirmada")


def _validate_scheduled_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ControlledDryRunError(
            "Data de agendamento deve estar no formato YYYY-MM-DD"
        )
    try:
        if dt.date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as error:
        raise ControlledDryRunError(
            "Data de agendamento deve estar no formato YYYY-MM-DD"
        ) from error
    return value


def _validate_visible_close_code(plan: dict[str, Any], order: dict[str, Any]) -> None:
    visible = _text(plan.get("close_code"))
    if not re.fullmatch(r"\d{1,4}", visible):
        raise ControlledDryRunError("O codigo visivel de baixa e invalido")
    close_code = order.get("codigobaixa")
    if type(close_code) is not int or not 0 <= close_code <= 9999:
        raise ControlledDryRunError(
            "codigobaixa deve ser um numero inteiro visivel"
        )
    if close_code != int(visible):
        raise ControlledDryRunError(
            "O JSON oficial nao preservou o codigo visivel de baixa"
        )


def _validate_order_fields(
    plan: dict[str, Any],
    order: dict[str, Any],
    source_order: dict[str, Any],
    scheduled_date: str,
) -> None:
    number = order.get("numero")
    if not isinstance(number, str) or not number.isdigit():
        raise ControlledDryRunError("numero deve ser uma string numerica")
    plan_number = _text(plan.get("num_os"))
    if number != plan_number:
        raise ControlledDryRunError(
            "O payload nao preservou o num_os do plano"
        )
    payload_date = _validate_scheduled_date(order.get("dataagendamento"))
    if payload_date != scheduled_date:
        raise ControlledDryRunError(
            "O payload nao preservou a data de agendamento solicitada"
        )
    technician = order.get("codigotecnico")
    if not isinstance(technician, str) or not technician.strip():
        raise ControlledDryRunError("codigotecnico deve ser uma string nao vazia")
    source_technician = source_order.get("technician_login")
    if not isinstance(source_technician, str) or not source_technician.strip():
        raise ControlledDryRunError("technician_login deve ser uma string nao vazia")
    if technician != source_technician:
        raise ControlledDryRunError(
            "O payload nao preservou o technician_login da OS"
        )
    _validate_visible_close_code(plan, order)


def _validate_plan_conservation(
    plans: Any,
    orders_by_number: dict[str, dict[str, Any]],
    close_only_numbers: set[str],
    scheduled_date: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(plans, list):
        raise ControlledDryRunError("O planejador retornou uma colecao invalida")

    plan_numbers: list[str] = []
    plans_by_number: dict[str, dict[str, Any]] = {}
    for plan in plans:
        if not isinstance(plan, dict):
            raise ControlledDryRunError("O planejador retornou um plano invalido")
        number = _text(plan.get("num_os"))
        plan_numbers.append(number)
        if number in plans_by_number:
            raise ControlledDryRunError("O planejador duplicou uma OS")
        plans_by_number[number] = plan

    input_numbers = set(orders_by_number)
    if len(plans) != len(orders_by_number) or set(plan_numbers) != input_numbers:
        raise ControlledDryRunError(
            "O planejador omitiu, acrescentou ou substituiu uma OS"
        )

    planned_close_only_numbers = {
        number
        for number, plan in plans_by_number.items()
        if _text(plan.get("capability")) == "close_only"
    }
    if planned_close_only_numbers != close_only_numbers:
        raise ControlledDryRunError(
            "O planejador nao preservou exatamente as OS close_only"
        )

    if all(plan.get("ok") for plan in plans):
        for number, plan in plans_by_number.items():
            payload_order = _official_order(plan)
            _validate_order_fields(
                plan,
                payload_order,
                orders_by_number[number],
                scheduled_date,
            )
    return plans_by_number


def _validate_installed_serials(order: dict[str, Any]) -> None:
    installed = order.get("instaladosserializados")
    if not isinstance(installed, list):
        raise ControlledDryRunError("instaladosserializados deve ser uma lista")
    for item in installed:
        if not isinstance(item, dict) or set(item) != {"serialnumber"}:
            raise ControlledDryRunError(
                "Cada instalado deve possuir somente serialnumber"
            )
        serial = item.get("serialnumber")
        if not isinstance(serial, str) or not serial.strip():
            raise ControlledDryRunError("Serial instalado nao pode ser vazio")


def _valid_code_format(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)
    )


def _validate_materials(order: dict[str, Any]) -> None:
    materials = order.get("instaladosmiscelaneas")
    if not isinstance(materials, list):
        raise ControlledDryRunError("instaladosmiscelaneas deve ser uma lista")
    for material in materials:
        if not isinstance(material, dict):
            raise ControlledDryRunError("A lista de miscelaneas possui item invalido")
        code = material.get("codigoequipamento")
        quantity = material.get("qtd")
        if set(material) != {"codigoequipamento", "qtd"}:
            raise ControlledDryRunError(
                "Cada miscelanea deve possuir codigoequipamento e qtd"
            )
        if not _valid_code_format(code):
            raise ControlledDryRunError(
                "O formato do codigo da miscelanea e invalido"
            )
        if not isinstance(quantity, str) or not re.fullmatch(
            r"(?:0|[1-9]\d*)(?:\.\d+)?",
            quantity,
        ):
            raise ControlledDryRunError(
                f"A quantidade da miscelanea {code} deve ser uma string decimal"
            )
        try:
            parsed_quantity = Decimal(quantity)
        except InvalidOperation as error:
            raise ControlledDryRunError(
                f"A quantidade da miscelanea {code} deve ser uma string decimal"
            ) from error
        if not parsed_quantity.is_finite() or parsed_quantity <= 0:
            raise ControlledDryRunError(
                f"A quantidade da miscelanea {code} deve ser maior que zero"
            )


def _validate_removed_serials(order: dict[str, Any]) -> None:
    removed = order.get("removidosserializados")
    if not isinstance(removed, list):
        raise ControlledDryRunError("removidosserializados deve ser uma lista")
    for item in removed:
        if not isinstance(item, dict) or set(item) != {
            "codigoequipamento",
            "serialnumber",
        }:
            raise ControlledDryRunError(
                "Cada removido deve possuir codigoequipamento e serialnumber"
            )
        if not _valid_code_format(item.get("codigoequipamento")):
            raise ControlledDryRunError(
                "Equipamento removido deve possuir codigoequipamento concreto"
            )
        serial = item.get("serialnumber")
        if not isinstance(serial, str) or not serial.strip():
            raise ControlledDryRunError("Serial removido nao pode ser vazio")


def _validate_inventory(order: dict[str, Any]) -> None:
    _validate_installed_serials(order)
    _validate_materials(order)
    _validate_removed_serials(order)


def validate_single_official_payload(payload: Any) -> dict[str, Any]:
    """Validate and copy exactly one official close payload."""
    if not isinstance(payload, dict) or set(payload) != {"ordemservico"}:
        raise ControlledDryRunError(
            "O payload deve conter somente um objeto ordemservico"
        )

    order = payload.get("ordemservico")
    expected_fields = {
        "numero",
        "dataagendamento",
        "codigotecnico",
        "codigobaixa",
        "instaladosserializados",
        "instaladosmiscelaneas",
        "removidosserializados",
    }
    if not isinstance(order, dict) or set(order) != expected_fields:
        raise ControlledDryRunError(
            "ordemservico nao possui exatamente os campos oficiais esperados"
        )

    number = order.get("numero")
    if not isinstance(number, str) or not number.isdigit():
        raise ControlledDryRunError("numero deve ser uma string numerica")
    _validate_scheduled_date(order.get("dataagendamento"))

    technician = order.get("codigotecnico")
    if not isinstance(technician, str) or not technician.strip():
        raise ControlledDryRunError("codigotecnico deve ser uma string nao vazia")

    close_code = order.get("codigobaixa")
    if type(close_code) is not int or not 0 <= close_code <= 9999:
        raise ControlledDryRunError(
            "codigobaixa deve ser um numero inteiro visivel"
        )

    _validate_inventory(order)
    return copy.deepcopy(payload)


def _validate_close_only_inventory(order: dict[str, Any]) -> None:
    for field in (
        "instaladosserializados",
        "instaladosmiscelaneas",
        "removidosserializados",
    ):
        if order.get(field) != []:
            raise ControlledDryRunError(
                f"A OS close_only deve enviar {field} como lista vazia"
            )


def build_controlled_official_dry_run(
    review: dict[str, Any],
    orders: list[dict[str, Any]],
    scheduled_date: str,
    *,
    authorized_material_os: str,
) -> dict[str, Any]:
    """Build one authorized official request without exposing any send operation."""
    authorized_number = _text(authorized_material_os)
    if not authorized_number or not authorized_number.isdigit():
        raise ControlledDryRunError("Informe uma OS material_capable autorizada")

    if not isinstance(review, dict) or not isinstance(orders, list):
        raise ControlledDryRunError("Dados de entrada invalidos")
    _validate_confirmed_route(review)
    date_text = _validate_scheduled_date(scheduled_date)

    material_orders: list[dict[str, Any]] = []
    close_only_orders: list[dict[str, Any]] = []
    orders_by_number: dict[str, dict[str, Any]] = {}
    unsupported: list[str] = []
    for order in orders:
        if not isinstance(order, dict):
            unsupported.append("-")
            continue
        number = order.get("num_os")
        if not isinstance(number, str) or not number.isdigit():
            raise ControlledDryRunError(
                "Todo num_os de entrada deve ser uma string numerica"
            )
        if number in orders_by_number:
            raise ControlledDryRunError(
                f"Numero de OS duplicado na entrada: {number}"
            )
        orders_by_number[number] = order
        expected_capability = _service_capability(order.get("service"))
        capability = _text(order.get("capability"))
        if capability != expected_capability:
            raise ControlledDryRunError(
                f"A capacidade da OS {number} nao corresponde ao servico mapeado"
            )
        if capability == "material_capable":
            material_orders.append(order)
        elif capability == "close_only":
            close_only_orders.append(order)
        else:
            unsupported.append(_text(order.get("num_os")) or "-")
    if unsupported:
        raise ControlledDryRunError(
            "O contrato possui servico nao suportado neste teste: "
            + ", ".join(unsupported)
        )
    if len(material_orders) != 1:
        raise ControlledDryRunError(
            "O teste controlado exige exatamente uma OS material_capable"
        )
    if _text(material_orders[0].get("num_os")) != authorized_number:
        raise ControlledDryRunError(
            "A OS autorizada nao corresponde a unica OS material_capable do contrato"
        )

    plans = build_contract_official_plans(
        review,
        orders,
        date_text,
    )
    plans_by_number = _validate_plan_conservation(
        plans,
        orders_by_number,
        {_text(order.get("num_os")) for order in close_only_orders},
        date_text,
    )
    if not plans or any(not plan.get("ok") for plan in plans):
        blockers = sorted(
            {
                _text(blocker)
                for plan in plans
                for blocker in plan.get("blockers", [])
                if _text(blocker)
            }
        )
        raise ControlledDryRunError(
            "O planejamento oficial esta bloqueado: " + ", ".join(blockers or ["sem plano"])
        )

    close_only_plans = [
        plans_by_number[order["num_os"]] for order in close_only_orders
    ]
    material_plans = [plans_by_number[order["num_os"]] for order in material_orders]
    if len(material_plans) != 1:
        raise ControlledDryRunError(
            "O planejamento nao preservou a combinacao autorizada de OS"
        )

    material_plan = material_plans[0]
    if _text(material_plan.get("num_os")) != authorized_number:
        raise ControlledDryRunError(
            "A OS autorizada nao corresponde a unica OS material_capable do contrato"
        )

    material_order = _official_order(material_plan)
    if _text(material_order.get("numero")) != authorized_number:
        raise ControlledDryRunError(
            "O numero do JSON oficial nao corresponde a OS material_capable autorizada"
        )

    _validate_inventory(material_order)

    official_payload = material_plan["payload"]
    close_only_companions = []
    for close_only_plan in close_only_plans:
        close_only_order = _official_order(close_only_plan)
        _validate_inventory(close_only_order)
        _validate_close_only_inventory(close_only_order)
        close_only_companions.append({
            "send_authorized": False,
            "num_os": _text(close_only_plan.get("num_os")),
            "payload": close_only_plan["payload"],
        })
    return {
        "mode": "controlled_official_http_dry_run",
        "dry_run_only": True,
        "send_enabled": False,
        "human_confirmation_required": True,
        "human_confirmation_received": False,
        "authorized_request_limit": 1,
        "requests_sent": 0,
        "retry_enabled": False,
        "datasnap_fallback_enabled": False,
        "state_after_http_acceptance": "queued",
        "authorized_material_os": authorized_number,
        "imperium_current_status": {
            number: _text(order.get("imperium_current_status") or order.get("status"))
            for number, order in orders_by_number.items()
        },
        "validations": {
            "material_os_number_matches": True,
            "visible_close_code_preserved": True,
            "material_code_format_valid": True,
            "decimal_string_quantities_only": True,
            "installed_serial_shape_valid": True,
            "removed_serial_shape_valid": True,
            "close_only_inventory_lists_empty": True,
        },
        "official_payload_before_post": official_payload,
        "official_json_before_post": json.dumps(
            official_payload,
            ensure_ascii=False,
            indent=2,
        ),
        "close_only_companions": close_only_companions,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera um JSON oficial controlado sem realizar POST.",
    )
    parser.add_argument("input", type=Path, help="Fixture JSON com review, orders e data")
    arguments = parser.parse_args()
    source = json.loads(arguments.input.read_text(encoding="utf-8"))
    result = build_controlled_official_dry_run(
        source["review"],
        source["orders"],
        source["scheduled_date"],
        authorized_material_os=source["authorized_material_os"],
    )
    print(result["official_json_before_post"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
