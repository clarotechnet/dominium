'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {createReviewStore,resolveAtlas,serial,day}=require('./core');
const PREFIX='/desc-review';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function createDescReview({directory,groups,technicians={},toaBridge,toaLookup,verifyImperium,lookupPhoto,lookupSerials,now=Date.now,autoStart=true}) {
  fs.mkdirSync(directory,{recursive:true});
  const mappingFile=path.join(directory,'technicians.json');
  if(fs.existsSync(mappingFile))Object.assign(technicians,JSON.parse(fs.readFileSync(mappingFile,'utf8')));
  const store=createReviewStore({directory,groups,technicians,now,requireImperiumVerification:true});
  const accessFile=path.join(directory,'review-access.txt');
  let pin;
  if(fs.existsSync(accessFile))pin=fs.readFileSync(accessFile,'utf8').trim();
  else {pin=String(crypto.randomInt(10000000,100000000));fs.writeFileSync(accessFile,pin+'\n',{mode:0o600});}
  const pinHash=crypto.createHash('sha256').update(pin).digest();
  const sessions=new Map(),attempts=new Map();
  let busy=false,photoTail=Promise.resolve(),photoQueue=0;
  const pendingSenders=new Map();
  const status={mode:'test',executed:false,last_scan:null,last_error:'',photos_pending:0};
  const metadataFile=path.join(directory,'service-status.json');
  function persistStatus(){fs.writeFileSync(metadataFile,JSON.stringify({...status,updated_at:now()}));}
  function contracts(text){const raw=String(text||'');const set=new Set();for(const m of raw.matchAll(/(?<!\d)(\d{7})(?:\s*[-/:]?\s*(400|409|430|512|706))?(?!\d)/g))set.add(m[1]);return [...set];}
  function requestCode(text){const m=String(text||'').match(/(?:^|\D)(400|409|430|512|706)(?:\D|$)/);const joined=String(text||'').match(/^\s*\d{7}(400|409|430|512|706)\s*$/);return joined?.[1]||m?.[1]||'';}
  function canonicalEvent(event){return {...event,sender:technicians[event.sender]?.canonical_id||event.sender};}
  function captureMessage(event){event=canonicalEvent(event);if(!groups[event.group]||event.isImage||/^[!/]/.test(event.text||''))return null;const c=contracts(event.text);if(!c.length)return null;return store.ingest({...event,contract:c.length===1?c[0]:'',requested_code:requestCode(event.text),errors:c.length>1?['Mensagem com vários contratos; separe por contrato']:[]});}
  function capturePhoto(event,buffer) {
    event=canonicalEvent(event);
    if(!groups[event.group])return Promise.resolve(null);
    if(!Buffer.isBuffer(buffer)||buffer.length===0||buffer.length>15*1024*1024)return Promise.reject(new Error('Foto ausente ou maior que 15 MB'));
    if(photoQueue>=30)return Promise.reject(new Error('Fila de fotos cheia; reenvie após a revisão'));
    const photo=crypto.randomUUID()+'.jpg';const photosDir=path.join(directory,'photos');fs.mkdirSync(photosDir,{recursive:true});fs.writeFileSync(path.join(photosDir,photo),buffer,{mode:0o600});
    const capturedAt=Number.isFinite(event.received_at)?event.received_at:now(),senderKey=event.group+'|'+event.sender;pendingSenders.set(senderKey,(pendingSenders.get(senderKey)||0)+1);photoQueue++;status.photos_pending=photoQueue;persistStatus();
    const task=photoTail.then(async()=>{
      let entries=[],errors=[],reading=null;
      try {const consultation=await lookupPhoto(buffer);reading=consultation?.photoReading||null;entries=consultation?.resultadosAtlas || [];if(!entries.length&&consultation?.retorno?.resultado)entries=[{resultado:consultation.retorno.resultado}];if(!entries.length)errors.push('Foto: '+String(reading?.message||consultation?.retorno?.error||'Atlas/OCR sem resultado confirmado'));if(reading&&reading.stage!=='confirmed'&&entries.length)errors.push('Foto: '+reading.message);}catch(e){errors.push('Foto: '+e.message);}
      const caption=contracts(event.text),fromAtlas=[...new Set(entries.map(e=>String((e.resultado||e).numero_contrato||'')).filter(c=>/^\d{7}$/.test(c)))];
      const contract=caption.length===1?caption[0]:caption.length>1?'':fromAtlas.length===1?fromAtlas[0]:'';
      if(!contract)errors.push('Foto sem contrato único; não foi associada a outro lote');
      if(caption.length===1&&fromAtlas.some(c=>c!==contract))errors.push('Contrato da legenda diverge do Atlas');
      return store.ingest({...event,contract,atlas:entries,errors,photo,photo_reading:reading,received_at:capturedAt,requested_code:requestCode(event.text)});
    });
    photoTail=task.catch(e=>{status.last_error=e.message;}).finally(()=>{pendingSenders.set(senderKey,Math.max(0,(pendingSenders.get(senderKey)||1)-1));photoQueue--;status.photos_pending=photoQueue;persistStatus();});return task;
  }
  async function queryTOA(batch){
    if(toaLookup)return toaLookup(batch);
    if(!toaBridge?.getExtensionStatus()?.online)throw new Error('TOA: extensão offline; nenhuma ausência de OS foi presumida');
    const id='review-'+crypto.randomUUID();
    const job={job_id:id,message_id:batch.id,chat_id:batch.group,sender_id:batch.sender,contract:batch.contract,requested_close_code:'',expected_city:batch.city,expected_profile_key:batch.profile,created_at:new Date(now()).toISOString(),timeout_at:new Date(now()+60000).toISOString()};
    if(!toaBridge.queueDisconnectLookup(job))throw new Error('TOA: consulta de leitura não aceita');
    const deadline=now()+60000;
    while(now()<deadline){const result=toaBridge.getDisconnectLookupResult(id);if(result){if(result.ok&&result.snapshot)return result.snapshot;if(['toa_sem_resultados','no_results','toa_activity_not_found'].includes(result.reason))return null;throw new Error('TOA: '+String(result.reason||'evidência incompleta'));}await sleep(750);}
    throw new Error('TOA: consulta excedeu 60 segundos');
  }
  async function prepareBatch(batch){
    const errors=[];let snapshot=null,imperium=null;
    if(!batch.demo){
      try{snapshot=await queryTOA(batch);}catch(e){if(['409','512','706'].includes(batch.requested_code))errors.push(e.message);}
      try{if(!verifyImperium)throw new Error('Imperium: consulta independente ainda não configurada');imperium=await verifyImperium(batch,snapshot);}catch(e){errors.push(e.message);}
    }
    return store.prepare(batch.id,snapshot,errors,imperium);
  }
  async function scan(){if(busy)return;busy=true;try{for(const b of store.list().filter(x=>x.state==='buffering'&&x.deadline<=now()&&!pendingSenders.get(x.group+'|'+x.sender)).slice(0,8)){const selected=store.markProcessing(b.id);if(selected)await prepareBatch(selected);}status.last_scan=now();status.last_error='';}catch(e){status.last_error=e.message;}finally{busy=false;persistStatus();}}
  const timer=autoStart?setInterval(()=>void scan(),5000):null;timer?.unref();
  function json(res,code,payload,headers={}){res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...headers});res.end(JSON.stringify(payload));}
  async function body(req){let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>65536)throw new Error('Payload maior que 64 KB');}return raw?JSON.parse(raw):{};}
  function authenticated(req){const cookie=String(req.headers.cookie||'').split(';').find(x=>x.trim().startsWith('desc_review='))?.trim().slice('desc_review='.length);const session=sessions.get(cookie);if(!session||session.expires<now())return null;return session;}
  function sameOrigin(req){const origin=req.headers.origin;if(!origin)return true;try{return new URL(origin).host===req.headers.host;}catch{return false;}}
  function servePage(res){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",'X-Content-Type-Options':'nosniff'});res.end(fs.readFileSync(path.join(__dirname,'index.html')));}
  function createDemo(kind){
    const group=Object.keys(groups)[0],sender='demo-'+crypto.randomUUID();technicians[sender]={name:'TÉCNICO DEMONSTRAÇÃO',imperium_id:'999999',toa_login:'DEMO'};
    const raw={serial_consultado:'DEMO123456789',serial_baixavel:'DEMO123456789',enderecaveis_negrito:['DEMO123456789'],modelo_equipamento:'DECODER',historico:[...(kind==='400'?[{tipo_localizacao:'VIA EMBRATEL'}]:[]),{numero_contrato:'9999999',data_alteracao:'DEMONSTRAÇÃO',estado:'ATIVO',tipo_localizacao:'CLIENTE'}]};
    if(kind==='blocked')raw.enderecaveis_negrito.push('OUTRO123456789');
    const b=store.ingest({id:crypto.randomUUID(),group,sender,contract:'9999999',text:'Amostra sintética; não é uma OS real',atlas:[raw],demo:true});
    let snapshot=null;
    if(['409','512','706'].includes(kind))snapshot={contract:'9999999',activity_id:'DEMONSTRAÇÃO',activity_status:'completed',technician_external_id:'DEMO',materials_complete:true,tasks:[{os_number:'9999999999',close_code:kind,service:'OS fictícia de demonstração'}],installed_equipments:kind==='512'?[]:[{serial:'INST123456789',equipment_type:kind==='706'?'CHIP':'DECODER',pool:'install'}],removed_equipments:kind==='512'?[]:[{serial:'DEMO123456789',equipment_type:'DECODER',pool:'deinstall'}],materials:kind==='512'?[{code:'DEMO',description:'CONTROLE REMOTO',quantity:1}]:[]};
    return store.prepare(b.id,snapshot);
  }
  function report(month){
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month))throw new Error('Mês inválido');
    const XLSX=require('xlsx'),workbook=XLSX.utils.book_new(),daily=new Map(),summary=new Map();
    for(const b of store.list().filter(x=>!x.demo&&day(x.created_at).startsWith(month))){const date=day(b.created_at);if(!daily.has(date))daily.set(date,[]);for(const o of b.plan?.operations || [{code:'',os:null,incoming:[],outgoing:[],reason:(b.capture_errors||[]).join('; ')}]){daily.get(date).push({Modo:'TESTE',Data:date,Técnico:b.technician.name,Recurso:b.technician.imperium_id||'',Contrato:b.contract,OS:o.os||'PROPOSTA DE CRIAÇÃO',Código:o.code,Entrando:o.incoming.map(x=>x.serial).join(', '),Saindo:o.outgoing.map(x=>x.serial).join(', '),Situação:b.state,Motivo:o.reason,Aprovador:b.decision?.actor||'',Hora:new Date(b.created_at).toLocaleString('pt-BR',{timeZone:'America/Fortaleza'})});if(o.code==='400')summary.set(b.sender,{Técnico:b.technician.name,Correções:(summary.get(b.sender)?.Correções||0)+1});}}
    XLSX.utils.book_append_sheet(workbook,XLSX.utils.json_to_sheet([...summary.values()]),'Consolidado');
    const [year,m]=month.split('-').map(Number);const days=new Date(year,m,0).getDate();for(let d=1;d<=days;d++){const date=month+'-'+String(d).padStart(2,'0');XLSX.utils.book_append_sheet(workbook,XLSX.utils.json_to_sheet(daily.get(date)||[{Modo:'TESTE',Data:date,Situação:'Sem registros'}]),date);}
    return XLSX.write(workbook,{type:'buffer',bookType:'xlsx'});
  }
  async function handleRequest(req,res){const url=new URL(req.url,'http://localhost');if(!url.pathname.startsWith(PREFIX))return false;try{
    if(req.method==='GET'&&[PREFIX,PREFIX+'/'].includes(url.pathname)){servePage(res);return true;}
    if(req.method==='POST'&&!sameOrigin(req)){json(res,403,{error:'Origem não autorizada'});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/session'){
      const addr=req.socket.remoteAddress,record=attempts.get(addr)||{count:0,start:now()};if(now()-record.start>15*60000){record.count=0;record.start=now();}if(record.count>=8){json(res,429,{error:'Muitas tentativas; aguarde 15 minutos'});return true;}
      const data=await body(req);const h=crypto.createHash('sha256').update(String(data.pin||'')).digest();if(!crypto.timingSafeEqual(h,pinHash)){record.count++;attempts.set(addr,record);json(res,401,{error:'Código de acesso inválido'});return true;}
      attempts.delete(addr);const id=crypto.randomBytes(32).toString('hex'),csrf=crypto.randomBytes(24).toString('hex');sessions.set(id,{expires:now()+8*3600000,csrf,actor:'Dalton'});json(res,200,{ok:true,csrf},{'Set-Cookie':`desc_review=${id}; HttpOnly; SameSite=Strict; Path=${PREFIX}; Max-Age=28800`});return true;
    }
    const session=authenticated(req);if(!session){json(res,401,{error:'Entre com o código de acesso'});return true;}
    if(req.method==='POST'&&req.headers['x-review-csrf']!==session.csrf){json(res,403,{error:'Sessão de revisão inválida'});return true;}
    if(req.method==='GET'&&url.pathname===PREFIX+'/state'){json(res,200,{...status,csrf:session.csrf,batches:store.list().slice(-300).reverse(),technicians,groups,atlas:toaBridge?.getAtlasStatus(),toa:toaBridge?.getExtensionStatus()});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/decision'){const d=await body(req);json(res,200,{ok:true,batch:store.decide(d.id,d.action,d.revision,d.actor||session.actor,d.note)});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/technician'){const d=await body(req);store.updateTechnician(d.sender,d);const temp=mappingFile+'.tmp';fs.writeFileSync(temp,JSON.stringify(technicians,null,2),{mode:0o600});fs.renameSync(temp,mappingFile);json(res,200,{ok:true});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/demo'){const d=await body(req);if(!['430','400','409','512','706','blocked'].includes(d.kind))throw new Error('Amostra inválida');json(res,200,{ok:true,batch:createDemo(d.kind)});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/manual'){const d=await body(req);if(!groups[d.group]||!technicians[d.sender]||!/^\d{7}$/.test(String(d.contract)))throw new Error('Selecione grupo, técnico e contrato de 7 dígitos');const candidates=String(d.serials||'').split(/[\s,;]+/).map(serial).filter(Boolean);if(candidates.length>12)throw new Error('Informe no máximo 12 seriais');let entries=[];if(candidates.length){const result=await lookupSerials(candidates);entries=result?.resultadosAtlas||(result?.retorno?.resultado?[{resultado:result.retorno.resultado}]:[]);if(!entries.length)throw new Error('Atlas não confirmou os seriais');}const b=store.ingest({id:'manual-'+crypto.randomUUID(),group:d.group,sender:d.sender,contract:d.contract,text:'Teste manual informado por '+(d.actor||session.actor),atlas:entries,requested_code:String(d.code||'')});json(res,200,{ok:true,batch:b});return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/refresh'){
      const d=await body(req),b=store.get(d.id);
      if(['simulated','rejected','processing'].includes(b.state)||now()<b.deadline)throw new Error('Lote decidido, em consulta ou com janela aberta');
      const candidates=[...new Set(b.atlas.map(e=>serial((e.resultado||e).serial_consultado||e.serialSolicitado)).filter(Boolean))];
      let entries=[],retryErrors=[];const readings={},photos=b.messages.filter(m=>m.photo);
      if(photos.length){for(const photo of photos){
        const result=await lookupPhoto(fs.readFileSync(path.join(directory,'photos',photo.photo)));
        if(result?.photoReading)readings[photo.photo]=result.photoReading;
        const found=result?.resultadosAtlas||(result?.retorno?.resultado?[{resultado:result.retorno.resultado}]:[]);
        if(!found.length||result?.photoReading&&result.photoReading.stage!=='confirmed')retryErrors.push('Foto: '+(result?.photoReading?.message||'Atlas/OCR ainda sem resultado confirmado'));
        entries.push(...found);
      }}else if(candidates.length){const result=await lookupSerials(candidates);entries=result?.resultadosAtlas||(result?.retorno?.resultado?[{resultado:result.retorno.resultado}]:[]);if(!entries.length)retryErrors.push('Atlas sem retorno confirmado');}
      store.replaceEvidence(b.id,entries,retryErrors,readings);json(res,200,{ok:true});void scan();return true;
    }
    if(req.method==='GET'&&url.pathname===PREFIX+'/report.xlsx'){const month=url.searchParams.get('month')||day(now()).slice(0,7);const buffer=report(month);res.writeHead(200,{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Content-Disposition':`attachment; filename="DESC_TESTE_${month}.xlsx"`,'Cache-Control':'no-store'});res.end(buffer);return true;}
    if(req.method==='GET'&&url.pathname.startsWith(PREFIX+'/photo/')){const name=url.pathname.slice((PREFIX+'/photo/').length);if(!/^[a-f0-9-]{36}\.jpg$/.test(name)||!store.list().some(b=>b.messages.some(m=>m.photo===name)))throw new Error('Foto não encontrada');res.writeHead(200,{'Content-Type':'image/jpeg','Cache-Control':'no-store'});res.end(fs.readFileSync(path.join(directory,'photos',name)));return true;}
    json(res,404,{error:'Rota não disponível no modo de teste'});return true;
  }catch(e){if(!res.headersSent)json(res,400,{error:e.message});else res.end();return true;}}
  return {handleRequest,captureMessage,capturePhoto,isTestGroup:store.isTestGroup,store,status,scan,stop:()=>clearInterval(timer)};
}
module.exports={createDescReview};
