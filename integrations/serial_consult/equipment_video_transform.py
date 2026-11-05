"""Verified part of the video-style six-tab equipment reconciliation.

The original 28/10/2026 workbook was compared locally against the real
Imperium report for that day. All 40 IMPERIUM + 4 CHIP IMPERIUM serials
were precisely the intersection of the per-OS DataSnap used equipment
and the workbook's Nomes. mapping. Atlas and Assinantes require DIFFERENT
verified sources and cannot be derived from used-equipment rows.

No remote calls, historical writes or made-up current-physical-stock values.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

EXPECTED_TABS = (
    "Atlas", "Chips Atlas", "IMPERIUM", "CHIP IMPERIUM", "Assinantes", "Nomes."
)
ATLAS_HEADERS = ("Serial", "Código", "Equipamento", "Data", "Núm. OS", "Contrato", "Usuário")
IMPERIUM_HEADERS = ("Série / Ender. Princ.", "Modelo", "DATA", "Contrato NETSMS", "Tipo Contrato UNO")
ASSINANTES_HEADERS = (
    "Serial", "Código", "Equipamento", "Data", "Contrato", "Usuário", "Estoque Físico"
)
NOMES_HEADERS = ("SERIAL", "NOME")


class VideoSourceIncomplete(ValueError):
    """A missing business source must never yield a fake successful six-tab report."""


def serial_key(value: object) -> str:
    return str(value or "").strip().upper()


def is_chip(group: object, model: object = "") -> bool:
    """Explicit group classification, not a loose 'CARD' substring match."""
    descriptor = (str(group or "") + " " + str(model or "")).upper()
    return any(token in descriptor for token in ("SIM CARD", "SMART CARD", "CHIP", "ICCID"))


def names_first_match(rows: Iterable[Mapping | list | tuple]) -> dict[str,str]:
    """Excel VLOOKUP(...,0) uses the FIRST occurrence of a serial."""
    out: dict[str,str] = {}
    for row in rows:
        if isinstance(row, Mapping):
            serial = row.get("SERIAL", row.get("Serial", ""))
            name = row.get("NOME", row.get("Nome", ""))
        elif isinstance(row, (tuple,list)) and len(row) >= 2:
            serial, name = row[0], row[1]
        else:
            raise VideoSourceIncomplete("Linha da base Nomes. inválida")
        serial=serial_key(serial)
        if not serial or serial == "SERIAL":continue
        if serial not in out:
            out[serial] = str(name or "").strip()
    return out


def imperium_video_sheets(
    used_rows: list[dict],
    names_source: Iterable[Mapping | list | tuple],
) -> tuple[list[list], list[list], list[list], dict]:
    """Reproduce the verified DATA SNAP x Nomes serial intersection.

    Output is only the three demonstrably derivable worksheets: IMPERIUM,
    CHIP IMPERIUM, Nomes. The other three tabs are not silently fabricated.
    """
    if not isinstance(used_rows, list):
        raise VideoSourceIncomplete("DataSnap por OS não fornecido")
    names=names_first_match(names_source)
    if not names:
        raise VideoSourceIncomplete("Base Nomes. inexistente; não é possível cruzar seriais")
    equipments=[list(IMPERIUM_HEADERS)]
    chips=[list(IMPERIUM_HEADERS)]
    covered=set()
    identified=set()
    unmatched=set()
    for row in used_rows:
        if not isinstance(row, dict):
            raise VideoSourceIncomplete("Registro por OS inválido")
        serial=serial_key(row.get("SerialNumber"))
        if not serial:continue
        identified.add(serial)
        if serial not in names:
            unmatched.add(serial)
            continue
        if serial in covered:continue
        covered.add(serial)
        record=[
            serial,
            str(row.get("Equipamento") or ""),
            str(row.get("DataBaixa") or ""),
            str(row.get("Contrato") or ""),
            names[serial],
        ]
        (chips if is_chip(row.get("Grupo"),row.get("Equipamento")) else equipments).append(record)
    names_tab=[list(NOMES_HEADERS)]
    names_tab.extend([[serial,name] for serial,name in names.items()])
    summary={
        "source_used_serials":len(identified),
        "matched_used_serials":len(covered),
        "unmatched_used_serials":len(unmatched),
        "imperium":len(equipments)-1,
        "chip_imperium":len(chips)-1,
        "complete_six_tab_analysis":False,
        # The 28/10 reference has a different DATA timestamp for all 44
        # matched serials. DataBaixa/ DataBaixaMiscelanea are not the video
        # workbook's validated date source; these are provisional source dates.
        "date_source_matches_video":False,
        "product_label_mapping_verified":False,
    }
    return equipments,chips,names_tab,summary


def assemble_six_verified_sheets(
    *,
    atlas_rows: list[list] | None,
    chips_atlas_rows: list[list] | None,
    imperium_rows: list[list] | None,
    chip_imperium_rows: list[list] | None,
    assinantes_rows: list[list] | None,
    nomes_rows: list[list] | None,
) -> list[tuple[str,list[list]]]:
    """Structurally assemble SIX independently supplied tables.

    This checks headers, shape, and physical status flags. It DOES NOT
    certify that the workbook reproduces the video's date provenance,
    product aliases, Atlas inclusion rules or physical stock evidence.
    A separate business-level reconciliation is mandatory before release.
    """
    values=(atlas_rows,chips_atlas_rows,imperium_rows,chip_imperium_rows,
            assinantes_rows,nomes_rows)
    if any(not isinstance(tab,list) or not tab or not isinstance(tab[0],list) for tab in values):
        raise VideoSourceIncomplete(
            "Faltam as fontes independentes Atlas, Assinantes ou Nomes.; "
            "o DataSnap não comprova sozinho a análise final de seis abas"
        )
    expected_headers=(ATLAS_HEADERS,ATLAS_HEADERS,IMPERIUM_HEADERS,
                      IMPERIUM_HEADERS,ASSINANTES_HEADERS,NOMES_HEADERS)
    for name,tab,header in zip(EXPECTED_TABS,values,expected_headers):
        if tuple(str(v) for v in tab[0]) != header:
            raise VideoSourceIncomplete("Cabeçalho incompatível com o modelo: "+name)
        if any(not isinstance(row,(list,tuple)) or len(row)!=len(header) for row in tab):
            raise VideoSourceIncomplete("Colunas inválidas do modelo: "+name)
    for row in assinantes_rows[1:]:
        physical=serial_key(row[-1])
        if physical not in ("SIM","NÃO","NAO","NS"):
            raise VideoSourceIncomplete(
                "Conferência de estoque físico de assinante ausente ou inválida; "
                "não inferir SIM/NÃO a partir do histórico DataSnap"
            )
    return list(zip(EXPECTED_TABS,values))
