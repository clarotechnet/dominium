/* Estoque diario independente do Imperium; importacao por arquivo e historico. */
(() => {
 "use strict";
 const $=id=>document.getElementById(id);
 const tab=$("stockDailyTab"),pane=$("stockDailyPane"),inventory=$("stockInventoryTab"),quality=$("stockQualityTab");
 if(!tab||!pane)return;
 let latest=null,history=[],items=[],preview=null,loading=false,saving=false,loaded=false;
 const editable=()=>["admin","controller"].includes(state.authUser?.role);
 const notice=(text,fail=false)=>{
   $("dailyStockStatus").textContent=text||"";
   $("dailyStockStatus").classList.toggle("quality-error",fail);
 };
 const fmt=(n)=>Number(n||0).toLocaleString("pt-BR",{maximumFractionDigits:3});
 const dt=s=>s?new Date(s).toLocaleString("pt-BR"):"—";
 const td=(row,value)=>{
   const n=document.createElement("td");n.textContent=String(value??"");row.append(n);return n;
 };
 function activate(){
   inventory.classList.remove("active");quality.classList.remove("active");tab.classList.add("active");
   inventory.setAttribute("aria-selected","false");quality.setAttribute("aria-selected","false");
   tab.setAttribute("aria-selected","true");
   $("stockInventoryPane").classList.add("hidden");
   $("stockQualityPane").classList.add("hidden");
   pane.classList.remove("hidden");
   $("dailyStockUpload").hidden=!editable();
   if(state.activeModule==="stock"){
     const url=new URL(window.location.href);url.hash="estoque-diario";
     window.history.replaceState(null,"",url.pathname+url.search+url.hash);
   }
   document.dispatchEvent(new Event("dominium:module-change"));
   if(!loading&&!loaded)void load();
 }
 function render(){
   $("dailyStockFileCount").textContent=latest
     ?fmt(latest.materiais_distintos)+" materiais • "+fmt(latest.quantidade_total)+" unidades"
     :"Nenhum estoque importado";
   $("dailyStockDateLabel").textContent=latest
     ? "Saldo em "+latest.data_estoque.split("-").reverse().join("/")+" • "+latest.nome_arquivo
     :"Importe uma planilha para iniciar o controle diário.";
   const frag=document.createDocumentFragment();
   history.forEach(entry=>{
     const opt=document.createElement("option");
     opt.value=entry.id;
     opt.textContent=entry.data_estoque.split("-").reverse().join("/")+" • "+entry.nome_arquivo
       +" • "+fmt(entry.quantidade_total)+" unidades";
     frag.append(opt);
   });
   const current=latest?.id||"";
   $("dailyStockHistory").replaceChildren(frag);
   $("dailyStockHistory").value=current;
   const term=$("dailyStockSearch").value.trim().toLocaleLowerCase("pt-BR");
   const found=items.filter(item=>!term||
     (item.material+" "+item.descricao_material).toLocaleLowerCase("pt-BR").includes(term));
   const rows=document.createDocumentFragment();
   found.slice(0,500).forEach(item=>{
     const tr=document.createElement("tr");
     td(tr,item.material);
     td(tr,item.descricao_material);
     td(tr,fmt(item.quantidade_livre));
     rows.append(tr);
   });
   $("dailyStockBody").replaceChildren(rows);
   $("dailyStockRowsInfo").textContent=Math.min(found.length,500)+" de "+found.length+
      " materiais exibidos"+(found.length>500?" (limite visual: 500)":"");
 }
 async function load(id=""){
   if(loading)return;
   loading=true;
   $("dailyStockRefresh").disabled=true;
   notice("Consultando histórico do estoque da empresa...");
   try{
     const path=id?"/api/stock/daily?id="+encodeURIComponent(id):"/api/stock/daily";
     const response=await request(path,{timeoutMs:30000});
     if(!Array.isArray(response.historico)||!Array.isArray(response.items))
       throw Error("Resposta inválida do estoque diário");
     loaded=true;
     history=response.historico;
     latest=response.snapshot||null;items=response.items;
     notice(latest?"Estoque carregado. Os snapshots anteriores foram preservados.":"Ainda não há importações.");
   }catch(error){
     notice(error.message||"Estoque diário indisponível",true);
   }finally{loading=false;$("dailyStockRefresh").disabled=false;render();}
 }
 async function readFile(){
   const file=$("dailyStockFile").files?.[0];if(!file)return;
   preview=null;
   $("dailyStockConfirm").disabled=true;
   $("dailyStockPreview").classList.add("hidden");
   notice("Analisando o Excel localmente. Nenhum dado foi enviado ainda...");
   try{
     preview=await window.DominiumDailyStockParser.parseXlsx(file);
     $("dailyStockPreviewText").textContent=preview.linhas_origem+" linhas no arquivo • "+
       preview.materiais_distintos+" materiais distintos • "+
       fmt(preview.quantidade_total)+" unidades de Utilização Livre."+
       " Códigos sem zeros à esquerda e duplicados somados.";
     $("dailyStockPreview").classList.remove("hidden");
     $("dailyStockConfirm").disabled=!editable();
     notice("Conferência concluída. Escolha a data e confirme a importação.");
   }catch(err){notice(err.message,true);}
 }
 async function commit(){
   if(saving||!preview||!editable())return;
   const day=$("dailyStockImportDate").value;
   if(!/^\d{4}-\d{2}-\d{2}$/.test(day)){notice("Informe a data do estoque.",true);return;}
   if(!window.confirm("Confirmar importação de "+preview.materiais_distintos+
     " materiais em "+day+"? O histórico anterior será preservado."))return;
   saving=true;$("dailyStockConfirm").disabled=true;
   notice("Gravando snapshot no Supabase...");
   try{
     const result=await request("/api/stock/daily",{
       method:"POST",timeoutMs:90000,
       body:JSON.stringify({...preview,data_estoque:day})
     });
     if(!result?.ok)throw Error("Supabase não confirmou a importação");
     notice(result.repetido
       ?"Este mesmo arquivo já estava registrado nesta data."
       :"Importação concluída: "+result.materiais+" materiais gravados.");
     preview=null;$("dailyStockPreview").classList.add("hidden");
     $("dailyStockFile").value="";
     await load();
   }catch(err){
     notice(err.message||"Falha ao salvar",true);
     $("dailyStockConfirm").disabled=false;
   }finally{saving=false;}
 }
 tab.addEventListener("click",activate);
 $("dailyStockRefresh").addEventListener("click",()=>void load());
 $("dailyStockHistory").addEventListener("change",e=>void load(e.target.value));
 $("dailyStockSearch").addEventListener("input",render);
 $("dailyStockUpload").addEventListener("click",()=>$("dailyStockFile").click());
 $("dailyStockFile").addEventListener("change",()=>void readFile());
 $("dailyStockConfirm").addEventListener("click",()=>void commit());
 $("dailyStockCancel").addEventListener("click",()=>{
   preview=null;$("dailyStockFile").value="";$("dailyStockPreview").classList.add("hidden");
   notice("Importação cancelada: nada foi gravado.");
 });
 $("dailyStockImportDate").value=new Date(Date.now()-new Date().getTimezoneOffset()*60000)
   .toISOString().slice(0,10);
 $("dailyStockUpload").hidden=!editable();
 if(window.location.hash==="#estoque-diario"){
   if(state.activeModule==="stock")tab.click();
 }
 window.addEventListener("hashchange",()=>{
   if(window.location.hash==="#estoque-diario"&&state.activeModule==="stock")tab.click();
 });
})();
