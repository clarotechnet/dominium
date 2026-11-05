"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const html=fs.readFileSync(path.join(__dirname,"../static/index.html"),"utf8");
const policy=require("../deploy/hostinger-web/stock-analysis-policy.js");
const original="2026-11-03";

test("the Imperium source has its own explicit controls and does not claim six-tab completion",()=>{
 for(const id of ["stockDailyImperiumExtract","stockDailyImperiumHistory",
                  "stockDailyImperiumDownload","stockDailyImperiumMessage",
                  "stockDailyImperiumTabs","stockDailyImperiumTable"]){
   assert.match(html,new RegExp('id="'+id+'"'));
 }
 assert.match(html,/Consultar historico/);
 assert.match(html,/a conciliacao com Atlas para gerar as seis abas ainda esta em desenvolvimento/);
 assert.match(html,/stock-daily-analysis-ui\.js\?v=20261105-imperium-source-1/);
 assert.doesNotMatch(html,/Executar tratativa no Imperium \(aguardando integra/);
});
test("only exact authorized source URLs pass the Hostinger allowlist",()=>{
 const p="/api/stock/analyses/imperium";
 const runs=p+"/runs?city=natal&start="+original+"&end="+original;
 const sampleId="a".repeat(32);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/extract"),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",runs),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/runs/"+sampleId+"/sheets/0"),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/runs/"+sampleId+"/sheets/1"),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/runs/"+sampleId+"/export"),true);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/runs"),false);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/runs?city=all&start="+original+"&end="+original),false);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/runs/"+sampleId+"/sheets/2"),false);
 assert.equal(policy.allowedStockAnalysisRoute("DELETE",p+"/extract"),false);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/extract?x=1"),false);
});
