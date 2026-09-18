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
import re
import struct
from dataclasses import asdict, dataclass
from decimal import Decimal

from datasnap_client import DataSnapError


@dataclass(frozen=True)
class ManualMaterial:
    stock_id: int
    equipment_id: int
    code: str
    name: str
    identified: str
    brand_id: int
    unit: str
    quantity: Decimal
    business_unit_id: int
    group_id: int
    group: str

    def to_dict(self) -> dict:
        result = asdict(self)
        result["quantity"] = format(self.quantity, "f")
        return result


@dataclass(frozen=True)
class AppliedManualMaterial:
    id_os: int
    equipment_id: int
    stock_id: int
    temporary_id: int
    name: str
    unit: str
    identified: str
    quantity: int
    code: str
    business_unit_id: int

    def to_dict(self) -> dict:
        return asdict(self)


def _read_short_text(
    payload: bytes,
    position: int,
    *,
    maximum: int,
) -> tuple[str, int]:
    if position >= len(payload):
        raise DataSnapError("Texto truncado no catalogo manual de miscelaneas")
    length = payload[position]
    end = position + 1 + length
    if length > maximum or end > len(payload):
        raise DataSnapError("Texto invalido no catalogo manual de miscelaneas")
    return payload[position + 1 : end].decode("cp1252"), end


def decode_fmtdbcd(value: bytes) -> Decimal:
    """Decode the fixed-size FMTBcd value used by the manual stock dataset."""
    if len(value) != 18:
        raise DataSnapError("Saldo truncado no catalogo manual de miscelaneas")
    precision = value[0]
    sign_and_scale = value[1]
    scale = sign_and_scale & 0x3F
    negative = bool(sign_and_scale & 0x80)
    packed_size = (precision + 1) // 2
    if not 1 <= precision <= 16 or scale > precision or 2 + packed_size > len(value):
        raise DataSnapError("Saldo invalido no catalogo manual de miscelaneas")

    digits = []
    for byte in value[2 : 2 + packed_size]:
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            raise DataSnapError("Saldo BCD invalido no catalogo manual de miscelaneas")
        digits.extend((str(high), str(low)))
    number = Decimal(int("".join(digits[:precision]) or "0")).scaleb(-scale)
    return -number if negative else number


def parse_manual_material_catalog(payload: bytes) -> list[ManualMaterial]:
    """Parse DspBaixarMiscelaneasRomaneio, the source of the manual picker."""
    materials: list[ManualMaterial] = []
    # A stock may contain the same code for different business units (for
    # example CLARO and NET). Keep both so the official integration can use
    # the balance from its own business unit.
    seen: set[tuple[int, str, int]] = set()
    for match in re.finditer(rb"\x08(\d{8})", payload):
        record_start = match.start() - 8
        if record_start < 0:
            continue
        try:
            stock_id, equipment_id = struct.unpack_from("<II", payload, record_start)
            if not (0 < stock_id < 1_000_000 and 0 < equipment_id < 1_000_000):
                continue
            code = match.group(1).decode("ascii")
            position = match.end()
            name, position = _read_short_text(payload, position, maximum=160)
            identified, position = _read_short_text(payload, position, maximum=4)
            brand_id = struct.unpack_from("<I", payload, position)[0]
            position += 4
            unit, position = _read_short_text(payload, position, maximum=12)
            quantity = decode_fmtdbcd(payload[position : position + 18])
            position += 18
            business_unit_id, group_id = struct.unpack_from("<II", payload, position)
            position += 8
            group, _ = _read_short_text(payload, position, maximum=160)
        except (DataSnapError, UnicodeDecodeError, struct.error):
            continue

        key = (stock_id, code, business_unit_id)
        if (
            key in seen
            or identified not in ("N", "S")
            or not name.strip()
            or not unit.strip()
            or quantity < 0
            or business_unit_id <= 0
            or group_id <= 0
        ):
            continue
        seen.add(key)
        materials.append(
            ManualMaterial(
                stock_id=stock_id,
                equipment_id=equipment_id,
                code=code,
                name=name.strip(),
                identified=identified,
                brand_id=brand_id,
                unit=unit.strip(),
                quantity=quantity,
                business_unit_id=business_unit_id,
                group_id=group_id,
                group=group.strip(),
            )
        )

    if not materials:
        raise DataSnapError(
            "A consulta manual de miscelaneas nao retornou itens reconheciveis"
        )
    return sorted(materials, key=lambda item: (item.group.casefold(), item.name.casefold()))


def parse_applied_manual_materials(payload: bytes) -> list[AppliedManualMaterial]:
    """Read material rows embedded in an order ApplyUpdates packet."""
    prefix = bytes.fromhex("0400a8a00aa002")
    rows: list[AppliedManualMaterial] = []
    for match in re.finditer(re.escape(prefix), payload):
        position = match.end()
        try:
            id_os, equipment_id, stock_id, temporary_id = struct.unpack_from(
                "<IIIi", payload, position
            )
            position += 16
            name, position = _read_short_text(payload, position, maximum=160)
            unit, position = _read_short_text(payload, position, maximum=12)
            identified, position = _read_short_text(payload, position, maximum=4)
            if payload[position : position + 8] != bytes.fromhex(
                "1002000000000000"
            ):
                continue
            position += 8
            quantity = struct.unpack_from("<H", payload, position)[0]
            position += 10  # quantity, continuation flag and six reserved bytes
            code, position = _read_short_text(payload, position, maximum=16)
            business_unit_id = struct.unpack_from("<I", payload, position)[0]
        except (DataSnapError, UnicodeDecodeError, struct.error):
            continue
        if (
            id_os <= 0
            or equipment_id <= 0
            or stock_id <= 0
            or not re.fullmatch(r"\d{8}", code)
            or not name.strip()
            or not unit.strip()
            or identified not in ("N", "S")
            or quantity <= 0
            or business_unit_id <= 0
        ):
            continue
        rows.append(
            AppliedManualMaterial(
                id_os=id_os,
                equipment_id=equipment_id,
                stock_id=stock_id,
                temporary_id=temporary_id,
                name=name.strip(),
                unit=unit.strip(),
                identified=identified,
                quantity=quantity,
                code=code,
                business_unit_id=business_unit_id,
            )
        )
    return rows
