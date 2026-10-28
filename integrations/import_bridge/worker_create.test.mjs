import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

const token='s'.repeat(43);
const auth={Authorization:'Bearer '+token,'X-Dominium-Actor':'Controlador','X-Dominium-Role':'controller','Content-Type':'application/json'};
const url='https://safe.bridge.test/api/orders/bulk-create?profile=fortaleza';
const body=JSON.stringify({request_id:'req_20261028_ab12',confirmed:true,technician_id:52299,
  technician:'EDILSON',service:'RETIRADA FORA TOA',contracts:['5394655'],client_mode:'registered'});

test('order create uses VPC private service exactly once without browser cookies',async()=>{
 let calls=0,received;
 const env={IMPORT_TOKEN:token,IMPORT_SERVICE:{fetch:async req=>{
   calls++;received=req;return Response.json({ok:true,imported:1,orders:[{id_os:1}]});
 }},DESC_SERVICE:{fetch:()=>{throw Error('unexpected DESC service');}}};
 const result=await worker.fetch(new Request(url,{method:'POST',
   headers:{...auth,Cookie:'session', 'X-CSRF-Token':'browser-secret'},body}),env);
 assert.equal(result.status,200);
 assert.equal(calls,1);
 assert.equal(received.url,'http://127.0.0.1:8765/api/orders/bulk-create?profile=fortaleza');
 assert.equal(await received.text(),body);
 for(const name of ['authorization','cookie','x-csrf-token'])
   assert.equal(received.headers.get(name),null);
 assert.equal(received.headers.get('content-type'),'application/json');
});
test('unsafe creation requests fail before touching private backend',async()=>{
 let calls=0;
 const env={IMPORT_TOKEN:token,IMPORT_SERVICE:{fetch:async()=>{
   calls++;return Response.json({ok:true});
 }}};
 const requests=[
  [url,{'X-Dominium-Role':'viewer'},body,403],
  [url+'&profile=recife',{},body,404],
  [url.replace('fortaleza','unknown'),{},body,404],
  [url,{},JSON.stringify({confirmed:false,request_id:'valid12345678'}),400],
  [url,{},JSON.stringify({confirmed:true,request_id:'valid12345678',technician_id:1,service:'X'}),400],
  [url,{'Content-Type':'text/plain'},body,415],
  [url,{},'x'.repeat(256*1024+1),413],
 ];
 for(const [target,extra,data,status] of requests) {
   const response=await worker.fetch(new Request(target,{method:'POST',headers:{...auth,...extra},body:data}),env);
   assert.equal(response.status,status,target);
 }
 assert.equal(calls,0);
});
test('transport failure of order creation is uncertain, never automatically replayed',async()=>{
 let calls=0;
 const env={IMPORT_TOKEN:token,IMPORT_SERVICE:{fetch:async()=>{calls++;throw Error('lost response');}}};
 const result=await worker.fetch(new Request(url,{method:'POST',headers:auth,body}),env);
 assert.equal(result.status,502);
 assert.equal(calls,1);
 const payload=await result.json();
 assert.equal(payload.uncertain,true);
 assert.equal(payload.safe_to_retry,false);
});
test('operational mutations require controller, exact route and private POST',async()=>{
 let calls=0,received;
 const env={IMPORT_TOKEN:token,IMPORT_SERVICE:{fetch:async req=>{
   calls++;received=req;return Response.json({ok:true});
 }}};
 const good=await worker.fetch(new Request('https://safe.bridge.test/api/stock/writeoff?profile=fortaleza',{
   method:'POST',headers:auth,body:JSON.stringify({confirmed:true,request_id:'req_test_12345'})
 }),env);
 assert.equal(good.status,200);
 assert.equal(received.url,'http://127.0.0.1:8765/api/stock/writeoff?profile=fortaleza');
 const bad=await worker.fetch(new Request('https://safe.bridge.test/api/stock/writeoff?method=delete',{
   method:'POST',headers:auth,body:'{}'
 }),env);
 assert.equal(bad.status,404);
 assert.equal(calls,1);
});
