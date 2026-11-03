"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const root=path.join(__dirname,"..");
const read=name=>fs.readFileSync(path.join(root,"static",name),"utf8");

test("Estoque Diario emite mudanca de aba e nao falsifica mudanca de modulo",()=>{
 const daily=read("daily-stock.js");
 assert.match(daily,/new CustomEvent\("dominium:stock-tab-change",\s*\{detail:\{tab:"daily"\}\}\)/);
 assert.doesNotMatch(daily,/new Event\("dominium:module-change"\)/);
});

test("DESC suporta evento legado sem detail sem interromper a navegacao",()=>{
 const code=read("disconnection.js");
 const found=code.match(/document\.addEventListener\('dominium:module-change',\s*(event=>[^;]+)\);/);
 assert.ok(found,"listener do modulo DESC deve existir");
 let activated=0,deactivated=0;
 const controller={activate:()=>activated++,deactivate:()=>deactivated++};
 const listener=vm.runInNewContext("("+found[1]+")",{controller});
 assert.doesNotThrow(()=>listener({type:"dominium:module-change"}));
 assert.equal(deactivated,1);
 listener({detail:{module:"disconnection"}});
 assert.equal(activated,1);
 listener({detail:{module:"stock"}});
 assert.equal(deactivated,2);
});
