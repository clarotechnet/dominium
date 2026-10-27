import policy from '../../deploy/hostinger-web/import-policy.js';
import descPolicy from '../../deploy/hostinger-web/disconnection-policy.js';
import operationalPolicy from '../../deploy/hostinger-web/operational-policy.js';
import confrontPolicy from '../../deploy/hostinger-web/confront-policy.js';
import atlasPolicy from '../../deploy/hostinger-web/atlas-query-policy.js';
const {allowedImportRoute, MAX_IMPORT_BYTES} = policy;
const {allowedOperationalRead,allowedToaLookup} = operationalPolicy;
const {allowedConfrontRoute} = confrontPolicy;
const {allowedAtlasQueryRoute} = atlasPolicy;
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
    const officialStock=/^\/api\/imperium-official\/stocks(?:\/[1-9][0-9]{0,9}\/items)?$/.test(url.pathname);
    const serialConsult=url.pathname==='/api/serials/consult';
    const confrontation=allowedConfrontRoute(request.method,url.pathname+url.search);
    const query=allowedAtlasQueryRoute(request.method,url.pathname+url.search);
    const operational=allowedOperationalRead(request.method,url.pathname+url.search);
    const toaLookup=allowedToaLookup(request.method,url.pathname+url.search);
    const role=request.headers.get('x-dominium-role');
    if (!((operational && !officialStock && !serialConsult && !confrontation && !query && !toaLookup) ? ['admin','controller','viewer'] : ['admin','controller']).includes(role) ||
        !request.headers.get('x-dominium-actor')) return json(403,'Operador não identificado');
    let route;
    try {route=(operational || confrontation || query || toaLookup) ? url.pathname+url.search : (desc ? descPolicy.allowedRoute : allowedImportRoute)(request.method,url.pathname+url.search);}
    catch {return json(404,'Rota não permitida');}
    const headers=new Headers({Accept:'application/json','X-Dominium-Actor':request.headers.get('x-dominium-actor')});
    if(desc || officialStock || serialConsult || confrontation || query)headers.set('Authorization',request.headers.get('authorization'));
    if(desc || officialStock || serialConsult || confrontation || query)headers.set('X-Dominium-Role',role);
    let body;
    if (request.method==='POST') {
      if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) return json(415,'Envie JSON');
      const maxBytes=(desc || confrontation || query || toaLookup) ? 64*1024 : MAX_IMPORT_BYTES;
      if (Number(request.headers.get('content-length')||0)>maxBytes) return json(413,'Arquivo acima do limite');
      body=await request.arrayBuffer();
      if(body.byteLength>maxBytes)return json(413,'Arquivo acima do limite');
      headers.set('Content-Type','application/json');
    }
    try {
      const service=(desc || officialStock || serialConsult || confrontation || query) ? env.DESC_SERVICE : env.IMPORT_SERVICE;
      const origin=(desc || officialStock || serialConsult || confrontation || query) ? 'http://127.0.0.1:8793' : 'http://127.0.0.1:8765';
      const upstream=await service.fetch(new Request(origin+route,
        {method:request.method,headers,body,redirect:'manual'}));
      if (upstream.status>=300 && upstream.status<400) return json(502,'Redirecionamento interno bloqueado');
      return new Response(upstream.body,{status:upstream.status,headers:{
        'Content-Type':upstream.headers.get('content-type')||'application/json',
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Dominium-Backend':'private-import-bridge'}});
    } catch {return json(502,'Servidor operacional indisponível; não repita uma importação sem conferir o histórico');}
  }
};
