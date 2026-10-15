import test from 'node:test';
import assert from 'node:assert/strict';
let worker;
try {worker=(await import('./worker.mjs')).default;} catch(e) {if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;}
const secret='x'.repeat(43);
const headers={Authorization:'Bearer '+secret,'X-Dominium-Actor':'Operador','X-Dominium-Role':'controller','content-type':'application/json'};
test('bridge refuses missing or invalid credentials and unrelated operations',async()=>{
 assert.ok(worker);let calls=0;const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{calls++;return new Response('{}');}}};
 for(const authorization of ['', 'Bearer wrong']){
  const r=await worker.fetch(new Request('https://bridge.test/api/import-targets',{headers:{...headers,Authorization:authorization}}),env);assert.equal(r.status,401);
 }
 for(const path of ['/api/close','/api/imports/preview?url=evil','/.env']){
  const r=await worker.fetch(new Request('https://bridge.test'+path,{method:'POST',headers,body:'{}'}),env);assert.equal(r.status,404);
 }assert.equal(calls,0);
});
test('bridge forwards only the authorized import payload to the fixed private service',async()=>{
 assert.ok(worker);let seen;const body=JSON.stringify({filename:'Atividades-FTZ.csv',content_base64:'original'});
 const r=await worker.fetch(new Request('https://bridge.test/api/imports/preview',{method:'POST',headers:{...headers,Cookie:'private'},body}),{IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async(req)=>{seen=req;return new Response('{"ok":true}',{status:200});}}});
 assert.equal(r.status,200);assert.equal(seen.url,'http://127.0.0.1:8765/api/imports/preview');assert.equal(await seen.text(),body);
 assert.equal(seen.headers.get('cookie'),null);assert.equal(seen.headers.get('authorization'),null);assert.equal(r.headers.get('cache-control'),'no-store');
});
test('bridge rejects oversized requests before forwarding and never follows an upstream redirect',async()=>{
 assert.ok(worker);let calls=0;const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{calls++;return new Response('',{status:302});}}};
 const huge=await worker.fetch(new Request('https://bridge.test/api/imports/preview',{method:'POST',headers:{...headers,'content-length':String(13*1024*1024)},body:'{}'}),env);
 assert.equal(huge.status,413);assert.equal(calls,0);
 const r=await worker.fetch(new Request('https://bridge.test/api/imports/commit',{method:'POST',headers,body:'{}'}),env);assert.equal(r.status,502);assert.equal(calls,1);
});
