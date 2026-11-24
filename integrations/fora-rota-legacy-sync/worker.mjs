const ENDPOINT='https://haqzzxpocwzntyudrbch.supabase.co/functions/v1/dominium-fora-rota-legacy-sync';
const headers={'Content-Type':'application/json','Cache-Control':'no-store'};
function json(body,status=200){return new Response(JSON.stringify(body),{status,headers});}
async function equal(a,b){
 if(typeof a!=='string'||typeof b!=='string'||!a||a.length>128||b.length>128)return false;
 const dig=async s=>new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
 const [x,y]=await Promise.all([dig(a),dig(b)]);let n=0;for(let i=0;i<x.length;i++)n|=x[i]^y[i];return n===0;
}
export async function sync(env,{full=false,now=Date.now()}={}){
 if(!env.SYNC_TOKEN||!env.DB)throw Error('Sync configuration unavailable');
 const cutoff=new Date(now-48*3600*1000).toISOString();
 let cursor='',pages=0,read=0,changes=0;
 while(true){
  if(++pages>400)throw Error('D1 pagination limit');
  const statement=full
   ?env.DB.prepare('SELECT contract,data_json,city,city_label,technician,sent_date,sent_at,status,last_return_code,returned_at,returned_by_technician,group_id,group_name,last_message,return_count,updated_at FROM fora_rota_sent_contracts WHERE contract > ? ORDER BY contract LIMIT 250').bind(cursor)
   :env.DB.prepare('SELECT contract,data_json,city,city_label,technician,sent_date,sent_at,status,last_return_code,returned_at,returned_by_technician,group_id,group_name,last_message,return_count,updated_at FROM fora_rota_sent_contracts WHERE contract > ? AND updated_at >= ? ORDER BY contract LIMIT 250').bind(cursor,cutoff);
  const result=await statement.all();
  const rows=result.results||[];
  if(!rows.length)break;
  const records=rows.map(row=>{
   const record=JSON.parse(row.data_json);
   if(!record||typeof record!=='object'||Array.isArray(record))throw Error('Invalid D1 row');
   const mapped={...record,contract:String(row.contract)};
   const columns={city:'city',city_label:'cityLabel',technician:'technician',
    sent_date:'sentDate',sent_at:'sentAt',status:'status',last_return_code:'lastReturnCode',
    returned_at:'returnedAt',returned_by_technician:'returnedByTechnician',
    group_id:'groupId',group_name:'groupName',last_message:'lastMessage',updated_at:'updatedAt'};
   for(const [column,key] of Object.entries(columns)){
    const value=row[column];
    if(typeof value==='string'&&value.trim())mapped[key]=value;
   }
   if(Number.isSafeInteger(row.return_count)&&row.return_count>=0){
    mapped.returnCount=Math.max(Number.isSafeInteger(record.returnCount)?record.returnCount:0,row.return_count);
   }
   return mapped;
  });
  const r=await fetch(ENDPOINT,{method:'POST',headers:{...headers,'X-Sync-Token':env.SYNC_TOKEN},body:JSON.stringify({records}),redirect:'manual',signal:AbortSignal.timeout(45000)});
  const reply=await r.json().catch(()=>null);
  if(!r.ok||!reply?.ok||reply.received!==records.length)throw Error('Supabase sync rejected: '+r.status);
  read+=records.length;changes+=Number(reply.changed)||0;
  const next=String(rows.at(-1).contract);
  if(next<=cursor)throw Error('Invalid D1 cursor');
  cursor=next;if(rows.length<250)break;
 }
 return {ok:true,read,changes,full};
}
export default{
 async fetch(req,env){
  const u=new URL(req.url);
  if(req.method!=='POST'||u.pathname!=='/sync'||!await equal(req.headers.get('X-Sync-Token'),env.SYNC_TOKEN))return json({ok:false},404);
  try{return json(await sync(env,{full:true}));}catch(e){console.error('FORA_ROTA_SYNC_FAILED',e instanceof Error ? e.name : 'Error');return json({ok:false,error:'Sync failed'},503);}
 },
 async scheduled(event,env,ctx){
  const t=new Date(event.scheduledTime);
  const full=t.getUTCHours()===0&&t.getUTCMinutes()===0;
  ctx.waitUntil(sync(env,{full,now:event.scheduledTime}).then(r=>console.log('FORA_ROTA_SYNC',JSON.stringify(r))).catch(()=>{console.error('FORA_ROTA_SYNC_FAILED');throw Error('Sync failed');}));
 }
};
