'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { allowedOperationalRead } = require('../deploy/hostinger-web/operational-policy');
const { resolveOperationalRead } = require('../deploy/hostinger-web/operational-relay');
const privateConnection = () => ({token:'x'.repeat(43)});
const req = (method, originalUrl, role = 'viewer') => ({
  method, originalUrl, dominiumSession:{id:'fixture'},
  dominiumUser:{id:5, username:'viewer.test', role},
});

test('only explicit, safe GET routes may access the internal Windows API', () => {
  for(const route of [
    '/api/orders?date=2026-10-21&profile=natal',
    '/api/toa-contracts?profile=natal&date=2026-10-21',
    '/api/toa-live/status',
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
