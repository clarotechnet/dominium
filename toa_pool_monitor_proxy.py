"""DOMINIUM: read-only authenticated TOA pool monitor proxy.

No Oracle requests and no control commands. Shared coordinator credentials are
read from the server environment and NEVER returned to the browser.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_REPLY=256_000
BUCKET_RE=re.compile(r"^[A-Za-z0-9_-]{1,50}$")
AGENT_RE=re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


class TOAPoolMonitorError(RuntimeError):
    pass


def _origin(value: str) -> str:
    candidate=(value or "").strip()
    try:
        url=urlsplit(candidate)
        if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("invalid")
        if url.scheme=="http":
            if url.hostname not in ("127.0.0.1", "::1", "localhost"):
                raise ValueError("not local")
        elif url.scheme!="https":
            raise ValueError("invalid protocol")
        if not url.hostname:
            raise ValueError("missing hostname")
        return candidate.rstrip("/")
    except (ValueError, TypeError) as exc:
        raise TOAPoolMonitorError("Coordenador TOA não configurado corretamente") from exc


def _count(value: object) -> int:
    return value if isinstance(value,int) and not isinstance(value,bool) and 0<=value<=10_000_000 else 0


def _agents(value: object) -> list[dict]:
    if not isinstance(value,list):
        raise TOAPoolMonitorError("Resposta incompatível do coordenador TOA")
    safe=[]
    for agent in value[:120]:
        if not isinstance(agent,dict):
            continue
        identifier=str(agent.get("id") or "")
        if not AGENT_RE.fullmatch(identifier):
            continue
        buckets=agent.get("buckets")
        if not isinstance(buckets,list):
            buckets=[]
        unique=list(dict.fromkeys(b for b in buckets[:50]
            if isinstance(b,str) and BUCKET_RE.fullmatch(b)))
        seen=agent.get("last_seen")
        safe.append({
            "id":identifier,"online":agent.get("online") is True,
            "busy":agent.get("busy") is True,
            "buckets":unique,
            "queries":_count(agent.get("queries")),
            "requests_recent":_count(agent.get("requests_recent")),
            "last_seen":seen if isinstance(seen,(int,float)) and not isinstance(seen,bool)
                and 0<=seen<=4_102_444_800 else None,
        })
    return safe


def sanitize_status(payload: object) -> dict:
    if not isinstance(payload,dict):
        raise TOAPoolMonitorError("Resposta incompatível do coordenador TOA")
    data=payload.get("data",payload)
    if not isinstance(data,dict):
        raise TOAPoolMonitorError("Resposta incompatível do coordenador TOA")
    queue=data.get("queue_by_bucket") or {}
    if not isinstance(queue,dict):
        queue={}
    by_bucket={}
    for name,item in list(queue.items())[:100]:
        if not isinstance(name,str) or not BUCKET_RE.fullmatch(name) or not isinstance(item,dict):
            continue
        by_bucket[name]={
            "queued":_count(item.get("queued")),
            "in_progress":_count(item.get("in_progress")),
        }
    return {
        "ok":True,"agents":_agents(data.get("agents")),
        "enrollments_pending":_count(data.get("enrollments_pending")),
        "leases_today":_count(data.get("leases_today")),
        "max_leases_per_day":(
            _count(data["max_leases_per_day"])
            if data.get("max_leases_per_day") is not None else None
        ),
        "dispatch_blocked":data.get("dispatch_blocked") is True,
        "queue_by_bucket":by_bucket,
    }


def read_monitor(*, origin: str | None = None, token: str | None = None) -> dict:
    url=_origin(origin if origin is not None else os.environ.get("DOMINIUM_TOA_POOL_ORIGIN",""))
    secret=(token if token is not None else os.environ.get("DOMINIUM_TOA_POOL_ADMIN_TOKEN","")).strip()
    if len(secret)<24 or any(c in secret for c in "\r\n"):
        raise TOAPoolMonitorError("Monitor TOA não configurado")
    try:
        req=Request(url+"/admin/status",method="GET",headers={
            "Authorization":"Bearer "+secret,"Accept":"application/json",
            "Cache-Control":"no-store",
        })
        with urlopen(req,timeout=4) as resp:
            if resp.status!=200:
                raise TOAPoolMonitorError("Coordenador TOA indisponível")
            raw=resp.read(MAX_REPLY+1)
            if len(raw)>MAX_REPLY:
                raise TOAPoolMonitorError("Resposta excedeu o limite permitido")
        return sanitize_status(json.loads(raw))
    except (TOAPoolMonitorError,):
        raise
    except Exception as exc:
        # Never expose remote body, secret, origin, socket info, traceback or PII.
        raise TOAPoolMonitorError("Monitor TOA indisponível") from exc


def _call_admin(path: str, *, method: str = "GET") -> object:
    origin=_origin(os.environ.get("DOMINIUM_TOA_POOL_ORIGIN",""))
    secret=os.environ.get("DOMINIUM_TOA_POOL_ADMIN_TOKEN","").strip()
    if len(secret)<24 or any(c in secret for c in "\r\n"):
        raise TOAPoolMonitorError("Monitor TOA não configurado")
    if method not in {"GET","POST"} or not path.startswith("/admin/"):
        raise TOAPoolMonitorError("Operação não permitida")
    req=Request(origin+path,method=method,
                data=b"{}" if method=="POST" else None,
                headers={
                    "Authorization":"Bearer "+secret,
                    "Accept":"application/json",
                    "Content-Type":"application/json",
                    "Cache-Control":"no-store",
                })
    try:
        with urlopen(req,timeout=4) as resp:
            if resp.status!=200:raise TOAPoolMonitorError("Coordenador TOA indisponível")
            raw=resp.read(MAX_REPLY+1)
            if len(raw)>MAX_REPLY:raise TOAPoolMonitorError("Resposta excedeu o limite permitido")
        value=json.loads(raw)
        if not isinstance(value,dict) or value.get("ok") is not True:
            raise TOAPoolMonitorError("Coordenador TOA indisponível")
        return value.get("data")
    except TOAPoolMonitorError:
        raise
    except Exception as exc:
        raise TOAPoolMonitorError("Coordenador TOA indisponível") from exc


def read_enrollments() -> dict:
    response=_call_admin("/admin/enrollments")
    if not isinstance(response,list):
        raise TOAPoolMonitorError("Lista de controladores inválida")
    pending=[]
    for item in response[:40]:
        if not isinstance(item,dict):continue
        agent_id=item.get("id")
        if not isinstance(agent_id,str) or not re.fullmatch(r"ctl-[a-f0-9]{24}",agent_id):
            continue
        pending.append({"id":agent_id})
    return {"ok":True,"pending":pending,"total":len(pending)}


def review_enrollment(agent_id: str, approve: bool) -> dict:
    if not isinstance(agent_id,str) or not re.fullmatch(r"ctl-[a-f0-9]{24}",agent_id):
        raise TOAPoolMonitorError("Identificação inválida")
    response=_call_admin(
        "/admin/enrollments/"+agent_id+("/approve" if approve else "/deny"),
        method="POST")
    if not isinstance(response,dict) or response.get("id")!=agent_id:
        raise TOAPoolMonitorError("Resposta incompatível do coordenador")
    expected="approved" if approve else "denied"
    if response.get("state")!=expected:
        raise TOAPoolMonitorError("Estado inesperado do dispositivo")
    return {"ok":True,"id":agent_id,"state":expected}
