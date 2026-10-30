import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../integrations/import_bridge/worker.mjs';

const token='A'.repeat(50);
function envFor(calls) {
  return {
    IMPORT_TOKEN:token,
    IMPORT_SERVICE:{fetch:async req=>{
      calls.push({url:req.url,method:req.method,auth:req.headers.get('Authorization'),
        role:req.headers.get('X-Dominium-Role')});
      return Response.json({ok:true,method:req.method});
    }},
    DESC_SERVICE:{fetch:async()=>{throw Error('Wrong relay')}}};
}
function request(method,path,role='controller',body) {
  return new Request('https://bridge.example'+path,{
    method,
    headers:{authorization:'Bearer '+token,'x-dominium-role':role,
      'x-dominium-actor':'user-test',
      ...(body?{'content-type':'application/json'}:{})},
    ...(body?{body:JSON.stringify(body)}:{})
  });
}
test('private bridge read routes use operational service and authenticated actor',async()=>{
  const calls=[];
  const response=await worker.fetch(request('GET','/api/backlog/year/status'),envFor(calls));
  assert.equal(response.status,200);
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'http://127.0.0.1:9342/api/backlog/year/status');
  assert.equal(calls[0].auth,'Bearer '+token);
  assert.equal(calls[0].role,'controller');
});
test('private bridge POST start accepted only for controller/admin, capped',async()=>{
  const calls=[];
  assert.equal((await worker.fetch(request('POST','/api/backlog/year/start','controller',{mode:'probe',profile:'natal'}),envFor(calls))).status,200);
  assert.equal(calls.length,1);
  assert.equal(calls[0].method,'POST');
  assert.equal((await worker.fetch(request('POST','/api/backlog/year/start','viewer',{mode:'probe'}),envFor(calls))).status,403);
  assert.equal(calls.length,1);
});
test('bridge rejects unrecognized backlog path and invalid bearer',async()=>{
  const calls=[];
  const invalid=await worker.fetch(request('GET','/api/backlog/year/delete'),envFor(calls));
  assert.notEqual(invalid.status,200);
  const forged=request('GET','/api/backlog/year/status');
  forged.headers.set('authorization','Bearer invalid');
  assert.equal((await worker.fetch(forged,envFor(calls))).status,401);
  assert.equal(calls.length,0);
});
