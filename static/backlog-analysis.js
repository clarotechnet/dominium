/* DOMINIUM > Recursos > Análise Backlog. Existing request() adds CSRF/session. */
(() => {
  "use strict";
  const root = document.querySelector("#backlogWorkspace");
  if (!root) return;
  const $ = (id) => root.querySelector("#" + id);
  let comparison = [], candidates = [], currentProfile = "natal", busy = false, lastRunning = false;
  let autoFill = false, nextCycleScheduled = false;
  const call = (path, opts={}) => request(apiUrl(path), {timeoutMs:120000,...opts});
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
  async function refreshStatus(){
    try{
      const s=await call("/api/backlog/year/status"),run=s.run||null;
      const info=run ? [run.status,run.done_tasks+"/"+run.total_tasks+" dias",run.imported+" O.S. confirmadas",run.unconfirmed+" sem código"].join(" • ") : "Nenhuma consulta executada";
      update($("backlogSyncStatus"),"Histórico: "+(s.history.confirmed||0)+" confirmadas, "+(s.history.missing_code||0)+" sem código. "+info);
      const view=$("backlogProgress");view.replaceChildren();
      for(const [key,label] of Object.entries({natal:"Natal/Parnamirim",fortaleza:"Fortaleza",mossoro:"Mossoró",recife:"Recife"})){
        const span=document.createElement("span");span.textContent=label+": "+((s.checkpoints||{})[key]||"a iniciar");view.append(span);
      }
      if(run?.error){const p=document.createElement("p");p.textContent=run.error;p.className="backlog-warning";view.append(p);}
      $("backlogRun").disabled=Boolean(s.running);$("backlogPilot").disabled=Boolean(s.running);$("backlogPause").disabled=!s.running;lastRunning=Boolean(s.running);
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
  async function action(button,handler,out=$("backlogSyncStatus")){
    if(busy)return;busy=true;button.disabled=true;
    try{await handler();}catch(e){update(out,"Erro: "+e.message);}
    finally{busy=false;await refreshStatus();}
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
    update($("backlogUploadStatus"),"Rotas: "+r.files.map(x=>x.filename+" ("+x.rows+" O.S.)").join("; "));
  },$("backlogUploadStatus")));
  $("backlogCompare").addEventListener("click",()=>action($("backlogCompare"),async()=>{
    const r=await call("/api/backlog/year/compare?limit=300");
    const chosen=new Set([...root.querySelectorAll("[data-backlog-code]:checked")].map(x=>x.dataset.backlogCode));
    comparison=(r.rows||[]).map(row=>{
      const code=String(row.historical_code||"");
      return {...row,classification:!code ? "NÃO CONFIRMADO" : chosen.has(code) ? "SEGURAR" : "OUTRO HISTÓRICO"};
    });
    const counts={SEGURAR:0,"OUTRO HISTÓRICO":0,"NÃO CONFIRMADO":0};
    for(const row of comparison)counts[row.classification]++;
    const metrics=$("backlogMetrics");metrics.replaceChildren();
    for(const [label,count] of Object.entries(counts)){
      const span=document.createElement("span");span.textContent=label+": "+count;metrics.append(span);
    }
    comparison.sort((a,b)=>a.classification.localeCompare(b.classification)||
      a.city.localeCompare(b.city)||a.technician.localeCompare(b.technician));
    table($("backlogResult"),[["Análise","classification"],["Contrato","contract"],["Cidade","city"],["Recurso","technician"],["Bairro","bairro"],["Janela","window"],["Código","historical_code"],["Data","historical_date"]],comparison);
    update($("backlogUploadStatus"),comparison.length+" itens exibidos. Histórico parcial não prova ausência de baixa.");
  },$("backlogUploadStatus")));
  $("backlogCopyResult").addEventListener("click",()=>copy(comparison.map(r=>[r.contract,r.city,r.technician,r.historical_code||"NÃO CONFIRMADO",r.classification].join("\t")).join("\n")));
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
    });
  }
  document.addEventListener("dominium:module-change",event=>{if(event.detail?.module==="backlog")refreshStatus();});
  refreshStatus();
  setInterval(()=>{if(!root.classList.contains("hidden")&&lastRunning)refreshStatus();},5000);
})();