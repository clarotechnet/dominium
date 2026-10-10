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
