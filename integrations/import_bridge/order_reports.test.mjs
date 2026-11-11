import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';
const secret='x'.repeat(43);
const headers={Authorization:'Bearer '+secret,'X-Dominium-Actor':'user-1','X-Dominium-Role':'controller',
 Cookie:'private-browser-cookie','X-CSRF-Token':'private-browser-csrf'};
test('OS export preserves binary content and filename on the fixed read-only service',async()=>{
 let seen,calls=0;
 const target='/api/order-reports/export.xlsx?profile=natal&start=2026-01-01&end=2026-01-02&type=all';
 const env={IMPORT_TOKEN:secret,DESC_SERVICE:{fetch:async req=>{
  seen=req;calls++;return new Response(new Uint8Array([80,75,3,4]),{headers:{
   'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
   'Content-Disposition':'attachment; filename="OS_Todos.xlsx"'}});
 }}};
 const response=await worker.fetch(new Request('https://bridge.test'+target,{headers}),env);
 assert.equal(response.status,200);assert.equal(calls,1);
 assert.equal(seen.url,'http://127.0.0.1:8793'+target);
 assert.equal(seen.headers.get('authorization'),'Bearer '+secret);
 for(const name of ['cookie','x-csrf-token'])assert.equal(seen.headers.get(name),null);
 assert.equal(response.headers.get('content-disposition'),'attachment; filename="OS_Todos.xlsx"');
 assert.deepEqual([...new Uint8Array(await response.arrayBuffer())],[80,75,3,4]);
 const treatedTarget=target+'&variant=treated';
 const treated=await worker.fetch(new Request('https://bridge.test'+treatedTarget,{headers}),env);
 assert.equal(treated.status,200);assert.equal(calls,2);
 assert.equal(seen.url,'http://127.0.0.1:8793'+treatedTarget);
 for(const [url,extra,method,status] of [
  [target,{'X-Dominium-Role':'viewer'},'GET',403],
  [target+'&profile=recife',{},'GET',404],
  [target,{},'POST',404],
  [target.replace('natal','all'),{},'GET',404],
  [target+'&variant=raw',{},'GET',404],
 ]) {
  const blocked=await worker.fetch(new Request('https://bridge.test'+url,{headers:{...headers,...extra},method}),env);
  assert.equal(blocked.status,status);assert.equal(calls,2);
 }
});
