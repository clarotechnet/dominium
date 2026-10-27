'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {allowedOrderClose, validOfficialCloseBody, closeTransportFailure} = require('./operational-policy');
const ORIGIN = 'https://dominium-import-bridge.jogador743.workers.dev';
function readConnection() {
  const filename = path.join(__dirname, '.desc-review-connection.json');
  const stored = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : {};
  return {token:process.env.DOMINIUM_DESC_REVIEW_TOKEN || stored.token};
}
function createOrderCloseMiddleware({connection=readConnection, fetchImpl=fetch}={}) {
  return async (req,res) => {
    res.set('cache-control','no-store');
    if (!req.dominiumSession || !req.dominiumUser) return res.status(401).json({ok:false,error:'Entre no DOMINIUM para continuar'});
    if (!['admin','controller'].includes(req.dominiumUser.role)) return res.status(403).json({ok:false,error:'Baixa exige perfil operacional'});
    const csrf=String(req.headers['x-csrf-token'] || '');
    if (!csrf || crypto.createHash('sha256').update(csrf).digest('hex') !== req.dominiumSession.csrf_hash)
      return res.status(403).json({ok:false,error:'Sessao invalida; atualize a pagina'});
    if (!allowedOrderClose(req.method,req.originalUrl)) return res.status(400).json({ok:false,error:'Baixa exige uma OS e uma cidade validas'});
    if (!String(req.headers['content-type'] || '').toLowerCase().startsWith('application/json'))
      return res.status(415).json({ok:false,error:'Envie JSON'});
    if (!validOfficialCloseBody(req.body)) return res.status(400).json({ok:false,error:'Esta ponte exige o canal API oficial do Imperium'});
    const body=JSON.stringify(req.body);
    if (Buffer.byteLength(body)>64*1024) return res.status(413).json({ok:false,error:'Solicitacao de baixa acima do limite'});
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),req.body.materials?.length ? 470000 : 285000);
    let sent=false;
    try {
      const {token}=connection();
      if (!/^[A-Za-z0-9_-]{43,128}$/.test(String(token||''))) throw new Error('close_connection_missing');
      const actor=String(req.dominiumUser.display_name || req.dominiumUser.username || req.dominiumUser.id || '').slice(0,100);
      if (!actor) throw new Error('close_actor_missing');
      sent=true;
      const upstream=await fetchImpl(ORIGIN+req.originalUrl,{method:'POST',redirect:'manual',signal:controller.signal,body,
        headers:{Accept:'application/json','Content-Type':'application/json',Authorization:'Bearer '+token,
          'X-Dominium-Role':req.dominiumUser.role,'X-Dominium-Actor':encodeURIComponent(actor)}});
      if (upstream.status>=300 && upstream.status<400) throw new Error('close_redirect_blocked');
      const text=await upstream.text();
      if (Buffer.byteLength(text)>1024*1024) throw new Error('close_response_too_large');
      const payload=JSON.parse(text);
      if (!payload || typeof payload !== 'object' || Array.isArray(payload) || typeof payload.ok !== 'boolean') throw new Error('close_invalid_response');
      res.set('x-dominium-backend','private-order-close-bridge');
      if (upstream.status>=500) return res.status(502).json({...payload,...closeTransportFailure()});
      return res.status(upstream.status).json(payload);
    } catch {
      return res.status(502).json(sent ? closeTransportFailure() :
        {ok:false,error:'Conexao de baixa indisponivel. Nenhuma solicitacao foi enviada.'});
    } finally {clearTimeout(timer);}
  };
}
module.exports={createOrderCloseMiddleware};
