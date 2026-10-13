'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {createDescReview}=require('../server');
const photo='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg';
test('manual HTTP lookup/apply enforce login and CSRF, preserve photo and never execute a close',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'desc-manual-http-'));
 const review=createDescReview({directory,groups:{g:{profile:'natal'}},technicians:{t:{name:'T',imperium_id:'42'}},now:()=>1000,autoStart:false,lookupSerials:async()=>({resultadosAtlas:[{resultado:{serial_baixavel:'ABC123456789',enderecaveis_negrito:['ABC123456789'],tipo_equipamento:'EMTA',historico:[{numero_contrato:'3902235'}]}}]})});
 const batch=review.store.ingest({id:'photo',group:'g',sender:'t',contract:'3902235',photo,photo_reading:{stage:'no_identifier'},errors:['Foto: Sem serial']});
 const server=http.createServer((req,res)=>void review.handleRequest(req,res));await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port+'/desc-review';
 try{
  const body={id:batch.id,photo,revision:batch.revision,serial:'ABC123456789'};
  assert.equal((await fetch(base+'/serial-lookup',{method:'POST',body:JSON.stringify(body)})).status,401);
  const login=await fetch(base+'/session',{method:'POST',body:JSON.stringify({pin:fs.readFileSync(path.join(directory,'review-access.txt'),'utf8').trim()})});const cookie=login.headers.get('set-cookie').split(';')[0],csrf=(await login.json()).csrf;
  const post=(route,data,token=csrf)=>fetch(base+route,{method:'POST',headers:{cookie,'Content-Type':'application/json','X-Review-CSRF':token},body:JSON.stringify(data)});
  assert.equal((await post('/serial-lookup',body,'invalid')).status,403);
  const lookup=await post('/serial-lookup',body);assert.equal(lookup.status,200);const result=await lookup.json();assert.equal(result.can_apply,true);assert.equal(review.store.get(batch.id).atlas.length,0);
  const apply=await post('/serial-apply',{...body,query_token:result.query_token});assert.equal(apply.status,200);const updated=(await apply.json()).batch;assert.equal(updated.executed,false);assert.equal(updated.messages[0].photo,photo);assert.equal(updated.messages[0].reading.manual.actor,'Dalton');assert.equal(updated.atlas.length,1);
  assert.equal((await post('/serial-apply',{...body,query_token:result.query_token})).status,400);assert.throws(()=>review.store.execute(),/teste/);
 }finally{await new Promise(r=>server.close(r));review.stop();fs.rmSync(directory,{recursive:true,force:true});}
});
