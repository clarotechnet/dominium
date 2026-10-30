// Isolated, deny-by-default bridge. No operational OS-closing endpoints.
const ROLES=new Set(["admin","controller"]);
const GET=new Set(["/api/backlog/year/status","/api/backlog/year/compare","/api/backlog/year/fora-rota","/api/backlog/year/sent"]);
const POST=new Set(["/api/backlog/year/start","/api/backlog/year/pause","/api/backlog/year/routes","/api/backlog/year/sent"]);
const SECRET=/^[A-Za-z0-9_-]{43,128}$/;
const ACTOR=/^[A-Za-z0-9_.%-]{1,160}$/;
function json(status,data){return new Response(JSON.stringify(data),{status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}});}
function allowed(method,url){
  const u=new URL(url), keys=[...u.searchParams.keys()];
  if(u.hash||/[%\\]/.test(u.pathname)||u.pathname.includes("//")||new Set(keys).size!==keys.length)return false;
  if(method==="POST")return POST.has(u.pathname)&&!u.search;
  if(method!=="GET"||!GET.has(u.pathname))return false;
  if(u.pathname.endsWith("/status")||u.pathname.endsWith("/sent"))return !u.search;
  const bounded=(key,max)=>!u.searchParams.has(key)||(/^\d{1,4}$/.test(u.searchParams.get(key))&&Number(u.searchParams.get(key))>=1&&Number(u.searchParams.get(key))<=max);
  if(u.pathname.endsWith("/compare")){
    return keys.every(k=>["limit","codes"].includes(k)) && bounded("limit",1000) &&
      (!u.searchParams.has("codes")||/^(?:\d{3}(?:,\d{3}){0,9})?$/.test(u.searchParams.get("codes")));
  }
  return keys.every(k=>["limit","profile"].includes(k))&&bounded("limit",300)&&
    (!u.searchParams.has("profile")||["natal","fortaleza","mossoro","recife"].includes(u.searchParams.get("profile")));
}
function equal(a,b){
  if(typeof a!=="string"||typeof b!=="string")return false;
  let d=a.length^b.length;
  for(let i=0;i<Math.max(a.length,b.length);i++)d|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);
  return d===0;
}
export default {
  async fetch(request,env){
    const url=new URL(request.url);
    if(request.method==="GET" && url.pathname==="/health" && !url.search){
      return json(200,{ok:true,service:"dominium-backlog-bridge",mode:"isolated"});
    }
    if(!allowed(request.method,request.url))return json(404,{ok:false,error:"Rota inexistente"});
    if(!SECRET.test(env.BACKLOG_BRIDGE_TOKEN||"")||!env.BACKLOG_SERVICE)
      return json(503,{ok:false,error:"Integracao privada nao configurada"});
    if(!equal(request.headers.get("Authorization")||"","Bearer "+env.BACKLOG_BRIDGE_TOKEN))
      return json(401,{ok:false,error:"Nao autorizado"});
    const role=(request.headers.get("X-Dominium-Role")||"").toLowerCase();
    const actor=request.headers.get("X-Dominium-Actor")||"";
    if(!ROLES.has(role)||!ACTOR.test(actor))
      return json(403,{ok:false,error:"Operador nao autorizado"});
    const max=url.pathname.endsWith("/routes")?22*1024*1024:8192;
    let body;
    if(request.method==="POST"){
      if((request.headers.get("Content-Type")||"").split(";")[0].trim().toLowerCase()!=="application/json")
        return json(415,{ok:false,error:"Envie JSON"});
      if(Number(request.headers.get("Content-Length")||0)>max)
        return json(413,{ok:false,error:"Limite de requisicao excedido"});
      body=await request.arrayBuffer();
      if(body.byteLength>max)return json(413,{ok:false,error:"Limite de requisicao excedido"});
    }
    const headers=new Headers({
      "Authorization":"Bearer "+env.BACKLOG_BRIDGE_TOKEN,
      "X-Dominium-Role":role,"X-Dominium-Actor":actor
    });
    if(body)headers.set("Content-Type","application/json");
    try{
      const target="http://127.0.0.1:9342"+url.pathname+url.search;
      const upstream=await env.BACKLOG_SERVICE.fetch(new Request(target,{method:request.method,headers,body,redirect:"manual"}));
      return new Response(upstream.body,{status:upstream.status,headers:{"Cache-Control":"no-store","Content-Type":"application/json; charset=utf-8","X-Content-Type-Options":"nosniff"}});
    }catch{return json(502,{ok:false,error:"Servico privado indisponivel"});}
  }
};