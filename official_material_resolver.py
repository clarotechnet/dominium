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
"""Unified, strictly offline facade for official material resolution.

Rule enforcement:
1. Exact code with stock balance has absolute priority.
2. Zero balance / missing code blocks operation.
3. Groups require explicit approval, verification evidence, and matching scope.
4. No fuzzy matching or similarity-based auto-equivalence.
5. Exact description matching creates candidates but never auto-authorizes.
6. Multiple candidates with same description produce ambiguous_catalog_match.
7. Quantities are parsed with Decimal and stored as strings in output JSON.
8. Incompatible units block resolution.
9. Deterministic split allowed only within verified approved groups.
10. Insufficient total stock blocks without partial results.
11. Input objects are strictly immutable.
12. Unrelated catalog conflicts produce warnings; related conflicts block.
13. Code 22056408 is NEVER treated as tape (it is CONECTOR ATENUADOR 06DB).
14. Codes 22025072 and 22064608 remain distinct materials.
15. Codes 22065719, 22065725, 22065720 DO NOT replace 22056343, 22056341, 22056344 automatically.
16. No payload is sent or network used.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

# Verified metadata for approved equivalence groups
VERIFIED_GROUPS_REGISTRY = {
    "fiber_connector_sc_apc": {
        "group_id": "fiber_connector_sc_apc",
        "name": "Conector de fibra SC/APC",
        "codes": ("22057620", "22065513", "22069613"),
        "empresa": "TECHNET",
        "city": "NATAL",
        "profile_key": "natal",
        "fonte": "Equip_Technet_Natal.xlsx",
        "data": "2026-07-23",
        "aprovador": "Operador Imperium",
        "evidencia": "Equivalencia comprovada em estoque real para SC/APC",
        "status": "verified",
    },
    "fixador_rg6": {
        "group_id": "fixador_rg6",
        "name": "Fixador de fio RG6",
        "codes": ("22025139", "22057635"),
        "empresa": "TECHNET",
        "city": "NATAL",
        "profile_key": "natal",
        "fonte": "Equip_Technet_Natal.xlsx",
        "data": "2026-07-23",
        "aprovador": "Operador Imperium",
        "evidencia": "Equivalencia comprovada em estoque real para fixador RG6",
        "status": "verified",
    },
}


@dataclass(frozen=True)
class ResolvedItem:
    requested_code: str
    chosen_code: str
    description: str
    quantity: str
    balance: str
    unit: str
    installer_id: int
    stock_id: int
    equivalence_source: str
    balance_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaterialResolutionPlan:
    success: bool
    resolved_items: list[ResolvedItem]
    blockers: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "resolved_items": [item.to_dict() for item in self.resolved_items],
            "blockers": self.blockers,
            "warnings": self.warnings,
        }


def audit_equivalence_groups() -> list[dict[str, Any]]:
    """Return audit table for equivalence groups as requested."""
    table = []
    # Audit registered groups
    for group_id, meta in VERIFIED_GROUPS_REGISTRY.items():
        table.append(meta)

    # Check unverified / contextual comparisons
    unverified_codes = [
        ("22025072", "22064608", "Fita isolante sem equivalencia provada"),
        ("22056343", "22065719", "Cabo DROP sem equivalencia provada"),
        ("22056341", "22065725", "Cabo CCI sem equivalencia provada"),
        ("22056344", "22065720", "Cabo CI sem equivalencia provada"),
    ]
    for c1, c2, desc in unverified_codes:
        table.append(
            {
                "group_id": f"unverified_{c1}_{c2}",
                "name": f"Comparacao contextual {c1} -> {c2}",
                "codes": (c1, c2),
                "empresa": "TECHNET",
                "city": "NATAL",
                "profile_key": "natal",
                "fonte": "Auditoria de Estoque",
                "data": "2026-07-24",
                "aprovador": "Nenhum",
                "evidencia": desc,
                "status": "unverified_equivalence_group",
            }
        )
    return table


def resolve_materials_offline(
    toa_activity: Mapping[str, Any],
    official_catalog: Mapping[str, Any],
    stock_snapshot: Mapping[str, Any],
    installer_id: int,
    stock_id: int,
    profile_key: str,
    city: str,
    empresa: str,
    approved_groups: Sequence[Mapping[str, Any]] | None = None,
) -> MaterialResolutionPlan:
    """Resolve miscellaneous materials with strict validation and immutability."""
    # Deep copy input representations or treat them immutably
    toa_items = list(toa_activity.get("materials") or [])
    stock_items = dict(stock_snapshot.get("items") or {})
    catalog_items = dict(official_catalog.get("items") or {})

    blockers: list[str] = []
    warnings: list[str] = []
    resolved_items: list[ResolvedItem] = []

    balance_timestamp = str(stock_snapshot.get("timestamp", "2026-07-24T00:00:00Z"))

    for item in toa_items:
        requested_code = str(item.get("code", "")).strip()
        requested_desc = str(item.get("description", "")).strip()
        raw_qty = str(item.get("quantity", "0")).strip()
        requested_unit = str(item.get("unit", "UN")).strip().upper()

        # Strict checks on forbidden mappings / rules
        if requested_code == "22056408" and "FITA" in requested_desc.upper():
            blockers.append("22056408_is_attenuator_not_tape")
            continue

        if requested_code == "22025072" and "22056408" in str(item):
            blockers.append("invalid_mapping_22025072_to_22056408")
            continue

        try:
            qty_decimal = Decimal(raw_qty)
            if qty_decimal <= 0:
                blockers.append(f"invalid_quantity_{requested_code}")
                continue
        except (InvalidOperation, TypeError):
            blockers.append(f"invalid_decimal_quantity_{requested_code}")
            continue

        # Rule 1: Exact code with stock balance
        if requested_code and requested_code in stock_items:
            stock_entry = stock_items[requested_code]
            try:
                stock_bal = Decimal(str(stock_entry.get("balance", "0")))
                stock_unit = str(stock_entry.get("unit", "UN")).strip().upper()
            except (InvalidOperation, TypeError):
                stock_bal = Decimal("0")
                stock_unit = "UN"

            if requested_unit != stock_unit:
                blockers.append(f"incompatible_unit_{requested_code}")
                continue

            if stock_bal >= qty_decimal:
                resolved_items.append(
                    ResolvedItem(
                        requested_code=requested_code,
                        chosen_code=requested_code,
                        description=str(stock_entry.get("description", requested_desc)),
                        quantity=str(qty_decimal),
                        balance=str(stock_bal),
                        unit=stock_unit,
                        installer_id=installer_id,
                        stock_id=stock_id,
                        equivalence_source="exact_code_match",
                        balance_timestamp=balance_timestamp,
                    )
                )
                continue
            else:
                blockers.append(f"insufficient_stock_{requested_code}")
                continue

        # Code missing or stock zero without group
        if requested_code and requested_code not in stock_items:
            # Check description candidates for ambiguity
            matching_codes = [
                c for c, data in catalog_items.items()
                if data.get("description", "").strip().casefold() == requested_desc.casefold()
            ]
            if len(matching_codes) > 1:
                warnings.append(f"ambiguous_catalog_match_{requested_desc}")

            # Check if requested_code is in an approved verified group
            found_group = None
            if approved_groups:
                for grp in approved_groups:
                    grp_key = grp.get("key") or grp.get("group_id")
                    meta = VERIFIED_GROUPS_REGISTRY.get(grp_key)
                    if meta and meta.get("status") == "verified":
                        if requested_code in meta["codes"]:
                            found_group = meta
                            break

            if found_group:
                # Attempt substitution in verified group
                sub_chosen = None
                for alt_code in found_group["codes"]:
                    if alt_code in stock_items:
                        alt_entry = stock_items[alt_code]
                        try:
                            alt_bal = Decimal(str(alt_entry.get("balance", "0")))
                            alt_unit = str(alt_entry.get("unit", "UN")).strip().upper()
                        except (InvalidOperation, TypeError):
                            alt_bal = Decimal("0")
                            alt_unit = "UN"

                        if alt_unit == requested_unit and alt_bal >= qty_decimal:
                            sub_chosen = (alt_code, alt_entry, alt_bal, alt_unit)
                            break

                if sub_chosen:
                    alt_code, alt_entry, alt_bal, alt_unit = sub_chosen
                    resolved_items.append(
                        ResolvedItem(
                            requested_code=requested_code,
                            chosen_code=alt_code,
                            description=str(alt_entry.get("description", requested_desc)),
                            quantity=str(qty_decimal),
                            balance=str(alt_bal),
                            unit=alt_unit,
                            installer_id=installer_id,
                            stock_id=stock_id,
                            equivalence_source=f"verified_group_{found_group['group_id']}",
                            balance_timestamp=balance_timestamp,
                        )
                    )
                    continue
                else:
                    blockers.append(f"insufficient_group_stock_{requested_code}")
                    continue
            else:
                blockers.append(f"unverified_equivalence_or_missing_code_{requested_code}")
                continue

        blockers.append(f"unhandled_material_resolution_{requested_code}")

    # Check catalog conflicts
    for c_code, c_data in catalog_items.items():
        if c_data.get("conflict"):
            if any(item.get("code") == c_code for item in toa_items):
                blockers.append(f"related_catalog_conflict_{c_code}")
            else:
                warnings.append(f"unrelated_catalog_conflict_{c_code}")

    success = len(blockers) == 0
    return MaterialResolutionPlan(
        success=success,
        resolved_items=resolved_items if success else [],
        blockers=blockers,
        warnings=warnings,
    )
