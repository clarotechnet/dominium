"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const root=path.join(__dirname,"..");
function setup(respond){
 const elements=new Map(),calls=[];
 function node(id){
  if(!elements.has(id)) elements.set(id,{id,value:"",hidden:false,disabled:false,textContent:"",style:{},events:{},attrs:{},children:[],
   addEventListener(event,callback){this.events[event]=callback;},
   setAttribute(key,value){this.attrs[key]=value;},
   replaceChildren(...items){this.children=items;},appendChild(value){this.children.push(value);}});
  return elements.get(id);
 }
 const document={getElementById:node,createElement:()=>node("created_"+elements.size),
  createDocumentFragment:()=>({children:[],appendChild(item){this.children.push(item);}}),addEventListener:()=>{}};
 const state={profile:"natal",authUser:{role:"admin"},activeModule:"stock"};
 node("stockDailyRangeStart").value="2026-11-03";node("stockDailyRangeEnd").value="2026-11-03";
 const context={document,state,Intl,Date,Map,Promise,encodeURIComponent,
  request:(url)=>{calls.push(url);return respond(url);},
  requestBlob:async()=>{throw Error("Not expected")},saveBlob:()=>{}};
 vm.runInNewContext(fs.readFileSync(path.join(root,"static","stock-daily-analysis-ui.js"),"utf8"),context);
 return {node,calls};
}
test("Consultar periodo apresenta carregamento e nao exige Excel",async()=>{
 let finish;const pending=new Promise(resolve=>{finish=resolve});
 const {node,calls}=setup(()=>pending);
 node("stockDailyAnalysisRefresh").events.click();
 assert.equal(calls.length,1);
 assert.match(calls[0],/city=natal&start=2026-11-03&end=2026-11-03/);
 assert.equal(node("stockDailyAnalysisRefresh").disabled,true);
 assert.equal(node("stockDailyAnalysisRefresh").textContent,"Consultando período...");
 assert.match(node("stockDailyAnalysisMessage").textContent,/Consultando histórico/);
 assert.equal(node("stockDailyAnalysisPanel").attrs["aria-busy"],"true");
 finish({ok:true,selected:null,latest:{id:"old",date:"2026-10-01"},history:[]});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(node("stockDailyAnalysisRefresh").disabled,false);
 assert.equal(node("stockDailyAnalysisRefresh").textContent,"Consultar período");
 assert.equal(node("stockDailyAnalysisPanel").attrs["aria-busy"],"false");
 assert.match(node("stockDailyAnalysisMessage").textContent,/Nenhum registro encontrado/);
 assert.doesNotMatch(node("stockDailyAnalysisMessage").textContent,/Última análise disponível/);
});
test("Datas incompletas ou invertidas exibem erro sem consultar API",()=>{
 const {node,calls}=setup(async()=>({selected:null,latest:null,history:[]}));
 node("stockDailyRangeEnd").value="";
 node("stockDailyAnalysisRefresh").events.click();
 assert.equal(calls.length,0);
 assert.match(node("stockDailyAnalysisMessage").textContent,/Preencha a data inicial e a data final/);
 node("stockDailyRangeEnd").value="2026-11-01";
 node("stockDailyAnalysisRefresh").events.click();
 assert.equal(calls.length,0);
 assert.match(node("stockDailyAnalysisMessage").textContent,/Data inicial maior/);
});
test("Importacao de planilha fica em secao opcional separada da consulta",()=>{
 const html=fs.readFileSync(path.join(root,"static","index.html"),"utf8");
 assert.match(html,/<details id="stockDailyImportDetails"/);
 assert.match(html,/<summary>Registrar Excel histórico \(opcional\)<\/summary>/);
 assert.match(html,/<input id="stockDailyAnalysisFile" type="file"/);
});
