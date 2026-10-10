'use strict';
// The private Imperium reader is authoritative for OS identity and assignment.
function orderEvidence(batch, snapshot, now=Date.now()) {
  if(!batch.require_imperium_verification)return {verified:false,blockers:[]};
  const e=batch.imperium, blockers=[];
  const stamp=typeof e?.checked_at==='string'?Date.parse(e.checked_at):NaN, age=now-stamp;
  if(!e||e.ok!==true||e.confirmed!==true||e.searched!==true||!Array.isArray(e.orders)||!['imperium_detail','open_orders_no_match'].includes(e.source)||!Number.isFinite(stamp)||age< -30000||age>300000) return {verified:false,blockers:['Imperium: reconsulte a OS para confirmar o recurso do remetente']};
  if(e.contract!==batch.contract||e.profile_key!==batch.profile)blockers.push('Imperium: contrato ou cidade divergente');
  if(e.orders.some(o=>!o||typeof o!=='object'||Array.isArray(o)||typeof o.num_os!=='string'||!/^\d{1,10}$/.test(o.num_os)||!Number.isSafeInteger(o.id_os)||o.id_os<=0||!Number.isSafeInteger(o.installer_id)||o.installer_id<=0))return {verified:false,blockers:['Imperium: resposta da OS malformada']};
  const seen=new Set();
  for(const o of e.orders){
    if(!/^\d{1,10}$/.test(String(o.num_os||''))||!Number.isSafeInteger(o.id_os)||o.id_os<=0||o.contract!==batch.contract||o.status!=='EM CAMPO'||!Number.isSafeInteger(o.installer_id)||o.installer_id<=0||seen.has(o.num_os))blockers.push('Imperium: identidade da OS não confirmada');
    seen.add(o.num_os);
    if(String(o.installer_id)!==String(batch.technician?.imperium_id||''))blockers.push(`Imperium: OS ${o.num_os} pertence a outro recurso, diferente do remetente`);
  }
  if(e.orders.length&&e.source!=='imperium_detail'||!e.orders.length&&e.source!=='open_orders_no_match')blockers.push('Imperium: resposta de consulta inconsistente');
  if(snapshot){
    const tasks=(snapshot.tasks||[]).filter(t=>['400','409','430','512','706'].includes(String(t.close_code||t.codigo_baixa||snapshot.current_close_code||'')));
    if(!tasks.length)blockers.push('Imperium: nenhuma OS selecionada para comparação');
    for(const t of tasks)if(!e.orders.some(o=>o.num_os===String(t.os_number||t.num_os||'')))blockers.push('Imperium: OS selecionada não está aberta no contrato');
    if(e.orders.length!==tasks.length)blockers.push('Imperium: OS retornadas divergem da seleção');
  }else if(e.orders.length)blockers.push('Imperium: OS aberta exige seleção explícita antes de propor nova OS');
  return {verified:blockers.length===0,blockers:[...new Set(blockers)]};
}
module.exports={orderEvidence};
