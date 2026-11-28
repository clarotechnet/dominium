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
  function liveBucket(capture, profile, providerLabel) {
    const routes = [capture.bucket, capture.route, capture.route_name].map(canonical).filter(Boolean);
    const provider = canonical(providerLabel(capture.route_provider));
    if (/^(?:NTL|PWM|FTZ|JCR|MRO|JPA)-DMV(?:-|$)/.test(provider)) routes.push(provider);
    if (routes.some(route => !isAdhesionBucket(profile, route) || route !== routes[0])) {
      throw Error("Bucket TOA divergente ou fora de adesao; nenhuma OS deste contrato sera enviada.");
    }
    return routes[0] || "";
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
  class ToaActivityScopeUnconfirmedError extends Error {}

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
    let activityUnconfirmed=false;
    for (let attempt = 0; attempt <= retryDelays.length; attempt++) {
      if (!active()) throw Error("Lote interrompido.");
      try {
        return await read();
      } catch (error) {
        activityUnconfirmed=[400,502].includes(error.status) && /\badhesion_activity_scope_unconfirmed\b/.test(error.message);
        const unavailable=error.status===502 && (error.message==="TOA secundario nao localizado"
          || /\btoa_resposta_busca_invalida\b/.test(error.message));
        if (!activityUnconfirmed && !unavailable) throw error;
        if (!active()) throw Error("Lote interrompido.");
        if (attempt === retryDelays.length) break;
        notify();
        await wait(retryDelays[attempt]);
      }
    }
    if(activityUnconfirmed) throw new ToaActivityScopeUnconfirmedError(
      "O TOA nao confirmou a atividade de adesao na data e na rota NTL/PWM. Nenhuma baixa foi enviada."
    );
    throw new ToaBridgeUnavailableError("A ponte do TOA nao respondeu. Nenhuma baixa foi enviada nesta tentativa.");
  }
  async function ordersForBatchContract(payload, contract, readFresh, scope, deps) {
    const orders=payload.imperium_all_orders;
    if(payload.imperium_refresh?.refreshed===true && Array.isArray(orders) &&
       orders.every(order=>order?.contract && order.status)) {
      // This snapshot establishes which OS are still in the field. Only
      // refreshCandidate can authorize a send using a fresh field-list row.
      const field=orders.filter(order=>String(order.contract)===contract && String(order.status).trim().toUpperCase()==="EM CAMPO");
      const source=scope && unproductiveSource(payload,scope,deps);
      if(!source || field.length>2 || !field.some(order=>isUnproductiveCompanion(order,source.sourceOs) &&
        !capturedOrders(source.capture,order).some(match=>match.approved_state_hash))) return field;
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
  function serviceWords(service) {
    return serviceLabel(service).replace(/[^A-Z0-9]+/g," ").trim().replace(/^\d+ /,"");
  }
  function isChipService(service) {
    return serviceWords(service)==="ENVIO DE CHIP VIA TECNICO";
  }
  function chipTaskCode(task) {
    const code=String(task?.close_code||"").trim();
    return /^(?:-+|N\/?A|NULL|NONE)$/i.test(code) ? "" : code;
  }
  function installedChipCapture(capture, equipmentType) {
    const installed=capture.installed_equipment||[];
    const materials=capture.materials||[];
    const mobileLabel=item=>!/\b(?:SMART\s*CARD|NAGRA|DECODER|DECO|EMTA|MODEM)\b/
      .test(serviceWords(`${item.type||""} ${item.description||""}`));
    const fromEquipment=new Map(installed.filter(item=>mobileLabel(item) && equipmentType?.(item)==="chip")
      .map(item=>[String(item.serial||"").trim(),item])
      .filter(([serial])=>/^\d{18,25}$/.test(serial)));
    const fromMaterial=item=>{
      if(!mobileLabel(item))return "";
      for(const value of [item.serial,item.identifier,item.material_code,item.code,item.description]){
        const match=/^(?:(?:ICCID|TELEFONICO|CHIP)\s*[:#=-]?\s*)?(\d{18,25})$/i.exec(
          serviceLabel(value).trim(),
        );
        if(match)return match[1];
      }
      return "";
    };
    const materialSerials=materials.map(fromMaterial);
    const serials=new Set([...fromEquipment.keys(),...materialSerials.filter(Boolean)]);
    if(serials.size!==1)return null;
    const [serial]=serials;
    return {...capture,
      installed_equipment:fromEquipment.has(serial)?installed:[...installed,{type:"chip",serial}],
      materials:materials.filter((_,i)=>materialSerials[i]!==serial),
    };
  }
  function captureDate(capture) {
    const value=String(capture.scheduled_date||"").slice(0,10);
    return /^\d{2}\/\d{2}\/\d{4}$/.test(value)?value.split("/").reverse().join("-"):value;
  }
  function displayOnlyTask(task) {
    return task.imperium_only===true || task.source==="imperium_contract_status"
      || (task.registry_only===true && !String(task.close_code||"").trim());
  }
  function validateCapture(capture, scope, deps, taskNumbers) {
    const legacyValidated=capture.decision==null && capture.found===true &&
      Array.isArray(capture.validation_errors) && capture.validation_errors.length===0 &&
      Array.isArray(capture.operation_blockers) && capture.operation_blockers.length===0;
    const issues=[];
    if(String(capture.contract)!==scope.contract)issues.push("contrato divergente");
    if(!capture.aid)issues.push("ID da atividade ausente");
    if(!deps.complete(capture.activity_status))issues.push("status da atividade: "+String(capture.activity_status||"nao informado").slice(0,80));
    if(capture.decision!=="candidate_after_validation" && !legacyValidated)issues.push("decisao: "+String(capture.decision||"nao validada").slice(0,80));
    if(capture.materials_complete===false)issues.push("captura de materiais incompleta");
    if((capture.validation_errors||[]).length)issues.push("erros de validacao: "+capture.validation_errors.length);
    if((capture.operation_blockers||[]).length)issues.push("bloqueios operacionais: "+capture.operation_blockers.length);
    if(issues.length)throw Error("Atividade incompleta ou bloqueada no TOA. OS "+taskNumbers.join(", ")+": "+issues.join("; ")+". Nenhuma baixa enviada.");
    if(captureDate(capture)!==scope.date)throw Error("Data do TOA divergente da data selecionada.");
    return liveBucket(capture,scope.profile,deps.route);
  }
  function approvedActivityOrder(order, capture, scope, deps, route) {
    if(!deps.valid(order,capture)) return false;
    if(order.operation_source==="toa_import") {
      const origin=importBucket(order,scope,capture);
      return Boolean(origin && (!route || route===origin));
    }
    return Boolean(route && order.operation_source==="imperium_cache"
      && order.manual_scope?.cache_date===scope.date
      && (!order.activity_id || String(order.activity_id)===String(capture.aid)));
  }
  function unproductiveSource(payload, scope, deps) {
    const captures=(payload.results||[]).filter(c=>String(c.contract)===scope.contract && captureDate(c)===scope.date);
    if(captures.length!==1) return;
    const [capture]=captures;
    const tasks=(capture.tasks||[]).filter(task=>!displayOnlyTask(task) &&
      (String(task.os_number||"").trim() || String(task.close_code||"").trim()));
    if(tasks.length!==1) return;
    const [sourceTask]=tasks;
    const sourceOs=String(sourceTask.os_number||"");
    const code=String(sourceTask.close_code||"").trim();
    if(!sourceOs || sourceTask.registry_only || !deps.executed(sourceTask.status)
      || !/^\d{3}$/.test(code) || code==="430" || !deps.knownCode(code) || deps.productive?.(code)!==false
      || !["installed_equipment","removed_equipment","materials"].every(key=>Array.isArray(capture[key]) && !capture[key].length)) return;
    return {capture,sourceTask,sourceOs,code};
  }
  function capturedOrders(capture, row) {
    return (capture.imperium_matches||[]).filter(order=>String(order.num_os)===String(row.num_os)
      && String(order.contract)===String(row.contract) && String(order.id_os)===String(row.id_os));
  }
  function isUnproductiveCompanion(order, sourceOs) {
    return String(order.num_os)!==sourceOs && codeOnly(order.service)
      && !/\b(?:DESCONEXAO|RETIRADA|CANCELAMENTO|STREAM(?:ING)?)\b/.test(serviceWords(order.service));
  }
  function addUnproductiveCompanion(payload, candidates, missing, scope, deps) {
    if(missing.length!==1 || candidates.length>1) return;
    const source=unproductiveSource(payload,scope,deps);
    if(!source) return;
    const {capture,sourceTask,sourceOs,code}=source;
    const [row]=missing;
    if(!isUnproductiveCompanion(row,sourceOs)) return;
    const numOs=String(row.num_os);
    const exact=capturedOrders(capture,row);
    // Some versions of the TOA bridge only attach orders present in a task.
    // A separately read field row carries its own backend approval.
    const order=exact[0]||row;
    if(exact.length>1 || (!exact.length && !row.approved_state_hash)) return;
    const route=validateCapture(capture,scope,deps,[sourceOs,numOs]);
    if(!approvedActivityOrder(order,capture,scope,deps,route)) return;
    const primary=candidates[0];
    if(primary) {
      if(primary.capture!==capture || primary.numOs!==sourceOs || primary.code!==code
        || !approvedActivityOrder(primary.order,capture,scope,deps,route)
        || ["technician_login","service_window","city"].some(key=>primary.order[key] && order[key]
          && serviceLabel(primary.order[key]).trim()!==serviceLabel(order[key]).trim())) return;
      primary.batchCodeOnly=true;
    } else {
      // A later run can finish the companion after a confirmed first send.
      const closed=(capture.imperium_all_orders||[]).filter(item=>String(item.num_os)===sourceOs
        && String(item.contract)===scope.contract && /^(?:CONCLUIDA|REAGENDADA|CANCELADA)$/.test(serviceLabel(item.status).trim()));
      if(!route || payload.imperium_refresh?.refreshed!==true || closed.length!==1
        || !deps.confirmedCloses?.some(item=>item.state==="confirmed" && String(item.close_code)===code
          && item.report_date===scope.date && String(item.id_os)===String(closed[0].id_os)
          && String(item.num_os)===sourceOs && String(item.contract)===scope.contract)) return;
    }
    candidates.push({
      capture,task:{os_number:numOs,status:sourceTask.status,close_code:code},order,numOs,code,
      isDisconnect:false,batchAdhesion:true,batchScope:{profile:scope.profile,date:scope.date,epoch:scope.epoch},
      batchCodeOnly:true,batchInheritedFrom:sourceOs,
    });
  }
  function installsVoip(service) {
    return /^(?:ADESAO )?(?:INSTALAR|INSTALACAO DE) PONTO VOIP$/.test(serviceWords(service));
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
    if(candidate.batchInheritedFrom && current.operation_source==="imperium_cache" &&
      (current.manual_scope?.cache_date!==scope.date ||
        ["activity_id","technician_login","service_window","city"].some(key=>String(current[key]||"")!==String(previous[key]||"")))) {
      throw Error("O vinculo da OS acompanhante mudou; nenhuma baixa enviada: "+candidate.numOs);
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
  function priorCloseOutcome(record, failures=[], expectedCode="") {
    const os="OS "+record.num_os+(record.close_code?" ("+record.close_code+")":"");
    if(record.state==="confirmed") {
      if(expectedCode && String(record.close_code)!==String(expectedCode)) {
        return {reason:os+" ja confirmada com codigo diferente do "+expectedCode+" pedido neste lote."};
      }
      return {closed:true};
    }
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
    if(isUnresolvedClose(record)) {
      const time=String(record.accepted_at||"").match(/T(\d\d:\d\d)/)?.[1];
      return {pending:true,reason:time
        ? os+" aceita as "+time+", aguardando confirmacao no Imperium. Reenvio bloqueado."
        : os+" possui tentativa anterior sem confirmacao no Imperium."};
    }
    return {reason:os+" possui tentativa anterior sem liberacao para reenvio."};
  }
  // One physical EMTA can support both Virtua and VoIP. Only an exact
  // completed activity with both tasks in field may use this rule.
  function applySharedEmtaRule(candidates, deps) {
    const groups=new Map();
    for(const c of candidates){const group=groups.get(c.capture.aid)||[];group.push(c);groups.set(c.capture.aid,group);}
    const kind=c=>serviceWords(c.order.service);
    for(const group of groups.values()){
      const virtua=group.filter(c=>/^(?:ADESAO )?(?:INSTALAR|INSTALACAO DE) PONTO VIRTUA$/.test(kind(c)));
      const voip=group.filter(c=>installsVoip(c.order.service));
      if(virtua.length!==1 || voip.length!==1)continue;
      const capture=virtua[0].capture;
      if(!deps.equipmentType || !group.every(c=>c.capture===capture))continue;
      const chip=group.filter(c=>isChipService(c.order.service));
      const allowed=group.every(c=>c===virtua[0]||c===voip[0]||chip.includes(c)||c.batchCodeOnly
        || /\bMESH\b/.test(kind(c)));
      const installed=capture.installed_equipment, removed=capture.removed_equipment;
      if(!allowed || chip.length>1 || !Array.isArray(installed) || !Array.isArray(removed)
        || removed.length>1 || removed.some(item=>deps.equipmentType(item)!=="emta"))continue;
      if((virtua[0].code!=="409" && deps.productive?.(virtua[0].code)!==true)
        || chip.some(c=>c.code!=="706"))continue;
      const bySerial=new Map();
      for(const item of installed){
        const serial=String(item.serial||"").replace(/[^A-Z0-9]/gi,"").toUpperCase();
        const type=deps.equipmentType(item);
        if(!serial || !["emta","chip","mesh"].includes(type) || (bySerial.has(serial)&&bySerial.get(serial)!==type))throw Error("Inventario Virtua/VoIP sem identidade segura.");
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
  function keepCustomerEmtaForStandaloneVoip(candidates, deps) {
    if (candidates.length !== 1) return;
    const [candidate] = candidates;
    const {capture, code, numOs, order} = candidate;
    const {installed_equipment: installed, removed_equipment: removed, customer_equipment: customer} = capture;
    if (!deps.productive?.(code) || !installsVoip(order.service)
      || (capture.tasks || []).some(task => task.os_number && String(task.os_number) !== numOs)
      || !Array.isArray(installed) || !Array.isArray(removed) || removed.length || !Array.isArray(customer)) return;

    // Use the TOA equipment type and the exact serial shown in the Cliente pool.
    const emtaSerial = item => /\bEMTA\b/.test(serviceWords(item?.type))
      ? String(item?.serial || "").trim().toUpperCase() : "";
    const existingSerials = new Set(customer.map(emtaSerial).filter(Boolean));
    const reused = new Set();
    const newInstallations = installed.filter(item => {
      const serial = emtaSerial(item);
      if (!existingSerials.has(serial)) return true;
      reused.add(serial);
      return false;
    });
    if (!reused.size) return;
    candidate.capture = {...capture, installed_equipment: newInstallations};
    candidate.batchCustomerEmta = [...reused];
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
    const candidates=[], toaOnly=[], seen=new Set(), imperiumOnly=new Set(), blockedCodes=new Map();
    for(const rawCapture of payload.results||[]) {
      const tasks=rawCapture.tasks||[];
      const chipOrders=(rawCapture.imperium_matches||[]).filter(o=>isChipService(o.service));
      const chipOrder=chipOrders.length===1?chipOrders[0]:null;
      const chipTask=chipOrder && byNumber.has(String(chipOrder.num_os))
        ? tasks.find(task=>String(task.os_number)===String(chipOrder.num_os)) : null;
      const linkedChip=chipTask && importBucket(chipOrder,scope,rawCapture);
      // An installed ICCID on the same completed activity supplies positive
      // evidence for the exact imported chip order when the TOA task is omitted.
      const chipOmitted=linkedChip && (chipTask.imperium_only===true
        || chipTask.source==="imperium_contract_status") && !chipTaskCode(chipTask);
      const chipExecuted=chipTask && /^(?:E|EXECUTAD[AO]|EXECUTED)$/.test(serviceLabel(chipTask.status).trim());
      const canResolveChip=chipTask && ["","409","706"].includes(chipTaskCode(chipTask))
        && (chipOmitted || (chipExecuted && (!displayOnlyTask(chipTask) || linkedChip)));
      const chipCapture=canResolveChip ? installedChipCapture(rawCapture,deps.equipmentType) : null;
      const capture=chipCapture||rawCapture;
      const matching=(capture.tasks||[]).filter(task=>{
        const os=String(task.os_number||"");
        if(!byNumber.has(os)) return false;
        if(displayOnlyTask(task) && !(task===chipTask && chipCapture)) {
          imperiumOnly.add(os);
          return false;
        }
        return true;
      });
      if(!matching.length) continue;
      const route=validateCapture(capture,scope,deps,matching.map(task=>String(task.os_number)));
      for(const task of matching) {
        const os=String(task.os_number), activeOrder=byNumber.get(os);
        const exact=(capture.imperium_matches||[]).filter(o=>String(o.num_os)===os && String(o.contract)===contract && Number(o.id_os)===Number(activeOrder.id_os));
        if(seen.has(os) || exact.length!==1 || !deps.valid(exact[0],capture)
          || !(deps.executed(task.status) || (task===chipTask && chipOmitted && chipCapture))) throw Error("OS sem correspondencia unica, aprovada e executada: "+os);
        const order=exact[0], service=String(order.service||"");
        const origin=importBucket(order,scope,capture);
        if(order.operation_source==="toa_import" && !origin) throw Error("OS "+os+": origem importada sem comprovacao de bucket, data e atividade de adesao.");
        if(!route && !origin) throw Error("OS "+os+": bucket NTL/PWM sem comprovacao no TOA ou no arquivo de importacao.");
        if(route && origin && route!==origin) throw Error("Bucket TOA diverge da origem importada.");
        if(!service || /DESCONEX|RETIRADA\s+DE\s+ASSINATURA/i.test(service)) throw Error("Servico fora do escopo de adesao: "+os);
        seen.add(os);
        const chipService=isChipService(service);
        let code=chipService ? chipTaskCode(task) : String(task.close_code||"").trim();
        if(code==="410"){
          toaOnly.push({capture,order,numOs:os,code,batchCodeOnly:codeOnly(service)});
          continue;
        }
        if(chipService && (code==="409" || code==="706" || (!code && (chipExecuted || chipOmitted)))) {
          if(task!==chipTask || !chipCapture || !deps.knownCode("706")) {
            throw Error("Chip sem ICCID unico ou tarefa executada confirmada para codigo 706: "+os);
          }
          code="706";
        }
        if(!/^\d{3}$/.test(code) || code==="430" || !deps.knownCode(code)) {
          const reason=!code ? "sem codigo de baixa confirmado no TOA" : /^\d{3}$/.test(code)
            ? "com codigo "+code+" indisponivel para a baixa oficial de adesao" : "com codigo de baixa invalido no TOA";
          blockedCodes.set(os,"OS "+os+" "+reason);
          continue;
        }
        candidates.push({capture,task:{...task,close_code:code},order,numOs:os,code,isDisconnect:false,batchAdhesion:true,batchScope:{profile,date,epoch:scope.epoch},batchCodeOnly:codeOnly(service)});
      }
    }
    applySharedEmtaRule([...candidates,...toaOnly],deps);
    const skipped=new Set();
    for(const item of toaOnly){
      const noInventory=["installed_equipment","removed_equipment","materials"]
        .every(key=>Array.isArray(item.capture[key])&&!item.capture[key].length);
      const message="OS "+item.numOs+" (410) registrada somente no TOA";
      if(item.batchCodeOnly || noInventory){
        skipped.add(item.numOs);
        deps.toaOnly?.(message);
      }else{
        blockedCodes.set(item.numOs,message+"; inventario compartilhado em tratativa");
      }
    }
    addUnproductiveCompanion(payload,candidates,rows.filter(order=>!seen.has(String(order.num_os))),scope,deps);
    const planned=new Set([...candidates.map(candidate=>candidate.numOs),...skipped]);
    if(planned.size!==byNumber.size) {
      const missing=[...byNumber.keys()].filter(os=>!planned.has(os));
      const displayed=missing.filter(os=>imperiumOnly.has(os));
      const independent = candidates.filter(candidate => candidate.batchCodeOnly);
      if(deps.hold && missing.every(os=>imperiumOnly.has(os)||blockedCodes.has(os)) && independent.length) {
        deps.hold([
          ...missing.map(os=>blockedCodes.get(os)||"OS "+os+" sem codigo de baixa confirmado no TOA"),
          ...candidates.filter(candidate => !candidate.batchCodeOnly).map(candidate =>
            "OS " + candidate.numOs + " retida para conciliar os itens da atividade"),
        ]);
        return independent;
      }
      if(blockedCodes.size) throw Error([...blockedCodes.values()].join(". "));
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
        if(!os || activeTasks.has(os) || skipped.has(os))continue;
        if((task.imperium_only===true || task.source==="imperium_contract_status") && seen.has(os))continue;
        const other=(capture.imperium_matches||[]).find(o=>String(o.num_os)===os)
          || (capture.imperium_all_orders||[]).find(o=>String(o.num_os)===os)
          || deps.confirmedCloses?.find(o=>String(o.num_os)===os && String(o.contract)===contract
            && o.report_date===date && o.state==="confirmed");
        if(!other || !codeOnly(other.service))throw Error("Atividade com OS acompanhante fora de campo; risco de duplicar estoque.");
      }
    }
    keepCustomerEmtaForStandaloneVoip(candidates,deps);
    deps.assign(candidates);
    const serials=new Map(), byActivity=new Map();
    for(const candidate of candidates) {
      if(candidate.batchCodeOnly) continue;
      const activitySerials=byActivity.get(candidate.capture.aid)||new Set();
      byActivity.set(candidate.capture.aid,activitySerials);
      const plan=deps.equipment(candidate);
      if(plan.error || plan.correction) throw Error("Equipamentos exigem tratativa: "+candidate.numOs);
      const expected=deps.expectedType?.(candidate.order.service);
      const {installed_equipment:installed,removed_equipment:removed}=candidate.capture;
      const service=serviceWords(candidate.order.service);
      const keepsEquipment=/^(?:ADESAO )?MUD(?:ANCA)? (?:DE )?END(?:ERECO)?(?: |$)/.test(service)
        && (expected==="emta" || expected==="decoder")
        && Array.isArray(installed) && Array.isArray(removed) && !plan.installed.length;
      if(expected && (candidate.code==="706" || deps.productive?.(candidate.code)) && !keepsEquipment && !plan.installed.some(item=>item.type===expected || (expected==="decoder" && item.type==="smart"))) {
        throw Error("Serial obrigatorio nao conciliado para OS "+candidate.numOs+" ("+expected+").");
      }
      if(expected==="mesh" && deps.productive?.(candidate.code) &&
        (plan.installed.length!==1 || plan.installed[0].type!=="mesh" || plan.removed.length)) {
        throw Error("OS "+candidate.numOs+" exige um unico Wi-Fi Mesh instalado.");
      }
      if(candidate.code==="706" && (plan.installed.length!==1 || plan.installed[0].type!=="chip" || !/^\d{18,25}$/.test(String(plan.installed[0].serial||"")) || plan.removed.length))throw Error("Codigo 706 exige um unico ICCID instalado.");
      for(const item of [...plan.installed,...plan.removed]) {
        const key=String(item.serial||"").replace(/[^A-Z0-9]/gi,"").toUpperCase();
        if(!key) throw Error("Serial obrigatorio ausente na OS "+candidate.numOs+".");
        if(serials.has(key)) throw Error("Serial sem vinculo unico no inventario TOA. Confira instalacao e retirada nas OS "+[...new Set([serials.get(key),candidate.numOs])].join(", ")+". Nenhuma baixa enviada.");
        serials.set(key,candidate.numOs);activitySerials.add(key);
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
  // A transport failure or generic busy response is not proof of no write.
  // Reconcile only the exact order, then preserve the server's durable outcome.
  async function reconcileCloseRead(candidate, response, readReport) {
    if(response?.closed || response?.pending || !readReport) return response;
    const order=candidate.order;
    if(!order?.id_os || !order?.contract || !candidate.numOs) return response;
    let report;
    try { report=await readReport(); }
    catch { return { ...response, pending:true, reason:"Resultado nao conciliado no relatorio; nao reenviar automaticamente." }; }
    if(!Array.isArray(report?.records))return {...response,pending:true,reason:"Relatorio indisponivel; nao reenviar automaticamente."};
    const matches=report.records.filter(r=>String(r.id_os)===String(order.id_os) && String(r.num_os)===String(candidate.numOs) && String(r.contract)===String(order.contract));
    const unresolved=matches.find(isUnresolvedClose);
    if(unresolved){
      const outcome=priorCloseOutcome(unresolved);
      // An uncertain stock transfer remains a review, never an automatic
      // resend or a retry of the material transfer in this execution.
      return {...response,...outcome,reason:outcome.reason||unresolved.message};
    }
    const confirmed=matches.find(r=>r.state==="confirmed");
    if(confirmed){
      const outcome=priorCloseOutcome(confirmed,[],candidate.code);
      return {...response,...outcome,pending:false,reason:outcome.reason||"Confirmada no relatorio do Imperium."};
    }
    const failed=matches.find(r=>r.state==="failed" && String(r.close_code)===String(candidate.code));
    if(failed)return {...response,reason:failed.message||response?.reason};
    return response;
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
        const toaOnly=[];
        const candidates=await hooks.prepare(contract, reasons => held.push(...reasons), reason=>toaOnly.push(reason));
        if(!hooks.active()) break;
        if(!candidates.length) {
          hooks.update(contract,toaOnly.length?"Somente TOA":"Sem OS em campo",toaOnly.join(" | ")||"Nenhuma baixa enviada.");
          continue;
        }
        let confirmed=0, waiting=0, blocked=0;
        const outcomes=[];
        for(const candidate of candidates) {
          if(!hooks.active()) break;
          const os="OS "+candidate.numOs+(candidate.code?" ("+candidate.code+")":"");
          hooks.update(contract,"Executando",os);
          let audit="", detail="", result="review";
          try {
            const res=await hooks.send(candidate);
            const reused = candidate.batchCustomerEmta?.length
              ? "EMTA ja cadastrado no cliente (sem movimentacao): " + candidate.batchCustomerEmta.join(", ") : "";
            const inherited=candidate.batchInheritedFrom ? "Codigo improdutivo da OS "+candidate.batchInheritedFrom : "";
            audit=[inherited,reused,materialAudit(res.materialPreparation)].filter(Boolean).join(". ");
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
        const detail=confirmed+" confirmada(s), "+waiting+" pendente(s), "+(blocked+held.length)+" em tratativa, "+rest+" nao enviada(s). "+[...outcomes,...held,...toaOnly].join(" | ");
        hooks.update(contract,waiting?"Aguardando confirmacao":blocked||held.length?"Tratativa":confirmed===candidates.length?"Baixado":"Interrompido",detail);
      } catch(err) {
        if ((err instanceof FreshOrdersBusyError || err instanceof ToaBridgeUnavailableError || err instanceof ToaActivityScopeUnconfirmedError) && !deferred && hooks.active()) {
          queue.push({contract, deferred: true});
          hooks.update(contract, "Na fila", err.message+" Nova consulta no fim do lote.");
        } else {
          hooks.update(contract, "Tratativa", String(err.message || err).slice(0, 300));
        }
      }
    }
  }
  function restoreQueue(raw, date) {
    const saved=JSON.parse(raw);
    if(saved?.date!==date || !Array.isArray(saved.rows) || !saved.rows.length) return [];
    const contracts=parseContracts(saved.rows.map(row=>row.contract).join("\n"));
    if(contracts.length!==saved.rows.length) return [];
    return saved.rows.map(({contract,label})=>{
      if(["Na fila","Consultando","Executando"].includes(label)) {
        return {contract,label:"Interrompido",detail:"Consulte o Imperium antes de retomar a fila."};
      }
      return {contract,label,detail:"Resultado salvo neste navegador. Confira no relatorio de baixas."};
    });
  }
  if(typeof module!=="undefined" && module.exports){module.exports={parseContracts,isAdhesionBucket,codeOnly,materialAudit,selectCandidates,runBatch,freshOrders,readBatchToa,ordersForBatchContract,refreshCandidate,priorCloseOutcome,reconcileCloseRead,restoreQueue};return;}
  const panel=document.getElementById("adhesionBatch");
  if(!panel)return;
  const input=document.getElementById("adhesionBatchInput"),start=document.getElementById("adhesionBatchStart"),
    stop=document.getElementById("adhesionBatchStop"),status=document.getElementById("adhesionBatchStatus"),list=document.getElementById("adhesionBatchResults");
  let stopped=false, rows=new Map(), visibleScope="", queueScope=null;
  function storageScope() {
    const user=state.authUser;
    if(state.profile!=="natal" || !user?.id || !["admin","controller"].includes(user.role))return null;
    return {key:"dominium-adhesion-queue:"+user.id,date:elements.date.value};
  }
  function saveQueue() {
    if(!queueScope || !rows.size) return;
    const {key,date}=queueScope;
    try {
      localStorage.setItem(key,JSON.stringify({date,rows:[...rows.values()].map(({contract,label})=>({contract,label}))}));
    } catch {/* Storage is optional and never controls a submission. */}
  }
  function busy(){return state.adhesionBatchRunning || state.semiAutoRunning || state.semiAutoWorker || state.semiAutoRefreshing || state.semiAutoPendingConfirmationWorker || state.toaLiveLoading || state.running || state.loading || state.disconnectAutomationWorker;}
  function render() {
    const scope=storageScope();
    const scopeId=scope ? scope.key+":"+scope.date : "";
    if(!state.adhesionBatchRunning && scopeId!==visibleScope) {
      visibleScope=scopeId;
      let restored=[];
      try {if(scope)restored=restoreQueue(localStorage.getItem(scope.key),scope.date);} catch {/* Ignore invalid saved queues. */}
      rows=new Map(restored.map(row=>[row.contract,row]));
      input.value=restored.map(row=>row.contract).join("\n");
      if(!restored.length) status.textContent="";
    }
    start.disabled=Boolean(busy() || state.profile!=="natal");stop.disabled=!state.adhesionBatchRunning;input.disabled=!!state.adhesionBatchRunning;
    const all=[...rows.values()], finished=all.filter(r=>!["Na fila","Consultando","Executando","Interrompido"].includes(r.label)).length;
    if(all.length) status.textContent=finished+" / "+all.length+" contratos | "+all.filter(r=>r.label==="Baixado").length+" baixados";
    list.replaceChildren(...all.map(r=>{
      const node=document.createElement("div");node.className="adhesion-batch-result";
      for(const value of [r.contract,r.label,r.detail]){const el=document.createElement("span");el.textContent=value;node.append(el);}
      return node;
    }));
  }
  function update(contract,label,detail){rows.set(contract,{contract,label,detail});saveQueue();render();}
  stop.addEventListener("click",()=>{stopped=true;status.textContent="Parando apos a solicitacao atual; nao sera reenviada.";});
  start.addEventListener("click",async()=>{
    if(busy()) return;
    let contracts;
    try{contracts=parseContracts(input.value);}catch(err){status.textContent=err.message;return;}
    if(!state.authUser || !["admin","controller"].includes(state.authUser.role) || !state.officialCloseEnabled || !state.closeEnabled){status.textContent="Baixa oficial indisponivel para esta sessao/cidade.";return;}
    const profile=state.profile,epoch=state.profileEpoch,date=elements.date.value;
    if(profile!=="natal" || !/^\d{4}-\d{2}-\d{2}$/.test(date)){status.textContent="Selecione cidade e data validas.";return;}
    state.adhesionBatchRunning=true;stopped=false;
    queueScope=storageScope();
    rows=new Map(contracts.map(contract=>[contract,{contract,label:"Na fila",detail:"Aguardando"}]));
    saveQueue();render();renderToaLiveStatus();
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
    async function outcomeFor(record, expectedCode) {
      if(!isUnresolvedClose(record) || record.category==="MATERIAL_TRANSFER_UNCERTAIN") return priorCloseOutcome(record,[],expectedCode);
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
        async prepare(contract, hold, toaOnly) {
          const payload = await readBatchToa(
            () => request(apiUrlForProfile("/api/toa-live/lookup", profile), {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({query: contract, expected_profile_key: profile, expected_date: date, adhesion_batch: true}),
              timeoutMs: 300000,
            }),
            {active, wait: sleep, notify: () => update(contract, "Consultando", "Ponte do TOA aguardando resposta.")},
          );
          if(!active()) throw Error("Cidade/data alterada; fila interrompida.");
          const scope={profile,contract,date,epoch};
          const deps={
            complete:disconnectActivityComplete,executed:disconnectTaskExecuted,route:automationProviderLabel,hold,toaOnly,
            confirmedCloses:Array.isArray(initialReport?.records)?initialReport.records:[],
            valid:validToaCloseSnapshot,knownCode:code=>state.closeCodes.some(c=>c.code===code),
            assign:semiAutoAssignMaterialOwners,equipment:semiAutoCandidateEquipmentPlan,materials:toaLiveMaterialsDraft,allowsMaterials:closeCodeAllowsMaterials,equipmentType:item=>toaLiveEquipmentType(item,true),expectedType:service=>expectedEquipmentType(service,true),productive:code=>Boolean(state.closeCodes.find(c=>c.code===code)?.productive)
          };
          const orders = await ordersForBatchContract(payload, contract, () =>
            readFieldOrders(contract, "Aguardando lista atualizada do Imperium."),scope,deps);
          return selectCandidates(payload,orders,scope,deps);
        },
        async send(candidate) {
          // A previously accepted/uncertain order is not submitted again.
          const report=await readCloseReport();
          if(!active() || !Array.isArray(report.records)) throw Error("Relatorio de baixa indisponivel.");
          const previous=report.records.find(r=>String(r.id_os)===String(candidate.order.id_os) &&
            (isUnresolvedClose(r) || r.state==="confirmed" || (r.state==="failed" && r.safe_to_retry!==true)));
          const outcome=previous?await outcomeFor(previous,candidate.code):null;
          if(outcome && !outcome.stockRetryRequestId) return outcome;
          if(!active()) throw Error("Lote interrompido.");
          const fresh = await readFieldOrders(
            String(candidate.order.contract), "Atualizando aprovacao da OS " + candidate.numOs + ".",
          );
          const refreshed=refreshCandidate(candidate,fresh.orders,validToaCloseSnapshot);
          if(!active()) throw Error("Lote interrompido.");
          const result=await processAutoCloseCandidate({...refreshed,stockRetryRequestId:outcome?.stockRetryRequestId},profile);
          if(!active())return result;
          return reconcileCloseRead(refreshed,result,readCloseReport);
        },
        async confirm(requestId, candidate) {
          for(let attempt=0;attempt<12;attempt++){
            if(!active()) return "pending";
            await sleep(10000);
            if(!active()) return "pending";
            try{
              const report=await readCloseReport();
              const row=(report.records||[]).find(r=>String(r.request_id)===requestId);
              if(row?.state==="confirmed")return String(row.close_code)===String(candidate.code) ? "confirmed" : "review";
              if(["failed","uncertain"].includes(row?.state))return "review";
            }catch{/* consultar novamente, nunca repetir a escrita */}
          }
          return "pending";
        }
      });
    } finally {
      state.adhesionBatchRunning=false;
      for(const row of rows.values())if(["Na fila","Consultando","Executando"].includes(row.label)){row.label="Interrompido";row.detail="Nenhuma nova solicitacao sera enviada.";}
      saveQueue();
      queueScope=null;
      renderToaLiveStatus();
    }
  });
  root.dominiumRenderAdhesionBatch=render;
  render();
})(globalThis);
