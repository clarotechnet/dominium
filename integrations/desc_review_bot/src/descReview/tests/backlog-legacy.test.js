'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {prepareBacklogDescReview,historyForContract}=require('../backlogLegacy');
const now=Date.parse('2026-11-11T17:20:00Z');
const stamp=new Date(now).toISOString();
const contract='1231232', serial='AB123456789';
const atlas={
  enderecaveis_negrito:[serial],serial_baixavel:serial,serial_encontrado:true,
  modelo_equipamento:'DECODER',historico:[{numero_contrato:contract,estado:'Cliente'}]
};
function input(extra={}){
  return {
    contract,profile:'natal',
    toaLookup:{ok:true,status:'not_found',contract,profile_key:'natal',checked_at:stamp},
    imperium:{ok:true,confirmed:true,searched:true,source:'open_orders_no_match',
      contract,profile_key:'natal',checked_at:stamp,orders:[]},
    photos:[{message_id:'photo-1',contract,serial,verified_label:true}],
    atlas:[atlas],
    historicalRows:[{contract,profile_key:'natal',historical_code:'106',
      historical_date:'2026-10-11',os_number:'1112223333'}],
    routeRows:[],
    technician:{name:'TECNICO TESTE',imperium_id:'42',profiles:['natal']},
    ...extra
  };
}
test('legacy DESC may only propose existing native RETIRADA FORA TOA flow',()=>{
  const out=prepareBacklogDescReview(input(),now);
  assert.equal(out.state,'review');
  assert.equal(out.create_os,true);
  assert.equal(out.os_number_preview,contract+' '+contract);
  assert.equal(out.service,'RETIRADA FORA TOA');
  assert.equal(out.requires_human_approval,true);
  assert.equal(out.executed,false);
  assert.deepEqual(out.plan.operations.map(x=>x.code),['430']);
  assert.equal(out.plan.operations[0].materials.length,0);
  assert.deepEqual(out.plan.operations[0].outgoing.map(x=>x.serial),[serial]);
  assert.equal(out.history.length,1);
});
test('TOA result wins over historical imported row; never create OS',()=>{
  const out=prepareBacklogDescReview(input({toaLookup:{...input().toaLookup,status:'found'}}),now);
  assert.equal(out.state,'use_toa');
  assert.equal(out.create_os,false);
  assert.equal(out.executed,false);
});
test('missing, stale, or failed TOA lookup never means outside TOA',()=>{
  for(const toaLookup of [null,{ok:false,status:'not_found',contract,profile_key:'natal',checked_at:stamp},
    {...input().toaLookup,checked_at:new Date(now-600000).toISOString()},
    {...input().toaLookup,contract:'9999999'},
    {...input().toaLookup,status:'failed'}]){
    const out=prepareBacklogDescReview(input({toaLookup}),now);
    assert.equal(out.state,'blocked');
    assert.equal(out.create_os,false);
  }
});
test('open Imperium OS and stale Imperium both block duplicate creation',()=>{
  for(const imperium of [
    {...input().imperium,source:'imperium_detail',orders:[{num_os:'1234567890',id_os:99,contract,installer_id:42,status:'EM CAMPO'}]},
    {...input().imperium,checked_at:new Date(now-600000).toISOString()},
    {...input().imperium,searched:false},
    {...input().imperium,source:'imperium_detail'}
  ]){
    const out=prepareBacklogDescReview(input({imperium}),now);
    assert.equal(out.create_os,false);
    assert.equal(out.state,'blocked');
  }
});
test('photographed serial and Atlas history must match contract',()=>{
  for(const extra of [
    {photos:[]},{photos:[{message_id:'a',contract,serial:'WRONG',verified_label:true}]},
    {atlas:[{...atlas,historico:[{numero_contrato:'7654321'}]}]},
    {photos:[{message_id:'a',contract,serial,verified_label:false}]},
    {atlas:[]}
  ]){
    const out=prepareBacklogDescReview(input(extra),now);
    assert.equal(out.state,'blocked');
    assert.equal(out.create_os,false);
  }
});
test('five TOA routes have precedence over claimed no TOA',()=>{
  const out=prepareBacklogDescReview(input({routeRows:[{contract,profile_key:'natal'}]}),now);
  assert.equal(out.state,'blocked');
  assert.equal(out.create_os,false);
});
test('duplicate historical events remain separate and cannot be converted to current OS state',()=>{
  const rows=[{contract,profile_key:'natal',historical_code:'106',os_number:'11111'},
    {contract,profile_key:'natal',historical_code:'430',os_number:'11111'},
    {contract:'7654321',profile_key:'natal',historical_code:'106',os_number:'22222'}];
  assert.deepEqual(historyForContract(rows,contract,'natal').map(x=>x.code),['106','430']);
  const out=prepareBacklogDescReview(input({historicalRows:rows}),now);
  assert.equal(out.state,'review');
  assert.equal(out.history.length,2);
});
