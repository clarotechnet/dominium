# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - contem validacao, consulta ou operacao ligada ao Imperium.
#
# TOA
# - SIM - contem captura, contexto, importacao ou evidencia vinda do TOA.
#
# DOMINIUM COMPARTILHADO
# - Ponte entre os dois dominios; alterar com testes dos dois lados.
#
# Categoria deste arquivo: MISTO.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
"""Read-only bridge from a TECHCAP capture to the official close dry-run.

The module accepts only local/injected data.  It does not contain an HTTP
client, retry logic, DataSnap fallback, credentials, or any send operation.
"""

from __future__ import annotations

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

from official_close_dry_run import (
    ControlledDryRunError,
    build_controlled_official_dry_run,
)
from material_matching import toa_material_ignore_reason
from toa_capture import CaptureSchemaError, TOACaptureLot


class TOAOfficialDryRunError(ValueError):
    """Raised when captured evidence cannot identify one safe dry-run."""


TASK_SLOTS = {
    "1": {"os": "193", "status": "194", "close_code": "195"},
    "2": {"os": "196", "status": "197", "close_code": "198"},
}
BENIGN_PLANNING_REASON = "imperium_payload_validation_required"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    return "".join(
        character for character in text if not unicodedata.combining(character)
    ).casefold()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _validate_date(value: Any) -> str:
    if not isinstance(value, str):
        raise TOAOfficialDryRunError("data deve estar no formato YYYY-MM-DD")
    try:
        if dt.date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as error:
        raise TOAOfficialDryRunError(
            "data deve estar no formato YYYY-MM-DD"
        ) from error
    return value


def _validate_contract(value: Any) -> str:
    contract = _text(value)
    if not contract.isdigit():
        raise TOAOfficialDryRunError("contrato deve ser numerico")
    return contract


def _load_json(path: str | Path) -> Any:
    source = Path(path).expanduser().resolve()
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise TOAOfficialDryRunError(
            f"nao foi possivel ler {source}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise TOAOfficialDryRunError(f"JSON invalido em {source}: {error}") from error


def _capture_lot(source: TOACaptureLot | dict[str, Any] | str | Path) -> TOACaptureLot:
    if isinstance(source, TOACaptureLot):
        return source
    try:
        if isinstance(source, dict):
            return TOACaptureLot.from_dict(copy.deepcopy(source))
        return TOACaptureLot.from_path(source)
    except CaptureSchemaError as error:
        raise TOAOfficialDryRunError(str(error)) from error


def _order_list(source: list[dict[str, Any]] | dict[str, Any] | str | Path) -> list[dict[str, Any]]:
    payload: Any = _load_json(source) if isinstance(source, (str, Path)) else source
    if isinstance(payload, dict):
        payload = payload.get("orders")
    if not isinstance(payload, list) or not all(
        isinstance(order, dict) for order in payload
    ):
        raise TOAOfficialDryRunError(
            "o indice de OS deve ser uma lista ou um objeto com a chave orders"
        )
    return copy.deepcopy(payload)


def _service_capability(service: Any) -> str:
    normalized = _normalized(service)
    capabilities = {
        "mudanca de pacote": "material_capable",
        "instalacao de cabo gpon": "close_only",
    }
    return capabilities.get(normalized, "unmapped")


def _toa_activity_is_complete(value: Any) -> bool:
    return _normalized(value) in {
        "complete",
        "completed",
        "concluida",
        "concluido",
        "executada",
        "executado",
    }


def _imperium_status_state(value: Any) -> str:
    normalized = _normalized(value)
    if normalized == "em campo":
        return "open"
    if normalized in {
        "baixada",
        "baixado",
        "cancelada",
        "cancelado",
        "concluida",
        "concluido",
        "finalizada",
        "finalizado",
    }:
        return "processed"
    return "unknown"


def _is_non_authoritative_toa_processing_marker(value: Any) -> bool:
    return _text(value) in {
        "already_processed",
        "activity_already_processed",
        "toa_already_processed",
    }


def _provider_login(provider: Any) -> str:
    if not isinstance(provider, dict):
        return ""
    return _text(provider.get("external_id") or provider.get("login")).upper()


def _provider_name(provider: Any) -> str:
    return _text(provider.get("name")) if isinstance(provider, dict) else ""


def _order_login(order: dict[str, Any]) -> str:
    return _text(
        order.get("technician_login")
        or order.get("technician_external_id")
        or order.get("external_id")
    ).upper()


def _order_name(order: dict[str, Any]) -> str:
    return _text(order.get("technician_name") or order.get("installer_name"))


def _decimal_quantity(value: Any) -> tuple[str, Decimal] | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:0|[1-9]\d*)(?:\.\d+)?", value
    ):
        return None
    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None
    if not decimal_value.is_finite() or decimal_value <= 0:
        return None
    return value, decimal_value


def _item_code(item: dict[str, Any]) -> str:
    return _text(
        item.get("material_code")
        or item.get("equipment_code")
        or item.get("code")
    )


def _inventory_view(item: dict[str, Any]) -> dict[str, Any]:
    legacy_quantity = _text(item.get("quantity"))
    # Confirmado na tela real: Inventory.quantity e a quantidade usada.
    # Ele prevalece sobre campos derivados por coletores anteriores.
    used_quantity = legacy_quantity or _text(item.get("used_quantity"))
    available_stock = _text(
        item.get("quantity_stock")
        or item.get("stock_quantity")
        or (
            item.get("available_stock")
            if _text(item.get("available_stock_source"))
            in {"imperium_quantity_stock", "imperium_quantidade_estoque"}
            else ""
        )
    )
    return {
        "invid": _text(item.get("invid")),
        "activity_id": _text(item.get("activity_id")),
        "point": _text(item.get("point")),
        "serial": _text(item.get("serial")),
        "equipment_code": _item_code(item),
        "used_quantity": used_quantity,
        "available_stock": available_stock,
        "description": _text(item.get("description") or item.get("type")),
    }


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    source_fields = task.get("source_fields")
    return {
        "index": _text(task.get("index")),
        "os_number": _text(task.get("os_number")),
        "status": _text(task.get("status")),
        "close_code": _text(task.get("close_code")),
        "point": _text(task.get("point") or task.get("property_335") or task.get("335")),
        "source_fields": copy.deepcopy(source_fields)
        if isinstance(source_fields, dict)
        else {},
    }


def _prepare_inspection(
    capture_source: TOACaptureLot | dict[str, Any] | str | Path,
    orders_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    contract: Any,
    scheduled_date: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    contract_text = _validate_contract(contract)
    date_text = _validate_date(scheduled_date)
    lot = _capture_lot(capture_source)
    indexed_orders = _order_list(orders_source)
    blockers = list(lot.validation_errors)
    alerts = list(lot.validation_warnings)
    matches = lot.find_contract(contract_text)

    inspection: dict[str, Any] = {
        "stage": "inspection",
        "dry_run_only": True,
        "authorization_granted": False,
        "contract": contract_text,
        "scheduled_date": date_text,
        "aid": "",
        "city": "",
        "work_type": "",
        "activity_status": "",
        "imperium_current_status": {},
        "technician": {"login": "", "name": ""},
        "route_provider": {"login": "", "name": ""},
        "inventory_providers": [],
        "form_submitters": [],
        "orders": [],
        "alerts": [],
        "blockers": [],
        "ok": False,
    }
    if len(matches) != 1:
        blockers.append(
            "contract_not_found" if not matches else "contract_has_multiple_activities"
        )
        inspection["alerts"] = _unique(alerts)
        inspection["blockers"] = _unique(blockers)
        return inspection, None, []

    review = matches[0].to_dict()
    aid = _text(review.get("aid"))
    inspection.update(
        {
            "aid": aid,
            "city": _text(review.get("city")),
            "work_type": _text(review.get("work_type")),
            "activity_status": _text(review.get("activity_status")),
        }
    )
    review_errors = [
        _text(value)
        for value in review.get("validation_errors", [])
        if not _is_non_authoritative_toa_processing_marker(value)
    ]
    if _toa_activity_is_complete(review.get("activity_status")):
        review_errors = [
            value for value in review_errors if value != "activity_not_complete"
        ]
    blockers.extend(review_errors)
    alerts.extend(_text(value) for value in review.get("validation_warnings", []))
    if _text(review.get("contract")) != contract_text:
        blockers.append("activity_contract_mismatch")
    captured_date = _text(review.get("scheduled_date"))
    if captured_date and captured_date != date_text:
        blockers.append("scheduled_date_mismatch")

    assigned = review.get("assigned_technician")
    route = review.get("route_provider")
    assigned_login = _provider_login(assigned)
    assigned_name = _provider_name(assigned)
    route_login = _provider_login(route)
    route_name = _provider_name(route)
    inspection["technician"] = {
        "login": assigned_login,
        "name": assigned_name,
    }
    inspection["route_provider"] = {
        "login": route_login,
        "name": route_name,
    }
    inspection["inventory_providers"] = copy.deepcopy(
        review.get("inventory_providers", [])
    )
    inspection["form_submitters"] = copy.deepcopy(
        review.get("form_submitters", [])
    )
    if not assigned_login:
        blockers.append("assigned_technician_login_missing")
    if not route_login:
        blockers.append("route_missing")
    if isinstance(route, dict):
        candidates = route.get("candidates")
        if route.get("ambiguous") is True or (
            isinstance(candidates, list) and len(candidates) > 1
        ):
            blockers.append("route_ambiguous")
    if "route_not_confirmed" in review.get("decision_reasons", []):
        blockers.append("route_not_confirmed")
    if assigned_login and route_login and assigned_login != route_login:
        blockers.append("route_technician_login_mismatch")
    if (
        assigned_login
        and route_login == assigned_login
        and assigned_name
        and route_name
        and _normalized(assigned_name) != _normalized(route_name)
    ):
        alerts.append(
            f"technician_name_spelling_diff:{assigned_name}:{route_name}"
        )

    all_orders_by_number: dict[str, dict[str, Any]] = {}
    for order in indexed_orders:
        number = _text(order.get("num_os"))
        if not number or not number.isdigit():
            blockers.append("indexed_order_number_invalid")
            continue
        if number in all_orders_by_number:
            blockers.append(f"indexed_order_duplicate:{number}")
            continue
        all_orders_by_number[number] = order

    task_numbers: set[str] = set()
    matched_orders: list[dict[str, Any]] = []
    order_views: list[dict[str, Any]] = []
    for raw_task in review.get("tasks", []):
        if not isinstance(raw_task, dict):
            blockers.append("task_invalid")
            continue
        task = _task_view(raw_task)
        number = task["os_number"]
        index = task["index"]
        if not number or not number.isdigit():
            blockers.append("task_os_number_invalid")
            continue
        if number in task_numbers:
            blockers.append(f"task_os_duplicate:{number}")
            continue
        task_numbers.add(number)
        expected_slots = TASK_SLOTS.get(index)
        if expected_slots is None or task["source_fields"] != expected_slots:
            blockers.append(f"task_source_slots_invalid:{number}")
        order = all_orders_by_number.get(number)
        if order is None:
            blockers.append(f"task_order_not_found:{number}")
            continue
        if _text(order.get("contract")) != contract_text:
            blockers.append(f"task_order_contract_mismatch:{number}")
        point = _text(order.get("point"))
        if not point:
            blockers.append(f"order_point_missing:{number}")
        task_point = task["point"] or point
        if task["point"] and task["point"] != point:
            blockers.append(f"task_order_point_mismatch:{number}")
        service = _text(order.get("service"))
        capability = _service_capability(service)
        if capability == "unmapped":
            blockers.append(f"service_capability_unmapped:{number}")
        imperium_current_status = _text(
            order.get("imperium_current_status") or order.get("status")
        )
        status_state = _imperium_status_state(imperium_current_status)
        if status_state == "processed":
            blockers.append(f"already_processed:{number}")
        elif status_state != "open":
            blockers.append(f"imperium_status_not_open:{number}")
        inspection["imperium_current_status"][number] = imperium_current_status
        login = _order_login(order)
        name = _order_name(order)
        if not login:
            blockers.append(f"order_technician_login_missing:{number}")
        if assigned_login and login and login != assigned_login:
            blockers.append(f"order_technician_login_mismatch:{number}")
        if route_login and login and login != route_login:
            blockers.append(f"order_route_login_mismatch:{number}")
        if (
            assigned_login
            and login == assigned_login
            and assigned_name
            and name
            and _normalized(assigned_name) != _normalized(name)
        ):
            alerts.append(f"technician_name_spelling_diff:{assigned_name}:{name}")
        order_copy = copy.deepcopy(order)
        order_copy["num_os"] = number
        order_copy["technician_login"] = login
        order_copy["capability"] = capability
        order_copy["imperium_current_status"] = imperium_current_status
        matched_orders.append(order_copy)
        order_views.append(
            {
                "num_os": number,
                "capability": capability,
                "service": service,
                "point": point,
                "task_point": task_point,
                "imperium_current_status": imperium_current_status,
                "task_index": index,
                "source_fields": task["source_fields"],
                "task_status": task["status"],
                "close_code": task["close_code"],
                "technician_login": login,
                "technician_name": name,
                "installed_equipment": [],
                "removed_equipment": [],
                "materials": [],
            }
        )

    if set(task_numbers) != {_text(order.get("num_os")) for order in matched_orders}:
        blockers.append("task_order_plan_partial")
    material_views = [
        order
        for order in order_views
        if order["capability"] == "material_capable"
    ]
    if len(material_views) != 1:
        blockers.append("material_capable_order_count_invalid")
    points = [order["task_point"] for order in order_views if order["task_point"]]
    if len(points) != len(set(points)):
        blockers.append("order_points_duplicate")
    orders_by_point = {
        order["task_point"]: order
        for order in order_views
        if order["task_point"]
    }

    ignored_materials: list[dict[str, Any]] = []
    seen_invids: set[str] = set()
    for field in ("installed_equipment", "removed_equipment", "materials"):
        values = review.get(field, [])
        if not isinstance(values, list):
            blockers.append(f"{field}_not_a_list")
            continue
        for position, raw_item in enumerate(values):
            if not isinstance(raw_item, dict):
                blockers.append(f"{field}_item_invalid:{position}")
                continue
            item = _inventory_view(raw_item)
            invid = item["invid"]
            if not invid:
                blockers.append(f"inventory_invid_missing:{field}:{position}")
            elif invid in seen_invids:
                blockers.append(f"inventory_invid_duplicate:{invid}")
            else:
                seen_invids.add(invid)
            if item["activity_id"] != aid:
                blockers.append(f"inventory_aid_mismatch:{invid or position}")
            if field == "materials":
                ignore_reason = toa_material_ignore_reason(
                    item["description"],
                    item["equipment_code"],
                )
                if ignore_reason:
                    ignored_materials.append(
                        {
                            **item,
                            "ignore_reason": ignore_reason,
                            "source": "toa_capture",
                        }
                    )
                    alerts.append(
                        f"material_ignored_by_operational_rule:"
                        f"{item['equipment_code'] or invid or position}:{ignore_reason}"
                    )
                    continue
            if not item["point"]:
                blockers.append(f"inventory_point_335_missing:{invid or position}")
                continue
            target = orders_by_point.get(item["point"])
            if target is None:
                blockers.append(f"inventory_point_unmatched:{invid or position}")
                continue
            if field == "materials":
                if not item["equipment_code"]:
                    blockers.append(f"material_code_missing:{invid or position}")
                if not item["used_quantity"]:
                    blockers.append(
                        f"material_used_quantity_missing:{invid or position}"
                    )
                elif _decimal_quantity(item["used_quantity"]) is None:
                    blockers.append(
                        f"material_used_quantity_invalid:{invid or position}"
                    )
                if target["capability"] == "close_only":
                    blockers.append(f"material_assigned_to_close_only:{invid or position}")
            elif field == "installed_equipment":
                if not item["serial"]:
                    blockers.append(f"installed_serial_missing:{invid or position}")
                if target["capability"] == "close_only":
                    blockers.append(f"equipment_assigned_to_close_only:{invid or position}")
            elif field == "removed_equipment":
                if not item["serial"]:
                    blockers.append(f"removed_serial_missing:{invid or position}")
                if not item["equipment_code"]:
                    blockers.append(f"removed_equipment_code_missing:{invid or position}")
                if target["capability"] == "close_only":
                    blockers.append(f"equipment_assigned_to_close_only:{invid or position}")
            target[field].append(item)

    inspection["orders"] = order_views
    inspection["ignored_materials"] = ignored_materials
    inspection["alerts"] = _unique(alerts)
    inspection["blockers"] = _unique(blockers)
    inspection["ok"] = not inspection["blockers"]
    return inspection, review, matched_orders


def inspect_toa_contract(
    capture_source: TOACaptureLot | dict[str, Any] | str | Path,
    orders_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    contract: Any,
    scheduled_date: Any,
) -> dict[str, Any]:
    """Inspect one contract without authorizing or producing an official JSON."""
    inspection, _, _ = _prepare_inspection(
        capture_source,
        orders_source,
        contract,
        scheduled_date,
    )
    return inspection


def _material_totals_from_inspection(
    order_view: dict[str, Any],
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    by_code: dict[str, Decimal] = {}
    by_invid: dict[str, Decimal] = {}
    for item in order_view["materials"]:
        parsed = _decimal_quantity(item["used_quantity"])
        if parsed is None:
            raise TOAOfficialDryRunError("quantidade de material invalida")
        _, quantity = parsed
        code = item["equipment_code"]
        by_code[code] = by_code.get(code, Decimal("0")) + quantity
        by_invid[item["invid"]] = quantity
    return by_code, by_invid


def _payload_material_totals(payload_order: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for item in payload_order["instaladosmiscelaneas"]:
        parsed = _decimal_quantity(item.get("qtd"))
        if parsed is None:
            raise TOAOfficialDryRunError("payload alterou a quantidade de material")
        _, quantity = parsed
        code = _text(item.get("codigoequipamento"))
        result[code] = result.get(code, Decimal("0")) + quantity
    return result


def _validate_payload_conservation(
    inspection: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    material_order = next(
        order
        for order in inspection["orders"]
        if order["capability"] == "material_capable"
    )
    official_order = payload["ordemservico"]
    expected_installed = [
        {"serialnumber": item["serial"].upper()}
        for item in material_order["installed_equipment"]
    ]
    expected_removed = [
        {
            "codigoequipamento": item["equipment_code"],
            "serialnumber": item["serial"].upper(),
        }
        for item in material_order["removed_equipment"]
    ]
    if official_order.get("instaladosserializados") != expected_installed:
        raise TOAOfficialDryRunError("o payload nao conservou os seriais instalados")
    if official_order.get("removidosserializados") != expected_removed:
        raise TOAOfficialDryRunError("o payload nao conservou os seriais removidos")
    material_totals, material_by_invid = _material_totals_from_inspection(
        material_order
    )
    if _payload_material_totals(official_order) != material_totals:
        raise TOAOfficialDryRunError("o payload nao conservou as miscelaneas")
    return {
        "installed_items": len(expected_installed),
        "removed_items": len(expected_removed),
        "material_items": len(material_by_invid),
        "material_invid_quantities": {
            invid: format(quantity, "f")
            for invid, quantity in material_by_invid.items()
        },
    }


def build_authorized_toa_dry_run(
    capture_source: TOACaptureLot | dict[str, Any] | str | Path,
    orders_source: list[dict[str, Any]] | dict[str, Any] | str | Path,
    contract: Any,
    scheduled_date: Any,
    *,
    authorized_material_os: Any,
    output_dir: str | Path = ".",
) -> dict[str, Any]:
    """Generate one local official JSON after explicit material-OS authorization."""
    inspection, review, matched_orders = _prepare_inspection(
        capture_source,
        orders_source,
        contract,
        scheduled_date,
    )
    if not inspection["ok"] or review is None:
        raise TOAOfficialDryRunError(
            "inspecao bloqueada: " + ", ".join(inspection["blockers"])
        )
    material_orders = [
        order
        for order in inspection["orders"]
        if order["capability"] == "material_capable"
    ]
    authorized_number = _text(authorized_material_os)
    if len(material_orders) != 1 or authorized_number != material_orders[0]["num_os"]:
        raise TOAOfficialDryRunError(
            "authorized_material_os nao corresponde a unica OS material_capable"
        )

    planning_review = copy.deepcopy(review)
    planning_review["materials"] = [
        material
        for material in planning_review.get("materials", [])
        if not toa_material_ignore_reason(
            _text(material.get("description") or material.get("type")),
            _item_code(material),
        )
    ]
    for material in planning_review.get("materials", []):
        used_quantity = _text(
            material.get("quantity") or material.get("used_quantity")
        )
        if _decimal_quantity(used_quantity) is None:
            raise TOAOfficialDryRunError(
                "quantidade utilizada de material ausente ou invalida"
            )
        material["used_quantity"] = used_quantity
        material["quantity"] = used_quantity
    planning_review["decision_reasons"] = [
        reason
        for reason in planning_review.get("decision_reasons", [])
        if reason != BENIGN_PLANNING_REASON
        and not _is_non_authoritative_toa_processing_marker(reason)
        and not (
            reason == "activity_not_complete"
            and _toa_activity_is_complete(planning_review.get("activity_status"))
        )
    ]
    if _toa_activity_is_complete(planning_review.get("activity_status")):
        planning_review["validation_errors"] = [
            reason
            for reason in planning_review.get("validation_errors", [])
            if reason != "activity_not_complete"
            and not _is_non_authoritative_toa_processing_marker(reason)
        ]
    try:
        controlled = build_controlled_official_dry_run(
            planning_review,
            matched_orders,
            inspection["scheduled_date"],
            authorized_material_os=authorized_number,
        )
    except ControlledDryRunError as error:
        raise TOAOfficialDryRunError(str(error)) from error

    payload = controlled["official_payload_before_post"]
    conservation = _validate_payload_conservation(inspection, payload)
    official_json = controlled["official_json_before_post"]
    fingerprint = hashlib.sha256(official_json.encode("utf-8")).hexdigest()
    output_directory = Path(output_dir).expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / (
        f"DRY_RUN_{inspection['contract']}_{authorized_number}.json"
    )
    output_path.write_text(official_json, encoding="utf-8")
    saved_payload = json.loads(output_path.read_text(encoding="utf-8"))
    if set(saved_payload) != {"ordemservico"} or saved_payload != payload:
        raise TOAOfficialDryRunError("o arquivo dry-run nao preservou o payload oficial")

    summary = {
        "contract": inspection["contract"],
        "aid": inspection["aid"],
        "authorized_material_os": authorized_number,
        "imperium_current_status": inspection["imperium_current_status"],
        "close_only_payloads": [
            companion["payload"]
            for companion in controlled["close_only_companions"]
        ],
        "scheduled_date": inspection["scheduled_date"],
        "technician_login": inspection["technician"]["login"],
        "close_code": payload["ordemservico"]["codigobaixa"],
        "alerts": inspection["alerts"],
        "conservation": conservation,
        "message": "Modo dry-run: nenhuma operacao foi enviada ao Imperium.",
    }
    human_summary = (
        f"Contrato {inspection['contract']} | AID {inspection['aid']} | "
        f"OS material_capable {authorized_number} | codigo "
        f"{payload['ordemservico']['codigobaixa']} | tecnico "
        f"{inspection['technician']['login']} | "
        f"{conservation['installed_items']} instalado(s), "
        f"{conservation['removed_items']} removido(s), "
        f"{conservation['material_items']} material(is) | dry_run_only=true"
    )
    return {
        "mode": "toa_official_close_dry_run",
        "dry_run_only": True,
        "send_enabled": False,
        "inspection": inspection,
        "official_payload": payload,
        "official_json": official_json,
        "fingerprint_sha256": fingerprint,
        "output_path": str(output_path),
        "summary": summary,
        "human_summary": human_summary,
    }


def _print_inspection(inspection: dict[str, Any]) -> None:
    print(f"Contrato: {inspection['contract']} | AID: {inspection['aid'] or '-'}")
    print(f"Data: {inspection['scheduled_date']} | dry_run_only=true")
    print(
        f"Tecnico: {inspection['technician']['login'] or '-'} "
        f"({inspection['technician']['name'] or '-'}) | "
        f"rota: {inspection['route_provider']['login'] or '-'}"
    )
    for order in inspection["orders"]:
        print(
            f"OS {order['num_os']} | {order['capability']} | "
            f"Imperium {order['imperium_current_status'] or '-'} | "
            f"ponto {order['point'] or '-'} "
            f"| codigo {order['close_code'] or '-'} | {order['service']}"
        )
        print(
            f"  slots={order['source_fields']} tecnico={order['technician_login'] or '-'} "
            f"materiais={len(order['materials'])} instalados={len(order['installed_equipment'])} "
            f"removidos={len(order['removed_equipment'])}"
        )
        for item in order["installed_equipment"]:
            print(
                f"  INSTALADO invid={item['invid']} ponto={item['point']} "
                f"serial={item['serial']}"
            )
        for item in order["removed_equipment"]:
            print(
                f"  REMOVIDO invid={item['invid']} ponto={item['point']} "
                f"codigo={item['equipment_code']} serial={item['serial']}"
            )
        for item in order["materials"]:
            print(
                f"  MATERIAL invid={item['invid']} ponto={item['point']} "
                f"codigo={item['equipment_code']} qtd_usada={item['used_quantity']} "
                f"saldo={item['available_stock'] or '-'}"
            )
    for alert in inspection["alerts"]:
        print(f"ALERTA: {alert}")
    for blocker in inspection["blockers"]:
        print(f"BLOQUEIO: {blocker}")
    print("Autorizacao automatica: nao")


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspeciona captura TECHCAP e gera somente dry-run local."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "dry-run"):
        command = subparsers.add_parser(name)
        command.add_argument("--capture", required=True, type=Path)
        command.add_argument("--orders", required=True, type=Path)
        command.add_argument("--contract", required=True)
        command.add_argument("--date", required=True)
        if name == "dry-run":
            command.add_argument("--authorized-material-os", required=True)
            command.add_argument("--output-dir", type=Path, default=Path("."))
    arguments = parser.parse_args()
    if arguments.command == "inspect":
        inspection = inspect_toa_contract(
            arguments.capture,
            arguments.orders,
            arguments.contract,
            arguments.date,
        )
        _print_inspection(inspection)
        return 0 if inspection["ok"] else 2

    result = build_authorized_toa_dry_run(
        arguments.capture,
        arguments.orders,
        arguments.contract,
        arguments.date,
        authorized_material_os=arguments.authorized_material_os,
        output_dir=arguments.output_dir,
    )
    _print_inspection(result["inspection"])
    print(result["official_json"])
    print(result["human_summary"])
    print(f"SHA-256: {result['fingerprint_sha256']}")
    print(f"Arquivo: {result['output_path']}")
    print(result["summary"]["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
