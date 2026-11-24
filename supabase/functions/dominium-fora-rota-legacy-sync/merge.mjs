const time=v=>{const n=Date.parse(v||'');return Number.isFinite(n)?n:0;};
const nonempty=v=>v!==null&&v!==undefined&&v!==''&&(!Array.isArray(v)||v.length>0);
function canonical(value){
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
export function mergeSync(previous,incoming){
 const records=[...previous],index=new Map(records.map((r,i)=>[r.contract,i]));
 let changed=0,conflicts=0;
 for(const row of incoming){
  const pos=index.get(row.contract);
  if(pos===undefined){index.set(row.contract,records.length);records.push(row);changed++;continue;}
  const old=records[pos],next={...old};
  const newer=time(row.updatedAt||row.sentAt)>time(old.updatedAt||old.sentAt);
  const oldReturn=time(old.returnedAt||old.updatedAt),newReturn=time(row.returnedAt||row.updatedAt);
  const oldCode=String(old.lastReturnCode||''),newCode=String(row.lastReturnCode||'');
  const returnFields=new Set(['lastReturnCode','returnedAt','lastMessage','returnedByTechnician','returnCount','returnHistory','groupId','groupName','status']);
  // Keep the original DOMINIUM send metadata; import only verified return details.
  const local=old.source==='dominium';
  const localFields=new Set(['city','name','address','bairro','cep','altAddress','agenda','technician','equipment','phones','sentAt','sentDate','source','baseCdNet']);
  for(const [key,value] of Object.entries(row)){
   if(returnFields.has(key)||(local&&localFields.has(key)))continue;
   if(nonempty(value)&&(newer||!nonempty(old[key])))next[key]=value;
  }
  if(oldCode&&newCode&&oldCode!==newCode&&newReturn===oldReturn)conflicts++;
  const preferReturn=!!newCode&&(!oldCode||newReturn>oldReturn);
  if(preferReturn){
   for(const field of ['lastReturnCode','returnedAt','lastMessage','returnedByTechnician','groupId','groupName','status'])if(nonempty(row[field]))next[field]=row[field];
  }else if(!oldCode&&!newCode&&newer&&nonempty(row.status)){next.status=row.status;}
  else if(oldCode&&oldCode===newCode&&newReturn===oldReturn){
   for(const field of ['returnedAt','lastMessage','returnedByTechnician','groupId','groupName'])if(!nonempty(old[field])&&nonempty(row[field]))next[field]=row[field];
  }
  const histories=[...(Array.isArray(old.returnHistory)?old.returnHistory:[])];
  const keys=new Set(histories.map(canonical));
  for(const event of Array.isArray(row.returnHistory)?row.returnHistory:[]){const k=canonical(event);if(!keys.has(k)){histories.push(event);keys.add(k);}}
  if(histories.length)next.returnHistory=histories;
  if(histories.length||Number(old.returnCount)||Number(row.returnCount))next.returnCount=Math.max(Number(old.returnCount)||0,Number(row.returnCount)||0,histories.length);
  if(canonical(old)!==canonical(next)){records[pos]=next;changed++;}
 }
 return {records,changed,conflicts};
}
