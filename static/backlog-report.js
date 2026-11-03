/* Read-only WhatsApp report derived from the route × historical-code comparison.
   No order close, inventory write, or WhatsApp send is performed. */
(function(root, factory){
  "use strict";
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  else root.DominiumBacklogReport=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const CITIES=["NATAL","PARNAMIRIM","FORTALEZA","RECIFE","MOSSORO"];
  const LABELS={NATAL:"NATAL/RN",PARNAMIRIM:"PARNAMIRIM/RN",FORTALEZA:"FORTALEZA/CE",RECIFE:"RECIFE/PE",MOSSORO:"MOSSORÓ/RN"};
  const SOURCE={NTL:"NATAL",PWM:"PARNAMIRIM",FTZ:"FORTALEZA",JCR:"RECIFE",MRO:"MOSSORO"};
  const clean=value=>String(value??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").trim().toUpperCase();

  function reportCity(row){
    const fromFile=String(row.route_file||row.filename||"").toUpperCase().match(/(?:^|[-_])(NTL|PWM|FTZ|JCR|MRO)(?:[-_.])/);
    if(fromFile)return SOURCE[fromFile[1]];
    const raw=clean(row.report_city||row.city);
    if(raw==="JABOATAO DOS GUARARAPES")return "RECIFE";
    if(raw==="MOSSORO")return "MOSSORO";
    if(raw==="NATAL/PARNAMIRIM")return "NATAL"; // Rotas antigas sem origem de arquivo
    return raw;
  }
  function withinScope(row,scope){
    const city=reportCity(row);
    if(scope==="all")return true;
    if(scope==="natal")return city==="NATAL"||city==="PARNAMIRIM";
    if(scope==="fortaleza")return city==="FORTALEZA";
    if(scope==="mossoro")return city==="MOSSORO";
    if(scope==="recife")return city==="RECIFE";
    return false;
  }
  function filterRows(rows,scope){
    return (rows||[]).filter(row=>withinScope(row,scope));
  }
  function formatDate(value){
    const s=String(value||"").trim();
    const iso=s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
    if(iso)return iso[3]+"/"+iso[2]+"/"+iso[1]+(iso[4]?" "+iso[4]+":"+iso[5]:"");
    return s||"Data não disponível";
  }
  function build(rows,scope="all",selectedCodes=["101","306","404","430"]){
    const allowed=new Set(selectedCodes.map(String));
    const matches=filterRows(rows,scope).filter(row=>
      row.classification==="SEGURAR"&&allowed.has(String(row.historical_code||"")));
    // A rota pode repetir o mesmo contrato ou a mesma O.S. nas planilhas.
    const unique=new Map();
    for(const row of matches){
      const city=reportCity(row);
      const technician=String(row.technician||"SEM TÉCNICO").trim()||"SEM TÉCNICO";
      const contract=String(row.contract||"").replace(/\D/g,"");
      if(!contract)continue;
      const key=[city,clean(technician),contract].join("|");
      const existing=unique.get(key);
      if(!existing||String(row.historical_date||"")>String(existing.historical_date||""))
        unique.set(key,{...row,report_city:city,technician,contract});
    }
    const groups=[];
    for(const city of CITIES){
      const items=[...unique.values()].filter(r=>r.report_city===city);
      if(!items.length)continue;
      const codeCounts={};
      for(const item of items)codeCounts[item.historical_code]=(codeCounts[item.historical_code]||0)+1;
      const byTechnician=new Map();
      for(const item of items){
        if(!byTechnician.has(item.technician))byTechnician.set(item.technician,[]);
        byTechnician.get(item.technician).push(item);
      }
      const technicians=[...byTechnician.entries()].map(([name,contracts])=>({
        name,contracts:contracts.sort((a,b)=>a.contract.localeCompare(b.contract,{numeric:true}))
      })).sort((a,b)=>b.contracts.length-a.contracts.length||a.name.localeCompare(b.name,"pt-BR"));
      groups.push({city,label:LABELS[city],count:items.length,codeCounts,technicians});
    }
    return {groups,total:[...unique.values()].length,codes:[...allowed]};
  }
  function toWhatsApp(report){
    const lines=["📋 RELATÓRIO DE CONTRATOS PARA SEGURAR",
      "Histórico do Imperium × rota do dia",
      "Códigos selecionados: "+report.codes.join(", ")];
    if(!report.total)return lines.concat(["","Nenhum contrato com histórico correspondente no filtro atual."]).join("\n");
    for(const group of report.groups){
      lines.push("","━━━━━━━━━━━━━━━━━━━━━━","📍 "+group.label,"━━━━━━━━━━━━━━━━━━━━━━");
      for(const tech of group.technicians){
        lines.push("","👤 "+tech.name,"🔹 "+tech.contracts.length+" contrato(s) com histórico selecionado");
        for(const row of tech.contracts){
          lines.push("","• Contrato: "+row.contract,
            "  📌 Baixa histórica: "+row.historical_code,
            "  📅 Data: "+formatDate(row.historical_date));
        }
      }
    }
    lines.push("","Obs.: código 430 é retirada produtiva. A lista indica histórico correspondente, não uma nova baixa.");
    return lines.join("\n");
  }
  return {CITIES,LABELS,reportCity,withinScope,filterRows,formatDate,build,toWhatsApp};
});
