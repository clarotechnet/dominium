'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { allowedOperationalRead } = require('../deploy/hostinger-web/operational-policy');
const { resolveOperationalRead } = require('../deploy/hostinger-web/operational-relay');
const { allowedToaLookup } = require('../deploy/hostinger-web/operational-policy');
const { restorePrivateJsonContentType } = require('../deploy/hostinger-web/operational-relay');
const privateConnection = () => ({token:'x'.repeat(43)});
const req = (method, originalUrl, role = 'viewer') => ({
  method, originalUrl, dominiumSession:{id:'fixture'},
  dominiumUser:{id:5, username:'viewer.test', role},
});

test('TOA lookup uses the private bridge only for the exact scoped read action', () => {
  for (const profile of ['natal','fortaleza','mossoro','recife']) {
    const target='/api/toa-live/lookup?profile='+profile;
    assert.equal(allowedToaLookup('POST',target),true);
    for (const role of ['admin','controller']) {
      const request=req('POST',target,role);
      request.headers={'content-type':'application/json',cookie:'private','x-csrf-token':'private'};
      const result=resolveOperationalRead(request,privateConnection);
      assert.equal(result.url,'https://dominium-import-bridge.jogador743.workers.dev'+target);
      restorePrivateJsonContentType(request,result.headers,'{"query":"4321295"}');
      assert.equal(result.headers['content-type'],'application/json');
      assert.equal(result.headers.cookie,undefined);
      assert.equal(result.headers['x-csrf-token'],undefined);
    }
    assert.throws(()=>resolveOperationalRead(req('POST',target,'viewer'),privateConnection),/operational_session_required/);
    assert.throws(()=>resolveOperationalRead({...req('POST',target,'admin'),dominiumSession:null},privateConnection),/operational_session_required/);
  }
  for (const target of ['/api/toa-live/connect?profile=natal','/api/toa-live/lookup',
    '/api/toa-live/lookup?profile=unknown','/api/toa-live/lookup?profile=natal&profile=recife',
    '/api/toa-live/lookup?profile=natal&url=evil','/api/toa-live/%6cookup?profile=natal',
    '/api/toa-live/../toa-live/lookup?profile=natal','/api/toa-live/lookup?profile=natal#x',
    '//evil/api/toa-live/lookup?profile=natal']) {
    assert.equal(allowedToaLookup('POST',target),false,target);
  }
  assert.equal(allowedToaLookup('GET','/api/toa-live/lookup?profile=natal'),false);
});

test('only explicit, safe GET routes may access the internal Windows API', () => {
  for(const route of [
    '/api/orders?date=2026-10-21&profile=natal',
    '/api/toa-contracts?profile=natal&date=2026-10-21',
    '/api/toa-live/status',
    '/api/orders/123/installer?profile=natal',
    '/api/toa-automation',
    '/api/auto-improductive-close',
    '/api/monitor/snapshot',
    '/api/serials/consult?serials=SERIAL000000&mode=analitico',
    '/api/imperium-official/stocks?profile=natal',
    '/api/imperium-official/stocks/123/items?profile=fortaleza',
  ]) assert.equal(allowedOperationalRead('GET',route),true,route);
  for(const route of [
    '/api/auth/session', '/api/auth/users', '/.env', '/api/imports/commit',
    '/api/operational/contracts/evil', '/api/toa-automation/run',
    'https://example.org/api/orders', '//evil/api/orders',
    '/api/%6f%72%64%65%72%73',
    '/api/imperium-official/stocks/123',
    '/api/imperium-official/stocks/123/commit',
  ]) assert.equal(allowedOperationalRead('GET',route),false,route);
  assert.equal(allowedOperationalRead('POST','/api/orders'),false);
  assert.equal(allowedOperationalRead('POST','/api/serials/consult'),false);
  assert.equal(allowedOperationalRead('DELETE','/api/toa-contracts'),false);
});

test('private relay is available only to authenticated users with a valid server secret', () => {
  for(const role of ['viewer','admin','controller']) {
    const out = resolveOperationalRead(req('GET','/api/toa-contracts?profile=natal',role),privateConnection);
    assert.match(out.url,/^https:\/\/dominium-import-bridge\.jogador743\.workers\.dev\/api\/toa-contracts/);
    assert.equal(out.headers.authorization,'Bearer '+'x'.repeat(43));
    assert.equal(out.headers['x-dominium-role'],role);
  }
  assert.equal(resolveOperationalRead(req('POST','/api/toa-automation'),privateConnection),null);
  assert.throws(()=>resolveOperationalRead({...req('GET','/api/orders'),dominiumSession:null},privateConnection),/operational_session_required/);
  assert.throws(()=>resolveOperationalRead(req('GET','/api/orders','unknown'),privateConnection),/operational_session_required/);
  assert.throws(()=>resolveOperationalRead(req('GET','/api/orders'),()=>({token:''})),/operational_private_relay_not_configured/);
});

const { allowedConfrontRoute } = require('../deploy/hostinger-web/confront-policy');

test('confront transport only allows explicit report jobs and no inventory writes', () => {
  for(const route of ['/api/confront/status','/api/confront/jobs',
    '/api/confront/jobs/'+'a'.repeat(32),
    '/api/confront/jobs/'+'a'.repeat(32)+'/export']) {
    assert.equal(allowedConfrontRoute('GET',route),true,route);
  }
  assert.equal(allowedConfrontRoute('POST','/api/confront/jobs'),true);
  for(const target of ['/api/stock/serial-owner','/api/confront/jobs/../../.env',
    '/api/confront/jobs/'+'z'.repeat(32),
    '/api/confront/jobs?url=evil',
    '//evil/api/confront/jobs',
    '/api/confront/%6aobs']) {
    assert.equal(allowedConfrontRoute('GET',target),false,target);
  }
  assert.equal(allowedConfrontRoute('POST','/api/confront/status'),false);
  assert.equal(allowedConfrontRoute('POST','/api/confront/jobs/'+'a'.repeat(32)),false);
});

test('authenticated admin and controller may create; viewers may not inspect confront data', () => {
  for(const role of ['admin','controller']) {
    const out=resolveOperationalRead(req('POST','/api/confront/jobs',role),privateConnection);
    assert.equal(out.headers['x-dominium-role'],role);
    assert.equal(out.headers['x-dominium-actor'],'user-5');
    assert.match(out.url,/\/api\/confront\/jobs$/);
  }
  assert.throws(()=>resolveOperationalRead(req('GET','/api/confront/jobs','viewer'),privateConnection),
    /operational_session_required/);
  assert.equal(resolveOperationalRead(req('POST','/api/orders','controller'),privateConnection),null);
});
