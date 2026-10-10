'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const sha=value=>crypto.createHash('sha256').update(String(value||'')).digest('hex');
function readConnection(){
  const privateFile=path.join(__dirname,'.desc-review-connection.json');
  const stored=fs.existsSync(privateFile)?JSON.parse(fs.readFileSync(privateFile,'utf8')):{};
  return {origin:process.env.DOMINIUM_DESC_REVIEW_ORIGIN||stored.origin,token:process.env.DOMINIUM_DESC_REVIEW_TOKEN||stored.token};
}
function allowedRoute(method,raw){
  const url=new URL(raw,'http://dominium.invalid');
  const route=url.pathname.slice('/api/disconnection/'.length);
  if(!url.pathname.startsWith('/api/disconnection/')||url.hash)throw new Error('Rota DESC inválida');
  const allowed=method==='GET'?['state','report.xlsx']:method==='POST'?['decision','refresh','technician','manual']:[];
  if(!allowed.includes(route)&&!(method==='GET'&&/^photo\/[a-f0-9-]{36}\.jpg$/.test(route)))throw new Error('Rota DESC não permitida');
  const params=[...url.searchParams];
  if(params.length&&(route!=='report.xlsx'||params.length!==1||params[0][0]!=='month'||!/^\d{4}-(0[1-9]|1[0-2])$/.test(params[0][1])))throw new Error('Parâmetros DESC inválidos');
  return url.pathname+url.search;
}
function createDisconnectionMiddleware({connection=readConnection,fetchImpl=fetch,audit=async()=>{}}={}){
  return async(req,res)=>{
    res.set('cache-control','no-store');
    const user=req.dominiumUser;
    if(!user?.role||!req.dominiumSession)return res.status(401).json({ok:false,error:'Entre no DOMINIUM para continuar'});
    if(!['admin','controller'].includes(user.role))return res.status(403).json({ok:false,error:'DESCONEXÃO exige perfil operacional'});
    if(req.method!=='GET'&&sha(req.headers['x-csrf-token'])!==req.dominiumSession.csrf_hash)return res.status(403).json({ok:false,error:'Sessão de revisão inválida'});
    let route;
    try {route=allowedRoute(req.method,req.originalUrl);}catch(error){return res.status(400).json({ok:false,error:error.message});}
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
    try{
      const {origin,token}=connection();
      const url=new URL(origin);
      if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/'||!/^[A-Za-z0-9_-]{43,128}$/.test(String(token||'')))throw new Error('review_connection_missing');
      const actor=String(user.display_name||user.username||user.id||'').slice(0,100);
      if(!actor)throw new Error('review_actor_missing');
      const options={method:req.method,headers:{Authorization:'Bearer '+token,'X-Dominium-Actor':encodeURIComponent(actor)},redirect:'manual',signal:controller.signal};
      if(req.method==='POST'){
        if(!req.body||typeof req.body!=='object'||Array.isArray(req.body))return res.status(400).json({ok:false,error:'Corpo da revisão inválido'});
        options.headers['Content-Type']='application/json';options.body=JSON.stringify({...req.body,actor});
      }
      const response=await fetchImpl(url.origin+route,options);
      if(response.status>=300&&response.status<400)throw new Error('review_redirect_blocked');
      const payload=Buffer.from(await response.arrayBuffer());
      if(payload.length>16*1024*1024)throw new Error('review_response_too_large');
      if(req.method==='POST')await audit(user,'desc_review',String(response.status),req,String(req.body.id||''));
      res.set('content-type',response.headers.get('content-type')||'application/json');
      return res.status(response.status).send(payload);
    }catch{
      return res.status(503).json({ok:false,error:'Serviço DESCONEXÃO indisponível; evidências anteriores preservadas'});
    }finally{clearTimeout(timer);}
  };
}
module.exports={createDisconnectionMiddleware,allowedRoute};
