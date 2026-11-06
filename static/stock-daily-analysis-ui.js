/* Daily equipment: independent period/catalog; Atlas QUERY is not its source. */
(() => {
"use strict";
const el=id=>document.getElementById(id);
const panel=el("stockDailyAnalysisPanel");
if(!panel)return;
const tabs=["Atlas","Chips Atlas","IMPERIUM","CHIP IMPERIUM","Assinantes","Nomes."];
let selected=null,activeTab=0,fetching=false,refreshQueued=false;
let allRuns=[];
let sourceSelected=null,sourceRuns=[],sourceBusy=false,sourceTab=0;
let liveRuns=[],liveSelected=null,livePage=1,liveBusy=false;
let treatmentBusy=false,treatmentStop=false,treatmentState=null;
let atlasVideoBusy=false,atlasVideoStop=false,atlasVideoState=null;
const currentCity=()=>state.allCities?"all":state.profile;
const canWrite=()=>!state.allCities&&["admin","controller"].includes(state.authUser?.role);
function status(msg,error=false){
 const node=el("stockDailyAnalysisMessage");node.textContent=msg;
 node.style.color=error?"#ff8898":"";
}
function referenceDate(){
 const d=new Date(Date.now()-86400000);
 return new Intl.DateTimeFormat("en-CA",{timeZone:"America/Fortaleza",year:"numeric",month:"2-digit",day:"2-digit"}).format(d);
}
function setVisible(visible){
 panel.hidden=!visible;
 if(!visible)return;
 el("stockDailyAnalysisDate").value ||= referenceDate();
 el("stockDailyRangeStart").value ||= referenceDate();
 el("stockDailyRangeEnd").value ||= referenceDate();
 el("stockDailyAnalysisImport").hidden=!canWrite()||currentCity()==="all";
 updateSourceAvailability();
 liveButton();
 void loadDaily();
 void loadLiveHistory();
 void loadSourceHistory();
}
function setLoading(on){
 const button=el("stockDailyHistoryRefresh");
 const indicator=el("stockDailyAnalysisLoading");
 button.disabled=on;
 button.classList.toggle("stock-daily-search-loading",on);
 button.setAttribute("aria-busy",String(on));
 button.textContent=on?"Buscando histórico...":"Consultar histórico anterior";
 indicator.hidden=!on;
 el("stockDailyAnalysisTable").setAttribute("aria-busy",String(on));
}
function formatDay(day){
 if(!day)return "";
 const parts=day.split("-");
 return parts.length===3?parts[2]+"/"+parts[1]+"/"+parts[0]:day;
}
async function loadDaily(){
 if(fetching){
   refreshQueued=true;
   status("Uma consulta ainda está em andamento. A nova seleção será pesquisada em seguida.");
   return;
 }
 fetching=true;
 const city=currentCity();
 const day=el("stockDailyAnalysisDate").value;
 const start=el("stockDailyRangeStart").value;
 const end=el("stockDailyRangeEnd").value;
 const place=city==="all"?"todas as cidades":city.toUpperCase();
 const period=start&&end?formatDay(start)+" a "+formatDay(end):"referência "+formatDay(day);
 setLoading(true);
 status("Consultando histórico de "+place+" • "+period+"...");
 try{
   let url="/api/stock/analyses/daily?city="+encodeURIComponent(city);
   if(start||end){
     if(!start||!end)throw new Error("Informe a data inicial e a data final.");
     if(start>end)throw new Error("A data inicial não pode ser posterior à data final.");
     url+="&start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
   }else if(day)url+="&date="+encodeURIComponent(day);
   const data=await request(url,{timeoutMs:30000});
   if(city!==currentCity()){
     refreshQueued=true;
     return;
   }
   if(!data?.ok)throw new Error(data?.error||"Resposta inválida da consulta.");
   const history=Array.isArray(data.history)?data.history:[];
   // Não mostrar a última análise de outra data como se pertencesse ao período solicitado.
   selected=data.selected||null;
   allRuns=[];
   if(city==="all"){
     const latestByCity=new Map();
     for(const item of history){
       if(!latestByCity.has(item.city))latestByCity.set(item.city,item);
     }
     allRuns=[...latestByCity.values()];
   }
   const historic=el("stockDailyAnalysisHistory");
   const options=document.createDocumentFragment();
   for(const item of history){
     const opt=document.createElement("option");
     opt.value=item.id;
     opt.textContent=item.city.toUpperCase()+" • "+item.date+" • "+item.origin+" • "+item.filename;
     options.appendChild(opt);
   }
   historic.replaceChildren(options);
   const finished=new Date().toLocaleTimeString("pt-BR");
   if(selected){
     historic.value=selected.id;
     status("Consulta concluída às "+finished+" • "+history.length+
       " arquivo(s) encontrado(s) em "+place+" ("+period+"). Exibindo "+
       formatDay(selected.date)+" • "+selected.filename+".");
     await displaySheet(0);
   }else{
     el("stockDailyAnalysisTable").replaceChildren();
     el("stockDailyAnalysisTabs").replaceChildren();
     el("stockDailyAnalysisSheetInfo").textContent="";
     el("stockDailyAnalysisDownload").disabled=true;
     status("Consulta concluída às "+finished+" • nenhum arquivo final salvo em "+
       place+" ("+period+"). Este botão busca somente o histórico de seis abas. "+
       "Para consultar dados novos, use a seção Fonte Imperium abaixo.");
   }
 }catch(error){
   status("Falha na consulta de "+place+" ("+period+"): "+(error.message||error),true);
 }finally{
   fetching=false;
   setLoading(false);
   if(refreshQueued){
     refreshQueued=false;
     void loadDaily();
   }
 }
}
async function displaySheet(index){
 if(!selected)return;
 activeTab=index;
 const item=selected,city=currentCity();
 try{
   let data=await request("/api/stock/analyses/daily/"+item.id+"/sheets/"+index,{timeoutMs:30000});
   if(city==="all" && allRuns.length){
     const groups=await Promise.all(allRuns.map(async run=>({
       city:run.city,
       data:run.id===item.id?data:await request("/api/stock/analyses/daily/"+run.id+"/sheets/"+index,{timeoutMs:30000})
     })));
     data={
       header:["Praça",...(groups[0]?.data.header||[])],
       rows:groups.flatMap(group=>(group.data.rows||[]).map(row=>[group.city.toUpperCase(),...row])),
       total:groups.reduce((sum,group)=>sum+(group.data.total||0),0),
       preview_limited:groups.some(group=>group.data.preview_limited)
     };
   }
   if(city!==currentCity()||selected?.id!==item.id)return;
   const nav=el("stockDailyAnalysisTabs");
   nav.replaceChildren();
   tabs.forEach((name,i)=>{
     const b=document.createElement("button");
     b.type="button";b.textContent=name;b.className="button secondary";
     b.setAttribute("aria-pressed",String(index===i));
     b.classList.toggle("active",index===i);
     b.addEventListener("click",()=>void displaySheet(i));
     nav.appendChild(b);
   });
   const table=el("stockDailyAnalysisTable");
   table.replaceChildren();
   const thead=document.createElement("thead"),head=document.createElement("tr");
   (data.header||[]).forEach(h=>{
     const th=document.createElement("th");th.textContent=String(h||"");head.appendChild(th);
   });thead.appendChild(head);table.appendChild(thead);
   const body=document.createElement("tbody");
   for(const row of data.rows||[]){
     const tr=document.createElement("tr");
     row.forEach(value=>{const td=document.createElement("td");td.textContent=String(value??"");tr.appendChild(td)});
     body.appendChild(tr);
   }
   table.appendChild(body);
   el("stockDailyAnalysisSheetInfo").textContent=
     tabs[index]+" • "+data.total+" registros"+(data.preview_limited?" • mostrando os primeiros 200":"");
   el("stockDailyAnalysisDownload").disabled=city==="all";
   if(city==="all")el("stockDailyAnalysisDownload").title="Para baixar o Excel, selecione uma cidade no cabeçalho";
 }catch(error){status("Falha ao abrir a aba: "+(error.message||error),true)}
}
async function download(){
 if(!selected)return;
 try{
   const response=await requestBlob("/api/stock/analyses/daily/"+selected.id+"/export",{timeoutMs:120000});
   const raw=new Uint8Array(await response.blob.slice(0,4).arrayBuffer());
   if(response.blob.size<300||raw[0]!==0x50||raw[1]!==0x4B||raw[2]!==0x03||raw[3]!==0x04){
     throw new Error("Resposta nao e um XLSX valido");
   }
   saveBlob(response.blob,"ANALISE-EQUIPAMENTOS-"+selected.city+"-"+selected.date+".xlsx");
 }catch(error){status("Erro no download: "+(error.message||error),true)}
}
async function importWorkbook(){
 const input=el("stockDailyAnalysisFile");
 const file=input.files?.[0];
 const city=currentCity(),day=el("stockDailyAnalysisDate").value;
 if(!canWrite()||!file){status("Selecione o Excel final de referência",true);return;}
 if(!day){status("Informe a data de referência da análise",true);return;}
 if(file.size>3500000){status("Arquivo acima do limite de 3,5 MB",true);return;}
 const button=el("stockDailyAnalysisImport");
 button.disabled=true;status("Validando e registrando o Excel final no histórico...");
 try{
   const bytes=new Uint8Array(await file.arrayBuffer());
   const chunks=[];
   for(let i=0;i<bytes.length;i+=8192)chunks.push(String.fromCharCode(...bytes.subarray(i,i+8192)));
   const content_base64=btoa(chunks.join(""));
   const payload=await request("/api/stock/analyses/daily/import",{
     method:"POST",headers:{"content-type":"application/json"},
     body:JSON.stringify({city,date:day,filename:file.name,content_base64}),
     timeoutMs:120000
   });
   if(payload.ok){input.value="";await loadDaily();}
 }catch(error){status("Falha ao importar: "+(error.message||error),true)}
 finally{button.disabled=false;}
}
function sourceMessage(text,error=false){
 const node=el("stockDailyImperiumMessage");
 node.textContent=text;
 node.style.color=error?"#ff8898":"";
}
function updateSourceAvailability(){
 const city=currentCity();
 const button=el("stockDailyImperiumExtract");
 const permitted=canWrite()&&["natal","mossoro","recife"].includes(city);
 button.disabled=sourceBusy||!permitted;
 button.setAttribute("aria-busy",String(sourceBusy));
 button.textContent=sourceBusy?"Extraindo no Imperium...":"Extrair fonte Imperium";
 button.title=["natal","mossoro","recife"].includes(city)
  ?(canWrite()?"Extração real: Consolidado e Por OS; não gera as seis abas finais":"Perfil sem permissão para gerar extração")
  :"Extração ainda não homologada nesta cidade. Não usar parceiros de outra praça.";
}
function clearSourceView(){
 sourceSelected=null;
 el("stockDailyImperiumTabs").replaceChildren();
 el("stockDailyImperiumTable").replaceChildren();
 el("stockDailyImperiumSheetInfo").textContent="";
 el("stockDailyImperiumDownload").disabled=true;
}
async function loadSourceHistory(){
 const city=currentCity();
 const start=el("stockDailyRangeStart").value,end=el("stockDailyRangeEnd").value;
 clearSourceView();
 sourceRuns=[];
 el("stockDailyImperiumHistory").replaceChildren();
 updateSourceAvailability();
 if(city==="all"){
  sourceMessage("Selecione uma cidade para visualizar as extrações reais; Todos não mistura perfis DataSnap.");
  return;
 }
 if(!start||!end||start>end){
  sourceMessage("Informe um período válido para consultar a fonte Imperium.",true);
  return;
 }
 try{
  const url="/api/stock/analyses/imperium/runs?city="+encodeURIComponent(city)+
   "&start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
  const result=await request(url,{timeoutMs:30000});
  if(city!==currentCity()||start!==el("stockDailyRangeStart").value||end!==el("stockDailyRangeEnd").value)return;
  if(!result?.ok)throw new Error(result.error||"Resposta inválida");
  sourceRuns=Array.isArray(result.history)?result.history:[];
  const opts=document.createDocumentFragment();
  for(const run of sourceRuns){
   const option=document.createElement("option");
   option.value=run.id;
   option.textContent=run.city.toUpperCase()+" • "+run.start+" a "+run.end+
    " • "+new Date(run.created_at).toLocaleString("pt-BR");
   opts.appendChild(option);
  }
  el("stockDailyImperiumHistory").replaceChildren(opts);
  if(sourceRuns.length){
   sourceSelected=sourceRuns[0];
   el("stockDailyImperiumHistory").value=sourceSelected.id;
   await displaySourceSheet(0);
   sourceMessage("Fonte Imperium: "+sourceRuns.length+" extração(ões) registrada(s). "+
    "Este arquivo contém duas abas reais; a análise completa de seis abas é separada.");
  }else if(!["natal","mossoro","recife"].includes(city)){
   sourceMessage("Nenhuma extração salva em "+city.toUpperCase()+". Consulta direta ainda não homologada nesta cidade.",true);
  }else{
   sourceMessage("Nenhuma extração do Imperium salva nesse período. "+
    (canWrite()?"Clique em Extrair fonte Imperium para consultar o DataSnap.":"Solicite a extração a um administrador."));
  }
 }catch(error){
  sourceMessage("Não foi possível consultar o histórico da fonte Imperium: "+(error.message||error),true);
 }
}
async function displaySourceSheet(index){
 if(!sourceSelected)return;
 sourceTab=index;
 const run=sourceSelected,city=currentCity();
 try{
  const payload=await request("/api/stock/analyses/imperium/runs/"+run.id+
   "/sheets/"+index,{timeoutMs:30000});
  if(!payload?.ok)throw new Error(payload.error||"Resposta inválida");
  if(city!==currentCity()||sourceSelected?.id!==run.id)return;
  const nav=el("stockDailyImperiumTabs");
  nav.replaceChildren();
  ["Consolidado Imperium","Por OS Imperium"].forEach((name,i)=>{
   const button=document.createElement("button");
   button.type="button";button.textContent=name;button.className="button secondary";
   button.classList.toggle("active",index===i);
   button.setAttribute("aria-pressed",String(index===i));
   button.addEventListener("click",()=>void displaySourceSheet(i));
   nav.appendChild(button);
  });
  const table=el("stockDailyImperiumTable");
  table.replaceChildren();
  const head=document.createElement("thead"),tr=document.createElement("tr");
  for(const name of payload.header||[]){
   const th=document.createElement("th");th.textContent=String(name||"");
   tr.appendChild(th);
  }
  head.appendChild(tr);table.appendChild(head);
  const body=document.createElement("tbody");
  for(const row of payload.rows||[]){
   const tr=document.createElement("tr");
   for(const value of row){
    const td=document.createElement("td");td.textContent=String(value??"");
    tr.appendChild(td);
   }
   body.appendChild(tr);
  }
  table.appendChild(body);
  el("stockDailyImperiumSheetInfo").textContent=
   payload.name+" • "+payload.total+" registros"+
   (payload.preview_limited?" • mostrando os primeiros 200":"");
  el("stockDailyImperiumDownload").disabled=false;
 }catch(error){sourceMessage("Falha ao abrir o dataset do Imperium: "+(error.message||error),true);}
}
async function extractSource(){
 const city=currentCity(),start=el("stockDailyRangeStart").value,end=el("stockDailyRangeEnd").value;
 if(!["natal","mossoro","recife"].includes(city)){
  sourceMessage("Extração DataSnap não homologada para "+city.toUpperCase()+
   ". Nenhum resultado de outra praça será utilizado.",true);return;
 }
 if(!canWrite()){sourceMessage("Somente administrador/controlador pode extrair.",true);return;}
 if(!start||!end||start>end){sourceMessage("Informe data inicial e final válidas.",true);return;}
 if(sourceBusy)return;
 sourceBusy=true;updateSourceAvailability();
 sourceMessage("Conectando ao DataSnap e consultando os dois datasets reais de "+city.toUpperCase()+" ("+
  formatDay(start)+" a "+formatDay(end)+")...");
 try{
  const result=await request("/api/stock/analyses/imperium/extract",{
   method:"POST",headers:{"content-type":"application/json"},
   body:JSON.stringify({city,start,end}),timeoutMs:120000
  });
  if(!result?.ok)throw new Error(result?.error||"Extração indisponível");
  if(city!==currentCity())return;
  await loadSourceHistory();
  sourceMessage("Extração concluída: "+result.selected?.counts?.["Consolidado Imperium"]+
   " consolidados e "+result.selected?.counts?.["Por OS Imperium"]+
   " por OS. Fonte salva para download; não é o XLSX final de seis abas.");
 }catch(error){
  sourceMessage("Extração do Imperium não concluída: "+(error.message||error),true);
 }finally{sourceBusy=false;updateSourceAvailability();}
}
async function downloadSource(){
 if(!sourceSelected)return;
 try{
  const response=await requestBlob("/api/stock/analyses/imperium/runs/"+
   sourceSelected.id+"/export",{timeoutMs:120000});
  const bytes=new Uint8Array(await response.blob.slice(0,4).arrayBuffer());
  if(response.blob.size<300||bytes[0]!==80||bytes[1]!==75||bytes[2]!==3||bytes[3]!==4){
   throw new Error("Arquivo retornado não é um XLSX");
  }
  saveBlob(response.blob,sourceSelected.filename);
 }catch(error){sourceMessage("Falha no download da fonte Imperium: "+(error.message||error),true);}
}
function liveMessage(text,error=false){
 const node=el("stockDailyLiveStatus");
 node.textContent=text;
 node.style.color=error?"#ff8898":"";
}
function liveButton(){
 const button=el("stockDailyAnalysisRefresh"),city=currentCity();
 const enabled=canWrite()&&["natal","mossoro","recife"].includes(city);
 button.disabled=liveBusy||!enabled;
 button.setAttribute("aria-busy",String(liveBusy));
 button.textContent=liveBusy?"Consultando Imperium e salvando no Supabase...":
  "Consultar período (DataSnap → Supabase)";
 button.title=enabled
  ?"Buscar dados reais da praça, tratar seriais e salvar no Supabase sem Excel"
  :"Escolha Natal, Mossoró ou Recife com perfil de administrador/controlador";
}
function clearLivePreview(){
 liveSelected=null;
 liveRuns=[];
 livePage=1;
 el("stockDailyLiveTable").replaceChildren();
 el("stockDailyLiveHistory").replaceChildren();
 el("stockDailyLiveCounts").textContent="";
 el("stockDailyLivePageInfo").textContent="";
 el("stockDailyLivePrevious").disabled=true;
 el("stockDailyLiveNext").disabled=true;
}
function renderLiveTable(items){
 const table=el("stockDailyLiveTable");
 table.replaceChildren();
 const header=items.length?Object.keys(items[0]):[];
 const thead=document.createElement("thead"),tr=document.createElement("tr");
 header.forEach(name=>{
  const th=document.createElement("th");th.textContent=name;tr.appendChild(th);
 });
 thead.appendChild(tr);table.appendChild(thead);
 const tbody=document.createElement("tbody");
 items.forEach(item=>{
  const row=document.createElement("tr");
  header.forEach(field=>{
   const td=document.createElement("td");
   td.textContent=String(item[field]??"");
   row.appendChild(td);
  });
  tbody.appendChild(row);
 });
 table.appendChild(tbody);
}
async function showLivePage(page){
 const run=liveSelected,city=currentCity();
 if(!run)return;
 const category=el("stockDailyLiveCategory").value;
 try{
  const url="/api/stock/analyses/imperium/live/"+run.id+"/data?city="+
   encodeURIComponent(city)+"&category="+encodeURIComponent(category)+"&page="+page;
  const data=await request(url,{timeoutMs:30000});
  if(!data?.ok)throw new Error(data?.error||"Dados indisponíveis");
  if(city!==currentCity()||run.id!==liveSelected?.id||
     category!==el("stockDailyLiveCategory").value)return;
  livePage=page;
  renderLiveTable(data.rows||[]);
  const max=Math.max(1,data.page_count||1);
  el("stockDailyLivePageInfo").textContent="Página "+page+" de "+max+
   " • "+data.total+" registros em "+category;
  el("stockDailyLivePrevious").disabled=page<=1;
  el("stockDailyLiveNext").disabled=page>=max;
  const c=run.counts||{};
  el("stockDailyLiveCounts").textContent=
   "Salvo no Supabase • "+(c.consolidado||0)+" consolidados • "+
   (c.por_os||0)+" registros por OS • "+(c.seriais_tratados||0)+
   " seriais coletados e ainda não tratados ("+(c.equipamentos||0)+" equipamentos e "+
   (c.chips||0)+" chips). Resultado de origem, ainda não o relatório final de seis abas.";
 }catch(err){liveMessage("Falha ao visualizar registros no Supabase: "+(err.message||err),true);}
}
async function loadLiveHistory(selectId){
 const city=currentCity(),start=el("stockDailyRangeStart").value,
       end=el("stockDailyRangeEnd").value;
 clearLivePreview();
 clearTreatmentView();
 liveButton();
 if(city==="all"){
  liveMessage("Selecione uma praça para consultar o Imperium. Todos não mistura as bases.");
  return;
 }
 if(!start||!end||start>end){
  liveMessage("Informe data inicial e final válidas.",true);return;
 }
 try{
  const url="/api/stock/analyses/imperium/live?city="+encodeURIComponent(city)+
   "&start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
  const payload=await request(url,{timeoutMs:30000});
  if(city!==currentCity()||start!==el("stockDailyRangeStart").value||
      end!==el("stockDailyRangeEnd").value)return;
  if(!payload?.ok)throw new Error(payload?.error||"Histórico Supabase inválido");
  liveRuns=Array.isArray(payload.history)?payload.history:[];
  const fragment=document.createDocumentFragment();
  for(const row of liveRuns){
   const option=document.createElement("option");
   option.value=row.id;
   option.textContent=row.city.toUpperCase()+" • "+row.start+" a "+row.end+
    " • atualizado em "+new Date(row.checked_at||row.created_at).toLocaleString("pt-BR");
   fragment.appendChild(option);
  }
  el("stockDailyLiveHistory").replaceChildren(fragment);
  liveSelected=liveRuns.find(row=>row.id===selectId)||liveRuns[0]||null;
  if(liveSelected){
   el("stockDailyLiveHistory").value=liveSelected.id;
   await showLivePage(1);
   liveMessage("Consulta concluída e persistida no Supabase operacional. "+
    "Os seriais foram coletados; a tratativa individual é uma segunda etapa.");
   await loadTreatmentStatus();
   await loadAtlasVideoStatus();
  }else{
   clearTreatmentView();
   liveMessage("Nenhuma consulta salva para "+city.toUpperCase()+
    " neste período. Clique em Consultar período para buscar diretamente pelo DataSnap.");
  }
 }catch(err){liveMessage("Histórico Supabase: "+(err.message||err),true);}
}
async function consultLivePeriod(){
 const city=currentCity(),start=el("stockDailyRangeStart").value,
       end=el("stockDailyRangeEnd").value;
 if(liveBusy)return;
 if(!["natal","mossoro","recife"].includes(city)){
  liveMessage("O acesso DataSnap ainda não está homologado nesta praça.",true);return;
 }
 if(!canWrite()){liveMessage("Perfil sem permissão para gerar consultas.",true);return;}
 if(!start||!end||start>end){liveMessage("Informe um período válido.",true);return;}
 liveBusy=true;liveButton();
 liveMessage("Consultando o Imperium de "+city.toUpperCase()+" ("+
  formatDay(start)+" a "+formatDay(end)+
  "). Tratamento em memória e gravação no Supabase; nenhum Excel é necessário...");
 try{
  const payload=await request("/api/stock/analyses/imperium/live",{
   method:"POST",headers:{"content-type":"application/json"},
   body:JSON.stringify({city,start,end}),timeoutMs:120000,
  });
  if(!payload?.ok)throw new Error(payload?.error||"Consulta não concluída");
  if(city!==currentCity())return;
  await loadLiveHistory(payload.selected?.id);
  if(liveSelected){
   liveMessage((payload.reused?"Pesquisa confirmada sem mudanças na fonte":"Seriais coletados e gravados")+
    " no Supabase operacional, para "+city.toUpperCase()+". "+
    "Confira os seriais da etapa 1 e use o segundo botão para iniciar a tratativa.");
  }
 }catch(err){
  liveMessage("Consulta não concluída; nenhum resultado parcial será exibido como final: "+
   (err.message||err),true);
 }finally{liveBusy=false;liveButton();}
}
function clearTreatmentView(){
 treatmentStop=true;
 treatmentState=null;
 clearAtlasVideoView();
 const bar=el("stockDailyTreatmentProgress");
 bar.value=0;bar.max=1;
 el("stockDailyTreatmentTable").replaceChildren();
 el("stockDailyTreatmentCounts").textContent="";
 el("stockDailyTreatmentStatus").textContent="Selecione uma coleta da etapa 1 para iniciar a tratativa.";
 updateTreatmentButtons();
}
function updateTreatmentButtons(){
 const city=currentCity(),run=liveSelected;
 const eligible=canWrite()&&city==="natal"&&!!run;
 const busy=treatmentBusy;
 const counts=treatmentState?.counts||{};
 const complete=treatmentState?.complete===true;
 const runButton=el("stockDailyTreatmentRun");
 runButton.disabled=busy||!eligible||(complete&&!(counts.erro_consulta>0));
 runButton.setAttribute("aria-busy",String(busy));
 runButton.textContent=busy?"Tratando seriais no Imperium...":
  complete&&counts.erro_consulta>0?"Repetir consultas com falha":
  complete?"Tratativa concluída":"Tratar seriais coletados";
 runButton.title=city!=="natal"
  ?"Tratativa individual ainda homologada somente para Natal"
  :!run?"Pesquise um período e selecione a coleta salva antes de tratar":"Consultar cada serial e salvar no Supabase";
 el("stockDailyTreatmentPause").disabled=!busy;
 el("stockDailyTreatmentExport").disabled=!run||!treatmentState?.download_enabled;
}
function showTreatmentResult(result){
 treatmentState=result;
 const counts=result.counts||{};
 const total=Math.max(1,counts.total||0);
 const bar=el("stockDailyTreatmentProgress");
 bar.max=total;
 bar.value=Math.min(total,counts.processados||0);
 el("stockDailyTreatmentCounts").textContent=
  (counts.processados||0)+" de "+(counts.total||0)+" seriais consultados/avaliados • "+
  (counts.historico_verificado||0)+" com histórico • "+
  (counts.sem_movimentos||0)+" sem movimentos confirmados • "+
  (counts.erro_consulta||0)+" falhas • "+
  (counts.formato_nao_suportado||0)+" formatos pendentes.";
 const table=el("stockDailyTreatmentTable");
 table.replaceChildren();
 const header=["Serial","Equipamento","Situação","Histórico","Movimentos","Posse atual","Observação"];
 const fields=["serial","equipamento","situacao","historico_confirmado",
  "quantidade_movimentos","posse_atual_comprovada","observacao"];
 const thead=document.createElement("thead"),tr=document.createElement("tr");
 for(const text of header){
  const th=document.createElement("th");th.textContent=text;tr.appendChild(th);
 }
 thead.appendChild(tr);table.appendChild(thead);
 const tbody=document.createElement("tbody");
 for(const record of result.rows||[]){
  const row=document.createElement("tr");
  for(const field of fields){
   const td=document.createElement("td");
   const val=record[field];
   td.textContent=typeof val==="boolean"?(val?"Sim":"Não"):
    val===null||val===undefined?"":String(val);
   row.appendChild(td);
  }
  tbody.appendChild(row);
 }
 table.appendChild(tbody);
 el("stockDailyTreatmentStatus").textContent=result.complete
  ?(result.status==="concluido_com_pendencias"
    ?"Tratativa concluída com pendências identificadas. O relatório pode ser baixado com os avisos."
    :"Tratativa concluída e salva no Supabase. O relatório está disponível para download.")
  :"Tratativa "+(counts.processados||0)+"/"+(counts.total||0)+
   " persistida no Supabase. Use o botão para iniciar ou continuar de onde parou.";
 updateTreatmentButtons();
}
async function loadTreatmentStatus(){
 const run=liveSelected,city=currentCity();
 treatmentStop=true;
 treatmentState=null;
 updateTreatmentButtons();
 if(!run){
  el("stockDailyTreatmentStatus").textContent="Pesquise primeiro os equipamentos utilizados.";
  return;
 }
 if(city!=="natal"){
  el("stockDailyTreatmentStatus").textContent=
   "Os seriais foram coletados. A consulta individual DataSnap está homologada apenas em Natal; "+
   "Mossoró/Recife aguardam validação do método por serial.";
  return;
 }
 try{
  const data=await request("/api/stock/analyses/imperium/serial-treatment/status?city="+
   encodeURIComponent(city)+"&run="+encodeURIComponent(run.id),{timeoutMs:30000});
  if(city!==currentCity()||run.id!==liveSelected?.id)return;
  if(!data?.ok)throw new Error(data?.error||"Tratativa indisponível");
  showTreatmentResult(data);
 }catch(err){
  if(city===currentCity()&&run.id===liveSelected?.id){
   el("stockDailyTreatmentStatus").textContent=
    "Não foi possível carregar a tratativa do Supabase: "+(err.message||err);
  }
 }
}
async function treatCollectedSerials(){
 const city=currentCity(),run=liveSelected;
 if(treatmentBusy)return;
 if(city!=="natal"||!run){
  el("stockDailyTreatmentStatus").textContent=
   "Selecione uma coleta salva de Natal; a tratativa individual de outras praças ainda não foi validada.";
  return;
 }
 if(!canWrite()){
  el("stockDailyTreatmentStatus").textContent="Somente administrador/controlador pode executar a tratativa.";
  return;
 }
 treatmentBusy=true;treatmentStop=false;updateTreatmentButtons();
 let retryErrors=Boolean(treatmentState?.complete&&treatmentState?.counts?.erro_consulta);
 try{
  while(!treatmentStop&&currentCity()===city&&liveSelected?.id===run.id){
   el("stockDailyTreatmentStatus").textContent=
    "Consultando o próximo serial no Imperium e salvando o resultado no Supabase...";
   const result=await request("/api/stock/analyses/imperium/serial-treatment/next",{
    method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify({city,run:run.id,retry_errors:retryErrors}),
    timeoutMs:120000
   });
   if(!result?.ok)throw new Error(result?.error||"Consulta do serial não confirmada");
   if(currentCity()!==city||liveSelected?.id!==run.id)return;
   showTreatmentResult(result);
   if(!result.updated){
    if(!retryErrors&&result.complete&&(result.counts?.erro_consulta||0)>0){
     retryErrors=true;continue;
    }
    break;
   }
  }
  if(treatmentStop){
   el("stockDailyTreatmentStatus").textContent=
    "Tratativa pausada. Os resultados já consultados foram salvos; clique novamente para retomar.";
  }
 }catch(err){
  el("stockDailyTreatmentStatus").textContent=
   "Tratativa interrompida: "+(err.message||err)+
   ". Os seriais já confirmados continuam salvos no Supabase; clique para retomar.";
 }finally{
  treatmentBusy=false;
  updateTreatmentButtons();
  if(liveSelected?.id===run.id)void loadAtlasVideoStatus();
 }
}
async function downloadTreatment(){
 const run=liveSelected,city=currentCity();
 if(!run||!treatmentState?.download_enabled)return;
 try{
  const result=await requestBlob("/api/stock/analyses/imperium/serial-treatment/export?city="+
   encodeURIComponent(city)+"&run="+encodeURIComponent(run.id),{timeoutMs:120000});
  const bytes=new Uint8Array(await result.blob.slice(0,4).arrayBuffer());
  if(result.blob.size<300||bytes[0]!==80||bytes[1]!==75||bytes[2]!==3||bytes[3]!==4){
   throw new Error("Relatório retornado não é um XLSX válido");
  }
  saveBlob(result.blob,"TRATATIVA-SERIAIS-"+city.toUpperCase()+"-"+
   (run.start||"periodo")+".xlsx");
 }catch(err){
  el("stockDailyTreatmentStatus").textContent=
   "Falha ao baixar o relatório tratado: "+(err.message||err);
 }
}
function clearAtlasVideoView(){
 atlasVideoStop=true;
 atlasVideoState=null;
 el("stockDailyAtlasVideoProgress").value=0;
 el("stockDailyAtlasVideoProgress").max=1;
 el("stockDailyAtlasVideoTable").replaceChildren();
 el("stockDailyAtlasVideoCounts").textContent="";
 el("stockDailyAtlasVideoMessage").textContent=
  "Primeiro pesquise o período e confirme a tratativa Imperium.";
 updateAtlasVideoButtons();
}
function updateAtlasVideoButtons(){
 const city=currentCity(),run=liveSelected;
 const ready=canWrite()&&city==="natal"&&!!run&&
  (treatmentState?.counts?.processados||0)>0;
 const atlas=atlasVideoState?.counts||{};
 const pending=atlasVideoState?.atlas_pendentes??Infinity;
 const busy=atlasVideoBusy;
 el("stockDailyAtlasVideoRun").disabled=busy||!ready||pending<=0;
 el("stockDailyAtlasVideoAll").disabled=busy||!ready||pending<=0;
 el("stockDailyAtlasVideoPause").disabled=!busy;
 el("stockDailyAtlasVideoReload").disabled=busy||!run||city!=="natal";
 el("stockDailyAtlasVideoRun").textContent=busy?
  "Conferindo serial no Atlas...":"Conferir próximo serial no Atlas";
 el("stockDailyAtlasVideoRun").title=city!=="natal"
  ?"Consulta Atlas por serial homologada somente para Natal":
  "Usa a ponte autenticada Atlas; preserva fila e progresso no Supabase";
}
function showAtlasVideoResult(payload){
 atlasVideoState=payload;
 const c=payload.counts||{},total=Math.max(1,c.total||0);
 const bar=el("stockDailyAtlasVideoProgress");
 bar.max=total;
 bar.value=Math.min(total,payload.atlas_finalizados||0);
 el("stockDailyAtlasVideoCounts").textContent=
  (payload.atlas_finalizados||0)+" de "+(c.total||0)+" seriais avaliados no Atlas • "+
  (c.atlas_verificados||0)+" verificados • "+
  (c.atlas_parciais||0)+" parciais • "+
  (c.atlas_nao_confirmados||0)+" não confirmados • "+
  (c.atlas_fila||0)+" na fila • "+
  (c.atlas_submissao_incerta||0)+" com confirmação pendente • "+
  (c.atlas_erros||0)+" erros • "+
  (c.atlas_formatos_pendentes||0)+" formatos pendentes.";
 const table=el("stockDailyAtlasVideoTable");
 table.replaceChildren();
 const fields=[
  ["serial","Serial"],["modelo_imperium","Equipamento"],
  ["situacao_atlas","Situação Atlas"],["estado_atlas","Estado"],
  ["localizacao_atlas","Localização informada"],
  ["data_alteracao_atlas","Data da alteração"],
  ["observacao","Observação"]
 ];
 const thead=document.createElement("thead"),heading=document.createElement("tr");
 for(const [,label] of fields){
  const th=document.createElement("th");th.textContent=label;
  heading.appendChild(th);
 }
 thead.appendChild(heading);table.appendChild(thead);
 const body=document.createElement("tbody");
 for(const item of payload.rows||[]){
  const tr=document.createElement("tr");
  for(const [name] of fields){
   const td=document.createElement("td");
   td.textContent=String(item[name]??"");
   tr.appendChild(td);
  }
  body.appendChild(tr);
 }
 table.appendChild(body);
 el("stockDailyAtlasVideoMessage").textContent=
  (payload.atlas_pendentes||0)===0
  ?"Conferência Atlas registrada com pendências explícitas. O estoque físico não está comprovado."
  :"Conferência Atlas salva no Supabase. Execute ou retome os seriais disponíveis.";
 updateAtlasVideoButtons();
}
async function loadAtlasVideoStatus(){
 const run=liveSelected,city=currentCity();
 atlasVideoStop=true;
 if(!run||city!=="natal"){
  clearAtlasVideoView();
  if(run&&city!=="natal"){
   el("stockDailyAtlasVideoMessage").textContent=
    "A consulta por período funciona nesta cidade; a ponte Atlas individual está validada somente para Natal.";
  }
  return;
 }
 try{
  const result=await request(
   "/api/stock/analyses/imperium/atlas-video/status?city="+
   encodeURIComponent(city)+"&run="+encodeURIComponent(run.id),
   {timeoutMs:30000}
  );
  if(currentCity()!==city||liveSelected?.id!==run.id)return;
  if(!result?.ok)throw new Error(result?.error||"Estado Atlas não disponível");
  showAtlasVideoResult(result);
 }catch(err){
  if(currentCity()===city&&liveSelected?.id===run.id){
   el("stockDailyAtlasVideoMessage").textContent=
    "Não foi possível consultar a conferência Atlas: "+(err.message||err);
  }
 }finally{updateAtlasVideoButtons();}
}
async function runAtlasVideo(limit=1){
 if(atlasVideoBusy||!canWrite()||currentCity()!=="natal"||!liveSelected)return;
 if(!(treatmentState?.counts?.processados>0)){
  el("stockDailyAtlasVideoMessage").textContent=
   "Trate primeiro pelo menos um serial no Imperium.";
  return;
 }
 const city=currentCity(),run=liveSelected;
 atlasVideoBusy=true;
 atlasVideoStop=false;
 updateAtlasVideoButtons();
 try{
  for(let step=0;step<limit&&!atlasVideoStop;step++){
   if(city!==currentCity()||liveSelected?.id!==run.id)break;
   el("stockDailyAtlasVideoMessage").textContent=
    "Consultando a próxima evidência Atlas e persistindo no Supabase...";
   const result=await request("/api/stock/analyses/imperium/atlas-video/next",{
    method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify({city,run:run.id}),timeoutMs:60000
   });
   if(!result?.ok)throw new Error(result?.error||"Atlas não confirmou o resultado");
   if(city!==currentCity()||liveSelected?.id!==run.id)break;
   showAtlasVideoResult(result);
   if(!result.updated||result.atlas_pendentes===0)break;
   // A returned queue ID is polled without re-enqueue. Pace calls so the
   // existing Atlas browser extension can finish each read-only lookup.
   if(limit>1&&result.updated.situacao==="aguardando_atlas"){
    await new Promise(resolve=>setTimeout(resolve,1400));
   }
  }
  if(city===currentCity()&&liveSelected?.id===run.id){
   el("stockDailyAtlasVideoMessage").textContent=atlasVideoStop
    ?"Conferência pausada. Os resultados e o ID da fila foram preservados para retomar."
    :"Consulta Atlas concluída ou lote encerrado. Confira os resultados e as pendências.";
  }
 }catch(err){
  el("stockDailyAtlasVideoMessage").textContent=
   "Consulta Atlas interrompida: "+(err.message||err)+
   ". IDs de fila já registrados permanecem no Supabase; verifique antes de repetir.";
 }finally{
  atlasVideoBusy=false;updateAtlasVideoButtons();
 }
}
clearAtlasVideoView();
el("stockDailyAtlasVideoRun").addEventListener("click",()=>void runAtlasVideo(1));
el("stockDailyAtlasVideoAll").addEventListener("click",()=>void runAtlasVideo(900));
el("stockDailyAtlasVideoPause").addEventListener("click",()=>{
 atlasVideoStop=true;
 el("stockDailyAtlasVideoMessage").textContent=
  "Pausando após salvar/confirmar a resposta Atlas atual...";
});
el("stockDailyAtlasVideoReload").addEventListener("click",()=>void loadAtlasVideoStatus());
clearTreatmentView();
el("stockDailyTreatmentRun").addEventListener("click",()=>void treatCollectedSerials());
el("stockDailyTreatmentPause").addEventListener("click",()=>{
 if(treatmentBusy){
  treatmentStop=true;
  el("stockDailyTreatmentStatus").textContent="Pausando após concluir a consulta atual...";
 }
});
el("stockDailyTreatmentExport").addEventListener("click",()=>void downloadTreatment());
el("stockDailyAnalysisRefresh").addEventListener("click",()=>void consultLivePeriod());
el("stockDailyHistoryRefresh").addEventListener("click",()=>void loadDaily());
el("stockDailyLiveHistory").addEventListener("change",event=>{
 treatmentStop=true;
 atlasVideoStop=true;
 clearTreatmentView();
 liveSelected=liveRuns.find(x=>x.id===event.target.value)||null;
 if(liveSelected){
  void showLivePage(1);
  void loadTreatmentStatus();
  void loadAtlasVideoStatus();
 }
});
el("stockDailyLiveCategory").addEventListener("change",()=>void showLivePage(1));
el("stockDailyLivePrevious").addEventListener("click",()=>void showLivePage(livePage-1));
el("stockDailyLiveNext").addEventListener("click",()=>void showLivePage(livePage+1));
el("stockDailyImperiumExtract").addEventListener("click",()=>void extractSource());
el("stockDailyImperiumDownload").addEventListener("click",()=>void downloadSource());
el("stockDailyImperiumHistory").addEventListener("change",e=>{
 sourceSelected=sourceRuns.find(run=>run.id===e.target.value)||null;
 if(sourceSelected)void displaySourceSheet(0);
});
el("stockDailyRangeStart").addEventListener("change",()=>{
 void loadLiveHistory();
 void loadSourceHistory();
});
el("stockDailyRangeEnd").addEventListener("change",()=>{
 void loadLiveHistory();
 void loadSourceHistory();
});
el("stockDailyAnalysisOpen").addEventListener("click",()=>setVisible(true));
el("stockDailyAnalysisHistory").addEventListener("change",async e=>{
 const id=e.target.value;const city=currentCity();
 try{
   const data=await request("/api/stock/analyses/daily?city="+city,{timeoutMs:30000});
   selected=(data.history||[]).find(x=>x.id===id)||null;
   if(selected)await displaySheet(0);
 }catch(error){status("Erro ao mudar a data: "+error.message,true)}
});
el("stockDailyAnalysisImport").addEventListener("click",()=>void importWorkbook());
el("stockDailyAnalysisDownload").addEventListener("click",()=>void download());
document.addEventListener("dominium:scope-change",()=>{
  if(state.activeModule!=="stock" || panel.hidden)return;
  // Não reter na interface linhas consolidadas ao voltar para uma cidade específica.
  selected=null;
  allRuns=[];
  el("stockDailyAnalysisTable").replaceChildren();
  el("stockDailyAnalysisTabs").replaceChildren();
  el("stockDailyAnalysisSheetInfo").textContent="";
  el("stockDailyAnalysisDownload").disabled=true;
  el("stockDailyAnalysisImport").hidden=!canWrite()||currentCity()==="all";
  clearSourceView();
  clearLivePreview();
  updateSourceAvailability();
  liveButton();
  void loadDaily();
  void loadLiveHistory();
  void loadSourceHistory();
});
document.addEventListener("dominium:stock-tab-change",()=>{
 if(state.activeModule!=="stock"||el("stockReportsTab")?.getAttribute("aria-selected")!=="true"){
   panel.hidden=true;
 }
});
})();
