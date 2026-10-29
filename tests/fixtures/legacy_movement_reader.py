"""Frozen legacy Windows reader methods used for safe CI regression tests.

Only the public binary row syntax and method bodies are captured. No records,
network destinations, access tokens, settings or customer data are present.
"""
import re
import struct
from dataclasses import dataclass, replace
from datasnap_client import DataSnapError

@dataclass(frozen=True)
class Equipment:
    id_equipment: int
    code: str
    name: str
    identified: str
    id_brand: int
    brand: str
    id_unit: int
    unit: str
    serial: str
    id_stock: int = 0
    id_group: int = 0

@dataclass(frozen=True)
class DetailContext:
    id_os: int
    contract: str
    installer_id: int
    installer_name: str

@dataclass(frozen=True)
class OrderEquipmentMovements:
    customer_serials: tuple[str, ...]
    installed: tuple[Equipment, ...]
    removed: tuple[Equipment, ...]
    materials_present: bool

class ImperiumAPI:
    @staticmethod
    def _detail_record(detail: bytes) -> bytes:
        raise NotImplementedError

    @staticmethod
    def _detail_context(detail: bytes) -> DetailContext:
        raise NotImplementedError

    @staticmethod
    def _read_short_text(data: bytes, position: int) -> tuple[str, int]:
        if position >= len(data):
            raise DataSnapError("The order detail text is incomplete")
        length = data[position]
        position += 1
        end = position + length
        if end > len(data):
            raise DataSnapError("The order detail text is incomplete")
        try:
            return data[position:end].decode("cp1252"), end
        except UnicodeDecodeError as exc:
            raise DataSnapError("The order detail text is invalid") from exc

    @staticmethod
    def _detail_u32(data: bytes, position: int) -> tuple[int, int]:
        if position < 0 or position + 4 > len(data):
            raise DataSnapError("The order equipment row is incomplete")
        return struct.unpack_from("<I", data, position)[0], position + 4

    @staticmethod
    def _detail_i32(data: bytes, position: int) -> tuple[int, int]:
        if position < 0 or position + 4 > len(data):
            raise DataSnapError("The order equipment row is incomplete")
        return struct.unpack_from("<i", data, position)[0], position + 4

    @classmethod
    def _parse_installed_detail_row(
        cls,
        record: bytes,
        position: int,
        context: DetailContext,
    ) -> tuple[Equipment, int, int]:
        marker = bytes.fromhex("040000800a0000")
        if record[position : position + len(marker)] != marker:
            raise DataSnapError("The installed equipment row marker is invalid")
        position += len(marker)
        id_os, position = cls._detail_u32(record, position)
        id_equipment, position = cls._detail_u32(record, position)
        id_stock, position = cls._detail_u32(record, position)
        temporary_id, position = cls._detail_i32(record, position)
        name, position = cls._read_short_text(record, position)
        id_brand, position = cls._detail_u32(record, position)
        brand, position = cls._read_short_text(record, position)
        id_unit, position = cls._detail_u32(record, position)
        unit, position = cls._read_short_text(record, position)
        identified, position = cls._read_short_text(record, position)
        installer_name, position = cls._read_short_text(record, position)
        trailer = bytes.fromhex("100200000000000001")
        if record[position : position + len(trailer)] != trailer:
            raise DataSnapError("The installed equipment row trailer is invalid")
        position += len(trailer)
        if (
            id_os != context.id_os
            or id_equipment <= 0
            or id_stock <= 0
            or temporary_id >= 0
            or not name
            or not installer_name
        ):
            raise DataSnapError("The installed equipment row identity is invalid")
        return (
            Equipment(
                id_equipment=id_equipment,
                code="",
                name=name,
                identified=identified,
                id_brand=id_brand,
                brand=brand,
                id_unit=id_unit,
                unit=unit,
                serial="",
                id_stock=id_stock,
                id_group=0,
            ),
            temporary_id,
            position,
        )

    @classmethod
    def _find_installed_detail_serial(
        cls,
        record: bytes,
        *,
        temporary_id: int,
        start: int,
    ) -> tuple[str, str, int]:
        for candidate in range(max(0, start), len(record)):
            try:
                position = candidate
                if record[position] != 0:
                    continue
                position += 1
                code, position = cls._read_short_text(record, position)
                quantity, position = cls._detail_u32(record, position)
                identified, position = cls._read_short_text(record, position)
                serial, position = cls._read_short_text(record, position)
                if record[position : position + 2] != b"\x01\x00":
                    continue
                position += 2
                id_group, position = cls._detail_u32(record, position)
                row_quantity, position = cls._detail_u32(record, position)
                if record[position : position + 2] != b"\x04\x00":
                    continue
                position += 2
                linked_id, position = cls._detail_i32(record, position)
                repeated_serial, position = cls._read_short_text(record, position)
                if record[position : position + 2] != b"\x01\x00":
                    continue
            except (DataSnapError, IndexError):
                continue
            normalized_serial = serial.strip().upper()
            if (
                linked_id == temporary_id
                and quantity == 1
                and row_quantity == 1
                and id_group >= 0
                and identified == "N"
                and repeated_serial.strip().upper() == normalized_serial
                and re.fullmatch(r"[A-Z0-9]{4,25}", normalized_serial)
                and code
            ):
                return normalized_serial, code, id_group
        raise DataSnapError(
            "The installed equipment serial row was not found in the order detail"
        )

    @classmethod
    def _parse_removed_detail_row(
        cls,
        record: bytes,
        position: int,
        context: DetailContext,
    ) -> tuple[Equipment, int]:
        marker = bytes.fromhex("040000200000")
        if record[position : position + len(marker)] != marker:
            raise DataSnapError("The removed equipment row marker is invalid")
        position += len(marker)
        id_os, position = cls._detail_u32(record, position)
        id_equipment, position = cls._detail_u32(record, position)
        code, position = cls._read_short_text(record, position)
        name, position = cls._read_short_text(record, position)
        identified, position = cls._read_short_text(record, position)
        id_brand, position = cls._detail_u32(record, position)
        brand, position = cls._read_short_text(record, position)
        id_unit, position = cls._detail_u32(record, position)
        unit, position = cls._read_short_text(record, position)
        serial, position = cls._read_short_text(record, position)
        repeated_id, position = cls._detail_u32(record, position)
        repeated_serial, position = cls._read_short_text(record, position)
        trailer = bytes.fromhex("01000100014e1002")
        if record[position : position + len(trailer)] != trailer:
            raise DataSnapError("The removed equipment row trailer is invalid")
        position += len(trailer)
        normalized_serial = serial.strip().upper()
        if (
            id_os != context.id_os
            or id_equipment <= 0
            or repeated_id != id_equipment
            or repeated_serial.strip().upper() != normalized_serial
            or not re.fullmatch(r"[A-Z0-9]{8,25}", normalized_serial)
            or not code
            or not name
        ):
            raise DataSnapError("The removed equipment row identity is invalid")
        return (
            Equipment(
                id_equipment=id_equipment,
                code=code,
                name=name,
                identified=identified,
                id_brand=id_brand,
                brand=brand,
                id_unit=id_unit,
                unit=unit,
                serial=normalized_serial,
            ),
            position,
        )

    @classmethod
    def read_detail_equipment_movements(
        cls,
        detail: bytes,
    ) -> OrderEquipmentMovements:
        """Decode only validated equipment structures from an OS detail packet."""

        record = cls._detail_record(detail)
        context = cls._detail_context(detail)
        id_marker = struct.pack("<I", context.id_os)
        installed_marker = bytes.fromhex("040000800a0000") + id_marker
        removed_marker = bytes.fromhex("040000200000") + id_marker
        material_marker = bytes.fromhex("0400a8a00aa002") + id_marker

        installed: list[Equipment] = []
        position = 0
        while True:
            row_position = record.find(installed_marker, position)
            if row_position < 0:
                break
            equipment, temporary_id, row_end = cls._parse_installed_detail_row(
                record,
                row_position,
                context,
            )
            serial, code, id_group = cls._find_installed_detail_serial(
                record,
                temporary_id=temporary_id,
                start=row_end,
            )
            installed.append(
                replace(
                    equipment,
                    serial=serial,
                    code=code,
                    id_group=id_group,
                )
            )
            position = row_end

        removed: list[Equipment] = []
        position = 0
        while True:
            row_position = record.find(removed_marker, position)
            if row_position < 0:
                break
            equipment, row_end = cls._parse_removed_detail_row(
                record,
                row_position,
                context,
            )
            removed.append(equipment)
            position = row_end

        customer_serials: list[str] = []
        position = 1
        while True:
            row_position = record.find(id_marker, position)
            if row_position < 0:
                break
            try:
                serial, _ = cls._read_short_text(record, row_position + 4)
            except DataSnapError:
                position = row_position + 1
                continue
            normalized = serial.strip().upper()
            if re.fullmatch(r"[A-Z0-9]{4,25}", normalized):
                customer_serials.append(normalized)
            position = row_position + 4

        def unique_equipments(values: list[Equipment]) -> tuple[Equipment, ...]:
            by_serial: dict[str, Equipment] = {}
            for equipment in values:
                if equipment.serial in by_serial:
                    raise DataSnapError(
                        "The order detail contains a duplicated equipment serial"
                    )
                by_serial[equipment.serial] = equipment
            return tuple(by_serial.values())

        return OrderEquipmentMovements(
            customer_serials=tuple(dict.fromkeys(customer_serials)),
            installed=unique_equipments(installed),
            removed=unique_equipments(removed),
            materials_present=material_marker in record,
        )
