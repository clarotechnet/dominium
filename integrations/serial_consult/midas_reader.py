"""Bounded read-only decoder for Delphi MIDAS ClientDataSet binary packets.

Format based on DBReaderMidas (MIT), verified against captured IMPERIUM packets.
"""
from __future__ import annotations

import datetime as dt
import io
import struct
from decimal import Decimal


class PacketError(ValueError):
    pass


def _decode_bcd(raw: bytes) -> str | None:
    """Decode a Delphi MIDAS BCD cell as a JSON-safe exact decimal string.

    The wire field occupies 18 bytes (precision, sign/scale, 16 packed
    BCD bytes), even if the field metadata reports a size such as 10.
    """
    if len(raw) != 18:
        raise PacketError("Tamanho BCD invalido")
    precision, sign_special_places = raw[:2]
    if sign_special_places & 0x40:
        return None  # Delphi blank/special marker.
    scale = sign_special_places & 0x3F
    if not 1 <= precision <= 32 or scale > precision:
        raise PacketError("Precisao ou escala BCD invalida")
    nibbles = [digit for byte in raw[2:] for digit in (byte >> 4, byte & 0x0F)]
    digits = nibbles[:precision]
    if any(digit > 9 for digit in digits):
        raise PacketError("Digito BCD invalido")
    value = Decimal((int(bool(sign_special_places & 0x80)), tuple(digits), -scale))
    return format(value, "f")


def decode_dataset(blob: bytes, *, max_bytes: int = 4_000_000,
                   max_records: int = 5000) -> list[dict]:
    if len(blob) > max_bytes:
        raise PacketError("Pacote muito grande")
    sig_offset = blob.find(bytes.fromhex("9619e0bd"))
    if sig_offset < 0:
        raise PacketError("Resposta MIDAS sem assinatura")
    stream = io.BytesIO(blob)

    def read(n):
        if n < 0 or n > max_bytes:
            raise PacketError("Comprimento invalido")
        b = stream.read(n)
        if len(b) != n:
            raise PacketError("Pacote incompleto")
        return b

    def uint(n):
        if n not in (1, 2, 4):
            raise PacketError("Prefixo invalido")
        return int.from_bytes(read(n), "little")

    def prop():
        read(uint(1))
        size, kind = struct.unpack("<HH", read(4))
        if kind & 0x80:
            count = uint(4)
            read(count * size)
        elif size:
            read(uint(size) if kind & 0x40 else size)

    stream.seek(sig_offset)
    signature, version, marker, count, records, flags, meta_size = struct.unpack(
        "<IiiHIiH", read(24)
    )
    if signature != 0xBDE01996 or not (1 <= version <= 3):
        raise PacketError("Cabecalho MIDAS invalido")
    if count > 128 or records > max_records:
        raise PacketError("Limite de colunas/linhas excedido")
    fields = []
    for _ in range(count):
        name = read(uint(1)).decode("cp1252")
        size, kind, attrs, props = struct.unpack("<HHHH", read(8))
        if size > 1000 or props > 100:
            raise PacketError("Coluna invalida")
        for _ in range(props):
            prop()
        fields.append((name, size, kind))
    props = uint(2)
    if props > 100:
        raise PacketError("Metadados excessivos")
    for _ in range(props):
        prop()
    result = []
    for _ in range(records):
        read(1)
        bitmap = read((count + 3) // 4)
        row = {}
        for i, (name, size, kind) in enumerate(fields):
            if (bitmap[i // 4] >> ((i % 4) * 2)) & 3:
                row[name] = None
                continue
            base = kind & 0x3F
            if base in (1, 2):
                value = int.from_bytes(read(size), "little", signed=base == 1)
            elif base == 3:
                value = bool(uint(size))
            elif base == 4:
                value = struct.unpack("<d", read(8))[0]
            elif base == 5:
                value = _decode_bcd(read(18))
            elif base in (9, 10, 11):
                n = uint(size) if kind & 0x40 else size
                raw = read(n)
                if base == 10:
                    value = raw.decode("utf-16le", errors="replace").rstrip("\0")
                elif base == 11:
                    value = raw.hex()
                else:
                    value = raw.decode("cp1252", errors="replace").rstrip("\0")
            elif base == 17 and size == 16:
                parts = struct.unpack("<8H", read(16))
                try:
                    value = dt.datetime(*parts[:6], parts[6] * 1000).isoformat(timespec="seconds")
                except ValueError:
                    value = None
            elif base in (6, 7):
                value = uint(4)
            elif base == 8:
                value = struct.unpack("<d", read(8))[0]
            else:
                raise PacketError("Tipo de coluna ainda nao suportado")
            row[name] = value
        result.append(row)
    return result
