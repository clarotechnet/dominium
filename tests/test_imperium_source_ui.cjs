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
 assert.match(html,/Consultar período \(DataSnap → Supabase\)/);
 assert.match(html,/Consultar histórico anterior/);
 assert.match(html,/id="stockDailyLiveStatus"/);
 assert.match(html,/id="stockDailyLiveTable"/);
 assert.match(html,/Dados atuais Imperium salvos no Supabase/);
 assert.match(html,/stock-daily-analysis-ui\.js\?v=20261105-datasnap-supabase-2/);
 assert.doesNotMatch(html,/Executar tratativa no Imperium \(aguardando integra/);
});
test("only exact authorized source URLs pass the Hostinger allowlist",()=>{
 const p="/api/stock/analyses/imperium";
 const runs=p+"/runs?city=natal&start="+original+"&end="+original;
 const sampleId="a".repeat(32);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/extract"),true);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/live"),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/live?city=mossoro&start="+original+"&end="+original),true);
 assert.equal(policy.allowedStockAnalysisRoute("GET",p+"/live/550e8400-e29b-41d4-a716-446655440000/data?city=mossoro&category=seriais_tratados&page=1"),true);
 assert.equal(policy.allowedStockAnalysisRoute("POST",p+"/live?city=mossoro"),false);
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
