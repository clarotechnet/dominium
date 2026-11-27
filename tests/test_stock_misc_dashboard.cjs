"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const dashboard = require("../static/stock-misc-dashboard.js");
const {allowedStockAnalysisRoute} = require("../deploy/hostinger-web/stock-analysis-policy.js");

test("ranking deduplicates OS and requires an identifiable technician for the quantity excess", () => {
  const items = [
    {os:"01",code:"19",quantityCheck:"above",rows:[{technician:"Júlia"},{technician:"JULIA"}]},
    {os:"01",code:"18",quantityCheck:"above",rows:[{technician:"Júlia"}]},
    {os:"02",code:"18",quantityCheck:"above",rows:[{technician:"Júlia"},{technician:"Ari"}]},
    {os:"03",code:"17",quantityCheck:"above",rows:[{technician:"Júlia"},{}]},
  ];
  assert.deepEqual(dashboard.ranking(items,"technician","above").map(row => [row.id,row.count]), [["JULIA",1]]);
  assert.deepEqual(dashboard.ranking(items,"material","above")[0].count,2);
});

test("coverage and criteria without a rule do not produce an apparent zero", () => {
  const item = {os:"01",quantityCheck:"no_rule",rows:[{codeCheck:"no_rule"},{codeCheck:"different"}]};
  const report = {usage:{id:"saved"},items:[item],missingReports:[],missing:[]};
  assert.deepEqual(dashboard.stats(report),{usage:1,excess:null,quantityChecked:0,different:1,codeChecked:1,missing:null});
  assert.equal(dashboard.stats({...report,missingReports:[{count:0}]}).missing,0);
  assert.equal(dashboard.recordsFor(report,"different")[0].rows.length,1);
});

test("uses the real worksheet headers with scheduled date and preserves the OS text", () => {
  const cells = [
    ["Contratos Sem Miscelâneas"],
    ["Data Agend.","Contrato","Núm. O.S.","Controlador","Tipo de Serviço","Cód. Serv.","Serviço"],
    ["17/11/2026",123,"001560","Pessoa A","MANUTENÇÃO",502,"Visita técnica"],
  ];
  const parse = value => dashboard.spreadsheetDay(value,() => null);
  const result = dashboard.ordersByDay(cells,parse,"mossoro","2026-11-17","2026-11-17");
  assert.equal(result.dateBasis,"scheduled");
  assert.deepEqual(result.groups.get("2026-11-17"), [
    {os:"001560",contract:"123",controller:"Pessoa A",technician:"",service:"502"}
  ]);
  assert.throws(() => dashboard.ordersByDay([[...cells[1],"Cidade"],[...cells[2],"Fortaleza"]],
    parse,"mossoro","2026-11-17","2026-11-17"),/praça diferente/);
  assert.equal(parse("31/02/2026"),"");
  const empty = dashboard.ordersByDay([cells[1]],parse,"mossoro","2026-11-17","2026-11-17");
  assert.deepEqual(empty.groups.get("2026-11-17"),[]);
});

test("proxy allows only the scoped report and the two explicit mutations", () => {
  const path = "/api/stock/analyses/misc";
  const url = path+"?city=natal&start=2026-11-16&end=2026-11-16";
  assert.equal(allowedStockAnalysisRoute("GET",url),true);
  assert.equal(allowedStockAnalysisRoute("GET",url+"&run=550e8400-e29b-41d4-a716-446655440000"),true);
  assert.equal(allowedStockAnalysisRoute("GET",url.replace("natal","all")),false);
  assert.equal(allowedStockAnalysisRoute("GET",url+"&file=anything"),false);
  assert.equal(allowedStockAnalysisRoute("POST",path+"/rules"),true);
  assert.equal(allowedStockAnalysisRoute("POST",path+"/missing"),true);
  assert.equal(allowedStockAnalysisRoute("POST",path+"/other"),false);
});
