'use strict';
const crypto=require('node:crypto');
const {allowedBacklogRoute}=require('./operational-policy');

const ORIGIN='https://dominium-backlog-bridge.dmv-analise-backlog.workers.dev';
const TOKEN_PATTERN=/^[A-Za-z0-9_-]{43,128}$/;
const ID_PATTERN=/^[A-Za-z0-9_.%-]{1,160}$/;
function config() {
  const token=String(process.env.DOMINIUM_BACKLOG_BRIDGE_TOKEN||'').trim();
  return TOKEN_PATTERN.test(token)?{origin:ORIGIN,token}:null;
}
function createBacklogMiddleware({connection=config,fetchImpl=globalThis.fetch}={}) {
  return async function backlogProxy(req,res) {
    const session=req.dominiumSession,user=req.dominiumUser;
    if(!session||!user)return res.status(401).json({ok:false,error:'Entre no DOMINIUM para continuar'});
    const role=String(user.role||'');
    if(!['admin','controller'].includes(role))return res.status(403).json({ok:false,error:'Perfil operacional necessario'});
    const path=String(req.originalUrl||'');
    if(!allowedBacklogRoute(req.method,path))return res.status(404).json({ok:false,error:'Rota Backlog nao autorizada'});
    if(req.method==='POST') {
      const received=String(req.headers?.['x-csrf-token']||'');
      const expected=String(session.csrf_hash||'');
      const hash=crypto.createHash('sha256').update(received).digest('hex');
      if(!received||!expected||hash!==expected)return res.status(403).json({ok:false,error:'Sessao invalida; entre novamente'});
    }
    const actor=String(user.id??'');
    if(!ID_PATTERN.test(actor))return res.status(403).json({ok:false,error:'Identidade operacional invalida'});
    const privateLink=connection();
    if(!privateLink||!TOKEN_PATTERN.test(String(privateLink.token||''))||privateLink.origin!==ORIGIN){
      return res.status(503).json({ok:false,error:'Ponte privada do Backlog ainda nao configurada'});
    }
    let body;
    if(req.method==='POST'){
      body=JSON.stringify(req.body??{});
      if(Buffer.byteLength(body,'utf8')>(req.path==='/api/backlog/year/routes'?22*1024*1024:8192)){
        return res.status(413).json({ok:false,error:'Solicitacao acima do limite'});
      }
    }
    const headers={
      Authorization:'Bearer '+privateLink.token,
      'X-Dominium-Role':role,
      'X-Dominium-Actor':actor,
      Accept:'application/json',
    };
    if(body!==undefined)headers['Content-Type']='application/json';
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),req.path==='/api/backlog/year/routes'?160000:120000);
    try{
      const upstream=await fetchImpl(ORIGIN+path,{
        method:req.method,headers,body,redirect:'manual',signal:controller.signal,
      });
      if(upstream.status>=300&&upstream.status<400)return res.status(502).json({ok:false,error:'Redirecionamento inesperado na ponte'});
      if(upstream.status>=500)return res.status(502).json({ok:false,error:'API privada do Backlog indisponivel'});
      if(!String(upstream.headers?.get('content-type')||'').toLowerCase().includes('application/json'))
        return res.status(502).json({ok:false,error:'Formato de resposta inesperado'});
      const payload=Buffer.from(await upstream.arrayBuffer());
      if(payload.length>8*1024*1024)return res.status(502).json({ok:false,error:'Resposta acima do limite'});
      return res.status(upstream.status).set('cache-control','no-store').set('content-type','application/json; charset=utf-8').send(payload);
    }catch{
      return res.status(502).json({ok:false,error:'Nao foi possivel contactar o Backlog privado'});
    }finally{
      clearTimeout(timer);
    }
  };
}
module.exports={createBacklogMiddleware};
