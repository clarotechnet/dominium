/* DOMINIUM > Recursos > Análise Backlog. Existing request() adds CSRF/session. */
(() => {
  "use strict";
  const root = document.querySelector("#backlogWorkspace");
  if (!root) return;
  const $ = (id) => root.querySelector("#" + id);
  let comparison = [], candidates = [], currentProfile = "natal", busy = false, lastRunning = false;
  let autoFill = false, nextCycleScheduled = false;
  let routeImportActive = false, dailyRows = [];
  const call = (path, opts={}) => request(path, {timeoutMs:120000,...opts});
  const post = (path, body) => call(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const update = (target, value) => {target.textContent=String(value);};
  async function copy(text) {
    if(!text.trim())return;
    try {await navigator.clipboard.writeText(text);}
    catch {const el=document.createElement("textarea");el.value=text;document.body.append(el);el.select();document.execCommand("copy");el.remove();}
  }
  function table(target,columns,rows,onSend){
    target.replaceChildren();
    if(!rows.length){const p=document.createElement("p");p.textContent="Nenhum registro disponível.";target.append(p);return;}
    const scroll=document.createElement("div");scroll.className="backlog-table-scroll";
    const grid=document.createElement("table");grid.className="backlog-table";
    const head=document.createElement("thead"),tr=document.createElement("tr");
    for(const [label] of columns){const th=document.createElement("th");th.textContent=label;tr.append(th);}
    if(onSend){const th=document.createElement("th");th.textContent="Ação";tr.append(th);}
    head.append(tr);grid.append(head);
    const body=document.createElement("tbody");
    for(const item of rows){
      const tr=document.createElement("tr");
      for(const [,key] of columns){const td=document.createElement("td");td.textContent=String(item[key]??"—");tr.append(td);}
      if(onSend){
        const td=document.createElement("td"),btn=document.createElement("button");btn.type="button";btn.className="button secondary compact";btn.textContent="Marcar enviado";
        btn.addEventListener("click",()=>onSend(item,btn));td.append(btn);tr.append(td);
      }
      body.append(tr);
    }
    grid.append(body);scroll.append(grid);target.append(scroll);
  }
  const reportApi=globalThis.DominiumBacklogReport;
  let comparisonReady=false,comparisonTruncated=false,reportCodes=["101","306","404","430"];
  function scopeFromTop(){
    const current=document.querySelector("#profileTabs .profile-tab.active");
    const label=String(current?.textContent||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase();
    if(label.includes("TODOS"))return "all";
    if(label.includes("FORTALEZA"))return "fortaleza";
    if(label.includes("MOSSORO"))return "mossoro";
    if(label.includes("RECIFE"))return "recife";
    return "natal";
  }
  function cityScope(){
    const chosen=$("backlogCityScope")?.value||"top";
    return chosen==="top"?scopeFromTop():chosen;
  }
  function refreshScopeLabel(){
    const scope=cityScope();
    const names={all:"Todas as cidades",natal:"Natal + Parnamirim",
      fortaleza:"Fortaleza",mossoro:"Mossoró",recife:"Recife"};
    update($("backlogScopeLabel"),"Exibindo: "+(names[scope]||scope));
    return scope;
  }
  function renderDailyRows(){
    if(!reportApi)return;
    const shown=reportApi.filterRows(dailyRows,refreshScopeLabel());
    const metrics=$("backlogDailyMetrics");metrics.replaceChildren();
    const files=document.createElement("span");
    files.textContent=shown.length+" atividades nesta seleção";
    metrics.append(files);
    const counts={};
    for(const row of shown)counts[row.treatment]=(counts[row.treatment]||0)+1;
    for(const [name,count] of Object.entries(counts)){
      const metric=document.createElement("span");metric.textContent=name+": "+count;metrics.append(metric);
    }
    const priority=item=>item.treatment==="IMPRODUTIVA CONFIRMADA"?0:
      item.treatment.startsWith("DIVERGENCIA")?1:item.treatment==="PENDENTE"?3:2;
    const sorted=[...shown].sort((a,b)=>priority(a)-priority(b)||
      String(a.city).localeCompare(String(b.city))||
      String(a.technician).localeCompare(String(b.technician)));
    table($("backlogDailyResult"),[["Tratativa","treatment"],["Contrato","contract"],
      ["Cidade","city"],["Técnico","technician"],["O.S.","os_number"],
      ["Status TOA","activity_status"],["Código","route_code"]],sorted);
  }
  function renderHistoricalReport(){
    const scope=refreshScopeLabel();
    const summary=$("backlogReportSummary");summary.replaceChildren();
    const detail=$("backlogReportDetails");detail.replaceChildren();
    const actions=[$("backlogCopyResult"),$("backlogCopySummary"),$("backlogDownloadImage")];
    for(const btn of actions)btn.disabled=true;
    if(!comparisonReady||!reportApi)return;
    const selected=reportApi.filterRows(comparison,scope);
    const report=reportApi.build(comparison,scope,reportCodes);
    const counts={SEGURAR:0,"OUTRO HISTÓRICO":0,"NÃO CONFIRMADO":0};
    for(const item of selected)counts[item.classification]=(counts[item.classification]||0)+1;
    const metrics=$("backlogMetrics");metrics.replaceChildren();
    for(const [label,count] of Object.entries(counts)){
      const item=document.createElement("span");item.textContent=label+": "+count;metrics.append(item);
    }
    const total=document.createElement("span");
    total.textContent="Contratos para segurar: "+report.total;metrics.prepend(total);
    table($("backlogResult"),[["Análise","classification"],["Contrato","contract"],
      ["Cidade","report_city"],["Recurso","technician"],["Código","historical_code"],
      ["Data histórica","historical_date"]],selected);
    if(comparisonTruncated){
      update($("backlogReportStatus"),
        "ATENÇÃO: há mais contratos na rota do que o limite de análise. O relatório está incompleto e a cópia foi bloqueada.");
      $("backlogReportStatus").classList.add("backlog-warning");
    }else{
      $("backlogReportStatus").classList.remove("backlog-warning");
      update($("backlogReportStatus"),report.total+" contrato(s) com os códigos selecionados, agrupados por cidade e técnico. A base histórica atual preserva a data da baixa, mas não o horário.");
      $("backlogCopyResult").disabled=report.total===0;
      $("backlogCopySummary").disabled=report.total===0;
      $("backlogDownloadImage").disabled=report.total===0;
    }
    if(!report.groups.length){
      const empty=document.createElement("p");empty.textContent="Nenhuma correspondência com os códigos selecionados nesta cidade.";
      summary.append(empty);return;
    }
    for(const city of report.groups){
      const card=document.createElement("section");card.className="backlog-report-city";
      const header=document.createElement("h4");header.textContent=city.label;card.append(header);
      const grid=document.createElement("table"),head=document.createElement("thead");
      const heading=document.createElement("tr");
      for(const label of ["Código","Quantidade"]){
        const cell=document.createElement("th");cell.textContent=label;heading.append(cell);
      }
      head.append(heading);grid.append(head);
      const body=document.createElement("tbody");
      for(const [code,count] of Object.entries(city.codeCounts).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))){
        const tr=document.createElement("tr");
        for(const value of [code,count]){const td=document.createElement("td");td.textContent=String(value);tr.append(td);}
        body.append(tr);
      }
      grid.append(body);
      const foot=document.createElement("tfoot"),row=document.createElement("tr");
      for(const value of ["TOTAL",city.count]){const td=document.createElement("td");td.textContent=String(value);row.append(td);}
      foot.append(row);grid.append(foot);card.append(grid);summary.append(card);

      const cityDetails=document.createElement("details");cityDetails.open=true;
      const headline=document.createElement("summary");headline.textContent=city.label+" • "+city.count+" contrato(s)";
      cityDetails.append(headline);
      for(const tech of city.technicians){
        const sec=document.createElement("section");sec.className="backlog-report-tech";
        const name=document.createElement("h5");name.textContent=tech.name+" — "+tech.contracts.length+" contrato(s)";sec.append(name);
        const list=document.createElement("ul");
        for(const item of tech.contracts){
          const li=document.createElement("li");
          const contract=document.createElement("strong");contract.textContent="Contrato "+item.contract;
          li.append(contract,document.createTextNode(" • Baixa histórica "+item.historical_code+
            " • "+reportApi.formatDate(item.historical_date)));
          list.append(li);
        }
        sec.append(list);cityDetails.append(sec);
      }
      detail.append(cityDetails);
    }
  }
  function scopeChanged(){
    renderDailyRows();renderHistoricalReport();
  }
  $("backlogCityScope").addEventListener("change",scopeChanged);
  const topTabs=document.querySelector("#profileTabs");
  if(topTabs)new MutationObserver(scopeChanged).observe(topTabs,{childList:true});
  $("backlogDownloadImage").addEventListener("click",()=>action($("backlogDownloadImage"),async()=>{
    if(!reportApi||!comparisonReady||comparisonTruncated)
      throw Error("Analise os arquivos completos antes de baixar a imagem");
    const imageApi=globalThis.DominiumBacklogReportImage;
    if(!imageApi)throw Error("Exportador PNG indisponível; atualize a página");
    const scope=cityScope();
    const report=reportApi.build(comparison,scope,reportCodes);
    const filename=await imageApi.download(report,scope);
    update($("backlogReportStatus"),"Imagem PNG gerada: "+filename+". A cidade selecionada foi respeitada.");
  },$("backlogReportStatus")));
  $("backlogCopySummary").addEventListener("click",()=>{if(!reportApi||!comparisonReady||comparisonTruncated)return;
    const report=reportApi.build(comparison,cityScope(),reportCodes);
    const lines=["RESUMO DE CÓDIGOS POR CIDADE"];
    for(const city of report.groups){
      lines.push("","📍 "+city.label);
      for(const [code,count] of Object.entries(city.codeCounts).sort((a,b)=>b[1]-a[1])){
        lines.push("Código "+code+": "+count);
      }
      lines.push("TOTAL: "+city.count);
    }
    copy(lines.join("\n"));
  });
  async function refreshStatus(){
    try{
      const s=await call("/api/backlog/year/status"),run=s.run||null;
      const info=run ? ["Última execução: "+run.status,run.done_tasks+"/"+run.total_tasks+" dias",run.imported+" O.S. confirmadas",run.unconfirmed+" sem código"].join(" • ") : "Nenhuma consulta executada";
      const historyTotal=Object.values(s.history||{}).reduce((sum,n)=>sum+(Number(n)||0),0);
      update($("backlogSyncStatus"),"Histórico armazenado: "+historyTotal+" ocorrências. "+info);
      const view=$("backlogProgress");view.replaceChildren();
      for(const [key,label] of Object.entries({natal:"Natal/Parnamirim",fortaleza:"Fortaleza",mossoro:"Mossoró",recife:"Recife"})){
        const span=document.createElement("span");span.textContent=label+": "+((s.checkpoints||{})[key]||"a iniciar");view.append(span);
      }
      if(run?.error){const p=document.createElement("p");p.textContent=(s.running?"Erro da execução: ":"Erro da última tentativa: ")+run.error;p.className="backlog-warning";view.append(p);}
      $("backlogRun").disabled=true; // Annual importer remains server-locked.
      $("backlogPilot").disabled=Boolean(s.running);
      $("backlogPause").disabled=!s.running;
      lastRunning=Boolean(s.running);
      if(autoFill && !s.running && !busy && !nextCycleScheduled){
        if(s.run?.status==="failed" || s.run?.status==="interrupted"){
          autoFill=false;
        }else{
          const done=Object.keys({natal:1,fortaleza:1,mossoro:1,recife:1}).every(
            k=>(s.checkpoints||{})[k] && s.checkpoints[k]>=s.window_end
          );
          if(done){autoFill=false;update($("backlogSyncStatus"),"Histórico anual carregado até ontem.");}
          else{
            nextCycleScheduled=true;
            setTimeout(async()=>{
              nextCycleScheduled=false;
              if(!autoFill || busy)return;
              try{
                await post("/api/backlog/year/start",{mode:"batch",days_per_profile:1});
              }catch(e){autoFill=false;update($("backlogSyncStatus"),"Carga interrompida: "+e.message);}
              await refreshStatus();
            },15000);
          }
        }
      }

    }catch(err){update($("backlogSyncStatus"),"Status indisponível: "+err.message);$("backlogRun").disabled=true;}
  }
  function syncRouteButtons(){
    // A importação e a comparação não devem concorrer; ao concluir, liberar os três botões.
    const locked=busy||routeImportActive;
    for(const id of ["backlogFromTOA","backlogUpload","backlogCompare"]){
      $(id).disabled=locked;
    }
  }
  async function action(button,handler,out=$("backlogSyncStatus")){
    if(busy)return;
    const previouslyDisabled=button.disabled;
    busy=true;
    button.disabled=true;
    syncRouteButtons();
    try{await handler();}
    catch(e){update(out,"Erro: "+e.message);}
    finally{
      busy=false;
      try{await refreshStatus();}
      finally{
        // Os controles de execução refletem o estado real do servidor.
        if(button.id==="backlogRun")button.disabled=true;
        else if(button.id==="backlogPilot")button.disabled=lastRunning;
        else if(button.id==="backlogPause")button.disabled=!lastRunning;
        else button.disabled=previouslyDisabled;
        syncRouteButtons();
      }
    }
  }
  $("backlogRun").addEventListener("click",()=>action($("backlogRun"),async()=>{
    autoFill=true;
    const r=await post("/api/backlog/year/start",{mode:"batch",days_per_profile:1});
    update($("backlogSyncStatus"),"Carga anual iniciada: "+r.tasks+" dia(s) por lote, retomada automática a cada ciclo. Mantenha esta tela aberta.");
  }));
  $("backlogPilot").addEventListener("click",()=>action($("backlogPilot"),async()=>{
    autoFill=false;
    const r=await post("/api/backlog/year/start",{mode:"probe",profile:$("backlogProfile").value});
    update($("backlogSyncStatus"),"Teste somente leitura iniciado: "+r.run_id);
  }));
  $("backlogPause").addEventListener("click",()=>action($("backlogPause"),async()=>{
    autoFill=false;
    const r=await post("/api/backlog/year/pause",{});update($("backlogSyncStatus"),r.message);
  }));
  async function loadDailyTreatment(){
    const status=await call("/api/backlog/year/status");
    const r=status.daily_treatment||{rows:[],counts:{},sources:[],total:0};
    dailyRows=r.rows||[];
    renderDailyRows();
  }
  async function pollToaRoutes(){
    try{
      const response=await call("/api/backlog/year/status");
      const state=response.toa_import||{status:"idle",running:false,done:0,total:5};
      routeImportActive=Boolean(state.running);
      syncRouteButtons();
      update($("backlogAutoStatus"),state.running?
        "Consultando TOA: "+(state.route||"buckets")+" • "+state.done+"/"+state.total+" arquivos":
        state.status==="completed"?"Cinco rotas do TOA importadas. Tratativa atualizada.":
        state.status==="failed"?"Falha na captura TOA: "+(state.error||"verifique a sessão"):
        "Pronto para consultar as cinco rotas do TOA.");
      if(state.status==="completed"&&!pollToaRoutes._loaded){
        pollToaRoutes._loaded=true;await loadDailyTreatment();
        update($("backlogUploadStatus"),
          "Rotas atualizadas. Clique em Analisar arquivos para gerar o comparativo do grupo.");
      }
      if(state.running)pollToaRoutes._loaded=false;
    }catch(err){
      // Se a exportação já começou, preservar o bloqueio até confirmar seu fim.
      syncRouteButtons();
      update($("backlogAutoStatus"),"Status TOA indisponível: "+err.message);
    }
  }
  $("backlogFromTOA").addEventListener("click",()=>action($("backlogFromTOA"),async()=>{
    if(routeImportActive)throw Error("Consulta TOA já em andamento");
    pollToaRoutes._loaded=false;
    comparisonReady=false;comparison=[];renderHistoricalReport();
    await post("/api/backlog/year/routes",{source:"toa"});
    routeImportActive=true;
    await pollToaRoutes();
  },$("backlogAutoStatus")));
  $("backlogDailyRefresh").addEventListener("click",()=>action($("backlogDailyRefresh"),loadDailyTreatment,$("backlogAutoStatus")));
  $("backlogCopyImproductive").addEventListener("click",()=>copy(
    reportApi.filterRows(dailyRows,cityScope())
      .filter(r=>r.treatment==="IMPRODUTIVA CONFIRMADA")
      .map(r=>[r.contract,reportApi.reportCity(r),r.technician,r.os_number,r.validated_code].join("\t")).join("\n")));
  $("backlogUpload").addEventListener("click",()=>action($("backlogUpload"),async()=>{
    const chosen=[...$("backlogRouteFiles").files];
    if(!chosen.length||chosen.length>5)throw Error("Selecione de 1 a 5 planilhas");
    const files=[];
    for(const file of chosen){
      if(!/\.(csv|xlsx)$/i.test(file.name)||file.size>3*1024*1024)throw Error("Formato/tamanho inválido: "+file.name);
      const result=await new Promise((resolve,reject)=>{
        const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error("Falha na leitura"));reader.readAsDataURL(file);
      });
      files.push({name:file.name,base64:result.split(",")[1]});
    }
    const r=await post("/api/backlog/year/routes",{files});
    comparisonReady=false;comparison=[];renderHistoricalReport();
    update($("backlogUploadStatus"),"Rotas: "+r.files.map(x=>x.filename+" ("+x.rows+" O.S.)").join("; ")+
      ". Clique em Analisar arquivos para gerar o relatório do grupo.");
    await loadDailyTreatment();
  },$("backlogUploadStatus")));
  $("backlogCompare").addEventListener("click",()=>action($("backlogCompare"),async()=>{
    const codes=[...root.querySelectorAll("[data-backlog-code]:checked")].map(x=>x.dataset.backlogCode);
    if(!codes.length)throw Error("Selecione pelo menos um código histórico");
    const r=await call("/api/backlog/year/compare?limit=1000&codes="+encodeURIComponent(codes.join(",")));
    comparison=r.rows||[];
    comparisonTruncated=Boolean(r.truncated||r.route_total>comparison.length);
    reportCodes=codes;
    comparisonReady=true;
    renderHistoricalReport();
    update($("backlogUploadStatus"),comparison.length+" atividades analisadas. "+
      (comparisonTruncated?"Relatório acima do limite; cópia bloqueada.":"Relatório pronto para WhatsApp."));
    root.querySelector('[data-backlog-tab="result"]').click();
  },$("backlogUploadStatus")));
  $("backlogCopyResult").addEventListener("click",()=>{
    if(!reportApi||!comparisonReady||comparisonTruncated)return;
    copy(reportApi.toWhatsApp(reportApi.build(comparison,cityScope(),reportCodes)));
  });
  $("backlogFindOffRoute").addEventListener("click",()=>action($("backlogFindOffRoute"),async()=>{
    currentProfile=$("backlogOffRouteProfile").value;
    const r=await call("/api/backlog/year/fora-rota?profile="+encodeURIComponent(currentProfile)+"&limit=150");candidates=r.candidates||[];
    table($("backlogOffRouteResult"),[["Contrato","contract"],["Data","activity_date"],["O.S.","os_number"],["Código","code"],["Serviço","service"]],candidates,async(item,btn)=>{
      btn.disabled=true;
      try{const v=await post("/api/backlog/year/sent",{profile:currentProfile,contract:item.contract,note:"Registro manual no painel"});btn.textContent=v.ok?"Registrado":"Erro";}
      catch(e){btn.disabled=false;btn.textContent="Repetir";update($("backlogSyncStatus"),e.message);}
    });
  }));
  $("backlogCopyOffRoute").addEventListener("click",()=>copy(candidates.map(r=>"Contrato "+r.contract+" • O.S. "+r.os_number+" • "+r.code+" ("+r.activity_date+")").join("\n")));
  $("backlogRefreshSent").addEventListener("click",()=>action($("backlogRefreshSent"),async()=>{
    const r=await call("/api/backlog/year/sent");
    table($("backlogSentResult"),[["Base","profile"],["Contrato","contract"],["Enviado","sent_at"],["Observação","note"]],r.rows||[]);
  }));
  for(const tab of root.querySelectorAll("[data-backlog-tab]")){
    tab.addEventListener("click",()=>{
      const selected=tab.dataset.backlogTab;
      for(const btn of root.querySelectorAll("[data-backlog-tab]"))btn.classList.toggle("active",btn===tab);
      for(const pane of root.querySelectorAll("[data-backlog-pane]"))pane.classList.toggle("hidden",pane.dataset.backlogPane!==selected);
      if(selected==="sent")$("backlogRefreshSent").click();
      if(selected==="daily")loadDailyTreatment().catch(()=>{});
    });
  }
  document.addEventListener("dominium:module-change",event=>{
    if(event.detail?.module==="backlog"){
      refreshStatus();pollToaRoutes();loadDailyTreatment().catch(()=>{});
    }
  });
  refreshStatus();
  // On a hard reload the Backlog workspace can already be selected. The
  // module-change event then does not fire, so restore the persisted route
  // state explicitly. This GET reads the sidecar DB; it does not query TOA.
  pollToaRoutes();
  setInterval(()=>{if(!root.classList.contains("hidden")&&lastRunning)refreshStatus();},5000);
  setInterval(()=>{if(!root.classList.contains("hidden")&&routeImportActive)pollToaRoutes();},5000);
})();