"""Capturably identical READ-ONLY Imperium equipment report requests.

The wire packet generator was validated against the original 2026-11-03
ClientVCL Equipamentos Utilizados requests using a LOCAL capture. No
PCAP, credential, identifier from a customer, or response row is bundled.

Do not treat this as the six-sheet Atlas reconciliation report; it fetches
only the two original Imperium source datasets.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import struct
from pathlib import Path

try:
    from .used_equipment_report import (
        PARAM_MARKER, END_MARKER, PARAM_NAMES, PREPARE_METHOD,
        PROFILE_PORTS, PROVIDERS, load_contract, normalize_range,
        validate_capture_packet,
    )
except ImportError:  # script invocation with integrations/serial_consult on sys.path
    from used_equipment_report import (
        PARAM_MARKER, END_MARKER, PARAM_NAMES, PREPARE_METHOD,
        PROFILE_PORTS, PROVIDERS, load_contract, normalize_range,
        validate_capture_packet,
    )

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COLS = {
    "consolidado": {"Grupo", "CodigoEquipamento", "Equipamento", "Identificado", "Qtd"},
    "por_os": {"DataBaixa", "NumeroWO", "NumOs", "CodigoEquipamento", "Equipamento", "Qtd"},
}
# Non-secret SHA256 references of exact requests observed on 2026-11-05:
# NET/Natal 03/11/2026 partner=1 service=% group=%.
CAPTURED_SHA256 = {
    "consolidado": "b593109aad507e5f7296949a553506433af7115b92f198670f2b56168bbb680d",
    "por_os": "31ad439e925001de6838f90ad6da2e2e180a3bb4f21869efa0e25b48df7d0a02",
}
# Record offsets are documented static Delphi control/metadata bytes, not
# dates, partner ids, service/group values, session handles or secrets.
# The base templates come from different QUERY/stock forms; without these
# corrections the request differed in six bytes and failed live attempts.
CAPTURED_RECORD_CONTROLS = {
    "@DataIni": ((56, 9, 36), (82, 0, 3)),
    "@DataFim": ((56, 9, 36), (82, 0, 3)),
    "@IdTipoServico": ((76, 5, 4),),
    "@IdGrupoEquipamento": ((86, 10, 50),),
}


def _records(packet: bytes) -> dict[str, bytes]:
    if not isinstance(packet, bytes) or len(packet) < 50:
        raise ValueError("Pacote MIDAS vazio")
    size = packet[0] - 32
    if not 5 <= size <= 80 or packet[1 + size:6 + size] != b"!\x01\x60a\x01":
        raise ValueError("Envelope DataSnap inesperado")
    if not packet.endswith(END_MARKER):
        raise ValueError("Pacote incompleto")
    positions = [m.start() for m in re.finditer(re.escape(PARAM_MARKER), packet)]
    if not positions or len(positions) > 20:
        raise ValueError("Parâmetros ausentes ou excessivos")
    out = {}
    for i, pos in enumerate(positions):
        length = struct.unpack_from("<I", packet, pos + len(PARAM_MARKER))[0]
        if length < 1 or length > 80:
            raise ValueError("Nome de parâmetro inválido")
        at = pos + len(PARAM_MARKER) + 4
        name = packet[at:at + length * 2].decode("utf-16le")
        stop = positions[i + 1] if i + 1 < len(positions) else len(packet) - len(END_MARKER)
        if name in out:
            raise ValueError("Parâmetro duplicado")
        out[name] = packet[pos:stop]
    return out


def _value(record: bytes, name: str, value: str | int | float, kind: int) -> bytes:
    at = len(PARAM_MARKER) + 4 + 2 * len(name)
    if struct.unpack_from("<I", record, at)[0] != kind:
        raise ValueError("Tipo divergente: " + name)
    if kind == 7:
        new = struct.pack("<d", value)
        end = at + 12
    elif kind == 3:
        new = struct.pack("<I", value)
        end = at + 8
    elif kind == 8:
        old_size = struct.unpack_from("<I", record, at + 4)[0]
        end = at + 8 + old_size * 2
        new = struct.pack("<I", len(value)) + value.encode("utf-16le")
    else:
        raise ValueError("Tipo de parâmetro não autorizado")
    if end > len(record):
        raise ValueError("Parâmetro truncado")
    return record[:at + 4] + new + record[end:]


def _rename(record: bytes, old: str, new: str) -> bytes:
    at = len(PARAM_MARKER) + 4
    if record[at:at + 2 * len(old)] != old.encode("utf-16le"):
        raise ValueError("Campo de origem inesperado")
    return (record[:len(PARAM_MARKER)] + struct.pack("<I", len(new))
            + new.encode("utf-16le") + record[at + 2 * len(old):])


def _captured_controls(record: bytes, name: str) -> bytes:
    buffer = bytearray(record)
    for offset, expected, actual in CAPTURED_RECORD_CONTROLS.get(name, ()):
        if offset >= len(buffer) or buffer[offset] != expected:
            raise ValueError("Controle DataSnap divergente: " + name)
        buffer[offset] = actual
    return bytes(buffer)


def build_query(
    start: str,
    end: str,
    *,
    mode: str,
    partner_id: int,
    service: str = "%",
    group: str = "%",
    root: Path = ROOT,
    today: dt.date | None = None,
) -> bytes:
    """Generate the exact READ request bytes without connecting to DataSnap."""
    load_contract()
    if mode not in PROVIDERS:
        raise ValueError("Modo inválido")
    begin, finish = normalize_range(start, end, today=today)
    if isinstance(partner_id, bool) or not isinstance(partner_id, int) or not 1 <= partner_id <= 9999:
        raise ValueError("ID do parceiro não confirmado")
    if any(not isinstance(v, str) or not re.fullmatch(r"[A-Z0-9%,_-]{1,15}", v)
           for v in (service, group)):
        raise ValueError("Filtro de serviço/grupo inválido")
    root = Path(root)
    o = _records(base64.b64decode(json.loads(
        (root / "protocol_templates.json").read_text(encoding="utf-8")
    )["main_query"]))
    s = _records(base64.b64decode(json.loads(
        (root / "stock_protocol_templates.json").read_text(encoding="utf-8")
    )["items"]["query"]))
    serial = lambda date, end_of_day: (
        float((date - dt.date(1899, 12, 30)).days)
        + (1 - 1 / 86400000 if end_of_day else 0)
    )
    records = {
        "@RETURN_VALUE": o["@RETURN_VALUE"],
        "@DataIni": _value(o["@DataIni"], "@DataIni", serial(begin, False), 7),
        "@DataFim": _value(o["@DataFim"], "@DataFim", serial(finish, True), 7),
        "@IdParceiro": _value(s["@IdParceiro"], "@IdParceiro", partner_id, 3),
        "@IdTipoServico": _value(o["@IdTipoServico"], "@IdTipoServico", service, 8),
        "@IdGrupoEquipamento": _value(
            _rename(s["@IdGrupoEquipamentos"], "@IdGrupoEquipamentos",
                    "@IdGrupoEquipamento"),
            "@IdGrupoEquipamento", group, 8,
        ),
    }
    record_bytes = [
        _captured_controls(records[name], name) for name in PARAM_NAMES
    ]
    body = (PARAM_MARKER[:12] + struct.pack("<I", len(record_bytes) - 1)
            + b"".join(record_bytes) + END_MARKER)
    count = len(body) - 8
    if count > 65535:
        raise ValueError("Requisição excessiva")
    provider = PROVIDERS[mode].encode("ascii")
    packet = (bytes([32 + len(provider)]) + provider + b"!\x01\x60a\x01"
              + b"\x20\x10" + bytes([count // 256, count % 256, 2]) + body)
    validate_capture_packet(packet, mode)
    return packet


def fetch_read_only(
    start: str,
    end: str,
    *,
    profile: str,
    partner_id: int,
    credential_path: Path,
    service: str = "%",
    group: str = "%",
    timeout: float = 25,
) -> dict[str, list[dict]]:
    """Fetch both Imperium datasets over a single authenticated DataSnap session.

    Not wired to HTTP, not a scheduled job, and NEVER issues AS_Execute,
    movements, stock transfers, OS baixa or any other mutation.
    The caller must already be authorized to access this profile.
    """
    if profile not in PROFILE_PORTS:
        raise ValueError("Cidade não autorizada")
    if not 1 <= timeout <= 40:
        raise ValueError("Timeout inválido")
    packets = {
        mode: build_query(start, end, mode=mode, partner_id=partner_id,
                          service=service, group=group)
        for mode in PROVIDERS
    }
    from datasnap_client import DataSnapClient, load_credentials
    from imperium_api import HOST, ImperiumAPI
    try:
        from .midas_reader import decode_dataset, PacketError
    except ImportError:
        from midas_reader import decode_dataset, PacketError

    credentials = load_credentials(Path(credential_path))
    results: dict[str, list[dict]] = {}
    with DataSnapClient(
        HOST, PROFILE_PORTS[profile], credentials["username"],
        credentials["password"], timeout=timeout,
    ) as client:
        handle = ImperiumAPI._handle(client, PREPARE_METHOD)
        for mode, packet in packets.items():
            raw = ImperiumAPI._dataset_payload(
                client, handle, packet, "Equipamentos Utilizados " + mode
            )
            rows = decode_dataset(raw)
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise PacketError("Dataset não é uma lista de registros")
            if rows and not EXPECTED_COLS[mode].issubset(rows[0]):
                raise PacketError("Colunas inesperadas do relatório " + mode)
            results[mode] = rows
    return results
