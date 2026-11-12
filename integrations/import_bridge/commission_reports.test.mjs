import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

const secret='x'.repeat(43);
const target='/api/commission-reports/export.xlsx?profile=mossoro&start=2026-11-01&end=2026-11-11';
const headers={
  Authorization:'Bearer '+secret,
  'X-Dominium-Actor':'synthetic-controller',
  'X-Dominium-Role':'controller',
  Cookie:'private-test-cookie',
  'X-CSRF-Token':'private-test-csrf',
};
test('commission XLSX is forwarded to authenticated read-only DESC relay',async()=>{
 let count=0;
 const env={IMPORT_TOKEN:secret,DESC_SERVICE:{fetch:async req=>{
  count++;
  assert.equal(req.url,'http://127.0.0.1:8793'+target);
  assert.equal(req.method,'GET');
  assert.equal(req.headers.get('authorization'),'Bearer '+secret);
  assert.equal(req.headers.get('cookie'),null);
  assert.equal(req.headers.get('x-csrf-token'),null);
  return new Response(new Uint8Array([80,75,3,4]),{headers:{
   'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
   'Content-Disposition':'attachment; filename="Comissoes_mossoro.xlsx"',
  }});
 }}};
 const response=await worker.fetch(new Request('https://bridge.test'+target,{headers}),env);
 assert.equal(response.status,200);
 assert.equal(count,1);
 assert.equal(response.headers.get('content-disposition'),
   'attachment; filename="Comissoes_mossoro.xlsx"');
 assert.deepEqual([...new Uint8Array(await response.arrayBuffer())],[80,75,3,4]);
 for(const [url,extra,method,status] of [
  [target,{'X-Dominium-Role':'viewer'},'GET',403],
  [target+'&extra=1',{},'GET',404],
  [target.replace('mossoro','all'),{},'GET',404],
  [target,{},'POST',404],
 ]) {
  const result=await worker.fetch(new Request('https://bridge.test'+url,
    {headers:{...headers,...extra},method}),env);
  assert.equal(result.status,status,url);
  assert.equal(count,1);
 }
});
