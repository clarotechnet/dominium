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
"""Read-only offline candidate locator for official API closes.

Strictly offline: no socket, no HTTP, no TOA connection, no DataSnap.
Receives normalized snapshot data and returns deterministic evaluation reports.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

PROJECT_ID = "IMPERIUM_OLLAMA"
DEFAULT_REPORT_DIR = Path("reports") / "official_candidate_search"


@dataclass(frozen=True)
class CandidateEvaluation:
    contract: str
    num_os: str
    activity_id: str
    service: str
    toa_status: str
    imperium_status: str
    original_schedule_date: str
    tech_login: str
    installer_id: int
    stock_id: int
    serialized_equipment: list[dict]
    miscellaneous_materials: list[dict]
    blockers: list[str]
    warnings: list[str]
    source_hash: str
    state_hash: str
    eligibility_status: str  # "eligible", "blocked", "warning", "closed_fixture_not_eligible"
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_candidate(snapshot: Mapping[str, Any]) -> CandidateEvaluation:
    """Evaluate a single order candidate snapshot for official API eligibility."""
    project_id = str(snapshot.get("project_id", "")).strip()
    profile_key = str(snapshot.get("profile_key", "")).strip().casefold()
    city = str(snapshot.get("city", "")).strip().upper()
    contract = str(snapshot.get("contract", "")).strip()
    activity_id = str(snapshot.get("activity_id", "")).strip()
    num_os = str(snapshot.get("num_os", "")).strip()
    service = str(snapshot.get("service", "")).strip()
    toa_status = str(snapshot.get("toa_status", "")).strip()
    imperium_status = str(snapshot.get("imperium_status", "")).strip().upper()
    original_schedule_date = str(snapshot.get("original_schedule_date", "")).strip()
    tech_login = str(snapshot.get("tech_login", "")).strip()
    installer_id = int(snapshot.get("installer_id") or 0)
    stock_id = int(snapshot.get("stock_id") or 0)
    serialized = list(snapshot.get("serialized_equipment") or [])
    miscellaneous = list(snapshot.get("miscellaneous_materials") or [])
    existing_close_code = str(snapshot.get("existing_close_code", "")).strip()
    previous_movements = bool(snapshot.get("previous_movements"))
    catalog_blockers = list(snapshot.get("catalog_blockers") or [])
    stock_blockers = list(snapshot.get("stock_blockers") or [])
    source_hash = str(snapshot.get("source_hash", "")).strip()
    state_hash = str(snapshot.get("state_hash", "")).strip()

    blockers: list[str] = []
    warnings: list[str] = []

    # Check fixture rule
    if contract == "2221170" or num_os in {"2646508672", "2646508683"}:
        return CandidateEvaluation(
            contract=contract,
            num_os=num_os,
            activity_id=activity_id,
            service=service,
            toa_status=toa_status,
            imperium_status=imperium_status,
            original_schedule_date=original_schedule_date,
            tech_login=tech_login,
            installer_id=installer_id,
            stock_id=stock_id,
            serialized_equipment=serialized,
            miscellaneous_materials=miscellaneous,
            blockers=["closed_fixture_contract_or_os"],
            warnings=[],
            source_hash=source_hash,
            state_hash=state_hash,
            eligibility_status="closed_fixture_not_eligible",
            reason="Contrato de fixture offline baixado por outro operador",
        )

    if project_id != PROJECT_ID:
        blockers.append("wrong_project_id")
    if profile_key != "natal":
        blockers.append("wrong_profile_key")
    if city != "NATAL":
        blockers.append("wrong_city")
    if not activity_id:
        blockers.append("missing_activity_id")
    if imperium_status not in {"EM CAMPO", "ABERTO", "OPEN"}:
        blockers.append("imperium_os_not_open")
    if existing_close_code:
        blockers.append("has_existing_close_code")
    if toa_status.casefold() not in {"concluida", "complete", "completed", "concluido"}:
        blockers.append("toa_activity_not_complete")
    if not tech_login or installer_id <= 0:
        blockers.append("unresolved_technician_identity")
    if previous_movements:
        blockers.append("has_previous_inventory_movements")
    if not source_hash or not state_hash:
        blockers.append("missing_snapshot_hash")
    blockers.extend(catalog_blockers)
    blockers.extend(stock_blockers)

    if snapshot.get("warning_messages"):
        warnings.extend(list(snapshot["warning_messages"]))

    if blockers:
        status = "blocked"
        reason = f"Bloqueios identificados: {', '.join(blockers)}"
    elif warnings:
        status = "warning"
        reason = f"Elegível com avisos: {', '.join(warnings)}"
    else:
        status = "eligible"
        reason = "Candidato totalmente elegível para piloto seguro"

    return CandidateEvaluation(
        contract=contract,
        num_os=num_os,
        activity_id=activity_id,
        service=service,
        toa_status=toa_status,
        imperium_status=imperium_status,
        original_schedule_date=original_schedule_date,
        tech_login=tech_login,
        installer_id=installer_id,
        stock_id=stock_id,
        serialized_equipment=serialized,
        miscellaneous_materials=miscellaneous,
        blockers=blockers,
        warnings=warnings,
        source_hash=source_hash,
        state_hash=state_hash,
        eligibility_status=status,
        reason=reason,
    )


def generate_candidate_report(
    candidates: list[Mapping[str, Any]],
    output_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    """Sort candidates deterministically and generate JSON and TXT reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluations = [evaluate_candidate(c) for c in candidates]

    # Deterministic sorting: eligibility status (eligible first), contract, num_os
    status_order = {"eligible": 0, "warning": 1, "blocked": 2, "closed_fixture_not_eligible": 3}
    sorted_evals = sorted(
        evaluations,
        key=lambda e: (status_order.get(e.eligibility_status, 9), e.contract, e.num_os),
    )

    json_path = output_dir / "CANDIDATOS_API_OFICIAL.json"
    txt_path = output_dir / "CANDIDATOS_API_OFICIAL.txt"

    data = {
        "status": "live_candidate_search_not_executed",
        "mode": "offline_candidate_locator",
        "total_evaluated": len(sorted_evals),
        "candidates": [e.to_dict() for e in sorted_evals],
    }

    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "============================================================",
        "RELATORIO DE CANDIDATOS PARA API OFICIAL (LOCALIZADOR OFFLINE)",
        "Status da Busca ao Vivo: live_candidate_search_not_executed",
        f"Total Avaliado: {len(sorted_evals)}",
        "============================================================",
        "",
    ]
    for e in sorted_evals:
        lines.extend(
            [
                f"Contrato: {e.contract} | OS: {e.num_os} | ActivityID: {e.activity_id}",
                f"Serviço: {e.service} | Status TOA: {e.toa_status} | Status Imperium: {e.imperium_status}",
                f"Técnico Login: {e.tech_login} | InstallerID: {e.installer_id} | StockID: {e.stock_id}",
                f"Elegibilidade: {e.eligibility_status.upper()}",
                f"Motivo/Detalhes: {e.reason}",
                f"Blockers: {', '.join(e.blockers) if e.blockers else 'Nenhum'}",
                f"Warnings: {', '.join(e.warnings) if e.warnings else 'Nenhum'}",
                "-" * 60,
            ]
        )

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, txt_path
