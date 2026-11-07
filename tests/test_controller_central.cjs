'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..'),api=require('../static/controller-central.js');
const agents=[
 {id:'ctl-01',online:true,busy:false,buckets:['NTL-DMV_ADM','NTL-DMV','NTL-DMV'],queries:5,requests_recent:7,last_seen:10000},
 {id:'ctl-02',online:true,busy:false,buckets:['NTL-DMV_ADM'],queries:2,requests_recent:1,last_seen:10000},
 {id:'ctl-03',online:false,busy:false,buckets:['NTL-DMV_ADM'],queries:0,requests_recent:0,last_seen:null},
 {id:'ctl-04',online:true,busy:true,buckets:['MRO-DMV'],queries:3,requests_recent:2,last_seen:10000}
];
test('catálogo contém 12 buckets e mapeamento de negócio correto',()=>{
 assert.equal(Object.keys(api.MAP).length,12);
 assert.deepEqual(api.MAP['MRO-DMV'],['Mossoró','Adesão / Visita técnica / Desconexão']);
 assert.deepEqual(api.MAP['JCR-DMV'],['Recife','Adesão']);
 assert.deepEqual(api.MAP['FTZ-DMV_ADM'],['Fortaleza','Desconexão']);
 assert.equal(api.MAP['JCR-DMV_VT'],undefined);
});
test('sessões offline não contam como cobertura de bucket',()=>{
 const m=api.normalize({agents,enrollments_pending:2,leases_today:3,max_leases_per_day:0});
 assert.equal(m.online,3);
 assert.equal(m.busy,1);
 assert.equal(m.pending,2);
 assert.equal(m.coverage['NTL-DMV_ADM'].online,2);
 assert.equal(m.coverage['NTL-DMV_ADM'].busy,0);
 assert.equal(m.coverage['MRO-DMV'].busy,1);
 assert.equal(m.limit,0);
});
test('50 contratos podem ser divididos igualmente por 10 sessões livres elegíveis',()=>{
 const ten=Array.from({length:10},(_,n)=>({id:'ctl-'+n,online:true,busy:false,buckets:['NTL-DMV_ADM']}));
 const out=api.distribution('NTL-DMV_ADM',50,ten);
 assert.equal(out.eligible,10);assert.equal(out.unallocated,0);
 assert.deepEqual(out.assignments.map(x=>x.proposed),Array(10).fill(5));
});
test('não usa controlador ocupado ou sem acesso ao bucket',()=>{
 const out=api.distribution('NTL-DMV_ADM',12,agents);
 assert.equal(out.eligible,2);
 assert.deepEqual(out.assignments.map(x=>x.proposed),[6,6]);
});
test('sem sessão elegível mantém contratos aguardando',()=>{
 assert.deepEqual(api.distribution('PWM-DMV',8,agents),{eligible:0,assignments:[],unallocated:8});
});
test('rejeita bucket não cadastrado e quantidade inválida',()=>{
 assert.throws(()=>api.distribution('JCR-DMV_VT',5,agents),/Bucket/);
 assert.equal(api.distribution('NTL-DMV_ADM',-2,agents).unallocated,0);
});
test('normalize não traz credenciais nem contratos do payload da API',()=>{
 const m=api.normalize({data:{agents:[{...agents[0],token:'secret',contract:'123',password:'secret'}]}});
 assert.ok(!('token' in m.agents[0]));
 assert.ok(!('contract' in m.agents[0]));
 assert.ok(!('password' in m.agents[0]));
});
test('endpoint da interface é autenticado pelo DOMINIUM e não contém segredo',()=>{
 const html=fs.readFileSync(path.join(root,'static/index.html'),'utf8'),
       code=fs.readFileSync(path.join(root,'static/controller-central.js'),'utf8');
 assert.match(html,/id="toaCentral"/);assert.match(html,/controller-central\.css/);
 assert.match(html,/controller-central\.js/);
 assert.match(code,/\/api\/toa-pool\/monitor/);
 assert.match(code,/credentials:"same-origin"/);
 assert.doesNotMatch(code,/\/agents\/next|\/agents\/enroll|Authorization:/);
});
