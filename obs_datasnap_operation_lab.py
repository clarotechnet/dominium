"""Guarded observation-only write for a CLOSED Natal O.S. (lab, not exposed).
One DataSnap ApplyUpdates per approved intent; never retries ambiguous outcomes.
No equipment / material / close code writes. Requires preflight snapshot SHA256.
HTTP routes must enforce administrator + Natal + feature flag before invoking this writer.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os, re, threading, time, uuid
from pathlib import Path
from typing import Any
from obs_datasnap_lab import ObservationFormatError,make_append_preview,decode_observation

class ObservationConflict(ObservationFormatError):
    pass
class ObservationResultUncertain(Exception):
    pass

def utcnow()->str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def audit_atomic(path:Path,data:dict)->None:
    temp=path.with_suffix(".tmp")
    with temp.open("x",encoding="utf-8") as file:
        json.dump(data,file,indent=2,ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())
    temp.replace(path)

def fields_unchanged(api:Any,before:bytes,after:bytes,id_os:int,os_number:str,contract:str)->bool:
    b,mask_b=api._detail_parts(before)
    a,mask_a=api._detail_parts(after)
    try:
        sb=decode_observation(b,id_os,os_number,contract)
        sa=decode_observation(a,id_os,os_number,contract)
    except ObservationFormatError:
        return False
    if sb.code!=sa.code or sb.status!=sa.status:
        return False
    # Only the encoded ObservacaoBaixa bytes may differ.
    if b[:sb.start]+b[sb.end:]!=a[:sa.start]+a[sa.end:]:
        return False
    if len(mask_b)!=len(mask_a) or len(mask_b)!=19:
        return False
    if sb.present and mask_b!=mask_a:
        return False
    if not sb.present:
        # During addition, only the null/value indicator of the note may change.
        changes=[(i,x,y) for i,(x,y) in enumerate(zip(mask_b,mask_a)) if x!=y]
        if len(changes)>1:
            return False
    return True

def preview_readonly(api:Any,id_os:int,number:str,contract:str,text:str)->dict:
    with api._client(timeout=18) as client:
        detail=api._fetch_detail_on(client,id_os)
    ctx=api._detail_context(detail)
    if ctx.id_os!=id_os or ctx.contract!=contract or number.encode("ascii") not in detail:
        raise ObservationConflict("identity_changed")
    preview,packet=make_append_preview(api,detail,id_os,number,contract,text)
    return {
      "id_os":id_os,"num_os":number,"contract":contract,
      "snapshot_sha256":preview.snapshot_sha256,
      "code":preview.code,
      "existing_note_bytes":preview.previous_length,
      "append_bytes":preview.requested_append_length,
      "result_bytes":preview.new_length,
      "packet_bytes":preview.packet_length,
      "already_closed":True,
      "preview_only":True,
    }

def append_once(
    api:Any,id_os:int,number:str,contract:str,text:str,
    expected_snapshot_sha256:str,idempotency_key:str,
    audit_dir:Path,*,enable_live:bool=False,
)->dict:
    if not enable_live:
        raise ObservationConflict("live_note_write_disabled")
    local=dt.datetime.now().astimezone()
    if local.utcoffset()!=dt.timedelta(hours=-3) or not 7<=local.hour<21:
        raise ObservationConflict("outside_operational_window")
    if not re.fullmatch(r"[0-9]{10}",str(number)) or not re.fullmatch(r"[0-9]{6,10}",str(contract)):
        raise ObservationConflict("invalid_order_identity")
    if not re.fullmatch(r"[0-9a-f]{64}",str(expected_snapshot_sha256)):
        raise ObservationConflict("snapshot_hash_required")
    try:
        intent=uuid.UUID(idempotency_key)
        if str(intent)!=idempotency_key:
            raise ValueError
    except (ValueError,AttributeError):
        raise ObservationConflict("valid_uuid_idempotency_key_required")
    if id_os<=0:
        raise ObservationConflict("invalid_id_os")
    audit_dir=Path(audit_dir)
    if not audit_dir.is_dir():
        raise ObservationConflict("audit_directory_missing")
    marker=audit_dir/("OBS_"+number+"_"+idempotency_key+".json")
    with api._operation_lock:
        # Never send duplicate intent, including attempts with unknown outcome.
        if marker.exists():
            raise ObservationConflict("intent_already_reserved")
        with api._client(timeout=18) as client:
            original=api._fetch_detail_on(client,id_os)
        ctx=api._detail_context(original)
        if ctx.id_os!=id_os or ctx.contract!=contract or number.encode("ascii") not in original:
            raise ObservationConflict("identity_changed")
        preview,packet=make_append_preview(api,original,id_os,number,contract,text)
        if preview.snapshot_sha256!=expected_snapshot_sha256:
            raise ObservationConflict("observation_changed_since_preview")
        # Second read immediately before preparation, fail closed on any change.
        with api._client(timeout=18) as client:
            current=api._fetch_detail_on(client,id_os)
        if hashlib.sha256(current).hexdigest()!=expected_snapshot_sha256:
            raise ObservationConflict("observation_changed_before_send")
        data={
          "intent":str(intent),"id_os":id_os,"num_os":number,"contract":contract,
          "created_at":utcnow(),"state":"RESERVED_NO_RETRY",
          "transport":"datasnap_note_only","code_before":preview.code,
          "snapshot_sha256":preview.snapshot_sha256,
          "packet_sha256":preview.blob_sha256,
          "observation_bytes_before":preview.previous_length,
          "observation_bytes_after":preview.new_length,
        }
        # Cross-process O.S. lock is exclusive; retain it after uncertain outcomes.
        os_lock=audit_dir/("OBS_LOCK_"+number+".lock")
        with os_lock.open("x",encoding="utf-8") as exclusive:
            json.dump({"num_os":number,"intent":str(intent),"created_at":utcnow()},exclusive)
            exclusive.flush();os.fsync(exclusive.fileno())
        try:
            with marker.open("x",encoding="utf-8") as f:
                json.dump(data,f,ensure_ascii=False,indent=2)
                f.flush();os.fsync(f.fileno())
        except Exception:
            os_lock.unlink(missing_ok=True)
            raise
        def change_status(status:str,extra:dict|None=None):
            data["state"]=status;data["updated_at"]=utcnow()
            if extra:data.update(extra)
            audit_atomic(marker,data)
        try:
            # No automatic retries, irrespective of return status or timeout.
            with api._client(timeout=18) as client:
                handle=api._handle(client,"TDtmOrdemServico.AS_ApplyUpdates")
                response=client.request("execute",[{"handle":[handle]},packet])
                returned=response["result"][1]["data"][1]
                if returned!=api.apply_success:
                    change_status("RESPONSE_NOT_SUCCESS_NO_RETRY")
                    raise ObservationResultUncertain("unexpected_apply_response")
            change_status("APPLY_ACCEPTED_CONFIRMATION_REQUIRED")
        except Exception as exc:
            if data["state"]=="RESERVED_NO_RETRY":
                change_status("UNKNOWN_AFTER_SEND_NO_RETRY",{"error_type":type(exc).__name__})
            # The request could already be committed. NEVER resend.
            raise ObservationResultUncertain("apply_status_requires_readback") from exc
        for attempt in range(1,4):
            if attempt>1:time.sleep(2)
            try:
                with api._client(timeout=14) as client:
                    after=api._fetch_detail_on(client,id_os)
                b,_=api._detail_parts(original)
                a,_=api._detail_parts(after)
                old=decode_observation(b,id_os,number,contract).note
                new=decode_observation(a,id_os,number,contract).note
                target=old+("" if not old or old.endswith((chr(13),chr(10))) else chr(13)+chr(10))+text.strip()
                if new==target and fields_unchanged(api,original,after,id_os,number,contract):
                    change_status("CONFIRMED_READBACK",{"checks":attempt})
                    os_lock.unlink(missing_ok=True)
                    return {"ok":True,"confirmed":True,"num_os":number,"code":preview.code}
            except Exception:
                pass
        change_status("AWAITING_CONFIRMATION_NO_RETRY",{"checks":3})
        return {"ok":False,"confirmed":False,"num_os":number,"pending":True,"safe_to_retry":False}
