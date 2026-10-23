'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const uiCode=fs.readFileSync(path.join(__dirname,'../static/atlas-query-ui.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');

function setup(response){
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
    request: async(url,opts)=>{calls.push({url,method:opts?.method||'GET'});return response(url,opts)},
    requestBlob:async()=>({blob:new Blob([])}),
    saveBlob:()=>{},localDate:()=>'',switchProfile:async city=>{state.profile=city}};
  vm.runInNewContext(uiCode,ctx,{filename:'atlas-query-ui.js'});
  return {elements,element,listeners,documentListeners,calls,operations,state,window:ctx.window,interval:()=>interval()};
}

test('dashboard includes visible permanent activity log',()=>{
  assert.match(html,/id="atlasQueryActivity"/);
  assert.match(html,/Histórico desta sessão/);
  assert.match(html,/id="atlasQueryTimestamps"/);
  assert.match(html,/id="atlasQueryReconcile"/);
  assert.match(html,/atlas-query-ui\.js\?v=20261023-7/);
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
