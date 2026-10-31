'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const { createBacklogMiddleware } = require('../deploy/hostinger-web/backlog-proxy');
const TOKEN = 'B'.repeat(56);
function request(method='GET',url='/api/backlog/year/status',role='controller'){
  return {
    method,path:url.split('?')[0],originalUrl:url,
    dominiumSession:{csrf_hash:crypto.createHash('sha256').update('validcsrf').digest('hex')},
    dominiumUser:{role,id:77,display_name:'Operador'},
    headers:{cookie:'__Host-dominium_session=sensitive','x-csrf-token':'validcsrf',
      'x-dominium-role':'admin','x-dominium-actor':'forged'},
    body:{mode:'probe',profile:'natal'},
  };
}
function response(){
  return {code:200,headers:{},status(n){this.code=n;return this},
    set(k,v){this.headers[k.toLowerCase()]=v;return this},
    json(value){this.body=value;return this},
    send(value){this.body=value;return this}};
}
const cfg=(fetchImpl,token=TOKEN)=>({connection:()=>({origin:'https://dominium-backlog-bridge.dmv-analise-backlog.workers.dev',token}),fetchImpl});
test('must refuse anonymous/viewer before calling private Worker',async()=>{
  let calls=0;
  const proxy=createBacklogMiddleware(cfg(async()=>{calls++}));
  for(const role of ['', 'viewer']){
    const r=response(),q=request('GET',undefined,role);
    if(!role){delete q.dominiumSession; delete q.dominiumUser}
    await proxy(q,r);
    assert.equal(r.code,role?403:401);
  }
  assert.equal(calls,0);
});
test('POST requires real CSRF and rejects unrecognized routes',async()=>{
  let calls=0;
  const proxy=createBacklogMiddleware(cfg(async()=>{calls++}));
  const q=request('POST','/api/backlog/year/start');
  q.headers['x-csrf-token']='wrong';
  let r=response();await proxy(q,r);assert.equal(r.code,403);
  r=response();await proxy(request('GET','/api/backlog/year/delete'),r);assert.equal(r.code,404);
  r=response();await proxy(request('GET','/api/backlog/year/compare?limit=99999'),r);assert.equal(r.code,404);
  assert.equal(calls,0);
});
test('missing private secret must fail closed without calling public Worker',async()=>{
  let calls=0;
  const proxy=createBacklogMiddleware(cfg(async()=>{calls++},null));
  const r=response();await proxy(request(),r);
  assert.equal(r.code,503);assert.equal(calls,0);
});
test('uses server-owned bearer and role; strips browser cookies/forged headers',async()=>{
  let call;
  const proxy=createBacklogMiddleware(cfg(async (url,init)=>{
    call={url,init};
    return new Response(JSON.stringify({ok:true,rows:[]}),{status:200,headers:{'content-type':'application/json'}});
  }));
  const r=response();
  await proxy(request('POST','/api/backlog/year/start'),r);
  assert.equal(r.code,200);
  assert.equal(call.url,'https://dominium-backlog-bridge.dmv-analise-backlog.workers.dev/api/backlog/year/start');
  assert.equal(call.init.headers.Authorization,'Bearer '+TOKEN);
  assert.equal(call.init.headers['X-Dominium-Role'],'controller');
  assert.equal(call.init.headers['X-Dominium-Actor'],'77');
  assert.equal(call.init.headers.Cookie,undefined);
  assert.equal(call.init.headers['x-csrf-token'],undefined);
  assert.deepEqual(JSON.parse(call.init.body),{mode:'probe',profile:'natal'});
  assert.deepEqual(JSON.parse(r.body),{ok:true,rows:[]});
});
test('read-only query path and upstream outage handled safely',async()=>{
  let target;
  const proxy=createBacklogMiddleware(cfg(async(url)=>{target=url;throw Error('upstream outage')}));
  const r=response();
  await proxy(request('GET','/api/backlog/year/compare?limit=100&codes=106%2C430'),r);
  assert.match(target,/compare\?limit=100&codes=/);
  assert.equal(r.code,502);
});
