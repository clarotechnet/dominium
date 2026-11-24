"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const src = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8").replace(/\r\n/g, "\n");
const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
function extract(name) {
  const start = src.indexOf("function " + name + "(");
  assert.notEqual(start, -1);
  const end = src.indexOf("\n}", start);
  assert.notEqual(end, -1);
  return src.slice(start, end + 2);
}
const parse = new Function(extract("parseManualCloseContracts") + ";return parseManualCloseContracts")();
test("accepts pasted newlines, comma, whitespace and semicolons; preserves zeros and deduplicates", () => {
  assert.deepEqual(parse("12323123\n21343243, 35234343; 65934934\t0012345\n12323123"), {
    contracts: ["12323123","21343243","35234343","65934934","0012345"], invalid: [], duplicates: 1
  });
});
test("rejects partial, decimal or nonnumeric tokens", () => {
  assert.deepEqual(parse("abc12345, 1234, 12345.0, 123456"), {
    contracts: ["123456"], invalid: ["abc12345","1234","12345.0"], duplicates: 0
  });
});
const routeMatch = new Function(
  "const semiAutoCanonicalRoute = x=>String(x||'').toUpperCase(); const automationProviderLabel=x=>x; const semiAutoJobRoutePrefixes=()=>['NTL'];"
  + extract("semiAutoRouteMatchesJob") + ";return semiAutoRouteMatchesJob"
)();
test("manual batch refuses other bases, missing route, ADM in normal scope, and unspecified ADM", () => {
  const normal = {manualBatch:true,isDisconnect:false};
  const adm = {manualBatch:true,isDisconnect:true};
  assert.equal(routeMatch({route_provider:"NTL-DMV-TEC"},normal),true);
  assert.equal(routeMatch({route_provider:"NTL-DMV-ADM"},normal),false);
  assert.equal(routeMatch({route_provider:"NTL-DMV-ADM"},adm),true);
  assert.equal(routeMatch({route_provider:"NTL-DMV"},adm),false);
  assert.equal(routeMatch({route_provider:"FTZ-DMV-ADM"},adm),false);
  assert.equal(routeMatch({},normal),false);
});
const candidates = new Function(
  "const state={closeCodes:[{code:'409'}]}; const semiAutoRouteMatchesJob=()=>true; const disconnectActivityComplete=x=>x==='completed'; const disconnectTaskExecuted=x=>x==='E'; const toaLiveImperiumMatch=(c,t)=>t.match; const semiAutoAssignMaterialOwners=()=>{};"
  + extract("semiAutoCandidates") + ";return semiAutoCandidates"
)();
const job={manualBatch:true,contract:"123456",osNumbers:["1"]};
const task={status:"E",close_code:"409",os_number:"1",match:{num_os:"1",contract:"123456"}};
const capture={activity_status:"completed",contract:"123456",tasks:[task]};
test("only selected contract and OS, completed activities, executed tasks; duplicate OS blocked", () => {
  assert.equal(candidates({results:[capture]},job).length,1);
  assert.equal(candidates({results:[{...capture,contract:"654321"}]},job).length,0);
  assert.equal(candidates({results:[{...capture,activity_status:"started"}]},job).length,0);
  assert.equal(candidates({results:[{...capture,tasks:[{...task,match:{num_os:"2",contract:"123456"}}]}]},job).length,0);
  assert.throws(()=>candidates({results:[capture,capture]},job),/duplicada/);
});
test("explicit start and scope, queue guards, no agenda-wide fallback", () => {
  assert.match(html,/id="manualCloseContracts"/);
  assert.match(html,/id="manualCloseScope"/);
  assert.match(src,/window\.confirm\("Enviar baixas reais/);
  assert.match(src,/const records = parsed\.contracts\.map/);
  assert.match(src,/state\.semiAutoStopRequested \|\| !state\.semiAutoRunning/);
  assert.match(src,/!job\.manualBatch && job\.state === "skipped"/);
});
