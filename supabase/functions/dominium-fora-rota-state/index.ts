import { PROFILES, KINDS, validateScope, cleanRecords, mergeLegacy } from './core.mjs';
const url=Deno.env.get('SUPABASE_URL')||'';
const service=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});}
async function rest(path,method='GET',body=undefined){
  const r=await fetch(url+'/rest/v1/'+path,{method,headers:{apikey:service,Authorization:'Bearer '+service,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  if(!r.ok) throw new Error('Banco indisponivel');
  return r.json();
}
const rpc=(name,body)=>rest('rpc/'+name,'POST',body);
async function latest(profile,kind) {
  validateScope(profile,kind);
  const rows=await rest('dominium_fora_rota_snapshots?select=revision,records,source_name,created_at&profile=eq.'+profile+'&kind=eq.'+kind+'&order=revision.desc&limit=1');
  return rows[0]||{revision:0,records:[],source_name:'',created_at:null};
}
Deno.serve(async req=>{
  if(req.method!=='POST')return json({ok:false,error:'Metodo invalido'},405);
  const key=req.headers.get('x-dominium-edge-key')||'';
  if(!service||!url||key.length<32||key.length>256)return json({ok:false,error:'Acesso negado'},403);
  try {
    if(await rpc('dominium_web_bridge_ok',{p_token:key})!==true)return json({ok:false,error:'Acesso negado'},403);
    const length=Number(req.headers.get('content-length')||0);
    if(length>5500000)return json({ok:false,error:'Arquivo acima do limite'},413);
    const raw=await req.text();
    if(new TextEncoder().encode(raw).length>5500000)return json({ok:false,error:'Arquivo acima do limite'},413);
    const b=JSON.parse(raw),actor=Number(b.actor_user_id);
    if(!Number.isSafeInteger(actor)||actor<=0)return json({ok:false,error:'Acesso negado'},403);
    const user=await rpc('dominium_web_user_json',{p_user_id:actor});
    if(user?.status!=='active'||!['admin','controller'].includes(user?.role))return json({ok:false,error:'Acesso negado'},403);
    if(b.action==='get_all') {
      const pairs=PROFILES.flatMap(profile=>KINDS.filter(kind=>profile!=='unassigned'||kind==='legacy_sent').map(kind=>({profile,kind})));
      const snapshots=await Promise.all(pairs.map(async ({profile,kind})=>({profile,kind,...await latest(profile,kind)})));
      return json({ok:true,snapshots});
    }
    const profile=b.profile,kind=b.kind;
    validateScope(profile,kind);
    if(b.action==='get')return json({ok:true,...await latest(profile,kind)});
    if(b.action==='mark_sent') {
      if(kind!=='legacy_sent'||profile==='unassigned'||!Array.isArray(b.records)||b.records.length<1||b.records.length>100)return json({ok:false,error:'Lista de envio invalida'},400);
      const requested=cleanRecords(profile,kind,b.records);
      const [previous,unknown,claro,clean]=await Promise.all([latest(profile,kind),latest('unassigned',kind),latest(profile,'claro'),latest(profile,'clean106')]);
      if(previous.revision!==b.expected_revision)return json({ok:false,error:'Historico alterado; gere novamente',revision:previous.revision},409);
      const used=new Set([...previous.records,...unknown.records].map(r=>r.contract));
      const eligible=new Set(clean.records);
      const allowed=new Set(claro.records.map(r=>r.contract));
      if(requested.some(r=>used.has(r.contract)||!eligible.has(r.contract)||!allowed.has(r.contract)))return json({ok:false,error:'Contrato ja registrado ou fora da base 106/Claro; gere novamente'},409);
      const now=new Date().toISOString();
      const rows=requested.map(r=>({contract:r.contract,city:r.city,technician:r.technician,agenda:r.agenda,sentDate:r.sentDate||now.slice(0,10),sentAt:now,updatedAt:now,status:'aguardando_tecnico',source:'dominium'}));
      const result=await rpc('dominium_fora_rota_snapshot_put',{p_profile:profile,p_kind:kind,p_expected_revision:previous.revision,p_records:[...previous.records,...rows],p_source_name:'Registro de envio DOMINIUM',p_actor_id:actor});
      if(!result?.ok)return json({ok:false,error:'Historico alterado; gere novamente'},409);
      return json({ok:true,revision:result.revision,count:rows.length});
    }
    if(b.action!=='put')return json({ok:false,error:'Acao invalida'},400);
    if(kind==='legacy_sent'&&user.role!=='admin')return json({ok:false,error:'Migracao exige administrador'},403);
    if(!Number.isInteger(b.expected_revision)||b.expected_revision<0||typeof b.source_name!=='string'||!b.source_name.trim()||b.source_name.length>200)return json({ok:false,error:'Versao ou origem invalida'},400);
    let records=cleanRecords(profile,kind,b.records);
    if(kind==='legacy_sent') {
      const previous=await latest(profile,kind);
      if(previous.revision!==b.expected_revision)return json({ok:false,error:'Versao alterada; atualize antes de importar',revision:previous.revision},409);
      records=mergeLegacy(previous.records,records);
    }
    const result=await rpc('dominium_fora_rota_snapshot_put',{p_profile:profile,p_kind:kind,p_expected_revision:b.expected_revision,p_records:records,p_source_name:b.source_name,p_actor_id:actor});
    if(!result?.ok)return json({ok:false,error:'Versao alterada; atualize antes de importar',revision:result?.revision},409);
    return json({ok:true,revision:result.revision,unchanged:result.unchanged});
  } catch(e) {
    const msg=e instanceof Error?e.message:'';
    const safe=['Contrato invalido no arquivo','Escopo invalido','Lista invalida ou acima do limite','Registro invalido','Registro fora da cidade selecionada','Codigo de retorno invalido','Contrato/cidade duplicado com dados divergentes'].includes(msg);
    return json({ok:false,error:safe?msg:'Falha na operacao de bases compartilhadas'},safe?400:503);
  }
});
