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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


PLAN_SCHEMA = "dominium_official_stock_remediation_plan_v1"
EXPECTED_CONTRACT = "2221170"
EXPECTED_INSTALLER_ID = 328898
EXPECTED_CODES = (
    "22025072",
    "22056343",
    "22056341",
    "22056344",
)
CONTEXTUAL_CLOSE_CODE = "104"
CONTEXTUAL_CLOSE_DESCRIPTION = "Falta de Material"
CONTEXTUAL_CLOSE_CATEGORY = "IMPRODUTIVOS"
CONTEXTUAL_CLOSE_USAGE_RULE = (
    "Quando o técnico vai até a residência do cliente e não consegue "
    "executar o serviço, devido à falta de material ou equipamento."
)


class StockRemediationPlanError(ValueError):
    pass


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value))


def load_json_object(path: str | Path) -> dict:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StockRemediationPlanError(
            f"Nao foi possivel ler {source}: {exc}"
        ) from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StockRemediationPlanError(
            f"JSON invalido em {source}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise StockRemediationPlanError(
            f"O arquivo {source} deve conter um objeto JSON"
        )
    return value


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise StockRemediationPlanError(
            f"Nao foi possivel calcular SHA-256 de {source}: {exc}"
        ) from exc
    return digest.hexdigest()


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise StockRemediationPlanError(f"{label} deve ser Decimal positivo")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise StockRemediationPlanError(
            f"{label} deve ser Decimal positivo"
        ) from exc
    if not result.is_finite() or result <= 0:
        raise StockRemediationPlanError(f"{label} deve ser Decimal positivo")
    return result


def _nonnegative_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise StockRemediationPlanError(
            f"{label} deve ser Decimal nao negativo"
        )
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise StockRemediationPlanError(
            f"{label} deve ser Decimal nao negativo"
        ) from exc
    if not result.is_finite() or result < 0:
        raise StockRemediationPlanError(
            f"{label} deve ser Decimal nao negativo"
        )
    return result


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


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
        raise StockRemediationPlanError(
            f"{label} possui codigos duplicados: "
            f"{', '.join(sorted(duplicates))}"
        )
    return result


def _normalize_stock_state(value: object) -> str:
    normalized = " ".join(str(value).strip().casefold().split())
    return {
        "sem saldo": "sem_saldo",
        "sem_saldo": "sem_saldo",
        "ausente": "ausente",
        "divergente": "conflito",
        "conflito": "conflito",
        "warning": "warning",
    }.get(normalized, normalized.replace(" ", "_"))


def _parse_blocker(value: object) -> tuple[str, str]:
    text = str(value).strip()
    if ":" not in text:
        raise StockRemediationPlanError(f"Blocker invalido: {text}")
    prefix, code = text.rsplit(":", 1)
    if not prefix.startswith("stock_audit_") or not code.strip():
        raise StockRemediationPlanError(f"Blocker invalido: {text}")
    return (
        _normalize_stock_state(prefix[len("stock_audit_") :]),
        code.strip(),
    )


def _canonical_blocker(state: str, code: str) -> str:
    return f"stock_audit_{state}:{code}"


def _blockers_by_code(values: object, label: str) -> dict[str, str]:
    if not isinstance(values, list):
        raise StockRemediationPlanError(f"{label} deve ser uma lista")
    result = {}
    for value in values:
        state, code = _parse_blocker(value)
        if code in result:
            raise StockRemediationPlanError(
                f"{label} possui blocker duplicado para {code}"
            )
        result[code] = state
    return result


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
        raise StockRemediationPlanError(
            "A captura TOA deve conter exatamente uma atividade do contrato"
        )
    return candidates[0]


def _assert_false_safety(document: dict, label: str) -> None:
    if document.get("payload_generated") not in (None, False):
        raise StockRemediationPlanError(f"{label} declara payload gerado")
    safety = document.get("safety", {})
    if not isinstance(safety, dict):
        raise StockRemediationPlanError(f"{label}.safety invalido")
    forbidden_true = (
        "network_used",
        "post_executed",
        "datasnap_read_executed",
        "datasnap_write_executed",
        "stock_movement_executed",
        "close_executed",
    )
    for key in forbidden_true:
        if safety.get(key) is True:
            raise StockRemediationPlanError(
                f"{label} registra operacao externa: {key}"
            )


def _close_code_context(catalog: dict) -> dict:
    if catalog.get("schema") != "dominium_official_close_code_catalog_v1":
        raise StockRemediationPlanError(
            "Schema invalido no catalogo de codigos de baixa"
        )
    source = catalog.get("source", {})
    if not isinstance(source, dict):
        raise StockRemediationPlanError(
            "Fonte invalida no catalogo de codigos de baixa"
        )
    file_name = str(source.get("file_name", "")).strip()
    source_sha256 = str(source.get("sha256", "")).strip().lower()
    if file_name != "Tabela_codigo_baixa0711.pdf":
        raise StockRemediationPlanError(
            "PDF de referencia de codigos de baixa divergente"
        )
    if len(source_sha256) != 64 or any(
        value not in "0123456789abcdef" for value in source_sha256
    ):
        raise StockRemediationPlanError(
            "SHA-256 invalido no catalogo de codigos de baixa"
        )

    entries = _index_unique(
        catalog.get("entries", []),
        lambda value: value.get("code"),
        "Catalogo de codigos de baixa",
    )
    entry = entries.get(CONTEXTUAL_CLOSE_CODE)
    if entry is None:
        raise StockRemediationPlanError(
            "Codigo contextual 104 ausente no catalogo de baixa"
        )
    if entry.get("status") != "valid":
        raise StockRemediationPlanError(
            "Codigo contextual 104 inconsistente no catalogo de baixa"
        )
    if str(entry.get("category", "")).strip() != CONTEXTUAL_CLOSE_CATEGORY:
        raise StockRemediationPlanError(
            "Categoria divergente para o codigo contextual 104"
        )
    if (
        str(entry.get("description", "")).strip()
        != CONTEXTUAL_CLOSE_DESCRIPTION
    ):
        raise StockRemediationPlanError(
            "Descricao divergente para o codigo contextual 104"
        )
    if (
        str(entry.get("usage_rule", "")).strip()
        != CONTEXTUAL_CLOSE_USAGE_RULE
    ):
        raise StockRemediationPlanError(
            "Regra de uso divergente para o codigo contextual 104"
        )
    pages = sorted(
        {
            int(page)
            for page in entry.get("source_pages", [])
            if isinstance(page, int) and not isinstance(page, bool)
        }
    )
    if pages != [4]:
        raise StockRemediationPlanError(
            "Pagina de origem divergente para o codigo contextual 104"
        )

    warnings = catalog.get("warnings", [])
    if not isinstance(warnings, list):
        raise StockRemediationPlanError(
            "Warnings invalidos no catalogo de codigos de baixa"
        )
    related_warnings = [
        value
        for value in warnings
        if isinstance(value, dict)
        and str(value.get("code", "")).strip() == CONTEXTUAL_CLOSE_CODE
    ]
    if related_warnings:
        raise StockRemediationPlanError(
            "Codigo contextual 104 possui duplicidade no PDF"
        )

    return {
        "code": CONTEXTUAL_CLOSE_CODE,
        "category": CONTEXTUAL_CLOSE_CATEGORY,
        "description": CONTEXTUAL_CLOSE_DESCRIPTION,
        "usage_rule": CONTEXTUAL_CLOSE_USAGE_RULE,
        "customer_communication": entry.get("customer_communication"),
        "source": {
            "file_name": file_name,
            "sha256": source_sha256,
            "page": 4,
        },
        "catalog_warnings_unrelated": _json_copy(warnings),
        "selection_authorized": False,
        "application_authorized": False,
        "stock_blocker_alone_authorizes_code": False,
        "conditions_required": [
            "visita_ao_cliente_confirmada",
            (
                "falta_de_material_ou_equipamento_impediu_"
                "o_servico_confirmada"
            ),
            "confirmacao_humana_explicita",
        ],
        "payload_generated": False,
        "close_executed": False,
    }


def _catalog_entry(catalog_material: dict, code: str) -> tuple[str, list[str]]:
    toa = catalog_material.get("toa", {})
    official = catalog_material.get("official", {})
    code_entry = official.get("code_entry", {}) if isinstance(official, dict) else {}
    if str(toa.get("code", "")).strip() != code:
        raise StockRemediationPlanError(
            f"Catalogo nao preserva o codigo TOA {code}"
        )
    if str(code_entry.get("code", "")).strip() != code:
        raise StockRemediationPlanError(
            f"Catalogo nao confirma o codigo oficial {code}"
        )
    ids = sorted(
        {
            str(value).strip()
            for value in code_entry.get("ids", [])
            if str(value).strip()
        }
    )
    if len(ids) != 1:
        raise StockRemediationPlanError(
            f"Catalogo deve fornecer um unico identificador para {code}"
        )
    descriptions = sorted(
        {
            str(value).strip()
            for value in code_entry.get("descriptions", [])
            if str(value).strip()
        }
    )
    if not descriptions:
        raise StockRemediationPlanError(
            f"Catalogo nao fornece descricao para {code}"
        )
    return ids[0], descriptions


def _validate_no_substitution(review: dict, code: str) -> None:
    decision = review.get("decision", {})
    if (
        decision.get("automatic_alias_created") is not False
        or decision.get("automatic_substitution_authorized") is not False
    ):
        raise StockRemediationPlanError(
            f"A revisao autoriza alias ou substituicao para {code}"
        )
    for candidate in review.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("equivalence_authorized") is not False:
            raise StockRemediationPlanError(
                f"Candidato foi autorizado como substituto de {code}"
            )


def _unit_plan(
    review: dict,
    stock_row: dict,
) -> dict:
    unit_evidence = review.get("unit_evidence", {})
    stock_unit = _optional_text(stock_row.get("unit"))
    if _optional_text(unit_evidence.get("stock_unit")) != stock_unit:
        raise StockRemediationPlanError(
            f"Unidade diverge entre revisao e auditoria para {review.get('code')}"
        )
    toa_unit = _optional_text(unit_evidence.get("toa_unit"))
    if toa_unit is not None:
        return {
            "unit": toa_unit,
            "unit_source": "toa_inventory",
            "toa_unit": toa_unit,
            "stock_unit": stock_unit,
            "status": (
                "comprovada"
                if stock_unit is None or stock_unit.casefold() == toa_unit.casefold()
                else "conflito"
            ),
        }
    return {
        "unit": stock_unit,
        "unit_source": (
            "official_stock_audit.stock_row" if stock_unit is not None else None
        ),
        "toa_unit": None,
        "stock_unit": stock_unit,
        "status": "unidade_nao_comprovada",
    }


def _actions_for_state(state: str) -> dict:
    if state == "sem_saldo":
        external_action = "repor_saldo"
        description = (
            "Disponibilizar saldo do mesmo codigo concreto no estoque auditado "
            "do tecnico, mediante procedimento externo autorizado."
        )
    elif state == "ausente":
        external_action = "cadastrar_ou_disponibilizar_no_estoque"
        description = (
            "Cadastrar ou disponibilizar o mesmo codigo concreto no estoque "
            "auditado do tecnico, mediante procedimento externo autorizado."
        )
    else:
        raise StockRemediationPlanError(
            f"Estado sem plano conservador definido: {state}"
        )
    return {
        "external_action": external_action,
        "description": description,
        "required_controls": [
            "exigir_confirmacao_manual",
            "nenhuma_acao_automatica",
        ],
        "executed": False,
    }


def build_stock_remediation_plan(
    inspection: dict,
    toa_capture: dict,
    catalog_report: dict,
    stock_report: dict,
    blocker_review: dict,
    close_code_catalog: dict,
    *,
    contract: str = EXPECTED_CONTRACT,
    installer_id: int = EXPECTED_INSTALLER_ID,
    evidence_files: list[dict] | None = None,
) -> dict:
    originals = (
        _json_copy(inspection),
        _json_copy(toa_capture),
        _json_copy(catalog_report),
        _json_copy(stock_report),
        _json_copy(blocker_review),
        _json_copy(close_code_catalog),
    )

    contract = str(contract).strip()
    if contract != EXPECTED_CONTRACT:
        raise StockRemediationPlanError(
            f"Contrato nao autorizado para este plano: {contract}"
        )
    if installer_id != EXPECTED_INSTALLER_ID:
        raise StockRemediationPlanError(
            f"Installer ID nao autorizado para este plano: {installer_id}"
        )
    if str(inspection.get("contract", "")).strip() != contract:
        raise StockRemediationPlanError("Contrato divergente na inspecao")
    if str(catalog_report.get("contract", "")).strip() != contract:
        raise StockRemediationPlanError("Contrato divergente no catalogo")
    if str(blocker_review.get("contract", "")).strip() != contract:
        raise StockRemediationPlanError("Contrato divergente na revisao")
    if stock_report.get("installer_id") != installer_id:
        raise StockRemediationPlanError("Installer ID divergente na auditoria")
    if blocker_review.get("installer_id") != installer_id:
        raise StockRemediationPlanError("Installer ID divergente na revisao")

    imperium_identity = (
        inspection.get("technician_identity_evidence", {})
        .get("imperium_orders", {})
    )
    if imperium_identity.get("installer_id") != installer_id:
        raise StockRemediationPlanError("Installer ID divergente na inspecao")

    _assert_false_safety(inspection, "inspecao")
    _assert_false_safety(catalog_report, "catalogo")
    _assert_false_safety(stock_report, "auditoria")
    _assert_false_safety(blocker_review, "revisao")
    _assert_false_safety(
        close_code_catalog,
        "catalogo de codigos de baixa",
    )
    close_code_context = _close_code_context(close_code_catalog)

    capture_entry = _find_contract_capture(toa_capture, contract)
    os_data = capture_entry.get("os", {})
    activity = os_data.get("activity", {})
    activity_aid = str(activity.get("aid", "")).strip()
    if not activity_aid:
        raise StockRemediationPlanError("Captura TOA sem AID")
    if str(blocker_review.get("activity_aid", "")).strip() != activity_aid:
        raise StockRemediationPlanError("AID divergente na revisao")

    material_os = str(blocker_review.get("material_os", "")).strip()
    inspection_material_os = str(
        inspection.get("routing_evidence", {}).get(
            "effective_material_os",
            "",
        )
    ).strip()
    if not material_os or material_os != inspection_material_os:
        raise StockRemediationPlanError("OS de materiais divergente")

    toa_materials = _index_unique(
        (
            value
            for value in os_data.get("inventory", [])
            if isinstance(value, dict) and value.get("kind") == "material"
        ),
        lambda value: value.get("material_code"),
        "Inventario TOA",
    )
    inspection_materials = _index_unique(
        inspection.get("inventory", {}).get("materials", []),
        lambda value: value.get("equipment_code"),
        "Inspecao",
    )
    catalog_materials = _index_unique(
        catalog_report.get("materials", []),
        lambda value: value.get("toa", {}).get("code"),
        "Catalogo",
    )
    stock_materials = _index_unique(
        stock_report.get("materials", []),
        lambda value: value.get("code"),
        "Auditoria",
    )
    reviews = _index_unique(
        blocker_review.get("reviews", []),
        lambda value: value.get("code"),
        "Revisao",
    )

    audit_blockers = _blockers_by_code(
        stock_report.get("blockers"),
        "Auditoria.blockers",
    )
    review_blockers = _blockers_by_code(
        blocker_review.get("blockers_remaining"),
        "Revisao.blockers_remaining",
    )
    expected_codes = set(EXPECTED_CODES)
    if set(audit_blockers) != expected_codes:
        raise StockRemediationPlanError(
            "A auditoria nao contem exatamente os quatro blockers esperados"
        )
    if set(review_blockers) != expected_codes:
        raise StockRemediationPlanError(
            "A revisao nao mantem exatamente os quatro blockers esperados"
        )
    if blocker_review.get("blockers_removable") != []:
        raise StockRemediationPlanError(
            "A revisao marcou blocker como removivel"
        )

    plans = []
    for code in EXPECTED_CODES:
        toa_material = toa_materials.get(code)
        inspected = inspection_materials.get(code)
        catalog_material = catalog_materials.get(code)
        stock_row = stock_materials.get(code)
        review = reviews.get(code)
        if None in (
            toa_material,
            inspected,
            catalog_material,
            stock_row,
            review,
        ):
            raise StockRemediationPlanError(
                f"Evidencia obrigatoria ausente para {code}"
            )

        state = audit_blockers[code]
        if review_blockers[code] != state:
            raise StockRemediationPlanError(
                f"Estado diverge entre auditoria e revisao para {code}"
            )
        if _normalize_stock_state(review.get("canonical_state")) != state:
            raise StockRemediationPlanError(
                f"Estado canonico divergente na revisao para {code}"
            )
        if review.get("decision", {}).get("keep_blocked") is not True:
            raise StockRemediationPlanError(
                f"A revisao nao manteve o blocker {code}"
            )
        _validate_no_substitution(review, code)

        required = _decimal(
            toa_material.get("quantity"),
            f"Quantidade TOA de {code}",
        )
        inspected_required = _decimal(
            inspected.get("used_quantity"),
            f"Quantidade inspecionada de {code}",
        )
        review_required = _decimal(
            review.get("origin", {}).get("used_quantity"),
            f"Quantidade revisada de {code}",
        )
        if not (required == inspected_required == review_required):
            raise StockRemediationPlanError(
                f"Quantidade diverge entre captura, inspecao e revisao para {code}"
            )

        invid = str(toa_material.get("invid", "")).strip()
        if not invid:
            raise StockRemediationPlanError(f"INVID ausente para {code}")
        if str(inspected.get("invid", "")).strip() != invid:
            raise StockRemediationPlanError(
                f"INVID diverge entre captura e inspecao para {code}"
            )
        if str(review.get("origin", {}).get("invid", "")).strip() != invid:
            raise StockRemediationPlanError(
                f"INVID diverge entre captura e revisao para {code}"
            )
        if str(toa_material.get("activity_id", "")).strip() != activity_aid:
            raise StockRemediationPlanError(
                f"INV_AID divergente na captura para {code}"
            )
        if str(inspected.get("inv_aid", "")).strip() != activity_aid:
            raise StockRemediationPlanError(
                f"INV_AID divergente na inspecao para {code}"
            )

        official_id, catalog_descriptions = _catalog_entry(
            catalog_material,
            code,
        )
        reviewed_ids = sorted(
            str(value).strip()
            for value in review.get("official_catalog", {}).get("ids", [])
            if str(value).strip()
        )
        if reviewed_ids != [official_id]:
            raise StockRemediationPlanError(
                f"Identificador oficial diverge na revisao para {code}"
            )
        if str(stock_row.get("code", "")).strip() != code:
            raise StockRemediationPlanError(
                f"Auditoria nao preserva o codigo {code}"
            )
        if stock_row.get("installer_id") != installer_id:
            raise StockRemediationPlanError(
                f"Installer ID diverge na linha de estoque de {code}"
            )
        if stock_row.get("stock_id") != stock_report.get("stock_id"):
            raise StockRemediationPlanError(
                f"Stock ID diverge na linha de estoque de {code}"
            )
        stock_state = _normalize_stock_state(stock_row.get("status"))
        if stock_state != state:
            raise StockRemediationPlanError(
                f"Estado diverge na linha de estoque de {code}"
            )

        if state == "sem_saldo":
            available = _nonnegative_decimal(
                stock_row.get("available_quantity"),
                f"Saldo auditado de {code}",
            )
            deficit = required - available
            if deficit <= 0:
                raise StockRemediationPlanError(
                    f"Blocker sem_saldo sem deficit para {code}"
                )
            available_text = _decimal_text(available)
            deficit_basis = "required_quantity_minus_audited_balance"
        elif state == "ausente":
            if stock_row.get("available_quantity") is not None:
                raise StockRemediationPlanError(
                    f"Material ausente possui saldo numerico para {code}"
                )
            available_text = None
            deficit = required
            deficit_basis = (
                "minimum_required_quantity_because_exact_code_is_absent_"
                "from_audited_stock"
            )
        else:
            raise StockRemediationPlanError(
                f"Estado inesperado para {code}: {state}"
            )

        unit = _unit_plan(review, stock_row)
        candidates = [
            {
                "code": str(candidate.get("code", "")).strip(),
                "sources": sorted(candidate.get("sources", [])),
                "equivalence_authorized": False,
            }
            for candidate in review.get("candidates", [])
            if str(candidate.get("code", "")).strip() != code
        ]
        candidates.sort(key=lambda value: value["code"])

        plans.append(
            {
                "code": code,
                "description": catalog_descriptions[0],
                "official_material_id": official_id,
                "invid": invid,
                "activity_aid": activity_aid,
                "material_os": material_os,
                "required_quantity": _decimal_text(required),
                "available_quantity": available_text,
                "deficit_quantity": _decimal_text(deficit),
                "deficit_basis": deficit_basis,
                "unit_evidence": unit,
                "current_state": state,
                "actions": _actions_for_state(state),
                "evidence": {
                    "toa": {
                        "code": code,
                        "invid": invid,
                        "quantity": _decimal_text(required),
                        "description": str(
                            toa_material.get("description", "")
                        ).strip(),
                    },
                    "inspection": {
                        "code": code,
                        "invid": str(inspected.get("invid", "")).strip(),
                        "inv_aid": str(inspected.get("inv_aid", "")).strip(),
                        "used_quantity": _decimal_text(inspected_required),
                    },
                    "catalog": {
                        "code": code,
                        "official_material_id": official_id,
                        "descriptions": catalog_descriptions,
                    },
                    "stock_audit": {
                        "installer_id": installer_id,
                        "stock_id": stock_report.get("stock_id"),
                        "status": state,
                        "available_quantity": available_text,
                        "unit": _optional_text(stock_row.get("unit")),
                        "source": stock_row.get("source"),
                        "read_at": stock_row.get("read_at"),
                    },
                    "blocker_review": {
                        "matching_incorreto": review.get("matching", {}).get(
                            "matching_incorreto"
                        ),
                        "keep_blocked": True,
                    },
                },
                "rejected_candidates": candidates,
                "regularization_evidence_required": [
                    "nova_leitura_somente_de_estoque",
                    f"installer_id_exato:{installer_id}",
                    f"stock_id_exato:{stock_report.get('stock_id')}",
                    f"codigo_concreto_exato:{code}",
                    (
                        "saldo_disponivel_maior_ou_igual:"
                        f"{_decimal_text(required)}"
                    ),
                    "unidade_exposta_e_confirmada_manualmente",
                ],
                "expected_after_future_read": {
                    "status": "encontrado",
                    "minimum_available_quantity": _decimal_text(required),
                    "blocker_expected_absent": _canonical_blocker(state, code),
                    "requires_new_read": True,
                    "automatically_assumed": False,
                },
                "risks_and_ambiguities": [
                    "unidade_nao_comprovada",
                    "procedimento_externo_nao_autorizado",
                    "candidatos_nao_sao_equivalencias",
                    (
                        "codigo_ausente_sem_linha_de_estoque"
                        if state == "ausente"
                        else "saldo_insuficiente_no_snapshot_auditado"
                    ),
                ],
                "blocker_active": True,
                "automatic_action_authorized": False,
            }
        )

    if (
        originals[0] != inspection
        or originals[1] != toa_capture
        or originals[2] != catalog_report
        or originals[3] != stock_report
        or originals[4] != blocker_review
        or originals[5] != close_code_catalog
    ):
        raise AssertionError("Os documentos de entrada foram modificados")

    blockers_active = [
        _canonical_blocker(audit_blockers[code], code)
        for code in EXPECTED_CODES
    ]
    return {
        "schema": PLAN_SCHEMA,
        "mode": "offline_stock_remediation_plan",
        "contract": contract,
        "activity_aid": activity_aid,
        "material_os": material_os,
        "installer_id": installer_id,
        "stock_id": stock_report.get("stock_id"),
        "profile": stock_report.get("profile"),
        "source_stock_read_at": stock_report.get("read_at"),
        "evidence_files": evidence_files or [],
        "materials": plans,
        "blockers_before": blockers_active,
        "blockers_active": blockers_active,
        "blockers_removable": [],
        "new_stock_read_required_after_regularization": True,
        "external_actions_executed": [],
        "aliases_created": [],
        "equivalences_authorized": [],
        "operational_close_code_context": close_code_context,
        "payload_generated": False,
        "safety": {
            "datasnap_read_executed": False,
            "datasnap_write_executed": False,
            "post_executed": False,
            "stock_movement_executed": False,
            "close_executed": False,
            "payload_generated": False,
        },
    }


def render_text(plan: dict) -> str:
    lines = [
        "PLANO OFFLINE DE REGULARIZACAO DE ESTOQUE",
        "",
        f"Contrato: {plan['contract']}",
        f"AID: {plan['activity_aid']}",
        f"OS de materiais: {plan['material_os']}",
        f"Installer ID: {plan['installer_id']}",
        f"Stock ID: {plan['stock_id']}",
        f"Perfil: {plan['profile']}",
        f"Leitura de origem: {plan['source_stock_read_at']}",
        "",
    ]
    for material in plan["materials"]:
        unit = material["unit_evidence"]
        actions = material["actions"]
        lines.extend(
            [
                f"{material['code']} | {material['current_state'].upper()}",
                f"  Descricao: {material['description']}",
                f"  ID oficial: {material['official_material_id']}",
                f"  INVID: {material['invid']}",
                f"  Quantidade exigida: {material['required_quantity']}",
                (
                    "  Quantidade disponivel: "
                    f"{material['available_quantity'] or 'ausente'}"
                ),
                f"  Deficit: {material['deficit_quantity']}",
                (
                    "  Unidade: "
                    f"{unit['unit'] or 'null'} "
                    f"({unit['status']})"
                ),
                f"  Acao externa necessaria: {actions['external_action']}",
                "  Acao executada: nao",
                (
                    "  Evidencia futura: nova leitura do mesmo installer_id, "
                    "stock_id e codigo concreto com saldo suficiente."
                ),
                "  Blocker ativo: sim",
                "",
            ]
        )
    lines.append("BLOCKERS ATIVOS")
    lines.extend(f"- {value}" for value in plan["blockers_active"])
    close_context = plan["operational_close_code_context"]
    lines.extend(
        [
            "",
            "REFERENCIA OPERACIONAL CONDICIONADA",
            (
                f"- Codigo {close_context['code']} | "
                f"{close_context['description']} | "
                f"pagina {close_context['source']['page']}"
            ),
            (
                "- Uso somente se a visita ocorreu e a falta de material "
                "ou equipamento impediu efetivamente o servico."
            ),
            "- Selecao automatica autorizada: nao",
            "- Blocker de estoque isolado autoriza o codigo: nao",
            "",
            "Nenhum blocker foi removido.",
            "Nenhuma acao externa foi executada.",
            "Nenhum encerramento de OS foi executado.",
            "Nenhum payload operacional foi gerado.",
            "Uma nova leitura sera necessaria depois da regularizacao.",
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


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Gera plano offline de regularizacao a partir de artefatos locais."
        ),
    )
    parser.add_argument("--contract", default=EXPECTED_CONTRACT)
    parser.add_argument("--installer-id", type=int, default=EXPECTED_INSTALLER_ID)
    parser.add_argument("--inspection", required=True)
    parser.add_argument("--toa-capture", required=True)
    parser.add_argument("--catalog-report", required=True)
    parser.add_argument("--stock-report", required=True)
    parser.add_argument("--blocker-review", required=True)
    parser.add_argument("--close-code-catalog", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--text-output")
    args = parser.parse_args(argv)

    source_paths = (
        args.inspection,
        args.toa_capture,
        args.catalog_report,
        args.stock_report,
        args.blocker_review,
        args.close_code_catalog,
    )
    evidence_files = [
        {
            "path": str(Path(path).as_posix()),
            "sha256": sha256_file(path),
        }
        for path in source_paths
    ]
    plan = build_stock_remediation_plan(
        load_json_object(args.inspection),
        load_json_object(args.toa_capture),
        load_json_object(args.catalog_report),
        load_json_object(args.stock_report),
        load_json_object(args.blocker_review),
        load_json_object(args.close_code_catalog),
        contract=args.contract,
        installer_id=args.installer_id,
        evidence_files=evidence_files,
    )
    _write_json_atomic(Path(args.output), plan)
    if args.text_output:
        _write_text_atomic(Path(args.text_output), render_text(plan))
    print(
        json.dumps(
            {
                "report": args.output,
                "blockers_active": plan["blockers_active"],
                "external_actions_executed": [],
                "payload_generated": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
