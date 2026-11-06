/* Controle de baixas — módulo visual read-only. Zero chamadas ao TOA e zero POST. */
(() => {
  "use strict";
  const root = document.getElementById("closeControlWorkspace");
  const engine = window.DominiumCloseControlEngine;
  if (!root || !engine) return;
  const get = id => root.querySelector("#" + id);
  const tableBody = get("ccRows"), counts = get("ccMetrics"), report = get("ccReport");
  const filter = get("ccFilter"), search = get("ccSearch");
  const source = get("ccSource"), current = get("ccCurrentTime"), refresh = get("ccRefresh");
  const demoClock = new Date("2026-11-06T09:37:00-03:00");
  let demo = true, records = engine.demoOrders(), clock = demoClock, latest = null;

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
  function draw() {
    const plan=engine.plan(records,clock);
    latest=plan;
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
    demo=true;records=engine.demoOrders();clock=demoClock;
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
