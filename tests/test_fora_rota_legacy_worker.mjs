import test from 'node:test';
import assert from 'node:assert/strict';
import {sync} from '../integrations/fora-rota-legacy-sync/worker.mjs';

test('D1 sync uses indexed columns, retains history and pages safely',async()=>{
 const originalFetch=globalThis.fetch;
 const sent=[],queries=[];
 const rows=Array.from({length:251},(_,i)=>({
  contract:String(100000+i),city:'natal_parnamirim',city_label:'Natal/Parnamirim',
  technician:'T1',sent_date:'2026-11-22',sent_at:'2026-11-22T13:00:00Z',
  status:'retornado_pelo_tecnico',last_return_code:'430',
  returned_at:'2026-11-23T13:00:00Z',returned_by_technician:'T2',
  group_id:'group1',group_name:'Natal',last_message:'test',
  return_count:2,updated_at:'2026-11-23T13:00:00Z',
  data_json:JSON.stringify({status:'aguardando_tecnico',returnCount:1,returnHistory:[{code:'430'}]})
 }));
 const env={SYNC_TOKEN:'a'.repeat(48),DB:{prepare(sql){
  queries.push(sql);
  return {bind(cursor){return {async all(){return {results:rows.filter(r=>r.contract>cursor).slice(0,250)}}}}};
 }}};
 globalThis.fetch=async(url,options)=>{
  assert.equal(options.method,'POST');
  assert.equal(options.redirect,'error');
  const body=JSON.parse(options.body);
  sent.push(...body.records);
  return new Response(JSON.stringify({ok:true,received:body.records.length,changed:body.records.length}),{status:200});
 };
 try{
  const result=await sync(env,{full:true});
  assert.equal(result.read,251);
  assert.equal(sent.length,251);
  assert.equal(queries.length,2);
  assert.ok(queries.every(q=>q.startsWith('SELECT ')&&q.includes('returned_by_technician')));
  assert.equal(sent[0].status,'retornado_pelo_tecnico');
  assert.equal(sent[0].lastReturnCode,'430');
  assert.equal(sent[0].returnedByTechnician,'T2');
  assert.equal(sent[0].technician,'T1');
  assert.equal(sent[0].returnCount,2);
  assert.deepEqual(sent[0].returnHistory,[{code:'430'}]);
 }finally{globalThis.fetch=originalFetch;}
});
