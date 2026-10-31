'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','static','backlog-analysis.js'),'utf8');
const begin=source.indexOf('    const files=[];\n    let totalBytes=0;');
const end=source.indexOf('      const result=await new Promise',begin);
assert.ok(begin>=0&&end>begin,'Cannot locate upload validation');
// Execute the actual production checks, not a copy of their thresholds.
const check=new Function('chosen',source.slice(begin,end)+'\n    }\n    return totalBytes;');
const file=(name,size)=>({name,size});
test('6.6 MiB official upload is no longer rejected just for size',()=>{
  const size=6921172;
  assert.equal(check([file('NTL_TOA_20261031.xlsx',size)]),size);
});
test('per-file size exceeding 8 MiB is rejected with actionable explanation',()=>{
  assert.throws(()=>check([file('NTL_TOA.xlsx',8*1024*1024+1)]),/8 MiB/);
});
test('batch cannot exceed 15 MiB while proxy has a 22 MiB body limit',()=>{
  assert.throws(()=>check([file('NTL_A.xlsx',8*1024*1024),file('NTL_B.xlsx',8*1024*1024)]),/15 MiB/);
});
test('up to 5 smaller files fit into a single request',()=>{
  const chosen=[1,2,3,4,5].map(i=>file('NTL_'+i+'.csv',2*1024*1024));
  assert.equal(check(chosen),10*1024*1024);
});
test('unsupported and empty files are rejected explicitly',()=>{
  assert.throws(()=>check([file('note.txt',100)]),/csv ou .xlsx/);
  assert.throws(()=>check([file('NTL_empty.csv',0)]),/vazio/);
});
test('the original route/matching action remains present',()=>{
  assert.match(source,/post\("\/api\/backlog\/year\/routes",\{files\}\)/);
  assert.match(source,/backlogCompare/);
});
