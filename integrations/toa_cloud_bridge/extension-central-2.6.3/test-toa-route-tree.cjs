const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class FakeXHR {
  addEventListener() {}
  open() {}
  send() {}
}

const context = {
  console,
  URL,
  URLSearchParams,
  AbortController,
  Blob,
  setTimeout,
  clearTimeout,
  location: { href: 'https://clarobrasil.etadirect.com/', origin: 'https://clarobrasil.etadirect.com' },
  document: { querySelectorAll: () => [] },
  fetch: async () => ({ clone: () => ({ json: async () => ({}) }) }),
  XMLHttpRequest: FakeXHR,
};
context.window = context;

const source = fs.readFileSync(path.join(__dirname, 'toa-auto-export.js'), 'utf8');
vm.runInNewContext(source, context, { filename: 'toa-auto-export.js' });

const api = context.TNTOAAutoExport;
assert.ok(api, 'API da árvore não foi instalada');

api.observePayload({
  delta: {
    Provider: {
      33128: { pid: 33128, pname: 'NTL-DMV', external_id: 'BUCKET', parent_id: 0 },
      1439: { pid: 1439, pname: 'EDICARLOS DE LIRA SILVA', external_id: 'Z131568', parent_id: 33128 },
    },
  },
});

assert.deepEqual(
  JSON.parse(JSON.stringify(api.routeForProvider('1439'))),
  { name: 'NTL-DMV', providerId: '33128', source: 'Time.get:delta' },
);
assert.equal(api.treeStatus().buckets, 1);

// A completed search row can lack Provider details although Time.get knows it.
api.observePayload({trees: [{tree_updates: {
  66627: {z: 66627, n: 'TECNICO EXATO', e: 'Z657615', p: 33128, t: 5},
  777: {z: 777, n: '', e: 'ZEMPTY', p: 33128, t: 5},
}}]});
const mainSource = fs.readFileSync(path.join(__dirname, 'content-main.js'), 'utf8');
function actualFunction(name) {
  const start = mainSource.indexOf(`  function ${name}(`);
  assert.notEqual(start, -1);
  const end = mainSource.indexOf('\n  function ', start + 1);
  return mainSource.slice(start, end);
}
context.state = {providersByPid: new Map(), providersByExternalId: new Map()};
vm.runInNewContext(['firstText', 'sanitizeTechnicianName', 'rememberProviders',
  'resolveTechnicianForRow'].map(actualFunction).join('\n'), context);
const resolve = context.resolveTechnicianForRow;
assert.equal(resolve({}, {pid: 66627, external_id: 'Z657615'}, {}), 'TECNICO EXATO');
assert.equal(resolve({}, {pid: 66627, external_id: 'Z699388'}, {}), '');
assert.equal(resolve({}, {pid: 123, external_id: 'Z657615'}, {}), '');
assert.equal(resolve({}, {pid: 66627}, {}), '');
assert.equal(resolve({}, {pid: 777, external_id: 'ZEMPTY'}, {}), '');
assert.equal(resolve({}, {pid: 33128, external_id: 'BUCKET'}, {}), '');
assert.equal(resolve({}, {pid: 123, external_id: 'Z657615'}, {
  auto_routed_to_provider_id: 66627, auto_routed_to_provider_name: 'TECNICO ANTIGO',
}), '');
assert.equal(resolve({}, {pid: 123, external_id: 'Z123'}, {
  auto_routed_to_provider_id: 123, auto_routed_to_provider_name: 'TECNICO ROTEADO',
}), 'TECNICO ROTEADO');
assert.equal(resolve({delta: {Provider: {1439: {pid:1439, pname:'NOME DIRETO',
  external_id:'Z131568'}}}}, {pid:1439, external_id:'Z131568'}, {}), 'NOME DIRETO');
assert.equal(resolve({}, {pid: '66627', external_id: 'z657615'}, {}), 'TECNICO EXATO');
const returned = api.providerById('66627', 'Z657615');
returned.name = 'ALTERADO';
assert.equal(resolve({}, {pid:66627, external_id:'Z657615'}, {}), 'TECNICO EXATO');
console.log('test-toa-route-tree: ok');
