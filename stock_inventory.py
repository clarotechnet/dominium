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
import base64
import json
import re
import struct
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from datasnap_client import DataSnapError


@dataclass(frozen=True)
class StockTechnician:
    stock_id: int
    stock_name: str
    installer_id: int
    technician_name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StockSerial:
    equipment_id: int
    group_id: int
    business_unit_id: int
    serial: str
    smart: str
    boxed: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StockItem:
    equipment_id: int
    group_id: int
    group: str
    code: str
    equipment: str
    brand_id: int
    brand: str
    unit_id: int
    unit: str
    identified: str
    quantity: str
    quantity_label: str
    serials: tuple[StockSerial, ...] = ()

    @property
    def quantity_number(self) -> Decimal:
        try:
            return Decimal(self.quantity)
        except InvalidOperation:
            return Decimal(0)

    def to_dict(self) -> dict:
        value = asdict(self)
        value["serial_count"] = len(self.serials)
        return value


class StockProtocol:
    def __init__(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise DataSnapError("Os templates de estoque nao foram encontrados") from exc
        except json.JSONDecodeError as exc:
            raise DataSnapError("Os templates de estoque estao invalidos") from exc
        if payload.get("version") != 1:
            raise DataSnapError("Versao de template de estoque nao suportada")

        self.technicians_method, self.technicians_query = self._simple_template(
            payload.get("technicians"), "tecnicos"
        )
        self.items_method, self.items_template, self.items_stock_offset = (
            self._stock_template(payload.get("items"), "equipamentos")
        )
        self.serials_method, self.serials_template, self.serials_stock_offset = (
            self._stock_template(payload.get("serials"), "seriais")
        )

    @staticmethod
    def _simple_template(value: object, label: str) -> tuple[str, bytes]:
        if not isinstance(value, dict):
            raise DataSnapError(f"Template de {label} ausente")
        method = str(value.get("server_method", "")).strip()
        try:
            query = base64.b64decode(str(value.get("query", "")), validate=True)
        except ValueError as exc:
            raise DataSnapError(f"Template de {label} invalido") from exc
        if not method or not query:
            raise DataSnapError(f"Template de {label} incompleto")
        return method, query

    @classmethod
    def _stock_template(
        cls, value: object, label: str
    ) -> tuple[str, bytes, int]:
        method, query = cls._simple_template(value, label)
        assert isinstance(value, dict)
        try:
            offset = int(value["stock_id_offset"])
            captured = int(value["captured_stock_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSnapError(f"Marcador de estoque de {label} invalido") from exc
        if offset < 0 or offset + 4 > len(query):
            raise DataSnapError(f"Offset de estoque de {label} invalido")
        if struct.unpack_from("<I", query, offset)[0] != captured:
            raise DataSnapError(f"Marcador de estoque de {label} nao confere")
        return method, query, offset

    @staticmethod
    def _with_stock(template: bytes, offset: int, stock_id: int) -> bytes:
        if stock_id <= 0 or stock_id > 0x7FFFFFFF:
            raise ValueError("Estoque invalido")
        output = bytearray(template)
        struct.pack_into("<I", output, offset, stock_id)
        return bytes(output)

    def items_query(self, stock_id: int) -> bytes:
        return self._with_stock(self.items_template, self.items_stock_offset, stock_id)

    def serials_query(self, stock_id: int) -> bytes:
        return self._with_stock(self.serials_template, self.serials_stock_offset, stock_id)


def _read_short_text(payload: bytes, position: int, max_length: int) -> tuple[str, int]:
    if position >= len(payload):
        raise ValueError("fim do pacote")
    length = payload[position]
    position += 1
    if length > max_length or position + length > len(payload):
        raise ValueError("texto fora do pacote")
    raw = payload[position : position + length]
    if any(byte < 0x20 or byte == 0x7F for byte in raw):
        raise ValueError("texto binario")
    return raw.decode("cp1252", errors="replace").strip(), position + length


def _valid_name(value: str) -> bool:
    if not value:
        return False
    return all(character.isprintable() and character not in "\x00\r\n\t" for character in value)


def parse_technicians(payload: bytes) -> list[StockTechnician]:
    marker = payload.find(b"PRIMARY_KEY")
    if marker < 0:
        raise DataSnapError("A lista de tecnicos nao possui metadados validos")

    candidates: list[StockTechnician] = []
    seen: set[tuple[int, int]] = set()
    for position in range(marker, max(marker, len(payload) - 24)):
        try:
            null_flags = payload[position]
            if null_flags > 0x1F:
                continue
            stock_id = struct.unpack_from("<I", payload, position + 1)[0]
            if stock_id <= 0 or stock_id > 1_000_000:
                continue
            cursor = position + 5
            stock_name, cursor = _read_short_text(payload, cursor, 100)
            installer_id = struct.unpack_from("<I", payload, cursor)[0]
            cursor += 4
            if installer_id <= 0 or installer_id in (0xFFFFFFFF,) or installer_id > 1_000_000:
                continue
            technician_name, cursor = _read_short_text(payload, cursor, 120)
            flags: list[str] = []
            for _ in range(4):
                flag, cursor = _read_short_text(payload, cursor, 5)
                flags.append(flag)
            _email, cursor = _read_short_text(payload, cursor, 160)
            if not _valid_name(stock_name) or not _valid_name(technician_name):
                continue
            if any(flag not in ("", "N", "S") for flag in flags):
                continue
            key = (stock_id, installer_id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                StockTechnician(
                    stock_id=stock_id,
                    stock_name=stock_name,
                    installer_id=installer_id,
                    technician_name=technician_name,
                )
            )
        except (IndexError, struct.error, ValueError):
            continue

    if not candidates:
        raise DataSnapError("Nenhum estoque de tecnico foi localizado")
    return sorted(
        candidates,
        key=lambda item: (item.technician_name.casefold(), item.stock_name.casefold()),
    )


_QUANTITY_LABEL = re.compile(r"-?\d+(?:[.,]\d+)?\s+[A-Z]{1,8}$")


def _quantity_from_label(value: str) -> str:
    number = value.split(maxsplit=1)[0].replace(",", ".")
    try:
        decimal = Decimal(number)
    except InvalidOperation:
        return "0"
    normalized = format(decimal, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def parse_stock_items(payload: bytes) -> list[StockItem]:
    candidates: list[StockItem] = []
    seen: set[int] = set()
    for position in range(0, max(0, len(payload) - 80)):
        try:
            equipment_id = struct.unpack_from("<I", payload, position)[0]
            group_id = struct.unpack_from("<I", payload, position + 4)[0]
            if not (0 < equipment_id < 1_000_000 and 0 < group_id < 1_000_000):
                continue
            cursor = position + 8
            group, cursor = _read_short_text(payload, cursor, 100)
            code, cursor = _read_short_text(payload, cursor, 40)
            equipment, cursor = _read_short_text(payload, cursor, 150)
            brand_id = struct.unpack_from("<I", payload, cursor)[0]
            cursor += 4
            if not (0 < brand_id < 100_000):
                continue
            brand, cursor = _read_short_text(payload, cursor, 80)
            unit_id = struct.unpack_from("<I", payload, cursor)[0]
            cursor += 4
            if not (0 < unit_id < 10_000):
                continue
            unit, cursor = _read_short_text(payload, cursor, 12)
            identified, cursor = _read_short_text(payload, cursor, 4)
            if identified not in ("N", "S"):
                continue
            if not all((_valid_name(group), _valid_name(code), _valid_name(equipment))):
                continue

            quantity_label = ""
            for probe in range(cursor, min(cursor + 180, len(payload) - 2)):
                length = payload[probe]
                if length < 4 or length > 24 or probe + 1 + length > len(payload):
                    continue
                raw = payload[probe + 1 : probe + 1 + length]
                try:
                    text = raw.decode("ascii")
                except UnicodeDecodeError:
                    continue
                if _QUANTITY_LABEL.fullmatch(text):
                    quantity_label = text
                    break
            if not quantity_label or equipment_id in seen:
                continue
            seen.add(equipment_id)
            candidates.append(
                StockItem(
                    equipment_id=equipment_id,
                    group_id=group_id,
                    group=group,
                    code=code,
                    equipment=equipment,
                    brand_id=brand_id,
                    brand=brand,
                    unit_id=unit_id,
                    unit=unit,
                    identified=identified,
                    quantity=_quantity_from_label(quantity_label),
                    quantity_label=quantity_label,
                )
            )
        except (IndexError, struct.error, ValueError):
            continue

    if not candidates and payload[:3] != b"\xc0\xc0\x60":
        raise DataSnapError("A consulta de estoque nao retornou itens reconheciveis")
    return sorted(candidates, key=lambda item: (item.group.casefold(), item.equipment.casefold()))


def parse_stock_serials(payload: bytes) -> list[StockSerial]:
    candidates: list[StockSerial] = []
    seen: set[tuple[int, str]] = set()
    serial_pattern = re.compile(r"[A-Za-z0-9._/\-]{5,50}$")
    for position in range(0, max(0, len(payload) - 20)):
        try:
            equipment_id, group_id, business_unit_id = struct.unpack_from(
                "<III", payload, position
            )
            if not (
                0 < equipment_id < 1_000_000
                and 0 < group_id < 1_000_000
                and 0 < business_unit_id < 100_000
            ):
                continue
            cursor = position + 12
            serial, cursor = _read_short_text(payload, cursor, 60)
            smart, cursor = _read_short_text(payload, cursor, 60)
            boxed, cursor = _read_short_text(payload, cursor, 5)
            if not serial_pattern.fullmatch(serial) or boxed not in ("", "N", "S"):
                continue
            key = (equipment_id, serial.upper())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                StockSerial(
                    equipment_id=equipment_id,
                    group_id=group_id,
                    business_unit_id=business_unit_id,
                    serial=serial.upper(),
                    smart=smart.upper(),
                    boxed=boxed,
                )
            )
        except (IndexError, struct.error, ValueError):
            continue
    return candidates


def attach_serials(items: list[StockItem], serials: list[StockSerial]) -> list[StockItem]:
    by_equipment: dict[int, list[StockSerial]] = {}
    for serial in serials:
        by_equipment.setdefault(serial.equipment_id, []).append(serial)
    return [
        StockItem(
            **{
                **item.__dict__,
                "serials": tuple(
                    sorted(
                        by_equipment.get(item.equipment_id, []),
                        key=lambda value: value.serial,
                    )
                ),
            }
        )
        for item in items
    ]
