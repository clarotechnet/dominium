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
function mount(request, options={}){
 const nodes=new Map();
 const get=id=>{
  if(!nodes.has(id))nodes.set(id,new Element(id));
  return nodes.get(id);
 };
 get("stockDailyRangeStart").value="2026-11-01";
 get("stockDailyRangeEnd").value="2026-11-02";
 get("stockDailyAnalysisDate").value="2026-11-02";
 get("stockDailyAnalysisLoading").hidden=true;
 get("stockDailyLiveCategory").value="seriais_tratados";
 const state={profile:"mossoro",allCities:false,
              authUser:{role:options.role||"admin"},activeModule:"stock"};
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

test("legacy history remains an explicit separate action",async()=>{
 assert.match(html,/id="stockDailyAnalysisLoading"/);
 assert.match(html,/stock-daily-analysis-ui\.js\?v=20261105-datasnap-supabase-2/);
 let finish,calls=0,url;
 const {get}=mount(next=>{
  if(next.startsWith("/api/stock/analyses/imperium/"))return Promise.resolve({ok:true,history:[]});
  calls++;url=next;
  return new Promise(resolve=>{finish=resolve;});
 });
 get("stockDailyAnalysisOpen").click();
 assert.equal(calls,1);
 assert.equal(url,"/api/stock/analyses/daily?city=mossoro&start=2026-11-01&end=2026-11-02");
 assert.equal(get("stockDailyHistoryRefresh").disabled,true);
 assert.equal(get("stockDailyHistoryRefresh").textContent,"Buscando histórico...");
 assert.equal(get("stockDailyAnalysisLoading").hidden,false);
 finish({ok:true,selected:null,history:[]});
 await tick();
 assert.equal(get("stockDailyHistoryRefresh").disabled,false);
 assert.equal(get("stockDailyAnalysisLoading").hidden,true);
 assert.match(get("stockDailyAnalysisMessage").textContent,/nenhum arquivo final salvo/);
 get("stockDailyHistoryRefresh").click();
 assert.equal(calls,2);
 finish({ok:true,selected:null,history:[]});
 await tick();
});

test("when clicked, the main button sends a live DataSnap sync with no Excel payload",async()=>{
 let resolveSync,requests=[];
 const {get}=mount((url,options={})=>{
  requests.push({url,options});
  if(url==="/api/stock/analyses/imperium/live"){
   return new Promise(resolve=>{resolveSync=resolve;});
  }
  if(url.startsWith("/api/stock/analyses/imperium/live?")){
   return Promise.resolve({ok:true,history:[{
    id:"550e8400-e29b-41d4-a716-446655440000",city:"mossoro",start:"2026-11-01",
    end:"2026-11-02",created_at:"2026-11-05T12:00:00Z",
    counts:{consolidado:16,por_os:52,seriais_tratados:12,equipamentos:10,chips:2}
   }]});
  }
  if(url.includes("/data?")){
   return Promise.resolve({ok:true,total:12,page_count:1,rows:[{
    serial:"00123",classificacao:"equipamento",cidade:"MOSSORO"
   }]});
  }
  if(url.startsWith("/api/stock/analyses/imperium/runs?"))return Promise.resolve({ok:true,history:[]});
  if(url.startsWith("/api/stock/analyses/daily?"))return Promise.resolve({ok:true,history:[],selected:null});
  throw new Error("Unexpected URL "+url);
 });
 get("stockDailyAnalysisOpen").click();
 await tick();
 get("stockDailyAnalysisRefresh").click();
 const call=requests.find(x=>x.url==="/api/stock/analyses/imperium/live");
 assert.ok(call);
 assert.equal(call.options.method,"POST");
 assert.equal(JSON.parse(call.options.body).city,"mossoro");
 assert.deepEqual(Object.keys(JSON.parse(call.options.body)).sort(),["city","end","start"]);
 assert.equal(get("stockDailyAnalysisRefresh").disabled,true);
 assert.match(get("stockDailyLiveStatus").textContent,/nenhum Excel é necessário/);
 resolveSync({ok:true,reused:false,selected:{
   id:"550e8400-e29b-41d4-a716-446655440000",city:"mossoro"
 }});
 await tick();await tick();await tick();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,false);
 assert.match(get("stockDailyLiveStatus").textContent,/Supabase operacional/);
 assert.match(get("stockDailyLiveCounts").textContent,/52 registros por OS/);
 assert.equal(get("stockDailyLiveTable").children.length,2);
});

test("Supabase error is shown explicitly and does not claim success",async()=>{
 const {get}=mount((url)=>{
  if(url==="/api/stock/analyses/imperium/live"){
   return Promise.reject(new Error("As tabelas da análise Imperium ainda não foram instaladas"));
  }
  return Promise.resolve({ok:true,history:[],selected:null});
 });
 get("stockDailyAnalysisRefresh").click();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,true);
 await tick();
 assert.equal(get("stockDailyAnalysisRefresh").disabled,false);
 assert.match(get("stockDailyLiveStatus").textContent,/não concluída/);
 assert.match(get("stockDailyLiveStatus").textContent,/tabelas/);
});

test("invalid live period is visible and never triggers network",async()=>{
 let calls=0;
 const {get}=mount(()=>{calls++;return Promise.resolve({ok:true,history:[]});});
 get("stockDailyRangeStart").value="2026-11-03";
 get("stockDailyRangeEnd").value="2026-11-01";
 get("stockDailyAnalysisRefresh").click();
 await tick();
 assert.equal(calls,0);
 assert.match(get("stockDailyLiveStatus").textContent,/período válido/);
});

test("live sync blocked for viewer and global selection",async()=>{
 let calls=0;
 const {get,state}=mount(()=>{calls++;return Promise.resolve({ok:true,history:[]});},{role:"viewer"});
 get("stockDailyAnalysisRefresh").click();
 assert.match(get("stockDailyLiveStatus").textContent,/sem permissão/);
 assert.equal(calls,0);
 state.authUser.role="admin";
 state.allCities=true;
 get("stockDailyAnalysisRefresh").click();
 assert.match(get("stockDailyLiveStatus").textContent,/não está homologado/);
 assert.equal(calls,0);
});
