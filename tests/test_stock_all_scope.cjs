"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const root=path.resolve(__dirname,"..");
const navigation=fs.readFileSync(path.join(root,"static/stock-nav.js"),"utf8");
const analysis=fs.readFileSync(path.join(root,"static/stock-daily-analysis-ui.js"),"utf8");
const report=fs.readFileSync(path.join(root,"static/stock-report-preview-ui.js"),"utf8");

function getScopeModel(allCities,role="admin"){
  const state={allCities,profile:"fortaleza",authUser:{role}};
  const start=analysis.indexOf("const currentCity=");
  const end=analysis.indexOf("function status(",start);
  assert.ok(start>=0&&end>start);
  const ctx={state};
  vm.runInNewContext(analysis.slice(start,end)+"\nglobalThis.__result={currentCity,canWrite};",ctx);
  return ctx.__result;
}
test("global stock selection reads city=all and disables writes",()=>{
  const model=getScopeModel(true);
  assert.equal(model.currentCity(),"all");
  assert.equal(model.canWrite(),false);
  assert.match(analysis,/el\("stockDailyAnalysisImport"\)\.hidden=!canWrite\(\)\|\|currentCity\(\)==="all"/);
  assert.match(analysis,/if\(city==="all"\)el\("stockDailyAnalysisDownload"\)\.title=/);
});
test("selected city still permits normal authorized stock functions",()=>{
  const model=getScopeModel(false);
  assert.equal(model.currentCity(),"fortaleza");
  assert.equal(model.canWrite(),true);
  assert.equal(getScopeModel(false,"viewer").canWrite(),false);
});
test("global stock navigation opens equipment workspace, not a prior-city report",()=>{
  const start=navigation.indexOf("  function openAllCityReadOnly() {");
  const end=navigation.indexOf("  function setQualityAddress",start);
  assert.ok(start>=0&&end>start);
  let reports=0,equipment=0,highlight=0;
  const ctx={
    state:{activeModule:"stock",allCities:true},
    reportsTab:{click(){reports++}},
    document:{querySelector(selector){
      assert.match(selector,/equipamentos/);
      return {click(){equipment++}};
    }},
    updateHighlight(){highlight++}
  };
  vm.runInNewContext(navigation.slice(start,end)+"\nglobalThis.open=openAllCityReadOnly;",ctx);
  ctx.open();
  assert.equal(reports,1);
  assert.equal(equipment,1);
  assert.equal(highlight,1);
  ctx.state.allCities=false;
  ctx.open();
  assert.equal(reports,1);
});
test("old-city QUERY and Suspects cannot display under global selection",()=>{
  assert.match(report,/if\(state\.activeModule==="stock" && state\.allCities && name!=="equipamentos"\)/);
  assert.match(report,/if\(state\.allCities \|\| !\["query","suspeitos"\]\.includes\(kind\)\)return/);
});
test("scope change invalidates and reloads any visible daily equipment view",()=>{
  assert.match(analysis,/document\.addEventListener\("dominium:scope-change"/);
  assert.match(analysis,/el\("stockDailyAnalysisTable"\)\.replaceChildren\(\)/);
  assert.match(analysis,/el\("stockDailyAnalysisImport"\)\.hidden=!canWrite\(\)\|\|currentCity\(\)==="all"/);
});
