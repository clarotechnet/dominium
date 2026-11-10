"""DOMINIUM observation-after-close DataSnap proof of concept.
READ-ONLY / OFFLINE ONLY. No ApplyUpdates execution permitted by this module.
Validated against PCAP of 2026-11-10 (field ObservacaoBaixa, ordinal 25).
Payload builder only; HTTP authorization and single-write controls are separate.
"""
from __future__ import annotations
import dataclasses, hashlib, re, struct
from typing import Any

class ObservationFormatError(ValueError):
    pass

def _text(row:bytes,offset:int,label:str)->tuple[str,int]:
    if offset>=len(row):raise ObservationFormatError(label+"_out_of_range")
    length=row[offset]
    if offset+1+length>len(row):raise ObservationFormatError(label+"_truncated")
    return row[offset+1:offset+1+length].decode("cp1252"),offset+1+length

def _memo(row:bytes,offset:int,label:str)->tuple[str,int]:
    if offset+2>len(row):raise ObservationFormatError(label+"_truncated")
    length=struct.unpack_from("<H",row,offset)[0]
    if length>4000 or offset+2+length>len(row):
        raise ObservationFormatError(label+"_length_invalid")
    return row[offset+2:offset+2+length].decode("cp1252"),offset+2+length

def _fixed(row:bytes,offset:int,size:int)->int:
    if offset+size>len(row):raise ObservationFormatError("fixed_field_truncated")
    return offset+size

@dataclasses.dataclass(frozen=True)
class ObservationState:
    note:str
    start:int
    end:int
    present:bool
    code:str
    company:str
    status:int

# Precise schema prefix for 2026-11-10 Natal AS_GetRecords.
# 25 fields precede ObservacaoBaixa, including optional Observacao.
def decode_observation(
    record:bytes,id_os:int,num_os:str,contract:str,
)->ObservationState:
    if len(record)<160 or struct.unpack_from("<I",record,0)[0]!=id_os:
        raise ObservationFormatError("id_os_mismatch")
    offset=4
    number,offset=_text(record,offset,"num_os")
    contract_actual,offset=_text(record,offset,"contract")
    if number!=num_os or contract_actual!=contract:
        raise ObservationFormatError("record_identity_mismatch")
    offset=_fixed(record,offset,4)
    _,offset=_text(record,offset,"codigo_servico")
    _,offset=_text(record,offset,"servico")
    offset=_fixed(record,offset,4)
    _,offset=_text(record,offset,"turno")
    offset=_fixed(record,offset,8)
    offset=_fixed(record,offset,4)
    code,offset=_text(record,offset,"codigo_baixa")
    desc,offset=_text(record,offset,"descricao_baixa")
    if not re.fullmatch(r"[0-9]{3}",code) or not desc:
        raise ObservationFormatError("order_not_confirmed_closed")
    offset=_fixed(record,offset,20)
    _,offset=_text(record,offset,"instalador")
    offset=_fixed(record,offset,4)
    _,offset=_text(record,offset,"tipo_valor")
    candidates=[]
    for obs18 in (False,True):
        try:
            pos=offset
            if obs18:_,pos=_memo(record,pos,"Observacao")
            pos=_fixed(record,pos,4+16+16+4+4)
            company,pos=_text(record,pos,"company")
            if not 1<=len(company)<=30 or not re.fullmatch(r"[A-Z0-9_ ./-]+",company):
                continue
            for obs25 in (False,True):
                try:
                    start=pos;note=""
                    if obs25:note,pos2=_memo(record,pos,"ObservacaoBaixa")
                    else:pos2=pos
                    if pos2>=len(record):continue
                    status=record[pos2]
                    if status not in (0,1,2,3):continue
                    node,at=_text(record,pos2+1,"node")
                    client,at=_text(record,at,"client")
                    address,at=_text(record,at,"address")
                    if not 4<=len(client)<=90 or not 4<=len(address)<=160:continue
                    if node and not re.fullmatch(r"[A-Z0-9_-]{1,60}",node):continue
                    _,at=_text(record,at,"apt")
                    candidates.append(ObservationState(note,start,pos2,obs25,code,company,status))
                except (ObservationFormatError,ValueError):continue
        except (ObservationFormatError,ValueError):continue
    if len(candidates)!=1:
        raise ObservationFormatError("observation_field_layout_ambiguous")
    return candidates[0]

# The row delta mask modifies ONLY field 25, ObservacaoBaixa.
# Mask AA..A2..AA corresponds to null-indicator bit pair for that field.
NOTE_MASK=bytes([0xaa]*6+[0xa2]+[0xaa]*13)
NOTE_TRAILER=bytes.fromhex("60601000050200000000c0")
def create_note_suffix(text:str)->bytes:
    if not isinstance(text,str) or not text.strip():
        raise ObservationFormatError("note_required")
    try:data=text.encode("cp1252")
    except UnicodeEncodeError as exc:
        raise ObservationFormatError("unsupported_note_character") from exc
    if len(data)>1000 or chr(0) in text:
        raise ObservationFormatError("note_size_or_null_invalid")
    return bytes([8])+NOTE_MASK+bytes([2])+struct.pack("<H",len(data))+data+NOTE_TRAILER

@dataclasses.dataclass(frozen=True)
class ObservationPreview:
    id_os:int
    num_os:str
    code:str
    had_previous_note:bool
    previous_length:int
    requested_append_length:int
    new_length:int
    snapshot_sha256:str
    packet_length:int
    blob_sha256:str
    # Deliberately do not serialize note text or binary packet in logs.

def make_append_preview(
    api:Any,detail:bytes,id_os:int,num_os:str,contract:str,
    append_text:str,expected_code:str="409",
)->tuple[ObservationPreview,bytes]:
    record,record_mask=api._detail_parts(detail)
    state=decode_observation(record,id_os,num_os,contract)
    if state.code!=expected_code or state.status!=2:
        raise ObservationFormatError("closed_state_or_code_mismatch")
    if not isinstance(append_text,str) or not append_text.strip():
        raise ObservationFormatError("append_text_required")
    if len(append_text)>500 or chr(13) in append_text or chr(10) in append_text:
        raise ObservationFormatError("only_single_line_append_allowed")
    cleaned=append_text.strip()
    if state.note and cleaned.casefold() in state.note.casefold():
        raise ObservationFormatError("duplicate_observation")
    next_note=state.note+("" if not state.note else (chr(13)+chr(10) if not state.note.endswith((chr(10),chr(13))) else ""))+cleaned
    suffix=create_note_suffix(next_note)
    if len(record_mask)!=19:
        raise ObservationFormatError("detail_field_mask_invalid")
    packet=api._packet_from_modified_record(record,record_mask,suffix)
    if not packet.startswith(b"#Dsp"):
        raise ObservationFormatError("packet_prefix_invalid")
    preview=ObservationPreview(
       id_os=id_os,num_os=num_os,code=state.code,
       had_previous_note=bool(state.note),previous_length=len(state.note.encode("cp1252")),
       requested_append_length=len(cleaned.encode("cp1252")),
       new_length=len(next_note.encode("cp1252")),
       snapshot_sha256=hashlib.sha256(detail).hexdigest(),
       packet_length=len(packet),blob_sha256=hashlib.sha256(packet).hexdigest())
    return preview,packet
