"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const engine=require("../static/close-control-engine.js");
const at=(h,m)=>new Date(2026,10,6,h,m);
function base(other={}) {
 return {os:"DEMO",contract:"C001",windowStart:"08:00",windowEnd:"11:00",
 routeImported:true,orderImported:true,imperiumOrderPresent:true,
 toaStatus:"pendente",toaObservedAt:"2026-11-06T09:37:00-03:00",...other};
}
test("janela 09:37: apenas 08-11 e 08-22, não 11-14/12-14",()=>{
 const plan=engine.plan(engine.demoOrders(),at(9,37));
 assert.equal(plan.counts.total,10);
 assert.equal(plan.rows.filter(x=>x.decision.key==="future_window").length,7);
 assert.equal(plan.rows.filter(x=>x.decision.key==="future_window"&&x.decision.due).length,0);
 assert.equal(plan.counts.ready,1);
 assert.equal(plan.counts.contractsDue,0);
 assert.equal(plan.networkCalls,0);
 assert.equal(plan.closesSent,0);
});
test("janela fecha no limite e só abre no início",()=>{
 assert.equal(engine.decide(base(),at(7,59)).key,"future_window");
 assert.notEqual(engine.decide(base(),at(8,0)).key,"future_window");
 assert.equal(engine.decide(base(),at(11,0)).key,"expired_window");
 assert.equal(engine.decide(base({windowStart:"12:00",windowEnd:"14:00"}),at(11,59)).key,"future_window");
 assert.equal(engine.decide(base({windowStart:"08:00",windowEnd:"22:00"}),at(21,59)).key,"due");
 assert.equal(engine.decide(base({windowStart:"08:00",windowEnd:"22:00"}),at(22,0)).key,"expired_window");
});
test("não consultar antes de importar rota e O.S.",()=>{
 assert.equal(engine.decide(base({routeImported:null,toaStatus:"nao_consultada"}),at(9,37)).key,"route_not_imported");
 assert.equal(engine.decide(base({routeImported:true,orderImported:false,toaStatus:"nao_consultada"}),at(9,37)).key,"order_not_imported");
 assert.equal(engine.decide(base({imperiumOrderPresent:false,toaStatus:"concluida"}),at(9,37)).key,"order_not_imported");
});
test("iniciada: 15 → 20 → 30, mantendo 30 nas tentativas seguintes",()=>{
 for(const [round,expected] of [[1,15],[2,20],[3,30],[4,30],[8,30]]){
  const job=base({toaStatus:"iniciada",startedObservations:round});
  const d=engine.decide(job,at(9,37));
  assert.equal(d.delayMinutes,expected);
  assert.equal(d.nextAt,at(9,37+expected).getTime());
  assert.equal(d.due,false);
  const after=engine.decide(job,at(10,10));
  assert.equal(after.key,"due");
 }
});
test("pendente/em rota: sempre 30 min",()=>{
 for(const toaStatus of ["pendente","em_rota"]){
  const before=engine.decide(base({toaStatus}),at(9,55));
  assert.equal(before.delayMinutes,30);
  assert.equal(before.key,"cooldown");
  assert.equal(engine.decide(base({toaStatus}),at(10,7)).key,"due");
 }
});
test("concluída só libera prévia com detalhes, importação e confirmação negativa Imperium",()=>{
 const job=base({toaStatus:"concluida",productive:true,code:"409",
  toaDetailConfirmed:true,codeConfirmed:true,materialsValidated:true,
  identityValidated:true,bucketValidated:true,imperiumAlreadyClosed:false});
 const ok=engine.decide(job,at(9,37));
 assert.equal(ok.key,"ready");assert.equal(ok.readyFor,"productive");
 assert.equal(engine.decide({...job,materialsValidated:false},at(9,37)).key,"review_completed");
 assert.equal(engine.decide({...job,imperiumAlreadyClosed:null},at(9,37)).key,"imperium_status_unknown");
 assert.equal(engine.decide({...job,imperiumAlreadyClosed:true},at(9,37)).key,"confirmed");
 assert.equal(engine.decide({...job,productive:undefined},at(9,37)).review,true);
});
test("incerta/confirmada não repetir baixa",()=>{
 assert.equal(engine.decide(base({confirmationState:"uncertain"}),at(9,37)).key,"uncertain");
 assert.equal(engine.decide(base({confirmationState:"sent"}),at(9,37)).key,"uncertain");
 assert.equal(engine.decide(base({confirmationState:"confirmed"}),at(9,37)).key,"confirmed");
});
test("erro e janela inválida vão para tratativa humana",()=>{
 assert.equal(engine.decide(base({toaStatus:"erro"}),at(9,37)).review,true);
 assert.equal(engine.decide(base({windowEnd:"xx:yy"}),at(9,37)).review,true);
 assert.equal(engine.decide(base({contract:""}),at(9,37)).review,true);
});
test("lote agrupa contrato e nunca envia requisição",()=>{
 const rows=[base({os:"OS1",toaStatus:"nao_consultada"}),base({os:"OS2",toaStatus:"nao_consultada"}),base({os:"OS3",contract:"C002",toaStatus:"nao_consultada"})];
 const p=engine.plan(rows,at(9,37));
 assert.equal(p.counts.due,3);assert.equal(p.counts.contractsDue,2);
 assert.deepEqual(p.lookups[0].os,["OS1","OS2"]);
 assert.equal(p.networkCalls,0);assert.equal(p.closesSent,0);
});
test("nenhum acesso de rede no motor determinístico",()=>{
 const fs=require("node:fs"),source=fs.readFileSync(require("node:path").join(__dirname,"../static/close-control-engine.js"),"utf8");
 assert.doesNotMatch(source,/\bfetch\s*\(|XMLHttpRequest|WebSocket|sendMessage|\/api\/.*\/close/);
});
