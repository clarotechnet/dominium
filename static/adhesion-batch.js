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
  // The operational endpoint returns HTTP 200 + stale=true (or 409)
  // while its shared lock is held. Only retry reads, never a close.
  class FreshOrdersBusyError extends Error {}
  class ToaBridgeUnavailableError extends Error {}

  async function freshOrders(read, {active,wait,notify=()=>{},attempts=4,delay=1500,budgetMs=15000,now=Date.now}) {
    const deadline=now()+budgetMs;
    for(let attempt=1;attempt<=attempts;attempt++){
      if(!active())throw Error("Lote interrompido.");
      const remaining=deadline-now();
      if(remaining<=0)break;
      let payload;
      try {payload=await read(remaining);}
      catch(err){if(err.status!==409)throw err;}
      if(!active())throw Error("Lote interrompido.");
      if(payload && payload.stale!==true && Array.isArray(payload.orders))return payload;
      if(payload && payload.stale!==true)throw Error("Resposta invalida da lista Imperium.");
      if(attempt===attempts || deadline-now()<=delay)break;
      notify(attempt,attempts);
      await wait(delay);
    }
    throw new FreshOrdersBusyError("Imperium ocupado: nao foi possivel obter lista atualizada no tempo da fila.");
  }
  async function readBatchToa(read, {active,wait,notify}) {
    const retryDelays = [1000, 3000, 5000];
    for (let attempt = 0; attempt <= retryDelays.length; attempt++) {
      if (!active()) throw Error("Lote interrompido.");
      try {
        return await read();
      } catch (error) {
        if (error.status !== 502 || error.message !== "TOA secundario nao localizado") throw error;
        if (!active()) throw Error("Lote interrompido.");
        if (attempt === retryDelays.length) break;
        notify();
        await wait(retryDelays[attempt]);
      }
    }
    throw new ToaBridgeUnavailableError("A ponte do TOA nao respondeu. Nenhuma baixa foi enviada nesta tentativa.");
  }
  async function ordersForBatchContract(payload, contract, readFresh) {
    const orders=payload.imperium_all_orders;
    if(payload.imperium_refresh?.refreshed===true && Array.isArray(orders) &&
       orders.every(order=>order?.contract && order.status)) {
      // This snapshot establishes which OS are still in the field. Only
      // refreshCandidate can authorize a send using a fresh field-list row.
      return orders.filter(order=>String(order.contract)===contract && String(order.status).trim().toUpperCase()==="EM CAMPO");
    }
    return (await readFresh()).orders;
  }
  function serviceLabel(service) {
    return String(service||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase();
  }
  function codeOnly(service) {
    const s=serviceLabel(service);
    return s.includes("ASSINATURA") || /INST(?:ALACAO)?\.?\s+GPON\s*-\s*INST(?:ALACAO)?\.?\s+CABO/.test(s) || /INSTALACAO (?:DE )?CABO GPON/.test(s);
  }
  function refreshCandidate(candidate, orders, valid) {
    const previous=candidate.order, scope=candidate.batchScope;
    const matches=orders.filter(o=>String(o.num_os)===String(previous.num_os) && String(o.id_os)===String(previous.id_os) && String(o.contract)===String(previous.contract));
    if(matches.length!==1) throw Error("OS nao esta mais em campo ou mudou de identidade: "+candidate.numOs);
    const current=matches[0];
    const identityKeys=["profile_key","contract","activity_id","city","project_id"];
    if(!valid(current,candidate.capture) || current.operation_source!==previous.operation_source ||
       String(current.service)!==String(previous.service) ||
       identityKeys.some(k=>String(current.operation_identity?.[k]||"")!==String(previous.operation_identity?.[k]||"")) ||
       current.import_scope?.source_hash!==previous.import_scope?.source_hash ||
       (current.operation_source==="toa_import" && !importBucket(current,{...scope,contract:String(current.contract)},candidate.capture))) {
      throw Error("Escopo da OS mudou; nenhuma baixa enviada: "+candidate.numOs);
    }
    return {...candidate,order:current};
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
  function isUnresolvedClose(record) {
    return ["sending","pending","uncertain"].includes(record.state);
  }
  function priorCloseOutcome(record, failures=[]) {
    if(record.state==="confirmed") return {closed:true};
    const os="OS "+record.num_os+(record.close_code?" ("+record.close_code+")":"");
    // The legacy observer can overwrite an uncertain stock result with a
    // sending state. The day failure log retains the stock failure instead.
    const stockFailure=!record.accepted_at && !record.official_http_status && failures.find(f=>String(f.id_os)===String(record.id_os) &&
      String(f.num_os)===String(record.num_os) && String(f.contract)===String(record.contract) &&
      String(f.close_code)===String(record.close_code) &&
      /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(String(f.last_at||"")) &&
      /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(String(record.created_at||"")) &&
      f.last_at.slice(0,19)>=record.created_at.slice(0,19) &&
      /complemento das miscelaneas ficou incerto.*a baixa da os nao foi enviada/i.test(String(f.error||"")));
    if(record.category==="MATERIAL_TRANSFER_UNCERTAIN" || stockFailure) {
      return {
        reason:os+": "+String(stockFailure?.error||record.message||"Complemento de estoque sem confirmacao. A baixa da OS nao foi enviada."),
        stockRetryRequestId:isUnresolvedClose(record) && !record.accepted_at && !record.official_http_status
          ? String(record.request_id||"") : "",
      };
    }
    if(isUnresolvedClose(record)) return {pending:true,reason:os+" possui tentativa anterior sem confirmacao no Imperium."};
    return {reason:os+" possui tentativa anterior sem liberacao para reenvio."};
  }
  // One physical EMTA can support both Virtua and VoIP. Only an exact
  // completed activity with both tasks in field may use this rule.
  function applySharedEmtaRule(candidates, deps) {
    const groups=new Map();
    for(const c of candidates){const group=groups.get(c.capture.aid)||[];group.push(c);groups.set(c.capture.aid,group);}
    const kind=c=>serviceLabel(c.order.service).replace(/[^A-Z0-9]+/g," ").trim().replace(/^\d+ /,"");
    for(const group of groups.values()){
      const virtua=group.filter(c=>kind(c)==="ADESAO INSTALAR PONTO VIRTUA");
      const voip=group.filter(c=>kind(c)==="ADESAO INSTALAR PONTO VOIP");
      if(virtua.length!==1 || voip.length!==1)continue;
      const capture=virtua[0].capture;
      if(!deps.equipmentType || !group.every(c=>c.capture===capture))continue;
      const chip=group.filter(c=>kind(c)==="ENVIO DE CHIP VIA TECNICO");
      const allowed=group.every(c=>c===virtua[0]||c===voip[0]||chip.includes(c)||kind(c)==="ADESAO INSTALACAO DE ASSINATURA");
      const installed=capture.installed_equipment, removed=capture.removed_equipment;
      if(!allowed || chip.length>1 || !Array.isArray(installed) || !Array.isArray(removed) || removed.length)continue;
      if(virtua[0].code!=="409" || voip[0].code!=="409" || chip.some(c=>c.code!=="706"))continue;
      const bySerial=new Map();
      for(const item of installed){
        const serial=String(item.serial||"").replace(/[^A-Z0-9]/gi,"").toUpperCase();
        const type=deps.equipmentType(item);
        if(!serial || !["emta","chip"].includes(type) || (bySerial.has(serial)&&bySerial.get(serial)!==type))throw Error("Inventario Virtua/VoIP sem identidade segura.");
        bySerial.set(serial,type);
      }
      const emtas=[...bySerial].filter(([,type])=>type==="emta");
      const chips=[...bySerial].filter(([,type])=>type==="chip");
      if(emtas.length>1)throw Error("Virtua/VoIP com EMTAs distintos: confirmar vinculo por OS/ponto antes de movimentar.");
      if(emtas.length!==1 || chips.length!==chip.length)continue;
      voip[0].batchCodeOnly=true;
      voip[0].batchSharedEmta=true;
    }
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
    const candidates=[], seen=new Set(), imperiumOnly=new Set();
    for(const capture of payload.results||[]) {
      const matching=(capture.tasks||[]).filter(task=>{
        const os=String(task.os_number||"");
        if(!byNumber.has(os)) return false;
        if(task.imperium_only===true || task.source==="imperium_contract_status") {
          imperiumOnly.add(os);
          return false;
        }
        return true;
      });
      if(!matching.length) continue;
      const legacyValidated=capture.decision==null && capture.found===true &&
        Array.isArray(capture.validation_errors) && capture.validation_errors.length===0 &&
        Array.isArray(capture.operation_blockers) && capture.operation_blockers.length===0;
      const captureIssues=[];
      if(String(capture.contract)!==contract)captureIssues.push("contrato divergente");
      if(!capture.aid)captureIssues.push("ID da atividade ausente");
      if(!deps.complete(capture.activity_status))captureIssues.push("status da atividade: "+String(capture.activity_status||"nao informado").slice(0,80));
      if(capture.decision!=="candidate_after_validation" && !legacyValidated)captureIssues.push("decisao: "+String(capture.decision||"nao validada").slice(0,80));
      if(capture.materials_complete===false)captureIssues.push("captura de materiais incompleta");
      if((capture.validation_errors||[]).length)captureIssues.push("erros de validacao: "+capture.validation_errors.length);
      if((capture.operation_blockers||[]).length)captureIssues.push("bloqueios operacionais: "+capture.operation_blockers.length);
      if(captureIssues.length)throw Error("Atividade incompleta ou bloqueada no TOA. OS "+matching.map(t=>String(t.os_number)).join(", ")+": "+captureIssues.join("; ")+". Nenhuma baixa enviada.");
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
    if(seen.size!==byNumber.size) {
      const missing=[...byNumber.keys()].filter(os=>!seen.has(os));
      const displayed=missing.filter(os=>imperiumOnly.has(os));
      const independent = candidates.filter(candidate => candidate.batchCodeOnly);
      if (deps.hold && displayed.length === missing.length && independent.length) {
        deps.hold([
          ...displayed.map(os => "OS " + os + " sem codigo de baixa confirmado no TOA"),
          ...candidates.filter(candidate => !candidate.batchCodeOnly).map(candidate =>
            "OS " + candidate.numOs + " retida para conciliar os itens da atividade"),
        ]);
        return independent;
      }
      if(displayed.length) throw Error("OS "+displayed.join(", ")+" nao localizada no TOA; codigo de baixa nao confirmado.");
      throw Error("OS em campo sem conciliacao no TOA: "+missing.join(", ")+".");
    }
    // If a productive companion already left the field, the remaining OS
    // cannot safely claim the activity's shared stock a second time.
    for(const candidate of candidates) {
      if(candidate.batchCodeOnly)continue;
      const capture=candidate.capture;
      const activeTasks=new Set(candidates.filter(c=>c.capture.aid===capture.aid).map(c=>c.numOs));
      for(const task of capture.tasks||[]) {
        const os=String(task.os_number||"");
        if(!os || activeTasks.has(os))continue;
        if((task.imperium_only===true || task.source==="imperium_contract_status") && seen.has(os))continue;
        const other=(capture.imperium_matches||[]).find(o=>String(o.num_os)===os)
          || (capture.imperium_all_orders||[]).find(o=>String(o.num_os)===os);
        if(!other || !codeOnly(other.service))throw Error("Atividade com OS acompanhante fora de campo; risco de duplicar estoque.");
      }
    }
    applySharedEmtaRule(candidates,deps);
    deps.assign(candidates);
    const serials=new Set(), byActivity=new Map();
    for(const candidate of candidates) {
      if(candidate.batchCodeOnly) continue;
      const activitySerials=byActivity.get(candidate.capture.aid)||new Set();
      byActivity.set(candidate.capture.aid,activitySerials);
      const plan=deps.equipment(candidate);
      if(plan.error || plan.correction) throw Error("Equipamentos exigem tratativa: "+candidate.numOs);
      const expected=deps.expectedType?.(candidate.order.service);
      const {installed_equipment:installed,removed_equipment:removed}=candidate.capture;
      const service=serviceLabel(candidate.order.service).replace(/[^A-Z0-9]+/g," ").trim().replace(/^\d+ /,"");
      const keepsEquipment=service==="MUDANCA DE ENDERECO INSTALAR PONTO ADICIONAL VIRTUA" &&
        Array.isArray(installed) && installed.length===0 && Array.isArray(removed) && removed.length===0;
      if(expected && deps.productive?.(candidate.code) && !keepsEquipment && !plan.installed.some(item=>item.type===expected || (expected==="decoder" && item.type==="smart"))) {
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
    const queue = contracts.map(contract => ({contract, deferred: false}));
    for(const {contract, deferred} of queue) {
      if(!hooks.active()) break;
      hooks.update(contract,"Consultando","Conferindo TOA e Imperium");
      try {
        const prior=await hooks.priorContract?.(contract);
        if(!hooks.active()) break;
        if(prior) {
          hooks.update(contract,prior.pending?"Aguardando confirmacao":"Tratativa",prior.reason);
          continue;
        }
        const held = [];
        const candidates=await hooks.prepare(contract, reasons => held.push(...reasons));
        if(!hooks.active()) break;
        if(!candidates.length) {hooks.update(contract,"Sem OS em campo","Nenhuma baixa enviada.");continue;}
        let confirmed=0, waiting=0, blocked=0;
        const outcomes=[];
        for(const candidate of candidates) {
          if(!hooks.active()) break;
          const os="OS "+candidate.numOs+(candidate.code?" ("+candidate.code+")":"");
          hooks.update(contract,"Executando",os);
          let audit="", detail="", result="review";
          try {
            const res=await hooks.send(candidate);
            audit=materialAudit(res.materialPreparation);
            detail=String(res.reason || res.error || "").slice(0,240);
            if(res.closed) result="confirmed";
            else if(res.pending) {
              result="pending";
              if(res.requestId) {
                hooks.update(contract,"Aguardando confirmacao",os+" enviada uma vez. "+audit);
                result=await hooks.confirm(res.requestId,candidate);
              }
            }
          } catch(err) {
            if (err instanceof FreshOrdersBusyError && confirmed === 0 && outcomes.length === 0) throw err;
            detail=String(err.message || err).slice(0,240);
          }
          if(result==="confirmed") {
            confirmed++;
            outcomes.push([os+" confirmada no Imperium",audit].filter(Boolean).join(". "));
            continue;
          }
          if(result==="pending") waiting++; else blocked++;
          outcomes.push([os+(result==="pending"?" aguardando confirmacao":" em tratativa"),detail,audit].filter(Boolean).join(". "));
          // Nao movimentar OS acompanhantes se o primeiro envio esta incerto.
          break;
        }
        const rest=candidates.length-confirmed-waiting-blocked;
        const detail=confirmed+" confirmada(s), "+waiting+" pendente(s), "+(blocked+held.length)+" em tratativa, "+rest+" nao enviada(s). "+[...outcomes,...held].join(" | ");
        hooks.update(contract,waiting?"Aguardando confirmacao":blocked||held.length?"Tratativa":confirmed===candidates.length?"Baixado":"Interrompido",detail);
      } catch(err) {
        if ((err instanceof FreshOrdersBusyError || err instanceof ToaBridgeUnavailableError) && !deferred && hooks.active()) {
          queue.push({contract, deferred: true});
          hooks.update(contract, "Na fila", err instanceof ToaBridgeUnavailableError ? "Ponte TOA indisponivel. Nova consulta no fim do lote; nenhuma baixa enviada." : "Imperium ocupado. Nova consulta no fim do lote.");
        } else {
          hooks.update(contract, "Tratativa", String(err.message || err).slice(0, 300));
        }
      }
    }
  }
  if(typeof module!=="undefined" && module.exports){module.exports={parseContracts,isAdhesionBucket,codeOnly,materialAudit,selectCandidates,runBatch,freshOrders,readBatchToa,ordersForBatchContract,refreshCandidate,priorCloseOutcome};return;}
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
    const profile=state.profile,epoch=state.profileEpoch,date=elements.date.value;
    if(profile!=="natal" || !/^\d{4}-\d{2}-\d{2}$/.test(date)){status.textContent="Selecione cidade e data validas.";return;}
    state.adhesionBatchRunning=true;stopped=false;
    rows=new Map(contracts.map(contract=>[contract,{contract,label:"Na fila",detail:"Aguardando"}]));
    render();renderToaLiveStatus();
    const active=()=>!stopped && state.profile===profile && state.profileEpoch===epoch && elements.date.value===date && state.officialCloseEnabled && state.closeEnabled;
    const fieldPath="/api/orders?date="+encodeURIComponent(date)+"&status=field&service_type=all&wait_for_fresh=1";
    const readFieldOrders = (contract, detail) => {
      update(contract, "Consultando", detail);
      return freshOrders(
        timeoutMs => request(apiUrlForProfile(fieldPath, profile), {timeoutMs}),
        {active, wait: sleep, attempts: 1, budgetMs: 75000},
      );
    };
    const readCloseReport=()=>request(apiUrlForProfile("/api/close-report?date="+encodeURIComponent(date),profile),{timeoutMs:60000});
    let initialReport;
    async function outcomeFor(record) {
      if(!isUnresolvedClose(record) || record.category==="MATERIAL_TRANSFER_UNCERTAIN") return priorCloseOutcome(record);
      let failures=[];
      try {
        const report=await request(apiUrlForProfile("/api/failures",profile),{timeoutMs:10000});
        if(Array.isArray(report.failures)) failures=report.failures;
      } catch {/* Preserve the known block while the failure log is unavailable. */}
      return priorCloseOutcome(record,failures);
    }
    try {
      await runBatch(contracts,{
        active,update,
        async priorContract(contract) {
          try {initialReport ??= await readCloseReport();} catch {return null;}
          if(!Array.isArray(initialReport.records)) return null;
          for(const prior of initialReport.records.filter(r=>String(r.contract)===contract && isUnresolvedClose(r))) {
            const outcome=await outcomeFor(prior);
            if(!outcome.stockRetryRequestId) return outcome;
          }
        },
        async prepare(contract, hold) {
          const payload = await readBatchToa(
            () => request(apiUrlForProfile("/api/toa-live/lookup", profile), {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({query: contract, expected_profile_key: profile, expected_date: date}),
              timeoutMs: 300000,
            }),
            {active, wait: sleep, notify: () => update(contract, "Consultando", "Ponte do TOA aguardando resposta.")},
          );
          if(!active()) throw Error("Cidade/data alterada; fila interrompida.");
          const orders = await ordersForBatchContract(payload, contract, () =>
            readFieldOrders(contract, "Aguardando lista atualizada do Imperium."));
          return selectCandidates(payload,orders,{profile,contract,date,epoch},{
            complete:disconnectActivityComplete,executed:disconnectTaskExecuted,route:automationProviderLabel,hold,
            valid:validToaCloseSnapshot,knownCode:code=>state.closeCodes.some(c=>c.code===code),
            assign:semiAutoAssignMaterialOwners,equipment:semiAutoCandidateEquipmentPlan,materials:toaLiveMaterialsDraft,allowsMaterials:closeCodeAllowsMaterials,equipmentType:item=>toaLiveEquipmentType(item,true),expectedType:expectedEquipmentType,productive:code=>Boolean(state.closeCodes.find(c=>c.code===code)?.productive)
          });
        },
        async send(candidate) {
          // A previously accepted/uncertain order is not submitted again.
          const report=await readCloseReport();
          if(!active() || !Array.isArray(report.records)) throw Error("Relatorio de baixa indisponivel.");
          const previous=report.records.find(r=>String(r.id_os)===String(candidate.order.id_os) &&
            (isUnresolvedClose(r) || r.state==="confirmed" || (r.state==="failed" && r.safe_to_retry!==true)));
          const outcome=previous?await outcomeFor(previous):null;
          if(outcome && !outcome.stockRetryRequestId) return outcome;
          if(!active()) throw Error("Lote interrompido.");
          const fresh = await readFieldOrders(
            String(candidate.order.contract), "Atualizando aprovacao da OS " + candidate.numOs + ".",
          );
          const refreshed=refreshCandidate(candidate,fresh.orders,validToaCloseSnapshot);
          if(!active()) throw Error("Lote interrompido.");
          return processAutoCloseCandidate({...refreshed,stockRetryRequestId:outcome?.stockRetryRequestId},profile);
        },
        async confirm(requestId) {
          for(let attempt=0;attempt<12;attempt++){
            if(!active()) return "pending";
            await sleep(10000);
            if(!active()) return "pending";
            try{
              const report=await readCloseReport();
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
      renderToaLiveStatus();
    }
  });
  root.dominiumRenderAdhesionBatch=render;
  render();
})(globalThis);
