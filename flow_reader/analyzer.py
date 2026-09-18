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
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import io
import ipaddress
import re
import struct
import zipfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


IMPERIUM_PORTS = {
    212: "Natal / Parnamirim",
    596: "Fortaleza",
    579: "Mossoro",
    599: "Recife / JCR",
}
MAX_CAPTURE_BYTES = 256 * 1024 * 1024
MAX_FLOWS = 20_000
MAX_PREVIEW_BYTES = 320

CLOSE_CODES = {
    "000": "CANCELAMENTO",
    "106": "CLIENTE AUSENTE",
    "306": "NAO RESIDE NO ENDERECO",
    "312": "NAO SOLICITOU SERVICO",
    "400": "CORRECAO DE CADASTRO",
    "404": "CLIENTE RECUSA-SE DEVOLVER EQUIPAMENTO",
    "409": "INSTALACAO CONCLUIDA",
    "430": "EQUIPAMENTO RETIRADO",
    "512": "CONTROLE REMOTO COM DEFEITO - TROCA",
    "706": "CHIP ENTREGUE",
}

FILTER_FIELDS = (
    "Status",
    "IdTipoServico",
    "IdOs",
    "NumOs",
    "NumeroOs",
    "Contrato",
    "IdContrato",
    "IdInstalador",
    "IdPessoa",
    "IdEstoque",
    "Serial",
    "Descricao",
)

METHOD_RE = re.compile(rb'"method":"([a-z_]+)', re.IGNORECASE)
PREPARE_TARGET_RE = re.compile(
    rb'"DataSnap\.ServerMethod","([^"]+)"', re.IGNORECASE
)
HANDLE_RE = re.compile(rb'"handle":\[(\d+)\]')
MORE_BLOB_HANDLE_RE = re.compile(rb'"params":\[(\d+)')
ERROR_RE = re.compile(rb'"error"\s*:\s*"([^"]{1,500})', re.IGNORECASE)
ASCII_RUN_RE = re.compile(rb"[\x20-\x7e]{4,160}")
DIGIT_RUN_RE = re.compile(rb"(?<!\d)(\d{6,20})(?!\d)")
SERIAL_RE = re.compile(rb"(?<![A-Za-z0-9])([A-Z0-9._/-]{8,24})(?![A-Za-z0-9])")


class CaptureFormatError(ValueError):
    pass


@dataclass(frozen=True)
class PacketSegment:
    sequence: int
    payload: bytes
    push: bool
    timestamp: float


@dataclass
class StreamDirection:
    segments: list[PacketSegment] = field(default_factory=list)


@dataclass
class TcpStream:
    stream_id: int
    client_ip: str
    client_port: int
    server_ip: str
    server_port: int
    started_at: float
    client: StreamDirection = field(default_factory=StreamDirection)
    server: StreamDirection = field(default_factory=StreamDirection)
    packet_count: int = 0
    payload_bytes: int = 0


@dataclass(frozen=True)
class ApplicationMessage:
    direction: str
    started_at: float
    ended_at: float
    payload: bytes
    boundary: str


def _timestamp_iso(value: float) -> str:
    return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat(
        timespec="milliseconds"
    )


def _safe_decode(value: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("latin-1", errors="replace")


def _select_capture(content: bytes, filename: str) -> tuple[bytes, str, str]:
    if len(content) > MAX_CAPTURE_BYTES:
        raise CaptureFormatError("A captura ultrapassa o limite de 256 MB")
    lower = filename.lower()
    if lower.endswith(".pcapng"):
        return content, Path(filename).name, ""
    if not lower.endswith(".zip"):
        raise CaptureFormatError("Selecione um arquivo ZIP ou PCAPNG")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            candidates = [
                item
                for item in archive.infolist()
                if not item.is_dir() and item.filename.lower().endswith(".pcapng")
            ]
            if not candidates:
                raise CaptureFormatError("O ZIP nao contem um arquivo PCAPNG")
            if len(candidates) > 1:
                candidates.sort(key=lambda item: item.file_size, reverse=True)
            selected = candidates[0]
            if selected.file_size > MAX_CAPTURE_BYTES:
                raise CaptureFormatError("O PCAPNG do ZIP ultrapassa 256 MB")
            pcap = archive.read(selected)
            info = ""
            info_entry = next(
                (
                    item
                    for item in archive.infolist()
                    if not item.is_dir()
                    and Path(item.filename).name.upper() == "INFORMACOES.TXT"
                ),
                None,
            )
            if info_entry and info_entry.file_size <= 128 * 1024:
                info = _safe_decode(archive.read(info_entry)).strip()
            return pcap, Path(selected.filename).name, info
    except zipfile.BadZipFile as exc:
        raise CaptureFormatError("O arquivo ZIP esta corrompido ou incompleto") from exc


def _pcapng_options(
    data: bytes,
    start: int,
    end: int,
    endian: str,
) -> dict[int, list[bytes]]:
    result: dict[int, list[bytes]] = defaultdict(list)
    position = start
    while position + 4 <= end:
        code, length = struct.unpack_from(endian + "HH", data, position)
        position += 4
        if code == 0:
            break
        padded = (length + 3) & ~3
        if position + padded > end:
            break
        result[code].append(data[position : position + length])
        position += padded
    return result


def _timestamp_resolution(options: dict[int, list[bytes]]) -> float:
    values = options.get(9)
    if not values or not values[0]:
        return 1_000_000.0
    raw = values[0][0]
    return float(2 ** (raw & 0x7F) if raw & 0x80 else 10**raw)


def _network_payload(frame: bytes, link_type: int) -> tuple[bytes, int] | None:
    if link_type == 1:
        if len(frame) < 14:
            return None
        ethertype = struct.unpack_from("!H", frame, 12)[0]
        offset = 14
        while ethertype in (0x8100, 0x88A8, 0x9100):
            if len(frame) < offset + 4:
                return None
            ethertype = struct.unpack_from("!H", frame, offset + 2)[0]
            offset += 4
        return frame[offset:], ethertype
    if link_type in (101, 228):
        version = frame[0] >> 4 if frame else 0
        return frame, 0x0800 if version == 4 else 0x86DD
    return None


def _tcp_packet(
    frame: bytes,
    link_type: int,
) -> tuple[str, str, int, int, int, int, bytes] | None:
    network = _network_payload(frame, link_type)
    if network is None:
        return None
    packet, ethertype = network
    if ethertype == 0x0800:
        if len(packet) < 20 or packet[0] >> 4 != 4:
            return None
        header_length = (packet[0] & 0x0F) * 4
        if header_length < 20 or len(packet) < header_length + 20:
            return None
        if packet[9] != 6:
            return None
        fragment = struct.unpack_from("!H", packet, 6)[0]
        if fragment & 0x1FFF:
            return None
        source = str(ipaddress.ip_address(packet[12:16]))
        destination = str(ipaddress.ip_address(packet[16:20]))
        tcp_offset = header_length
    elif ethertype == 0x86DD:
        if len(packet) < 60 or packet[0] >> 4 != 6 or packet[6] != 6:
            return None
        source = str(ipaddress.ip_address(packet[8:24]))
        destination = str(ipaddress.ip_address(packet[24:40]))
        tcp_offset = 40
    else:
        return None
    source_port, destination_port = struct.unpack_from("!HH", packet, tcp_offset)
    sequence = struct.unpack_from("!I", packet, tcp_offset + 4)[0]
    data_offset = (packet[tcp_offset + 12] >> 4) * 4
    if data_offset < 20 or len(packet) < tcp_offset + data_offset:
        return None
    flags = packet[tcp_offset + 13]
    payload = packet[tcp_offset + data_offset :]
    return (
        source,
        destination,
        source_port,
        destination_port,
        sequence,
        flags,
        payload,
    )


def _read_streams(data: bytes) -> tuple[list[TcpStream], dict]:
    if len(data) < 12 or data[:4] != b"\x0a\x0d\x0d\x0a":
        raise CaptureFormatError("O arquivo nao e um PCAPNG valido")
    position = 0
    endian = "<"
    interfaces: list[tuple[int, float]] = []
    streams: dict[tuple[str, int, str, int, int], TcpStream] = {}
    active_sessions: dict[tuple[str, int, str, int], int] = {}
    next_stream_id = 1
    block_counts: Counter[str] = Counter()
    packet_count = 0
    ignored_packets = 0
    first_timestamp: float | None = None
    last_timestamp: float | None = None

    while position + 12 <= len(data):
        if data[position : position + 4] == b"\x0a\x0d\x0d\x0a":
            byte_order = data[position + 8 : position + 12]
            if byte_order == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif byte_order == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                raise CaptureFormatError("PCAPNG com ordem de bytes desconhecida")
            block_type = 0x0A0D0D0A
            interfaces = []
        else:
            block_type = struct.unpack_from(endian + "I", data, position)[0]
        block_length = struct.unpack_from(endian + "I", data, position + 4)[0]
        if (
            block_length < 12
            or block_length % 4
            or position + block_length > len(data)
        ):
            raise CaptureFormatError(
                f"Bloco PCAPNG invalido na posicao {position}"
            )
        trailing = struct.unpack_from(
            endian + "I", data, position + block_length - 4
        )[0]
        if trailing != block_length:
            raise CaptureFormatError(
                f"Bloco PCAPNG incompleto na posicao {position}"
            )
        block_counts[f"0x{block_type:08x}"] += 1

        if block_type == 1:
            if block_length < 20:
                raise CaptureFormatError("Interface PCAPNG incompleta")
            link_type = struct.unpack_from(endian + "H", data, position + 8)[0]
            options = _pcapng_options(
                data,
                position + 16,
                position + block_length - 4,
                endian,
            )
            interfaces.append((link_type, _timestamp_resolution(options)))
        elif block_type == 6:
            if block_length < 32:
                raise CaptureFormatError("Pacote PCAPNG incompleto")
            interface_id, high, low, captured_length = struct.unpack_from(
                endian + "IIII", data, position + 8
            )
            if interface_id >= len(interfaces):
                ignored_packets += 1
                position += block_length
                continue
            frame_start = position + 28
            frame_end = frame_start + captured_length
            if frame_end > position + block_length - 4:
                raise CaptureFormatError("Pacote PCAPNG truncado")
            link_type, resolution = interfaces[interface_id]
            timestamp = ((high << 32) | low) / resolution
            parsed = _tcp_packet(data[frame_start:frame_end], link_type)
            packet_count += 1
            if parsed is None:
                ignored_packets += 1
                position += block_length
                continue
            (
                source,
                destination,
                source_port,
                destination_port,
                sequence,
                flags,
                payload,
            ) = parsed
            if source_port not in IMPERIUM_PORTS and destination_port not in IMPERIUM_PORTS:
                ignored_packets += 1
                position += block_length
                continue
            from_server = source_port in IMPERIUM_PORTS
            client_ip = destination if from_server else source
            client_port = destination_port if from_server else source_port
            server_ip = source if from_server else destination
            server_port = source_port if from_server else destination_port
            endpoint = (client_ip, client_port, server_ip, server_port)
            syn = bool(flags & 0x02)
            ack = bool(flags & 0x10)
            if syn and not ack:
                active_sessions[endpoint] = active_sessions.get(endpoint, -1) + 1
            session = active_sessions.setdefault(endpoint, 0)
            stream_key = (*endpoint, session)
            stream = streams.get(stream_key)
            if stream is None:
                stream = TcpStream(
                    stream_id=next_stream_id,
                    client_ip=client_ip,
                    client_port=client_port,
                    server_ip=server_ip,
                    server_port=server_port,
                    started_at=timestamp,
                )
                streams[stream_key] = stream
                next_stream_id += 1
            stream.packet_count += 1
            stream.payload_bytes += len(payload)
            if payload:
                segment = PacketSegment(
                    sequence=sequence,
                    payload=payload,
                    push=bool(flags & 0x08),
                    timestamp=timestamp,
                )
                target = stream.server if from_server else stream.client
                target.segments.append(segment)
            first_timestamp = (
                timestamp
                if first_timestamp is None
                else min(first_timestamp, timestamp)
            )
            last_timestamp = (
                timestamp
                if last_timestamp is None
                else max(last_timestamp, timestamp)
            )
        position += block_length

    if position != len(data):
        raise CaptureFormatError("Existem bytes incompletos no final do PCAPNG")
    return list(streams.values()), {
        "packet_count": packet_count,
        "ignored_packet_count": ignored_packets,
        "stream_count": len(streams),
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "block_counts": dict(block_counts),
        "interface_count": len(interfaces),
    }


def _reassemble(
    segments: Iterable[PacketSegment],
    direction: str,
) -> list[ApplicationMessage]:
    preferred: dict[int, PacketSegment] = {}
    for segment in segments:
        previous = preferred.get(segment.sequence)
        if previous is None or len(segment.payload) > len(previous.payload):
            preferred[segment.sequence] = segment
        elif len(segment.payload) == len(previous.payload) and segment.push:
            preferred[segment.sequence] = segment
    ordered = sorted(preferred.values(), key=lambda item: item.sequence)
    messages: list[ApplicationMessage] = []
    buffer = bytearray()
    current_end: int | None = None
    started_at = 0.0
    ended_at = 0.0

    def flush(boundary: str) -> None:
        nonlocal buffer, current_end, started_at, ended_at
        if buffer:
            messages.append(
                ApplicationMessage(
                    direction=direction,
                    started_at=started_at,
                    ended_at=ended_at,
                    payload=bytes(buffer),
                    boundary=boundary,
                )
            )
        buffer = bytearray()
        current_end = None
        started_at = 0.0
        ended_at = 0.0

    for segment in ordered:
        sequence = segment.sequence
        end = sequence + len(segment.payload)
        if current_end is None:
            buffer.extend(segment.payload)
            current_end = end
            started_at = segment.timestamp
            ended_at = segment.timestamp
        elif sequence > current_end:
            flush("tcp_gap")
            buffer.extend(segment.payload)
            current_end = end
            started_at = segment.timestamp
            ended_at = segment.timestamp
        elif end > current_end:
            overlap = current_end - sequence
            buffer.extend(segment.payload[overlap:])
            current_end = end
            ended_at = max(ended_at, segment.timestamp)
        if segment.push:
            flush("push")
    flush("stream_end")
    return messages


def _method(payload: bytes) -> str:
    match = METHOD_RE.search(payload)
    return match.group(1).decode("ascii", errors="replace").lower() if match else ""


def _prepare_target(payload: bytes) -> str:
    match = PREPARE_TARGET_RE.search(payload)
    return _safe_decode(match.group(1)) if match else ""


def _request_handle(payload: bytes, method: str) -> int | None:
    expression = MORE_BLOB_HANDLE_RE if method == "more_blob" else HANDLE_RE
    match = expression.search(payload)
    return int(match.group(1)) if match else None


def _response_handle(payload: bytes) -> int | None:
    match = HANDLE_RE.search(payload)
    return int(match.group(1)) if match else None


def _extract_filters(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in FILTER_FIELDS:
        marker = name.encode("utf-16le")
        start = 0
        while True:
            position = payload.find(marker, start)
            if position < 0:
                break
            meta = position + len(marker)
            start = meta
            if meta + 8 > len(payload):
                continue
            value_type, length = struct.unpack_from("<II", payload, meta)
            if length > 512 or meta + 8 + length > len(payload):
                continue
            raw = payload[meta + 8 : meta + 8 + length]
            # DataSnap query parameters captured from the official client use
            # type 8. Dataset schemas contain the same UTF-16 field names, so
            # accepting arbitrary types here would create false filters.
            if value_type != 8 or not raw or b"\x00" in raw:
                continue
            value = _safe_decode(raw).strip()
            if not value or any(ord(character) < 32 for character in value):
                continue
            if value:
                result[name] = value
    return result


def _extract_close_codes(payload: bytes, is_write: bool) -> list[dict]:
    if not is_write:
        return []
    found: list[dict] = []
    for wire_code, description in CLOSE_CODES.items():
        marker = wire_code.encode("ascii")
        positions = [
            match.start()
            for match in re.finditer(re.escape(marker), payload)
        ]
        if not positions:
            continue
        strong = any(
            position > 0
            and payload[position - 1] in (3, len(marker))
            for position in positions
        )
        if strong or description.encode("ascii", errors="ignore")[:8] in payload.upper():
            found.append(
                {
                    "code": "0" if wire_code == "000" else wire_code,
                    "wire_code": wire_code,
                    "description": description,
                    "confidence": "high" if strong else "medium",
                }
            )
    return found


def _extract_numbers(payload: bytes, is_write: bool) -> dict[str, list[str]]:
    values = {match.group(1).decode("ascii") for match in DIGIT_RUN_RE.finditer(payload)}
    contracts = sorted(value for value in values if 6 <= len(value) <= 8)[:30]
    order_numbers = sorted(value for value in values if 9 <= len(value) <= 11)[:30]
    serials: set[str] = {
        value for value in values if 12 <= len(value) <= 20
    }
    if is_write:
        for match in SERIAL_RE.finditer(payload.upper()):
            candidate = match.group(1).decode("ascii", errors="ignore")
            if (
                any(character.isdigit() for character in candidate)
                and not candidate.isdigit()
                and not candidate.startswith(("DATASNAP", "APPLYUPDATES"))
            ):
                serials.add(candidate)
    return {
        "contracts": contracts,
        "order_numbers": order_numbers,
        "serials": sorted(serials)[:40],
    }


def _text_fragments(payload: bytes) -> list[str]:
    ignored_prefixes = (
        '{"method"',
        '{"result"',
        '"params"',
        "PROVFLAGS",
        "SUBTYPE",
        "WIDTH",
        "DECIMALS",
    )
    values: list[str] = []
    seen: set[str] = set()
    for raw in ASCII_RUN_RE.findall(payload):
        value = " ".join(_safe_decode(raw).split())
        if not value or value.startswith(ignored_prefixes):
            continue
        if not any(character.isalpha() for character in value):
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
        if len(values) >= 18:
            break
    return values


def _preview(payload: bytes) -> str:
    clipped = payload[:MAX_PREVIEW_BYTES]
    result = []
    for byte in clipped:
        if 32 <= byte <= 126:
            result.append(chr(byte))
        elif byte in (9, 10, 13):
            result.append(" ")
        else:
            result.append(".")
    text = "".join(result)
    return text + ("..." if len(payload) > len(clipped) else "")


def _classify(method: str, server_method: str) -> tuple[str, str, str]:
    target = server_method.lower()
    if method in {"connect", "disconnect", "command_close", "reader_close"}:
        return "session", "Sessao", "Controle de conexao"
    if method == "prepare":
        prepared = server_method.rsplit(".", 1)[0].removeprefix("TDtm")
        write_capable = "applyupdates" in target or "as_apply" in target
        return (
            "prepare",
            f"Preparar {'escrita de ' if write_capable else ''}{prepared}" if prepared else "Preparacao de metodo",
            "prepara alteracao; nao executada" if write_capable else "somente leitura",
        )
    if "applyupdates" in target or "as_apply" in target:
        category = "write"
    elif "as_getrecords" in target or method == "more_blob":
        category = "query"
    elif target:
        category = "action"
    else:
        category = "transport"

    if "ordemservico" in target and category == "write":
        label = "Baixa / alteracao de OS"
    elif "ordemservico" in target:
        label = "Consulta de OS"
    elif "movestoque" in target or "estoque" in target:
        label = "Estoque / movimentacao"
    elif "equipamento" in target:
        label = "Equipamentos"
    elif "usuario" in target or "instalador" in target:
        label = "Tecnicos / usuarios"
    elif "pessoa" in target or "cliente" in target:
        label = "Cliente / contrato"
    elif target:
        label = server_method.rsplit(".", 1)[0].removeprefix("TDtm")
    elif method == "prepare":
        label = "Preparacao de metodo"
    elif method == "execute":
        label = "Execucao sem metodo resolvido"
    else:
        label = method.replace("_", " ").title() or "Payload TCP"
    risk = "altera dados" if category in {"write", "action"} else "somente leitura"
    return category, label, risk


def _response_state(payload: bytes) -> tuple[str, str]:
    if not payload:
        return "pending", "Sem resposta associada"
    error = ERROR_RE.search(payload)
    if error:
        return "error", _safe_decode(error.group(1))
    if b'"result"' in payload:
        return "ok", "Resposta recebida"
    return "unknown", "Resposta binaria"


def _analyze_stream(stream: TcpStream) -> list[dict]:
    messages = _reassemble(stream.client.segments, "client") + _reassemble(
        stream.server.segments, "server"
    )
    messages.sort(key=lambda item: (item.started_at, item.direction != "client"))
    pending: deque[int] = deque()
    operations: list[dict] = []
    handles: dict[int, str] = {}

    for message in messages:
        if message.direction == "client":
            method = _method(message.payload)
            if not method:
                continue
            target = _prepare_target(message.payload) if method == "prepare" else ""
            handle = _request_handle(message.payload, method)
            if not target and handle is not None:
                target = handles.get(handle, "")
            category, label, risk = _classify(method, target)
            is_write = category == "write"
            numbers = _extract_numbers(message.payload, is_write)
            operation = {
                "stream_id": stream.stream_id,
                "timestamp": _timestamp_iso(message.started_at),
                "timestamp_epoch": round(message.started_at, 6),
                "duration_ms": round(
                    max(0.0, message.ended_at - message.started_at) * 1000,
                    2,
                ),
                "base": IMPERIUM_PORTS.get(stream.server_port, "Desconhecida"),
                "port": stream.server_port,
                "client": f"{stream.client_ip}:{stream.client_port}",
                "server": f"{stream.server_ip}:{stream.server_port}",
                "method": method,
                "server_method": target,
                "handle": handle,
                "category": category,
                "label": label,
                "risk": risk,
                "status": "pending",
                "status_detail": "Sem resposta associada",
                "request_bytes": len(message.payload),
                "response_bytes": 0,
                "request_sha256": hashlib.sha256(message.payload).hexdigest(),
                "request_base64": base64.b64encode(message.payload).decode("ascii"),
                "response_sha256": "",
                "boundary": message.boundary,
                "filters": _extract_filters(message.payload),
                "close_codes": _extract_close_codes(message.payload, is_write),
                "contracts": numbers["contracts"],
                "order_numbers": numbers["order_numbers"],
                "serials": numbers["serials"],
                "text_fragments": _text_fragments(message.payload),
                "request_preview": _preview(message.payload),
                "response_preview": "",
            }
            operations.append(operation)
            pending.append(len(operations) - 1)
        else:
            if not pending:
                continue
            index = pending.popleft()
            operation = operations[index]
            operation["response_bytes"] = len(message.payload)
            operation["response_sha256"] = hashlib.sha256(
                message.payload
            ).hexdigest()
            operation["response_preview"] = _preview(message.payload)
            operation["status"], operation["status_detail"] = _response_state(
                message.payload
            )
            operation["duration_ms"] = round(
                max(0.0, message.ended_at - operation["timestamp_epoch"]) * 1000,
                2,
            )
            if operation["method"] == "prepare":
                response_handle = _response_handle(message.payload)
                if response_handle is not None and operation["server_method"]:
                    handles[response_handle] = operation["server_method"]
                    operation["handle"] = response_handle

    # A handle may be learned after operations were created when timestamps tie.
    for operation in operations:
        if not operation["server_method"] and operation["handle"] in handles:
            operation["server_method"] = handles[operation["handle"]]
            category, label, risk = _classify(
                operation["method"], operation["server_method"]
            )
            operation.update(category=category, label=label, risk=risk)
    return operations


def _summary(operations: list[dict], capture: dict) -> dict:
    category_counts = Counter(item["category"] for item in operations)
    status_counts = Counter(item["status"] for item in operations)
    port_counts = Counter(str(item["port"]) for item in operations)
    method_counts = Counter(
        item["server_method"] or item["method"] for item in operations
    )
    close_codes = Counter(
        code["code"]
        for item in operations
        for code in item["close_codes"]
    )
    prepared_write_methods = Counter(
        item["server_method"]
        for item in operations
        if item["category"] == "prepare"
        and ("applyupdates" in item["server_method"].lower() or "as_apply" in item["server_method"].lower())
    )
    first = capture.get("first_timestamp")
    last = capture.get("last_timestamp")
    return {
        "flow_count": len(operations),
        "query_count": category_counts["query"],
        "write_count": category_counts["write"],
        "prepared_write_count": sum(prepared_write_methods.values()),
        "prepared_write_methods": [
            {"method": method, "count": count}
            for method, count in prepared_write_methods.most_common()
        ],
        "action_count": category_counts["action"],
        "error_count": status_counts["error"],
        "unresolved_count": sum(
            1
            for item in operations
            if item["method"] in {"execute", "more_blob"}
            and not item["server_method"]
        ),
        "category_counts": dict(category_counts),
        "status_counts": dict(status_counts),
        "port_counts": dict(port_counts),
        "close_code_counts": dict(close_codes),
        "top_methods": [
            {"method": method, "count": count}
            for method, count in method_counts.most_common(30)
        ],
        "started_at": _timestamp_iso(first) if first is not None else "",
        "finished_at": _timestamp_iso(last) if last is not None else "",
        "duration_seconds": round(max(0.0, last - first), 3)
        if first is not None and last is not None
        else 0,
    }


def analyze_capture(content: bytes, filename: str = "captura.pcapng") -> dict:
    pcap, pcap_name, notes = _select_capture(content, filename)
    streams, capture = _read_streams(pcap)
    operations: list[dict] = []
    for stream in streams:
        operations.extend(_analyze_stream(stream))
        if len(operations) > MAX_FLOWS:
            raise CaptureFormatError(
                "A captura possui mais de 20 mil fluxos reconhecidos"
            )
    operations.sort(key=lambda item: (item["timestamp_epoch"], item["stream_id"]))
    for index, operation in enumerate(operations, start=1):
        operation["id"] = index
        operation.pop("timestamp_epoch", None)
    summary = _summary(operations, capture)
    return {
        "ok": True,
        "reader": {
            "name": "DOMINIUM FlowScope",
            "version": "1.0.0",
            "mode": "read_only",
        },
        "source": {
            "filename": Path(filename).name,
            "pcapng_filename": pcap_name,
            "sha256": hashlib.sha256(pcap).hexdigest(),
            "size_bytes": len(pcap),
            "notes": notes,
        },
        "capture": capture,
        "summary": summary,
        "flows": operations,
    }
