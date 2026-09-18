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
import datetime as dt
import hashlib
import json
import struct
from pathlib import Path

from datasnap_client import DataSnapError


class SerializedTransferUncertainError(DataSnapError):
    """The write was sent, but its final stock state could not be proved."""


class SerializedTransferProtocol:
    _REQUIRED_MARKERS = {
        "controller_id",
        "source_stock_id",
        "source_stock_name",
        "source_installer_id",
        "source_technician_name",
        "target_stock_id",
        "target_stock_name",
        "target_installer_id",
        "target_technician_name",
        "equipment_id",
        "equipment_code",
        "equipment_name",
        "brand_id",
        "brand",
        "unit_id",
        "unit",
        "identified",
        "serial",
    }

    def __init__(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise DataSnapError(
                "O protocolo de transferencia serializada nao foi encontrado"
            ) from exc
        except json.JSONDecodeError as exc:
            raise DataSnapError(
                "O protocolo de transferencia serializada esta invalido"
            ) from exc

        if payload.get("version") != 1:
            raise DataSnapError(
                "Versao de transferencia serializada nao suportada"
            )
        self.profile = str(payload.get("profile", "")).strip().lower()
        self.apply_method = str(payload.get("apply_method", "")).strip()
        self.finalize_method = str(payload.get("finalize_method", "")).strip()
        template_name = str(payload.get("template_file", "")).strip()
        try:
            self.template = path.with_name(template_name).read_bytes()
            self.finalize_blob = base64.b64decode(
                str(payload.get("finalize_blob", "")),
                validate=True,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise DataSnapError(
                "Os pacotes da transferencia serializada estao invalidos"
            ) from exc
        expected_hash = str(payload.get("template_sha256", "")).lower()
        if hashlib.sha256(self.template).hexdigest() != expected_hash:
            raise DataSnapError(
                "O pacote capturado da transferencia serializada foi alterado"
            )
        if (
            not self.profile
            or not self.apply_method
            or not self.finalize_method
            or not self.template.startswith(b"#Dsp")
            or not self.finalize_blob
        ):
            raise DataSnapError(
                "O protocolo de transferencia serializada esta incompleto"
            )

        raw_markers = payload.get("markers")
        if not isinstance(raw_markers, dict):
            raise DataSnapError(
                "Os marcadores da transferencia serializada estao ausentes"
            )
        if set(raw_markers) != self._REQUIRED_MARKERS:
            raise DataSnapError(
                "Os marcadores da transferencia serializada estao incompletos"
            )
        self.markers: dict[str, dict] = {}
        occupied: list[tuple[int, int, str]] = []
        for name, raw_marker in raw_markers.items():
            if not isinstance(raw_marker, dict):
                raise DataSnapError(f"Marcador de transferencia invalido: {name}")
            kind = str(raw_marker.get("kind", "")).strip().lower()
            captured = raw_marker.get("captured")
            try:
                offsets = tuple(int(value) for value in raw_marker["offsets"])
            except (KeyError, TypeError, ValueError) as exc:
                raise DataSnapError(
                    f"Offsets de transferencia invalidos: {name}"
                ) from exc
            captured_bytes = self._encode(kind, captured)
            if not offsets:
                raise DataSnapError(f"Marcador sem offset: {name}")
            for offset in offsets:
                end = offset + len(captured_bytes)
                if (
                    offset < 0
                    or end > len(self.template)
                    or self.template[offset:end] != captured_bytes
                ):
                    raise DataSnapError(
                        f"Marcador capturado nao confere: {name}"
                    )
                occupied.append((offset, end, name))
            self.markers[name] = {
                "kind": kind,
                "captured": captured,
                "captured_bytes": captured_bytes,
                "offsets": offsets,
            }

        raw_timestamp = payload.get("timestamp")
        if not isinstance(raw_timestamp, dict):
            raise DataSnapError("Marcadores de data da transferencia ausentes")
        try:
            self.captured_timestamp = dt.datetime.fromisoformat(
                str(raw_timestamp["captured"])
            )
            self.timestamp_offsets = {
                name: int(raw_timestamp[name])
                for name in (
                    "year",
                    "month",
                    "day",
                    "hour",
                    "minute",
                    "second",
                    "millisecond",
                )
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSnapError(
                "Marcadores de data da transferencia invalidos"
            ) from exc
        captured_time_parts = self._timestamp_parts(self.captured_timestamp)
        for name, value in captured_time_parts.items():
            offset = self.timestamp_offsets[name]
            encoded = self._encode("u32" if name == "millisecond" else "u16", value)
            end = offset + len(encoded)
            if offset < 0 or end > len(self.template) or self.template[offset:end] != encoded:
                raise DataSnapError(
                    f"Marcador de data capturado nao confere: {name}"
                )
            occupied.append((offset, end, f"timestamp.{name}"))

        occupied.sort()
        for previous, current in zip(occupied, occupied[1:]):
            if previous[1] > current[0]:
                raise DataSnapError(
                    "Os marcadores da transferencia serializada se sobrepoem"
                )

    @staticmethod
    def _encode(kind: str, value: object) -> bytes:
        if kind in ("u16", "u32"):
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("Identificador de transferencia invalido") from exc
            limit = 0xFFFF if kind == "u16" else 0xFFFFFFFF
            if number < 0 or number > limit:
                raise ValueError("Identificador de transferencia fora do limite")
            return struct.pack("<H" if kind == "u16" else "<I", number)
        if kind == "short":
            try:
                encoded = str(value).encode("cp1252")
            except UnicodeEncodeError as exc:
                raise ValueError(
                    f"Texto nao suportado pelo Imperium: {value}"
                ) from exc
            if not encoded or len(encoded) > 255:
                raise ValueError("Texto da transferencia fora do limite")
            return bytes((len(encoded),)) + encoded
        raise DataSnapError(f"Codificacao de transferencia desconhecida: {kind}")

    @staticmethod
    def _timestamp_parts(value: dt.datetime) -> dict[str, int]:
        return {
            "year": value.year,
            "month": value.month,
            "day": value.day,
            "hour": value.hour,
            "minute": value.minute,
            "second": value.second,
            "millisecond": value.microsecond // 1000,
        }

    @staticmethod
    def _update_packet_lengths(blob: bytes) -> bytes:
        packet = bytearray(blob[4:])
        if len(packet) < 8:
            raise DataSnapError("Pacote de transferencia incompleto")
        captured_packet_length = struct.unpack_from("<I", packet, 4)[0] + 23
        captured_dynamic = struct.unpack_from("<H", packet, 2)[0]
        dynamic_length_base = captured_packet_length - captured_dynamic
        dynamic_length = len(packet) - dynamic_length_base
        page_delta = dynamic_length // 256 - captured_dynamic // 256
        encoded_dynamic = dynamic_length - page_delta * 256
        encoded_page = packet[1] + page_delta
        if not (0 <= encoded_dynamic <= 0xFFFF and 0 <= encoded_page <= 0xFF):
            raise DataSnapError(
                "Comprimento dinamico da transferencia fora do limite"
            )
        packet[1] = encoded_page
        struct.pack_into("<H", packet, 2, encoded_dynamic)
        struct.pack_into("<I", packet, 4, len(packet) - 23)
        return b"#Dsp" + bytes(packet)

    def build_apply(
        self,
        values: dict[str, object],
        *,
        timestamp: dt.datetime | None = None,
    ) -> bytes:
        missing = self._REQUIRED_MARKERS - set(values)
        if missing:
            raise ValueError(
                "Dados da transferencia incompletos: " + ", ".join(sorted(missing))
            )
        replacements: list[tuple[int, int, bytes]] = []
        for name, marker in self.markers.items():
            encoded = self._encode(marker["kind"], values[name])
            captured_length = len(marker["captured_bytes"])
            for offset in marker["offsets"]:
                replacements.append((offset, offset + captured_length, encoded))
        for name, value in self._timestamp_parts(timestamp or dt.datetime.now()).items():
            kind = "u32" if name == "millisecond" else "u16"
            encoded = self._encode(kind, value)
            offset = self.timestamp_offsets[name]
            replacements.append((offset, offset + len(encoded), encoded))

        replacements.sort()
        output = bytearray()
        cursor = 0
        for start, end, replacement in replacements:
            if start < cursor:
                raise DataSnapError(
                    "Os dados da transferencia se sobrepoem no pacote"
                )
            output.extend(self.template[cursor:start])
            output.extend(replacement)
            cursor = end
        output.extend(self.template[cursor:])
        return self._update_packet_lengths(bytes(output))
