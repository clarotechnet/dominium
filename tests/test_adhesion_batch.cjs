"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {parseContracts,isAdhesionBucket,codeOnly,selectCandidates,runBatch,readBatchToa}=require("../static/adhesion-batch.js");
const scope={profile:"natal",date:"2026-11-24",contract:"12345678",epoch:4};
test("restores a closed tab's list without treating interrupted work as confirmed", () => {
 const {restoreQueue} = require("../static/adhesion-batch.js");
 const saved = JSON.stringify({date:scope.date,rows:[
  {contract:"12345678",label:"Baixado"}, {contract:"23456789",label:"Executando"},
  {contract:"34567890",label:"Na fila"}, {contract:"45678901",label:"Aguardando confirmacao"},
 ]});
 assert.deepEqual(restoreQueue(saved,scope.date).map(({label})=>label),
  ["Baixado","Interrompido","Interrompido","Aguardando confirmacao"]);
 assert.deepEqual(restoreQueue(saved,"2026-11-25"), []);
 assert.deepEqual(restoreQueue(null,scope.date), []);
});
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
 assert.equal(codeOnly("MUDANCA DE ENDERECO - INSTALAR ASSINATURA"),true);
 assert.equal(codeOnly("INST GPON - INST CABO"),true);
 assert.equal(codeOnly("INSTALACAO VIRTUA"),false);
});

test("additional Virtua relocation can use materials while keeping the customer's EMTA", () => {
 const f = fixture();
 f.order.service = "Mudança de endereço - Instalar ponto adicional Virtua";
 const signature = {...f.order, id_os: 2, num_os: "2612345680", service: "MUDANCA DE ENDERECO - INSTALAR ASSINATURA"};
 f.capture.tasks.push({os_number: signature.num_os, status: "executed", close_code: "409"});
 f.capture.imperium_matches.push(signature);
 f.capture.installed_equipment = [];
 f.capture.removed_equipment = [];
 f.capture.customer_equipment = [{serial: "AABBCCDDEEFF", type: "emta"}];
 f.capture.materials = [{code: "22026219", quantity: 1}];
 f.deps.expectedType = () => "emta";
 f.deps.productive = () => true;
 const plans = [];
 f.deps.equipment = candidate => {
  plans.push(candidate.numOs);
  return {installed: f.capture.installed_equipment || [], removed: f.capture.removed_equipment};
 };
 f.deps.assign = candidates => candidates.forEach(candidate => {candidate.materialOwner = !candidate.batchCodeOnly;});

 assert.deepEqual(selectCandidates(f.payload, [f.order, signature], scope, f.deps).map(candidate => [candidate.batchCodeOnly, candidate.materialOwner]), [
  [false, true], [true, false],
 ]);
 assert.deepEqual(plans, [f.order.num_os]);

 delete f.capture.installed_equipment;
 assert.throws(() => selectCandidates(f.payload, [f.order, signature], scope, f.deps), /Serial obrigatorio/);
 f.capture.installed_equipment = [];
 f.capture.removed_equipment = [{serial: "CCDDEEFFAABB", type: "emta"}];
 assert.equal(selectCandidates(f.payload, [f.order, signature], scope, f.deps).length, 2);
 f.capture.installed_equipment = [{serial: "AABBCC112233", type: "emta"}];
 assert.equal(selectCandidates(f.payload, [f.order, signature], scope, f.deps).length, 2);
});

test("relocation can use materials without a new EMTA or decoder across service labels", () => {
 for (const [service, expected] of [
  ["Mudança de endereço - Internet", "emta"],
  ["Mudança de endereço - Instalar ponto digital TV", "decoder"],
  ["123 - MUD. DE END. - TV", "decoder"],
 ]) {
  const f = fixture();
  f.order.service = service;
  f.capture.installed_equipment = [];
  f.capture.removed_equipment = [];
  f.capture.materials = [{code: "22026219", quantity: 1}];
  f.deps.expectedType = () => expected;
  f.deps.productive = () => true;
  f.deps.assign = candidates => candidates.forEach(candidate => {candidate.materialOwner = true;});
  f.deps.equipment = () => ({installed: f.capture.installed_equipment, removed: []});

  let [candidate] = selectCandidates(f.payload, [f.order], scope, f.deps);
  assert.equal(candidate.batchCodeOnly, false);
  assert.equal(candidate.materialOwner, true);
  assert.deepEqual(f.deps.equipment(candidate).installed, []);
  assert.deepEqual(candidate.capture.materials, f.capture.materials);

  const serial = expected === "emta" ? "AABBCC112233" : "123456789";
  f.capture.installed_equipment = [{serial, type: expected}];
  [candidate] = selectCandidates(f.payload, [f.order], scope, f.deps);
  assert.deepEqual(f.deps.equipment(candidate).installed, [{serial, type: expected}]);
  f.deps.equipment = () => ({installed: [], removed: []});
  assert.throws(() => selectCandidates(f.payload, [f.order], scope, f.deps), /sem alocacao segura/);

  f.capture.installed_equipment = [];
  f.order.service = "ADESAO - INSTALAR PONTO VIRTUA";
  assert.throws(() => selectCandidates(f.payload, [f.order], scope, f.deps), /Serial obrigatorio/);
 }
});

test("a relocation companion can use existing equipment when the only new serial belongs to another OS", () => {
 const f = fixture();
 f.order.service = "MUDANCA DE ENDERECO - VIRTUA";
 const tv = {...f.order, id_os: 2, num_os: "2612345680", service: "MUDANCA DE ENDERECO - TV"};
 f.capture.tasks.push({...f.capture.tasks[0], os_number: tv.num_os});
 f.capture.imperium_matches.push(tv);
 const decoder = {serial: "123456789", type: "decoder"};
 f.capture.installed_equipment = [decoder];
 f.capture.removed_equipment = [];
 f.capture.materials = [{code: "22026219", quantity: 1}];
 f.deps.expectedType = service => service.endsWith("TV") ? "decoder" : "emta";
 f.deps.productive = () => true;
 f.deps.assign = candidates => candidates.forEach(candidate => {candidate.materialOwner = candidate.order === f.order;});
 f.deps.equipment = candidate => ({installed: candidate.order === tv ? [decoder] : [], removed: []});
 assert.deepEqual(selectCandidates(f.payload, [f.order, tv], scope, f.deps).map(candidate => [
  candidate.numOs, candidate.materialOwner, f.deps.equipment(candidate).installed,
 ]), [[f.order.num_os, true, []], [tv.num_os, false, [decoder]]]);
});
test("validated contract produces scoped candidate",()=>{
 const f=fixture();const [c]=selectCandidates(f.payload,[f.order],scope,f.deps);
 assert.equal(c.batchAdhesion,true);assert.equal(c.batchCodeOnly,true);assert.equal(c.batchScope.epoch,4);
});
test("trusted live route_name proves the bucket and cannot override conflicting signed import", () => {
 const f = fixture();
 delete f.capture.route;
 f.capture.route_name = "NTL-DMV";
 f.order.operation_source = "imperium_cache";
 assert.equal(selectCandidates(f.payload, [f.order], scope, f.deps).length, 1);
 f.capture.bucket = "PWM-DMV";
 assert.throws(() => selectCandidates(f.payload, [f.order], scope, f.deps), /Bucket TOA divergente/);
 delete f.capture.bucket;
 f.order.operation_source = "toa_import";
 f.order.operation_identity = {profile_key:"natal",contract:scope.contract,activity_id:f.capture.aid};
 f.order.import_scope = {source_file:"Atividades-PWM-DMV_24_11_26.csv",expected_profile_key:"natal",source_hash:"fixture"};
 assert.throws(() => selectCandidates(f.payload, [f.order], scope, f.deps), /diverge da origem importada/);
 delete f.order.import_scope.source_hash;
 assert.throws(() => selectCandidates(f.payload, [f.order], scope, f.deps), /origem importada sem comprovacao/);
});

test("reports both OS when a serialized movement lacks a unique owner", () => {
 const f = fixture();
 f.order.service = "MUDANCA DE PACOTE";
 const other = {...f.order, num_os:"2612345679", id_os:2};
 f.capture.tasks.push({...f.capture.tasks[0], os_number:other.num_os});
 f.capture.imperium_matches.push(other);
 f.deps.equipment = () => ({installed:[{serial:"AABBCCDDEEFF"}],removed:[]});
 assert.throws(() => selectCandidates(f.payload, [f.order, other], scope, f.deps), /2612345678, 2612345679\. Nenhuma baixa enviada/);
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

test("a busy read defers one contract and never repeats a close with an uncertain result", async () => {
 const {freshOrders} = require("../static/adhesion-batch.js");
 const order = [], sends = [];
 let reads = 0;
 await runBatch(["busy", "uncertain", "ready"], {
  active: () => true, update: () => {},
  async prepare(contract) {
   order.push(contract);
   if (contract === "busy" && ++reads === 1) {
    await freshOrders(async () => {throw Object.assign(Error("busy"), {status:409});},
      {active: () => true, wait: async () => {}, attempts: 1});
   }
   return [{numOs: contract}];
  },
  async send(candidate) {
   sends.push(candidate.numOs);
   return candidate.numOs === "uncertain" ? {pending: true} : {closed: true};
  },
 });
 assert.deepEqual(order, ["busy", "uncertain", "ready", "busy"]);
 assert.deepEqual(sends, ["uncertain", "ready", "busy"]);
});

test("a matching legacy stock failure explains the blocked attempt before any write", async () => {
 const {priorCloseOutcome} = require("../static/adhesion-batch.js");
 const record = {request_id: "stock-attempt", contract: scope.contract, num_os: "2612345678", id_os: 42, close_code: "409", state: "sending", created_at: "2026-11-24T09:27:56-03:00"};
 const failure = {...record, last_at: "2026-11-24T09:31:09", error: "O resultado do complemento das miscelaneas ficou incerto. A baixa da OS nao foi enviada. Codigo 22025139."};
 const known = priorCloseOutcome(record, [failure]);
 assert.match(known.reason, /nao foi enviada.*22025139/);
 assert.equal(known.stockRetryRequestId, record.request_id);
 assert.equal(known.pending, undefined);
 for(const irrelevant of [{...failure,id_os: 43},{...failure,last_at: "2026-11-24T09:26:00"},{...failure,close_code: "106"}]) {
  assert.equal(priorCloseOutcome(record, [irrelevant]).pending, true);
 }
 assert.equal(priorCloseOutcome({...record,accepted_at: "2026-11-24T09:31:00-03:00"}, [failure]).pending, true);
 const prepared = [], sent = [], events = [];
 await runBatch([scope.contract, "87654321"], {
  active: () => true,
  update: (...event) => events.push(event),
  priorContract: async contract => contract === scope.contract ? known : undefined,
  prepare: async contract => {prepared.push(contract);return [{numOs: "2"}];},
  send: async candidate => {sent.push(candidate.numOs);return {closed:true};},
 });
 assert.deepEqual(prepared, ["87654321"]);
 assert.deepEqual(sent, ["2"]);
 assert.equal(events.findLast(event => event[0] === scope.contract)[1], "Tratativa");
 assert.match(events.findLast(event => event[0] === scope.contract)[2], /22025139/);
});

test("keeps confirmed OS and material audit when companion approval fails", async () => {
 const events = [], sent = [];
 await runBatch([scope.contract], {
  active: () => true,
  update: (...event) => events.push(event),
  prepare: async () => [{numOs: "1", code: "409"}, {numOs: "2", code: "409"}, {numOs: "3"}],
  send: async ({numOs}) => {
   sent.push(numOs);
   if (numOs === "2") throw Error("Aprovacao da OS expirou");
   return {
    pending: true,
    requestId: "r",
    reason: "solicitacao enviada; aguardando confirmacao",
    materialPreparation: {discarded_shortfalls: [{code: "22056366"}]},
   };
  },
  confirm: async () => "confirmed",
 });
 assert.deepEqual(sent, ["1", "2"]);
 const [, label, detail] = events.at(-1);
 assert.equal(label, "Tratativa");
 assert.match(detail, /1 confirmada.*1 em tratativa.*1 nao enviada/);
 assert.match(detail, /OS 1 \(409\) confirmada no Imperium.*22056366/);
 assert.match(detail, /OS 2 \(409\) em tratativa.*Aprovacao da OS expirou/);
 assert.doesNotMatch(detail, /aguardando confirmacao/);
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

test("busy cache and HTTP 409 wait for fresh data without submitting writes",async()=>{
 const {freshOrders}=require("../static/adhesion-batch.js");
 const queue=[{stale:true,orders:[{id_os:1}]},Object.assign(new Error("busy"),{status:409}),{orders:[{id_os:2}]}];
 const waits=[],notices=[];
 const result=await freshOrders(async()=>{const r=queue.shift();if(r instanceof Error)throw r;return r;},{active:()=>true,wait:async d=>waits.push(d),notify:(a,m)=>notices.push([a,m]),attempts:3,delay:5});
 assert.equal(result.orders[0].id_os,2);assert.deepEqual(waits,[5,5]);assert.deepEqual(notices,[[1,3],[2,3]]);
});
test("persistent cache, cancellation and nonbusy errors fail closed",async()=>{
 const {freshOrders}=require("../static/adhesion-batch.js");let reads=0;
 await assert.rejects(freshOrders(async()=>{reads++;return {stale:true,orders:[]};},{active:()=>true,wait:async()=>{},attempts:2}),/Imperium ocupado/);assert.equal(reads,2);
 let active=true;
 await assert.rejects(freshOrders(async()=>({stale:true,orders:[]}),{active:()=>active,wait:async()=>{active=false;}}),/interrompido/);
 await assert.rejects(freshOrders(async()=>{throw Object.assign(new Error("auth"),{status:401});},{active:()=>true,wait:async()=>{throw Error("must not retry");}}),/auth/);
 assert.equal(codeOnly("INSTALACAO DE CABO GPON"),true);
});

test("persistent busy stops after four reads and passes the remaining time to each read", async () => {
 const {freshOrders} = require("../static/adhesion-batch.js");
 let elapsed = 0;
 const budgets = [];
 await assert.rejects(freshOrders(async timeout => {
  budgets.push(timeout);
  return {stale: true, orders: []};
 }, {active: () => true, now: () => elapsed, wait: async delay => {elapsed += delay;}}), /Imperium ocupado/);
 assert.deepEqual(budgets, [15000, 13500, 12000, 10500]);
 assert.equal(elapsed, 4500);

 elapsed = 0;
 budgets.length = 0;
 await assert.rejects(freshOrders(async timeout => {
  budgets.push(timeout);
  elapsed += Math.min(8000, timeout);
  return {stale: true, orders: []};
 }, {active: () => true, now: () => elapsed, wait: async delay => {elapsed += delay;}}), /Imperium ocupado/);
 assert.deepEqual(budgets, [15000, 5500]);
 assert.equal(elapsed, 15000);
});

const unavailableToa = () => Object.assign(new Error("TOA secundario nao localizado"), {status: 502});

test("recovers from transient TOA bridge timeouts using only contract reads", async () => {
  const payload = {ok: true, contract: scope.contract};
  const replies = [unavailableToa(), unavailableToa(), payload];
  const waits = [];
  let notices = 0;
  const result = await readBatchToa(async () => {
    const reply = replies.shift();
    if (reply instanceof Error) throw reply;
    return reply;
  }, {active: () => true, wait: async delay => waits.push(delay), notify: () => notices++});
  assert.equal(result, payload);
  assert.deepEqual(waits, [1000, 3000]);
  assert.equal(notices, 2);
});

test("limits bridge retries and preserves cancellation and other lookup failures", async () => {
  let reads = 0;
  const read = async () => { reads++; throw unavailableToa(); };
  const hooks = {active: () => true, wait: async () => {}, notify: () => {}};
  await assert.rejects(readBatchToa(read, hooks), /Nenhuma baixa foi enviada/);
  assert.equal(reads, 4);

  let active = true;
  await assert.rejects(readBatchToa(read, {
    ...hooks, active: () => active, wait: async () => { active = false; },
  }), /Lote interrompido/);
  assert.equal(reads, 5);

  const error = Object.assign(new Error("Contrato nao localizado no TOA"), {status: 502});
  await assert.rejects(readBatchToa(async () => { reads++; throw error; }, hooks), error);
  assert.equal(reads, 6);
});

test("retries a TOA scope response and retains review when the date and route are still inconclusive",async()=>{
 const error=Object.assign(new Error("Error: adhesion_activity_scope_unconfirmed"),{status:502});
 const options={active:()=>true,wait:async()=>{},notify:()=>{}};
 const payload={ok:true,contract:scope.contract};
 let reads=0;
 assert.equal(await readBatchToa(async()=>{if(++reads===1)throw error;return payload;},options),payload);
 assert.equal(reads,2);
 await assert.rejects(readBatchToa(async()=>{throw error;},options),/data e na rota NTL\/PWM/);
});

test("keeps an unsupported code in review and plans only the independent signature order",()=>{
 const f=fixture();
 const voip={...f.order,id_os:2,num_os:"2612345680",service:"ADESAO - INSTALAR PONTO VOIP"};
 const virtua={...f.order,id_os:3,num_os:"2612345681",service:"ADESAO - INSTALAR PONTO VIRTUA"};
 f.capture.tasks.push(
  {os_number:voip.num_os,status:"executed",close_code:"410"},
  {os_number:virtua.num_os,status:"executed",close_code:"409"},
 );
 f.capture.imperium_matches.push(voip,virtua);
 const held=[];
 f.deps.hold=items=>held.push(...items);
 f.deps.equipment=()=>assert.fail("Nenhum estoque compartilhado deve ser planejado");
 const planned=selectCandidates(f.payload,[f.order,voip,virtua],scope,f.deps);
 assert.deepEqual(planned.map(c=>c.numOs),[f.order.num_os]);
 assert.match(held[0],/2612345680.*410 indisponivel/);
 assert.match(held[1],/2612345681.*conciliar os itens/);
});

test("a prior accepted HTTP 200 stays pending and a confirmation with a different code remains in review",()=>{
 const {priorCloseOutcome}=require("../static/adhesion-batch.js");
 const accepted={num_os:"2612345680",close_code:"409",state:"pending",official_http_status:200,accepted_at:"2026-11-27T16:37:09-03:00"};
 assert.match(priorCloseOutcome(accepted).reason,/16:37.*Reenvio bloqueado/);
 assert.equal(priorCloseOutcome(accepted).pending,true);
 const confirmed={...accepted,state:"confirmed"};
 assert.equal(priorCloseOutcome(confirmed,[],"409").closed,true);
 assert.match(priorCloseOutcome(confirmed,[],"110").reason,/codigo diferente do 110/);
});

test("uses the refreshed lookup status list without repeating the initial field read", async () => {
 const {ordersForBatchContract} = require("../static/adhesion-batch.js");
 const active = {contract: scope.contract, num_os: "1", status: "EM CAMPO"};
 const payload = {
  imperium_refresh: {refreshed: true},
  imperium_all_orders: [active, {...active, num_os: "2", status: "CONCLUIDA"}, {...active, contract: "23456789"}],
 };
 let reads = 0;
 const readFresh = async () => {reads++; return {orders: [active]};};
 assert.deepEqual(await ordersForBatchContract(payload, scope.contract, readFresh), [active]);
 assert.deepEqual(await ordersForBatchContract({...payload, imperium_all_orders: []}, scope.contract, readFresh), []);
 assert.equal(reads, 0);
 assert.deepEqual(await ordersForBatchContract({...payload, imperium_refresh: {busy: true}}, scope.contract, readFresh), [active]);
 assert.deepEqual(await ordersForBatchContract({...payload, imperium_all_orders: [{}]}, scope.contract, readFresh), [active]);
 assert.equal(reads, 2);
});

test("refresh approval before companion without changing OS identity",()=>{
 const {refreshCandidate}=require("../static/adhesion-batch.js");
 const old={id_os:2,num_os:"999",contract:"12345678",service:"INSTALACAO DE CABO GPON",operation_source:"toa_import",operation_identity:{profile_key:"natal",contract:"12345678",activity_id:"123"},import_scope:{source_file:"Atividades-NTL-DMV_24_11_26.csv",expected_profile_key:"natal",source_hash:"fixture"},approved_state_hash:"old"};
 const candidate={order:old,numOs:"999",capture:{aid:"123",contract:"12345678"},batchScope:scope,batchCodeOnly:true};
 const fresh={...old,approved_state_hash:"new"};
 assert.equal(refreshCandidate(candidate,[fresh],()=>true).order.approved_state_hash,"new");
 assert.equal(candidate.order.approved_state_hash,"old");
 assert.throws(()=>refreshCandidate(candidate,[],()=>true),/nao esta mais em campo/);
 assert.throws(()=>refreshCandidate(candidate,[{...fresh,import_scope:{...fresh.import_scope,source_hash:"other"}}],()=>true),/Escopo/);
 assert.throws(()=>refreshCandidate(candidate,[fresh],()=>false),/Escopo/);
});
test("Imperium-only companion without confirmed TOA code is not inferred",()=>{
 const f=fixture();f.capture.tasks[0].imperium_only=true;f.capture.tasks[0].close_code="";
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps),/codigo de baixa nao confirmado/);
});

function unproductivePair(code, service) {
 const f=fixture();
 const manual_scope={profile_key:scope.profile,cache_date:scope.date};
 Object.assign(f.order,{service:"MUDANCA DE PACOTE",operation_source:"imperium_cache",manual_scope});
 const companion={...f.order,id_os:2,num_os:"2612345680",service};
 Object.assign(f.capture,{installed_equipment:[],removed_equipment:[],materials:[]});
 Object.assign(f.capture.tasks[0],{status:"N",close_code:code});
 f.capture.tasks.push({os_number:companion.num_os,imperium_only:true});
 f.capture.imperium_matches.push(companion);
 f.deps.executed=status=>status==="N";
 f.deps.knownCode=value=>["106","110","409"].includes(value);
 f.deps.productive=value=>value==="409";
 f.deps.equipment=()=>assert.fail("Ordens improdutivas devem seguir sem equipamentos");
 return {...f,companion};
}

test("copies a confirmed unproductive code from the sole TOA task to GPON or signature", async()=>{
 for(const [code,service] of [
  ["110","INSTALACAO DE CABO GPON"],
  ["106","ADESAO - INSTALACAO DE ASSINATURA"],
 ]) {
  const f=unproductivePair(code,service);
  const orders=[f.companion,f.order];
  const sent=[], events=[];
  await runBatch([scope.contract],{
   active:()=>true,
   update:(...args)=>events.push(args),
   prepare:async()=>selectCandidates(f.payload,orders,scope,f.deps),
   send:async candidate=>{sent.push(candidate); return {closed:true};},
  });
  assert.deepEqual(sent.map(c=>[c.numOs,c.code,c.batchCodeOnly,c.batchInheritedFrom]),[
   [f.order.num_os,code,true,undefined],[f.companion.num_os,code,true,f.order.num_os],
  ]);
  assert.equal(events.at(-1)[1],"Baixado");
  assert.match(events.at(-1)[2],/Codigo improdutivo da OS 2612345678/);
 }
});

test("uses separately approved Imperium field rows when the TOA only attaches the reported task", async()=>{
 const {ordersForBatchContract}=require("../static/adhesion-batch.js");
 const f=unproductivePair("110","INSTALACAO DE CABO GPON");
 f.capture.imperium_matches.pop();
 f.capture.tasks.splice(1,0,{os_number:"", status:"N", close_code:""});
 f.payload.imperium_refresh={refreshed:true};
 f.payload.imperium_all_orders=[f.order,f.companion].map(({num_os,id_os,contract,service})=>({
  num_os,id_os,contract,service,status:"EM CAMPO",operation_source:"imperium_status_snapshot",
 }));
 const readOnly=f.payload.imperium_all_orders;
 const approved={...f.companion,approved_state_hash:"fresh-field-approval"};
 let reads=0;
 const orders=await ordersForBatchContract(f.payload,scope.contract,async()=>{
  reads++;
  return {orders:[f.order,approved]};
 },scope,f.deps);
 assert.equal(reads,1);
 const [primary,companion]=selectCandidates(f.payload,orders,scope,f.deps);
 assert.equal(primary.numOs,f.order.num_os);
 assert.equal(companion.code,"110");
 assert.equal(companion.order,approved);
 assert.throws(()=>selectCandidates(f.payload,readOnly,scope,f.deps),/codigo de baixa nao confirmado/);
 f.capture.tasks[1].close_code="106";
 assert.throws(()=>selectCandidates(f.payload,orders,scope,f.deps),/codigo de baixa nao confirmado/);
});

test("leaves the missing companion in review when the exact unproductive pair is ambiguous",()=>{
 const changes=[
  f=>{f.capture.tasks[0].close_code="409";},
  f=>{f.capture.tasks[0].close_code="999";},
  f=>{f.capture.tasks[0].registry_only=true;},
  f=>{f.capture.installed_equipment.push({serial:"AA0000000001"});},
  f=>{delete f.capture.removed_equipment;},
  f=>{f.companion.service="ADESAO - INSTALAR PONTO VIRTUA";},
  f=>{f.companion.service="RETIRADA DE ASSINATURA";},
  f=>{f.companion.activity_id="456";},
  f=>{f.companion.manual_scope={...f.companion.manual_scope,cache_date:"2026-11-23"};},
  f=>{f.payload.results.push({...f.capture,aid:"456",tasks:[]});},
  f=>{f.capture.imperium_matches.pop();},
 ];
 for(const change of changes){
  const f=unproductivePair("110","INSTALACAO DE CABO GPON");
  change(f);
  assert.throws(()=>selectCandidates(f.payload,[f.order,f.companion],scope,f.deps),/codigo de baixa nao confirmado|codigo 999 indisponivel/);
 }
});

test("waits for the primary close and only resumes the companion with the exact confirmed report", async()=>{
 const f=unproductivePair("106","INSTALACAO DE CABO GPON");
 const sent=[];
 await runBatch([scope.contract],{
  active:()=>true, update:()=>{},
  prepare:async()=>selectCandidates(f.payload,[f.order,f.companion],scope,f.deps),
  send:async candidate=>{sent.push(candidate.numOs);return {pending:true};},
 });
 assert.deepEqual(sent,[f.order.num_os]);
 f.payload.imperium_refresh={refreshed:true};
 f.capture.imperium_all_orders=[{...f.order,status:"REAGENDADA"}];
 f.deps.confirmedCloses=[{
  id_os:f.order.id_os,num_os:f.order.num_os,contract:scope.contract,
  report_date:scope.date,state:"confirmed",close_code:"106",
 }];
 const [candidate]=selectCandidates(f.payload,[f.companion],scope,f.deps);
 assert.equal(candidate.batchInheritedFrom,f.order.num_os);
 assert.equal(candidate.code,"106");
 const {refreshCandidate}=require("../static/adhesion-batch.js");
 assert.throws(()=>refreshCandidate(candidate,[{...f.companion,activity_id:"456"}],()=>true),/vinculo da OS acompanhante mudou/);
 f.deps.confirmedCloses[0].close_code="110";
 assert.throws(()=>selectCandidates(f.payload,[f.companion],scope,f.deps),/codigo de baixa nao confirmado/);
});

test("an exact GPON task can proceed with code alone while uncorrelated orders stay in review", async () => {
 const f=fixture();
 f.order.service="INSTALACAO DE CABO GPON";
 const other={...f.order,id_os:2,num_os:"2612345680",service:"MUDANCA DE PACOTE"};
 f.capture.tasks.push({os_number:other.num_os,imperium_only:true});
 const sent=[], events=[];
 await runBatch([scope.contract], {
  active:()=>true, update:(...args)=>events.push(args),
  prepare:async (_contract,hold)=>selectCandidates(f.payload,[f.order,other],scope,{...f.deps,hold}),
  send:async c=>{sent.push(c); return {closed:true};},
 });
 assert.deepEqual(sent.map(c=>[c.numOs,c.batchCodeOnly]), [[f.order.num_os,true]]);
 assert.equal(events.at(-1)[1], "Tratativa");
 assert.match(events.at(-1)[2], /2612345680.*sem codigo de baixa/);
});

test("display rows from another activity do not override the exact TOA task for GPON", () => {
 const f = fixture();
 f.order.service = "ADESAO - INSTALAR PONTO VIRTUA";
 const gpon = {...f.order, id_os: 2, num_os: "2612345679", service: "INSTALACAO DE CABO GPON"};
 const displayOnly = num => ({os_number: num, source: "imperium_contract_status", imperium_only: true});
 f.capture.tasks.push(displayOnly(gpon.num_os));
 f.payload.results.push({
  ...f.capture,
  aid: "456",
  tasks: [displayOnly(f.order.num_os), {os_number: gpon.num_os, status: "executed", close_code: "409"}],
  imperium_matches: [gpon],
 });
 const orders = [f.order, gpon];
 const candidates = selectCandidates(f.payload, orders, scope, f.deps);
 assert.deepEqual(candidates.map(c => [c.numOs, c.capture.aid, c.batchCodeOnly]), [
  [f.order.num_os, "123", false], [gpon.num_os, "456", true],
 ]);
 f.payload.results[1].tasks.pop();
 assert.throws(() => selectCandidates(f.payload, orders, scope, f.deps), /2612345679.*codigo de baixa nao confirmado/);
});

test("incomplete TOA capture explains the failed guard without relaxing it",()=>{
 const f=fixture();
 f.capture.activity_status="pending";
 f.capture.materials_complete=false;
 f.capture.operation_blockers=["test"];
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps), /status da atividade: pending.*captura de materiais incompleta.*bloqueios operacionais: 1.*Nenhuma baixa enviada/);
});

test("TOA lookup failure is deferred once without ever repeating an uncertain write",async()=>{
 const prepared=[],sent=[],events=[];
 const opts={active:()=>true,wait:async()=>{},notify:()=>{}};
 await runBatch(["bridge","ok","permanent"],{
  active:()=>true,update:(...args)=>events.push(args),
  async prepare(c){
   prepared.push(c);
   if(c==="permanent" || (c==="bridge" && prepared.filter(x=>x===c).length===1)){
    await readBatchToa(async()=>{throw unavailableToa();},opts);
   }
   return [{numOs:c}];
  },
  async send(c){sent.push(c.numOs);return c.numOs==="ok"?{pending:true}:{closed:true};}
 });
 assert.deepEqual(prepared,["bridge","ok","permanent","bridge","permanent"]);
 assert.deepEqual(sent,["ok","bridge"]);
 assert.equal(events.findLast(x=>x[0]==="permanent")[1],"Tratativa");
});
test("standalone VoIP keeps its materials and omits only an EMTA already in Cliente", async () => {
 const f=fixture();
 f.order.service="INSTALAR PONTO VOIP";
 const installed={serial:"112233AABBCC", type:"3 - EMTA", pool:"install"};
 const customer={...installed, serial:"112233aabbcc", pool:"customer"};
 f.capture.installed_equipment=[installed];
 f.capture.customer_equipment=[customer];
 f.capture.removed_equipment=[];
 f.capture.materials=[{code:"22025139",quantity:5}];
 f.deps.productive=code=>code==="409";
 f.deps.assign=cs=>cs.forEach(c=>{c.materialOwner=!c.batchCodeOnly;});
 f.deps.equipment=c=>({installed:c.capture.installed_equipment,removed:c.capture.removed_equipment});
 const [candidate]=selectCandidates(f.payload,[f.order],scope,f.deps);
 assert.equal(candidate.batchCodeOnly,false);
 assert.equal(candidate.materialOwner,true);
 assert.deepEqual(candidate.capture.installed_equipment,[]);
 assert.deepEqual(candidate.capture.materials,f.capture.materials);
 assert.deepEqual(candidate.batchCustomerEmta,[installed.serial]);
 assert.deepEqual(f.capture.installed_equipment,[installed]);

 const events=[];
 await runBatch([scope.contract],{
  active:()=>true,update:(...args)=>events.push(args),prepare:async()=>[candidate],send:async()=>({closed:true})
 });
 assert.match(events.at(-1)[2],/EMTA ja cadastrado no cliente .*112233AABBCC/);

 for(const different of [[],[{...customer,serial:"AABBCCDDEEFF"}],[{...customer,type:"5 - DECODER"}]]){
  f.capture.customer_equipment=different;
  const [other]=selectCandidates(f.payload,[f.order],scope,f.deps);
  assert.deepEqual(other.capture.installed_equipment,[installed]);
  assert.equal(other.batchCustomerEmta,undefined);
 }
 f.capture.customer_equipment=[customer];
 const replacement={...installed,serial:"AABBCCDDEEFF"};
 f.capture.removed_equipment=[replacement];
 const [swap]=selectCandidates(f.payload,[f.order],scope,f.deps);
 assert.deepEqual(swap.capture.installed_equipment,[installed]);
 assert.deepEqual(swap.capture.removed_equipment,[replacement]);
});

test("one shared EMTA moves once in Virtua; VoIP code only; chip gets its own serial",()=>{
 const f=fixture();
 const virtua={...f.order,id_os:2,num_os:"2612345679",service:"ADESAO - INSTALAR PONTO VIRTUA"};
 const voip={...f.order,id_os:3,num_os:"2612345680",service:"ADESAO - INSTALAR PONTO VOIP"};
 const chip={...f.order,id_os:4,num_os:"2612345681",service:"ENVIO DE CHIP VIA TECNICO"};
 const orders=[f.order,virtua,voip,chip];
 f.capture.imperium_matches=orders;
 f.capture.tasks=orders.map(o=>({os_number:o.num_os,status:"executed",close_code:o===chip?"706":"409"}));
 const emta={serial:"AABBCCDDEEFF",type:"emta"};
 const sim={serial:"89550000000000000001",type:"chip"};
 f.capture.installed_equipment=[emta,{...emta,invid:"2"},sim];
 f.capture.removed_equipment=[];
 f.capture.materials=[{code:"22026223",quantity:1}];
 f.deps.knownCode=c=>["409","706"].includes(c);
 f.deps.equipmentType=i=>i.type;
 f.deps.expectedType=s=>s===virtua.service?"emta":s===chip.service?"chip":"";
 f.deps.productive=()=>true;
 f.deps.assign=cs=>cs.forEach(c=>c.materialOwner=c.order===virtua);
 f.deps.equipment=c=>({installed:c.order===virtua?[emta]:c.order===chip?[sim]:[emta],removed:[]});
 const result=selectCandidates(f.payload,orders,scope,f.deps);
 assert.equal(result.find(c=>c.order===voip).batchCodeOnly,true);
 assert.equal(result.find(c=>c.order===virtua).materialOwner,true);
 assert.equal(result.find(c=>c.order===chip).code,"706");
 f.capture.installed_equipment[1]={...emta,serial:"112233445566"};
 assert.throws(()=>selectCandidates(f.payload,orders,scope,f.deps),/EMTAs distintos/);
 f.capture.installed_equipment[1]={...emta,invid:"2"};
 virtua.service="INSTALAR PONTO VIRTUA";
 voip.service="INSTALAR PONTO VOIP";
 assert.equal(selectCandidates(f.payload,orders,scope,f.deps).find(c=>c.order===voip).batchCodeOnly,true);
});

test("generic close error is reconciled against exact durable stock result without write",async()=>{
 const {reconcileCloseRead}=require("../static/adhesion-batch.js");
 const candidate={order:{id_os:42,contract:"12345678"},numOs:"2612345678",code:"409"};
 const response={closed:false,humanReview:true,reason:"Outra operacao esta em andamento"};
 const record={id_os:42,contract:"12345678",num_os:"2612345678",close_code:"409",state:"uncertain",category:"MATERIAL_TRANSFER_UNCERTAIN",message:"Complemento sem confirmacao"};
 const result=await reconcileCloseRead(candidate,response,async()=>({records:[record]}));
 assert.match(result.reason,/Complemento sem confirmacao/);
 assert.equal(result.closed,false);
 assert.equal((await reconcileCloseRead(candidate,response,async()=>({records:[{...record,contract:"other"}]}))).reason,response.reason);
 assert.equal((await reconcileCloseRead(candidate,response,async()=>{throw Error("offline")})).pending,true);
 assert.equal((await reconcileCloseRead(candidate,response,async()=>({records:[{...record,state:"confirmed"}]}))).closed,true);
});

test("confirmed executed chip task maps generic TOA success to official 706",()=>{
 const f=fixture();f.order.service="ENVIO DE CHIP VIA TECNICO";
 const chip={serial:"89550000000000000001",type:"chip"};
 f.capture.installed_equipment=[chip];f.capture.removed_equipment=[];
 f.capture.tasks[0].status="E";
 f.deps.executed=()=>true;
 f.deps.equipmentType=i=>i.type;
 f.deps.expectedType=()=>"chip";f.deps.knownCode=c=>["409","706"].includes(c);
 f.deps.equipment=()=>({installed:[chip],removed:[]});
 assert.equal(selectCandidates(f.payload,[f.order],scope,f.deps)[0].code,"706");
 f.capture.tasks[0].status="N";
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps),/Chip sem ICCID/);
 f.capture.tasks[0].status="E";
 f.capture.installed_equipment=[];
 assert.throws(()=>selectCandidates(f.payload,[f.order],scope,f.deps),/Chip sem ICCID/);
});
