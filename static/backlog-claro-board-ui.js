/* Adendo visual ao painel existente Análise Backlog.
 * Lê o evento da tratativa diária. Sem requisições diretas ao TOA/Imperium.
 */
(() => {
  "use strict";
  const api=window.DominiumClaroTreatment;
  const root=document.getElementById("backlogWorkspace");
  const grid=document.getElementById("backlogClaroGrid");
  const meta=document.getElementById("backlogClaroStatus");
  const download=document.getElementById("backlogClaroExportCsv");
  const offroute=document.getElementById("backlogClaroOpenOffroute");
  if(!root || !grid || !meta || !api) return;
  let model=api.build([]),lastReceived=null,details=null,loaded=false;

  const elt=(tag,text,cls)=>{
    const n=document.createElement(tag);
    if(text!==undefined&&text!==null)n.textContent=String(text);
    if(cls)n.className=cls;
    return n;
  };
  const shorten=(value,n=85)=>{
    const s=String(value||"").trim();
    return s.length>n?s.slice(0,n-1)+"…":s;
  };
  const td=(parent,value,cls)=>{
    const item=elt("span",value,cls);
    parent.append(item);return item;
  };
  function render(){
    grid.replaceChildren();
    if(!loaded){
      meta.textContent="Sem base carregada nesta sessão. Atualize a tratativa do dia; nenhuma consulta TOA será feita por este quadro.";
    }else{
      const s=model.totals;
      meta.textContent="Base do Imperium / rotas existentes · "+s.records+" O.S. distintas"+
        " · "+s.improductive+" improdutivas confirmadas"+
        " · "+s.pending+" pendentes"+
        " · "+s.review+" em revisão"+
        (s.unknown?" · "+s.unknown+" linhas sem cidade identificada":"")+
        (details?.sources?.length?" · "+details.sources.length+" fonte(s)":"");
    }
    download.disabled=model.totals.records===0;
    for(const key of api.CITY_ORDER){
      const city=model.cities[key];
      const column=elt("section",null,"claro-board-col");
      column.setAttribute("data-city",key);
      const head=elt("div",null,"claro-board-head");
      const name=elt("strong",city.label);
      const number=elt("span",city.rows.length+" O.S.","claro-board-number");
      head.append(name,number);column.append(head);
      const metrics=elt("div",null,"claro-board-metrics");
      [
        [city.counts.improductive,"Improdutivas","improductive"],
        [city.counts.pending,"Pendentes","pending"],
        [city.counts.review,"Revisar","review"],
      ].forEach(([num,label,cls])=>{
        metrics.append(elt("span",num+" "+label,"claro-metric "+cls));
      });
      column.append(metrics);
      const list=elt("div",null,"claro-board-list");
      if(!city.rows.length){
        list.append(elt("p",loaded?"Sem registros confirmados nesta fonte.":"Aguardando dados do Imperium.","claro-board-empty"));
      }
      for(const item of city.rows.slice(0,70)){
        const card=elt("article",null,"claro-ticket "+item.status.key);
        const title=elt("div",null,"claro-ticket-title");
        const contract=elt("b","Contrato "+item.contract);
        const badge=elt("span",item.status.label,"claro-ticket-tag");
        title.append(contract,badge);card.append(title);
        const os=elt("p","O.S. "+item.os_number+" · "+shorten(item.technician||"Técnico não informado",40));
        card.append(os);
        const detail=elt("p",shorten(item.treatment || "Conferir tratativa",110),"claro-ticket-detail");
        card.append(detail);
        const code=String(item.validated_code||"").trim();
        if(code)card.append(elt("p","Código validado: "+code,"claro-ticket-code"));
        list.append(card);
      }
      if(city.rows.length>70)list.append(elt("p","+"+(city.rows.length-70)+" O.S. adicionais na tabela técnica e CSV.","claro-board-empty"));
      column.append(list);grid.append(column);
    }
  }
  document.addEventListener("dominium:backlog-daily-loaded",event=>{
    const d=event.detail || {};
    model=api.build(d.rows);details=d;loaded=true;lastReceived=new Date();
    render();
  });
  download?.addEventListener("click",()=>{
    if(!model.totals.records)return;
    const data=api.exportCsv(model);
    const blob=new Blob([data],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    try{
      const a=document.createElement("a");
      const local=new Date();
      a.href=url;a.download="tratativa-claro-"+local.toISOString().slice(0,10)+".csv";
      document.body.append(a);a.click();a.remove();
    }finally{
      setTimeout(()=>URL.revokeObjectURL(url),5000);
    }
  });
  offroute?.addEventListener("click",()=>{
    const tab=root.querySelector('[data-backlog-tab="offroute"]');
    if(tab)tab.click();
  });
  render();
})();
