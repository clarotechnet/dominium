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
test("Natal and Parnamirim adhesion only, not ADM, unspecified or other city",()=>{
 assert.equal(isAdhesionBucket("natal","NTL-DMV"),true);
 assert.equal(isAdhesionBucket("natal","PWM-DMV"),true);
 for(const r of ["PWM-DMV_ADM","NTL-DMV_ADM","FTZ-DMV",""])assert.equal(isAdhesionBucket("natal",r),false);
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

test("legacy production lookup uses signed import scope, not technician as bucket",()=>{
 const f=fixture();
 delete f.payload.resolved_contract;delete f.payload.query_type;
 f.payload.contract=scope.contract;f.payload.ok=true;
 delete f.capture.route;delete f.capture.decision;delete f.capture.materials_complete;
 f.capture.found=true;f.capture.validation_errors=[];f.capture.operation_blockers=[];
 f.capture.route_provider={name:"TECNICO TESTE"};
 f.deps.route=p=>p?.name||"";
 f.order.operation_source="toa_import";
 f.order.operation_identity={profile_key:"natal",contract:scope.contract,activity_id:f.capture.aid};
 f.order.import_scope={source_file:"Atividades-NTL-DMV_24_11_26.csv",expected_profile_key:"natal",source_hash:"fixture"};
 assert.equal(selectCandidates(f.payload,[f.order],scope,f.deps).length,1);
 f.order.import_scope.source_file="Atividades-PWM-DMV_24_11_26.csv";
 assert.equal(selectCandidates(f.payload,[f.order],scope,f.deps).length,1);
 for(const source of ["Atividades-PWM-DMV_ADM_24_11_26.csv","Atividades-FTZ-DMV_24_11_26.csv","Atividades-NTL-DMV_23_11_26.csv"]){
   f.order.import_scope.source_file=source;
   assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps));
 }
 f.order.import_scope.source_file="Atividades-PWM-DMV_24_11_26.csv";
 f.order.operation_identity.activity_id="different";
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps));
});

test("serial mandatory on productive Virtua; code-only companion needs no items",()=>{
 const f=fixture(), virtua={...f.order,id_os:2,num_os:"2612345679",service:"ADESAO - INSTALAR PONTO VIRTUA"};
 f.capture.tasks.push({os_number:virtua.num_os,status:"executed",close_code:"409"});
 f.capture.imperium_matches.push(virtua);
 f.capture.materials=[{code:"22026219",quantity:15},{code:"22056364",quantity:1}];
 f.deps.expectedType=s=>s.includes("VIRTUA")?"emta":"";
 f.deps.productive=()=>true;
 f.deps.assign=cs=>cs.forEach(c=>c.materialOwner=c.numOs===virtua.num_os);
 assert.throws(()=>selectCandidates(f.payload,[f.order,virtua],scope,f.deps),/Serial obrigatorio/);
 f.capture.installed_equipment=[{serial:"AABBCCDDEEFF",type:"emta"}];
 f.deps.equipment=c=>({installed:c.batchCodeOnly?[]:f.capture.installed_equipment,removed:[]});
 const cs=selectCandidates(f.payload,[f.order,virtua],scope,f.deps);
 assert.equal(cs[0].numOs,virtua.num_os);assert.equal(cs[1].batchCodeOnly,true);
});
test("shortage audit permits confirmed completion and next contract, no serial waiver",async()=>{
 const events=[],sent=[];
 await runBatch(["12345678","23456789"],{active:()=>true,update:(...v)=>events.push(v),prepare:async c=>c==="12345678"?[{numOs:"1"},{numOs:"2"}]:[{numOs:"3"}],send:async c=>{sent.push(c.numOs);return c.numOs==="1"?{pending:true,requestId:"r",materialPreparation:{discarded_shortfalls:[{code:"22056364"},{code:"22056365"}],partial_shortfalls:[]}}:c.numOs==="3"?{closed:false,reason:"Serial fora do estoque"}:{closed:true}},confirm:async()=>"confirmed"});
 assert.deepEqual(sent,["1","2","3"]);
 const done=events.findLast(v=>v[0]==="12345678");
 assert.equal(done[1],"Baixado");assert.match(done[2],/22056364, 22056365/);
 assert.equal(events.at(-1)[1],"Tratativa");assert.match(events.at(-1)[2],/Serial fora do estoque/);
});
test("already absent contract never submits a write",async()=>{
 let writes=0;const events=[];
 await runBatch(["12345678"],{active:()=>true,update:(...v)=>events.push(v),prepare:async()=>[],send:async()=>{writes++;return {closed:true}},confirm:async()=>"confirmed"});
 assert.equal(writes,0);assert.equal(events.at(-1)[1],"Sem OS em campo");
});
