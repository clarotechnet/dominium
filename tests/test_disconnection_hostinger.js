'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
let create;
try {({createDisconnectionMiddleware:create}=require('../deploy/hostinger-web/disconnection-proxy'));}catch(e){if(e.code!=='MODULE_NOT_FOUND')throw e;}
const crypto=require('node:crypto');
function req(role='controller',method='GET',url='/api/disconnection/state') {return {method,originalUrl:url,dominiumUser:{role,display_name:'José de teste'},dominiumSession:{csrf_hash:crypto.createHash('sha256').update('fixture').digest('hex')},headers:{'x-csrf-token':'fixture'},body:{id:'one',actor:'forged'}};}
function response(){return {code:200,headers:{},status(n){this.code=n;return this;},set(name,value){this.headers[name]=value;return this;},json(value){this.body=value;return this;},send(value){this.body=value;return this;}};}
test('DESC refuses anonymous, viewer and invalid csrf before any upstream request',async()=>{
 assert.ok(create);let calls=0;const handler=create({connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async()=>{calls++;}});
 for(const role of ['','viewer']){const r=response();await handler(req(role),r);assert.equal(r.code,role?403:401);}
 const r=response(),request=req('controller','POST','/api/disconnection/decision');request.headers={};await handler(request,r);assert.equal(r.code,403);assert.equal(calls,0);
});
test('DESC uses private relay credential and authenticated actor, never visitor cookies',async()=>{
 assert.ok(create);let options;const handler=create({connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async(_url,o)=>{options=o;return new Response('{"mode":"test"}',{headers:{'Content-Type':'application/json'}});}});
 const r=response(),request=req('controller','POST','/api/disconnection/decision');request.headers.cookie='visitor=private';await handler(request,r);
 assert.equal(r.code,200);assert.equal(options.headers.Authorization,'Bearer '+'a'.repeat(43));assert.equal(options.headers.Cookie,undefined);assert.equal(JSON.parse(options.body).actor,'José de teste');assert.equal(options.headers['X-Dominium-Actor'],encodeURIComponent('José de teste'));assert.equal(options.redirect,'manual');
});
test('DESC rejects unsafe routes, redirects and reports offline explicitly',async()=>{
 assert.ok(create);let calls=0;const config={connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async()=>{calls++;return new Response('',{status:302,headers:{Location:'https://outside.example'}});}};
 const handler=create(config);
 for(const url of ['/api/disconnection/session','/api/disconnection/state?url=evil','/api/disconnection/photo/../secret','/api/disconnection/report.xlsx?month=2026-99']){const r=response();await handler(req('controller','GET',url),r);assert.equal(r.code,400);}
 assert.equal(calls,0);const redirect=response();await handler(req(),redirect);assert.equal(redirect.code,503);
 const offline=create({...config,fetchImpl:async()=>{throw new Error('connect failure');}});const r=response();await offline(req(),r);assert.equal(r.code,503);assert.match(r.body.error,/indisponível/);
});

test('DESC history accepts one ISO date and remains access-controlled',async()=>{
 const {allowedRoute}=require('../deploy/hostinger-web/disconnection-proxy');
 assert.equal(allowedRoute('GET','/api/disconnection/history?date=2026-10-09'),'/api/disconnection/history?date=2026-10-09');
 for(const url of ['/api/disconnection/history','/api/disconnection/history?date=2026-10-09&date=2026-10-10','/api/disconnection/history?date=2026-10-09&token=x','/api/disconnection/history?date=yesterday'])
  assert.throws(()=>allowedRoute('GET',url));
 let seen='';
 const handler=create({connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async(url)=>{seen=url;return new Response('{"batches":[],"view":"history"}',{headers:{'Content-Type':'application/json'}});}});
 const ok=response();await handler(req('controller','GET','/api/disconnection/history?date=2026-10-09'),ok);
 assert.equal(ok.code,200);assert.equal(seen,'https://relay.example/api/disconnection/history?date=2026-10-09');
 const unauthorized=response();await handler(req('viewer','GET','/api/disconnection/history?date=2026-10-09'),unauthorized);
 assert.equal(unauthorized.code,403);
});

test('manual serial endpoints require authenticated controller, CSRF and the safe allowlist',async()=>{
 const {allowedRoute}=require('../deploy/hostinger-web/disconnection-proxy');
 for(const route of ['serial-lookup','serial-apply']){
  assert.equal(allowedRoute('POST','/api/disconnection/'+route),'/api/disconnection/'+route);
  assert.throws(()=>allowedRoute('GET','/api/disconnection/'+route));
  assert.throws(()=>allowedRoute('POST','/api/disconnection/'+route+'?token=bad'));
  let calls=0;const handler=create({connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async()=>{calls++;return new Response('{"ok":true}',{headers:{'Content-Type':'application/json'}});}});
  const denied=response();await handler(req('viewer','POST','/api/disconnection/'+route),denied);assert.equal(denied.code,403);
  const stale=req('controller','POST','/api/disconnection/'+route);stale.headers={};const staleResponse=response();await handler(stale,staleResponse);assert.equal(staleResponse.code,403);assert.equal(calls,0);
  const ok=response();await handler(req('controller','POST','/api/disconnection/'+route),ok);assert.equal(ok.code,200);assert.equal(calls,1);
 }
});
test('manual tokens receive an opaque trusted binding that changes on a new DOMINIUM session',async()=>{
 const bodies=[];const handler=create({connection:()=>({origin:'https://relay.example',token:'a'.repeat(43)}),fetchImpl:async(_u,o)=>{bodies.push(JSON.parse(o.body));return new Response('{}');}});
 for(const session of ['first','new']){const request=req('controller','POST','/api/disconnection/serial-lookup');request.dominiumSession.csrf_hash=crypto.createHash('sha256').update(session).digest('hex');request.headers['x-csrf-token']=session;request.body.review_session='forged';await handler(request,response());}
 assert.match(bodies[0].review_session,/^[a-f0-9]{64}$/);assert.notEqual(bodies[0].review_session,bodies[1].review_session);assert.notEqual(bodies[0].review_session,'forged');
});

test('obsolete quick-tunnel review origins migrate to the permanent bridge without overriding explicit stable origins',()=>{
 const {resolveReviewOrigin}=require('../deploy/hostinger-web/disconnection-proxy');
 assert.equal(typeof resolveReviewOrigin,'function');
 assert.equal(resolveReviewOrigin('https://old.trycloudflare.com'),'https://dominium-import-bridge.jogador743.workers.dev');
 assert.equal(resolveReviewOrigin('https://private.example'),'https://private.example');
 assert.equal(resolveReviewOrigin('https://old.trycloudflare.com','https://explicit.example'),'https://explicit.example');
 assert.equal(resolveReviewOrigin('https://old.trycloudflare.com','https://another.trycloudflare.com'),'https://dominium-import-bridge.jogador743.workers.dev');
});
