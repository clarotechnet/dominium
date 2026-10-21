"""Bounded read-only decoder for Delphi MIDAS ClientDataSet binary packets.

Format based on DBReaderMidas (MIT), verified against captured IMPERIUM packets.
"""
from __future__ import annotations

import datetime as dt
import io
import struct


class PacketError(ValueError):
    pass


def decode_dataset(blob: bytes) -> list[dict]:
    if len(blob) > 4_000_000:
        raise PacketError("Pacote muito grande")
    sig_offset = blob.find(bytes.fromhex("9619e0bd"))
    if sig_offset < 0:
        raise PacketError("Resposta MIDAS sem assinatura")
    stream = io.BytesIO(blob)

    def read(n):
        if n < 0 or n > 4_000_000:
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
    if count > 128 or records > 5000:
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
