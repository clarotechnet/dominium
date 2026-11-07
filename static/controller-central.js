/* Central de Controladores TOA — somente leitura; sem credenciais no navegador. */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.DominiumControllerCentral=api;
})(typeof window!=="undefined"?window:null,function(){
"use strict";
const MAP={
 "FTZ-DMV_01":["Fortaleza","Adesão"],"FTZ-DMV_ADM":["Fortaleza","Desconexão"],
 "FTZ-DMV_01_VT":["Fortaleza","Visita técnica"],"JCR-DMV":["Recife","Adesão"],
 "JCR-DMV_ADM":["Recife","Desconexão"],
 "MRO-DMV":["Mossoró","Adesão / Visita técnica / Desconexão"],
 "NTL-DMV":["Natal","Adesão"],"NTL-DMV_ADM":["Natal","Desconexão"],
 "NTL-DMV_VT":["Natal","Visita técnica"],
 "PWM-DMV":["Parnamirim","Adesão"],"PWM-DMV_ADM":["Parnamirim","Desconexão"],
 "PWM-DMV_VT":["Parnamirim","Visita técnica"]
};
const MAP_FROZEN=Object.freeze(Object.fromEntries(Object.entries(MAP).map(([k,v])=>[k,Object.freeze(v)])));
function uniq(value){return [...new Set(Array.isArray(value)?value.filter(x=>typeof x==="string"):[])];}
function nonNeg(v){return Number.isSafeInteger(v)&&v>=0?v:0;}
function normalize(input){
 const data=input?.data&&typeof input.data==="object"?input.data:input;
 if(!data||!Array.isArray(data.agents))throw Error("Resposta do coordenador incompatível");
 const agents=data.agents.map(a=>{
  const b=uniq(a.buckets);
  return {id:/^[A-Za-z0-9._:-]{1,100}$/.test(a.id)?a.id:"Sem identificação",
   online:a.online===true,busy:a.busy===true,buckets:b,
   known:b.filter(x=>MAP_FROZEN[x]),unknown:b.filter(x=>!MAP_FROZEN[x]),
   queries:nonNeg(a.queries),recent:nonNeg(a.requests_recent),
   seen:Number.isFinite(a.last_seen)?a.last_seen:null};
 });
 const coverage=Object.fromEntries(Object.keys(MAP_FROZEN).map(name=>[name,{
  online:agents.filter(a=>a.online&&a.known.includes(name)).length,
  busy:agents.filter(a=>a.online&&a.busy&&a.known.includes(name)).length,
  waiting:nonNeg(data.queue_by_bucket?.[name]?.queued),
  processing:nonNeg(data.queue_by_bucket?.[name]?.in_progress)
 }]));
 return {agents,coverage,online:agents.filter(a=>a.online).length,
  busy:agents.filter(a=>a.online&&a.busy).length,
  pending:nonNeg(data.enrollments_pending),leases:nonNeg(data.leases_today),
  limit:data.max_leases_per_day==null?null:nonNeg(data.max_leases_per_day),
  blocked:data.dispatch_blocked===true};
}
function distribution(bucket,count,agents){
 if(!MAP_FROZEN[bucket])throw Error("Bucket não cadastrado");
 const n=Math.max(0,Math.min(5000,nonNeg(count)));
 const eligible=(Array.isArray(agents)?agents:[]).filter(a=>
  a.online===true&&!a.busy&&uniq(a.buckets).includes(bucket));
 if(!eligible.length)return {eligible:0,assignments:[],unallocated:n};
 const arr=eligible.map(a=>({id:a.id,proposed:0}));
 for(let i=0;i<n;i++)arr[i%arr.length].proposed++;
 return {eligible:eligible.length,assignments:arr,unallocated:0};
}
function init(){
 const box=document.getElementById("toaCentral");
 if(!box)return;
 const el=id=>document.getElementById(id);
 const status=el("toaCentralStatus"),summary=el("toaCentralSummary"),
  agentList=el("toaCentralAgents"),buckets=el("toaCentralBuckets"),
  pendingList=el("toaCentralEnrollmentList"),
  filter=el("toaCentralFilter"),bucketPick=el("toaCentralSimBucket"),
  quantity=el("toaCentralSimQty"),result=el("toaCentralSimResult");
 const make=(tag,txt,cls)=>{
  const x=document.createElement(tag);
  if(txt!=null)x.textContent=String(txt).slice(0,230);
  if(cls)x.className=cls;
  return x;
 };
 let current=null,demonstration=false;
 function render(){
  if(!current)return;
  const data=current;
  summary.replaceChildren();
  for(const [label,value] of [["Online",data.online],["Ocupados",data.busy],
    ["Aguardando aprovação",data.pending],["Concessões hoje",data.leases]]){
   const card=make("div",null,"tc-metric");
   card.append(make("small",label),make("strong",value));
   summary.append(card);
  }
  agentList.replaceChildren();
  const selected=filter.value;
  const visible=data.agents.filter(a=>selected==="all"||a.buckets.includes(selected));
  if(!visible.length)agentList.append(make("p","Nenhuma sessão disponível para este filtro.","tc-empty"));
  for(const a of visible){
   const card=make("article",null,"tc-agent"),
    head=make("div",null,"tc-agent-head"),
    chips=make("div",null,"tc-chips");
   head.append(make("strong",a.id),make("span",a.online?(a.busy?"Em consulta":"Online"):"Desconectado",
    "tc-state "+(a.online?"online":"offline")));
   for(const b of a.buckets)chips.append(make("span",b,"tc-chip"+(!MAP_FROZEN[b]?" unknown":"")));
   card.append(head,make("p",a.known.length+" buckets conhecidos · "+a.buckets.length+" encontrados"),
    chips,make("p","Tentativas "+a.queries+" · Contador 15 min "+a.recent+
       " · Último sinal "+(a.seen==null?"indisponível":new Date(a.seen*1000).toLocaleString("pt-BR"))));
   agentList.append(card);
  }
  buckets.replaceChildren();
  for(const [name,meta] of Object.entries(MAP_FROZEN)){
   const c=data.coverage[name],row=make("div",null,"tc-bucket"),detail=make("div");
   detail.append(make("strong",name),make("p",meta[0]+" · "+meta[1]));
   row.append(detail,make("span",c.online+" sessões · "+c.waiting+" aguardando"));
   buckets.append(row);
  }
  const tip=demonstration?"DEMONSTRAÇÃO FICTÍCIA · ":"";
  status.textContent=tip+(data.blocked?"BLOQUEIO GLOBAL 429":
   data.limit===0?"DESPACHO BLOQUEADO":"Orçamento não confirmado")+
   " · Concessões não equivalem a HTTP Oracle.";
  showSimulation();
 }
 function showSimulation(){
  result.replaceChildren();
  if(!current)return;
  const plan=distribution(bucketPick.value,Number(quantity.value),current.agents);
  result.append(make("p",plan.eligible+" controladores disponíveis neste bucket."),
   make("p",plan.assignments.length?
    plan.assignments.map(a=>a.id+": "+a.proposed).join(" · "):
    plan.unallocated+" contratos aguardam sessão elegível."),
   make("p","Simulação apenas. A execução depende das janelas e do orçamento global."));
 }
 function showPending(items, demo=false){
  pendingList.replaceChildren();
  if(demo){
   pendingList.append(make("p","Demonstração: dois pedidos fictícios. Nenhum dispositivo pode ser autorizado aqui.","tc-empty"));
   return;
  }
  const pending=(Array.isArray(items)?items:[]).filter(item=>
    item && /^ctl-[a-f0-9]{24}$/.test(item.id));
  if(!pending.length){
   pendingList.append(make("p","Nenhum controlador aguardando autorização.","tc-empty"));
   return;
  }
  for(const entry of pending){
   const row=make("div",null,"tc-enrollment"),
    label=make("div",null,"tc-enrollment-detail"),
    controls=make("div",null,"tc-enrollment-actions");
   label.append(make("strong","Código de verificação: "+entry.id.slice(-8)),
    make("p","Dispositivo "+entry.id));
   for(const [action,title] of [["approve","Aprovar"],["deny","Recusar"]]){
    const button=make("button",title,"button "+(action==="approve"?"primary":"secondary")+" compact");
    button.type="button";
    button.addEventListener("click",async()=>{
     if(demonstration)return;
     if(!window.confirm((action==="approve"?"Autorizar":"Recusar")+
       " este dispositivo? Confira o código "+entry.id.slice(-8)+" na extensão do controlador."))return;
     button.disabled=true;
     try{
      // Fetch CSRF only from the authenticated same-origin DOMINIUM session.
      const sessionResponse=await fetch("/api/auth/session",{
       credentials:"same-origin",cache:"no-store",
       headers:{"Accept":"application/json"},signal:AbortSignal.timeout(8000)
      });
      if(!sessionResponse.ok)throw Error("Sessão administrativa indisponível");
      const session=await sessionResponse.json();
      if(!session.authenticated || session.user?.role!=="admin" ||
        typeof session.csrf_token!=="string" || !session.csrf_token)
        throw Error("Aprovação exige administrador autenticado");
      const response=await fetch("/api/toa-pool/enrollments/"+entry.id+"/"+action,{
       method:"POST",credentials:"same-origin",cache:"no-store",
       headers:{"Content-Type":"application/json","X-CSRF-Token":session.csrf_token},
       body:"{}",signal:AbortSignal.timeout(8000)
      });
      if(!response.ok)throw Error("Servidor não confirmou a revisão do dispositivo");
      await refresh();
     }catch(err){
      status.textContent="Aprovação não concluída: "+String(err.message||"erro").slice(0,120);
      button.disabled=false;
     }
    });
    controls.append(button);
   }
   row.append(label,controls);pendingList.append(row);
  }
 }
 async function loadPending(){
  const response=await fetch("/api/toa-pool/enrollments",{
   credentials:"same-origin",cache:"no-store",
   headers:{"Accept":"application/json"},signal:AbortSignal.timeout(8000)
  });
  if(!response.ok)throw Error("Cadastro indisponível");
  const data=await response.json();
  if(data.ok!==true || !Array.isArray(data.pending))throw Error("Resposta incompatível");
  showPending(data.pending);
 }
 async function refresh(){
  status.textContent="Consultando monitor autenticado...";
  try{
   const resp=await fetch("/api/toa-pool/monitor",{
     credentials:"same-origin",cache:"no-store",headers:{"Accept":"application/json"},
     signal:AbortSignal.timeout(8000)
   });
   if(!resp.ok)throw Error(resp.status===404?
     "Integração segura com o coordenador ainda não publicada.":"Monitor indisponível (HTTP "+resp.status+")");
   current=normalize(await resp.json());demonstration=false;render();
    try{await loadPending();}
    catch{pendingList.replaceChildren(make("p","Não foi possível carregar pedidos de autorização.","tc-empty"));}
  }catch(err){
   current=null;summary.replaceChildren();buckets.replaceChildren();
    pendingList.replaceChildren(make("p","Cadastro não conectado.","tc-empty"));
   agentList.replaceChildren(make("p","Nenhum controlador real carregado.","tc-empty"));
   status.textContent=String(err.message||"Monitor indisponível").slice(0,220);
  }
 }
 el("toaCentralRefresh").addEventListener("click",refresh);
 el("toaCentralDemo").addEventListener("click",()=>{
  const now=Date.now()/1000;
  current=normalize({max_leases_per_day:0,leases_today:0,enrollments_pending:2,
   agents:[
    {id:"CONTROLADOR-EXEMPLO-01",online:true,busy:false,buckets:["NTL-DMV_ADM","NTL-DMV"],queries:5,requests_recent:7,last_seen:now},
    {id:"CONTROLADOR-EXEMPLO-02",online:true,busy:false,buckets:["MRO-DMV"],queries:3,requests_recent:4,last_seen:now-25},
    {id:"CONTROLADOR-EXEMPLO-03",online:false,busy:false,buckets:["FTZ-DMV_01_VT"],queries:2,requests_recent:1,last_seen:now-4000}
   ],queue_by_bucket:{"NTL-DMV_ADM":{queued:12},"MRO-DMV":{queued:9}}});
  demonstration=true;render();showPending([],true);
 });
 filter.addEventListener("change",render);
 bucketPick.addEventListener("change",showSimulation);
 quantity.addEventListener("input",showSimulation);
 status.textContent="Aguardando conexão autenticada com o coordenador.";
}
if(typeof document!=="undefined"){
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
 else init();
}
return Object.freeze({MAP:MAP_FROZEN,normalize,distribution});
});
