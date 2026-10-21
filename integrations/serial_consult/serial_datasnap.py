"""Private read-only DataSnap query for IMPERIUM serial movement history.

Templates derive from protocol captures, with the original serial replaced by
a neutral placeholder. Provider handles are prepared fresh for every session.
No write methods are used. Only the Natal (212) protocol is verified.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

from midas_reader import decode_dataset, PacketError

RUNTIME_ROOT = Path(r"C:\DominiumMain")
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.append(str(RUNTIME_ROOT))
from datasnap_client import DataSnapClient, load_credentials, DataSnapError
from imperium_api import HOST, ImperiumAPI

MOVEMENT_TEMPLATE = base64.b64decode(
    "LERzcENvblNlcmlhbCEBYGEBIBACHQIMIAAAAQAAAAAAAAACAAAADCAAAAEAAAAAAAAABgAAAAgAAAANAAAAQABSAEUAVABVAFIATgBfAFYAQQBMAFUARQAAAAAAEAAAAAMQAAAABAMAAAAAAAAAAwAAAAAAAAADAAAAAAAAAAwgAAABAAAAAAAAAAYAAAAIAAAABQAAAEAAVABpAHAAbwAIAAAAAQAAAEEAEAAAABcQAAAAAQMAAAABAAAAAwAAAAAAAAADAAAAAAAAAAwgAAABAAAAAAAAAAYAAAAIAAAABwAAAEAAQQByAHEAWABtAGwACAAAAIsAAAA8AD8AeABtAGwAIAB2AGUAcgBzAGkAbwBuAD0AIgAxAC4AMAAiACAAZQBuAGMAbwBkAGkAbgBnAD0AIgBJAFMATwAtADgAOAA1ADkALQAxACIAIAA/AD4ADQAKADwAQwBvAG4AcwB1AGwAdABhAFMAZQByAGkAYQBpAHMAPgANAAoAPABTAGUAcgBpAGEAaQBzAD4ADQAKADwAUwBlAHIAaQBhAGwAPgBTAEUAUgBJAEEATAAwADAAMAAwADAAMAA8AC8AUwBlAHIAaQBhAGwAPgANAAoAPAAvAFMAZQByAGkAYQBpAHMAPgANAAoAPAAvAEMAbwBuAHMAdQBsAHQAYQBTAGUAcgBpAGEAaQBzAD4ADQAKABAAAAAQEAAAAAEDAAAA////fwMAAAAAAAAAAwAAAAAAAAAQAAUCAAAAAMA="
)
BOX_TEMPLATE = base64.b64decode(
    "MURzcENvbkNhaXhhU2VyaWFsIQFgYQEgEAC3AgwgAAABAAAAAAAAAAEAAAAMIAAAAQAAAAAAAAAGAAAACAAAAA0AAABAAFIARQBUAFUAUgBOAF8AVgBBAEwAVQBFAAAAAAAQAAAAAxAAAAAEAwAAAAAAAAADAAAAAAAAAAMAAAAAAAAADCAAAAEAAAAAAAAABgAAAAgAAAAFAAAAQABUAGkAcABvAAgAAAABAAAAQQAQAAAAFxAAAAABAwAAAAEAAAADAAAAAAAAAAMAAAAAAAAAEAAFAgAAAADA"
)
PLACEHOLDER = "SERIAL000000".encode("utf-16-le")
SERIAL_SLOT = 419
METHOD = "TDtmMovEstoque.AS_GetRecords"


def prepare_queries(serial: str, mode: str) -> tuple[bytes, bytes]:
    candidate = str(serial).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{12}", candidate):
        raise ValueError("Historico direto DataSnap validado apenas para seriais alfanumericos de 12 caracteres")
    if mode not in ("analitico", "sintetico"):
        raise ValueError("Modo de consulta invalido")
    if len(MOVEMENT_TEMPLATE) != 572 or len(BOX_TEMPLATE) != 219:
        raise DataSnapError("Template da consulta invalido")
    if MOVEMENT_TEMPLATE[SERIAL_SLOT:SERIAL_SLOT+24] != PLACEHOLDER:
        raise DataSnapError("Marcador de serial invalido")
    movement = bytearray(MOVEMENT_TEMPLATE)
    movement[SERIAL_SLOT:SERIAL_SLOT+24] = candidate.encode("utf-16le")
    movement[169] = ord("A" if mode == "analitico" else "S")
    box = bytearray(BOX_TEMPLATE)
    box[174] = ord("A" if mode == "analitico" else "S")
    return bytes(movement), bytes(box)


def fetch_serial_history(serial: str, *, mode: str = "analitico", profile: str = "natal"):
    if profile != "natal":
        raise ValueError("Historico DataSnap capturado e validado somente para Natal/P​​arnamirim")
    move_query, box_query = prepare_queries(serial, mode)
    credentials = load_credentials(RUNTIME_ROOT / "config" / "credentials.dat")
    with DataSnapClient(HOST, 212, credentials["username"], credentials["password"], timeout=30.0) as client:
        handle = ImperiumAPI._handle(client, METHOD)
        movement_packet = ImperiumAPI._dataset_payload(client, handle, move_query, "movimentacoes do serial")
        moves = decode_dataset(movement_packet)
        box_packet = ImperiumAPI._dataset_payload(client, handle, box_query, "caixa associada ao serial")
        boxes = decode_dataset(box_packet)
    requested = serial.strip().upper()
    # Empty search results may contain a provider placeholder row (Empresa only).
    # Never present such a row as an actual movement.
    moves = [row for row in moves if row.get("Id") and row.get("Movimento") and row.get("Data")]
    if any(str(row.get("Serial") or "").upper() != requested for row in moves):
        raise PacketError("Imperium retornou movimentacoes de outro serial")
    smart_values = {str(row.get("Smart") or "").upper() for row in moves}
    safe_boxes = [box for box in boxes
                  if str(box.get("Serial") or "").upper() in smart_values
                  and str(box.get("Serial") or "").strip()]
    return {
        "source": "imperium_datasnap_live",
        "mode": mode,
        "serial": requested,
        "count": len(moves),
        "movements": moves,
        "boxes": safe_boxes,
        "verified": True,
    }
