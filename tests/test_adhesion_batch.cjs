"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {parseContracts,isAdhesionBucket,codeOnly,selectCandidates,runBatch}=require("../static/adhesion-batch.js");
const scope={profile:"natal",date:"2026-11-24",contract:"12345678",epoch:4};
function fixture(){
 const order={id_os:1,num_os:"2612345678",contract:scope.contract,service:"ADESAO - INSTALACAO DE ASSINATURA"};
 const capture={aid:"123",contract:scope.contract,route:"NTL-DMV",scheduled_date:scope.date,activity_status:"completed",decision:"candidate_after_validation",materials_complete:true,tasks:[{os_number:order.num_os,status:"executed",close_code:"409"}],imperium_matches:[order]};
 const payload={profile:"natal",resolved_contract:scope.contract,query_type:"contract",results:[capture]};
 const deps={complete:s=>s==="completed",executed:s=>s==="executed",route:()=>"",valid:()=>true,knownCode:c=>c==="409",assign:()=>{},equipment:()=>({installed:[],removed:[]}),materials:a=>a||[]};
 return {order,capture,payload,deps};
}
test("multiple separators, duplicate contracts, invalid values and limit",()=>{
 assert.deepEqual(parseContracts("12345678, 23456789\n12345678; 00001234"),["12345678","23456789","00001234"]);
 assert.throws(()=>parseContracts("12345a")); assert.throws(()=>parseContracts(""));
 assert.throws(()=>parseContracts(Array.from({length:51},(_,i)=>String(10000+i)).join(",")));
});
test("Natal adhesion only, not Parnamirim, ADM, unspecified or other city",()=>{
 assert.equal(isAdhesionBucket("natal","NTL-DMV"),true);
 for(const r of ["PWM-DMV","NTL-DMV_ADM","FTZ-DMV",""])assert.equal(isAdhesionBucket("natal",r),false);
 assert.equal(isAdhesionBucket("fortaleza","FTZ-DMV"),false);
});
test("exact code-only exceptions",()=>{
 assert.equal(codeOnly("ADESAO - INSTALACAO DE ASSINATURA"),true);
 assert.equal(codeOnly("INST GPON - INST CABO"),true);
 assert.equal(codeOnly("INSTALACAO VIRTUA"),false);
});
test("validated contract produces scoped candidate",()=>{
 const f=fixture();const [c]=selectCandidates(f.payload,[f.order],scope,f.deps);
 assert.equal(c.batchAdhesion,true);assert.equal(c.batchCodeOnly,true);assert.equal(c.batchScope.epoch,4);
});
test("blocks foreign bucket, bad date, incomplete capture, unapproved or ambiguous OS",()=>{
 for(const change of [f=>f.capture.route="NTL-DMV_ADM",f=>f.capture.scheduled_date="2026-11-23",f=>f.capture.materials_complete=false,f=>f.deps.valid=()=>false,f=>f.capture.tasks[0].status="pending",f=>f.capture.tasks.push({...f.capture.tasks[0]}),f=>f.payload.resolved_contract="99999999",f=>f.capture.decision="blocked_manual_review"]){
  const f=fixture();change(f);assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps));
 }
});
test("blocks missing OS and incomplete equipment allocation",()=>{
 const f=fixture();assert.throws(()=>selectCandidates(f.payload,[f.order,{...f.order,id_os:2,num_os:"2612345679"}],scope,f.deps));
 f.order.service="ADESAO VIRTUA";f.capture.installed_equipment=[{serial:"ABC123"}];
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps));
});
test("pending confirmation never resends, never submits companion while uncertain, continues next contract",async()=>{
 const sent=[],events=[];
 await runBatch(["12345678","23456789"],{active:()=>true,update:(...v)=>events.push(v),prepare:async c=>c==="12345678"?[{numOs:"1"},{numOs:"2"}]:[{numOs:"3"}],send:async c=>{sent.push(c.numOs);return c.numOs==="1"?{pending:true,requestId:"r"}:{closed:true}},confirm:async()=>"pending"});
 assert.deepEqual(sent,["1","3"]);assert.equal(events.findLast(v=>v[0]==="12345678")[1],"Aguardando confirmacao");assert.equal(events.at(-1)[1],"Baixado");
});
test("stop prevents next write",async()=>{
 let active=true;const sent=[];
 await runBatch(["12345678","23456789"],{active:()=>active,update:()=>{},prepare:async()=>[{numOs:"1"},{numOs:"2"}],send:async c=>{sent.push(c.numOs);active=false;return {closed:true}},confirm:async()=>"confirmed"});
 assert.deepEqual(sent,["1"]);
});
