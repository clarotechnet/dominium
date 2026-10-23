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
  function element(id){
    if(!elements.has(id)) elements.set(id,{
      id, value:'', textContent:'', dataset:{}, disabled:false, children:[],
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
    'atlasQueryStatus','atlasQueryId','atlasQueryGrid','atlasQueryProgress',
    'atlasQueryPage','atlasQueryPrev','atlasQueryNext','atlasQueryCsv',
    'atlasQueryXlsx','atlasQueryRefresh','atlasQuerySummary','atlasQueryActivity'
  ].forEach(element);
  element('atlasQueryLocation').value='empreiteira';
  const document={
    getElementById:element,
    createElement:tag=>({tag,textContent:'',children:[],append(){},className:''}),
    addEventListener(){}
  };
  let interval;
  const state={profile:'mossoro',activeModule:'inactive',authUser:{role:'admin'}};
  const calls=[];
  const ctx={document,state,window:{},setInterval(fn){interval=fn},
    request: async(url,opts)=>{calls.push({url,method:opts?.method||'GET'});return response(url,opts)},
    requestBlob:async()=>({blob:new Blob([])}),
    saveBlob:()=>{},localDate:()=>'',switchProfile:async()=>{}};
  vm.runInNewContext(uiCode,ctx,{filename:'atlas-query-ui.js'});
  return {elements,element,listeners,calls,state,interval:()=>interval()};
}

test('dashboard includes visible permanent activity log',()=>{
  assert.match(html,/id="atlasQueryActivity"/);
  assert.match(html,/Histórico desta sessão/);
  assert.match(html,/atlas-query-ui\.js\?v=20261023-2/);
});

test('successful POST leaves durable confirmation after automatic refresh',async()=>{
  const id='a'.repeat(32);
  const job={id,city:'mossoro',location:'empreiteira',
             state:'queued',remote_queue_id:'276841868'};
  const {element,listeners,state,interval,calls}=setup(async(url,opts)=>{
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
});

test('HTTP rejection remains visible instead of vanishing after polling',async()=>{
  const {element,listeners,state,interval}=setup(async(url,opts)=>{
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
});
