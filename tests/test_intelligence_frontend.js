'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
function section(start, end) {
  const from = source.indexOf(start);
  assert.notEqual(from, -1);
  return source.slice(from, source.indexOf(end, from));
}
function setup(request) {
  const elements = new Proxy({}, {get(target, key) {
    return target[key] ||= {textContent: '', innerHTML: '', value: '', dataset: {}, classList: {toggle() {}}, style: {setProperty() {}}};
  }});
  const state = {intelligence: null, intelligenceLoading: false, healthCheck: null, healthLoading: false};
  const context = vm.createContext({state, elements, request, showToast() {}, localDate: () => '2026-10-10',
    escapeHtml: value => String(value), formatDateTime: value => String(value), normalize: value => String(value), formatOperationalDuration: value => `${value || 0}s`});
  vm.runInContext(section('function renderHealthCheck()', 'function serialAuditStatusLabel(')
    + section('async function loadIntelligence(', 'async function runSerialAudit('), context);
  return {context, state, elements};
}
test('Node health results render base labels, measured latency and timestamp without invented endpoints', async () => {
  const {context, elements} = setup(async () => ({online: 1, offline: 1, results: [
    {label: 'Natal', online: true, elapsed_ms: 27}, {label: 'Recife', online: false, elapsed_ms: 4010},
  ], generated_at: '2026-10-10T13:00:00Z'}));
  await context.loadHealthCheck();
  assert.match(elements.healthBaseGrid.innerHTML, /Natal/);
  assert.match(elements.healthBaseGrid.innerHTML, /27 ms/);
  assert.match(elements.healthBaseGrid.innerHTML, /Recife/);
  assert.doesNotMatch(elements.healthBaseGrid.innerHTML, /undefined|null/);
  assert.match(elements.healthCheckedAt.textContent, /2026-10-10T13:00:00Z/);
});
test('Python health contract remains supported', async () => {
  const {context, elements} = setup(async () => ({bases: [{label: 'Natal', host: 'example.test', port: 7777, online: true, latency_ms: 17}], checked_at: '2026-10-10T14:00:00Z'}));
  await context.loadHealthCheck();
  assert.match(elements.healthBaseGrid.innerHTML, /example.test:7777/);
  assert.match(elements.healthBaseGrid.innerHTML, /17 ms/);
  assert.equal(elements.healthNavStatus.textContent, '1 bases online');
});
test('missing health results do not claim successful connectivity', async () => {
  const {context, elements} = setup(async () => ({}));
  await context.loadHealthCheck();
  assert.match(elements.healthBaseGrid.innerHTML, /Nenhuma base retornada/);
  assert.equal(elements.healthNavStatus.dataset.tone, 'neutral');
  assert.doesNotMatch(elements.healthCheckedAt.textContent, /undefined/);
});
test('unavailable intelligence explains deployment capability and suppresses false zero metrics and export', async () => {
  const {context, elements} = setup(async () => {throw Object.assign(new Error('404'), {status: 404});});
  await context.loadIntelligence();
  assert.match(elements.intelligenceGenerated.textContent, /indisponivel nesta implantacao/);
  assert.equal(elements.intelligencePdf.disabled, true);
  assert.equal(elements.intelligenceSuccessRate.textContent, '—');
  assert.equal(elements.intelligenceConfirmed.textContent, '—');
  assert.match(elements.basePerformanceList.innerHTML, /indisponiveis/);
});
test('successful intelligence recovers after unsupported deployment and preserves the last reading on transient failure', async () => {
  let result = Object.assign(new Error('Unavailable'), {status: 501});
  const {context, elements, state} = setup(async () => {if (result instanceof Error) throw result;return result;});
  await context.loadIntelligence();
  assert.equal(elements.intelligencePdf.disabled, true);
  result = {summary: {success_rate: 100, confirmed: 3}, days: 1, end_date: '2026-10-10', generated_at: '2026-10-10T14:00:00Z', bases: [], technicians: []};
  await context.loadIntelligence();
  assert.equal(elements.intelligenceConfirmed.textContent, '3');
  assert.equal(elements.intelligencePdf.disabled, false);
  assert.equal(state.intelligenceError, '');
  result = Object.assign(new Error('Temporary'), {status: 503});
  await context.loadIntelligence();
  assert.equal(elements.intelligenceConfirmed.textContent, '3');
  assert.match(elements.intelligenceGenerated.textContent, /2026-10-10T14:00:00Z.*Nao foi possivel atualizar/);
});
