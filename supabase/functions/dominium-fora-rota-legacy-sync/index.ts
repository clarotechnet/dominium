import { profileForCity, cleanRecords } from './core.mjs';
import { mergeSync } from './merge.mjs';
const TOKEN_HASH='7f14acf7a266a5495d8731b412479eb2330427a99c1eeb54aa6c155df4e9ad73';
const url=Deno.env.get('SUPABASE_URL')||'';
const service=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
const profiles=['natal','fortaleza','mossoro','recife','unassigned'];
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
async function authorized(token:string){
 if(token.length<40||token.length>128)return false;
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)))).map(b=>b.toString(16).padStart(2,'0')).join('');
 let diff=0;for(let i=0;i<TOKEN_HASH.length;i++)diff|=hash.charCodeAt(i)^TOKEN_HASH.charCodeAt(i);return diff===0;
}
async function rest(path:string,body?:unknown){
 const r=await fetch(url+'/rest/v1/'+path,{method:body===undefined?'GET':'POST',headers:{apikey:service,Authorization:'Bearer '+service,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
 if(!r.ok)throw Error('Database operation failed');
 return r.json();
}
Deno.serve(async req=>{
 if(req.method!=='POST'||!await authorized(req.headers.get('X-Sync-Token')||''))return json({ok:false},403);
 try{
  if(!url||!service)return json({ok:false},503);
  const length=Number(req.headers.get('content-length')||0);if(length>5000000)return json({ok:false},413);
  const raw=await req.text();if(new TextEncoder().encode(raw).length>5000000)return json({ok:false},413);
  const b=JSON.parse(raw);if(!Array.isArray(b.records)||b.records.length>250)return json({ok:false},400);
  const groups=Object.fromEntries(profiles.map(p=>[p,[]]));
  const seen=new Set();
  for(const row of b.records){
   if(!row||typeof row.contract!=='string'||seen.has(row.contract))return json({ok:false},400);
   seen.add(row.contract);
   groups[profileForCity(row.city||row.cityLabel)||'unassigned'].push(row);
  }
  // Validate every group before writing any of them.
  for(const p of profiles)groups[p]=cleanRecords(p,'legacy_sent',groups[p]);
  let changed=0,conflicts=0;
  for(const p of profiles){
   if(!groups[p].length)continue;
   let done=false;
   for(let attempt=0;attempt<3;attempt++){
    const prev=(await rest('dominium_fora_rota_snapshots?select=revision,records&profile=eq.'+p+'&kind=eq.legacy_sent&order=revision.desc&limit=1'))[0]||{revision:0,records:[]};
    const next=mergeSync(prev.records,groups[p]);
    if(!next.changed){conflicts+=next.conflicts;done=true;break;}
    const r=await rest('rpc/dominium_fora_rota_snapshot_put',{p_profile:p,p_kind:'legacy_sent',p_expected_revision:prev.revision,p_records:next.records,p_source_name:'Cloudflare bot sync (service)',p_actor_id:900000001});
    if(r?.ok){changed+=r.unchanged?0:next.changed;conflicts+=next.conflicts;done=true;break;}
    if(!r?.conflict)break;
   }
   if(!done)return json({ok:false},409);
  }
  return json({ok:true,received:b.records.length,changed,conflicts});
 }catch{return json({ok:false},503);}
});
