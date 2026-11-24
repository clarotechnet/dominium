"use strict";
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const {execFileSync}=require("node:child_process");
const {performance}=require("node:perf_hooks");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
function setup(source,n,sends,bairros) {
  source=source.replace("operationalProfile, putShared\n","operationalProfile, putShared, populateNeighborhoods\n");
  const ctx={document:{addEventListener(){}},window:{__DOMINIUM_FORA_ROTA_TEST__:true},console};
  vm.runInNewContext(source,ctx);
  const api=ctx.DominiumForaRotaTestHooks;
  const records=Array.from({length:n},(_,i)=>({contract:String(100000+i),city:i%4===0?"FORTALEZA":"NATAL",bairro:i%17===0?"":"BAIRRO "+(i%bairros)}));
  api.state.claroRecords=records;
  api.state.clean106ByCity={natal_parnamirim:records.map(r=>r.contract),fortaleza:records.map(r=>r.contract)};
  api.state.sentContracts=Object.fromEntries(Array.from({length:sends},(_,i)=>[i,{contract:String(100000+i),city:i%5===0?"":i%3===0?"fortaleza":"natal_parnamirim"}]));
  Object.assign(api.els,{cidade:{value:"natal_parnamirim"},bairro:{value:"",innerHTML:""}});
  return api;
}
function run(source,n,s,b) {
  const api=setup(source,n,s,b);
  const start=performance.now();
  api.populateNeighborhoods();
  return {ms:performance.now()-start,html:api.els.bairro.innerHTML,available:api.availableRecordsForBairro("").length};
}
const before=execFileSync("git",["show","6fd585d:static/backlog-fora-rota.js"],{cwd:root,encoding:"utf8"});
const after=fs.readFileSync(path.join(root,"static","backlog-fora-rota.js"),"utf8");
const old=run(before,600,300,60);
const fixed=run(after,600,300,60);
assert.equal(fixed.available,old.available);
assert.equal(fixed.html,old.html);
console.log("SAME RESULTS | before "+old.ms.toFixed(1)+" ms | after "+fixed.ms.toFixed(1)+" ms | "+(old.ms/fixed.ms).toFixed(1)+"x");
const full=run(after,8039,1795,150);
console.log("FULL SYNTHETIC SIZE | 8039 contracts / 1795 sent | "+full.ms.toFixed(1)+" ms | "+full.available+" available");
assert.ok(full.ms<2000,"large base processing should remain responsive");
