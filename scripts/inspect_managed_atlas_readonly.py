"""Safe Chrome-for-Testing Atlas inspection: metadata only, no navigation or secrets."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import urllib.request
import websocket

portfile = Path(r"C:\DominiumRuntime\ManagedAtlasTOA-20261022\profile\DevToolsActivePort")
port = int(portfile.read_text(encoding="utf-8").splitlines()[0])
with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
    tabs = json.load(response)

expression = r"""(() => ({
  ready:document.readyState,
  title:document.title.slice(0,100),
  host:location.host,
  path:location.pathname,
  atlasInjected:window.__TN_ATLAS_INJECTED__===true,
  forms:[...document.querySelectorAll('form')].slice(0,12).map(f=>({
    method:f.method, action:(()=>{try{return new URL(f.action).pathname}catch{return ''}})(),
    fields:[...f.querySelectorAll('input,select')].slice(0,22).map(x=>({tag:x.tagName.toLowerCase(),type:x.type,name:x.name,id:x.id}))
  })),
  links:[...document.querySelectorAll('a')].map(x=>(x.textContent||'').trim().replace(/\\s+/g,' ').slice(0,75))
    .filter(x=>/(rastreab|equipam|relat[oó]rio|invent[aá]rio)/i.test(x)).slice(0,18),
  buttons:[...document.querySelectorAll('button,input[type=submit],input[type=button]')]
    .map(x=>(x.innerText||x.value||'').trim().slice(0,60)).filter(Boolean).slice(0,22),
  loginVisible:!!document.querySelector('input[type=password]'),
  tableCount:document.querySelectorAll('table').length
}))()"""

def evaluate(tab):
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=6, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 125, "method":"Runtime.evaluate", "params":{
            "expression": expression, "returnByValue":True, "awaitPromise":False
        }}))
        for _ in range(15):
            message=json.loads(ws.recv())
            if message.get("id")==125:
                return (message.get("result") or {}).get("result",{}).get("value") or {"error":(message.get("result") or {}).get("exceptionDetails",{}).get("text","no_value")}
        return {"error":"no_response"}
    finally:
        ws.close()

for tab in tabs:
    if tab.get("type") != "page":
        continue
    url = urlsplit(str(tab.get("url") or ""))
    if (url.hostname or "") not in ("atlas.netservicos.com.br", "www.atlas.netservicos.com.br"):
        continue
    print(json.dumps(evaluate(tab), ensure_ascii=False, sort_keys=True))
