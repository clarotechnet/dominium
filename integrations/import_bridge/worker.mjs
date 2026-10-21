import policy from '../../deploy/hostinger-web/import-policy.js';
import descPolicy from '../../deploy/hostinger-web/disconnection-policy.js';
import operationalPolicy from '../../deploy/hostinger-web/operational-policy.js';
const {allowedImportRoute, MAX_IMPORT_BYTES} = policy;
const {allowedOperationalRead} = operationalPolicy;
function json(status, error) {
  return Response.json({ok:false,error},{status,headers:{'cache-control':'no-store','x-content-type-options':'nosniff'}});
}
async function authorized(request, token) {
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(String(token||''))) return false;
  const hash=async value=>new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)));
  const [a,b]=await Promise.all([hash(request.headers.get('authorization')||''),hash('Bearer '+token)]);
  let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];return diff===0;
}
export default {
  async fetch(request,env) {
    if (!await authorized(request,env.IMPORT_TOKEN)) return json(401,'Conexão interna não autorizada');
    const url=new URL(request.url);
    const desc=url.pathname.startsWith('/api/disconnection/');
    const operational=allowedOperationalRead(request.method,url.pathname+url.search);
    const role=request.headers.get('x-dominium-role');
    if (!(operational ? ['admin','controller','viewer'] : ['admin','controller']).includes(role) ||
        !request.headers.get('x-dominium-actor')) return json(403,'Operador não identificado');
    let route;
    try {route=operational ? url.pathname+url.search : (desc ? descPolicy.allowedRoute : allowedImportRoute)(request.method,url.pathname+url.search);}
    catch {return json(404,'Rota não permitida');}
    const headers=new Headers({Accept:'application/json','X-Dominium-Actor':request.headers.get('x-dominium-actor')});
    if(desc)headers.set('Authorization',request.headers.get('authorization'));
    let body;
    if (request.method==='POST') {
      if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) return json(415,'Envie JSON');
      const maxBytes=desc ? 64*1024 : MAX_IMPORT_BYTES;
      if (Number(request.headers.get('content-length')||0)>maxBytes) return json(413,'Arquivo acima do limite');
      body=await request.arrayBuffer();
      if(body.byteLength>maxBytes)return json(413,'Arquivo acima do limite');
      headers.set('Content-Type','application/json');
    }
    try {
      const service=desc ? env.DESC_SERVICE : env.IMPORT_SERVICE;
      const origin=desc ? 'http://127.0.0.1:8793' : 'http://127.0.0.1:8765';
      const upstream=await service.fetch(new Request(origin+route,
        {method:request.method,headers,body,redirect:'manual'}));
      if (upstream.status>=300 && upstream.status<400) return json(502,'Redirecionamento interno bloqueado');
      return new Response(upstream.body,{status:upstream.status,headers:{
        'Content-Type':upstream.headers.get('content-type')||'application/json',
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Dominium-Backend':'private-import-bridge'}});
    } catch {return json(502,'Servidor operacional indisponível; não repita uma importação sem conferir o histórico');}
  }
};
