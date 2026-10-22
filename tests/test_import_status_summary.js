const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.resolve(__dirname, '../static/app.js'), 'utf8');
const extracted = source.match(/function importOutcomeCounts\(orders\) \{[\s\S]*?\n\}\s*function importOutcomeSummary\(orders\) \{[\s\S]*?\n\}/);
if (!extracted) throw new Error('Missing import summary helpers');
const ctx = vm.createContext({});
vm.runInContext(extracted[0] + '\nthis.count=importOutcomeCounts;this.describe=importOutcomeSummary;',ctx);
test('separates created, updated, registered, and unresolved orders',()=>{
  const rows=[
    ...Array.from({length:22},()=>({import_status:'IMPORTADA COM SUCESSO',imported:true})),
    ...Array.from({length:114},()=>({import_status:'DATA/INSTALADOR ATUALIZADO',imported:false})),
    ...Array.from({length:7},()=>({import_status:'OS JÁ CADASTRADA',imported:false})),
  ];
  const result=ctx.count(rows);
  assert.deepEqual({...result},{created:22,updated:114,existing:7,unresolved:0});
  assert.equal(ctx.describe(rows),'22 importadas como novas; 114 atualizadas; 7 ja cadastradas');
});
test('does not mistake unknown outcomes for successful imports',()=>{
  const counts=ctx.count([{import_status:'incomplete_order_dataset',imported:false},{import_status:'',imported:false}]);
  assert.equal(counts.unresolved,2);
  assert.match(ctx.describe([{import_status:'timeout'}]),/1 sem resultado confirmado/);
});
test('empty file yields all zero, with no false failures',()=>{
  assert.equal(ctx.count([]).unresolved,0);
});
