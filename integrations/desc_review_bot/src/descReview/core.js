'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {orderEvidence}=require('./orderEvidence');
const clone = value => JSON.parse(JSON.stringify(value));
const serial = value => String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
const text = value => String(value || '').trim();
const day = time => new Intl.DateTimeFormat('en-CA', {timeZone:'America/Fortaleza',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(time));
const norm = value => text(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
function resolveAtlas(raw) {
  const a = raw.resultado || raw;
  if(a.partial===true || (a.pagination_errors||[]).length) throw new Error('Atlas: histórico incompleto por falha de paginação');
  const bold = [...new Set((a.enderecaveis_negrito || []).map(serial).filter(Boolean))];
  if (bold.length !== 1) throw new Error('Atlas: exige exatamente um serial canônico em negrito');
  if (a.serial_baixavel && serial(a.serial_baixavel) !== bold[0]) throw new Error('Atlas: serial canônico divergente');
  if (a.serial_encontrado === false) throw new Error('Atlas: serial consultado não confirmado');
  const history = a.historico || a.history;
  if (!Array.isArray(history) || !history.length) throw new Error('Atlas: histórico não confirmado');
  const index = history.findIndex(r => text(r.numero_contrato || r.contract));
  if (index < 0) throw new Error('Atlas: nenhum contrato válido no histórico');
  const row = history[index];
  const contract = text(row.numero_contrato || row.contract);
  if(!/^\d{7}$/.test(contract))throw new Error('Atlas: primeiro contrato preenchido é inválido');
  if (a.numero_contrato && text(a.numero_contrato) !== contract) throw new Error('Atlas: primeiro contrato do histórico diverge');
  const type = text(a.tipo_equipamento || a.modelo_equipamento || a.equipment_type || (a.imperium_itens || []).find(x=>serial(x.serial)===bold[0])?.tipo);
  if (!type) throw new Error('Atlas: tipo/modelo do equipamento não confirmado');
  return {serial:bold[0],candidate:serial(a.serial_consultado || raw.serialSolicitado),contract,type,model:text(a.modelo_equipamento),date:text(row.data_alteracao),state:text(row.estado),location:text(row.tipo_localizacao || row.localizacao),history:clone(history),embratel:history.slice(0,index).some(r=>/\b(?:VIA\s+)?EMBRATEL\b/.test(norm(JSON.stringify(r)))),source:'ATLAS'};
}
function equipment(values, direction, blockers) {
  const map = new Map();
  for (const item of values || []) {
    const s = serial(item.serial);
    const type = text(item.equipment_type || item.tipo || item.type);
    if (!s || !type) {blockers.push('TOA: equipamento sem serial ou tipo confirmado');continue;}
    if (item.pool && ((direction==='incoming'&&!['install','installed'].includes(item.pool)) || (direction==='outgoing'&&!['deinstall','removed'].includes(item.pool)))) blockers.push('TOA: direção de equipamento divergente');
    if (map.has(s) && map.get(s).type !== type) blockers.push('TOA: tipo divergente para o mesmo serial');
    map.set(s,{serial:s,type,source:'TOA',direction});
  }
  return [...map.values()];
}
function buildPlan(batch, snapshot, now=Date.now()) {
  const blockers = [...(batch.capture_errors || [])];
  const warnings = [];
  const operations = [];
  const resolved = [];
  const authority=orderEvidence(batch,snapshot,now);
  blockers.push(...authority.blockers);
  if (!/^\d{7}$/.test(text(batch.contract))) blockers.push('Contrato deve ter exatamente 7 dígitos');
  if (!/^\d+$/.test(text(batch.technician?.imperium_id))||!Number.isSafeInteger(Number(batch.technician?.imperium_id))||Number(batch.technician?.imperium_id)<=0) blockers.push('Técnico sem recurso Imperium confirmado');
  if(batch.technician?.profiles?.length&&!batch.technician.profiles.includes(batch.profile))blockers.push('Técnico não cadastrado nesta cidade');
  for (const entry of batch.atlas || []) {
    try {
      const e=resolveAtlas(entry);
      if(e.contract!==batch.contract) blockers.push(`Atlas: contrato diverge para ${e.serial}`);
      if(!resolved.some(x=>x.serial===e.serial)) resolved.push(e);
    } catch(error) {blockers.push(error.message);}
  }
  const previouslySeen = new Set(batch.previously_seen || []);
  const fresh = resolved.filter(e=>!previouslySeen.has(e.serial));
  if (fresh.length !== resolved.length) warnings.push('Seriais já aprovados em teste no mesmo dia foram excluídos');
  const op = (code, incoming, outgoing, task=null, reason='') => ({code,os:task ? text(task.os_number || task.num_os) : null,create_os:!task,service:task?text(task.service || task.description):code==='400'?'Correção de estoque':code==='706'?'Envio de chip via técnico':'Retirada fora TOA',incoming,outgoing,materials:[],reason,source:task?'TOA':'WHATSAPP/ATLAS',notification:code==='400'?{recipient:'Alex Campos',whatsapp_id:'218442707820573@lid',state:'proposta não enviada'}:null,executed:false});
  const atlasItem = e => ({...e,direction:'outgoing'});
  if (snapshot) {
    const selectedTasks=(snapshot.tasks||[]).filter(t=>['400','409','430','512','706'].includes(text(t.close_code||t.codigo_baixa||snapshot.current_close_code)));
    const atlasRemoval=authority.verified && selectedTasks.length===1 && text(selectedTasks[0].close_code||selectedTasks[0].codigo_baixa||snapshot.current_close_code)==='430';
    if(text(snapshot.contract)!==batch.contract) blockers.push('TOA: contrato divergente');
    if(snapshot.profile_key && snapshot.profile_key!==batch.profile) blockers.push('TOA: cidade divergente');
    if(!atlasRemoval&&!snapshot.activity_id) blockers.push('TOA: ID da atividade ausente');
    if(!atlasRemoval&&!/^(completed|conclu[ií]d[ao]|complete)$/i.test(text(snapshot.activity_status || snapshot.status))) blockers.push('TOA: atividade ainda não concluída');
    const toaLogin = text(snapshot.technician_external_id || snapshot.technician_login || snapshot.responsibility?.route_provider?.external_id);
    if(!authority.verified&&batch.technician?.toa_login && toaLogin && norm(batch.technician.toa_login)!==norm(toaLogin)) blockers.push('TOA: técnico diverge do remetente');
    if(!authority.verified&&!toaLogin) blockers.push('TOA: técnico não confirmado');
    if(!authority.verified&&!batch.technician?.toa_login) blockers.push('TOA: vínculo do técnico com o remetente não confirmado');
    if(!atlasRemoval&&snapshot.materials_complete!==true) blockers.push('TOA: materiais incompletos');
    if((snapshot.unknown_equipments || []).length) blockers.push('TOA: equipamento com direção desconhecida');
    const incoming = equipment([...(snapshot.installed_equipments || []),...(snapshot.added_equipments || [])],'incoming',blockers);
    const outgoing = equipment(snapshot.removed_equipments,'outgoing',blockers);
    if(incoming.some(e=>outgoing.some(x=>x.serial===e.serial))) blockers.push('TOA: mesmo serial entrando e saindo');
    const tasks = (snapshot.tasks || []).filter(t=>['400','409','430','512','706'].includes(text(t.close_code || t.codigo_baixa || snapshot.current_close_code)));
    const codes = [...new Set(tasks.map(t=>text(t.close_code || t.codigo_baixa || snapshot.current_close_code)))];
    if(!tasks.length) blockers.push('TOA: nenhuma OS compatível com os códigos do fluxo');
    if(batch.requested_code&&codes.some(code=>code!==batch.requested_code))blockers.push('Código solicitado diverge da OS; não é permitido converter o código');
    if(codes.length>1) blockers.push('TOA: lote com códigos mistos exige movimentos por OS');
    if(tasks.length>1) blockers.push('TOA: várias OS exigem seleção explícita e equipamentos por tarefa');
    if(tasks.length===1) {
      const t=tasks[0], code=codes[0];
      if(!/^\d+$/.test(text(t.os_number || t.num_os))) blockers.push('TOA: número de OS inválido');
      if(['409','706'].includes(code)&&!incoming.length) blockers.push(`${code}: falta equipamento instalado no TOA`);
      if(code==='706'&&(incoming.length!==1||!/CHIP|SIM.?CARD/.test(norm(incoming[0]?.type)))) blockers.push('706: exige exatamente um chip instalado confirmado');
      if(code==='430'&&incoming.length) blockers.push('430: não aceita equipamentos entrando');
      const materialRows=(snapshot.materials || []).filter(x=>!norm(typeof x==='string'?x:x.description).includes('SERVICO SEM MATERIAL'));
      if(code==='430'&&materialRows.length) blockers.push('430: nunca recebe miscelânea');
      if(materialRows.some(x=>typeof x==='object'&&(!Number.isFinite(Number(x.quantity))||Number(x.quantity)<=0||Number(x.quantity)>5))) blockers.push('Material: quantidade inválida ou superior a 5');
      if(materialRows.some(x=>typeof x!=='object'))blockers.push('Material: quantidade não estruturada; exige conferência');
      if(materialRows.reduce((sum,x)=>sum+(Number(x?.quantity)||0),0)>5)blockers.push('Material: quantidade total superior a 5');
      const used=new Set([...incoming,...outgoing].map(e=>e.serial));
      const extras=fresh.filter(e=>!used.has(e.serial));
      const special=extras.filter(e=>e.embratel || batch.late_collection);
      const regular=extras.filter(e=>!special.includes(e));
      let removed=[...outgoing];
      if(code==='430') removed=[...removed,...regular.map(atlasItem)];
      if(atlasRemoval&&removed.some(e=>!resolved.some(a=>a.serial===e.serial&&a.contract===batch.contract)))blockers.push('430: todos os seriais retirados exigem confirmação Atlas do contrato');
      if(atlasRemoval&&!fresh.length)blockers.push('430: exige evidência Atlas do contrato informado');
      if(code==='430'&&!removed.length) blockers.push('430: exige serial retirado');
      const base=op(code,incoming,removed,t,atlasRemoval?'Retirada Atlas com recurso da OS confirmado no Imperium':'Movimentação original do TOA');
      base.materials=clone(materialRows);
      if((batch.previously_seen_os||[]).includes(base.os)){warnings.push('OS já simulada no mesmo dia; movimentação original excluída');if(base.materials.length||[...incoming,...outgoing].some(e=>!previouslySeen.has(e.serial)))blockers.push('OS já simulada com movimentos novos ou miscelânea; exige conferência');}else operations.push(base);
      if(code!=='430'&&regular.length) operations.push(op('430',[],regular.map(atlasItem),null,'Equipamentos adicionais fora da movimentação TOA'));
      if(special.length) operations.push(op('400',[],special.map(atlasItem),null,batch.late_collection?'Retirada adicional após lote anterior no mesmo dia':'EMBRATEL acima do primeiro contrato no Atlas'));
    }
  } else if(['409','512','706'].includes(batch.requested_code)&&!(batch.requested_code==='706'&&batch.technician?.freelancer)) {
    blockers.push(`${batch.requested_code}: exige movimentação confirmada no TOA`);
  } else if(batch.requested_code==='706'&&batch.technician?.freelancer) {
    if(fresh.length!==1||!/CHIP|SIM.?CARD/.test(norm(fresh[0]?.type))) blockers.push('706 freelancer: exige um chip Atlas do contrato informado');
    else operations.push(op('706',[{...fresh[0],direction:'incoming'}],[],null,'Entrega de chip pelo freelancer confirmado'));
  } else {
    const special=fresh.filter(e=>e.embratel || batch.late_collection);
    const regular=fresh.filter(e=>!special.includes(e));
    if(regular.length) operations.push(op('430',[],regular.map(atlasItem),null,'Retirada fora TOA com evidência Atlas'));
    if(special.length) operations.push(op('400',[],special.map(atlasItem),null,batch.late_collection?'Retirada adicional no mesmo dia':'EMBRATEL acima do contrato'));
  }
  if(!operations.length) blockers.push('Nenhuma movimentação confirmada para simular');
  return {mode:'test',contract:batch.contract,technician:clone(batch.technician || {}),activity:snapshot?.activity_id || null,operations,atlas:resolved,blockers:[...new Set(blockers)],warnings,executed:false,requires_human_approval:true};
}
function createReviewStore({directory,groups={},technicians={},now=Date.now,windowMs=300000,requireImperiumVerification=false}) {
  fs.mkdirSync(directory,{recursive:true});
  const file=path.join(directory,'review-state.json');
  let state={version:1,mode:'test',batches:[],messages:{},audit:[]};
  if(fs.existsSync(file)) {
    const loaded=JSON.parse(fs.readFileSync(file,'utf8'));
    if(loaded.version!==1||!Array.isArray(loaded.batches)||loaded.mode!=='test') throw new Error('Estado de revisão inválido; não foi sobrescrito');
    state=loaded;
    for(const b of state.batches) if(b.state==='processing') {b.state='blocked';b.capture_errors=[...(b.capture_errors||[]),'Consulta interrompida; refaça a leitura'];}
  }
  function save(){const temp=file+'.tmp';fs.writeFileSync(temp,JSON.stringify(state,null,2),{mode:0o600});fs.renameSync(temp,file);}
  function get(id){const b=state.batches.find(x=>x.id===id);if(!b)throw new Error('Lote não encontrado');return clone(b);}
  function ingest(event) {
    if(!groups[event.group]) return null;
    if(!text(event.id)||!text(event.sender)) throw new Error('Mensagem sem identidade');
    const messageKey=event.group+'|'+event.id;
    if(state.messages[messageKey]) return get(state.messages[messageKey]);
    const contract=text(event.contract);
    const time=Number.isFinite(event.received_at)?Math.min(event.received_at,now()):now();
    const key=[event.group,event.sender,contract].join('|');
    let b=state.batches.find(x=>x.key===key&&x.state==='buffering'&&x.deadline>time);
    if(!b) {
      const t=technicians[event.sender] || {name:text(event.sender_name)||event.sender};
      b={id:crypto.randomUUID(),key,group:event.group,profile:groups[event.group].profile,city:groups[event.group].city,sender:event.sender,contract,technician:clone(t),created_at:time,deadline:time+(event.demo===true?0:windowMs),state:'buffering',revision:1,messages:[],atlas:[],capture_errors:[],executed:false,demo:event.demo===true};
      if(!/^\d{7}$/.test(contract)){b.state='blocked';b.capture_errors.push('Contrato não identificado de forma única');}
      state.batches.push(b);
    }
    b.messages.push({id:event.id,text:text(event.text).slice(0,4000),received_at:time,photo:event.photo||null,reading:event.photo_reading?clone(event.photo_reading):null});
    b.atlas.push(...clone(event.atlas || []));
    b.capture_errors.push(...(event.errors || []));
    if(event.requested_code) {if(b.requested_code&&b.requested_code!==event.requested_code)b.capture_errors.push('Códigos diferentes no mesmo lote');b.requested_code=event.requested_code;}
    b.revision++;state.messages[messageKey]=b.id;save();return clone(b);
  }
  function prepare(id,snapshot,errors=[],imperium=null) {
    const b=state.batches.find(x=>x.id===id);if(!b)throw new Error('Lote não encontrado');
    if(['simulated','rejected'].includes(b.state))throw new Error('Lote já decidido');
    if(now()<b.deadline)throw new Error('Janela de 5 minutos ainda aberta');
    b.capture_errors=[...b.capture_errors,...errors];
    const previous=state.batches.filter(x=>x.id!==b.id&&x.state==='simulated'&&x.contract===b.contract&&x.sender===b.sender&&x.group===b.group&&x.demo===b.demo&&day(x.created_at)===day(b.created_at));
    b.previously_seen=previous.flatMap(x=>x.plan.operations.flatMap(o=>[...o.incoming,...o.outgoing].map(e=>e.serial)));
    b.previously_seen_os=previous.flatMap(x=>x.plan.operations.map(o=>o.os).filter(Boolean));
    b.late_collection=previous.length>0;
    b.require_imperium_verification=requireImperiumVerification&&!b.demo;
    b.imperium=imperium?clone(imperium):null;
    b.snapshot=snapshot?clone(snapshot):null;
    b.plan=buildPlan(b,b.snapshot,now());b.state=b.plan.blockers.length?'blocked':'review';b.revision++;save();return clone(b);
  }
  function decide(id,action,revision,actor,note='') {
    const b=state.batches.find(x=>x.id===id);if(!b)throw new Error('Lote não encontrado');
    if(!['approve','reject'].includes(action))throw new Error('Decisão inválida');
    if(b.revision!==Number(revision))throw new Error('A revisão mudou; recarregue o lote');
    if(!['review','blocked'].includes(b.state))throw new Error('Lote ainda não revisável ou já decidido');
    if(action==='approve'&&requireImperiumVerification&&!b.demo){const check=orderEvidence({...b,require_imperium_verification:true},b.snapshot,now());if(!check.verified)throw new Error(check.blockers.join('; '));}
    if(action==='approve'&&(b.state!=='review'||b.plan.blockers.length))throw new Error('Lote bloqueado não pode ser aprovado');
    b.state=action==='approve'?'simulated':'rejected';b.executed=false;b.revision++;b.decision={actor:text(actor).slice(0,100)||'Operador',note:text(note).slice(0,1000),at:now(),action,mode:'test'};
    state.audit.push({batch_id:id,...b.decision,revision:b.revision});save();return clone(b);
  }
  function updateTechnician(sender,record){if(!text(sender)||!text(record.name)||(!/^\d+$/.test(text(record.imperium_id))||!Number.isSafeInteger(Number(record.imperium_id))||Number(record.imperium_id)<=0))throw new Error('Informe nome e ID numérico do recurso Imperium');technicians[sender]={...technicians[sender],...record,name:text(record.name),imperium_id:text(record.imperium_id),freelancer:record.freelancer===true};for(const b of state.batches.filter(x=>x.sender===sender&&!['simulated','rejected'].includes(x.state))){b.technician=clone(technicians[sender]);b.revision++;if(b.plan){b.plan=buildPlan(b,b.snapshot,now());b.state=b.plan.blockers.length?'blocked':'review';}}save();return clone(technicians);}
  function markProcessing(id){const b=state.batches.find(x=>x.id===id);if(b&&b.state==='buffering'&&now()>=b.deadline){b.state='processing';save();return clone(b);}return null;}
  function replaceEvidence(id,entries,errors=[],readings={}){
    const b=state.batches.find(x=>x.id===id);if(!b||['simulated','rejected'].includes(b.state))throw new Error('Lote já decidido ou inexistente');
    const immutable=b.capture_errors.filter(e=>/Códigos diferentes no mesmo lote|Mensagem com vários contratos/.test(e));
    b.atlas=clone(entries);b.capture_errors=[...new Set([...immutable,...clone(errors)])];
    for(const m of b.messages)if(readings[m.photo])m.reading=clone(readings[m.photo]);
    if(!b.contract){
      const contracts=[...new Set(entries.flatMap(e=>{try{return [resolveAtlas(e).contract];}catch{return [];}}))];
      const captions=[...new Set(b.messages.flatMap(m=>[...m.text.matchAll(/(?<!\d)(\d{7})(?:\s*[-/:]?\s*(?:400|409|430|512|706))?(?!\d)/g)].map(x=>x[1])))];
      if(contracts.length===1&&captions.length<=1&&(!captions.length||captions[0]===contracts[0])){b.contract=contracts[0];b.key=[b.group,b.sender,b.contract].join('|');}
    }
    b.plan=null;b.state='buffering';b.revision++;save();return clone(b);
  }
  return {get,ingest,prepare,decide,updateTechnician,markProcessing,replaceEvidence,list:()=>clone(state.batches),audit:()=>clone(state.audit),execute:()=>{throw new Error('Modo de teste: baixa real desabilitada no código');},isTestGroup:group=>Boolean(groups[group]),groups,technicians};
}
module.exports={resolveAtlas,buildPlan,createReviewStore,serial,day};
