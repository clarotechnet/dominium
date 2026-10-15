'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {allowedImportRoute, MAX_IMPORT_BYTES} = require('./import-policy');
const IMPORT_ORIGIN = 'https://dominium-import-bridge.jogador743.workers.dev';
function readConnection() {
  const filename = path.join(__dirname, '.desc-review-connection.json');
  const stored = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : {};
  return {token: process.env.DOMINIUM_DESC_REVIEW_TOKEN || stored.token};
}
function createImportMiddleware({connection = readConnection, fetchImpl = fetch} = {}) {
  return async (req,res) => {
    res.set('cache-control','no-store');
    const user = req.dominiumUser;
    if (!user?.role || !req.dominiumSession) return res.status(401).json({ok:false,error:'Entre no DOMINIUM para continuar'});
    if (!['admin','controller'].includes(user.role)) return res.status(403).json({ok:false,error:'Importação exige perfil operacional'});
    if (req.method === 'POST') {
      const csrf = String(req.headers['x-csrf-token'] || '');
      if (!csrf || crypto.createHash('sha256').update(csrf).digest('hex') !== req.dominiumSession.csrf_hash)
        return res.status(403).json({ok:false,error:'Sessão inválida; atualize a página'});
    }
    let route;
    try {route=allowedImportRoute(req.method,req.originalUrl);}
    catch(error) {return res.status(400).json({ok:false,error:error.message});}
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(),285000);
    let sent = false;
    try {
      const {token} = connection();
      if (!/^[A-Za-z0-9_-]{43,128}$/.test(String(token||''))) throw new Error('import_connection_missing');
      const actor = String(user.display_name || user.username || user.id || '').slice(0,100);
      if (!actor) throw new Error('import_actor_missing');
      const headers = {Authorization:'Bearer '+token,'X-Dominium-Actor':encodeURIComponent(actor),
        'X-Dominium-Role':user.role,Accept:'application/json','User-Agent':'DOMINIUM-Hostinger-Import/1.0'};
      let body;
      if (req.method === 'POST') {
        if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return res.status(400).json({ok:false,error:'Corpo da importação inválido'});
        body=JSON.stringify(req.body);
        if (Buffer.byteLength(body)>MAX_IMPORT_BYTES) return res.status(413).json({ok:false,error:'Arquivo de importação acima do limite'});
        headers['Content-Type']='application/json';
      }
      sent=true;
      const upstream=await fetchImpl(IMPORT_ORIGIN+route,{method:req.method,headers,body,redirect:'manual',signal:controller.signal});
      if (upstream.status>=300 && upstream.status<400) throw new Error('import_redirect_blocked');
      const payload=Buffer.from(await upstream.arrayBuffer());
      if (payload.length>24*1024*1024) throw new Error('import_response_too_large');
      res.set('content-type',upstream.headers.get('content-type')||'application/json');
      res.set('x-dominium-backend','private-import-bridge');
      return res.status(upstream.status).send(payload);
    } catch {
      const uncertain=sent && route==='/api/imports/commit';
      return res.status(502).json({ok:false,outcome_unknown:uncertain,error:uncertain ?
        'A resposta da importação não foi confirmada. Consulte o histórico de importações e o estado das OS antes de repetir.' :
        'Conexão de importação indisponível. Nenhuma repetição automática foi realizada.'});
    } finally {clearTimeout(timer);}
  };
}
module.exports={createImportMiddleware};
