'use strict';
const crypto=require('node:crypto');
const {resolveAtlas,serial}=require('./core');
const PHOTO=/^[a-f0-9-]{36}\.jpg$/;
const clone=value=>JSON.parse(JSON.stringify(value));
function createManualSerialReview({store,lookupSerials,now=Date.now,scan=()=>{}}){
  const queries=new Map();
  function context(input,session){
    if(!input||typeof input!=='object'||typeof input.id!=='string'||input.id.length>100||!PHOTO.test(input.photo||'')||!Number.isSafeInteger(input.revision)||input.revision<1)throw new Error('Informe lote, foto e revisão válidos');
    if(!session||typeof session.actor!=='string'||!session.actor||typeof session.csrf!=='string'||!session.csrf)throw new Error('Sessão de consulta inválida');
    const batch=store.get(input.id);
    if(!batch.messages.some(m=>m.photo===input.photo))throw new Error('Foto não pertence a este lote');
    if(batch.archived_at||batch.state==='archived')throw new Error('Histórico de fotos é somente leitura');
    return batch;
  }
  function matchesContract(batch,equipment){
    if(batch.contract)return batch.contract===equipment.contract;
    const contracts=new Set(batch.messages.flatMap(m=>[...String(m.text||'').matchAll(/(?<!\d)(\d{7})(?!\d)/g)].map(x=>x[1])));
    for(const entry of batch.atlas||[]){try{contracts.add(resolveAtlas(entry).contract);}catch{}}
    return contracts.size===0||contracts.size===1&&contracts.has(equipment.contract);
  }
  async function lookup(input,session){
    const batch=context(input,session);
    if(typeof input.serial!=='string'||input.serial.length>80||!/^[A-Za-z0-9\s:.-]+$/.test(input.serial))throw new Error('Digite apenas o serial ou endereço do equipamento');
    const candidate=serial(input.serial);
    if(!/^[A-Z0-9]{8,24}$/.test(candidate))throw new Error('Serial deve ter entre 8 e 24 letras ou números');
    if(batch.revision!==input.revision)throw new Error('A revisão mudou; atualize o lote e consulte novamente');
    let result;
    try{result=await lookupSerials([candidate]);}catch{throw new Error('Atlas indisponível; nenhuma evidência foi alterada');}
    const entries=result?.resultadosAtlas?.length?result.resultadosAtlas:result?.retorno?.ok&&result.retorno.resultado?[{resultado:result.retorno.resultado}]:[];
    if(entries.length!==1)throw new Error('Atlas precisa confirmar exatamente um equipamento para este serial');
    const entry=entries[0],raw=entry?.resultado||entry;
    if(!raw||typeof raw!=='object'||!Array.isArray(raw.enderecaveis_negrito))throw new Error('Atlas retornou evidência inválida');
    const identifiers=[raw.serial_baixavel,...(Array.isArray(raw.enderecaveis)?raw.enderecaveis:[]),...(raw.serial_encontrado===true?[raw.serial_consultado]:[])].filter(x=>typeof x==='string').map(serial);
    if(!identifiers.includes(candidate))throw new Error('Atlas não confirmou que o equipamento pertence ao serial digitado');
    const equipment=resolveAtlas(entry);
    const latest=context(input,session),sameRevision=latest.revision===input.revision;
    const matches=matchesContract(latest,equipment);
    const canApply=matches&&sameRevision&&!['processing','simulated','rejected','executed'].includes(latest.state);
    for(const [key,value] of queries)if(value.expires_at<=now())queries.delete(key);
    while(queries.size>=200)queries.delete(queries.keys().next().value);
    const queryToken=crypto.randomUUID(),expiresAt=now()+300000;
    queries.set(queryToken,{id:batch.id,photo:input.photo,revision:input.revision,actor:session.actor,csrf:session.csrf,operator_session:session.operator_session||session.csrf,candidate,equipment:clone(equipment),entry:clone(entry),can_apply:canApply,expires_at:expiresAt});
    return {ok:true,query_token:queryToken,serial:candidate,equipment,matches_contract:matches,can_apply:canApply,expires_at:expiresAt};
  }
  async function apply(input,session){
    const batch=context(input,session),query=queries.get(input.query_token);
    if(!query||query.expires_at<=now()||query.id!==input.id||query.photo!==input.photo||query.actor!==session.actor||query.csrf!==session.csrf||query.operator_session!==(session.operator_session||session.csrf))throw new Error('Consulta expirou ou pertence a outra foto/sessão; consulte novamente');
    if(!query.can_apply||!matchesContract(batch,query.equipment))throw new Error('Contrato divergente ou lote indisponível para aplicar evidência');
    if(batch.revision!==input.revision||query.revision!==input.revision||['processing','simulated','rejected','executed'].includes(batch.state))throw new Error('A revisão mudou; consulte novamente antes de aplicar');
    const reading={stage:'confirmed',source:'manual_atlas',message:'Serial conferido manualmente no Atlas',candidates:[{value:query.candidate,source:'manual'}],confirmed:[{candidate:query.candidate,serial:query.equipment.serial,contract:query.equipment.contract,type:query.equipment.type}],manual:{actor:session.actor,at:now(),queried_serial:query.candidate,canonical_serial:query.equipment.serial}};
    const entries=(batch.atlas||[]).filter(e=>{try{return resolveAtlas(e).serial!==query.equipment.serial;}catch{return true;}});
    entries.push({...clone(query.entry),manual_lookup:reading.manual});
    const remainingPhotos=batch.messages.filter(m=>m.photo&&m.photo!==input.photo&&m.reading?.stage!=='confirmed');
    const errors=(batch.capture_errors||[]).filter(error=>!(remainingPhotos.length===0&&/^(Foto:|Foto sem contrato único|Contrato não identificado de forma única)/.test(error)));
    for(const m of remainingPhotos){const error='Foto: '+(m.reading?.message||'Outra foto ainda precisa de conferência');if(!errors.includes(error))errors.push(error);}
    const updated=store.replaceEvidence(batch.id,entries,errors,{[input.photo]:reading});
    queries.delete(input.query_token);
    void Promise.resolve().then(scan).catch(()=>{});
    return {ok:true,batch:updated};
  }
  return {lookup,apply};
}
module.exports={createManualSerialReview};
