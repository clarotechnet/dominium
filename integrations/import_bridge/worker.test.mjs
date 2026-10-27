import test from 'node:test';
import assert from 'node:assert/strict';
let worker;
try {worker=(await import('./worker.mjs')).default;} catch(e) {if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;}
const secret='x'.repeat(43);
const headers={Authorization:'Bearer '+secret,'X-Dominium-Actor':'Operador','X-Dominium-Role':'controller','content-type':'application/json'};

test('TOA lookup POST reaches the existing private panel without browser credentials',async()=>{
 let seen,calls=0;
 const body=JSON.stringify({query:'4321295',expected_profile_key:'natal'});
 const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async(req)=>{calls++;seen=req;return Response.json({ok:true,profile:'natal',results:[{contract:'4321295'}]});}},DESC_SERVICE:{fetch:async()=>{throw Error('wrong service');}}};
 const response=await worker.fetch(new Request('https://bridge.test/api/toa-live/lookup?profile=natal',{
   method:'POST',headers:{...headers,Cookie:'private','X-CSRF-Token':'private'},body}),env);
 assert.equal(response.status,200);
 assert.equal(seen.url,'http://127.0.0.1:8765/api/toa-live/lookup?profile=natal');
 assert.equal(await seen.text(),body);
 assert.equal(seen.headers.get('content-type'),'application/json');
 for(const name of ['cookie','x-csrf-token','authorization'])assert.equal(seen.headers.get(name),null);
 assert.equal((await response.json()).results[0].contract,'4321295');
 assert.equal(calls,1);
});

test('TOA lookup rejects invalid scope, role, JSON media type and oversized body before forwarding',async()=>{
 let calls=0;
 const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{calls++;return Response.json({ok:true});}}};
 const target='https://bridge.test/api/toa-live/lookup?profile=natal';
 for(const [url,extra,body,status] of [
   [target,{'X-Dominium-Role':'viewer'},'{}',403],
   [target.replace('natal','unknown'),{},'{}',404],
   [target+'&url=evil',{},'{}',404],
   [target,{'content-type':'text/plain'},'{}',415],
   [target,{'content-length':String(65537)},'{}',413],
   [target,{},'x'.repeat(65537),413],
 ]){
   const response=await worker.fetch(new Request(url,{method:'POST',headers:{...headers,...extra},body}),env);
   assert.equal(response.status,status,url);
 }
 assert.equal(calls,0);
});

test('TOA lookup propagates backend errors once and never retries or hides them',async()=>{
 let calls=0;
 const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{calls++;return Response.json({ok:false,error:'toa_contrato_nao_encontrado'},{status:404});}}};
 const response=await worker.fetch(new Request('https://bridge.test/api/toa-live/lookup?profile=natal',{
   method:'POST',headers,body:JSON.stringify({query:'4321295',expected_profile_key:'natal'})}),env);
 assert.equal(response.status,404);
 assert.equal((await response.json()).error,'toa_contrato_nao_encontrado');
 assert.equal(calls,1);
});
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

test('the DESC panel uses only its dedicated private service and preserves internal authentication',async()=>{
 assert.ok(worker);let seen;let imports=0;
 const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{imports++;}},DESC_SERVICE:{fetch:async(req)=>{seen=req;return new Response('{"batches":[]}');}}};
 const r=await worker.fetch(new Request('https://bridge.test/api/disconnection/state',{headers}),env);
 assert.equal(r.status,200);assert.equal(imports,0);assert.equal(seen.url,'http://127.0.0.1:8793/api/disconnection/state');
 assert.equal(seen.headers.get('authorization'),'Bearer '+secret);
 assert.equal(seen.headers.get('x-dominium-actor'),'Operador');
 const bad=await worker.fetch(new Request('https://bridge.test/api/disconnection/session',{method:'POST',headers,body:'{}'}),env);assert.equal(bad.status,404);
});

test('approved operational GETs pass through the existing VPC service without cookies or CSRF',async()=>{
  assert.ok(worker);let seen;let descCalls=0;
  const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async(req)=>{
    seen=req;return new Response('{"ok":true,"contracts":[]}',{status:200,headers:{'content-type':'application/json'}});
  }},DESC_SERVICE:{fetch:async()=>{descCalls++;throw Error('Unexpected DESC call');}}};
  const request=new Request('https://bridge.test/api/toa-contracts?profile=natal&date=2026-10-21',{
    headers:{...headers,'X-Dominium-Role':'viewer',Cookie:'browser-session', 'X-CSRF-Token':'private'}
  });
  const result=await worker.fetch(request,env);
  assert.equal(result.status,200);
  assert.equal(seen.url,'http://127.0.0.1:8765/api/toa-contracts?profile=natal&date=2026-10-21');
  assert.equal(seen.headers.get('cookie'),null);
  assert.equal(seen.headers.get('x-csrf-token'),null);
  assert.equal(seen.headers.get('authorization'),null);
  assert.equal(descCalls,0);
  assert.equal(result.headers.get('x-dominium-backend'),'private-import-bridge');
});

test('private bridge blocks write, unauthorized and unrelated operational requests',async()=>{
  let calls=0;
  const env={IMPORT_TOKEN:secret,IMPORT_SERVICE:{fetch:async()=>{
    calls++;return new Response('{}',{status:200});
  }}};
  for(const request of [
    new Request('https://bridge.test/api/orders',{method:'POST',headers,body:'{}'}),
    new Request('https://bridge.test/api/auto-improductive-close/toggle',{method:'POST',headers,body:'{}'}),
    new Request('https://bridge.test/api/auth/users',{headers}),
    new Request('https://bridge.test/api/orders',{headers:{...headers,Authorization:'Bearer invalid'}}),
  ]){
    const result=await worker.fetch(request,env);
    assert.ok(result.status===401 || result.status===404, String(result.status));
  }
  assert.equal(calls,0);
});

test('stock official API reads use the DESC private service and enforce admin/controller',async()=>{
  let descCalls=0,importCalls=0,seen;
  const env={
    IMPORT_TOKEN:secret,
    IMPORT_SERVICE:{fetch:async()=>{importCalls++;return new Response('{}')}},
    DESC_SERVICE:{fetch:async(req)=>{descCalls++;seen=req;return Response.json({ok:true,count:2,stocks:[]});}},
  };
  for(const route of ['/api/imperium-official/stocks?profile=natal','/api/imperium-official/stocks/123/items?profile=fortaleza']){
    const request=new Request('https://bridge.test'+route,{headers:{...headers,Cookie:'private'}});
    const result=await worker.fetch(request,env);
    assert.equal(result.status,200);
    assert.equal(seen.url,'http://127.0.0.1:8793'+route);
    assert.equal(seen.headers.get('Authorization'),'Bearer '+secret);
    assert.equal(seen.headers.get('x-dominium-role'),'controller');
    assert.equal(seen.headers.get('Cookie'),null);
  }
  assert.equal(descCalls,2);
  assert.equal(importCalls,0);
  const viewer=await worker.fetch(new Request('https://bridge.test/api/imperium-official/stocks',{headers:{...headers,'X-Dominium-Role':'viewer'}}),env);
  assert.equal(viewer.status,403);
  const mutation=await worker.fetch(new Request('https://bridge.test/api/imperium-official/stocks',{method:'POST',headers,body:'{}'}),env);
  assert.equal(mutation.status,404);
  assert.equal(descCalls,2);
});

test('serial consultation is read-only and limited to operational roles', async()=>{
  let descCalls=0, importCalls=0, captured;
  const env={
    IMPORT_TOKEN:secret,
    IMPORT_SERVICE:{fetch:async()=>{importCalls++;return Response.json({ok:false})}},
    DESC_SERVICE:{fetch:async req=>{
      descCalls++;captured=req;
      return Response.json({ok:true,results:[{serial:'SERIAL000000',datasnap:{movements:[]}}]});
    }},
  };
  const uri='https://bridge.test/api/serials/consult?serials=SERIAL000000&mode=analitico';
  const allowed=await worker.fetch(new Request(uri,{headers:{...headers,'X-Dominium-Role':'controller',Cookie:'browser-cookie'}}),env);
  assert.equal(allowed.status,200);
  assert.equal(captured.url,'http://127.0.0.1:8793/api/serials/consult?serials=SERIAL000000&mode=analitico');
  assert.equal(captured.headers.get('cookie'),null);
  assert.equal(captured.headers.get('authorization'),'Bearer '+secret);
  assert.equal(captured.headers.get('x-dominium-role'),'controller');
  assert.equal(descCalls,1);
  assert.equal(importCalls,0);
  const viewer=await worker.fetch(new Request(uri,{headers:{...headers,'X-Dominium-Role':'viewer'}}),env);
  assert.equal(viewer.status,403);
  const writing=await worker.fetch(new Request(uri,{method:'POST',headers,body:'{}'}),env);
  assert.equal(writing.status,404);
  assert.equal(descCalls,1);
});

test('operator REPORTs pass only authenticated read/write paths to DESC and never send cookies',async()=>{
  let descCalls=0,importCalls=0,seen;
  const env={IMPORT_TOKEN:secret,
    IMPORT_SERVICE:{fetch:async()=>{importCalls++;return Response.json({ok:false});}},
    DESC_SERVICE:{fetch:async(req)=>{descCalls++;seen=req;return Response.json({ok:true,reports:[]});}}};
  for(const method of ['GET','POST']){
    const options={method,headers:{...headers,Cookie:'private-browser-session','X-CSRF-Token':'secret'}};
    if(method==='POST')options.body=JSON.stringify({kind:'erro',title:'Teste de operação',detail:'Falha de teste do sistema operacional'});
    const result=await worker.fetch(new Request('https://bridge.test/api/disconnection/reports',options),env);
    assert.equal(result.status,200);
    assert.equal(seen.url,'http://127.0.0.1:8793/api/disconnection/reports');
    assert.equal(seen.headers.get('x-dominium-role'),'controller');
    assert.equal(seen.headers.get('authorization'),'Bearer '+secret);
    assert.equal(seen.headers.get('cookie'),null);
    assert.equal(seen.headers.get('x-csrf-token'),null);
  }
  assert.equal(descCalls,2);
  assert.equal(importCalls,0);
  const viewer=await worker.fetch(new Request('https://bridge.test/api/disconnection/reports',{headers:{...headers,'X-Dominium-Role':'viewer'}}),env);
  assert.equal(viewer.status,403);
  const deleting=await worker.fetch(new Request('https://bridge.test/api/disconnection/reports',{method:'DELETE',headers}),env);
  assert.equal(deleting.status,404);
  assert.equal(descCalls,2);
});

test('confront report routes use DESC service, authenticated role and never forward browser cookies', async()=>{
  let descCalls=0,importCalls=0,captured;
  const env={IMPORT_TOKEN:secret,
    IMPORT_SERVICE:{fetch:async()=>{importCalls++;return Response.json({ok:true});}},
    DESC_SERVICE:{fetch:async req=>{
      descCalls++;captured=req;
      return Response.json({ok:true,job:{job_id:'a'.repeat(32),total:1,done:0}});
    }}};
  const create=await worker.fetch(new Request('https://bridge.test/api/confront/jobs',
    {method:'POST',headers:{...headers,Cookie:'browser-private','X-CSRF-Token':'secret'},
     body:JSON.stringify({serials:['ABCDEF123456'],profile:'natal',mode:'analitico'})}),env);
  assert.equal(create.status,200);
  assert.equal(descCalls,1);
  assert.equal(importCalls,0);
  assert.equal(captured.url,'http://127.0.0.1:8793/api/confront/jobs');
  assert.equal(captured.headers.get('authorization'),'Bearer '+secret);
  assert.equal(captured.headers.get('cookie'),null);
  assert.equal(captured.headers.get('x-csrf-token'),null);
  assert.equal(captured.headers.get('x-dominium-role'),'controller');
  for(const method of ['GET']) {
    const res=await worker.fetch(new Request('https://bridge.test/api/confront/jobs/'+'a'.repeat(32),
     {method,headers}),env);
    assert.equal(res.status,200);
  }
  assert.equal(descCalls,2);
});

test('viewer and unapproved confront paths cannot consume private services', async()=>{
  let calls=0;
  const env={IMPORT_TOKEN:secret,
    IMPORT_SERVICE:{fetch:async()=>{calls++;return Response.json({ok:true});}},
    DESC_SERVICE:{fetch:async()=>{calls++;return Response.json({ok:true});}}};
  for(const request of [
    new Request('https://bridge.test/api/confront/jobs',{method:'POST',
      headers:{...headers,'X-Dominium-Role':'viewer'},body:'{}'}),
    new Request('https://bridge.test/api/confront/status',{headers:{...headers,'X-Dominium-Role':'viewer'}}),
    new Request('https://bridge.test/api/confront/jobs/invalid',{headers}),
    new Request('https://bridge.test/api/confront/status',{method:'POST',headers,body:'{}'}),
    new Request('https://bridge.test/api/confront/jobs?ignored=yes',{headers}),
  ]) {
    const res=await worker.fetch(request,env);
    assert.ok([403,404].includes(res.status), String(res.status));
  }
  assert.equal(calls,0);
});
