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
import hashlib
import json
from pathlib import Path
from typing import Iterable


REVIEW_SCHEMA = "dominium_official_stock_blocker_review_v1"
EXPECTED_CONTRACT = "2221170"
EXPECTED_INSTALLER_ID = 328898

# These codes were included in the previous stock audit for comparison only.
# The mapping is evidence to review, never an alias or equivalence rule.
CONTEXTUAL_COMPARISONS = {
    "22025072": ("22064608",),
    "22056343": ("22065719",),
    "22056341": ("22065725",),
    "22056344": ("22065720",),
}


class BlockerReviewError(ValueError):
    pass


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value))


def _read_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BlockerReviewError(f"JSON invalido: {Path(path).name}")
    return value


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _index_unique(
    values: Iterable[dict],
    key_getter,
    label: str,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    duplicates = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        key = str(key_getter(value) or "").strip()
        if not key:
            continue
        if key in result:
            duplicates.add(key)
        else:
            result[key] = value
    if duplicates:
        raise BlockerReviewError(
            f"{label} possui codigos duplicados: {', '.join(sorted(duplicates))}"
        )
    return result


def _normalize_stock_state(value: str) -> str:
    normalized = " ".join(str(value).strip().casefold().split())
    return {
        "sem saldo": "sem_saldo",
        "sem_saldo": "sem_saldo",
        "ausente": "ausente",
        "divergente": "conflito",
        "conflito": "conflito",
        "warning": "warning",
        "encontrado": "warning",
    }.get(normalized, normalized.replace(" ", "_"))


def _parse_blocker(value: object) -> tuple[str, str]:
    text = str(value).strip()
    if ":" not in text:
        raise BlockerReviewError(f"Blocker de estoque invalido: {text}")
    prefix, code = text.rsplit(":", 1)
    if not prefix.startswith("stock_audit_") or not code.strip():
        raise BlockerReviewError(f"Blocker de estoque invalido: {text}")
    state = _normalize_stock_state(prefix[len("stock_audit_") :])
    return state, code.strip()


def _find_contract_capture(toa_capture: dict, contract: str) -> dict:
    candidates = []
    for entry in toa_capture.get("os_list", []):
        if not isinstance(entry, dict):
            continue
        os_data = entry.get("os")
        activity = os_data.get("activity", {}) if isinstance(os_data, dict) else {}
        if str(activity.get("contract", "")).strip() == contract:
            candidates.append(entry)
    if len(candidates) != 1:
        raise BlockerReviewError(
            "A captura TOA deve conter exatamente uma atividade do contrato"
        )
    return candidates[0]


def _candidate_rows(
    catalog_review: dict | None,
    contextual_codes: Iterable[str],
    stock_by_code: dict[str, dict],
) -> list[dict]:
    candidates: dict[str, dict] = {}

    def add_catalog(values: object, source: str) -> None:
        if not isinstance(values, list):
            return
        for value in values:
            if not isinstance(value, dict):
                continue
            code = str(value.get("code", "")).strip()
            if not code:
                continue
            candidate = candidates.setdefault(
                code,
                {
                    "code": code,
                    "descriptions": list(value.get("descriptions", [])),
                    "sources": [],
                    "stock_status": None,
                    "available_quantity": None,
                    "unit": None,
                    "equivalence_authorized": False,
                },
            )
            if source not in candidate["sources"]:
                candidate["sources"].append(source)

    if catalog_review is not None:
        add_catalog(
            catalog_review.get(
                "official_candidates_by_exact_normalized_description",
            ),
            "official_catalog_exact_normalized_description",
        )
        add_catalog(
            catalog_review.get(
                "desktop_candidates_by_exact_normalized_description",
            ),
            "desktop_description_exact_normalized_catalog_lookup",
        )

    for code in contextual_codes:
        candidate = candidates.setdefault(
            code,
            {
                "code": code,
                "descriptions": [],
                "sources": [],
                "stock_status": None,
                "available_quantity": None,
                "unit": None,
                "equivalence_authorized": False,
            },
        )
        candidate["sources"].append(
            "previous_stock_audit_context_only_not_equivalence"
        )

    for code, candidate in candidates.items():
        stock = stock_by_code.get(code)
        if stock:
            candidate["stock_status"] = stock.get("status")
            candidate["available_quantity"] = stock.get("available_quantity")
            candidate["unit"] = stock.get("unit")
        candidate["reason"] = (
            "Evidencia apenas informativa: um codigo concreto diferente nao "
            "pode substituir o codigo do contrato sem prova explicita e "
            "rastreavel de equivalencia."
        )
    return sorted(candidates.values(), key=lambda item: item["code"])


def _unit_assessment(
    toa_material: dict | None,
    inspection_material: dict | None,
    catalog_review: dict | None,
    stock_row: dict | None,
) -> dict:
    toa_unit = None
    if toa_material is not None:
        toa_unit = _optional_text(toa_material.get("unit"))
    inspection_unit = None
    if inspection_material is not None:
        inspection_unit = _optional_text(inspection_material.get("unit"))
    catalog_unit = None
    if catalog_review is not None:
        official = catalog_review.get("official", {})
        if isinstance(official, dict):
            catalog_unit = _optional_text(official.get("unit"))
    stock_unit = None
    if stock_row is not None:
        stock_unit = _optional_text(stock_row.get("unit"))

    known_units = {
        value.casefold()
        for value in (toa_unit, inspection_unit, catalog_unit, stock_unit)
        if value
    }
    comparable = sum(
        value is not None
        for value in (toa_unit, inspection_unit, catalog_unit, stock_unit)
    ) >= 2
    divergent = comparable and len(known_units) > 1
    if divergent:
        status = "conflito"
    elif comparable:
        status = "sem_divergencia"
    else:
        status = "nao_comparavel"
    return {
        "toa_unit": toa_unit,
        "inspection_unit": inspection_unit,
        "catalog_unit": catalog_unit,
        "stock_unit": stock_unit,
        "comparable": comparable,
        "divergent": divergent,
        "status": status,
        "reason": (
            "TOA and the official catalog do not expose a unit for this "
            "contract material; stock unit alone cannot prove a divergence."
            if not comparable
            else None
        ),
    }


def build_blocker_review(
    inspection: dict,
    toa_capture: dict,
    catalog_report: dict,
    stock_report: dict,
    *,
    contract: str = EXPECTED_CONTRACT,
    installer_id: int = EXPECTED_INSTALLER_ID,
    contextual_comparisons: dict[str, Iterable[str]] | None = None,
    evidence_files: list[dict] | None = None,
) -> dict:
    contract = str(contract).strip()
    if str(inspection.get("contract", "")).strip() != contract:
        raise BlockerReviewError("A inspecao pertence a outro contrato")
    if str(catalog_report.get("contract", "")).strip() != contract:
        raise BlockerReviewError("O relatorio de catalogo pertence a outro contrato")
    if int(stock_report.get("installer_id", 0) or 0) != installer_id:
        raise BlockerReviewError("O relatorio de estoque pertence a outro instalador")
    if stock_report.get("payload_generated") is not False:
        raise BlockerReviewError("Relatorio de estoque nao e somente auditoria")

    captured = _find_contract_capture(toa_capture, contract)
    os_data = captured.get("os", {})
    activity = os_data.get("activity", {}) if isinstance(os_data, dict) else {}
    activity_aid = str(activity.get("aid", "")).strip()
    if activity_aid != str(inspection.get("toa", {}).get("activity_aid", "")):
        raise BlockerReviewError("AID diverge entre captura TOA e inspecao")

    raw_materials = [
        value
        for value in os_data.get("inventory", [])
        if isinstance(value, dict)
        and value.get("kind") == "material"
        and str(value.get("activity_id", "")).strip() == activity_aid
    ]
    inspection_materials = inspection.get("inventory", {}).get("materials", [])
    catalog_materials = catalog_report.get("materials", [])
    stock_materials = stock_report.get("materials", [])

    raw_by_code = _index_unique(
        raw_materials,
        lambda value: value.get("material_code"),
        "Captura TOA",
    )
    inspection_by_code = _index_unique(
        inspection_materials,
        lambda value: value.get("equipment_code"),
        "Inspecao",
    )
    catalog_by_code = _index_unique(
        catalog_materials,
        lambda value: value.get("toa", {}).get("code"),
        "Relatorio de catalogo",
    )
    stock_by_code = _index_unique(
        stock_materials,
        lambda value: value.get("code"),
        "Relatorio de estoque",
    )

    context = contextual_comparisons or {}
    reviews = []
    remaining = []
    removable = []
    for source_blocker in stock_report.get("blockers", []):
        source_state, code = _parse_blocker(source_blocker)
        raw = raw_by_code.get(code)
        inspected = inspection_by_code.get(code)
        catalog = catalog_by_code.get(code)
        stock = stock_by_code.get(code)

        raw_quantity = str(raw.get("quantity", "")).strip() if raw else None
        inspected_quantity = (
            str(inspected.get("used_quantity", "")).strip()
            if inspected
            else None
        )
        origin_conflicts = []
        if (raw is None) != (inspected is None):
            origin_conflicts.append("material_presence_mismatch")
        if raw and inspected:
            if str(raw.get("invid", "")).strip() != str(
                inspected.get("invid", "")
            ).strip():
                origin_conflicts.append("invid_mismatch")
            if str(raw.get("activity_id", "")).strip() != str(
                inspected.get("inv_aid", "")
            ).strip():
                origin_conflicts.append("activity_aid_mismatch")
            if raw_quantity != inspected_quantity:
                origin_conflicts.append("used_quantity_mismatch")

        official_entry = None
        if catalog:
            official = catalog.get("official", {})
            if isinstance(official, dict):
                official_entry = official.get("code_entry")
        official_exact = (
            isinstance(official_entry, dict)
            and str(official_entry.get("code", "")).strip() == code
        )
        required_by_contract = raw is not None and inspected is not None

        unit = _unit_assessment(raw, inspected, catalog, stock)
        if origin_conflicts or unit["divergent"]:
            classification = "conflito"
            keep_blocked = True
            decision_reason = (
                "As evidencias do contrato divergem entre si; o material "
                "deve permanecer bloqueado."
            )
        elif not required_by_contract:
            classification = "matching_incorreto"
            keep_blocked = True
            decision_reason = (
                "O codigo nao aparece no inventario TOA nem na inspecao "
                "normalizada, mas a completude das fontes nao foi confirmada "
                "independentemente. A revisao conservadora mantem o blocker."
            )
        elif not official_exact:
            classification = "conflito"
            keep_blocked = True
            decision_reason = (
                "O codigo concreto do TOA nao foi confirmado pela entrada "
                "correspondente do catalogo oficial."
            )
        elif source_state == "sem_saldo":
            classification = "sem_saldo"
            keep_blocked = True
            decision_reason = (
                "O codigo exato do contrato e oficial e obrigatorio, mas o "
                "saldo auditado do tecnico e zero."
            )
        elif source_state == "ausente":
            classification = "ausente"
            keep_blocked = True
            decision_reason = (
                "O codigo exato do contrato e oficial e obrigatorio, mas "
                "esta ausente do estoque auditado do tecnico."
            )
        else:
            classification = source_state or "warning"
            keep_blocked = True
            decision_reason = (
                "As evidencias offline do contrato nao invalidaram o blocker "
                "de origem."
            )

        canonical_blocker = f"stock_audit_{classification}:{code}"
        if keep_blocked:
            remaining.append(canonical_blocker)
        else:
            removable.append(canonical_blocker)

        material_os = str(
            inspection.get("routing_evidence", {}).get(
                "effective_material_os",
                "",
            )
        ).strip()
        review = {
            "code": code,
            "source_blocker": str(source_blocker),
            "canonical_state": classification,
            "origin": {
                "source": "inventario normalizado da atividade TOA",
                "contract": contract,
                "activity_aid": activity_aid,
                "invid": str(raw.get("invid", "")).strip() if raw else None,
                "description": raw.get("description") if raw else None,
                "used_quantity": raw_quantity,
                "json_pointer": (
                    f"os_list[contract={contract}].os.inventory"
                    f"[material_code={code}]"
                    if raw
                    else None
                ),
            },
            "contract_dependency": {
                "required": required_by_contract,
                "material_os": material_os or None,
                "capability": inspection.get(
                    "routing_evidence",
                    {},
                ).get("effective_material_capability"),
                "inspection_invid": (
                    str(inspected.get("invid", "")).strip()
                    if inspected
                    else None
                ),
                "inspection_inv_aid": (
                    str(inspected.get("inv_aid", "")).strip()
                    if inspected
                    else None
                ),
                "used_quantity": inspected_quantity,
            },
            "matching": {
                "assessment": (
                    "exact_code_from_toa_and_inspection"
                    if required_by_contract and not origin_conflicts
                    else (
                        "source_conflict"
                        if origin_conflicts
                        else "not_present_in_contract_sources"
                    )
                ),
                "matching_incorreto": classification == "matching_incorreto",
                "origin_conflicts": origin_conflicts,
            },
            "official_catalog": {
                "exact_code_confirmed": official_exact,
                "code": (
                    str(official_entry.get("code", "")).strip()
                    if isinstance(official_entry, dict)
                    else None
                ),
                "ids": (
                    list(official_entry.get("ids", []))
                    if isinstance(official_entry, dict)
                    else []
                ),
                "descriptions": (
                    list(official_entry.get("descriptions", []))
                    if isinstance(official_entry, dict)
                    else []
                ),
                "catalog_review_status": (
                    catalog.get("status") if catalog else None
                ),
            },
            "stock_evidence": _json_copy(stock) if stock else None,
            "unit_evidence": unit,
            "candidates": _candidate_rows(
                catalog,
                context.get(code, ()),
                stock_by_code,
            ),
            "decision": {
                "keep_blocked": keep_blocked,
                "blocker_can_be_removed": not keep_blocked,
                "material_action": (
                    "manter_bloqueado"
                    if keep_blocked
                    else "remover_blocker_de_matching_incorreto"
                ),
                "reason": decision_reason,
                "automatic_alias_created": False,
                "automatic_substitution_authorized": False,
            },
        }
        reviews.append(review)

    unrelated_errors = stock_report.get("unrelated_catalog_errors", [])
    warnings = list(stock_report.get("warnings", []))
    return {
        "schema": REVIEW_SCHEMA,
        "mode": "offline_blocker_review",
        "contract": contract,
        "activity_aid": activity_aid,
        "material_os": str(
            inspection.get("routing_evidence", {}).get(
                "effective_material_os",
                "",
            )
        ).strip(),
        "installer_id": installer_id,
        "stock_id": stock_report.get("stock_id"),
        "profile": stock_report.get("profile"),
        "stock_read_at": stock_report.get("read_at"),
        "evidence_files": evidence_files or [],
        "reviews": reviews,
        "states_present": sorted(
            {review["canonical_state"] for review in reviews}
        ),
        "blockers_before": list(stock_report.get("blockers", [])),
        "blockers_remaining": remaining,
        "blockers_removable": removable,
        "warnings": warnings,
        "unrelated_catalog_errors": _json_copy(unrelated_errors),
        "conclusions": {
            "material_matching_defect_proven": False,
            "material_matching_change_required": False,
            "aliases_created": [],
            "payload_generated": False,
        },
        "safety": {
            "offline_only": True,
            "network_used": False,
            "post_executed": False,
            "datasnap_read_executed": False,
            "datasnap_write_executed": False,
            "stock_movement_executed": False,
        },
    }


def render_text(report: dict) -> str:
    lines = [
        "REVISAO OFFLINE DOS BLOCKERS DE ESTOQUE",
        "",
        f"Contrato: {report['contract']}",
        f"AID: {report['activity_aid']}",
        f"OS de materiais: {report['material_os']}",
        f"Installer ID: {report['installer_id']}",
        f"Stock ID: {report['stock_id']}",
        f"Leitura original: {report['stock_read_at']}",
        "",
    ]
    for review in report["reviews"]:
        decision = review["decision"]
        origin = review["origin"]
        stock = review["stock_evidence"] or {}
        candidates = ", ".join(
            (
                f"{candidate['code']}"
                f"[estoque={candidate['stock_status'] or 'nao_auditado'};"
                "equivalencia=nao]"
            )
            for candidate in review["candidates"]
            if candidate["code"] != review["code"]
        )
        lines.extend(
            [
                f"{review['code']} | {review['canonical_state'].upper()}",
                f"  Origem: {origin['source']}",
                f"  Invid: {origin['invid'] or '-'}",
                f"  Quantidade usada: {origin['used_quantity'] or '-'}",
                (
                    "  Catalogo: "
                    f"{', '.join(review['official_catalog']['descriptions']) or '-'}"
                ),
                (
                    "  Estoque: "
                    f"{stock.get('available_quantity') or '-'} "
                    f"{stock.get('unit') or ''}"
                ).rstrip(),
                f"  Unidade: {review['unit_evidence']['status']}",
                f"  Candidatos recusados: {candidates or '-'}",
                f"  Decisao: {decision['material_action']}",
                f"  Motivo: {decision['reason']}",
                "  Alias automatico: nao",
                "",
            ]
        )
    lines.append("BLOCKERS QUE PERMANECEM")
    lines.extend(f"- {value}" for value in report["blockers_remaining"])
    lines.append("")
    lines.append("BLOCKERS REMOVIVEIS")
    if report["blockers_removable"]:
        lines.extend(f"- {value}" for value in report["blockers_removable"])
    else:
        lines.append("- nenhum")
    lines.extend(
        [
            "",
            "Nenhum payload foi gerado.",
            "Nenhuma consulta, escrita ou movimentacao foi executada.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Revisa blockers de estoque usando somente artefatos locais.",
    )
    parser.add_argument("--contract", default=EXPECTED_CONTRACT)
    parser.add_argument("--installer-id", type=int, default=EXPECTED_INSTALLER_ID)
    parser.add_argument("--inspection", required=True)
    parser.add_argument("--toa-capture", required=True)
    parser.add_argument("--catalog-report", required=True)
    parser.add_argument("--stock-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--text-output")
    args = parser.parse_args(argv)

    source_paths = (
        args.inspection,
        args.toa_capture,
        args.catalog_report,
        args.stock_report,
    )
    evidence_files = [
        {
            "path": str(Path(path).as_posix()),
            "sha256": _sha256(path),
        }
        for path in source_paths
    ]
    report = build_blocker_review(
        _read_json(args.inspection),
        _read_json(args.toa_capture),
        _read_json(args.catalog_report),
        _read_json(args.stock_report),
        contract=args.contract,
        installer_id=args.installer_id,
        contextual_comparisons=CONTEXTUAL_COMPARISONS,
        evidence_files=evidence_files,
    )
    _write_json_atomic(Path(args.output), report)
    if args.text_output:
        output = Path(args.text_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_text(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": args.output,
                "blockers_remaining": report["blockers_remaining"],
                "blockers_removable": report["blockers_removable"],
                "payload_generated": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
