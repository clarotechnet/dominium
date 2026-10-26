'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const uiCode=fs.readFileSync(path.join(__dirname,'../static/atlas-query-ui.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');

function setup(response,now){
  const elements=new Map();
  const listeners=new Map();
  const documentListeners=new Map();
  function element(id){
    if(!elements.has(id)) elements.set(id,{
      id, value:'', textContent:'', dataset:{}, style:{}, disabled:false, children:[],
      addEventListener(type,fn){listeners.set(id+':'+type,fn)},
      prepend(node){this.children.unshift(node)},
      get lastElementChild(){return this.children[this.children.length-1]},
      remove(){},
      replaceChildren(...items){this.children=items},
      get firstChild(){return this.children[0]},
      append(){},focus(){}
    });
    return elements.get(id);
  }
  [
    'atlasQueryCity','atlasQueryLocation','atlasQueryStart',
    'atlasQueryStatus','atlasQueryId','atlasQueryTimestamps','atlasQueryGrid','atlasQueryProgress',
    'atlasQueryPage','atlasQueryPrev','atlasQueryNext','atlasQueryCsv',
    'atlasQueryXlsx','atlasQueryRefresh','atlasQueryReconcile',
    'atlasQuerySummary','atlasQueryActivity'
  ].forEach(element);
  element('atlasQueryLocation').value='empreiteira';
  const document={
    getElementById:element,
    createElement:tag=>({tag,textContent:'',children:[],append(){},className:''}),
    addEventListener(type,fn){documentListeners.set(type,fn)}
  };
  let interval;
  const state={profile:'mossoro',activeModule:'inactive',authReady:true,authUser:{role:'admin'}};
  const calls=[];
  const operations=[];
  const ctx={document,state,window:{confirm:()=>true,DOMINIUM_MOTION:{operation(payload){operations.push(payload)}}},setInterval(fn){interval=fn},
    request: async(url,opts)=>{calls.push({url,method:opts?.method||'GET',body:opts?.body});return response(url,opts)},
    requestBlob:async()=>({blob:new Blob([])}),
    saveBlob:()=>{},localDate:()=>'',switchProfile:async city=>{state.profile=city}};
  if(now!==undefined)ctx.Date=class extends Date {static now(){return now}};
  vm.runInNewContext(uiCode,ctx,{filename:'atlas-query-ui.js'});
  return {elements,element,listeners,documentListeners,calls,operations,state,window:ctx.window,interval:()=>interval()};
}

test('dashboard includes visible permanent activity log',()=>{
  assert.match(html,/id="atlasQueryActivity"/);
  assert.match(html,/Histórico desta sessão/);
  assert.match(html,/id="atlasQueryTimestamps"/);
  assert.match(html,/id="atlasQueryReconcile"/);
  assert.match(html,/atlas-query-ui\.js\?v=20261026-4/);
});

test('old completed family permits one explicit generation without automatic POST',async()=>{
  const old=(Date.now()-9*3600*1000)/1000;
  const primary={id:'7'.repeat(32),city:'fortaleza',state:'attachment_wait',
    error_code:'attachment_http_404',remote_queue_id:'276868465',created_at:old,fallback_of:''};
  const reserve={...primary,id:'8'.repeat(32),remote_queue_id:'276868467',fallback_of:primary.id};
  const next={id:'9'.repeat(32),city:'fortaleza',state:'submission_uncertain',remote_queue_id:null};
  const {element,state,interval,listeners,calls}=setup(async(url,opts)=>{
    if(opts?.method==='POST')return {job:next,reused:false};
    if(url.endsWith(reserve.id))return {job:reserve};
    return {jobs:[reserve,primary]};
  });
  state.profile='fortaleza';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryStart').disabled,false);
  interval();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
  listeners.get('atlasQueryStart:click')();
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,1);
  assert.equal(element('atlasQueryStart').disabled,true);
});

test('repeated 404 on both confirmed IDs permits one linked explicit recovery before eight hours',async()=>{
  const primary={id:'7'.repeat(32),city:'natal',state:'attachment_wait',
    error_code:'attachment_http_404',remote_queue_id:'276907780',
    created_at:Date.now()/1000-300,attachment_failures:2,fallback_of:''};
  const reserve={...primary,id:'8'.repeat(32),remote_queue_id:'276907783',fallback_of:primary.id};
  const next={id:'9'.repeat(32),city:'natal',state:'submission_uncertain',remote_queue_id:null};
  const {element,state,interval,listeners,calls}=setup(async(url,opts)=>{
    if(opts?.method==='POST')return {job:next};
    return url.endsWith(reserve.id)?{job:reserve}:{jobs:[reserve,primary]};
  });
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryStart').disabled,false);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
  listeners.get('atlasQueryStart:click')();listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  const posts=calls.filter(c=>c.method==='POST');
  assert.equal(posts.length,1);
  assert.deepEqual(JSON.parse(posts[0].body),{city:'natal',location:'empreiteira',retry_job_id:primary.id});
});

for(const [label,override] of [
  ['recent family',{created_at:Date.now()/1000-3600}],
  ['missing ID',{remote_queue_id:null}],
  ['uncertain submission',{state:'submission_uncertain',error_code:'atlas_submit_unconfirmed'}],
  ['processing queue',{state:'processing'}],
  ['transport timeout',{error_code:'attachment_transport_timeout'}],
  ['missing timestamp',{created_at:null}],
])test('recovery keeps '+label+' blocked even when a click handler is invoked',async()=>{
  const job={id:'6'.repeat(32),city:'fortaleza',state:'attachment_wait',
    remote_queue_id:'276868465',created_at:Date.now()/1000-9*3600,
    error_code:'attachment_http_404',fallback_of:'',...override};
  const {element,state,interval,listeners,calls}=setup(async url=>
    url.endsWith(job.id)?{job}:{jobs:[job]});
  state.profile='fortaleza';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryStart').disabled,true);
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

test('recent reserve keeps an old completed primary blocked',async()=>{
  const primary={id:'7'.repeat(32),city:'fortaleza',state:'attachment_wait',
    remote_queue_id:'276868465',created_at:Date.now()/1000-9*3600,fallback_of:'',
    error_code:'attachment_http_404'};
  const reserve={...primary,id:'8'.repeat(32),remote_queue_id:'276868467',
    created_at:Date.now()/1000-60,fallback_of:primary.id};
  const {element,state,interval,listeners,calls}=setup(async url=>
    url.endsWith(reserve.id)?{job:reserve}:{jobs:[reserve,primary]});
  state.profile='fortaleza';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryStart').disabled,true);
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

for(const [label,stateValue,error,created,wantDisabled] of [
  ['eight-hour boundary','attachment_wait','attachment_http_404',1999971200,false],
  ['inside reuse window','attachment_wait','attachment_http_404',1999971201,true],
  ['missing attachment','attachment_missing','attachment_not_listed',1999970000,false],
  ['auth warning on confirmed completed queue','attachment_wait','atlas_auth_required',1999970000,false],
])test('explicit recovery handles '+label,async()=>{
  const job={id:'5'.repeat(32),city:'fortaleza',state:stateValue,error_code:error,
    remote_queue_id:'276868465',created_at:created,fallback_of:''};
  const {element,state,interval,calls}=setup(async url=>
    url.endsWith(job.id)?{job}:{jobs:[job]},2000000000000);
  state.profile='fortaleza';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryStart').disabled,wantDisabled);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

test('successful POST leaves durable confirmation after automatic refresh',async()=>{
  const id='a'.repeat(32);
  const job={id,city:'mossoro',location:'empreiteira',
             state:'queued',remote_queue_id:'276841868'};
  const {element,listeners,state,interval,calls,operations}=setup(async(url,opts)=>{
    if(opts?.method==='POST')return {job};
    if(url.includes('/'+id))return {job};
    return {jobs:[job]};
  });
  await listeners.get('atlasQueryStart:click')();
  // Listener triggers fire-and-forget async create; flush microtasks.
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryStatus').textContent,/O servidor registrou a solicitação/);
  assert.equal(element('atlasQueryId').textContent,'Fila Atlas: 276841868');
  state.activeModule='confront';
  interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryStatus').textContent,/O servidor registrou a solicitação/);
  assert.ok(element('atlasQueryActivity').children.length>=1);
  assert.equal(calls.filter(x=>x.method==='POST').length,1);
  assert.ok(operations.some(x=>x.phase==='searching'&&x.label==='Gerando QUERY no Atlas'));
  assert.ok(operations.some(x=>x.phase==='working'&&x.label==='Consultando fila da QUERY'));
});

test('HTTP rejection remains visible instead of vanishing after polling',async()=>{
  const {element,listeners,state,interval,operations}=setup(async(url,opts)=>{
    if(opts?.method==='POST'){
      const e=new Error('Perfil operacional necessário');e.status=403;throw e;
    }
    return {jobs:[]};
  });
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryStatus').textContent,/Falha ao solicitar QUERY.*Perfil operacional necessário/);
  state.activeModule='confront';
  interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryActivity').children[0].textContent,/Falha ao solicitar QUERY/);
  assert.ok(operations.some(x=>x.phase==='error'&&x.label==='Falha ao gerar QUERY'));
});


test('complete QUERY animates green success only after ready state',async()=>{
  const id='b'.repeat(32);
  const job={id,city:'mossoro',location:'empreiteira',
             state:'ready',remote_queue_id:'276841868'};
  const {operations,listeners}=setup(async(url,options)=>{
    if(options?.method==='POST')return {job};
    return {jobs:[job]};
  });
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(operations.some(x=>x.phase==='success'&&x.label==='QUERY pronta'));
});


test('unconfirmed Atlas submit terminates the animation and automatic polling without retry',async()=>{
  const id='c'.repeat(32);
  const job={id,city:'mossoro',location:'empreiteira',state:'submission_uncertain',
    error_code:'atlas_submit_unconfirmed',remote_queue_id:null};
  const {element,listeners,state,interval,calls,operations}=setup(async(url,opts)=>{
    if(opts?.method==='POST')return {job};
    if(url.includes('/'+id))return {job};
    return {jobs:[job]};
  });
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryProgress').textContent,/Confirmação do Atlas não obtida/);
  assert.equal(element('atlasQueryStart').disabled,true);
  assert.ok(operations.some(x=>x.phase==='error'&&x.label==='Envio Atlas não confirmado'));
  const before=calls.length;
  state.activeModule='confront';
  interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,before,'no continuing background requests');
  assert.equal(calls.filter(x=>x.method==='POST').length,1,'never re-submit QUERY');
});


test('expired NetTask session stops spinner and keeps confirmed queue ID',async()=>{
  const id='d'.repeat(32);
  const job={id,city:'mossoro',location:'empreiteira',state:'queued',
    error_code:'atlas_auth_required',remote_queue_id:'276850938'};
  const {element,listeners,state,interval,calls,operations}=setup(async(url,opts)=>{
    if(opts?.method==='POST')return {job};
    if(url.includes('/'+id))return {job};
    return {jobs:[job]};
  });
  listeners.get('atlasQueryStart:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryProgress').textContent,/Sessão Atlas expirada/);
  assert.match(element('atlasQueryId').textContent,/276850938/);
  assert.equal(element('atlasQueryStart').disabled,true);
  assert.ok(operations.some(x=>x.phase==='error'&&x.label==='Sessão Atlas expirada'));
  const before=calls.length;
  state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,before);
  assert.equal(calls.filter(x=>x.method==='POST').length,1);
});

test('queue lookup displays full date and time and follows a confirmed reserve',async()=>{
  const original={id:'1'.repeat(32),city:'mossoro',location:'empreiteira',
      state:'attachment_wait',remote_queue_id:'276850938',error_code:'attachment_http_404',
      fallback_of:'',created_at:1792800000,updated_at:1792800300};
  const reserve={id:'2'.repeat(32),city:'mossoro',location:'empreiteira',
      state:'queued',remote_queue_id:'276855582',fallback_of:original.id,
      created_at:1792800500,updated_at:1792800600};
  const {element,state,interval}=setup(async(url)=>{
    if(url.endsWith(reserve.id))return {job:reserve};
    return {jobs:[reserve,original]};
  });
  state.activeModule='confront';
  interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryId').textContent,/Principal: 276850938.*Reserva: 276855582/);
  assert.match(element('atlasQueryTimestamps').textContent,/Principal solicitada: \d{2}\/\d{2}\/\d{4}/);
  assert.match(element('atlasQueryTimestamps').textContent,/Reserva solicitada: \d{2}\/\d{2}\/\d{4}/);
  assert.match(element('atlasQueryTimestamps').textContent,/Consultada: \d{2}\/\d{2}\/\d{4}/);
  assert.match(element('atlasQueryTimestamps').textContent,/\d{2}:\d{2}:\d{2}/);
  assert.match(element('atlasQueryProgress').textContent,/ID recebido/);
});

test('ready principal wins over pending reserve and preserves ready report',async()=>{
  const primary={id:'3'.repeat(32),city:'mossoro',location:'empreiteira',
      state:'ready',remote_queue_id:'276855590',fallback_of:'',
      created_at:1792800000,updated_at:1792800100};
  const reserve={id:'4'.repeat(32),city:'mossoro',location:'empreiteira',
      state:'queued',remote_queue_id:'276855591',fallback_of:primary.id};
  const {element,state,interval}=setup(async(url)=>{
    if(url.includes('/rows/'))return {total:0,rows:[],columns:[]};
    if(url.endsWith(primary.id))return {job:primary};
    return {jobs:[reserve,primary]};
  });
  state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryId').textContent,/Principal: 276855590.*Reserva: 276855591/);
  assert.match(element('atlasQueryProgress').textContent,/QUERY disponível/);
  assert.equal(element('atlasQueryCsv').disabled,false);
});

test('Natal old unconfirmed shows reconciliation without a new Atlas POST',async()=>{
  const id='f'.repeat(32);
  const stale={id,city:'natal',location:'empreiteira',
    state:'submission_uncertain',error_code:'atlas_submit_unconfirmed',
    created_at:1792760000,updated_at:1792760400,remote_queue_id:null};
  const closed={...stale,state:'failed',error_code:'manually_closed_unconfirmed'};
  const {state,element,listeners,interval,calls}=setup(async(url,opts)=>{
    if(url==='/api/atlas-query/jobs'&&opts?.method==='POST'&&
       JSON.parse(opts.body||'{}').reconcile_job_id===id)return {job:closed};
    if(url.includes('/'+id))return {job:stale};
    return {jobs:[stale]};
  });
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryReconcile').hidden,false);
  assert.equal(element('atlasQueryStart').disabled,true);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
  listeners.get('atlasQueryReconcile:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,1);
  assert.ok(calls.some(c=>c.method==='POST'&&c.url==='/api/atlas-query/jobs'));
  assert.equal(element('atlasQueryStart').disabled,false);
  assert.equal(element('atlasQueryReconcile').hidden,true);
  assert.match(element('atlasQueryProgress').textContent,/Tentativa antiga encerrada/);
});

test('operator cancellation leaves stale submission untouched',async()=>{
  const id='e'.repeat(32);
  const stale={id,city:'natal',location:'empreiteira',state:'submission_uncertain',
    error_code:'atlas_submit_unconfirmed',remote_queue_id:null};
  const {window,state,listeners,interval,calls}=setup(async(url)=>{
    if(url.includes('/'+id))return {job:stale};
    return {jobs:[stale]};
  });
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  window.confirm=()=>false;
  listeners.get('atlasQueryReconcile:click')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

test('switching cities mid-request never displays a previous city report',async()=>{
  const natal={id:'a'.repeat(32),city:'natal',state:'submission_uncertain',
      error_code:'atlas_submit_unconfirmed',remote_queue_id:null};
  const fortaleza={id:'b'.repeat(32),city:'fortaleza',state:'queued',
      remote_queue_id:'276888001',error_code:''};
  let releaseFirst;
  let reads=0;
  const {state,element,listeners,interval,calls}=setup(async url=>{
    if(url==='/api/atlas-query/jobs'){
      reads++;
      if(reads===1)return new Promise(resolve=>{releaseFirst=resolve});
      return {jobs:[natal,fortaleza]};
    }
    if(url.includes(fortaleza.id))return {job:fortaleza};
    if(url.includes(natal.id))return {job:natal};
    throw Error('unexpected endpoint '+url);
  });
  state.profile='natal';state.activeModule='confront';interval();
  assert.equal(typeof releaseFirst,'function');
  element('atlasQueryCity').value='fortaleza';
  await listeners.get('atlasQueryCity:change')();
  assert.equal(element('atlasQueryId').textContent,'Nenhuma fila criada');
  releaseFirst({jobs:[natal,fortaleza]});
  await new Promise(resolve=>setImmediate(resolve));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(element('atlasQueryId').textContent,'Fila Atlas: 276888001');
  assert.doesNotMatch(element('atlasQueryProgress').textContent,/Confirmação do Atlas não obtida/);
  assert.equal(calls.filter(x=>x.method==='POST').length,0);
});

test('temporary missing auth shows session validation rather than forbidden role',async()=>{
  const {state,element,listeners}=setup(async()=>({jobs:[]}));
  state.authUser=null;state.authReady=false;
  element('atlasQueryCity').value='mossoro';
  await listeners.get('atlasQueryCity:change')();
  assert.match(element('atlasQueryProgress').textContent,/Validando sessão/);
  assert.doesNotMatch(element('atlasQueryProgress').textContent,/exige perfil administrador/);
  assert.equal(element('atlasQueryStart').disabled,true);
});

test('activity records display the city to avoid mixing Natal and Fortaleza',async()=>{
  const {state,element,listeners}=setup(async()=>({jobs:[]}));
  state.activeModule='confront';
  element('atlasQueryCity').value='natal';
  await listeners.get('atlasQueryCity:change')();
  assert.match(element('atlasQueryActivity').children[0].textContent,/\[NATAL\]/);
  element('atlasQueryCity').value='fortaleza';
  await listeners.get('atlasQueryCity:change')();
  assert.match(element('atlasQueryActivity').children[0].textContent,/\[FORTALEZA\]/);
  assert.equal(element('atlasQueryActivity').children.some(x=>x.textContent.includes('[NATAL]')),true);
});

test('BatAtlas transport timeout shows recoverable warning without second submission',async()=>{
  const job={id:'8'.repeat(32),city:'recife',location:'empreiteira',
    state:'attachment_wait',error_code:'attachment_transport_timeout',
    attachment_failures:0,remote_queue_id:'276861849',
    created_at:1792843000,updated_at:1792843100};
  const {element,state,interval,calls,operations}=setup(async(url)=>{
    if(url.endsWith('/'+job.id))return {job};
    return {jobs:[job]};
  });
  state.profile='recife';state.activeModule='confront';
  interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(element('atlasQueryProgress').textContent,/A consulta do anexo expirou/);
  assert.equal(element('atlasQueryStart').disabled,true);
  assert.match(element('atlasQueryId').textContent,/276861849/);
  assert.ok(operations.some(x=>x.label==='Servidor de arquivos demorando'&&x.phase==='waiting'));
  assert.equal(calls.filter(x=>x.method==='POST').length,0);
});

test('timer reserve stays observable and a failed principal cannot unlock another pair',async()=>{
  const primary={id:'a'.repeat(32),city:'natal',state:'failed',error_code:'remote_queue_failed',
    remote_queue_id:'276930001',fallback_of:'',fallback_enabled:1,
    fallback_delay_seconds:45,fallback_due_at:Date.now()/1000+30};
  const reserve={...primary,id:'b'.repeat(32),state:'processing',error_code:'',
    remote_queue_id:'276930002',fallback_of:primary.id,fallback_delay_seconds:0};
  let jobs=[primary];
  const {element,state,interval,calls}=setup(async url=>
    url.endsWith(primary.id)?{job:primary}:url.endsWith(reserve.id)?{job:reserve}:{jobs});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(r=>setImmediate(r));
  assert.equal(element('atlasQueryStart').disabled,true);
  assert.match(element('atlasQueryProgress').textContent,/reserva|45/i);
  jobs=[reserve,primary];interval();await new Promise(r=>setImmediate(r));
  assert.match(element('atlasQueryId').textContent,/276930002/);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

test('ready report explicitly requests a new linked cycle instead of reusing old ready',async()=>{
  const primary={id:'a'.repeat(32),city:'natal',state:'ready',remote_queue_id:'276930001',fallback_of:''};
  const {state,interval,listeners,calls}=setup(async(url,opts)=>
    opts?.method==='POST'?{job:{...primary,id:'b'.repeat(32),state:'submission_uncertain'}}:
    url.includes('/rows/')?{rows:[],columns:[],total:1}:
    url.endsWith(primary.id)?{job:primary}:{jobs:[primary]});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(r=>setImmediate(r));
  listeners.get('atlasQueryStart:click')();await new Promise(r=>setImmediate(r));
  const post=calls.find(c=>c.method==='POST');
  assert.equal(JSON.parse(post.body).refresh_job_id,primary.id);
});

test('failed reserve does not stop observation of a processing principal',async()=>{
  const primary={id:'a'.repeat(32),city:'natal',state:'processing',remote_queue_id:'276930001',fallback_of:''};
  const reserve={...primary,id:'b'.repeat(32),state:'failed',error_code:'remote_queue_failed',
    remote_queue_id:'276930002',fallback_of:primary.id};
  const {state,interval,calls,element}=setup(async url=>
    url.endsWith(primary.id)?{job:primary}:url.endsWith(reserve.id)?{job:reserve}:{jobs:[reserve,primary]});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(r=>setImmediate(r));
  const before=calls.length;
  interval();await new Promise(r=>setImmediate(r));
  assert.ok(calls.length>before);
  assert.equal(element('atlasQueryStart').disabled,true);
});

test('ready principal keeps polling and blocks a new cycle while reserve is pending',async()=>{
  const primary={id:'a'.repeat(32),city:'natal',state:'ready',remote_queue_id:'276930001',fallback_of:'',
    fallback_enabled:1,fallback_delay_seconds:45,fallback_due_at:Date.now()/1000-5};
  const reserve={...primary,id:'b'.repeat(32),state:'submission_uncertain',remote_queue_id:null,
    fallback_of:primary.id,fallback_delay_seconds:0};
  const {state,interval,calls,element}=setup(async url=>url.includes('/rows/')?{rows:[],columns:[],total:1}:
    url.endsWith(primary.id)?{job:primary}:{jobs:[reserve,primary]});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(r=>setImmediate(r));
  const before=calls.length;interval();await new Promise(r=>setImmediate(r));
  assert.ok(calls.length>before);
  assert.equal(element('atlasQueryStart').disabled,true);
});

for(const [label,primary,reserve,enabled] of [
  ['reconciled no-ID timed primary', {state:'failed',error_code:'manually_closed_unconfirmed',remote_queue_id:null},null,true],
  ['ready primary with exhausted 404 reserve',{state:'ready'},
    {state:'attachment_wait',error_code:'attachment_http_404',attachment_failures:2,created_at:Date.now()/1000-300},true],
])test(label+' allows explicit replacement without automatic POST',async()=>{
  const root={id:'a'.repeat(32),city:'natal',remote_queue_id:'276930001',fallback_of:'',
    fallback_enabled:1,fallback_delay_seconds:45,...primary};
  const child=reserve?{...root,id:'b'.repeat(32),fallback_of:root.id,fallback_delay_seconds:0,remote_queue_id:'276930002',...reserve}:null;
  const {state,interval,element,calls}=setup(async url=>url.includes('/rows/')?{rows:[],columns:[],total:1}:
    url.endsWith(root.id)?{job:root}:{jobs:child?[child,root]:[root]});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(r=>setImmediate(r));
  assert.equal(element('atlasQueryStart').disabled,!enabled);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
});

for(const [stateName,error] of [['attachment_wait','attachment_http_404'],['attachment_missing','attachment_not_listed']]){
 test(stateName+' uses a persistent waiting indication without continuous working animation',async()=>{
  const job={id:'1'.repeat(32),city:'natal',state:stateName,error_code:error,
    remote_queue_id:'276935365',fallback_of:'',created_at:Date.now()/1000};
  const {element,state,interval,calls,operations}=setup(async url=>
    url.endsWith(job.id)?{job}:{jobs:[job]});
  state.profile='natal';state.activeModule='confront';interval();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(operations.at(-1).phase,'waiting');
  assert.equal(element('atlasQueryCsv').disabled,true);
  interval();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.filter(x=>x.method==='POST').length,0);
  assert.equal(operations.filter(x=>x.phase==='waiting').length,1);
  assert.ok(calls.filter(x=>x.method==='GET').length>=2);
 });
}

test('shared waiting HUD preserves feedback without a busy heading or animation',()=>{
 const src=fs.readFileSync(path.join(__dirname,'../static/motion-ui.js'),'utf8');
 const cut=src.slice(src.indexOf('function renderOperationState('),src.indexOf('document.addEventListener("dominium:operation-state"'));
 const children=new Map();
 const hud={dataset:{},classList:{add(){},remove(){}},querySelector(s){
  if(!children.has(s))children.set(s,{textContent:''});return children.get(s);
 }};
 const timers=[];
 const context={ensureOperationHud:()=>hud,activeOperationToken:'',operationHudHideTimer:null,
  clearTimeout(){},window:{setTimeout(fn){timers.push(fn)}}};
 vm.runInNewContext(cut+';renderOperationState({token:"query",phase:"waiting",label:"Aguardando arquivo",detail:"ID preservado"})',context);
 assert.equal(hud.dataset.phase,'waiting');
 assert.match(children.get('.operation-orb-eyebrow').textContent,/AGUARDANDO/);
 assert.equal(children.get('.operation-orb-label').textContent,'Aguardando arquivo');
 assert.equal(timers.length,0);
 const css=fs.readFileSync(path.join(__dirname,'../static/styles.css'),'utf8');
 assert.match(css,/data-phase="waiting"[^}]*animation-play-state:\s*paused/s);
});
