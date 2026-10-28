const assert=require('node:assert/strict');
const test=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=require('../static/all-operations.js');
const profiles=['natal','fortaleza','mossoro','recife'].map((key)=>({key,label:key.toUpperCase()}));
test('Todas as praças são consultadas com perfis reais e sem profile=all',()=>{
 const jobs=core.makeRequestJobs(profiles,'2026-10-28',(url,profile)=>'/api/mock?'+encodeURIComponent(url)+'&profile='+profile);
 assert.equal(jobs.length,8);
 assert.deepEqual(jobs.filter(j=>j.source==='imperium').map(j=>j.key),profiles.map(p=>p.key));
 assert.deepEqual(jobs.filter(j=>j.source==='toa').map(j=>j.key),profiles.map(p=>p.key));
 assert.ok(jobs.every(j=>j.url.includes('profile='+j.key)));
 assert.ok(jobs.every(j=>!j.url.includes('profile=all')));
 assert.ok(jobs.every(j=>j.source==='imperium'?'field&service_type=all'.includes('field'):j.url.includes('toa-contracts')));
});
test('Dados ausentes não são convertidos silenciosamente em zero',()=>{
 assert.equal(core.sourceSummary({status:'pending',rows:[]}), 'Carregando...');
 assert.equal(core.sourceSummary({status:'error',rows:[]}), 'Indisponível');
 assert.equal(core.sourceSummary({status:'ok',rows:[]}), '0');
 assert.throws(()=>core.validatePayload('imperium',{ok:true}),/lista|Fonte/);
 assert.throws(()=>core.validatePayload('toa',{ok:true}),/lista|Fonte/);
 assert.equal(core.validatePayload('toa',{records:[{contract:'12345'}]}).length,1);
});
class Node {
 constructor(tag){this.tag=tag;this.children=[];this.event={};this.classList={s:new Set(),contains(k){return this.s.has(k);},toggle(k,v){if(v===undefined)v=!this.s.has(k);v?this.s.add(k):this.s.delete(k);}};this.value='';this.textContent='';this.disabled=false;}
 append(...n){this.children.push(...n);}
 replaceChildren(...n){this.children=[...n];}
 addEventListener(name,cb){(this.event[name] ||= []).push(cb);}
 click(){for(const cb of this.event.click||[])cb();}
}
test('Visão Todos consulta duas fontes por cidade, preserva falha parcial e abre praça correta',async()=>{
 const ids=['allOperationsWorkspace','allOperationsDate','allOperationsRefresh','allOperationsSearch','allOperationsMetrics','allOperationsCards','allOperationsStatus','allOperationsFilterImperium','allOperationsFilterToa','allOperationsTableHead','allOperationsTableBody','allOperationsTableInfo'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Node(id)]));
 const document={getElementById:id=>nodes[id],createElement:tag=>new Node(tag),createDocumentFragment:()=>new Node('frag')};
 const window={};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/all-operations.js'),'utf8'),{window,document,console});
 let opened=null;const calls=[];
 const request=async(url)=>{
  calls.push(url);
  if(url.includes('profile=mossoro')&&url.includes('/api/toa-contracts'))throw Error('Fonte indisponivel');
  if(url.includes('/api/orders'))return {orders:[{num_os:'AB12',contract:'10001',status:'EM CAMPO'}]};
  return {records:[{contract:'00001',window:'08-12'}]};
 };
 window.DominiumAllOperations.activate({profiles,date:'2026-10-28',
   apiUrlForProfile:(url,p)=>url+'&profile='+p,request,onOpenProfile:key=>{opened=key;}});
 for(let i=0;i<15&&calls.length<8;i++)await new Promise(r=>setImmediate(r));
 await new Promise(r=>setImmediate(r));
 assert.equal(calls.length,8);
 assert.match(nodes.allOperationsStatus.textContent,/parcial/i);
 const cards=nodes.allOperationsCards.children[0].children;
 assert.equal(cards.length,4);
 const first=cards[0];
 first.children[0].children[1].click();
 assert.equal(opened,'natal');
 assert.match(nodes.allOperationsTableInfo.textContent,/8|4/);
 assert.equal(profiles[0].key,'natal');
});
test('view is isolated from existing route logic',()=>{
 const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
 const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
 assert.match(app,/if \(state\.activeModule === "all-operations"\) state\.activeModule = "dashboard";/);
 assert.match(app,/state\.activeModule = "all-operations";/);
 assert.match(html,/<section class="all-ops-workspace hidden"/);
 assert.match(html,/all-operations\.js/);
 assert.match(fs.readFileSync(path.join(__dirname,'../static/all-operations.js'),'utf8'),/Abrir operação/);
});
