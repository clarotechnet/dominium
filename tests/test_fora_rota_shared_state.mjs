import test from 'node:test';
import assert from 'node:assert/strict';
import {profileForCity,cleanRecords,mergeLegacy,validateScope} from '../supabase/functions/dominium-fora-rota-state/core.mjs';
test('city mapping is exact, Paulista not operational',()=>{
  assert.equal(profileForCity('NATAL / PARNAMIRIM'),'natal');
  assert.equal(profileForCity('Jaboatão dos Guararapes'),'recife');
  assert.equal(profileForCity('PAULISTA'),'');
  assert.equal(profileForCity('PAULISTA / RECIFE'),'');
  assert.throws(()=>validateScope('unassigned','claro'));
});
test('strict scoped storage rejects other cities and malformed contracts',()=>{
  assert.throws(()=>cleanRecords('natal','claro',[{contract:'123456',city:'Fortaleza'}]));
  assert.throws(()=>cleanRecords('recife','claro',[{contract:'123456',city:'Paulista'}]));
  assert.throws(()=>cleanRecords('natal','clean106',['1abc23']));
  assert.deepEqual(cleanRecords('natal','clean106',['123456','012345','123456']),['012345','123456']);
  assert.equal(cleanRecords('natal','claro',[{contract:'123456',city:'Natal',secret:'not stored'}])[0].secret,undefined);
});
test('sent history merges without losing existing contracts or confirmed return',()=>{
  const old=cleanRecords('natal','legacy_sent',[{contract:'123456',city:'Natal',lastReturnCode:'430',returnedAt:'2026-11-20T12:00:00Z',updatedAt:'2026-11-20T12:00:00Z',lastMessage:'Retorno'},{contract:'234567',city:'Natal'}]);
  const next=cleanRecords('natal','legacy_sent',[{contract:'123456',city:'Natal',updatedAt:'2026-11-21T12:00:00Z',status:'aguardando_tecnico'}]);
  const merged=mergeLegacy(old,next);
  assert.equal(merged.length,2);assert.equal(merged[0].lastReturnCode,'430');assert.equal(merged[0].lastMessage,'Retorno');
  assert.equal(cleanRecords('unassigned','legacy_sent',[{contract:'345678'}]).length,1);
});
test('same contract in different cities stays distinct; ambiguous duplicate rejected',()=>{
  assert.equal(cleanRecords('natal','claro',[{contract:'123456',city:'Natal'},{contract:'123456',city:'Parnamirim'}]).length,2);
  assert.throws(()=>cleanRecords('natal','claro',[{contract:'123456',city:'Natal',name:'A'},{contract:'123456',city:'Natal',name:'B'}]));
});
