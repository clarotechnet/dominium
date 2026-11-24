/* Lista explicita de contratos: sem varredura geral, sem fallback DataSnap. */
(function(root) {
  "use strict";
  const MAX = 50;
  const PREFIXES = { natal:["NTL","PWM"] };
  function parseContracts(raw) {
    const tokens = String(raw || "").trim().split(/[\s,;]+/).filter(Boolean);
    const invalid = tokens.filter(value => !/^\d{5,18}$/.test(value));
    const contracts = [...new Set(tokens.filter(value => /^\d{5,18}$/.test(value)))];
    if (invalid.length) throw Error("Use somente numeros de contrato separados por virgula, espaco ou linha.");
    if (!contracts.length || contracts.length > MAX) throw Error("Informe de 1 a " + MAX + " contratos distintos.");
    return contracts;
  }
  function canonical(value) {return String(value || "").trim().toUpperCase().replace(/_/g,"-").replace(/\s+/g,"");}
  function isAdhesionBucket(profile, value) {
    return (PREFIXES[profile] || []).some(prefix => canonical(value) === prefix+"-DMV");
  }
  function importBucket(order, scope, capture) {
    const source=String(order?.import_scope?.source_file||"").split(/[\\/]/).pop();
    const parts=source.match(/^Atividades-(NTL|PWM)-DMV_(\d{2})_(\d{2})_(\d{2})(?:\s*\(\d+\))?\.(?:csv|xlsx)$/i);
    const expected=scope.date.split("-");
    if(!parts || parts[2]!==expected[2] || parts[3]!==expected[1] || parts[4]!==expected[0].slice(-2))return "";
    const identity=order.operation_identity;
    if(order.operation_source!=="toa_import" || order.import_scope.expected_profile_key!==scope.profile ||
       !order.import_scope.source_hash || identity?.profile_key!==scope.profile ||
       String(identity.contract)!==scope.contract || String(identity.activity_id)!==String(capture.aid))return "";
    return parts[1].toUpperCase()+"-DMV";
  }
  function codeOnly(service) {
    const s=String(service||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase();
    return s.includes("ASSINATURA") || /INST(?:ALACAO)?\.?\s+GPON\s*-\s*INST(?:ALACAO)?\.?\s+CABO/.test(s);
  }
  function materialAudit(preparation) {
    if(!preparation || typeof preparation!=="object") return "";
    const label=rows=>(Array.isArray(rows)?rows:[]).map(row=>String(row.requested_code||row.code||row.requested_codes?.join("/")||"codigo nao informado")).join(", ");
    const parts=[];
    const omitted=label(preparation.discarded_shortfalls),partial=label(preparation.partial_shortfalls);
    if(omitted)parts.push("Sem saldo (dispensadas): "+omitted);
    if(partial)parts.push("Quantidade limitada ao saldo: "+partial);
    if(preparation.transferred)parts.push("Complemento pelo RETORNO");
    if(preparation.fallback_removed_after_rejection?.length)parts.push("Itens retirados apos rejeicao confirmada: "+preparation.fallback_removed_after_rejection.join(", "));
    return parts.join("; ");
  }
  function selectCandidates(payload, active, scope, deps) {
    const {profile,contract,date}=scope;
    if(profile!=="natal") throw Error("Lote exclusivo da base Natal/Parnamirim.");
    if(payload.ok===false || payload.profile!==profile || String(payload.resolved_contract||payload.contract||"")!==contract || payload.query_type==="os") throw Error("Contrato ou cidade divergente no TOA.");
    const rows=active.filter(o=>String(o.contract)===contract);
    if(!rows.length) return [];
    const byNumber=new Map();
    for(const row of rows) {
      const os=String(row.num_os||"");
      if(!os || byNumber.has(os)) throw Error("OS duplicada ou sem numero no Imperium.");
      byNumber.set(os,row);
    }
    const candidates=[], seen=new Set();
    for(const capture of payload.results||[]) {
      const matching=(capture.tasks||[]).filter(t=>byNumber.has(String(t.os_number||"")));
      if(!matching.length) continue;
      const legacyValidated=capture.decision==null && capture.found===true &&
        Array.isArray(capture.validation_errors) && capture.validation_errors.length===0 &&
        Array.isArray(capture.operation_blockers) && capture.operation_blockers.length===0;
      if(String(capture.contract)!==contract || !capture.aid || !deps.complete(capture.activity_status) ||
         (capture.decision!=="candidate_after_validation" && !legacyValidated) || capture.materials_complete===false ||
         (capture.validation_errors||[]).length || (capture.operation_blockers||[]).length) throw Error("Atividade incompleta ou bloqueada no TOA.");
      const rawDate=String(capture.scheduled_date||"").slice(0,10);
      const normalizedDate=/^\d{2}\/\d{2}\/\d{4}$/.test(rawDate)?rawDate.split("/").reverse().join("-"):rawDate;
      if(normalizedDate!==date) throw Error("Data do TOA divergente da data selecionada.");
      const explicit=canonical(capture.bucket || capture.route || "");
      const provider=canonical(deps.route(capture.route_provider));
      const route=explicit || (/^(?:NTL|PWM|FTZ|JCR|MRO)-DMV(?:-|$)/.test(provider)?provider:"");
      if(route && !isAdhesionBucket(profile,route)) throw Error("Bucket de adesao nao confirmado; nenhuma OS deste contrato sera enviada.");
      for(const task of matching) {
        const os=String(task.os_number), activeOrder=byNumber.get(os);
        const exact=(capture.imperium_matches||[]).filter(o=>String(o.num_os)===os && String(o.contract)===contract && Number(o.id_os)===Number(activeOrder.id_os));
        if(seen.has(os) || exact.length!==1 || !deps.valid(exact[0],capture) || !deps.executed(task.status)) throw Error("OS sem correspondencia unica, aprovada e executada: "+os);
        const code=String(task.close_code||"").trim();
        if(!code || code==="430" || !deps.knownCode(code)) throw Error("Codigo de baixa ausente ou invalido: "+os);
        const order=exact[0], service=String(order.service||"");
        const origin=importBucket(order,scope,capture);
        if(!route && !isAdhesionBucket(profile,origin)) throw Error("Bucket de origem sem comprovacao no arquivo de importacao.");
        if(order.operation_source==="toa_import" && !isAdhesionBucket(profile,origin)) throw Error("Escopo de importacao fora de adesao.");
        if(route && origin && route!==origin) throw Error("Bucket TOA diverge da origem importada.");
        if(!service || /DESCONEX|RETIRADA\s+DE\s+ASSINATURA/i.test(service)) throw Error("Servico fora do escopo de adesao: "+os);
        seen.add(os);
        candidates.push({capture,task:{...task,close_code:code},order,numOs:os,code,isDisconnect:false,batchAdhesion:true,batchScope:{profile,date,epoch:scope.epoch},batchCodeOnly:codeOnly(service)});
      }
    }
    if(seen.size!==byNumber.size) throw Error("Nem todas as OS em campo foram conciliadas com o TOA.");
    // If a productive companion already left the field, the remaining OS
    // cannot safely claim the activity's shared stock a second time.
    for(const candidate of candidates) {
      if(candidate.batchCodeOnly)continue;
      const capture=candidate.capture;
      const activeTasks=new Set(candidates.filter(c=>c.capture.aid===capture.aid).map(c=>c.numOs));
      for(const task of capture.tasks||[]) {
        const os=String(task.os_number||"");
        if(!os || activeTasks.has(os))continue;
        const other=(capture.imperium_matches||[]).find(o=>String(o.num_os)===os)
          || (capture.imperium_all_orders||[]).find(o=>String(o.num_os)===os);
        if(!other || !codeOnly(other.service))throw Error("Atividade com OS acompanhante fora de campo; risco de duplicar estoque.");
      }
    }
    deps.assign(candidates);
    const serials=new Set(), byActivity=new Map();
    for(const candidate of candidates) {
      if(candidate.batchCodeOnly) continue;
      const activitySerials=byActivity.get(candidate.capture.aid)||new Set();
      byActivity.set(candidate.capture.aid,activitySerials);
      const plan=deps.equipment(candidate);
      if(plan.error || plan.correction) throw Error("Equipamentos exigem tratativa: "+candidate.numOs);
      const expected=deps.expectedType?.(candidate.order.service);
      if(expected && deps.productive?.(candidate.code) && !plan.installed.some(item=>item.type===expected || (expected==="decoder" && item.type==="smart"))) {
        throw Error("Serial obrigatorio nao conciliado para OS "+candidate.numOs+" ("+expected+").");
      }
      for(const item of [...plan.installed,...plan.removed]) {
        const key=String(item.serial||"").replace(/[^A-Z0-9]/gi,"").toUpperCase();
        if(!key || serials.has(key)) throw Error("Serial ausente ou repetido no contrato: "+candidate.numOs);
        serials.add(key);activitySerials.add(key);
      }
    }
    // Uma atividade com diversas OS nao pode perder itens por alocacao automatica.
    const groups=new Map();
    for(const candidate of candidates) {
      const group=groups.get(candidate.capture.aid)||[];
      group.push(candidate);groups.set(candidate.capture.aid,group);
    }
    for(const group of groups.values()) {
      const capture=group[0].capture;
      if(group.every(c=>c.batchCodeOnly)) continue;
      const expected=[...(capture.installed_equipment||[]),...(capture.removed_equipment||[])];
      for(const item of expected) {
        const key=String(item.serial||"").replace(/[^A-Z0-9]/gi,"").toUpperCase();
        if(!key || !byActivity.get(capture.aid)?.has(key)) throw Error("Inventario TOA sem alocacao segura em OS.");
      }
      const materials=deps.materials(capture.materials);
      if(materials.length && !group.some(c=>!c.batchCodeOnly && c.materialOwner && (!deps.allowsMaterials || deps.allowsMaterials(c.code)))) throw Error("Miscelaneas TOA sem OS responsavel.");
    }
    // Movimentacao principal antes de acompanhantes; confirmar antes da proxima OS do contrato.
    return candidates.sort((a,b)=>Number(b.materialOwner)-Number(a.materialOwner));
  }
  async function runBatch(contracts, hooks) {
    for(const contract of contracts) {
      if(!hooks.active()) break;
      hooks.update(contract,"Consultando","Conferindo TOA e Imperium");
      try {
        const candidates=await hooks.prepare(contract);
        if(!hooks.active()) break;
        if(!candidates.length) {hooks.update(contract,"Sem OS em campo","Nenhuma baixa enviada.");continue;}
        let confirmed=0, waiting=0, blocked=0, reason=""; const audits=[];
        for(const candidate of candidates) {
          if(!hooks.active()) break;
          hooks.update(contract,"Executando","OS "+candidate.numOs+" ("+candidate.code+")");
          const res=await hooks.send(candidate);
          if(res.reason || res.error) reason=String(res.reason || res.error).slice(0,240);
          const audit=materialAudit(res.materialPreparation);
          if(audit)audits.push("OS "+candidate.numOs+": "+audit);
          if(res.closed) {confirmed++;continue;}
          if(res.pending && res.requestId) {
            hooks.update(contract,"Aguardando confirmacao","OS "+candidate.numOs+" enviada uma vez. "+audit);
            const result=await hooks.confirm(res.requestId,candidate);
            if(result==="confirmed") {confirmed++;continue;}
            if(result==="pending") waiting++; else blocked++;
          } else {blocked++;}
          // Nao movimentar OS acompanhantes se o primeiro envio esta incerto.
          break;
        }
        const rest=candidates.length-confirmed-waiting-blocked;
        const detail=confirmed+" confirmada(s), "+waiting+" pendente(s), "+blocked+" em tratativa, "+rest+" nao enviada(s)."+(reason?" "+reason:"")+(audits.length?" "+audits.join(" | "):"");
        hooks.update(contract,confirmed===candidates.length?"Baixado":waiting?"Aguardando confirmacao":blocked?"Tratativa":"Interrompido",detail);
      } catch(err) {hooks.update(contract,"Tratativa",String(err.message||err).slice(0,300));}
    }
  }
  if(typeof module!=="undefined" && module.exports){module.exports={parseContracts,isAdhesionBucket,codeOnly,materialAudit,selectCandidates,runBatch};return;}
  const panel=document.getElementById("adhesionBatch");
  if(!panel)return;
  const input=document.getElementById("adhesionBatchInput"),start=document.getElementById("adhesionBatchStart"),
    stop=document.getElementById("adhesionBatchStop"),status=document.getElementById("adhesionBatchStatus"),list=document.getElementById("adhesionBatchResults");
  let stopped=false, rows=new Map();
  function busy(){return state.adhesionBatchRunning || state.semiAutoRunning || state.semiAutoWorker || state.semiAutoRefreshing || state.semiAutoPendingConfirmationWorker || state.toaLiveLoading || state.running || state.loading || state.disconnectAutomationWorker;}
  function render() {
    start.disabled=Boolean(busy() || state.profile!=="natal");stop.disabled=!state.adhesionBatchRunning;input.disabled=!!state.adhesionBatchRunning;
    const all=[...rows.values()], finished=all.filter(r=>!["Na fila","Consultando","Executando"].includes(r.label)).length;
    if(all.length) status.textContent=finished+" / "+all.length+" contratos | "+all.filter(r=>r.label==="Baixado").length+" baixados";
    list.replaceChildren(...all.map(r=>{
      const node=document.createElement("div");node.className="adhesion-batch-result";
      for(const value of [r.contract,r.label,r.detail]){const el=document.createElement("span");el.textContent=value;node.append(el);}
      return node;
    }));
  }
  function update(contract,label,detail){rows.set(contract,{contract,label,detail});render();}
  stop.addEventListener("click",()=>{stopped=true;status.textContent="Parando apos a solicitacao atual; nao sera reenviada.";});
  start.addEventListener("click",async()=>{
    if(busy()) return;
    let contracts;
    try{contracts=parseContracts(input.value);}catch(err){status.textContent=err.message;return;}
    if(!state.authUser || !["admin","controller"].includes(state.authUser.role) || !state.officialCloseEnabled || !state.closeEnabled){status.textContent="Baixa oficial indisponivel para esta sessao/cidade.";return;}
    if(!state.toaLiveStatus?.connected || !state.toaLiveStatus?.authenticated){status.textContent="Ponte TOA desconectada.";return;}
    const profile=state.profile,epoch=state.profileEpoch,date=elements.date.value;
    if(profile!=="natal" || !/^\d{4}-\d{2}-\d{2}$/.test(date)){status.textContent="Selecione cidade e data validas.";return;}
    state.adhesionBatchRunning=true;stopped=false;
    rows=new Map(contracts.map(contract=>[contract,{contract,label:"Na fila",detail:"Aguardando"}]));
    render();renderToaLiveStatus();
    const active=()=>!stopped && state.profile===profile && state.profileEpoch===epoch && elements.date.value===date && state.officialCloseEnabled && state.closeEnabled;
    try {
      await runBatch(contracts,{
        active,update,
        async prepare(contract) {
          const path="/api/orders?date="+encodeURIComponent(date)+"&status=field&service_type=all";
          const orders=await request(apiUrlForProfile(path,profile),{timeoutMs:180000});
          if(!active() || orders.stale || !Array.isArray(orders.orders)) throw Error("Lista Imperium indisponivel ou desatualizada.");
          if(!orders.orders.some(o=>String(o.contract)===contract)) return [];
          const payload=await request(apiUrlForProfile("/api/toa-live/lookup",profile),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query:contract,expected_profile_key:profile,expected_date:date}),timeoutMs:300000});
          if(!active()) throw Error("Cidade/data alterada; fila interrompida.");
          return selectCandidates(payload,orders.orders,{profile,contract,date,epoch},{
            complete:disconnectActivityComplete,executed:disconnectTaskExecuted,route:automationProviderLabel,
            valid:validToaCloseSnapshot,knownCode:code=>state.closeCodes.some(c=>c.code===code),
            assign:semiAutoAssignMaterialOwners,equipment:semiAutoCandidateEquipmentPlan,materials:toaLiveMaterialsDraft,allowsMaterials:closeCodeAllowsMaterials,expectedType:expectedEquipmentType,productive:code=>Boolean(state.closeCodes.find(c=>c.code===code)?.productive)
          });
        },
        async send(candidate) {
          // A previously accepted/uncertain order is not submitted again.
          const report=await request(apiUrlForProfile("/api/close-report?date="+encodeURIComponent(date),profile),{timeoutMs:60000});
          if(!active() || !Array.isArray(report.records)) throw Error("Relatorio de baixa indisponivel.");
          const previous=report.records.find(r=>String(r.id_os)===String(candidate.order.id_os) &&
            (["sending","pending","uncertain","confirmed"].includes(String(r.state)) || (r.state==="failed" && r.safe_to_retry!==true)));
          if(previous){
            if(previous.state==="confirmed")return {closed:true};
            return {humanReview:true,reason:"OS possui tentativa anterior sem liberacao para reenvio."};
          }
          if(!active()) throw Error("Lote interrompido.");
          return processAutoCloseCandidate(candidate,profile);
        },
        async confirm(requestId) {
          for(let attempt=0;attempt<12;attempt++){
            if(!active()) return "pending";
            await sleep(10000);
            if(!active()) return "pending";
            try{
              const report=await request(apiUrlForProfile("/api/close-report?date="+encodeURIComponent(date),profile),{timeoutMs:60000});
              const row=(report.records||[]).find(r=>String(r.request_id)===requestId);
              if(row?.state==="confirmed")return "confirmed";
              if(["failed","uncertain"].includes(row?.state))return "review";
            }catch{/* consultar novamente, nunca repetir a escrita */}
          }
          return "pending";
        }
      });
    } finally {
      state.adhesionBatchRunning=false;
      for(const row of rows.values())if(["Na fila","Consultando","Executando"].includes(row.label)){row.label="Interrompido";row.detail="Nenhuma nova solicitacao sera enviada.";}
      render();renderSemiAutoQueue();
    }
  });
  root.dominiumRenderAdhesionBatch=render;
  render();
})(globalThis);
