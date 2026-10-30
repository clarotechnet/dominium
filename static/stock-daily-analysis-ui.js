/* Daily equipment: independent period/catalog; Atlas QUERY is not its source. */
(() => {
"use strict";
const el=id=>document.getElementById(id);
const panel=el("stockDailyAnalysisPanel");
if(!panel)return;
const tabs=["Atlas","Chips Atlas","IMPERIUM","CHIP IMPERIUM","Assinantes","Nomes."];
let selected=null,activeTab=0,fetching=false;
let allRuns=[];
const currentCity=()=>state.profile;
const canWrite=()=>["admin","controller"].includes(state.authUser?.role);
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
 void loadDaily();
}
async function loadDaily(){
 if(fetching)return;
 fetching=true;
 const city=currentCity(),day=el("stockDailyAnalysisDate").value;
 try{
   let url="/api/stock/analyses/daily?city="+encodeURIComponent(city);
   const start=el("stockDailyRangeStart").value,end=el("stockDailyRangeEnd").value;
   if(start&&end){if(start>end)throw new Error("Data inicial maior que a final");url+="&start="+start+"&end="+end;}
   else if(day)url+="&date="+encodeURIComponent(day);
   const data=await request(url,{timeoutMs:30000});
   if(city!==currentCity())return;
   selected=data.selected||data.latest||null;
   allRuns=[];
   if(city==="all"){
     const latestByCity=new Map();
     for(const item of data.history||[]){
       if(!latestByCity.has(item.city))latestByCity.set(item.city,item);
     }
     allRuns=[...latestByCity.values()];
   }
   const historic=el("stockDailyAnalysisHistory");
   const options=document.createDocumentFragment();
   for(const item of data.history||[]){
     const opt=document.createElement("option");
     opt.value=item.id;
     opt.textContent=item.city.toUpperCase()+" • "+item.date+" • "+item.origin+" • "+item.filename;
     options.appendChild(opt);
   }
   historic.replaceChildren(options);
   if(selected){
     historic.value=selected.id;
     status((data.selected?"Período selecionado":"Última análise disponível")+
       ": "+selected.date+" • "+selected.origin+
       ". Dados compartilhados entre usuários. Fonte: "+selected.filename);
     await displaySheet(0);
   }else{
     el("stockDailyAnalysisTable").replaceChildren();
     el("stockDailyAnalysisTabs").replaceChildren();
     el("stockDailyAnalysisDownload").disabled=true;
     status("Nenhuma análise diária registrada para esta operação. A extração automática por período do Imperium ainda não está integrada. É possível registrar o Excel final histórico.");
   }
 }catch(error){status("Erro ao consultar análise diária: "+(error.message||error),true)}
 finally{fetching=false;}
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
el("stockDailyAnalysisOpen").addEventListener("click",()=>setVisible(true));
el("stockDailyAnalysisDate").addEventListener("change",()=>void loadDaily());
el("stockDailyRangeStart").addEventListener("change",()=>void loadDaily());
el("stockDailyRangeEnd").addEventListener("change",()=>void loadDaily());
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
el("stockDailyAnalysisRefresh").addEventListener("click",()=>void loadDaily());
document.addEventListener("dominium:stock-tab-change",()=>{
 if(state.activeModule!=="stock"||el("stockReportsTab")?.getAttribute("aria-selected")!=="true"){
   panel.hidden=true;
 }
});
})();
