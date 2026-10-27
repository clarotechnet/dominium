'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { allowedOrderClose } = require('../deploy/hostinger-web/operational-policy');
const { createOrderCloseMiddleware } = require('../deploy/hostinger-web/order-close-proxy');
const target='/api/orders/123/close?profile=natal';
const token='x'.repeat(43);
function request(extra={}) {
  return {method:'POST',originalUrl:target,headers:{'content-type':'application/json','x-csrf-token':'csrf'},
    dominiumSession:{csrf_hash:crypto.createHash('sha256').update('csrf').digest('hex')},
    dominiumUser:{id:5,display_name:'Operador',role:'controller'},
    body:{transport:'official_http',num_os:'999999',code:'409',materials:[],approved_state_hash:'scope'},...extra};
}
function response() {
  return {code:200,headers:{},status(code){this.code=code;return this;},set(name,value){this.headers[name]=value;return this;},json(value){this.payload=value;return this;}};
}
test('only explicit POST close paths with one known city and positive ID are accepted',()=>{
  for(const profile of ['natal','fortaleza','mossoro','recife'])assert.equal(allowedOrderClose('POST',target.replace('natal',profile)),true);
  for(const url of [target.replace('/123/','/0/'),target.replace('/123/','/-1/'),target+'&profile=recife',target+'&url=evil',target+'#x',target.replace('natal','unknown'),'/api/orders/123/close','/api/orders/123/move-installer?profile=natal','/api/orders/%31/close?profile=natal'])assert.equal(allowedOrderClose('POST',url),false,url);
  assert.equal(allowedOrderClose('GET',target),false);
});
test('official close reaches the private bridge once with body intact and no browser credentials',async()=>{
  let seen,calls=0;
  const handler=createOrderCloseMiddleware({connection:()=>({token}),fetchImpl:async(url,options)=>{calls++;seen={url,...options};return Response.json({ok:true,pending_confirmation:true,request_id:'request'});}});
  const req=request(),res=response();await handler(req,res);
  assert.equal(res.code,200);assert.equal(res.payload.pending_confirmation,true);
  assert.equal(seen.url,'https://dominium-import-bridge.jogador743.workers.dev'+target);
  assert.deepEqual(JSON.parse(seen.body),req.body);assert.equal(calls,1);
  assert.equal(seen.headers.Authorization,'Bearer '+token);
  assert.equal(seen.headers.Cookie,undefined);assert.equal(seen.headers['X-CSRF-Token'],undefined);
});
test('session, role, CSRF, route, media type, transport and body limit fail before forwarding',async()=>{
  let calls=0;
  const handler=createOrderCloseMiddleware({connection:()=>({token}),fetchImpl:async()=>{calls++;return Response.json({ok:true});}});
  for(const [extra,status] of [
    [{dominiumSession:null},401],[{dominiumUser:{role:'viewer'}},403],
    [{headers:{'content-type':'application/json','x-csrf-token':'wrong'}},403],
    [{originalUrl:target+'&profile=recife'},400],
    [{headers:{'content-type':'text/plain','x-csrf-token':'csrf'}},415],
    [{body:{transport:'datasnap'}},400],[{body:{}},400],[{body:[]},400],
    [{body:{transport:'official_http',data:'x'.repeat(65536)}},413],
  ]){const res=response();await handler(request(extra),res);assert.equal(res.code,status);}
  assert.equal(calls,0);
});
test('backend validation rejection remains visible and transport failures are uncertain without retry',async()=>{
  for(const upstream of [
    ()=>Response.json({ok:false,error:'Serial pertence a outro tecnico'},{status:400}),
    ()=>{throw new Error('transport_lost');},
    ()=>new Response('',{status:302}),
    ()=>new Response('<html>error</html>',{status:200}),
    ()=>Response.json({ok:false,error:'internal'},{status:503}),
  ]){
    let calls=0;const res=response();
    await createOrderCloseMiddleware({connection:()=>({token}),fetchImpl:async()=>{calls++;return upstream();}})(request(),res);
    assert.equal(calls,1);
    if(res.code===400){assert.equal(res.payload.error,'Serial pertence a outro tecnico');assert.equal(res.payload.uncertain,undefined);}
    else {assert.equal(res.code,502);assert.equal(res.payload.uncertain,true);assert.equal(res.payload.safe_to_retry,false);assert.match(res.payload.error,/confir|relat/i);}
  }
});
