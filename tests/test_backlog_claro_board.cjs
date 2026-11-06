"use strict";
const {test}=require("node:test"), assert=require("node:assert/strict");
const path=require("node:path"),fs=require("node:fs");
const api=require("../static/backlog-claro-board.js");
function row(city,os,contract,code,treatment){
 return {city,os_number:os,contract,validated_code:code,treatment,
   technician:"TECNICO SIMULADO",activity_status:"completed"};
}
test("quatro cidades / Natal e Parnamirim agrupadas",()=>{
 const d=api.build([row("Natal","100","500","106","IMPRODUTIVA CONFIRMADA"),
 row("Parnamirim","101","501","106","IMPRODUTIVA CONFIRMADA"),
 row("Fortaleza","102","502","","PENDENTE"),
 row("Recife","103","503","430","CONCLUIDA"),
 row("Mossoró","104","504","","DIVERGENCIA CODIGO")]);
 assert.equal(d.cities.natal.rows.length,2);
 assert.deepEqual(api.CITY_ORDER,["natal","fortaleza","recife","mossoro"]);
 assert.equal(d.totals.records,5);
 assert.equal(d.totals.improductive,2);
 assert.equal(d.totals.pending,1);
 assert.equal(d.totals.review,1);
});
test("430 não é improdutiva; código ausente exige revisão",()=>{
 assert.equal(api.statusFor(row("Natal","100","500","430","IMPRODUTIVA CONFIRMADA")).key,"review");
 assert.equal(api.statusFor(row("Natal","100","500","","IMPRODUTIVA CONFIRMADA")).key,"review");
 assert.equal(api.statusFor(row("Natal","100","500","409","IMPRODUTIVA CONFIRMADA")).key,"review");
});
test("pendente não é improdutiva",()=>{
 assert.equal(api.statusFor(row("Natal","100","500","","PENDENTE")).key,"pending");
});
test("duplicatas de mesma OS não viram dupla contagem",()=>{
 const a=row("Natal","100","500","106","IMPRODUTIVA CONFIRMADA");
 const d=api.build([a,{...a},row("Fortaleza","101","500","","PENDENTE")]);
 assert.equal(d.totals.records,2);
 assert.equal(d.cities.natal.rows.length,1);
});
test("duplicatas contraditórias migram para revisão",()=>{
 const d=api.build([
 row("Natal","100","500","106","IMPRODUTIVA CONFIRMADA"),
 row("Natal","100","500","","PENDENTE")]);
 assert.equal(d.totals.review,1);
 assert.equal(d.totals.improductive,0);
});
test("sem cidade ou contrato não declara improdutiva",()=>{
 const d=api.build([row("Outra cidade","100","500","106","IMPRODUTIVA CONFIRMADA"),
 row("Mossoró","100","","106","IMPRODUTIVA CONFIRMADA")]);
 assert.equal(d.totals.unknown,1);
 assert.equal(d.totals.review,1);
});
test("CSV exporta somente dados já carregados",()=>{
 const d=api.build([row("Fortaleza","100","500","106","IMPRODUTIVA CONFIRMADA")]);
 const csv=api.exportCsv(d);
 assert.match(csv,/FORTALEZA/);assert.match(csv,/500/);
 assert.match(csv,/IMPRODUTIVA/);
 assert.equal(csv.split(/\r?\n/).length,2);
});
test("integra em UI existente, sem HTTP TOA adicional",()=>{
 const p=path.join(__dirname,"..","static");
 const html=fs.readFileSync(path.join(p,"index.html"),"utf8");
 const js=fs.readFileSync(path.join(p,"backlog-analysis.js"),"utf8");
 const board=fs.readFileSync(path.join(p,"backlog-claro-board-ui.js"),"utf8");
 assert.match(html,/id="backlogClaroGrid"/);
 assert.match(html,/backlog-claro-board-ui\.js/);
 assert.match(js,/dominium:backlog-daily-loaded/);
 assert.doesNotMatch(board,/\bfetch\s*\(|\bXMLHttpRequest\b|\/api\/toa-live\/lookup|\/api\/orders|\/api\/close\b/);
});
