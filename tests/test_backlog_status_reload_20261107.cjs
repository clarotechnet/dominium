"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path");
const root=path.join(__dirname,"..");
const js=fs.readFileSync(path.join(root,"static/backlog-analysis.js"),"utf8");
const html=fs.readFileSync(path.join(root,"static/index.html"),"utf8");
test("hard reload restores TOA capture state even without module-change event",()=>{
  const end=js.slice(js.lastIndexOf('document.addEventListener("dominium:module-change"'));
  assert.match(end,/\n  refreshStatus\(\);[\s\S]{0,400}\n  pollToaRoutes\(\);\n  setInterval/);
  const routeGetter=js.slice(js.indexOf("async function pollToaRoutes()"),js.indexOf('$("backlogFromTOA").addEventListener'));
  assert.match(routeGetter,/call\("\/api\/backlog\/year\/status"\)/);
  assert.doesNotMatch(routeGetter,/post\(|\/toa\/export|\/toa\/buckets/);
});
test("completed import renders persisted 5\/5 state; history error remains identified as previous run",()=>{
  assert.match(js,/state\.status==="completed"\?"Cinco rotas do TOA importadas/);
  assert.match(js,/"Última execução: "\+run\.status/);
  assert.match(js,/"Erro da última tentativa: "/);
});
test("cache-busts the status-polling javascript without changing application routes",()=>{
  assert.match(html,/backlog-analysis\.js\?v=20261107-restore-status-1/);
  assert.ok(!html.includes("backlog-analysis.js?v=20261103-route-buttons-1"));
});
