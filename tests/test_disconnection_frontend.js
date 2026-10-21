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
test('photo zoom preserves the pointed label and stays within 100–400%', () => {
  const bounds = {width:600,height:400,imageWidth:600,imageHeight:400};
  const zoomed = ui.photoTransform({scale:1,x:0,y:0},2,{x:180,y:120},bounds);
  assert.deepEqual(zoomed,{scale:2,x:-180,y:-120});
  assert.equal((180-zoomed.x)/zoomed.scale,180);
  assert.equal((120-zoomed.y)/zoomed.scale,120);
  assert.equal(ui.photoTransform(zoomed,20,{x:300,y:200},bounds).scale,4);
  assert.deepEqual(ui.photoTransform(zoomed,0,{x:300,y:200},bounds),{scale:1,x:0,y:0});
});
test('small photos remain centered until zoom makes them exceed the viewport', () => {
  assert.deepEqual(ui.photoTransform({scale:1,x:200,y:150},2,{x:300,y:200},{width:600,height:400,imageWidth:200,imageHeight:100}),{scale:2,x:100,y:100});
});

test('same contract and resource groups all photos without mixing other technicians', () => {
  const msg=(id,photo)=>({id,photo});
  const common={profile:'natal',group:'grupo1',sender:'tecnico1',contract:'1234567',state:'review'};
  const rows=[
    {...common,id:'a',messages:[msg('1','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg')]},
    {...common,id:'b',messages:[msg('2','bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jpg'),msg('3','cccccccc-cccc-cccc-cccc-cccccccccccc.jpg')]},
    {...common,id:'c',sender:'outro-tecnico',messages:[msg('4','dddddddd-dddd-dddd-dddd-dddddddddddd.jpg')]},
    {...common,id:'d',contract:'7654321',messages:[]},
    {...common,id:'e',profile:'recife',messages:[]},
  ];
  const groups=ui.contractGroups(rows);
  assert.equal(groups.length,4);
  const grouped=groups.find(x=>x.contract==='1234567'&&x.batches.length===2);
  assert.ok(grouped);
  assert.equal(grouped.photoCount,3);
  assert.deepEqual(grouped.batches.map(x=>x.id),['a','b']);
  assert.equal(grouped.messages[1].batch_id,'b');
});
