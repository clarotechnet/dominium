/* The three stock analysis processes have independent, paged workspace views. */
(() => {
  "use strict";
  const byId=id=>document.getElementById(id);
  const buttons=[...document.querySelectorAll("[data-stock-analysis-tab]")];
  if(!buttons.length)return;
  const stateByKind={query:{page:1,pages:1,job:null},suspeitos:{page:1,pages:1,job:null}};
  let selected="query";
  const title={query:"Query",suspeitos:"Suspects"};
  function displayTab(name){
    if(!["query","equipamentos","suspeitos"].includes(name))return;
    selected=name;
    for(const button of buttons){
      const active=button.dataset.stockAnalysisTab===name;
      button.classList.toggle("active",active);
      button.setAttribute("aria-selected",String(active));
    }
    document.querySelectorAll("[data-stock-analysis-workspace]").forEach(panel=>{
      panel.hidden=panel.dataset.stockAnalysisWorkspace!==name;
    });
    if(name==="equipamentos"){
      byId("stockDailyAnalysisOpen")?.click();
    }else{void loadLatest(name);}
  }
  function draw(kind,data){
    const key=title[kind];
    const table=byId("stock"+key+"PreviewTable");
    if(!table)return;
    table.replaceChildren();
    const head=document.createElement("thead");
    const hr=document.createElement("tr");
    for(const v of data.header||[]){
      const th=document.createElement("th");
      th.textContent=String(v||"");hr.appendChild(th);
    }
    head.appendChild(hr);table.appendChild(head);
    const body=document.createElement("tbody");
    for(const row of data.rows||[]){
      const tr=document.createElement("tr");
      for(const v of row){
        const td=document.createElement("td");
        td.textContent=String(v??"");tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    stateByKind[kind].page=data.page;
    stateByKind[kind].pages=data.pages;
    byId("stock"+key+"PageInfo").textContent=
      data.total.toLocaleString("pt-BR")+" registros • página "+data.page+" de "+data.pages;
    byId("stock"+key+"Prev").disabled=data.page<=1;
    byId("stock"+key+"Next").disabled=data.page>=data.pages;
  }
  async function showPage(kind,page){
    const ctx=stateByKind[kind];
    const job=ctx.job;
    if(!job||state.profile!==job.city)return;
    const key=title[kind];
    try{
      const result=await request("/api/stock/analyses/jobs/"+job.id+"/data?page="+page,{timeoutMs:60000});
      if(ctx.job?.id!==job.id || state.profile!==job.city)return;
      draw(kind,result);
    }catch(error){
      byId("stock"+key+"PageInfo").textContent="Falha ao carregar: "+(error.message||error);
    }
  }
  async function loadLatest(kind){
    if(!["query","suspeitos"].includes(kind))return;
    const city=state.profile,key=title[kind];
    try{
      const data=await request("/api/stock/analyses/jobs",{timeoutMs:30000});
      if(city!==state.profile)return;
      const job=(data.jobs||[]).find(x=>x.city===city && x.kind===kind && x.state==="ready"
         && x.summary?.filter_version==="dmv_diniz_me_eireli_v1");
      const ctx=stateByKind[kind];
      if(!job){
        ctx.job=null;
        byId("stock"+key+"PageInfo").textContent=
          "Nenhuma versão tratada com o filtro DMV DINIZ. Clique em Atualizar tratamento.";
        byId("stock"+key+"PreviewTable").replaceChildren();
        byId("stock"+key+"Prev").disabled=true;
        byId("stock"+key+"Next").disabled=true;
        byId(kind==="query"?"stockQueryLastDownload":"stockSuspectsLastDownload").hidden=true;
        return;
      }
      if(ctx.job?.id!==job.id){ctx.job=job;ctx.page=1;}
      await showPage(kind,ctx.page);
    }catch(error){
      byId("stock"+key+"PageInfo").textContent="Consulta indisponível: "+(error.message||error);
    }
  }
  for(const button of buttons){
    button.addEventListener("click",()=>displayTab(button.dataset.stockAnalysisTab));
  }
  for(const kind of ["query","suspeitos"]){
    const key=title[kind];
    byId("stock"+key+"Prev")?.addEventListener("click",()=>void showPage(kind,stateByKind[kind].page-1));
    byId("stock"+key+"Next")?.addEventListener("click",()=>void showPage(kind,stateByKind[kind].page+1));
  }
  byId("stockReportsRefresh")?.addEventListener("click",()=>{if(selected!=="equipamentos")void loadLatest(selected);});
  document.addEventListener("dominium:stock-report-ready",event=>{
    if(event.detail?.kind===selected)void loadLatest(selected);
  });
  document.addEventListener("dominium:module-change",()=>{
    if(state.activeModule==="stock" && byId("stockReportsTab")?.getAttribute("aria-selected")==="true"){
      displayTab(selected);
    }
  });
  displayTab("query");
})();
