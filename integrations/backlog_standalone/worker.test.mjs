import test from "node:test";
import assert from "node:assert/strict";
import worker from "./worker.mjs";
const t="S".repeat(52);
const url="https://dominium-backlog-bridge.test";
const api="/api/backlog/year/status";
function req(method,path,opts={}){
  return new Request(url+path,{method,headers:opts.headers||{},
    body:method==="POST"?(opts.body??"{}"):undefined});
}
function auth(role="controller"){
  return {Authorization:"Bearer "+t,"X-Dominium-Role":role,"X-Dominium-Actor":"test-actor"};
}
test("independent health and secret absent -> 503",async()=>{
  assert.equal((await worker.fetch(req("GET","/health"),{})).status,200);
  assert.equal((await worker.fetch(req("GET",api),{BACKLOG_SERVICE:{}})).status,503);
});
test("reject unauthenticated and forged role",async()=>{
  const env={BACKLOG_BRIDGE_TOKEN:t,BACKLOG_SERVICE:{fetch:async()=>Response.json({ok:true})}};
  assert.equal((await worker.fetch(req("GET",api),env)).status,401);
  assert.equal((await worker.fetch(req("GET",api,{headers:auth("viewer")}),env)).status,403);
});
test("authenticated allowed request forwards private token and path only",async()=>{
  const recorded=[];
  const env={BACKLOG_BRIDGE_TOKEN:t,BACKLOG_SERVICE:{fetch:async request=>{
    recorded.push({url:request.url,auth:request.headers.get("Authorization"),
      role:request.headers.get("X-Dominium-Role")});
    return Response.json({ok:true,history:[]});
  }}};
  const response=await worker.fetch(req("GET",api,{headers:auth()}),env);
  assert.equal(response.status,200);
  assert.equal(recorded.length,1);
  assert.deepEqual(recorded[0],{url:"http://127.0.0.1:9342"+api,
    auth:"Bearer "+t,role:"controller"});
});
test("no unrelated operational endpoints or excessive query params",async()=>{
  const env={BACKLOG_BRIDGE_TOKEN:t,BACKLOG_SERVICE:{fetch:async()=>{throw Error("should not run")}}};
  for(const path of ["/api/orders","/api/orders/42/close","/api/backlog/year/delete",
    "/api/backlog/year/compare?limit=999999",
    "/api/backlog/year/status?unexpected=yes"]){
    assert.equal((await worker.fetch(req("GET",path,{headers:auth()}),env)).status,404,path);
  }
});
test("POST blocked without json content type or oversized data",async()=>{
  const env={BACKLOG_BRIDGE_TOKEN:t,BACKLOG_SERVICE:{fetch:async()=>Response.json({ok:true})}};
  assert.equal((await worker.fetch(req("POST","/api/backlog/year/start",{headers:auth(),body:"{}"}),env)).status,415);
  const headers={...auth(),"Content-Type":"application/json"};
  const reqbig=req("POST","/api/backlog/year/start",{headers,body:"x".repeat(8193)});
  assert.equal((await worker.fetch(reqbig,env)).status,413);
});
