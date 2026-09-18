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
import re
import unicodedata
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from typing import Iterable


# These groups contain substitutions confirmed by the operator from real
# Imperium stock. They are intentionally explicit: similarly named materials
# outside this list are never treated as interchangeable automatically.
APPROVED_EQUIVALENCE_GROUPS = (
    {
        "key": "fiber_connector_sc_apc",
        "label": "Conector de fibra SC/APC",
        "codes": ("22057620", "22065513", "22069613", "22065512"),
    },
    {
        "key": "fixador_rg6",
        "label": "Fixador de fio RG6",
        "codes": ("22025139", "22057635", "22060738"),
    },
    {
        "key": "cabo_rg6_com_mensag_preto",
        "label": "Cabo Coaxial RG6 Trish Com Mensag Preto",
        "codes": ("22026223", "22066906"),
    },
    {
        "key": "cabo_rg6_sem_mensag_branco",
        "label": "Cabo Coaxial RG6 Trish Sem Mensag Branco",
        "codes": ("22026219", "22066907"),
    },
    {
        "key": "cabo_drop_1fo",
        "label": "Cabo Drop 1FO Low Friction",
        "codes": ("22061736", "22061796", "22026267"),
    },
    {
        "key": "fita_isolante",
        "label": "Fita Isolante 3M",
        "codes": ("22025072", "22064608", "22056696"),
    },
    {
        "key": "anel_vedacao",
        "label": "Anel de Vedacao",
        "codes": ("22024800", "22025321"),
    },
    {
        "key": "mini_isolador",
        "label": "Mini Isolador CPE",
        "codes": ("22056364", "22067384"),
    },
    {
        "key": "isolador",
        "label": "Isolador Coaxial",
        "codes": ("22056366", "22066517", "22056394"),
    },
    {
        "key": "fixador_fio",
        "label": "Fixador de Fio",
        "codes": ("22025091", "22025139", "22057635", "22060738"),
    },
    {
        "key": "abracadeira",
        "label": "Abracadeira Hellermann T50R / T30R",
        "codes": ("22055828", "22023400", "22025247", "22056346"),
    },
    {
        "key": "pitao_bucha",
        "label": "Pitao com Bucha",
        "codes": ("22026502", "22056395", "22061434", "22026489"),
    },
    {
        "key": "conector_utp_rj45",
        "label": "Conector UTP RJ45",
        "codes": ("22061811", "22026169", "22059179"),
    },
    {
        "key": "conector_rg11",
        "label": "Conector RG11 F-11",
        "codes": ("22026147", "22056764"),
    },
    {
        "key": "cabo_rg11",
        "label": "Cabo Coaxial RG11",
        "codes": ("22057341", "22057156"),
    },
    {
        "key": "marcador_casa_0",
        "label": "Marcador Casa Preto 0",
        "codes": ("22056342", "22065718", "22066616", "22055829"),
    },
    {
        "key": "marcador_casa_1",
        "label": "Marcador Casa Preto 1",
        "codes": ("22056343", "22065719", "22066615", "22055830"),
    },
    {
        "key": "marcador_casa_2",
        "label": "Marcador Casa Preto 2",
        "codes": ("22056344", "22065720", "22066614", "22055831"),
    },
    {
        "key": "marcador_casa_3",
        "label": "Marcador Casa Preto 3",
        "codes": ("22056345", "22065721", "22066613", "22055832"),
    },
    {
        "key": "marcador_casa_4",
        "label": "Marcador Casa Preto 4",
        "codes": ("22056340", "22065722", "22066612", "22055833"),
    },
    {
        "key": "marcador_casa_5",
        "label": "Marcador Casa Preto 5",
        "codes": ("22056331", "22065723", "22066611", "22055835"),
    },
    {
        "key": "marcador_casa_6",
        "label": "Marcador Casa Preto 6",
        "codes": ("22056336", "22065724", "22066610"),
    },
    {
        "key": "marcador_casa_7",
        "label": "Marcador Casa Preto 7",
        "codes": ("22056341", "22065725", "22066609", "22055827"),
    },
    {
        "key": "marcador_casa_8",
        "label": "Marcador Casa Preto 8",
        "codes": ("22056337", "22065726", "22066608", "22055857"),
    },
    {
        "key": "marcador_casa_9",
        "label": "Marcador Casa Preto 9",
        "codes": ("22056339", "22065727", "22066607"),
    },
    {
        "key": "marcador_casa_a",
        "label": "Marcador Casa Preto A",
        "codes": ("22025114", "22065728"),
    },
    {
        "key": "marcador_casa_b",
        "label": "Marcador Casa Preto B",
        "codes": ("22025115", "22065729"),
    },
    {
        "key": "marcador_casa_c",
        "label": "Marcador Casa Preto C",
        "codes": ("22025116", "22065730"),
    },
    {
        "key": "marcador_casa_d",
        "label": "Marcador Casa Preto D",
        "codes": ("22025117", "22065731"),
    },
    {
        "key": "marcador_casa_e",
        "label": "Marcador Casa Preto E",
        "codes": ("22025119", "22065732"),
    },
)

_GROUP_BY_CODE = {
    code: group
    for group in APPROVED_EQUIVALENCE_GROUPS
    for code in group["codes"]
}


def approved_equivalence_group_for_code(code: object) -> dict | None:
    """Return the explicit operator-approved group for a concrete TOA code."""
    group = _GROUP_BY_CODE.get(str(code or "").strip())
    if group is None:
        return None
    return {
        "key": str(group["key"]),
        "label": str(group["label"]),
        "codes": tuple(str(item) for item in group["codes"]),
    }

# Confirmed by the operator from the real Imperium close flow. These
# accessories remain in the raw TOA capture for audit, but are not posted as
# installed miscellaneous materials.
KNOWN_NON_POSTABLE_MATERIAL_CODES = {
    "22057705": "fonte",
    "22026096": "cabo_de_forca",
    "22066009": "fonte",
    "22062576": "fonte",
    "22026272": "fonte",
    "433135": "sapatilha",
}


def extract_material_code(value: object, description: object = "") -> str:
    raw_code = str(value or "").strip()
    code_match = re.fullmatch(r"\d{6,8}", raw_code)
    description_match = re.match(
        r"^\s*(\d{6,8})(?=$|[\s_/\-])",
        str(description or ""),
    )
    code = code_match.group(0) if code_match else ""
    description_code = description_match.group(1) if description_match else ""
    if code and description_code and code != description_code:
        raise ValueError("Codigo concreto diverge entre campo e descricao TOA")
    return code or description_code


def normalize_material_name(value: str, code: str = "") -> str:
    text = " ".join(str(value or "").strip().split())
    if code:
        text = re.sub(
            rf"^(?:{re.escape(str(code))})[\s_\-]+",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
    return " ".join(
        part
        for part in re.split(
            r"[^A-Z0-9]+",
            unicodedata.normalize("NFD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
            .upper(),
        )
        if part
    )


def toa_material_ignore_reason(description: object, code: object = "") -> str:
    material_code = str(code or "").strip()
    known_reason = KNOWN_NON_POSTABLE_MATERIAL_CODES.get(material_code)
    if known_reason:
        return known_reason

    name = normalize_material_name(str(description or ""), material_code)
    raw = str(description or "").upper()
    words = set(name.split())
    if "FONTE" in words or "FONTE" in name or "FONTE" in raw or "ALIMENTAC" in name or "TRAFO" in words:
        return "fonte"
    if re.search(r"\bCABO(?: DE)? FORCA\b", name) or "FORCA" in words or "FORCA" in name:
        return "cabo_de_forca"
    if "HDMI" in words or "HDMI" in name:
        return "hdmi"
    if "PILHA" in words or "PILHAS" in words or "BATERIA" in words or "BATERIAS" in words:
        return "pilha"
    if "SAPATILHA" in words or "SAPATILHA" in name or "PROPE" in words or "DESCARTAVEL" in words or "EPI" in words:
        return "sapatilha"
    return ""


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} invalida")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} invalida") from exc
    if result <= 0 or result > 0xFFFF:
        raise ValueError(f"{label} deve estar entre 1 e 65535")
    return result


def _candidate_rows(request: dict, inventory: list[dict]) -> list[tuple[int, str, dict]]:
    code = request["code"]
    approved_group = _GROUP_BY_CODE.get(code)
    candidates: list[tuple[int, str, dict]] = []
    seen: set[str] = set()

    def add(priority: int, reason: str, item: dict) -> None:
        item_code = str(item.get("code", "")).strip()
        if not item_code or item_code in seen:
            return
        seen.add(item_code)
        candidates.append((priority, reason, item))

    for item in inventory:
        if str(item.get("code", "")).strip() == code:
            add(0, "exact_code", item)

    if approved_group is not None:
        approved_codes = set(approved_group["codes"])
        for item in inventory:
            if str(item.get("code", "")).strip() in approved_codes:
                add(1, f"approved_group:{approved_group['key']}", item)

    return candidates


def resolve_material_requests(
    requests: Iterable[dict],
    inventory: Iterable[dict],
) -> dict:
    stock = []
    for raw in inventory:
        item = dict(raw)
        item["code"] = str(item.get("code", "")).strip()
        item["name"] = str(item.get("name", "")).strip()
        item["stock_quantity"] = max(0, int(item.get("stock_quantity", 0) or 0))
        if item["code"]:
            stock.append(item)

    normalized_requests = []
    ignored_materials = []
    for raw in requests:
        description = str(raw.get("description", "")).strip()
        code = extract_material_code(raw.get("code", ""), description)
        if not re.fullmatch(r"\d{8}", code) or not description:
            raise ValueError("Codigo ou descricao TOA invalida")
        normalized = {
            "code": code,
            "description": description,
            "quantity": _positive_integer(raw.get("quantity", 0), "Quantidade TOA"),
            "point": str(raw.get("point", "")).strip(),
        }
        ignore_reason = toa_material_ignore_reason(description, code)
        if ignore_reason:
            ignored_materials.append({**normalized, "ignore_reason": ignore_reason})
            continue
        normalized_requests.append(normalized)

    allocated: dict[str, int] = {}
    rows: OrderedDict[str, dict] = OrderedDict()
    for request in normalized_requests:
        candidates = _candidate_rows(request, stock)
        quantity = request["quantity"]
        sufficient = [
            candidate
            for candidate in candidates
            if int(candidate[2]["stock_quantity"])
            - allocated.get(str(candidate[2]["code"]), 0)
            >= quantity
        ]
        if sufficient:
            priority, reason, selected = min(
                sufficient,
                key=lambda candidate: (
                    candidate[0],
                    -(
                        int(candidate[2]["stock_quantity"])
                        - allocated.get(str(candidate[2]["code"]), 0)
                    ),
                    str(candidate[2]["code"]),
                ),
            )
        elif candidates:
            priority, reason, selected = min(
                candidates,
                key=lambda candidate: (
                    candidate[0],
                    -int(candidate[2]["stock_quantity"]),
                    str(candidate[2]["code"]),
                ),
            )
        else:
            key = f"unresolved:{request['code']}"
            row = rows.setdefault(
                key,
                {
                    "code": request["code"],
                    "name": request["description"],
                    "stock_quantity": 0,
                    "unit": "",
                    "quantity": 0,
                    "status": "unresolved",
                    "source": "toa",
                    "match_type": "unresolved",
                    "requires_confirmation": False,
                    "source_codes": [],
                    "source_items": [],
                    "lookup_description": request["description"],
                },
            )
            row["quantity"] += quantity
            if request["code"] not in row["source_codes"]:
                row["source_codes"].append(request["code"])
            row["source_items"].append(dict(request))
            continue

        target_code = str(selected["code"])
        allocated[target_code] = allocated.get(target_code, 0) + quantity
        row = rows.setdefault(
            target_code,
            {
                **selected,
                "quantity": 0,
                "status": "available",
                "source": "stock",
                "match_type": "exact",
                "requires_confirmation": False,
                "source_codes": [],
                "source_items": [],
                "equivalence_reasons": [],
                "lookup_description": str(selected.get("name", "")),
            },
        )
        row["quantity"] += quantity
        if request["code"] not in row["source_codes"]:
            row["source_codes"].append(request["code"])
        source_item = dict(request)
        source_item["description_matches_stock"] = (
            normalize_material_name(request["description"], request["code"])
            == normalize_material_name(
                str(selected.get("name", "")),
                target_code,
            )
        )
        row["source_items"].append(source_item)
        if request["code"] != target_code:
            row["requires_confirmation"] = True
            row["match_type"] = "equivalent"
            if reason not in row["equivalence_reasons"]:
                row["equivalence_reasons"].append(reason)

    output = list(rows.values())
    for row in output:
        if row["status"] == "unresolved":
            continue
        if int(row["quantity"]) > int(row.get("stock_quantity", 0)):
            row["status"] = "shortage"
        elif row.get("requires_confirmation"):
            row["status"] = "equivalent"

    unresolved = [row for row in output if row["status"] == "unresolved"]
    shortages = [row for row in output if row["status"] == "shortage"]
    equivalents = [row for row in output if row.get("requires_confirmation")]
    description_mismatches = [
        item
        for row in output
        for item in row.get("source_items", [])
        if item.get("description_matches_stock") is False
    ]
    messages = []
    for row in equivalents:
        messages.append(
            f"{' + '.join(row['source_codes'])} -> {row['code']} "
            f"({row['quantity']} {row.get('unit', '')})".strip()
        )
    for row in unresolved:
        messages.append(f"{row['code']} nao localizado no estoque do tecnico")
    for row in shortages:
        messages.append(
            f"{row['code']} requer {row['quantity']} e possui "
            f"{row.get('stock_quantity', 0)}"
        )
    for item in description_mismatches:
        messages.append(
            f"{item['code']} casado por codigo concreto; descricao difere do estoque"
        )

    return {
        "materials": output,
        "ignored_materials": ignored_materials,
        "validation": {
            "request_count": len(normalized_requests) + len(ignored_materials),
            "actionable_count": len(normalized_requests),
            "ignored_count": len(ignored_materials),
            "resolved_count": len(output) - len(unresolved),
            "equivalent_count": len(equivalents),
            "unresolved_count": len(unresolved),
            "shortage_count": len(shortages),
            "description_mismatch_count": len(description_mismatches),
            "requires_confirmation": bool(equivalents),
            "can_close": not unresolved and not shortages,
            "messages": messages,
        },
    }


def _decimal_quantity(
    value: object,
    label: str,
    *,
    allow_zero: bool = False,
) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} invalida")
    try:
        quantity = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} invalida") from exc
    if not quantity.is_finite():
        raise ValueError(f"{label} invalida")
    if quantity < 0 or (quantity == 0 and not allow_zero):
        qualifier = "nao pode ser negativa" if allow_zero else "deve ser maior que zero"
        raise ValueError(f"{label} {qualifier}")
    return quantity


def distribute_by_group(
    inventory: Iterable[dict],
    group_id: int = 0,
    group_name: str = "",
    requested_quantity: object = 0,
    preferred_code: str = "",
) -> list[dict]:
    requested = _decimal_quantity(requested_quantity, "Quantidade solicitada")
    normalized_group_name = normalize_material_name(group_name)

    candidates: list[tuple[dict, Decimal]] = []
    for item in inventory:
        item_group_id = int(item.get("group_id", 0) or 0)
        item_group = str(item.get("group", "")).strip()

        selected = False
        if group_id > 0:
            if item_group_id == group_id:
                selected = True
        elif normalized_group_name:
            selected = normalize_material_name(item_group) == normalized_group_name

        if selected:
            available = _decimal_quantity(
                item.get("stock_quantity", 0),
                "Quantidade em estoque",
                allow_zero=True,
            )
            candidates.append((item, available))

    if not candidates:
        raise ValueError(f"Grupo nao localizado no estoque: {group_name or group_id}")

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            str(candidate[0].get("code", "")) != str(preferred_code),
            str(candidate[0].get("name", "")).casefold(),
            str(candidate[0].get("code", "")),
        ),
    )

    total_available = sum(
        (available for _, available in sorted_candidates),
        Decimal("0"),
    )
    if total_available < requested:
        raise ValueError(
            f"Estoque insuficiente: grupo possui {total_available}, solicitado {requested}"
        )

    result = []
    remaining = requested

    for item, available in sorted_candidates:
        if remaining <= 0:
            break

        if available <= 0:
            continue

        to_take = min(remaining, available)
        result.append(
            {
                "code": str(item.get("code", "")),
                "name": str(item.get("name", "")),
                "quantity": to_take,
                "unit": str(item.get("unit", "")),
                "group_id": int(item.get("group_id", 0) or 0),
                "group": str(item.get("group", "")),
            }
        )
        remaining -= to_take

    return result
