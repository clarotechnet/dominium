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
import unicodedata
from typing import Any

from imperium_http_api import build_close_payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()


def _external_id(provider: Any) -> str:
    return _text(provider.get("external_id")).upper() if isinstance(provider, dict) else ""


def _item_point(item: Any) -> str:
    return _text(item.get("point")) if isinstance(item, dict) else ""


def _task_for_order(review: dict[str, Any], number: str) -> dict[str, Any] | None:
    matches = [
        task
        for task in review.get("tasks", [])
        if isinstance(task, dict) and _text(task.get("os_number")) == number
    ]
    return matches[0] if len(matches) == 1 else None


def _movement_points(review: dict[str, Any]) -> set[str]:
    points: set[str] = set()
    for field in ("installed_equipment", "removed_equipment", "materials"):
        for item in review.get(field, []):
            point = _item_point(item)
            if point:
                points.add(point)
    return points


def _belongs_to_order(
    item: dict[str, Any],
    order_point: str,
    *,
    sole_movement_point: str,
) -> bool:
    point = _item_point(item)
    if point:
        return point == order_point
    return bool(order_point and sole_movement_point == order_point)


def build_official_close_plan(
    review: dict[str, Any],
    order: dict[str, Any],
    scheduled_date: dt.date | str,
    *,
    allow_route_missing: bool = False,
) -> dict[str, Any]:
    number = _text(order.get("num_os"))
    contract = _text(order.get("contract"))
    point = _text(order.get("point"))
    warnings: list[str] = []
    blockers: list[str] = []

    if _text(review.get("contract")) != contract:
        blockers.append("contract_mismatch")
    task = _task_for_order(review, number)
    if task is None:
        blockers.append("task_not_found_or_duplicated")
        task = {}
    if _normalized(order.get("status")) != "em campo":
        blockers.append("order_not_open")
    if _normalized(review.get("activity_status")) not in {
        "complete",
        "completed",
        "concluido",
    }:
        blockers.append("toa_activity_not_complete")
    if review.get("validation_errors"):
        blockers.append("capture_validation_errors")

    decision = _text(review.get("decision"))
    reasons = {_text(value) for value in review.get("decision_reasons", [])}
    if decision == "blocked_manual_review":
        blockers.append("capture_blocked_manual_review")
    unsupported_reasons = reasons - {"route_not_confirmed"}
    if unsupported_reasons:
        blockers.append("capture_decision_requires_review")
    if "route_not_confirmed" in reasons:
        if allow_route_missing:
            warnings.append("route_missing_manually_accepted")
        else:
            blockers.append("route_not_confirmed")

    technician_code = _text(order.get("technician_login")).upper()
    if not technician_code:
        blockers.append("technician_login_missing")
    assigned_code = _external_id(review.get("assigned_technician"))
    if assigned_code and technician_code and assigned_code != technician_code:
        blockers.append("assigned_technician_login_mismatch")

    points = _movement_points(review)
    sole_movement_point = next(iter(points)) if len(points) == 1 else ""
    installed = [
        item
        for item in review.get("installed_equipment", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point, sole_movement_point=sole_movement_point)
    ]
    removed = [
        item
        for item in review.get("removed_equipment", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point, sole_movement_point=sole_movement_point)
    ]
    materials = [
        item
        for item in review.get("materials", [])
        if isinstance(item, dict)
        and _belongs_to_order(item, point, sole_movement_point=sole_movement_point)
    ]
    has_movement = bool(installed or removed or materials)
    if has_movement:
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
            continue
        installed_serials.append({"serialnumber": serial})

    installed_materials: list[dict[str, str]] = []
    for item in materials:
        code = _text(item.get("material_code"))
        quantity = _text(item.get("quantity"))
        if not code:
            blockers.append("material_code_missing")
            continue
        installed_materials.append({"codigoequipamento": code, "qtd": quantity})

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
        payload = build_close_payload(
            number=number,
            scheduled_date=date_text,
            technician_code=technician_code,
            close_code=close_code,
            installed_serials=installed_serials,
            installed_materials=installed_materials,
            removed_serials=removed_serials,
        )
    fingerprint = ""
    if payload is not None:
        fingerprint = hashlib.sha256(
            json.dumps(
                payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
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
        "point": point,
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
    *,
    allow_route_missing: bool = False,
) -> list[dict[str, Any]]:
    plans = [
        build_official_close_plan(
            review,
            order,
            scheduled_date,
            allow_route_missing=allow_route_missing,
        )
        for order in orders
    ]
    assigned_installed = sum(plan["installed_count"] for plan in plans)
    assigned_removed = sum(plan["removed_count"] for plan in plans)
    assigned_materials = sum(plan["material_count"] for plan in plans)
    expected = (
        len(review.get("installed_equipment", [])),
        len(review.get("removed_equipment", [])),
        len(review.get("materials", [])),
    )
    actual = (assigned_installed, assigned_removed, assigned_materials)
    if actual != expected:
        for plan in plans:
            plan["ok"] = False
            plan["payload"] = None
            plan["fingerprint"] = ""
            if "inventory_assignment_incomplete" not in plan["blockers"]:
                plan["blockers"].append("inventory_assignment_incomplete")
    return plans
