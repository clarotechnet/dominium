'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
let ui;
try { ui = require('../static/disconnection'); } catch (e) { if (e.code !== 'MODULE_NOT_FOUND') throw e; }
test('filters contracts and technicians without mixing batches', () => {
  assert.ok(ui, 'DESC module absent');
  const rows = [{id:'one',contract:'1234567',technician:{name:'José'},state:'review'}, {id:'two',contract:'7654321',technician:{name:'Ana'},state:'blocked'}];
  assert.deepEqual(ui.visibleBatches(rows,{search:'jose',state:'all'}).map(x=>x.id), ['one']);
  assert.deepEqual(ui.visibleBatches(rows,{search:'7654321',state:'blocked'}).map(x=>x.id), ['two']);
});
test('simulated results never appear as confirmed closes', () => {
  assert.ok(ui, 'DESC module absent');
  assert.equal(ui.stateLabel('simulated'), 'Simulada');
  assert.equal(ui.stateLabel('executed'), 'Baixa confirmada');
});
test('photo URLs and displayed data cannot inject paths or HTML', () => {
  assert.ok(ui, 'DESC module absent');
  assert.equal(ui.photoUrl('../private.txt'), '');
  assert.equal(ui.photoUrl('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg'), '/api/disconnection/photo/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg');
  assert.equal(ui.escape('<script>'), '&lt;script&gt;');
});
