"""Portable MCP stdio entrypoint for DOMINIUM read/search/record memory.

Uses newline-delimited JSON-RPC 2.0 over stdin/stdout, no external libraries
or network listeners. MCP clients launch this process after cloning the repo.
"""
from __future__ import annotations
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_memory as mem


TOOLS = [
    {"name":"dominium_memory_brief","description":"Read concise current DOMINIUM project state, pending issues and recent Git history.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"dominium_memory_search","description":"Search portable versioned DOMINIUM technical memory; returns source paths.",
     "inputSchema":{"type":"object","properties":{"query":{"type":"string"},
                        "limit":{"type":"integer","minimum":1,"maximum":20}},
                    "required":["query"],"additionalProperties":False}},
    {"name":"dominium_memory_history","description":"Show recent Git commit summaries with dates.",
     "inputSchema":{"type":"object","properties":{"limit":{"type":"integer","minimum":1,"maximum":30}},
                    "additionalProperties":False}},
    {"name":"dominium_memory_record","description":"Append a durable verified engineering note; do not include private data.",
     "inputSchema":{"type":"object","properties":{
        "title":{"type":"string"},"why":{"type":"string"},"changed":{"type":"string"},
        "tests":{"type":"string"},"next":{"type":"string"}},
        "required":["title","why","changed","tests","next"],"additionalProperties":False}},
]


def capture(call):
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):
        call()
    return stream.getvalue()


def handle(req: dict):
    method=req.get("method")
    params=req.get("params") or {}
    if method=="initialize":
        # Echo requested protocol; all exposed methods use the common basic MCP shape.
        return {"protocolVersion":params.get("protocolVersion","2025-06-18"),
                "capabilities":{"tools":{},"resources":{}},
                "serverInfo":{"name":"dominium-agent-memory","version":"1.0.0"}}
    if method in ("notifications/initialized","notifications/cancelled"):
        return None
    if method=="ping":return {}
    if method=="tools/list":return {"tools":TOOLS}
    if method=="resources/list":
        return {"resources":[{"uri":"dominium://memory/current",
                 "name":"DOMINIUM current state",
                 "mimeType":"text/markdown"}]}
    if method=="resources/read":
        if params.get("uri")!="dominium://memory/current":
            raise ValueError("Recurso não encontrado")
        source=mem.MEMORY/"CURRENT_STATE.md"
        return {"contents":[{"uri":params["uri"],"mimeType":"text/markdown",
                             "text":source.read_text(encoding="utf-8")}]}
    if method=="tools/call":
        name=params.get("name")
        args=params.get("arguments") or {}
        if name=="dominium_memory_brief":
            answer=capture(mem.brief)
        elif name=="dominium_memory_search":
            answer=capture(lambda:mem.search(str(args.get("query","")),int(args.get("limit",8))))
        elif name=="dominium_memory_history":
            answer=capture(lambda:mem.history(int(args.get("limit",10))))
        elif name=="dominium_memory_record":
            from argparse import Namespace
            fields={key:args.get(key,"") for key in ("title","why","changed","tests","next")}
            answer=capture(lambda:mem.record(Namespace(**fields)))
        else:
            raise ValueError("Ferramenta desconhecida")
        return {"content":[{"type":"text","text":answer}]}
    raise ValueError("Método MCP não suportado")


def process(line: str):
    try:
        req=json.loads(line)
        if not isinstance(req,dict) or req.get("jsonrpc")!="2.0":
            raise ValueError("Expected JSON-RPC 2.0")
        out=handle(req)
        if "id" not in req or out is None:
            return None
        return {"jsonrpc":"2.0","id":req["id"],"result":out}
    except Exception as exc:
        ident=None
        try:ident=req.get("id")
        except (NameError,AttributeError):pass
        # Errors contain no source/customer data.
        return {"jsonrpc":"2.0","id":ident,"error":{"code":-32603,
                         "message":type(exc).__name__+": "+str(exc)[:160]}}


def main():
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    for line in sys.stdin:
        if not line.strip():continue
        message=process(line)
        if message is not None:
            sys.stdout.write(json.dumps(message,ensure_ascii=False,separators=(",",":"))+"\n")
            sys.stdout.flush()


if __name__=="__main__":
    main()
