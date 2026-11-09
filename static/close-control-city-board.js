/* DOMINIUM Controle de baixas — painel por cidade.
 * Consome SOMENTE o resultado do motor de decisões do Controle de baixas.
 * Não usa dados de Backlog Claro e não executa rede, consulta ou POST.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports) module.exports=api;
  if(root) root.DominiumCloseCityBoard=api;
})(typeof window!=="undefined"?window:null,function(){
  "use strict";
  const CITIES=Object.freeze(["mossoro","natal","fortaleza","recife"]);
  const LABELS=Object.freeze({
    natal:"NATAL / PARNAMIRIM",fortaleza:"FORTALEZA",
    recife:"RECIFE",mossoro:"MOSSORÓ",
  });
  const norm=value=>String(value??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .trim().toLowerCase().replace(/[\s/-]+/g,"_");
  const cityOf=value=>{
    const s=norm(value);
    if(["natal","parnamirim","ntl","pwm","natal_parnamirim"].includes(s))return "natal";
    if(["fortaleza","ftz"].includes(s))return "fortaleza";
    if(["recife","jcr","jaboatao","recife_jcr"].includes(s))return "recife";
    if(["mossoro","mro"].includes(s))return "mossoro";
    return null;
  };
  function classification(item){
    const d=item.decision||{},order=item.order||{};
    // Estado visual da fila: somente muda por evento de execução validado.
    // Não confundir pendente/em rota no TOA com execução ativa da automação.
    if(d.key==="confirmed" && (order.confirmationState==="confirmed"
      || order.imperiumAlreadyClosed===true))
      return {key:"confirmed",label:"Baixada no Imperium"};
    if(d.key==="confirmed") return {key:"review",label:"Conferir confirmação Imperium"};
    if (order.processingState === "error")
      return {key:"review",label:"Falha na tratativa"};
    if (order.processingState === "processing" && !d.review)
      return {key:"active",label:"Em tratamento agora"};
    if(d.review)return {key:"review",label:"Tratativa humana"};
    if(d.ready)return {key:"ready",label:"Aguardando baixa"};
    if(d.key==="future_window")return {key:"window",label:"Aguardar janela"};
    if(d.key==="cooldown" || d.key==="due"){
      const status=norm(order.toaStatus);
      if(["pendente","pending"].includes(status))return {key:"in_progress",label:"Pendente"};
      if(["em_rota","in_route","emrota"].includes(status))return {key:"in_progress",label:"Em rota"};
      if(["iniciada","iniciado","started","in_progress"].includes(status))
        return {key:"in_progress",label:"Iniciada"};
      return {key:"unverified",label:"Consulta elegível · sem confirmação"};
    }
    return {key:"unverified",label:"Dados pendentes de validação"};
  }
  function build(rows){
    const cities=Object.fromEntries(CITIES.map(id=>[id,{
      key:id,label:LABELS[id],items:[],
      counts:{active:0,confirmed:0,ready:0,in_progress:0,window:0,review:0,unverified:0},
    }]));
    const grouped=new Map(); let unknown=0,duplicates=0;
    for(const entry of Array.isArray(rows)?rows:[]){
      const order=entry?.order||{},city=cityOf(order.city);
      if(!city){unknown++;continue;}
      const id=[city,String(order.os||"").trim(),String(order.contract||"").trim()].join("|");
      const item={order,decision:entry.decision||{},classification:classification(entry)};
      if(!order.os || !order.contract){
        item.classification={key:"review",label:"Identificação incompleta"};
        cities[city].items.push(item);
        continue;
      }
      if(grouped.has(id)){
        duplicates++;
        const prior=grouped.get(id);
        if(prior.classification.key!==item.classification.key ||
          String(prior.decision.key)!==String(item.decision.key)){
          prior.classification={key:"review",label:"O.S. duplicada divergente"};
        }
        continue;
      }
      grouped.set(id,item);
      cities[city].items.push(item);
    }
    // Ativa no topo; falhas mais recentes logo abaixo; concluídas no rodapé.
    const priority={active:0,review:1,ready:2,in_progress:3,unverified:4,window:5,confirmed:6};
    for(const city of Object.values(cities)){
      city.items.sort((a,b)=>priority[a.classification.key]-priority[b.classification.key]
        || (a.classification.key==="review" ?
            (Number(b.order.queueSequence)||0)-(Number(a.order.queueSequence)||0) : 0)
        || (a.classification.key==="confirmed" ?
            (Number(b.order.queueSequence)||0)-(Number(a.order.queueSequence)||0) : 0)
        || (Number(a.order.queueSequence)||0)-(Number(b.order.queueSequence)||0)
        || String(a.order.os||"").localeCompare(String(b.order.os||""),"pt-BR",{numeric:true}));
      for(const item of city.items)city.counts[item.classification.key]++;
    }
    const totals=Object.values(cities).reduce((acc,city)=>{
      for(const [key,value] of Object.entries(city.counts)) acc[key]+=value;
      acc.os+=city.items.length;
      return acc;
    },{os:0,active:0,confirmed:0,ready:0,in_progress:0,window:0,review:0,unverified:0});
    return {cities,totals,unknown,duplicates};
  }
  return Object.freeze({CITIES,LABELS,cityOf,classification,build});
});