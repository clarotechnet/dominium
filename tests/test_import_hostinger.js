'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
let create;
try { ({createImportMiddleware: create} = require('../deploy/hostinger-web/import-proxy')); }
catch (error) { if (error.code !== 'MODULE_NOT_FOUND') throw error; }
const token = 't'.repeat(43);
function request(method = 'POST', url = '/api/imports/preview', role = 'controller') {
  return {method, originalUrl: url, headers: {'x-csrf-token': 'fixture', cookie: 'private'},
    dominiumUser: {id: 8, role, display_name: 'Operador teste'},
    dominiumSession: {csrf_hash: crypto.createHash('sha256').update('fixture').digest('hex')},
    body: {target: 'rn', filename: 'Atividades-FTZ-DMV_ADM_15_10_26.csv', content_base64: 'YQ==', approved_source_hash: 'original'}};
}
function response() { return {code: 200, headers: {}, status(n) {this.code=n; return this;},
  set(k,v) {this.headers[k]=v;return this;}, json(v) {this.body=v;return this;}, send(v) {this.body=v;return this;}}; }
const connection = () => ({token});
test('imports reject anonymous, viewers and invalid csrf without forwarding', async () => {
  assert.equal(typeof create, 'function'); let calls=0;
  const handler=create({connection, fetchImpl:async()=>{calls++;}});
  for (const role of ['', 'viewer']) {const r=response();await handler(request('POST',undefined,role),r);assert.equal(r.code,role?403:401);}
  const req=request();req.headers={};const r=response();await handler(req,r);assert.equal(r.code,403);assert.equal(calls,0);
});
test('imports preserve filename city hints, exact CSV and approval fields with private server authentication', async () => {
  assert.equal(typeof create, 'function');let seen;
  const req=request('POST','/api/imports/commit');req.body.content_base64='A'.repeat(400000);
  const handler=create({connection, fetchImpl:async(url,opts)=>{seen={url,opts};return new Response('{"ok":true,"imported":2}');}});
  const r=response();await handler(req,r);assert.equal(r.code,200);
  assert.match(seen.url,/^https:\/\/dominium-import-bridge\.[a-z0-9]+\.workers\.dev\/api\/imports\/commit$/);
  assert.deepEqual(JSON.parse(seen.opts.body),req.body);
  assert.equal(seen.opts.headers.Authorization,'Bearer '+token);
  assert.equal(seen.opts.headers.Cookie,undefined);assert.equal(seen.opts.headers['X-Dominium-Role'],'controller');
  assert.equal(seen.opts.redirect,'manual');
});
test('imports reject unrelated routes and untrusted query parameters', async()=>{
  assert.equal(typeof create, 'function');let calls=0;const handler=create({connection,fetchImpl:async()=>{calls++;}});
  for(const [method,url] of [['POST','/api/close'],['GET','/api/imports/commit'],['POST','/api/imports/preview?url=evil'],['GET','/api/import-history?profile=natal&url=evil']]){
    const r=response();await handler(request(method,url),r);assert.equal(r.code,400);
  }assert.equal(calls,0);
});
test('imports return runtime validation and history statuses without treating them as connection errors',async()=>{
  assert.equal(typeof create, 'function');const handler=create({connection,fetchImpl:async()=>new Response('{"ok":false,"error":"CSV invalido"}',{status:400,headers:{'content-type':'application/json'}})});
  const r=response();await handler(request(),r);assert.equal(r.code,400);assert.match(r.body.toString(),/CSV invalido/);
});
test('a failed or redirected commit is never retried and reports uncertain outcome',async()=>{
  assert.equal(typeof create, 'function');
  for(const mode of ['offline','redirect']) {let calls=0;
    const handler=create({connection,fetchImpl:async()=>{calls++;if(mode==='offline')throw new Error('lost response');return new Response('',{status:302});}});
    const r=response();await handler(request('POST','/api/imports/commit'),r);
    assert.equal(calls,1);assert.equal(r.code,502);assert.equal(r.body.outcome_unknown,true);assert.match(r.body.error,/histórico/i);
  }
});

test('valid import history queries are preserved and missing private config fails closed',async()=>{
 assert.equal(typeof create,'function');let calls=0;
 const r=response();await create({connection:()=>({}),fetchImpl:async()=>{calls++;}})(request('GET','/api/import-targets'),r);
 assert.equal(r.code,502);assert.equal(calls,0);
 let seen;const h=create({connection,fetchImpl:async(url)=>{seen=url;return new Response('{"items":[]}');}});
 const out=response();await h(request('GET','/api/import-history?profile=fortaleza&date=2026-10-15&limit=120'),out);
 assert.equal(out.code,200);assert.match(seen,/import-history\?profile=fortaleza&date=2026-10-15&limit=120$/);
});
