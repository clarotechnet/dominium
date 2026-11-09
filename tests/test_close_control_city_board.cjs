"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path");
const board=require("../static/close-control-city-board.js");
const engine=require("../static/close-control-engine.js");
const now=new Date(2026,10,6,9,37);
function entry(order,decision){
 return {order:{os:"OS1",contract:"C1",city:"natal",technician:"Teste",windowStart:"08:00",windowEnd:"11:00",...order},
   decision:decision||{key:"route_not_imported",label:"Aguardar importação"}};
}
test("as quatro colunas são cidades de baixa, não backlog Claro",()=>{
 assert.deepEqual(board.CITIES,["natal","fortaleza","recife","mossoro"]);
 assert.equal(board.LABELS.natal,"NATAL / PARNAMIRIM");
 assert.equal(board.LABELS.mossoro,"MOSSORÓ");
});
test("normaliza cidades e só usa cidade comprovada da O.S.",()=>{
 assert.equal(board.cityOf("Natal / Parnamirim"),"natal");
 assert.equal(board.cityOf("Mossoró"),"mossoro");
 assert.equal(board.cityOf("FTZ"),"fortaleza");
 assert.equal(board.cityOf("JCR"),"recife");
 assert.equal(board.cityOf("TODOS"),null);
 assert.equal(board.cityOf(""),null);
});
test("baixa confirmada exige evidência explícita do Imperium",()=>{
 const ok=entry({confirmationState:"confirmed"},{key:"confirmed",label:"Baixa confirmada"});
 assert.equal(board.classification(ok).key,"confirmed");
 const uncertain=entry({}, {key:"confirmed",label:"Baixa confirmada"});
 assert.equal(board.classification(uncertain).key,"review");
});
test("concluída TOA sem prova de baixa gera revisão, não confirmação",()=>{
 const x=entry({toaStatus:"concluida",code:"430",routeImported:true,
  orderImported:true,imperiumOrderPresent:true,windowStart:"08:00",windowEnd:"11:00"});
 const d=engine.decide(x.order,now);
 assert.equal(d.key,"review_completed");
 assert.equal(board.classification({order:x.order,decision:d}).key,"review");
});
test("pendente, iniciada e em rota são acompanhadas, não improdutivas",()=>{
 for(const status of ["pendente","iniciada","em_rota"]){
   const v=entry({toaStatus:status},{key:"cooldown",label:status});
   assert.equal(board.classification(v).key,"in_progress");
 }
});
test("agrupa O.S. por cidade e distingue erros, baixadas e dúvidas",()=>{
 const items=[
  entry({os:"N1",city:"natal",confirmationState:"confirmed"},{key:"confirmed",label:"Confirmada"}),
  entry({os:"F1",city:"fortaleza"},{key:"route_not_imported",label:"Rota não importada"}),
  entry({os:"R1",city:"recife",toaStatus:"iniciada"},{key:"cooldown",label:"Iniciada"}),
  entry({os:"M1",city:"mossoro"},{key:"error",label:"Erro",review:true}),
 ];
 const d=board.build(items);
 assert.equal(d.totals.os,4);
 assert.equal(d.cities.natal.counts.confirmed,1);
 assert.equal(d.cities.fortaleza.counts.unverified,1);
 assert.equal(d.cities.recife.counts.in_progress,1);
 assert.equal(d.cities.mossoro.counts.review,1);
});
test("repetição divergente de contrato/OS não duplica confirmação",()=>{
 const a=entry({os:"321",city:"mossoro"},{key:"confirmed",label:"Confirmada"});
 a.order.confirmationState="confirmed";
 const b=entry({os:"321",city:"mossoro"},{key:"error",label:"Falha",review:true});
 const d=board.build([a,b]);
 assert.equal(d.cities.mossoro.items.length,1);
 assert.equal(d.cities.mossoro.counts.review,1);
 assert.equal(d.totals.confirmed,0);
 assert.equal(d.duplicates,1);
});
test("O.S. sem cidade permanece não classificada",()=>{
 const d=board.build([entry({city:"todos"}),entry({city:"natal"})]);
 assert.equal(d.unknown,1);
 assert.equal(d.totals.os,1);
});
test("demo de janela 09:37 usa quatro cidades, sem requisições",()=>{
 const p=engine.plan(engine.demoOrders(),now);
 const d=board.build(p.rows);
 assert.equal(d.totals.os,10);
 assert.deepEqual(board.CITIES.map(city=>d.cities[city].items.length),[2,3,2,3]);
 assert.equal(p.networkCalls,0);
 assert.equal(p.closesSent,0);
});
test("quadro isolado em Controle de baixas, módulo Backlog preservado",()=>{
 const root=path.join(__dirname,"../static");
 const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
 const city=fs.readFileSync(path.join(root,"close-control-city-board.js"),"utf8");
 const ui=fs.readFileSync(path.join(root,"close-control-ui.js"),"utf8");
 const backlog=fs.readFileSync(path.join(root,"backlog-analysis.js"),"utf8");
 assert.match(html,/id="closeControlWorkspace"/);
 assert.match(html,/id="ccCityBoard"/);
 assert.match(html,/close-control-city-board\.js/);
 assert.doesNotMatch(html,/id="backlogClaroGrid"/);
 assert.doesNotMatch(html,/backlog-claro-board/);
 assert.doesNotMatch(backlog,/dominium:backlog-daily-loaded/);
 assert.match(ui,/renderCityBoard/);
 assert.doesNotMatch(city,/\bfetch\s*\(|XMLHttpRequest|WebSocket|\/api\/|sendMessage\(/);
});

test("fila em movimento: ativa primeiro, erros recentes em seguida, confirmadas no fim",()=>{
 const make=(os,processingState,queueSequence,decision,extra={})=>({
   order:{os,contract:"C"+os,city:"natal",processingState,queueSequence,...extra},
   decision,
 });
 const items=[
   make("300","confirmed",5,{key:"confirmed",label:"Confirmada"},{confirmationState:"confirmed"}),
   make("200","error",7,{key:"manual_review",review:true,label:"Falha"}),
   make("100","processing",8,{key:"cooldown",label:"Iniciada"}),
   make("201","error",3,{key:"manual_review",review:true,label:"Falha"}),
   make("301","confirmed",4,{key:"confirmed",label:"Confirmada"},{confirmationState:"confirmed"}),
   make("400","queued",6,{key:"cooldown",label:"Pendente"}),
 ];
 const result=board.build(items).cities.natal;
 assert.deepEqual(result.items.map(x=>x.order.os),["100","200","201","400","300","301"]);
 assert.equal(result.counts.active,1);
 assert.equal(result.counts.review,2);
 assert.equal(result.counts.confirmed,2);
});
test("erro recém-detectado entra antes dos erros anteriores sem sumir",()=>{
 const error=n=>({order:{os:String(n),contract:"C"+n,city:"mossoro",
    processingState:"error",queueSequence:n},
   decision:{key:"manual_review",review:true,label:"Falha"}});
 const d=board.build([error(1),error(2),error(3)]);
 assert.deepEqual(d.cities.mossoro.items.map(x=>x.order.os),["3","2","1"]);
});
test("o modo demonstração tem botões próprios e respeita preferência por movimento reduzido",()=>{
 const root=path.join(__dirname,"../static");
 const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
 const css=fs.readFileSync(path.join(root,"close-control.css"),"utf8");
 const ui=fs.readFileSync(path.join(root,"close-control-ui.js"),"utf8");
 assert.match(html,/id="ccDemoError"/);
 assert.match(html,/id="ccDemoSuccess"/);
 assert.match(html,/id="ccDemoNext"/);
 assert.match(ui,/animateReorderedCards/);
 assert.match(ui,/processingState = "error"/);
 assert.match(ui,/confirmationState = "confirmed"/);
 assert.match(css,/prefers-reduced-motion:reduce/);
 assert.match(css,/cc-demo-actions\[hidden\]/);
});
