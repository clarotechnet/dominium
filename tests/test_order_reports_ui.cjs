'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {allowedOrderReport} = require('../deploy/hostinger-web/order-report-policy');
const {resolveOperationalRead} = require('../deploy/hostinger-web/operational-relay');

const target = '/api/order-reports/export.xlsx?profile=natal&start=2026-01-01&end=2026-01-02&type=all';
assert(allowedOrderReport('GET', target));
for (const bad of [target+'\n', target+'&sql=select', target.replace('natal','all'),target.replace('all','technical'),target.replace('2026-01-01','%32%30')])
  assert.equal(allowedOrderReport('GET',bad),false,bad);
assert.equal(allowedOrderReport('POST',target),false);
const req={method:'GET',originalUrl:target,dominiumSession:{},dominiumUser:{id:1,role:'admin'}};
assert.equal(resolveOperationalRead(req,()=>({token:'x'.repeat(43)})).url,
  'https://dominium-import-bridge.jogador743.workers.dev'+target);
assert.throws(()=>resolveOperationalRead({...req,dominiumUser:{id:1,role:'viewer'}},()=>({token:'x'.repeat(43)})));

function element(extra={}) {
  return Object.assign({value:'',max:'',disabled:false,textContent:'',dataset:{},attrs:{},listeners:{},
    classList:{add(){},remove(){}},addEventListener(n,fn){this.listeners[n]=fn;},
    setAttribute(n,v){this.attrs[n]=v;},remove(){},click(){this.clicked=true;}},extra);
}
async function testUI() {
  const buttons=[element({dataset:{orderReport:'all'}}),element({dataset:{orderReport:'maintenance'}})];
  const elements={
    orderReportsWorkspace:element({querySelectorAll:()=>buttons}),
    orderReportStart:element(),orderReportEnd:element(),orderReportStatus:element(),orderReportCity:element()
  };
  const links=[];const requests=[];const listeners={};let done;
  const ctx={profile:'natal',allCities:false,switching:false};
  const document={getElementById:id=>elements[id],addEventListener:(n,fn)=>{listeners[n]=fn;},
    createElement:()=>{const a=element();links.push(a);return a;},body:{append(){}}};
  const sandbox={document,Date,URLSearchParams,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setTimeout(){}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/order-reports-ui.js'),'utf8'),sandbox);
  const controller=sandbox.DominiumOrderReports.mount({
    getContext:()=>ctx,requestBlob:(url)=>{requests.push(url);return new Promise(resolve=>{done=resolve;});}
  });
  elements.orderReportStart.value=elements.orderReportEnd.value='2026-01-01';
  ctx.allCities=true;controller.render();assert(buttons.every(b=>b.disabled));
  await controller.download('all');assert.equal(requests.length,0);
  ctx.allCities=false;controller.render();
  const download=controller.download('maintenance');
  assert(buttons.every(b=>b.disabled));
  assert.equal(elements.orderReportsWorkspace.attrs['aria-busy'],'true');
  await controller.download('all');assert.equal(requests.length,1);
  assert.match(requests[0],/profile=natal.*type=maintenance$/);
  ctx.profile='recife';controller.render();done({blob:{}});await download;
  assert.match(links[0].download,/Manutencao_natal_2026-01-01/);
  assert(links[0].clicked);
  assert.match(elements.orderReportStatus.textContent,/Natal/);
  assert(buttons.every(b=>!b.disabled));
  elements.orderReportStart.value='2026-01-03';
  await controller.download('all');assert.equal(requests.length,1);
  assert.match(elements.orderReportStatus.textContent,/período válido/);
}
testUI().then(()=>console.log('OS reports policy, role, dates, city scope and download tests: OK'))
  .catch(e=>{console.error(e);process.exitCode=1;});
