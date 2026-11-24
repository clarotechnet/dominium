import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeSync} from '../supabase/functions/dominium-fora-rota-legacy-sync/merge.mjs';
test('older sent record cannot erase a confirmed return or existing records',()=>{
 const old=[{contract:'123456',lastReturnCode:'430',returnedAt:'2026-11-23T10:00:00Z',updatedAt:'2026-11-23T10:00:00Z',returnHistory:[{code:'430',returnedAt:'2026-11-23T10:00:00Z'}]},{contract:'234567'}];
 const r=mergeSync(old,[{contract:'123456',updatedAt:'2026-11-22T10:00:00Z',lastReturnCode:'',status:'aguardando_tecnico'}]);
 assert.equal(r.records.length,2);assert.equal(r.records[0].lastReturnCode,'430');assert.equal(r.records[0].returnCount,1);assert.equal(mergeSync(r.records,[]).changed,0);
});
test('new return preserves local send metadata and repeated sync is idempotent',()=>{
 const old=[{contract:'123456',city:'NATAL',source:'dominium',technician:'T1',sentAt:'2026-11-23T10:00:00Z',updatedAt:'2026-11-23T10:00:00Z'}];
 const incoming=[{contract:'123456',city:'natal_parnamirim',technician:'A DEFINIR',source:'bot',lastReturnCode:'430',returnedAt:'2026-11-23T12:00:00Z',updatedAt:'2026-11-23T12:00:00Z',returnHistory:[{code:'430',message:'ok'}],status:'retornado_pelo_tecnico'}];
 const r=mergeSync(old,incoming);assert.equal(r.changed,1);assert.equal(r.records[0].technician,'T1');assert.equal(r.records[0].source,'dominium');assert.equal(r.records[0].lastReturnCode,'430');
 assert.equal(mergeSync(r.records,[{...incoming[0],returnHistory:[{message:'ok',code:'430'}]}]).changed,0);
});
test('same-time conflicting codes stay preserved for review',()=>{
 const old=[{contract:'123456',lastReturnCode:'430',returnedAt:'2026-11-23T12:00:00Z'}];
 const r=mergeSync(old,[{contract:'123456',lastReturnCode:'106',returnedAt:'2026-11-23T12:00:00Z'}]);
 assert.equal(r.conflicts,1);assert.equal(r.records[0].lastReturnCode,'430');
});
test('new records append without deleting earlier records',()=>{
 const r=mergeSync([{contract:'123456'}],[{contract:'234567'}]);assert.equal(r.records.length,2);assert.equal(r.changed,1);
});
