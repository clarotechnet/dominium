/* Controle de baixas — módulo visual read-only. Zero chamadas ao TOA e zero POST. */
(() => {
  "use strict";
  const root = document.getElementById("closeControlWorkspace");
  const engine = window.DominiumCloseControlEngine;
  if (!root || !engine) return;
  const get = id => root.querySelector("#" + id);
  const tableBody = get("ccRows"), counts = get("ccMetrics"), report = get("ccReport");
  const cityApi = window.DominiumCloseCityBoard, cityGrid = get("ccCityBoard");
  const filter = get("ccFilter"), search = get("ccSearch");
  const source = get("ccSource"), current = get("ccCurrentTime"), refresh = get("ccRefresh");
  const demoClock = new Date("2026-11-06T09:37:00-03:00");
  let demo = true, records = engine.demoOrders(), clock = demoClock, latest = null;
  let queueSequence = 10;
  const queueCity = get("ccDemoQueueCity");
  const demoControls = get("ccQueueDemoActions");
  const stableKey = order => String(order.city || "") + "|" +
    String(order.contract || "") + "|" + String(order.os || "");
  function startDemo() {
    records = engine.demoOrders().map((item, index) => ({
      ...item,
      queueSequence: index + 1,
      processingState: index === 0 || index === 9 ? "processing" : "queued",
    }));
    queueSequence = 10;
  }
  startDemo();

  const add = (tag, text, cls="") => {
    const el = document.createElement(tag);
    if (cls) el.className=cls;
    if (text != null) el.textContent=String(text);
    return el;
  };
  const selectText = (value, otherwise="—") => value == null || value === ""
    ? otherwise : String(value);
  const formatDate = value => {
    if (value == null) return "—";
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? d.toLocaleTimeString("pt-BR",{
      hour:"2-digit",minute:"2-digit"}) : "—";
  };
  const paintCard = (label,count,hint) => {
    const card=add("div",null,"cc-metric");
    card.append(add("span",label),add("strong",count),add("small",hint));
    return card;
  };
  const badgeClass = d => d.ready && !d.review?"cc-ready"
    : d.review?"cc-review"
    : d.key==="route_not_imported"||d.key==="order_not_imported"?"cc-blocked":"cc-wait";

  function rowsFromLoadedImperium() {
    const snapshot = window.DominiumCloseControlBridge?.getSnapshot?.();
    if (!snapshot || !Array.isArray(snapshot.orders)) return [];
    return snapshot.orders.map(order => ({
      ...order,
      // Valores explícitos para evitar converter estado Imperium em conclusão TOA.
      toaStatus:"nao_consultada", toaObservedAt:null,
      routeImported:null, orderImported:null, imperiumOrderPresent: true,
      identityValidated:false, bucketValidated:false,
      codeConfirmed:false, toaDetailConfirmed:false, materialsValidated:false,
      imperiumAlreadyClosed:null,
    }));
  }
  function publishNote(message) {
    report.textContent=message;
  }
  // FLIP: cartões se deslocam da posição anterior para a nova posição.
  // Somente apresentação: não reordena operações ou envia comandos.
  function animateReorderedCards(previous) {
    if (!previous.size ||
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    requestAnimationFrame(() => {
      for (const card of cityGrid.querySelectorAll(".cc-city-item[data-queue-id]")) {
        const old = previous.get(card.dataset.queueId);
        if (!old || !card.isConnected) continue;
        const next = card.getBoundingClientRect();
        const dx = old.left - next.left, dy = old.top - next.top;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
        card.animate([
          { transform: "translate(" + dx + "px," + dy + "px)", opacity: .72 },
          { transform: "translate(0,0)", opacity: 1 },
        ], {duration: 460, easing:"cubic-bezier(.23,.9,.25,1)"});
      }
    });
  }
  function renderCityBoard(rows) {
    if(!cityGrid || !cityApi) return;
    const model = cityApi.build(rows);
    const previous = new Map(Array.from(cityGrid.querySelectorAll(".cc-city-item[data-queue-id]"),
      card => [card.dataset.queueId, card.getBoundingClientRect()]));
    cityGrid.replaceChildren();
    const statusTag = get("ccCitySource");
    statusTag.textContent = demo ? "DEMONSTRAÇÃO · DADOS FICTÍCIOS"
      : "IMPERIUM · DADOS JÁ CARREGADOS";
    for(const key of cityApi.CITIES) {
      const city = model.cities[key];
      const column = add("section", null, "cc-city");
      column.dataset.city = key;
      const heading = add("header",null,"cc-city-head");
      heading.append(add("strong",city.label),add("span",city.items.length+" O.S."));
      column.append(heading);
      const counters = add("div",null,"cc-city-counts");
      const badges = [
        ["active","Em tratamento"],
        ["confirmed","Baixadas"],
        ["ready","Para baixa"],
        ["in_progress","Em acompanhamento"],
        ["review","Revisar"],
        ["window","Fora da janela"],
        ["unverified","A validar"],
      ];
      for(const [type,label] of badges) {
        if(city.counts[type] || type==="confirmed" || type==="review"){
          counters.append(add("span",city.counts[type]+" "+label,"cc-city-count "+type));
        }
      }
      column.append(counters);
      const list=add("div",null,"cc-city-rows");
      if(!city.items.length) {
        list.append(add("p",demo?"Nenhuma O.S. fictícia nesta cidade."
          :"Nenhuma O.S. disponível desta cidade no carregamento atual.","cc-city-empty"));
      }
      for(const {order,decision,classification} of city.items.slice(0,35)) {
        const item=add("article",null,"cc-city-item "+classification.key);
        item.dataset.queueId = stableKey(order);
        item.append(add("h4","Contrato "+(order.contract||"não informado")),
          add("span",classification.label,"cc-city-state"),
          add("p","O.S. "+(order.os||"—")+" · "+(order.technician||"Técnico não informado")),
          add("p","Janela "+(order.windowStart||"—")+"–"+(order.windowEnd||"—")),
          add("p",decision.label+(decision.nextAt!=null
            ?" · próxima verificação "+formatDate(decision.nextAt):"")));
        list.append(item);
      }
      if(city.items.length>35)
        list.append(add("p","+"+(city.items.length-35)+" O.S. na tabela detalhada.","cc-city-empty"));
      column.append(list);cityGrid.append(column);
    }
    animateReorderedCards(previous);
    get("ccCitySummary").textContent =
      model.totals.os+" O.S. distintas com cidade identificada · "+
      model.totals.confirmed+" baixadas confirmadas · "+
      model.totals.ready+" aguardando baixa · "+
      model.totals.review+" para tratativa humana"+
      (model.unknown?" · "+model.unknown+" sem cidade identificada":"")+
      (model.duplicates?" · "+model.duplicates+" duplicações conciliadas":"")+
      " · 0 consultas TOA / 0 baixas realizadas nesta tela.";
  }
  function draw() {
    const plan=engine.plan(records,clock);
    latest=plan;
    if (demoControls) demoControls.hidden = !demo;
    renderCityBoard(plan.rows);
    counts.replaceChildren(
      paintCard("O.S. listadas",plan.counts.total,"Sem novas consultas"),
      paintCard("Janela / consulta",plan.counts.due,"Sugestões, não executadas"),
      paintCard("Contratos distintos",plan.counts.contractsDue,"Deduplicados por contrato"),
      paintCard("Aguardando",plan.counts.waiting,"Janela ou intervalo"),
      paintCard("Tratar / revisar",plan.counts.review,"Falhas ou dados insuficientes"),
    );
    current.textContent=demo
      ?"Demonstração · 06/11/2026 às 09:37"
      :"Lista Imperium já carregada · "+new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"});
    source.textContent=demo
      ?"10 O.S. fictícias · nenhuma requisição externa"
      :"Dados já carregados no DOMINIUM · estado TOA não confirmado";
    const term=search.value.trim().toLowerCase(),mode=filter.value;
    const selected=plan.rows.filter(({order,decision})=>{
      if (term && ![order.contract,order.os,order.technician].some(v=>String(v??"").toLowerCase().includes(term)))return false;
      if (mode==="all")return true;
      if (mode==="review")return decision.review;
      if (mode==="due")return decision.due;
      if (mode==="ready")return decision.ready && !decision.review;
      if (mode==="waiting")return !decision.due&&!decision.ready&&!decision.review;
      return true;
    });
    tableBody.replaceChildren();
    for(const {order,decision} of selected.slice(0,300)){
      const row=add("tr");
      const fields=[
        order.os,order.contract,order.technician,
        selectText(order.windowStart)+"–"+selectText(order.windowEnd),
        engine.statusOf(order.toaStatus).replaceAll("_"," "),
        decision.label,
        decision.nextAt != null? formatDate(decision.nextAt):"—",
      ];
      fields.forEach((v,index)=>{
        const cell=add("td");
        if (index===5) cell.append(add("span",v,"cc-badge "+badgeClass(decision)));
        else cell.textContent=String(v??"—");
        row.append(cell);
      });
      tableBody.append(row);
    }
    get("ccTableSummary").textContent=selected.length+" O.S. exibidas"
      +(selected.length>300?" (limitado a 300)":"")
      +" · "+(demo?"cenário demonstrativo":"consulta local sem acesso ao TOA");
    if(!selected.length){
      const row=add("tr"),cell=add("td","Nenhuma O.S. corresponde aos filtros.","cc-empty");
      cell.colSpan=7;row.append(cell);tableBody.append(row);
    }
  }
  function demoActive(city) {
    return records.find(order => order.city === city && order.processingState === "processing");
  }
  function promoteDemo(city) {
    if (demoActive(city)) return null;
    let next = records.find(order => order.city === city &&
      !["error","processing","confirmed"].includes(order.processingState) &&
      engine.windowDecision(order, clock) === null &&
      order.routeImported === true && order.orderImported === true &&
      order.imperiumOrderPresent === true);
    if (!next) {
      // Nova O.S. inventada APENAS para mostrar o movimento da fila.
      const seq = ++queueSequence;
      next = {
        os: "DEMO-FILA-" + seq,
        contract: "DEMO-C" + seq,
        technician: "Técnico fictício " + seq,
        city, windowStart: "08:00", windowEnd: "22:00",
        routeImported: true, orderImported: true, imperiumOrderPresent: true,
        toaStatus: "nao_consultada", confirmationState: "",
        processingState: "queued", imperiumAlreadyClosed: false,
        identityValidated: false, bucketValidated: false,
        codeConfirmed: false, toaDetailConfirmed: false, materialsValidated: false,
      };
      records.push(next);
    }
    next.processingState = "processing";
    next.queueSequence = ++queueSequence;
    return next;
  }
  function runDemoStep(step) {
    if (!demo) return;
    const city = queueCity.value;
    const currentOrder = demoActive(city);
    if (step === "next") {
      const newOrder = currentOrder || promoteDemo(city);
      draw();
      publishNote(currentOrder
        ? "Já existe uma O.S. em tratamento nessa cidade: " + currentOrder.os +
          ". Finalize ou registre a falha antes de iniciar outra."
        : "Simulação: " + (newOrder?.os || "nenhuma O.S.") +
          " entrou no topo da fila. Nenhuma operação real foi realizada.");
      return;
    }
    if (!currentOrder) {
      publishNote("Nenhuma O.S. ativa nesta cidade. Use Simular próxima O.S.");
      return;
    }
    if (step === "error") {
      currentOrder.processingState = "error";
      currentOrder.manualReview = true;
      currentOrder.queueSequence = ++queueSequence;
    } else {
      // Na demonstração, representa uma confirmação já ocorrida no Imperium.
      currentOrder.processingState = "confirmed";
      currentOrder.confirmationState = "confirmed";
      currentOrder.imperiumAlreadyClosed = true;
      currentOrder.toaStatus = "concluida";
      currentOrder.queueSequence = ++queueSequence;
    }
    const next = promoteDemo(city);
    draw();
    publishNote("SIMULAÇÃO: " + currentOrder.os +
      (step === "error" ? " deu erro e desceu para a fila de tratativa."
        : " teve baixa fictícia confirmada e desceu para o histórico.") +
      "\n" + (next ? next.os + " assumiu a 1ª posição." : "Sem próxima O.S. elegível.") +
      "\n0 consultas TOA · 0 POSTs · 0 baixas reais.");
  }
  function simulate(type) {
    const eligible=latest?.rows.filter(({decision})=>decision.ready
      && !decision.review&&decision.readyFor===type) || [];
    const candidates=eligible.map(({order})=>order.os);
    publishNote((type==="productive"?"PRÉVIA PRODUTIVAS":"PRÉVIA IMPRODUTIVAS")+
      "\n"+(candidates.length
        ? candidates.join(", ")+" · "+candidates.length+" O.S. com pré-requisitos simulados."
        : "Nenhuma O.S. possui confirmação completa para preparar essa fila.")+
      "\n0 POSTs enviados · 0 consultas TOA · nenhuma baixa realizada."+
      "\nPara uso real, faltam autorização do backend, prova de importação, orçamento TOA global e confirmação de baixa no Imperium.");
  }
  get("ccDemo").addEventListener("click",()=>{
    demo=true;startDemo();clock=demoClock;
    filter.value="all";search.value="";draw();
    publishNote("Cenário fictício de 10 O.S. às 09:37: duas janelas 08–11, quatro 11–14, três 12–14 e uma 08–22. Somente janelas ativas podem gerar sugestões de consulta.");
  });
  get("ccReal").addEventListener("click",()=>{
    demo=false;records=rowsFromLoadedImperium();clock=new Date();
    filter.value="all";search.value="";draw();
    publishNote(records.length
      ?"Lista carregada do Imperium. A presença da O.S. na lista não prova que a rota foi importada nem que ela esteja concluída no TOA. Nenhuma consulta adicional será feita."
      :"O DOMINIUM ainda não carregou O.S. nesta sessão. Abra 'Ordens de serviço' para carregar a lista; depois volte aqui.");
  });
  refresh.addEventListener("click",()=>{
    if(!demo){records=rowsFromLoadedImperium();clock=new Date();}
    draw();publishNote("Painel atualizado a partir de dados em memória. Nenhum acesso externo realizado.");
  });
  get("ccDemoNext")?.addEventListener("click",()=>runDemoStep("next"));
  get("ccDemoError")?.addEventListener("click",()=>runDemoStep("error"));
  get("ccDemoSuccess")?.addEventListener("click",()=>runDemoStep("success"));
  get("ccPreviewProductive").addEventListener("click",()=>simulate("productive"));
  get("ccPreviewImproductive").addEventListener("click",()=>simulate("improductive"));
  filter.addEventListener("change",draw);
  search.addEventListener("input",draw);
  document.addEventListener("dominium:module-change",ev=>{
    if(ev.detail?.module==="close-control"){
      if(!demo){records=rowsFromLoadedImperium();clock=new Date();}
      draw();
    }
  });
  document.addEventListener("dominium:orders-updated",()=>{
    if(!demo && !root.classList.contains("hidden")){
      records=rowsFromLoadedImperium();clock=new Date();draw();
    }
  });
  draw();
  publishNote("HOMOLOGAÇÃO: nenhum botão inicia baixas. Use 'Cenário 09:37' para validar as janelas e os intervalos de 15 → 20 → 30 minutos para O.S. iniciadas.");
})();
