"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const code=fs.readFileSync(path.join(__dirname,"../static/stock-daily-analysis-ui.js"),"utf8");
const html=fs.readFileSync(path.join(__dirname,"../static/index.html"),"utf8");

class Element {
 constructor(id){
  this.id=id;this.hidden=false;this.disabled=false;this.value="";
  this.textContent="";this.style={};this.children=[];this.handlers={};this.attrs={};
  this.classList={toggle:()=>{},add:()=>{},remove:()=>{}};
 }
 addEventListener(type,handler){(this.handlers[type]??=[]).push(handler);}
 click(){for(const fn of this.handlers.click||[])fn({target:this});}
 setAttribute(name,value){this.attrs[name]=value;}
 replaceChildren(...children){this.children=children;}
 appendChild(child){this.children.push(child);}
}
function mount(request){
 const nodes=new Map();
 const get=id=>{
  if(!nodes.has(id))nodes.set(id,new Element(id));
  return nodes.get(id);
 };
 get("stockDailyRangeStart").value="2026-11-01";
 get("stockDailyRangeEnd").value="2026-11-02";
 get("stockDailyAnalysisDate").value="2026-11-02";
 get("stockDailyAnalysisLoading").hidden=true;
 const state={profile:"natal",authUser:{role:"admin"},activeModule:"stock"};
 const document={
  getElementById:get,
  addEventListener:()=>{},
  createElement:tag=>new Element(tag),
  createDocumentFragment:()=>new Element("fragment")
 };
 vm.runInNewContext(code,{document,state,request,requestBlob:()=>{},saveBlob:()=>{},console});
 return {get,state};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test("period search shows visible loading then explicit empty result and enables a new search",async()=>{
 assert.match(html,/id="stockDailyAnalysisLoading"/);
 assert.match(html,/stock-daily-analysis-ui\.js\?v=20261103-global-1/);
 let complete,calls=0,url;
 const {get}=mount(next=>{
  calls++;url=next;
  return new Promise(resolve=>{complete=resolve;});
 });
 get("stockDailyAnalysisOpen").click();
 assert.equal(calls,1);
 assert.equal(url,"/api/stock/analyses/daily?city=natal&start=2026-11-01&end=2026-11-02");
 assert.equal(get("stockDailyAnalysisRefresh").disabled,true);
 assert.equal(get("stockDailyAnalysisRefresh").textContent,"Consultando período...");
 assert.equal(get("stockDailyAnalysisLoading").hidden,false);
 assert.match(get("stockDailyAnalysisMessage").textContent,/Consultando histórico/);
 complete({ok:true,selected:null,latest:null,history:[]});
 await tick();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,false);
 assert.equal(get("stockDailyAnalysisLoading").hidden,true);
 assert.match(get("stockDailyAnalysisMessage").textContent,/Consulta concluída/);
 assert.match(get("stockDailyAnalysisMessage").textContent,/nenhum arquivo encontrado/);
 assert.match(get("stockDailyAnalysisMessage").textContent,/01\/11\/2026 a 02\/11\/2026/);
 get("stockDailyAnalysisRefresh").click();
 assert.equal(calls,2,"clicked search must create a fresh request");
 complete({ok:true,selected:null,latest:null,history:[]});
 await tick();
});

test("failed request shows feedback and resets loading controls",async()=>{
 const {get}=mount(()=>Promise.reject(new Error("Conexão temporariamente indisponível")));
 get("stockDailyAnalysisRefresh").click();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,true);
 await tick();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,false);
 assert.equal(get("stockDailyAnalysisLoading").hidden,true);
 assert.match(get("stockDailyAnalysisMessage").textContent,/Falha na consulta/);
 assert.match(get("stockDailyAnalysisMessage").textContent,/Conexão temporariamente indisponível/);
});

test("invalid date interval is visible and never sent to backend",async()=>{
 let calls=0;
 const {get}=mount(()=>{calls++;return Promise.resolve({ok:true,history:[],selected:null});});
 get("stockDailyRangeStart").value="2026-11-03";
 get("stockDailyRangeEnd").value="2026-11-01";
 get("stockDailyAnalysisRefresh").click();
 await tick();
 assert.equal(calls,0);
 assert.equal(get("stockDailyAnalysisRefresh").disabled,false);
 assert.match(get("stockDailyAnalysisMessage").textContent,/data inicial não pode ser posterior/);
});
