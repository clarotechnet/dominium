import assert from 'node:assert/strict';
import test from 'node:test';
import worker from '../integrations/import_bridge/worker.mjs';
import operationalPolicy from '../deploy/hostinger-web/operational-policy.js';
import relay from '../deploy/hostinger-web/operational-relay.js';

const token='q'.repeat(43);
const path='/api/stock/quality-control';
const headers={Authorization:'Bearer '+token,'X-Dominium-Actor':'Operador Teste','X-Dominium-Role':'controller','Content-Type':'application/json'};
test('quality control route limited to GET/POST and exact path',()=>{
 for(const method of ['GET','POST']) assert.equal(operationalPolicy.allowedQualityControl(method,path),true);
 for(const url of [path+'?foo=1',path+'/delete','/api/orders/1/close']) {
  assert.equal(operationalPolicy.allowedQualityControl('POST',url),false);
 }
 for(const method of ['DELETE','PUT','PATCH'])assert.equal(operationalPolicy.allowedQualityControl(method,path),false);
});
test('authenticated Hostinger session routes QC only via private Worker',()=>{
 for(const method of ['GET','POST']){
  const req={method,originalUrl:path,dominiumSession:{user:{id:7}},dominiumUser:{id:7,role:'controller',username:'operador'}};
  const result=relay.resolveOperationalRead(req,()=>({token}));
  assert.ok(result?.url.endsWith(path));
  assert.equal(result.headers.authorization,'Bearer '+token);
 }
 assert.throws(()=>relay.resolveOperationalRead({method:'GET',originalUrl:path},()=>({token})));
 const viewer={method:'POST',originalUrl:path,dominiumSession:{},dominiumUser:{role:'viewer',username:'teste'}};
 assert.throws(()=>relay.resolveOperationalRead(viewer,()=>({token})));
 const req={method:'POST',originalUrl:path,headers:{'content-type':'application/json'}};
 const h={};relay.restorePrivateJsonContentType(req,h,'{}');
 assert.equal(h['content-type'],'application/json');
});
test('Worker forwards quality GET/POST once to DESC relay without browser credentials',async()=>{
 for(const method of ['GET','POST']){
  let calls=0;let observed;
  const payload=JSON.stringify({material:'123',descricao_material:'Cabo',qtd_controle_qualidade:'menor que 4'});
  const opts={method,headers:{...headers,Cookie:'private-session','X-CSRF-Token':'secret'}};
  if(method==='POST') opts.body=payload;
  const res=await worker.fetch(new Request('https://bridge.test'+path,opts),{
    IMPORT_TOKEN:token,
    IMPORT_SERVICE:{fetch:async()=>{throw Error('must use DESC')}},
    DESC_SERVICE:{fetch:async(req)=>{calls++;observed=req;return Response.json({ok:true,items:[],count:0});}},
  });
  assert.equal(res.status,200);
  assert.equal(calls,1);
  assert.equal(observed.url,'http://127.0.0.1:8793'+path);
  assert.equal(observed.headers.get('cookie'),null);
  assert.equal(observed.headers.get('x-csrf-token'),null);
  assert.equal(observed.headers.get('authorization'),'Bearer '+token);
  if(method==='POST')assert.equal(await observed.text(),payload);
 }
});
test('Worker blocks viewer edits and arbitrary paths',async()=>{
 const env={IMPORT_TOKEN:token,DESC_SERVICE:{fetch:()=>{throw Error('must not reach backend')}}};
 const viewer=await worker.fetch(new Request('https://bridge.test'+path,{method:'POST',headers:{...headers,'X-Dominium-Role':'viewer'},body:'{}'}),env);
 assert.equal(viewer.status,403);
 const invalid=await worker.fetch(new Request('https://bridge.test'+path+'?evil=1',{method:'POST',headers,body:'{}'}),env);
 assert.equal(invalid.status,404);
});
