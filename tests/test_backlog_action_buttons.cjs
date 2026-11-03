"use strict";
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const test=require("node:test");
const assert=require("node:assert/strict");

const src=fs.readFileSync(path.join(__dirname,"../static/backlog-analysis.js"),"utf8");
const begin=src.indexOf("  function syncRouteButtons(){");
const end=src.indexOf('  $("backlogRun").addEventListener',begin);
assert.ok(begin>=0&&end>begin,"action and button-sync source must be present");
const actualCode=src.slice(begin,end);
const pollBegin=src.indexOf("  async function pollToaRoutes(){");
const pollEnd=src.indexOf('  $("backlogFromTOA").addEventListener',pollBegin);
assert.ok(pollBegin>=0&&pollEnd>pollBegin,"real TOA polling source must be present");
const pollCode=src.slice(pollBegin,pollEnd);

function harness(){
  const keys=["backlogFromTOA","backlogUpload","backlogCompare","backlogRun",
    "backlogPilot","backlogPause","backlogDailyRefresh","backlogDownloadImage",
    "backlogSyncStatus","backlogAutoStatus","backlogUploadStatus"];
  const elements=Object.fromEntries(keys.map(id=>[id,{id,disabled:id==="backlogRun",textContent:""}]));
  const source=[
    "let busy=false,routeImportActive=false,lastRunning=false;",
    "const elements=globalThis.__elements;",
    "const $=id=>elements[id];",
    "const update=(target,message)=>{target.textContent=String(message)};",
    "async function refreshStatus(){await Promise.resolve();}",
    "async function call(){return {toa_import:globalThis.__mockState};}",
    "async function loadDailyTreatment(){globalThis.__loaded++;}",
    actualCode,pollCode,
    "globalThis.__test={action,syncRouteButtons,pollToaRoutes,setImport(value){routeImportActive=value;syncRouteButtons();},setRunning(value){lastRunning=value},busy(){return busy},importing(){return routeImportActive}};"
  ].join("\n");
  const context={__elements:elements,__mockState:{status:"idle",running:false,done:0,total:5},__loaded:0,Promise};
  vm.runInNewContext(source,context);
  context.__test.setMock=(value)=>{context.__mockState=value};
  context.__test.loaded=()=>context.__loaded;
  return {...context.__test,elements};
}

test("analyze button re-enables after a successful comparison",async()=>{
  const app=harness();
  let resolveJob;
  const job=new Promise(resolve=>{resolveJob=resolve;});
  const invoked=app.action(app.elements.backlogCompare,async()=>{await job;});
  assert.equal(app.elements.backlogCompare.disabled,true);
  assert.equal(app.elements.backlogUpload.disabled,true);
  assert.equal(app.elements.backlogFromTOA.disabled,true);
  resolveJob();
  await invoked;
  assert.equal(app.busy(),false);
  assert.equal(app.elements.backlogCompare.disabled,false);
  assert.equal(app.elements.backlogUpload.disabled,false);
  assert.equal(app.elements.backlogFromTOA.disabled,false);
});

test("all route buttons remain blocked while TOA export is actually running",async()=>{
  const app=harness();
  await app.action(app.elements.backlogFromTOA,async()=>{
    app.setImport(true);
  });
  for(const id of ["backlogFromTOA","backlogUpload","backlogCompare"])
    assert.equal(app.elements[id].disabled,true,id);
  app.setImport(false);
  for(const id of ["backlogFromTOA","backlogUpload","backlogCompare"])
    assert.equal(app.elements[id].disabled,false,id);
});

test("completed TOA polling unlocks compare and upload without page refresh",async()=>{
  const app=harness();
  app.setImport(true);
  app.setMock({status:"completed",running:false,done:5,total:5,files:[{}, {}, {}, {}, {}]});
  await app.pollToaRoutes();
  assert.equal(app.importing(),false);
  assert.equal(app.elements.backlogCompare.disabled,false);
  assert.equal(app.elements.backlogUpload.disabled,false);
  assert.equal(app.elements.backlogFromTOA.disabled,false);
  assert.equal(app.loaded(),1);
});

test("failed upload can be retried, preserving the error message",async()=>{
  const app=harness();
  const status=app.elements.backlogSyncStatus;
  await app.action(app.elements.backlogUpload,async()=>{
    throw new Error("Formato inválido");
  },status);
  assert.match(status.textContent,/Erro: Formato inválido/);
  assert.equal(app.elements.backlogUpload.disabled,false);
  assert.equal(app.elements.backlogCompare.disabled,false);
  assert.equal(app.busy(),false);
});

test("historic importer stays disabled; pilot and pause reflect server status",async()=>{
  const app=harness();
  await app.action(app.elements.backlogRun,async()=>{});
  assert.equal(app.elements.backlogRun.disabled,true);
  app.setRunning(true);
  await app.action(app.elements.backlogPilot,async()=>{});
  assert.equal(app.elements.backlogPilot.disabled,true);
  await app.action(app.elements.backlogPause,async()=>{});
  assert.equal(app.elements.backlogPause.disabled,false);
  app.setRunning(false);
  await app.action(app.elements.backlogPause,async()=>{});
  assert.equal(app.elements.backlogPause.disabled,true);
});
