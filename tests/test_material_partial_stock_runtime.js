'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'),'utf8');
function extract(a,b) {
  const start = source.indexOf(a);
  const end = source.indexOf(b, start + a.length);
  assert.ok(start >= 0 && end > start, 'Missing function ' + a);
  return source.slice(start,end);
}
const js = [
  extract('function selectedMaterialIssues(', '\nfunction refreshMaterialControls('),
  extract('function materialValues()', '\nfunction expectedEquipmentType('),
].join('\n');

function run(rowsSpec, inventory) {
  const rows = rowsSpec.map(({code,quantity})=>({
    querySelector(s) {return {value:s === '.material-code' ? code : String(quantity)};}
  }));
  const ctx = vm.createContext({
    state:{materialInventory:inventory, materialEquivalenceConfirmed:true},
    elements:{materialRows:{querySelectorAll(){return rows;}}}
  });
  vm.runInContext(js + '\nthis.evaluate = {materialValues, selectedMaterialIssues,selectedMaterialAdjustments};',ctx);
  const result = ctx.evaluate;
  return {
    errors:[...result.selectedMaterialIssues()],
    adjusted:[...result.selectedMaterialAdjustments()].map(x=>({...x})),
    payload() {return Array.from(result.materialValues(),x=>({...x}));}
  };
}
const material=(code,stock,retorno)=>({
  code, name:'FIXADOR',stock_quantity:stock,
  ...(retorno===null?{}:{return_stock_quantity:retorno})
});
test('TOA 5 / tecnico 2 / RETORNO 1 => posta 3 e audita falta 2',()=>{
  const a=run([{code:'22060738',quantity:5}],[material('22060738',2,1)]);
  assert.deepEqual(a.errors,[]);
  assert.equal(a.adjusted[0].requested_quantity,5);
  assert.equal(a.adjusted[0].posted_quantity,3);
  assert.equal(a.adjusted[0].missing_quantity,2);
  assert.equal(a.payload()[0].quantity,3);
  assert.equal(a.payload()[0].requested_quantity,5);
});
test('sem saldo em OS seguinte => omite material; nao carrega debito',()=>{
  const a=run([{code:'22060738',quantity:5}],[material('22060738',0,0)]);
  assert.deepEqual(a.errors,[]);
  assert.equal(a.adjusted[0].missing_quantity,5);
  assert.deepEqual(a.payload(),[]);
});
test('saldo integral => posta 5',()=>{
  const a=run([{code:'22060738',quantity:5}],[material('22060738',4,1)]);
  assert.deepEqual(a.errors,[]);
  assert.equal(a.payload()[0].quantity,5);
});
test('RETORNO nao consultado => impede presumir saldo zero',()=>{
  const a=run([{code:'22060738',quantity:5}],[material('22060738',2,null)]);
  assert.match(a.errors.join(' '),/RETORNO nao consultado/);
  assert.throws(()=>a.payload(),/Baixa bloqueada/);
});
test('duas linhas => envia somente quantidade disponivel',()=>{
  const a=run([{code:'22060738',quantity:5},{code:'22025321',quantity:2}],
    [material('22060738',1,0),material('22025321',0,2)]);
  assert.deepEqual(a.errors,[]);
  assert.deepEqual(a.payload().map(v=>v.quantity),[1,2]);
});
test('material repetido => impede duplicidade',()=>{
  const a=run([{code:'22060738',quantity:2},{code:'22060738',quantity:1}],
    [material('22060738',3,0)]);
  assert.match(a.errors.join(' '),/duplicado/);
});
