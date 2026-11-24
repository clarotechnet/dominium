export const PROFILES = ['natal','fortaleza','mossoro','recife','unassigned'];
export const KINDS = ['claro','clean106','legacy_sent'];
const text = (v,max=200) => typeof v === 'string' ? v.trim().slice(0,max) : '';
const norm = v => text(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
export function profileForCity(city) {
  const n=norm(city);
  if (['natal','parnamirim','natal parnamirim'].includes(n)) return 'natal';
  if (n==='fortaleza') return 'fortaleza';
  if (n==='mossoro') return 'mossoro';
  if (['recife','pernambuco','recife pernambuco','jaboatao','jaboatao dos guararapes','olinda'].includes(n)) return 'recife';
  return '';
}
function contract(v) {
  if (typeof v !== 'string' || !/^\d{5,18}$/.test(v)) throw new Error('Contrato invalido no arquivo');
  return v;
}
export function validateScope(p,k) {
  if (!PROFILES.includes(p)||!KINDS.includes(k)||(p==='unassigned'&&k!=='legacy_sent')) throw new Error('Escopo invalido');
}
export function cleanRecords(profile,kind,records) {
  validateScope(profile,kind);
  if (!Array.isArray(records)||records.length>50000) throw new Error('Lista invalida ou acima do limite');
  if (kind==='clean106') return [...new Set(records.map(contract))].sort();
  const byKey=new Map();
  for (const r of records) {
    if (!r||typeof r!=='object'||Array.isArray(r)) throw new Error('Registro invalido');
    const city=text(r.city||r.cityLabel,100);
    const mapped=profileForCity(city);
    if (kind==='claro' ? mapped!==profile : (mapped||'unassigned')!==profile) throw new Error('Registro fora da cidade selecionada');
    const row={contract:contract(r.contract),city};
    for (const key of ['name','address','bairro','cep','altAddress','agenda','technician','equipment','baseCdNet']) row[key]=text(r[key],key==='equipment'?2000:500);
    row.phones=Array.isArray(r.phones)?[...new Set(r.phones.filter(v=>typeof v==='string').map(v=>v.slice(0,40)))].slice(0,16):[];
    if (kind==='legacy_sent') {
      for (const key of ['sentDate','sentAt','returnedAt','updatedAt','status','source','lastMessage','lastReturnCode','returnedByTechnician','groupName','groupId']) row[key]=text(r[key],key==='lastMessage'?2000:200);
      if (row.lastReturnCode&&!/^\d{1,4}$/.test(row.lastReturnCode)) throw new Error('Codigo de retorno invalido');
      if (Array.isArray(r.returnHistory)) row.returnHistory=r.returnHistory.slice(0,200).filter(x=>x&&typeof x==='object'&&!Array.isArray(x)&&JSON.stringify(x).length<=10000);
      if (Number.isSafeInteger(r.returnCount)&&r.returnCount>=0) row.returnCount=r.returnCount;
    }
    const key=(kind==='legacy_sent'?profile:norm(city))+':'+row.contract;
    if (byKey.has(key)&&JSON.stringify(byKey.get(key))!==JSON.stringify(row)) throw new Error('Contrato/cidade duplicado com dados divergentes');
    byKey.set(key,row);
  }
  return [...byKey.values()].sort((a,b)=>(norm(a.city)+':'+a.contract).localeCompare(norm(b.city)+':'+b.contract));
}
function time(v) { const n=Date.parse(v||''); return Number.isFinite(n)?n:0; }
export function mergeLegacy(oldRecords,newRecords) {
  const keyFor=r=>(profileForCity(r.city||r.cityLabel)||'unassigned')+':'+r.contract;
  const map=new Map(oldRecords.map(r=>[keyFor(r),r]));
  for (const r of newRecords) {
    const key=keyFor(r), old=map.get(key);
    if (!old) {map.set(key,r);continue;}
    const newest=time(r.updatedAt||r.sentAt)>=time(old.updatedAt||old.sentAt)?r:old;
    const merged={...old,...Object.fromEntries(Object.entries(newest).filter(([,v])=>v!==''&&(!Array.isArray(v)||v.length)))};
    // An ordinary sent marker must not erase an already recorded return.
    const ret=r.lastReturnCode&&(!old.lastReturnCode||time(r.returnedAt||r.updatedAt)>=time(old.returnedAt||old.updatedAt))?r:old;
    for (const field of ['lastReturnCode','returnedAt','lastMessage','returnedByTechnician']) merged[field]=ret[field]||'';
    const histories=new Map([...(old.returnHistory||[]),...(r.returnHistory||[])].map(h=>[JSON.stringify(h),h]));
    if(histories.size)merged.returnHistory=[...histories.values()];
    merged.returnCount=Math.max(Number(old.returnCount)||0,Number(r.returnCount)||0,histories.size);
    map.set(key,merged);
  }
  return [...map.values()].sort((a,b)=>(norm(a.city)+':'+a.contract).localeCompare(norm(b.city)+':'+b.contract));
}