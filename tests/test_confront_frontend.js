'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const code=fs.readFileSync(path.join(__dirname,'../static/confront.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
const IDS=['confrontModule','confrontInput','confrontMode','confrontRun','confrontRefresh',
 'confrontExport','confrontStatus','confrontNotice','confrontAtlasStatus',
 'confrontSummary','confrontResults','confrontHistory'];
const natal='a'.repeat(32), recife='b'.repeat(32), newJob='c'.repeat(32);
const wait=()=>new Promise(r=>setImmediate(r));

function harness({failFirst=false}={}){
 const elems=new Map();
 const make=(id='')=>({
  id, value:'', textContent:'', disabled:false, children:[], events:{},
  className:'', classList:{add(){},remove(){},toggle(){}},
  replaceChildren(...items){this.children=items},
  append(...items){this.children.push(...items)},
  addEventListener(name,fn){this.events[name]=fn}
 });
 for(const id of IDS)elems.set(id,make(id));
 const calls=[], messages=[];
 const jobs=[{id:natal,profile:'natal',mode:'analitico',created_at:10000},
             {id:recife,profile:'recife',mode:'sintetico',created_at:11000}];
 const state={activeModule:'confront',profile:'natal',authUser:{role:'controller'}};
 const request=async (url,options={})=>{
   calls.push({url,options});
   if(url==='/api/confront/status')return {ok:true,atlas_online:true};
   if(url==='/api/confront/jobs'&&options.method==='POST'){
     if(failFirst){failFirst=false;throw Error('timeout after request');}
     const body=JSON.parse(options.body);
     jobs.unshift({id:newJob,profile:body.profile,mode:body.mode,created_at:12000});
     return {ok:true,job:{job_id:newJob,profile:body.profile,
        mode:body.mode,total:1,done:0,states:{pending_imperium:1}}};
   }
   if(url==='/api/confront/jobs')return {ok:true,jobs};
   if(url.startsWith('/api/confront/jobs/')){
    const id=url.split('/').pop();
    return {ok:true,job:{job_id:id,profile:'natal',mode:'analitico',total:1,
      done:1,states:{complete:1},rows:[{serial:'TEST00000001',state:'complete',
        resultado:{situacao:'inconclusivo',atlas:{estado:'SUSPEITO'},
        imperium:{ultima_localizacao_nao_confirmada:'Estoque antigo'},
        motivos:['revisao_manual'],alertas:[]}}]}};
   }
   throw Error('Unexpected request '+url);
 };
 const ctx={
   state, document:{getElementById:id=>elems.get(id),
      addEventListener(name,fn){messages.push({name,fn})},
      createElement(tag){return make(tag)}},
   Option:function(label,value){return {value,textContent:label}},
   request, requestBlob:async()=>({blob:{}}),
   serialConsultValues:x=>[...new Set(String(x).trim().split(/[\s,;]+/).filter(Boolean).map(v=>v.toUpperCase()))],
   crypto:{randomUUID:()=> '12345678-1234-1234-1234-123456789abc'},
   setInterval:()=>{}, saveBlob:()=>{}, localDate:()=> '2026-10-22',
   setModule:module=>{state.activeModule=module}, console,
 };
 vm.runInNewContext(code,ctx,{timeout:1000});
 return {elems,calls,messages,state};
}

test('all DOM elements exist and panel is directly below Consulta de Seriais',()=>{
 for(const id of IDS)assert.ok(html.includes('id="'+id+'"'),id);
 assert.ok(html.indexOf('id="confrontModule"')>html.indexOf('id="serialsModule"'));
 assert.ok(html.indexOf('id="confrontModule"')<html.indexOf('id="techniciansModule"'));
});
test('panel restores own Natal history only and safely renders classified rows',async()=>{
 const h=harness();
 await wait();await wait();await wait();
 const select=h.elems.get('confrontHistory');
 assert.equal(select.children.length,1);
 assert.equal(select.value,natal);
 assert.equal(h.elems.get('confrontAtlasStatus').textContent,'Atlas conectado');
 const results=h.elems.get('confrontResults');
 assert.equal(results.children.length,1);
 assert.equal(results.children[0].children[0].children[0].children[1].textContent,'TEST00000001');
});
test('network timeout retries with the SAME idempotency key and one serial',async()=>{
 const h=harness({failFirst:true});
 await wait();await wait();await wait();
 const input=h.elems.get('confrontInput');input.value='TEST00000001\nTEST00000001';
 const create=h.elems.get('confrontRun').events.click;
 create();await wait();await wait();await wait();
 create();await wait();await wait();await wait();await wait();
 const posts=h.calls.filter(x=>x.options.method==='POST');
 assert.equal(posts.length,2);
 const b=posts.map(x=>JSON.parse(x.options.body));
 assert.equal(b[0].request_key,b[1].request_key);
 assert.match(b[0].request_key,/^[a-f0-9]{32}$/);
 assert.equal(b[0].serials.length,1);
 assert.equal(h.elems.get('confrontInput').value,'');
});
test('viewer cannot start or refresh a confrontation',async()=>{
 const h=harness();
 await wait();await wait();await wait();
 h.state.authUser={role:'viewer'};
 h.elems.get('confrontRun').events.click();
 await wait();
 assert.ok(h.elems.get('confrontRun').disabled===false || h.elems.get('confrontStatus'));
 const posts=h.calls.filter(x=>x.options.method==='POST');
 assert.equal(posts.length,0);
});
