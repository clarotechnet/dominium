'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {allowedCommissionReport}=require('../deploy/hostinger-web/commission-report-policy');
const {resolveOperationalRead}=require('../deploy/hostinger-web/operational-relay');

const target='/api/commission-reports/export.xlsx?profile=natal&start=2026-11-01&end=2026-11-11';
assert.equal(allowedCommissionReport('GET',target),true);
for(const bad of [
 target+'\n',target+'&sql=anything',target.replace('natal','all'),
 target.replace('profile=','city='),target.replace('start=','from=')
])assert.equal(allowedCommissionReport('GET',bad),false,bad);
assert.equal(allowedCommissionReport('POST',target),false);
const req={method:'GET',originalUrl:target,dominiumSession:{},dominiumUser:{id:1,role:'admin'}};
assert.equal(resolveOperationalRead(req,()=>({token:'x'.repeat(43)})).url,
 'https://dominium-import-bridge.jogador743.workers.dev'+target);
assert.throws(()=>resolveOperationalRead({...req,dominiumUser:{id:1,role:'viewer'}},()=>({token:'x'.repeat(43)})));
function element(extra={}) {
 return Object.assign({value:'',max:'',disabled:false,textContent:'',attrs:{},listeners:{},
   classList:{add(){},remove(){}},addEventListener(n,fn){this.listeners[n]=fn;},
   setAttribute(n,v){this.attrs[n]=v;},remove(){},click(){this.clicked=true;}},extra);
}
async function testUI(){
 const elements={
  commissionReportsWorkspace:element(),
  commissionReportStart:element(),commissionReportEnd:element(),
  commissionReportStatus:element(),commissionReportCity:element(),
  commissionReportDownload:element(),
 };
 elements.commissionReportsWorkspace.querySelector=selector=>elements[selector.slice(1)];
 const requests=[],links=[],listeners={};
 let resolveRequest;
 const ctx={profile:'natal',allCities:false,switching:false};
 const document={
  getElementById:id=>elements[id],
  addEventListener:(n,fn)=>{listeners[n]=fn;},
  createElement:()=>{const e=element();links.push(e);return e;},
  body:{append(){}}
 };
 const sandbox={document,Date,URLSearchParams,
   URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},setTimeout(){}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/commission-reports-ui.js'),'utf8'),sandbox);
 const ctrl=sandbox.DominiumCommissionReports.mount({
  getContext:()=>ctx,
  requestBlob:url=>{requests.push(url);return new Promise(resolve=>{resolveRequest=resolve;});}
 });
 ctx.allCities=true;ctrl.render();
 assert.equal(elements.commissionReportDownload.disabled,true);
 await ctrl.download();assert.equal(requests.length,0);
 ctx.allCities=false;ctrl.render();
 elements.commissionReportStart.value='2026-11-01';
 elements.commissionReportEnd.value='2026-11-11';
 const first=ctrl.download();
 assert.equal(elements.commissionReportDownload.disabled,true);
 assert.match(requests[0],/^\/api\/commission-reports\/export\.xlsx\?profile=natal/);
 await ctrl.download();assert.equal(requests.length,1);
 ctx.profile='recife';
 resolveRequest({blob:{size:1500}});
 await first;
 assert.equal(links.length,1);
 assert.match(links[0].download,/Comissoes_natal_2026-11-01_2026-11-11/);
 assert.equal(links[0].clicked,true);
 assert.match(elements.commissionReportStatus.textContent,/Natal/);
 elements.commissionReportEnd.value='2026-01-01';
 await ctrl.download();
 assert.equal(requests.length,1);
 assert.match(elements.commissionReportStatus.textContent,/período válido/);
}
testUI().then(()=>console.log('Commission UI, proxy, roles, filters and Excel download: OK'))
  .catch(e=>{console.error(e);process.exitCode=1;});
