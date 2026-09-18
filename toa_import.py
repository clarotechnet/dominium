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
import base64
import csv
import datetime as dt
import io
import json
import re
import struct
import unicodedata
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path

from operation_scope import ImportScope


MAX_CSV_BYTES = 8 * 1024 * 1024
MAX_PREVIEW_ROWS = 5000


def _key(value: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    ).casefold().replace(".", "")
    return " ".join(
        "".join(character if character.isalnum() else " " for character in normalized)
        .split()
    )


@dataclass(frozen=True)
class TOAOrder:
    date: str
    technician: str
    activity_status: str
    address: str
    address_complement: str
    district: str
    zip_code: str
    time_window: str
    city: str
    state: str
    contract: str
    work_order: str
    node: str
    os_number: str
    point: str
    os_status: str
    os_type: str
    close_code: str
    workzone_key: str
    service_window: str = ""
    started_at: str = ""
    ended_at: str = ""
    start_end: str = ""
    sla_start: str = ""
    sla_end: str = ""
    duration: str = ""
    travel_time: str = ""
    activity_type: str = ""
    work_skills: str = ""
    work_area: str = ""
    assignment_time: str = ""
    reservation_time: str = ""
    coordinate_x: str = ""
    coordinate_y: str = ""
    technician_login: str = ""
    technician_name: str = ""
    activity_id: str = ""
    log_counter: str = "0"

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def service_name(self) -> str:
        return re.sub(r"^\s*\d+\s*-\s*", "", self.os_type).strip()

    @property
    def import_date(self) -> str:
        value = self.date.strip()
        for pattern in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(value, pattern).strftime("%d/%m/%Y")
            except ValueError:
                continue
        raise ValueError(f"Data TOA invalida na OS {self.os_number}: {value}")

    def address_parts(self) -> tuple[str, str, str]:
        address = self.address.strip()
        district_suffix = f" - {self.district}" if self.district else ""
        if district_suffix and address.upper().endswith(district_suffix.upper()):
            address = address[: -len(district_suffix)].rstrip()

        street, separator, remainder = address.partition(",")
        number = ""
        inferred_complement = ""
        if separator:
            pieces = remainder.split(",")
            number = pieces[0].strip()
            if len(pieces) > 1:
                inferred_complement = "," + ",".join(pieces[1:]).strip()

        complement = self.address_complement.strip() or inferred_complement
        if complement and not complement.startswith(","):
            complement = "," + complement
        return street.strip(), number, complement


@dataclass(frozen=True)
class TOATimelineActivity:
    date: str
    technician: str
    activity_status: str
    label: str
    time_window: str
    service_window: str
    started_at: str
    ended_at: str
    start_end: str
    duration: str
    source_row: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TOAPreview:
    filename: str
    source_rows: int
    orders: tuple[TOAOrder, ...]
    import_scope: ImportScope | None = None
    scope_exclusions: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        cities = Counter(order.city for order in self.orders if order.city)
        statuses = Counter(
            order.activity_status for order in self.orders if order.activity_status
        )
        payload = {
            "filename": self.filename,
            "source_rows": self.source_rows,
            "count": len(self.orders),
            "cities": dict(sorted(cities.items())),
            "statuses": dict(sorted(statuses.items())),
            "orders": [order.to_dict() for order in self.orders],
            "excluded_count": len(self.scope_exclusions),
            "scope_exclusions": list(self.scope_exclusions),
        }
        if self.import_scope is not None:
            payload["import_scope"] = self.import_scope.to_dict()
        return payload


def unpack_toa_content(
    content: bytes,
    filename: str = "atividades.csv",
) -> tuple[bytes, str]:
    if not content:
        raise ValueError("O arquivo CSV esta vazio")
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                has_pcap = any(
                    name.lower().endswith((".pcapng", ".pcap")) for name in names
                )
                has_gravador = any("informacoes" in name.lower() for name in names)
                if has_pcap or has_gravador:
                    raise ValueError(
                        "Este arquivo é uma captura do Gravador Imperium (.zip com pcapng). "
                        "Para importar OS no DOMINIUM, selecione a planilha CSV exportada do TOA "
                        "(ex: Atividades-PWM-DMV_VT_05_09_26.csv)."
                    )
                csv_candidates = [
                    name
                    for name in names
                    if name.lower().endswith(".csv")
                    and not name.startswith("__MACOSX/")
                    and not Path(name).name.startswith("._")
                ]
                if not csv_candidates:
                    raise ValueError(
                        "Nenhum arquivo CSV foi encontrado dentro do arquivo ZIP informado."
                    )
                chosen = csv_candidates[0]
                for name in csv_candidates:
                    if "atividade" in name.lower():
                        chosen = name
                        break
                csv_bytes = archive.read(chosen)
                return csv_bytes, Path(chosen).name
        except zipfile.BadZipFile as exc:
            raise ValueError("O arquivo ZIP esta corrompido ou e invalido.") from exc
    return content, filename


def _decode_csv(content: bytes) -> str:
    if not content:
        raise ValueError("O arquivo CSV esta vazio")
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("O arquivo CSV excede o limite de 8 MB")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("O arquivo CSV nao esta em UTF-8 nem Windows-1252")


def parse_toa_csv(content: bytes, filename: str = "atividades.csv") -> TOAPreview:
    content, filename = unpack_toa_content(content, filename)
    source = io.StringIO(_decode_csv(content), newline="")
    reader = csv.reader(source)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("O arquivo CSV nao possui cabecalho") from exc

    positions: dict[str, int] = {}
    for index, header in enumerate(headers):
        positions.setdefault(_key(header), index)

    required = (
        "data",
        "login do tecnico",
        "status da atividade",
        "cidade",
        "uf",
        "contrato",
        "numero da wo",
        "numero da os 1",
        "tipo os 1",
    )
    missing = [name for name in required if name not in positions]
    if missing:
        raise ValueError(
            "CSV TOA invalido; colunas ausentes: " + ", ".join(missing)
        )

    def value(row: list[str], name: str) -> str:
        index = positions.get(name)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    def first_value(row: list[str], *names: str) -> str:
        for name in names:
            candidate = value(row, name)
            if candidate:
                return candidate
        return ""

    orders: list[TOAOrder] = []
    scope_exclusions: list[dict] = []
    source_rows = 0
    cancelled_terms = {"cancelado", "cancelada", "suspenso", "suspensa"}
    for row in reader:
        source_rows += 1
        if len(orders) >= MAX_PREVIEW_ROWS:
            raise ValueError("O CSV excede o limite de 5.000 OS por importacao")
        for number in range(1, 11):
            os_number = value(row, f"numero da os {number}")
            if not os_number:
                continue
            activity_status = value(row, "status da atividade")
            os_status = value(row, f"status da o.s {number}")
            norm_activity = _key(activity_status)
            norm_os = _key(os_status)
            if norm_activity in cancelled_terms or norm_os in cancelled_terms:
                scope_exclusions.append(
                    {
                        "os_number": os_number,
                        "contract": value(row, "contrato"),
                        "city": value(row, "cidade").upper(),
                        "state": value(row, "uf").upper(),
                        "service": value(row, f"tipo os {number}"),
                        "reason": f"Atividade {activity_status or os_status} no TOA ignorada",
                    }
                )
                continue
            technician = value(row, "login do tecnico")
            orders.append(
                TOAOrder(
                    date=value(row, "data"),
                    technician=technician,
                    activity_status=activity_status,
                    address=value(row, "endereco"),
                    address_complement=value(row, "complemento endereco"),
                    district=value(row, "bairro"),
                    zip_code=re.sub(r"\D", "", value(row, "cep codigo postal")),
                    time_window=value(row, "intervalo de tempo"),
                    city=value(row, "cidade").upper(),
                    state=value(row, "uf").upper(),
                    contract=value(row, "contrato"),
                    work_order=value(row, "numero da wo"),
                    node=value(row, "node"),
                    os_number=os_number,
                    point=value(row, f"ponto {number}"),
                    os_status=os_status,
                    os_type=value(row, f"tipo os {number}"),
                    close_code=value(row, f"cod de baixa {number}"),
                    workzone_key=value(row, "workzone key"),
                    service_window=value(row, "janela de servico"),
                    started_at=value(row, "inicio"),
                    ended_at=value(row, "fim"),
                    start_end=value(row, "inicio fim"),
                    sla_start=value(row, "inicio do sla"),
                    sla_end=value(row, "fim do sla"),
                    duration=value(row, "duracao"),
                    travel_time=value(row, "tempo de deslocamento"),
                    activity_type=value(row, "tipo de atividade"),
                    work_skills=value(row, "habilidade de trabalho"),
                    work_area=value(row, "area de trabalho"),
                    assignment_time=value(row, "tempo de atribuicao da atividade"),
                    reservation_time=value(row, "tempo de reserva da atividade"),
                    coordinate_x=value(row, "coordenada x"),
                    coordinate_y=value(row, "coordenada y"),
                    technician_login=technician.upper(),
                    activity_id=first_value(
                        row,
                        "id da atividade",
                        "id atividade",
                        "activity id",
                        "aid",
                    ),
                    log_counter=first_value(row, "contador de log", "log") or "0",
                )
            )

    if not orders:
        if scope_exclusions:
            raise ValueError(
                f"Todas as {len(scope_exclusions)} OS encontradas no arquivo estao canceladas ou suspensas no TOA."
            )
        raise ValueError("Nenhuma OS foi encontrada nas colunas Numero da O.S 1 a 10")
    return TOAPreview(
        filename=filename,
        source_rows=source_rows,
        orders=tuple(orders),
        scope_exclusions=tuple(scope_exclusions),
    )


def parse_toa_timeline_activities(content: bytes) -> tuple[TOATimelineActivity, ...]:
    """Read non-OS timeline blocks such as the technician meal interval."""
    content, _ = unpack_toa_content(content)
    source = io.StringIO(_decode_csv(content), newline="")
    reader = csv.reader(source)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("O arquivo CSV nao possui cabecalho") from exc

    normalized_headers = [_key(header) for header in headers]

    def index_for(name: str, *, last: bool = False) -> int | None:
        matches = [
            index for index, header in enumerate(normalized_headers)
            if header == name
        ]
        if not matches:
            return None
        return matches[-1] if last else matches[0]

    def row_value(row: list[str], index: int | None) -> str:
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    login_index = index_for("login do tecnico")
    activity_index = index_for("tipo de atividade", last=True)
    if login_index is None or activity_index is None:
        return ()

    date_index = index_for("data")
    status_index = index_for("status da atividade")
    time_window_index = index_for("intervalo de tempo")
    service_window_index = index_for("janela de servico")
    started_index = index_for("inicio")
    ended_index = index_for("fim")
    start_end_index = index_for("inicio fim")
    duration_index = index_for("duracao")
    current_technician = ""
    activities: list[TOATimelineActivity] = []
    for source_row, row in enumerate(reader, start=2):
        technician = row_value(row, login_index).upper()
        if technician:
            current_technician = technician
        label = row_value(row, activity_index)
        if _key(label) not in {"refeicao", "almoco", "intervalo refeicao"}:
            continue
        started_at = row_value(row, started_index)
        ended_at = row_value(row, ended_index)
        time_window = row_value(row, time_window_index)
        # TOA may emit a second placeholder meal row carrying only the broad
        # window. It has no drawable interval and must not duplicate the pause.
        if not current_technician or not (started_at and ended_at):
            continue
        activities.append(
            TOATimelineActivity(
                date=row_value(row, date_index),
                technician=current_technician,
                activity_status=row_value(row, status_index),
                label="REFEICAO",
                time_window=time_window,
                service_window=row_value(row, service_window_index),
                started_at=started_at,
                ended_at=ended_at,
                start_end=row_value(row, start_end_index),
                duration=row_value(row, duration_index),
                source_row=source_row,
            )
        )
    return tuple(activities)


_IMPORT_FIELDS = (
    ("Img", lambda order: ""),
    ("Log", lambda order: getattr(order, "log_counter", "0") or "0"),
    ("Contrato", lambda order: order.contract),
    ("NumOs", lambda order: order.os_number),
    ("Cidade", lambda order: order.city),
    ("Node", lambda order: order.node),
    ("Cliente", lambda order: "CLIENTE"),
    ("Endereco", lambda order: order.address_parts()[0]),
    ("CodigoServico", lambda order: order.service_name),
    ("DataAgendamento", lambda order: order.import_date),
    ("Turno", lambda order: order.time_window),
    ("Instalador", lambda order: order.technician),
    ("Situacao", lambda order: ""),
    ("Numero", lambda order: order.address_parts()[1]),
    ("Complemento", lambda order: order.address_parts()[2]),
    ("Bairro", lambda order: order.district),
    ("UF", lambda order: order.state),
    ("CPFCNPJ", lambda order: ""),
    ("CEP", lambda order: order.zip_code),
    ("TelRes", lambda order: ""),
    ("TelOutros", lambda order: ""),
    ("TelComercial", lambda order: ""),
    ("TelCelular", lambda order: ""),
    ("TelFax", lambda order: ""),
    ("Arquivo", lambda order: ""),
    ("Latitude", lambda order: ""),
    ("Longitude", lambda order: ""),
    ("Produto", lambda order: ""),
    ("DataAgendamentoActivia", lambda order: order.import_date),
    ("Tipo", lambda order: ""),
    ("NumeroWO", lambda order: order.work_order),
)


def build_toa_xml(preview: TOAPreview) -> str:
    lines = [
        '<?xml version="1.0" encoding="ISO-8859-1" ?>',
        "<OrdensDeServico>",
    ]
    for order in preview.orders:
        lines.append("<OS>")
        for name, getter in _IMPORT_FIELDS:
            value = escape(str(getter(order)), quote=False)
            lines.append(f"<{name}>{value}</{name}>")
        lines.append("</OS>")
    lines.append("</OrdensDeServico>")
    return "\r\n".join(lines) + "\r\n"


class TOAImportProtocol:
    def __init__(self, template_path: Path, controller_id: int) -> None:
        try:
            template = json.loads(template_path.read_text(encoding="ascii"))
        except FileNotFoundError as exc:
            raise ValueError("O modelo do protocolo de importacao nao foi encontrado") from exc
        if template.get("version") != 1:
            raise ValueError("Versao do protocolo de importacao nao suportada")

        self.server_method = str(template["server_method"])
        self.chunk_size = int(template["chunk_size"])
        self.chunk_length_offset = int(template["chunk_length_offset"])
        self.xml_length_offset = int(template["xml_length_offset"])
        self.transport_trailer = base64.b64decode(template["transport_trailer"])
        prefix_bytes = bytearray(base64.b64decode(template["prefix"]))
        if len(prefix_bytes) > 20:
            prefix_bytes[20] = 0x10
        self.prefix = bytes(prefix_bytes)
        self.suffix = base64.b64decode(template["suffix"])

        captured_controller = struct.pack(
            "<I", int(template["captured_controller_id"])
        )
        runtime_controller = struct.pack("<I", controller_id)
        if self.suffix.count(captured_controller) != 1:
            raise ValueError("Marcador de controlador da importacao invalido")
        self.suffix = self.suffix.replace(
            captured_controller, runtime_controller, 1
        )

    def build_packet(self, preview: TOAPreview) -> bytes:
        xml = build_toa_xml(preview).encode("utf-16le")
        prefix = bytearray(self.prefix)
        struct.pack_into("<I", prefix, self.xml_length_offset, len(xml) // 2)
        packet = prefix + xml + self.suffix
        first_length = min(len(packet), self.chunk_size)
        dynamic_length = first_length - 23
        if dynamic_length < 0 or dynamic_length > 0xFFFF:
            raise ValueError("Tamanho inicial do pacote de importacao invalido")
        struct.pack_into(
            ">H", packet, self.chunk_length_offset, dynamic_length
        )
        return bytes(packet)

    def chunks(self, packet: bytes) -> tuple[bytes, ...]:
        if len(packet) <= self.chunk_size:
            return (packet + self.transport_trailer,)
        values = [packet[: self.chunk_size] + self.transport_trailer]
        values.extend(
            packet[offset : offset + self.chunk_size]
            for offset in range(self.chunk_size, len(packet), self.chunk_size)
        )
        return tuple(values)

    @staticmethod
    def incomplete_result_length(payload: bytes) -> int | None:
        """Return the full MIDAS size only when the received payload is shorter."""
        if len(payload) < 24:
            return None
        expected_length = struct.unpack_from("<I", payload, 20)[0] + 28
        return expected_length if expected_length > len(payload) else None

    @staticmethod
    def _read_short_text(payload: bytes, position: int) -> tuple[str, int]:
        if position >= len(payload):
            raise ValueError("Resultado da importacao incompleto")
        length = payload[position]
        start = position + 1
        end = start + length
        if end > len(payload):
            raise ValueError("Texto incompleto no resultado da importacao")
        return payload[start:end].decode("cp1252"), end

    @classmethod
    def _status_for(cls, payload: bytes, os_number: str) -> str:
        encoded = os_number.encode("ascii")
        marker = bytes((len(encoded),)) + encoded
        position = payload.find(marker)
        if position < 0:
            raise ValueError(
                f"O servidor nao devolveu resultado para a OS {os_number}"
            )
        position += len(marker)
        for _ in range(5):
            _, position = cls._read_short_text(payload, position)
        position += 4  # DataAgendamento no dataset MIDAS.
        _, position = cls._read_short_text(payload, position)  # Turno
        _, position = cls._read_short_text(payload, position)  # Instalador
        status, _ = cls._read_short_text(payload, position)
        return status

    @classmethod
    def parse_result(cls, payload: bytes, preview: TOAPreview) -> dict:
        rows = []
        imported = 0
        for order in preview.orders:
            status = cls._status_for(payload, order.os_number)
            normalized = _key(status)
            was_imported = (
                "importad" in normalized
                or (
                    "cadastrad" in normalized
                    and "ja cadastrad" not in normalized
                )
            )
            imported += int(was_imported)
            rows.append(
                {
                    **order.to_dict(),
                    "import_status": status,
                    "imported": was_imported,
                }
            )
        return {
            "ok": True,
            "count": len(rows),
            "imported": imported,
            "not_imported": len(rows) - imported,
            "orders": rows,
        }
