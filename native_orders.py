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
import json
import re
import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NativeContractContext:
    contract: str
    os_numbers: tuple[str, ...]
    client: str
    address: str
    city: str
    person_id: int
    number: str
    complement: str
    district: str
    state: str
    zip_code: str
    address_type: str


@dataclass(frozen=True)
class NativeService:
    id_service: int
    code: str
    name: str


def normalize_text(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
        .split()
    )


def short_text(value: str) -> bytes:
    encoded = str(value).encode("cp1252")
    if len(encoded) > 255:
        raise ValueError("Campo do cadastro nativo excede 255 caracteres")
    return bytes((len(encoded),)) + encoded


def nullable_text(value: str) -> bytes:
    return short_text(value) if value else b"\x01\x00"


def read_short_text(payload: bytes, position: int) -> tuple[str, int]:
    if position >= len(payload):
        raise ValueError("Registro de contrato incompleto")
    length = payload[position]
    position += 1
    end = position + length
    if end > len(payload):
        raise ValueError("Texto de contrato incompleto")
    return payload[position:end].decode("cp1252", errors="replace"), end


class NativeOrderProtocol:
    def __init__(
        self,
        template_path: Path,
        profile_key: str,
        controller_id: int,
    ) -> None:
        templates = json.loads(template_path.read_text(encoding="ascii"))
        if templates.get("version") != 1:
            raise ValueError("Unsupported native order protocol template version")
        self.profile_key = str(profile_key).strip().lower()
        self.controller_id = int(controller_id)
        self.captured_date = dt.date.fromisoformat(templates["captured_date"])
        self.apply_method = str(templates["apply_method"])
        lookup = templates["contract_lookup"]
        self.contract_method = str(lookup["server_method"])
        self.contract_query_template = base64.b64decode(lookup["query"])
        self.contract_marker = str(lookup["contract_marker"])
        self.services = {
            normalize_text(name): NativeService(
                int(values["id"]),
                str(values["code"]),
                str(values["name"]),
            )
            for name, values in templates.get("services", {})
            .get(self.profile_key, {})
            .items()
        }
        profile = templates.get("profiles", {}).get(self.profile_key)
        self.enabled = profile is not None
        if profile is None:
            self.prefix = b""
            self.record_template = b""
            self.suffix = b""
            self.captured = {}
            return
        self.prefix = base64.b64decode(profile["prefix"])
        self.record_template = base64.b64decode(profile["record"])
        self.suffix = base64.b64decode(profile["suffix"])
        self.captured = dict(profile["captured"])
        if (
            len(self.prefix) < 32
            or len(self.record_template) < 100
            or not self.suffix
            or not self.services
        ):
            raise ValueError("Invalid native order protocol template")

    def service(self, value: str) -> NativeService:
        try:
            return self.services[normalize_text(value)]
        except KeyError as exc:
            available = ", ".join(sorted(self.services))
            raise ValueError(
                f"Tipo de OS ainda nao mapeado para esta base. Disponiveis: {available}"
            ) from exc

    def contract_query(self, contract: str) -> bytes:
        if not re.fullmatch(r"\d{7}", contract):
            raise ValueError("A criacao nativa requer contrato com 7 digitos")
        marker = self.contract_marker.encode("utf-16le")
        replacement = contract.encode("utf-16le")
        if self.contract_query_template.count(marker) != 1:
            raise ValueError("Marcador da consulta nativa de contrato invalido")
        return self.contract_query_template.replace(marker, replacement, 1)

    @staticmethod
    def contains_os(payload: bytes, os_number: str) -> bool:
        candidates = {str(os_number).strip()}
        compact = re.sub(r"\s+", "", str(os_number))
        if compact:
            candidates.add(compact)
        for candidate in candidates:
            encoded = candidate.encode("ascii")
            if len(encoded) <= 255 and bytes((len(encoded),)) + encoded in payload:
                return True
        return False

    @staticmethod
    def _order_numbers(payload: bytes, contract: str) -> tuple[str, ...]:
        numbers = []
        for match in re.finditer(rb"[\x01-\x14](\d{1,20})", payload):
            number = match.group(1).decode("ascii")
            position = match.end()
            if position >= len(payload):
                continue
            length = payload[position]
            candidate = payload[position + 1 : position + 1 + length]
            if candidate == contract.encode("ascii") and number not in numbers:
                numbers.append(number)
        return tuple(numbers)

    @classmethod
    def parse_contract(cls, payload: bytes, contract: str) -> NativeContractContext:
        os_numbers = cls._order_numbers(payload, contract)
        contract_marker = short_text(contract)
        partnership_marker = short_text("NET")
        search_position = 0
        while True:
            contract_position = payload.find(contract_marker, search_position)
            if contract_position < 0:
                break
            row = payload[contract_position : contract_position + 1600]
            partnership = row.find(partnership_marker)
            if partnership < 0:
                search_position = contract_position + len(contract_marker)
                continue
            try:
                position = partnership + len(partnership_marker)
                _, position = read_short_text(row, position)  # Cor
                position += 2  # Status
                first_value, position = read_short_text(row, position)
                if re.fullmatch(r"[A-Z]{2,5}\d{1,3}[A-Z0-9]{0,3}", first_value):
                    client, position = read_short_text(row, position)
                else:
                    # Manual orders can omit Node entirely.
                    client = first_value
                address, position = read_short_text(row, position)

                if (
                    position + 1 < len(row)
                    and row[position] == 1
                    and row[position + 1 : position + 2] in (b"A", b"C")
                ):
                    house_apartment, position = read_short_text(row, position)
                else:
                    # Manual orders omit the optional Casa/Apto field entirely.
                    house_apartment = ""
                position += 4  # IdControladorBaixa
                _, position = read_short_text(row, position)

                location = None
                for city_position in range(position, min(position + 64, len(row))):
                    try:
                        city, tail_position = read_short_text(row, city_position)
                        normalized_city = normalize_text(city)
                        if not re.fullmatch(
                            r"[A-Z][A-Z .'-]{2,39}",
                            normalized_city,
                        ):
                            continue
                        if row[tail_position] == 0:
                            tail_position += 1
                            if (
                                tail_position < len(row)
                                and row[tail_position] == 0
                            ):
                                tail_position += 1
                        else:
                            close_code, next_position = read_short_text(
                                row,
                                tail_position,
                            )
                            if not (close_code.isdigit() and len(close_code) <= 3):
                                continue
                            _, tail_position = read_short_text(row, next_position)
                        person_id = struct.unpack_from(
                            "<I",
                            row,
                            tail_position,
                        )[0]
                        tail_position += 4
                        number, tail_position = read_short_text(row, tail_position)
                        complement, tail_position = read_short_text(
                            row,
                            tail_position,
                        )
                        district, tail_position = read_short_text(
                            row,
                            tail_position,
                        )
                        state, tail_position = read_short_text(row, tail_position)
                        zip_code, tail_position = read_short_text(
                            row,
                            tail_position,
                        )
                        if re.fullmatch(r"\d{11}|\d{14}", zip_code):
                            zip_code, tail_position = read_short_text(
                                row,
                                tail_position,
                            )
                        if (
                            person_id > 0
                            and city
                            and district
                            and re.fullmatch(r"[A-Z]{2}", state)
                            and re.fullmatch(r"\d{8}", zip_code)
                        ):
                            location = (
                                city,
                                person_id,
                                number,
                                complement,
                                district,
                                state,
                                zip_code,
                            )
                            break
                    except (IndexError, ValueError, struct.error):
                        continue
                if location is None:
                    raise ValueError("Endereco do contrato incompleto")
                (
                    city,
                    person_id,
                    number,
                    complement,
                    district,
                    state,
                    zip_code,
                ) = location
            except (ValueError, struct.error):
                search_position = contract_position + len(contract_marker)
                continue
            if (
                person_id > 0
                and client
                and address
                and city
                and district
                and re.fullmatch(r"[A-Z]{2}", state)
                and re.fullmatch(r"\d{8}", zip_code)
            ):
                address_hint = normalize_text(
                    f"{house_apartment} {complement}"
                )
                address_type = "CASA" if "CASA" in address_hint or (
                    house_apartment.upper() == "C"
                ) else "APTO"
                return NativeContractContext(
                    contract=contract,
                    os_numbers=os_numbers,
                    client=client,
                    address=address,
                    city=city,
                    person_id=person_id,
                    number=number,
                    complement=complement.replace("\x00", "").strip(),
                    district=district,
                    state=state,
                    zip_code=zip_code,
                    address_type=address_type,
                )
            search_position = contract_position + len(contract_marker)
        raise ValueError(
            f"O contrato {contract} nao retornou cliente e endereco validos no Imperium"
        )

    @staticmethod
    def _replace_short(record: bytes, old: str, new: str) -> bytes:
        marker = short_text(old)
        if record.count(marker) != 1:
            raise ValueError(f"Marcador nativo invalido: {old}")
        return record.replace(marker, short_text(new), 1)

    @staticmethod
    def _replace_integer(record: bytes, old: int, new: int, count: int = 1) -> bytes:
        marker = struct.pack("<I", int(old))
        if record.count(marker) != count:
            raise ValueError(f"Marcador inteiro nativo invalido: {old}")
        return record.replace(marker, struct.pack("<I", int(new)))

    def build_packet(
        self,
        context: NativeContractContext,
        os_number: str,
        service_name: str,
        technician_id: int,
        technician_name: str,
        order_date: dt.date,
    ) -> bytes:
        if not self.enabled:
            raise ValueError("Criacao nativa ainda nao mapeada para esta base")
        if not re.fullmatch(r"[A-Z0-9 ]{4,40}", os_number.upper()):
            raise ValueError("Numero da OS invalido para criacao nativa")
        if technician_id <= 0 or not technician_name.strip():
            raise ValueError("Tecnico invalido para criacao nativa")
        service = self.service(service_name)
        captured = self.captured
        record = self.record_template
        record = self._replace_short(record, captured["num_os"], os_number)
        record = self._replace_short(record, captured["contract"], context.contract)

        position = 4 + len(short_text(os_number)) + len(short_text(context.contract))
        if struct.unpack_from("<I", record, position)[0] != int(captured["service_id"]):
            raise ValueError("Marcador do servico nativo invalido")
        record = record[:position] + struct.pack("<I", service.id_service) + record[position + 4 :]
        position += 4
        captured_code, end = read_short_text(record, position)
        if captured_code != captured["service_code"]:
            raise ValueError("Marcador do codigo de servico nativo invalido")
        record = record[:position] + short_text(service.code) + record[end:]
        position += len(short_text(service.code))
        captured_name, end = read_short_text(record, position)
        if captured_name != captured["service_name"]:
            raise ValueError("Marcador do nome de servico nativo invalido")
        record = record[:position] + short_text(service.name) + record[end:]

        technician_marker = short_text(captured["technician_name"])
        technician_position = record.find(technician_marker)
        if technician_position < 4:
            raise ValueError("Marcador do tecnico nativo invalido")
        if struct.unpack_from("<I", record, technician_position - 4)[0] != int(
            captured["technician_id"]
        ):
            raise ValueError("Identificador do tecnico nativo invalido")
        record = (
            record[: technician_position - 4]
            + struct.pack("<I", technician_id)
            + short_text(technician_name.strip())
            + record[technician_position + len(technician_marker) :]
        )

        record = self._replace_short(record, captured["client"], context.client)
        record = self._replace_short(record, captured["address"], context.address)
        record = self._replace_short(
            record,
            captured["address_type"],
            context.address_type,
        )

        city_marker = short_text(captured["city"])
        city_position = record.rfind(city_marker)
        zip_marker = short_text(captured["zip_code"])
        zip_position = record.find(zip_marker, city_position)
        if city_position < 0 or zip_position < 0:
            raise ValueError("Marcador de endereco nativo invalido")
        location_end = zip_position + len(zip_marker)
        location = b"".join(
            (
                short_text(context.city),
                struct.pack("<I", context.person_id),
                short_text(context.number),
                nullable_text(context.complement),
                short_text(context.district),
                short_text(context.state),
                b"\x01\x00",
                short_text(context.zip_code),
            )
        )
        record = record[:city_position] + location + record[location_end:]

        captured_date = self.captured_date.toordinal()
        date_count = record.count(struct.pack("<I", captured_date))
        if date_count <= 0:
            raise ValueError("Marcador da data nativa invalido")
        record = self._replace_integer(
            record,
            captured_date,
            order_date.toordinal(),
            date_count,
        )
        captured_controller = int(captured["controller_id"])
        controller_count = record.count(struct.pack("<I", captured_controller))
        if controller_count <= 0:
            raise ValueError("Marcador do controlador nativo invalido")
        record = self._replace_integer(
            record,
            captured_controller,
            self.controller_id,
            controller_count,
        )
        record = struct.pack("<i", -1) + record[4:]

        packet = bytearray(self.prefix)
        packet.extend(record)
        packet.extend(self.suffix)
        captured_packet_length = struct.unpack_from("<I", self.prefix, 4)[0] + 23
        captured_dynamic = struct.unpack_from("<H", self.prefix, 2)[0]
        dynamic_length_base = captured_packet_length - captured_dynamic
        dynamic_length = len(packet) - dynamic_length_base
        page_delta = dynamic_length // 256 - captured_dynamic // 256
        encoded_dynamic = dynamic_length - page_delta * 256
        encoded_page = self.prefix[1] + page_delta
        if not (0 <= encoded_dynamic <= 0xFFFF and 0 <= encoded_page <= 0xFF):
            raise ValueError("Tamanho do pacote nativo invalido")
        packet[1] = encoded_page
        struct.pack_into("<H", packet, 2, encoded_dynamic)
        struct.pack_into("<I", packet, 4, len(packet) - 23)
        return b"#Dsp" + bytes(packet)
