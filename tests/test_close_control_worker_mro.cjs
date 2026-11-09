"use strict";
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const base=path.join(__dirname,"../static");
const text=(name)=>fs.readFileSync(path.join(base,name),"utf8");
test("interface em módulo próprio e Mossoró em foco",()=>{
  const html=text("index.html"),app=text("app.js"),css=text("close-control.css");
  for(const id of ["closeControlModule","closeControlWorkspace","ccCityBoard",
    "ccWorkerRefresh","ccWorkerMetrics","ccMossoroProductive","ccWorkerStatus"]){
    assert.match(html,new RegExp('id="'+id+'"'));
  }
  assert.match(html,/option value="mossoro" selected/);
  assert.match(css,/\.cc-city\[data-city="mossoro"\]/);
  assert.match(app,/window\.location\.hash === "#controle-baixas"/);
  assert.match(app,/setModule\("close-control"\)/);
  assert.match(app,/dominium:orders-updated/);
  assert.match(html,/close-control-worker\.js/);
  assert.doesNotMatch(html,/controller-central\.js|controller-central\.css|id="toaCentral"/);
});
test("worker usa somente o estado existente, sem comandos TOA/baixa",()=>{
  const worker=text("close-control-worker.js");
  const app=text("app.js");
  assert.match(app,/getWorkerStatus\(\)/);
  assert.match(app,/request\("\/api\/auto-improductive-close", \{ timeoutMs: 15000 \}\)/);
  assert.match(app,/productive_ignored/);
  assert.match(worker,/getWorkerStatus/);
  assert.match(worker,/cache TOA existente|Cache não significa|Cache vencido/);
  assert.doesNotMatch(worker,/fetch\s*\(|XMLHttpRequest|WebSocket|sendMessage\s*\(|\.post\s*\(/);
  assert.doesNotMatch(worker,/\/api\/auto-improductive-close\/toggle/);
  assert.match(worker,/state\.profiles\.mossoro\.productiveCached/);
});
test("confirmados não são inferidos de registros produtivos cacheados",()=>{
  const app=text("app.js"),board=require("../static/close-control-city-board.js");
  assert.match(app,/confirmed: row\.kind === "closed" && row\.already_closed === true/);
  assert.equal(board.classification({order:{contract:"100",os:"200",city:"mossoro"},
    decision:{key:"confirmed"}}).key,"review");
});
