/* Stock analysis reports: three read-only jobs reusing last verified Atlas QUERY. */
(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const tab = byId("stockReportsTab");
  const pane = byId("stockReportsPane");
  if (!tab || !pane) return;
  let pending = false;
  let current = null;
  let pollTimer = null;
  let lastProfile = null;
  const names = {
    query:"QUERY tratada",
    equipamentos:"Analise de equipamentos",
    suspeitos:"Analise de suspeitos"
  };
  const isActive = () => state.activeModule === "stock"
    && tab.getAttribute("aria-selected") === "true";
  const allowed = () => ["admin","controller"].includes(state.authUser?.role);
  function message(txt, error=false) {
    const n=byId("stockReportsNotice");
    n.textContent=txt||"";
    n.classList.toggle("quality-error", Boolean(error));
  }
  function setBusy(value) {
    pending=value;
    pane.querySelectorAll("[data-stock-report]").forEach(button=>button.disabled=value||!allowed());
    byId("stockReportsRefresh").disabled=value;
  }
  function select() {
    const views=[
      ["stockInventoryTab","stockInventoryPane"],
      ["stockQualityTab","stockQualityPane"],
      ["stockDailyTab","stockDailyPane"],
      ["stockReportsTab","stockReportsPane"]
    ];
    for(const [t,p] of views) {
      const active=t==="stockReportsTab";
      byId(t)?.classList.toggle("active",active);
      byId(t)?.setAttribute("aria-selected",String(active));
      byId(p)?.classList.toggle("hidden",!active);
    }
    if(state.activeModule==="stock") {
      const url=new URL(window.location.href);
      url.hash="analises-estoque";
      window.history.replaceState(null,"",url.pathname+url.search+url.hash);
    }
    document.dispatchEvent(new Event("dominium:stock-tab-change"));
    void refresh();
  }
  function stopPoll() {
    if(pollTimer!==null){clearTimeout(pollTimer);pollTimer=null;}
  }
  function renderJob(job) {
    current=job;
    const detail=byId("stockReportsProgress");
    const label=names[job.kind]||job.kind;
    const states={queued:"Na fila",processing:"Processando",ready:"Pronto para baixar",failed:"Falhou"};
    let extra="";
    if(job.state==="processing" && Number.isInteger(job.summary?.datasnap_checked)) {
      extra=" • DataSnap: "+job.summary.datasnap_checked+"/"+(job.summary.datasnap_total||0)+" seriais consultados";
    }
    if(job.summary?.parcial)extra=" • RELATORIO PARCIAL: "+(job.summary.limitation||"Validacao pendente");
    detail.textContent=label+" • "+(states[job.state]||job.state)+extra;
    detail.classList.toggle("quality-error",job.state==="failed");
    byId("stockReportsDownload").hidden=job.state!=="ready";
    byId("stockReportsDownload").disabled=job.state!=="ready";
    if(job.error)message("Erro na geracao: "+job.error,true);
    if(job.state==="ready")message(job.summary?.parcial
      ? "Arquivo disponivel com evidencias parciais e pendencias explicitadas. Confira a aba Fontes e criterios."
      : "Relatorio concluido com a ultima QUERY validada.");
    stopPoll();
    if(["queued","processing"].includes(job.state) && isActive()) {
      pollTimer=setTimeout(()=>void readJob(job.id),3500);
    }
  }
  async function readJob(id) {
    try {
      const res=await request("/api/stock/analyses/jobs/"+id,{timeoutMs:30000});
      if(res.job && isActive())renderJob(res.job);
    } catch(error){message("Nao foi possivel atualizar o andamento: "+error.message,true);}
  }
  async function refresh() {
    if(!isActive()||pending||!allowed())return;
    stopPoll();
    lastProfile=state.profile;
    setBusy(true);
    try {
      const [available,history]=await Promise.all([
        request("/api/stock/analyses/available?city="+encodeURIComponent(state.profile),{timeoutMs:25000}),
        request("/api/stock/analyses/jobs",{timeoutMs:25000})
      ]);
      if(lastProfile!==state.profile || !isActive())return;
      const q=available.latest;
      byId("stockReportsSource").textContent=q
        ? "QUERY validada: "+new Date(q.created_at*1000).toLocaleString("pt-BR")
          +" • "+q.total_rows.toLocaleString("pt-BR")+" registros • "+state.profile.toUpperCase()
        : "Nao ha QUERY Atlas concluida para esta operacao. Gere a QUERY na area Atlas Query.";
      if(!q)message("Nenhuma QUERY validada. Nao sera gerada outra automaticamente.");
      const select=byId("stockReportsHistory");
      const opts=document.createDocumentFragment();
      for(const job of history.jobs||[]) {
        const option=document.createElement("option");
        option.value=job.id;
        option.textContent=(names[job.kind]||job.kind)+" • "+job.city.toUpperCase()
          +" • "+new Date(job.created_at*1000).toLocaleString("pt-BR")
          +" • "+job.state;
        opts.append(option);
      }
      select.replaceChildren(opts);
      if(history.jobs?.length){
        const same=history.jobs.find(x=>x.city===state.profile);
        if(same){select.value=same.id;renderJob(same);}
      }
    } catch(error){message("Falha ao consultar relatorios: "+(error.message||""),true);}
    finally{setBusy(false);}
  }
  async function start(kind) {
    if(pending||!allowed()||!isActive()||!names[kind])return;
    stopPoll();setBusy(true);message("Solicitando "+names[kind]+". A QUERY existente sera reutilizada.");
    try {
      const response=await request("/api/stock/analyses/jobs",{
        method:"POST",headers:{"content-type":"application/json"},
        body:JSON.stringify({city:state.profile,kind}),timeoutMs:30000
      });
      if(response.job){renderJob(response.job);
        message(response.reused ? "Execucao anterior reutilizada, sem criar outra QUERY no Atlas."
          : "Relatorio registrado. O servidor ira preparar o XLSX.");}
    } catch(error){message("Nao foi possivel iniciar: "+(error.message||""),true);}
    finally{setBusy(false);}
  }
  async function download() {
    if(!current || current.state!=="ready")return;
    try{
      const response=await requestBlob("/api/stock/analyses/jobs/"+current.id+"/export",
        {timeoutMs:120000});
      saveBlob(response.blob, "DOMINIUM-"+current.kind+"-"+current.city+"-"+current.id.slice(0,8)+".xlsx");
    }catch(error){message("Erro ao baixar o XLSX: "+(error.message||""),true);}
  }
  tab.addEventListener("click",select);
  byId("stockReportsRefresh").addEventListener("click",()=>void refresh());
  byId("stockReportsHistory").addEventListener("change",e=>{if(e.target.value)void readJob(e.target.value);});
  byId("stockReportsDownload").addEventListener("click",()=>void download());
  pane.querySelectorAll("[data-stock-report]").forEach(button=>{
    button.addEventListener("click",()=>void start(button.dataset.stockReport));
  });
  document.addEventListener("dominium:module-change",()=>{
    if(!isActive())stopPoll();
  });
  window.addEventListener("hashchange",()=>{
    if(window.location.hash==="#analises-estoque" && state.activeModule==="stock")tab.click();
  });
  if(window.location.hash==="#analises-estoque" && state.activeModule==="stock")tab.click();
})();
