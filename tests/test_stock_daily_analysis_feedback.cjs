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
 const state={profile:options.profile||"mossoro",allCities:false,
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
 assert.match(html,/stock-daily-analysis-ui\.js\?v=20261106-atlas-video-3/);
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


test("the Natal screen shows collected serials first and only treats after second click",async()=>{
 const id="550e8400-e29b-41d4-a716-446655440000";
 let stepResolve;
 const calls=[];
 const initial={
  ok:true,city:"natal",run:id,
  counts:{total:2,processados:0,restantes:2,erro_consulta:0,formato_nao_suportado:0},
  complete:false,download_enabled:false,rows:[
   {serial:"000000000001",equipamento:"GPON",situacao:"aguardando"},
   {serial:"000000000002",equipamento:"GPON",situacao:"aguardando"},
  ],
 };
 const {get}=mount((url,opt={})=>{
  calls.push({url,opt});
  if(url==="/api/stock/analyses/imperium/live?city=natal&start=2026-11-01&end=2026-11-02"){
   return Promise.resolve({ok:true,history:[{
    id,city:"natal",start:"2026-11-01",end:"2026-11-02",
    created_at:"2026-11-06T10:00:00Z",
    counts:{consolidado:10,por_os:20,seriais_tratados:2,equipamentos:2,chips:0}
   }]});
  }
  if(url.includes("/api/stock/analyses/imperium/live/"+id+"/data?")){
   return Promise.resolve({ok:true,total:2,page_count:1,rows:[
    {serial:"000000000001",equipamento:"GPON"},
    {serial:"000000000002",equipamento:"GPON"},
   ]});
  }
  if(url.startsWith("/api/stock/analyses/imperium/serial-treatment/status?")){
   return Promise.resolve(initial);
  }
  if(url==="/api/stock/analyses/imperium/serial-treatment/next"){
   return new Promise(resolve=>{stepResolve=resolve;});
  }
  if(url.startsWith("/api/stock/analyses/imperium/runs?"))return Promise.resolve({ok:true,history:[]});
  if(url.startsWith("/api/stock/analyses/daily?"))return Promise.resolve({ok:true,history:[],selected:null});
  throw new Error("Unexpected URL "+url);
 },{profile:"natal"});
 get("stockDailyAnalysisOpen").click();
 await tick();await tick();await tick();await tick();
 assert.equal(get("stockDailyTreatmentRun").disabled,false,
   "treatment button is enabled only after choosing an existing stored source");
 assert.equal(get("stockDailyTreatmentExport").disabled,true);
 assert.match(get("stockDailyLiveCounts").textContent,/seriais coletados e ainda não tratados/);
 assert.equal(calls.filter(x=>x.url.endsWith("/serial-treatment/next")).length,0,
   "opening a collected source must never start historical serial lookups");
 get("stockDailyTreatmentRun").click();
 const request=calls.find(x=>x.url==="/api/stock/analyses/imperium/serial-treatment/next");
 assert.ok(request);
 assert.equal(request.opt.method,"POST");
 assert.equal(JSON.parse(request.opt.body).run,id);
 assert.equal(JSON.parse(request.opt.body).city,"natal");
 assert.equal(get("stockDailyTreatmentPause").disabled,false);
 get("stockDailyTreatmentPause").click();
 stepResolve({...initial,updated:{serial:"000000000001",situacao:"historico_verificado"},
  counts:{total:2,processados:1,restantes:1,erro_consulta:0,
          historico_verificado:1,formato_nao_suportado:0}});
 await tick();await tick();await tick();
 assert.equal(calls.filter(x=>x.url==="/api/stock/analyses/imperium/serial-treatment/next").length,1,
  "pause must stop before querying the next serial");
 assert.equal(get("stockDailyTreatmentRun").disabled,false);
 assert.equal(get("stockDailyTreatmentProgress").value,1);
 assert.match(get("stockDailyTreatmentStatus").textContent,/pausada/);
});


test("the Atlas stage is explicit, requires prior serial treatment, and shows progress",async()=>{
 const id="550e8400-e29b-41d4-a716-446655440000";
 let resolveQueued;
 const posted=[];
 const serial="000000000001";
 const history={ok:true,history:[{
   id,city:"natal",start:"2026-11-01",end:"2026-11-02",
   created_at:"2026-11-06T11:00:00Z",
   counts:{consolidado:2,por_os:5,seriais_tratados:1,equipamentos:1,chips:0},
 }]};
 const treatment={ok:true,counts:{total:1,processados:1,restantes:0,
     historico_verificado:1,erro_consulta:0},
     complete:true,download_enabled:true,rows:[{serial,situacao:"historico_verificado"}]};
 const atlas={ok:true,city:"natal",run:id,
   counts:{total:1,tratados_imperium:1,atlas_aguardando:1,atlas_verificados:0},
   atlas_finalizados:0,atlas_pendentes:1,rows:[{
    serial,modelo_imperium:"GPON",situacao_atlas:"aguardando",
    estado_atlas:"",localizacao_atlas:""
   }]
 };
 const {get}=mount((url,opts={})=>{
   if(url.startsWith("/api/stock/analyses/imperium/live?"))return Promise.resolve(history);
   if(url.includes("/data?"))return Promise.resolve({ok:true,rows:[{serial}],total:1,page_count:1});
   if(url.startsWith("/api/stock/analyses/imperium/serial-treatment/status?"))return Promise.resolve(treatment);
   if(url.startsWith("/api/stock/analyses/imperium/atlas-video/status?"))return Promise.resolve(atlas);
   if(url==="/api/stock/analyses/imperium/atlas-video/next"){
    posted.push(JSON.parse(opts.body));
    return new Promise(resolve=>{resolveQueued=resolve;});
   }
   if(url.startsWith("/api/stock/analyses/imperium/runs?"))return Promise.resolve({ok:true,history:[]});
   if(url.startsWith("/api/stock/analyses/daily?"))return Promise.resolve({ok:true,history:[],selected:null});
   throw new Error("Unexpected "+url);
 },{profile:"natal"});
 get("stockDailyAnalysisOpen").click();
 await tick();await tick();await tick();await tick();
 assert.equal(posted.length,0,"opening report must not enqueue Atlas automatically");
 assert.equal(get("stockDailyAtlasVideoRun").disabled,false);
 get("stockDailyAtlasVideoRun").click();
 assert.equal(posted.length,1);
 assert.equal(posted[0].run,id);
 assert.equal(posted[0].city,"natal");
 assert.equal(get("stockDailyAtlasVideoPause").disabled,false);
 resolveQueued({...atlas,updated:{situacao:"verificado"},atlas_finalizados:1,
   atlas_pendentes:0,counts:{...atlas.counts,atlas_verificados:1,atlas_aguardando:0},
   rows:[{serial,modelo_imperium:"GPON",situacao_atlas:"verificado",
     estado_atlas:"INICIALIZADO",localizacao_atlas:"ASSINANTE"}]
 });
 await tick();await tick();await tick();
 assert.equal(get("stockDailyAtlasVideoRun").disabled,true);
 assert.equal(get("stockDailyAtlasVideoProgress").value,1);
 assert.match(get("stockDailyAtlasVideoCounts").textContent,/1 de 1 seriais avaliados/);
 assert.equal(posted.length,1);
 assert.match(get("stockDailyAtlasVideoMessage").textContent,/Atlas/);
});

test("Atlas stage remains blocked for unvalidated city",async()=>{
 const {get}=mount(()=>Promise.resolve({ok:true,history:[]}),{profile:"mossoro"});
 assert.equal(get("stockDailyAtlasVideoRun").disabled,true);
 assert.equal(get("stockDailyAtlasVideoAll").disabled,true);
});
