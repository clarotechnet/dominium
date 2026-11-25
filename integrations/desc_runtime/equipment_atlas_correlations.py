"""Read-only Codigo -> DescricaoAtlas correlation in the legacy runtime."""
import re
from typing import NamedTuple

PROVIDER = "TDtmEquipamentos.AS_GetRecords"
CAPTURED_CODE = "22060738"
TEMPLATE_LENGTH = 826
_TEMPLATE_PROVIDER = b"&DspLoc"
_CODE_RE = re.compile(r"[0-9]{8}")
_ITEM_RE = re.compile(r"([0-9]{8})_([^|\x00-\x1f\x7f-\x9f]{3,150})")
_LABEL_RE = re.compile(r"[^\W\d_][^_|\x00-\x1f\x7f-\x9f]{2,149}")
_UNIT_RE = re.compile(rb"[A-Z0-9]{1,12}")
# Operator-confirmed connector family, 2026-11-25. Only supported
# eight-digit codes; no prefix or numeric-zero coercion.
_CONNECTOR_CODES = ("22026266", "22056396", "22057640", "22057620",
                    "22065513", "22065512", "22069613")
_CONNECTOR_NAME = re.compile(r"^CONECTOR FO CAMPO (?:FAST |CPO )?SC[ /]?APC(?:\b|$)", re.I)



class EquipmentAtlasCorrelationError(ValueError):
    """Malformed or ambiguous read-only catalogue mapping."""


class EquipmentAtlasRecord(NamedTuple):
    codes: tuple[str, ...]
    unit: str


def build_code_query(template: bytes, code: str) -> bytes:
    if not isinstance(code, str) or _CODE_RE.fullmatch(code) is None:
        raise EquipmentAtlasCorrelationError("Codigo de equipamento invalido")
    marker = (CAPTURED_CODE + "%").encode("utf-16le")
    if (
        len(template) != TEMPLATE_LENGTH
        or not template.startswith(_TEMPLATE_PROVIDER)
        or template.count(marker) != 1
        or template.count("CodigoEquipamento".encode("utf-16le")) != 1
    ):
        raise EquipmentAtlasCorrelationError("Template de consulta por codigo invalido")
    query = template.replace(marker, (code + "%").encode("utf-16le"))
    if len(query) != TEMPLATE_LENGTH:
        raise EquipmentAtlasCorrelationError("Comprimento da consulta alterado")
    return query


def _record_unit(payload: bytes, position: int) -> str:
    # DescricaoAtlas is followed by group ID, group text, unit ID and unit text.
    group_text = position + 4
    if group_text >= len(payload):
        return ""
    unit_id = group_text + 1 + payload[group_text]
    unit_text = unit_id + 4
    if unit_text >= len(payload) or not any(payload[unit_id:unit_text]):
        return ""
    unit_end = unit_text + 1 + payload[unit_text]
    unit = payload[unit_text + 1:unit_end]
    return unit.decode("ascii") if unit_end <= len(payload) and _UNIT_RE.fullmatch(unit) else ""


def parse_code_record(payload: bytes, requested_code: str) -> EquipmentAtlasRecord:
    """Read the exact master record, including the registered unit if present."""
    if not isinstance(payload, bytes) or _CODE_RE.fullmatch(requested_code) is None:
        raise EquipmentAtlasCorrelationError("Resposta de equipamento invalida")
    records: list[EquipmentAtlasRecord] = []
    for match in re.finditer(rb"\x08([0-9]{8})", payload):
        if match.group(1).decode("ascii") != requested_code:
            continue
        pos = match.end()
        try:
            name_length = payload[pos]
            pos += 1
            if not 3 <= name_length <= 150 or pos + name_length >= len(payload):
                continue
            name = payload[pos:pos + name_length].decode("latin1")
            pos += name_length
            description_length = payload[pos]
            pos += 1
            if description_length == 0:
                # The live dataset uses a second NUL before the group ID
                # for an empty Atlas field. Require a unique valid group/unit
                # layout and a real catalogue name, not just a byte match.
                units = set()
                for offset in (pos, pos + 1) if payload[pos:pos+1] == b"\x00" else (pos,):
                    group = payload[offset:offset+4]
                    if len(group) != 4 or not 0 < int.from_bytes(group, "little") < 65536:
                        continue
                    if payload[offset+4:offset+13] != b"\x08DIVERSOS":
                        continue
                    candidate_unit = _record_unit(payload, offset)
                    if candidate_unit in {"UN", "M", "PC", "PCA", "MT"}:
                        units.add(candidate_unit)
                if len(units) != 1 or not _LABEL_RE.fullmatch(name):
                    continue
                unit = next(iter(units))
                codes = (requested_code,)
                if requested_code in _CONNECTOR_CODES:
                    if unit != "UN" or not _CONNECTOR_NAME.match(name):
                        continue
                    codes += tuple(c for c in _CONNECTOR_CODES if c != requested_code)
                # A blank Atlas field proves only the exact code. No fuzzy
                # substitution for other items; stock remains authoritative.
                records.append(EquipmentAtlasRecord(codes, unit))
                continue
            if not 10 <= description_length <= 250 or pos + description_length > len(payload):
                continue
            # The optional leading NUL is excluded from the declared length.
            if payload[pos] == 0:
                pos += 1
            if pos + description_length > len(payload):
                continue
            description_end = pos + description_length
            description = payload[pos:description_end].decode("latin1")
            fragments = [value.strip() for value in description.split("|")]
            if len(fragments) > 1 and _LABEL_RE.fullmatch(fragments[0]):
                fragments = fragments[1:]
            if not 1 <= len(fragments) <= 20:
                continue
            items = [_ITEM_RE.fullmatch(value) for value in fragments]
            if any(item is None for item in items):
                continue
            # DescricaoAtlas can list aliases only. The outer record identifies
            # the exact requested item even when that item is absent from the list.
            codes = (requested_code, *(item.group(1) for item in items))
            records.append(EquipmentAtlasRecord(
                tuple(dict.fromkeys(codes)), _record_unit(payload, description_end),
            ))
        except IndexError:
            continue
    if len(records) != 1:
        raise EquipmentAtlasCorrelationError(
            f"Cadastro da miscelanea {requested_code} ausente ou ambiguo no Atlas"
        )
    return records[0]


def parse_code_group(payload: bytes, requested_code: str) -> tuple[str, ...]:
    return parse_code_record(payload, requested_code).codes
