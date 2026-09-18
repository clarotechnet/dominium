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
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from official_material_catalog import (
    OfficialMaterialCatalog,
    load_xlsx_catalog,
    normalize_description,
    normalize_identifier,
)


AUDIT_SCHEMA = "dominium_official_stock_audit_v1"
CAPTURE_SCHEMA = "dominium_official_stock_read_capture_v1"
EXPECTED_INSTALLER_ID = 328898
DEFAULT_CODES = (
    "22061736",
    "22069613",
    "22025072",
    "22064608",
    "22056332",
    "22056343",
    "22056341",
    "22056344",
    "22057659",
    "22065719",
    "22065725",
    "22065720",
)
TECHNICIAN_SOURCE = (
    "Imperium DataSnap read / TDtmMovEstoque.AS_GetRecords / DspConEst1"
)
STOCK_SOURCE = (
    "Imperium DataSnap read / TDtmEquipamentos.AS_GetRecords / "
    "DspListaEquiEstoque"
)


class StockAuditError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _decimal_text(value: object, label: str) -> str:
    try:
        number = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise StockAuditError(f"{label} invalida") from exc
    if not number.is_finite() or number < 0:
        raise StockAuditError(f"{label} invalida")
    result = format(number, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return result or "0"


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise StockAuditError(f"{label} invalido")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise StockAuditError(f"{label} invalido") from exc
    if result <= 0:
        raise StockAuditError(f"{label} invalido")
    return result


def _copy_json(value: object) -> object:
    return json.loads(json.dumps(value))


def _catalog_description(
    catalog: OfficialMaterialCatalog,
    code: str,
) -> tuple[str | None, list[str], list[dict]]:
    entry = catalog.lookup_code(code)
    if entry is None:
        return None, [], []
    descriptions = list(entry.get("descriptions", []))
    critical = [
        error
        for error in catalog.critical_errors
        if str(error.get("code", "")).strip() == code
    ]
    description = descriptions[0] if len(descriptions) == 1 else None
    return description, descriptions, _copy_json(critical)


def _validate_capture(
    capture: dict,
    *,
    installer_id: int,
) -> tuple[int, dict, list[str]]:
    if capture.get("schema") != CAPTURE_SCHEMA:
        raise StockAuditError("Schema da captura de estoque invalido")
    captured_installer_id = _positive_integer(
        capture.get("installer_id"),
        "installer_id da captura",
    )
    if captured_installer_id != installer_id:
        raise StockAuditError(
            "A captura nao pertence ao installer_id solicitado"
        )

    technicians = capture.get("technicians")
    if not isinstance(technicians, list):
        raise StockAuditError("Lista DspConEst1 invalida")
    exact_matches = [
        item
        for item in technicians
        if isinstance(item, dict)
        and int(item.get("installer_id", 0) or 0) == installer_id
    ]
    if len(exact_matches) != 1:
        raise StockAuditError(
            "DspConEst1 deve retornar exatamente um estoque para "
            f"installer_id {installer_id}"
        )
    technician = exact_matches[0]
    stock_id = _positive_integer(
        technician.get("stock_id"),
        "stock_id do DspConEst1",
    )

    stock = capture.get("stock")
    if not isinstance(stock, dict):
        raise StockAuditError("Resposta DspListaEquiEstoque invalida")
    stock_technician = stock.get("technician")
    if not isinstance(stock_technician, dict):
        raise StockAuditError(
            "DspListaEquiEstoque nao preservou o tecnico consultado"
        )
    if int(stock_technician.get("installer_id", 0) or 0) != installer_id:
        raise StockAuditError(
            "installer_id diverge entre DspConEst1 e DspListaEquiEstoque"
        )
    if int(stock_technician.get("stock_id", 0) or 0) != stock_id:
        raise StockAuditError(
            "stock_id diverge entre DspConEst1 e DspListaEquiEstoque"
        )
    items = stock.get("items")
    if not isinstance(items, list):
        raise StockAuditError("Itens DspListaEquiEstoque invalidos")
    return stock_id, stock, []


def build_stock_audit_report(
    catalog: OfficialMaterialCatalog,
    capture: dict,
    *,
    requested_codes: Iterable[object] = DEFAULT_CODES,
    installer_id: int = EXPECTED_INSTALLER_ID,
) -> dict:
    installer_id = _positive_integer(installer_id, "installer_id")
    codes = [
        normalize_identifier(code, "Codigo de auditoria")
        for code in requested_codes
    ]
    if len(codes) != len(set(codes)):
        raise StockAuditError("A lista de codigos possui duplicidade")

    stock_id, stock, warnings = _validate_capture(
        capture,
        installer_id=installer_id,
    )
    profile = str(capture.get("profile", "")).strip()
    read_at = str(capture.get("read_at", "")).strip()
    if not profile or not read_at:
        raise StockAuditError("Perfil ou horario da leitura ausente")

    items_by_code: dict[str, list[dict]] = {}
    for raw_item in stock["items"]:
        if not isinstance(raw_item, dict):
            continue
        code = normalize_identifier(
            raw_item.get("code"),
            "Codigo do estoque",
            allow_empty=True,
        )
        if code:
            items_by_code.setdefault(code, []).append(raw_item)

    rows = []
    for code in codes:
        official_description, catalog_descriptions, catalog_errors = (
            _catalog_description(catalog, code)
        )
        stock_items = items_by_code.get(code, [])
        row = {
            "code": code,
            "official_description": official_description,
            "catalog_descriptions": catalog_descriptions,
            "equipment_id": None,
            "installer_id": installer_id,
            "stock_id": stock_id,
            "available_quantity": None,
            "unit": None,
            "profile": profile,
            "source": STOCK_SOURCE,
            "read_at": read_at,
            "status": "ausente",
            "evidence": [],
            "divergences": [],
        }

        if catalog_errors:
            row["status"] = "divergente"
            row["divergences"].append(
                "catalog_code_has_divergent_descriptions"
            )
        if len(stock_items) > 1:
            row["status"] = "divergente"
            row["divergences"].append(
                "multiple_stock_rows_for_exact_code"
            )
        elif len(stock_items) == 1:
            item = stock_items[0]
            row["equipment_id"] = _positive_integer(
                item.get("equipment_id"),
                f"equipment_id de {code}",
            )
            row["available_quantity"] = _decimal_text(
                item.get("quantity"),
                f"Quantidade disponivel de {code}",
            )
            row["unit"] = str(item.get("unit", "")).strip() or None
            stock_description = str(item.get("equipment", "")).strip()
            row["stock_description"] = stock_description
            row["evidence"].append("exact_concrete_code_match")

            if official_description is None:
                row["status"] = "divergente"
                row["divergences"].append(
                    "official_catalog_description_not_unique"
                )
            elif (
                normalize_description(stock_description)
                != normalize_description(official_description)
            ):
                row["status"] = "divergente"
                row["divergences"].append(
                    "stock_description_differs_from_official_catalog"
                )
            elif row["unit"] is None:
                row["status"] = "divergente"
                row["divergences"].append("stock_unit_missing")
            elif Decimal(row["available_quantity"]) == 0:
                row["status"] = "sem saldo"
            else:
                row["status"] = "encontrado"

        if not catalog_descriptions:
            row["status"] = "divergente"
            row["divergences"].append("code_absent_from_official_catalog")
        rows.append(row)

    blockers = [
        f"stock_audit_{row['status']}:{row['code']}"
        for row in rows
        if row["status"] != "encontrado"
    ]
    unrelated_catalog_errors = [
        _copy_json(error)
        for error in catalog.critical_errors
        if str(error.get("code", "")).strip() not in set(codes)
    ]
    if unrelated_catalog_errors:
        warnings.append(
            "unrelated_official_catalog_critical_errors:"
            f"{len(unrelated_catalog_errors)}"
        )

    return {
        "schema": AUDIT_SCHEMA,
        "mode": "read_only_stock_audit",
        "installer_id": installer_id,
        "stock_id": stock_id,
        "profile": profile,
        "read_at": read_at,
        "sources": {
            "installer_stock_mapping": TECHNICIAN_SOURCE,
            "stock_items": STOCK_SOURCE,
        },
        "requested_codes": codes,
        "materials": rows,
        "blockers": blockers,
        "warnings": warnings,
        "unrelated_catalog_errors": unrelated_catalog_errors,
        "aliases_created": [],
        "payload_generated": False,
        "safety": {
            "read_only": True,
            "post_executed": False,
            "datasnap_write_executed": False,
            "stock_movement_executed": False,
        },
    }


def collect_read_capture(
    api: object,
    *,
    installer_id: int,
    profile: str,
    read_at: str | None = None,
) -> dict:
    installer_id = _positive_integer(installer_id, "installer_id")
    technicians = api.list_stock_technicians()
    exact_matches = [
        item
        for item in technicians
        if int(item.get("installer_id", 0) or 0) == installer_id
    ]
    if len(exact_matches) != 1:
        raise StockAuditError(
            "DspConEst1 deve retornar exatamente um estoque para "
            f"installer_id {installer_id}"
        )
    stock_id = _positive_integer(
        exact_matches[0].get("stock_id"),
        "stock_id do DspConEst1",
    )
    stock = api.technician_stock(stock_id)
    return {
        "schema": CAPTURE_SCHEMA,
        "profile": str(profile).strip(),
        "installer_id": installer_id,
        "read_at": read_at or _now_iso(),
        "sources": {
            "installer_stock_mapping": TECHNICIAN_SOURCE,
            "stock_items": STOCK_SOURCE,
        },
        "technicians": [_copy_json(exact_matches[0])],
        "stock": _copy_json(stock),
    }


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def render_stock_report_text(report: dict) -> str:
    lines = [
        "AUDITORIA SOMENTE LEITURA DE ESTOQUE OFICIAL",
        "",
        f"Perfil: {report['profile']}",
        f"Installer ID: {report['installer_id']}",
        f"Stock ID: {report['stock_id']}",
        f"Leitura: {report['read_at']}",
        f"Fonte tecnico: {report['sources']['installer_stock_mapping']}",
        f"Fonte estoque: {report['sources']['stock_items']}",
        "",
    ]
    for material in report["materials"]:
        lines.extend(
            [
                f"{material['code']} | {material['status'].upper()}",
                f"  Oficial: {material['official_description'] or '-'}",
                f"  Id interno: {material['equipment_id'] or '-'}",
                (
                    "  Disponivel: "
                    f"{material['available_quantity'] or '-'} "
                    f"{material['unit'] or ''}"
                ).rstrip(),
                (
                    "  Divergencias: "
                    f"{', '.join(material['divergences']) or '-'}"
                ),
            ]
        )
    lines.extend(["", "BLOCKERS"])
    lines.extend(f"- {value}" for value in report["blockers"])
    lines.extend(["", "WARNINGS"])
    lines.extend(f"- {value}" for value in report["warnings"])
    lines.extend(
        [
            "",
            "Nenhum payload foi produzido.",
            "Nenhum POST, escrita DataSnap ou movimentacao foi executado.",
        ]
    )
    return "\n".join(lines) + "\n"


def _capture_live(args: argparse.Namespace) -> int:
    expected = f"LER-ESTOQUE-{args.installer_id}"
    if args.confirm != expected:
        raise StockAuditError(
            f"Confirmacao literal exigida: {expected}"
        )
    from imperium_api import ImperiumAPI

    api = ImperiumAPI(
        Path(__file__).resolve().parent,
        port=args.port,
        company=args.profile,
        profile_key=args.profile_key,
    )
    capture = collect_read_capture(
        api,
        installer_id=args.installer_id,
        profile=args.profile,
    )
    _write_json_atomic(Path(args.output), capture)
    print(json.dumps({"capture": args.output, "read_only": True}))
    return 0


def _report(args: argparse.Namespace) -> int:
    catalog = load_xlsx_catalog(args.catalog_xlsx)
    capture = json.loads(
        Path(args.capture).read_text(encoding="utf-8")
    )
    report = build_stock_audit_report(
        catalog,
        capture,
        installer_id=args.installer_id,
    )
    _write_json_atomic(Path(args.output), report)
    if args.text_output:
        Path(args.text_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.text_output).write_text(
            render_stock_report_text(report),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "report": args.output,
                "blockers": report["blockers"],
                "payload_generated": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audita estoque oficial sem produzir payload.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture-read",
        help="Executa somente DspConEst1 e DspListaEquiEstoque.",
    )
    capture.add_argument("--installer-id", type=int, required=True)
    capture.add_argument("--profile", required=True)
    capture.add_argument("--profile-key", required=True)
    capture.add_argument("--port", type=int, required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument("--confirm", required=True)
    capture.set_defaults(handler=_capture_live)

    report = subparsers.add_parser(
        "report",
        help="Gera relatorio offline a partir de captura salva.",
    )
    report.add_argument("--catalog-xlsx", required=True)
    report.add_argument("--capture", required=True)
    report.add_argument("--installer-id", type=int, required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--text-output")
    report.set_defaults(handler=_report)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
