/* DOMINIUM — Tratativa Claro, painel por cidade.
 * Consome APENAS os dados ja calculados pelo modulo Análise Backlog.
 * Nao envia baixa, nao consulta TOA, nao interpreta historico como baixa de hoje.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DominiumClaroTreatment = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  const CITY_ORDER = Object.freeze(["natal", "fortaleza", "recife", "mossoro"]);
  const LABELS = Object.freeze({
    natal:"NATAL / PARNAMIRIM", fortaleza:"FORTALEZA",
    recife:"RECIFE", mossoro:"MOSSORÓ",
  });
  const tidy = s => String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toUpperCase();
  function cityFor(row) {
    // A sigla do arquivo de rota é mais confiável do que a cidade normalizada.
    const file = tidy(row?.route_file || row?.filename || "");
    const match = file.match(/(?:^|[-_.])(NTL|PWM|FTZ|JCR|MRO)(?:[-_.]|$)/);
    const fromFile = {NTL:"natal",PWM:"natal",FTZ:"fortaleza",JCR:"recife",MRO:"mossoro"}[match?.[1]];
    if (fromFile) return fromFile;
    const value = tidy(row?.report_city || row?.city || row?.profile || "");
    if (value.includes("PARNAMIRIM") || value.includes("NATAL") || value==="NTL" || value==="PWM") return "natal";
    if (value.includes("FORTALEZA") || value==="FTZ") return "fortaleza";
    if (value.includes("RECIFE") || value.includes("JABOATAO") || value==="JCR") return "recife";
    if (value.includes("MOSSORO") || value==="MRO") return "mossoro";
    return null;
  }
  function statusFor(row) {
    const t=tidy(row?.treatment), code=String(row?.validated_code || "").trim();
    if (t.startsWith("DIVERGENCIA") || t.startsWith("ERRO") || t.includes("SEM CONFIRMACAO"))
      return {key:"review",label:"Tratar divergência"};
    if (t==="IMPRODUTIVA CONFIRMADA") {
      // 430 (retirada produtiva) jamais é improdutiva; ausência de código
      // comprovado também bloqueia qualquer afirmação de baixa.
      if (!code || ["409","430","512"].includes(code))
        return {key:"review",label:"Revisar código/baixa"};
      return {key:"improductive",label:"Improdutiva confirmada"};
    }
    if (t==="PENDENTE") return {key:"pending",label:"Pendente · não iniciada"};
    if (t.includes("PRODUTIVA") || t.includes("CONCLUIDA"))
      return {key:"productive",label:"Concluída / produtiva"};
    return {key:"review",label:"Verificar no Imperium"};
  }
  function build(rows) {
    const cities=Object.fromEntries(CITY_ORDER.map(key=>[key,{
      key,label:LABELS[key],rows:[],counts:{improductive:0,productive:0,pending:0,review:0},
    }]));
    const seen=new Map(),unknown= [];
    for(const row of Array.isArray(rows)?rows:[]) {
      const city=cityFor(row);
      if(!city){unknown.push(row);continue;}
      const contract=String(row.contract || "").replace(/\D/g,"");
      const os=String(row.os_number || "").replace(/\D/g,"");
      const stable=contract && os ? city+"|"+contract+"|"+os : "";
      const status=statusFor(row);
      if(!stable) {
        cities[city].rows.push({...row,cityKey:city,status:{key:"review",label:"O.S./contrato ausente"}});
        cities[city].counts.review++;
        continue;
      }
      const existing=seen.get(stable);
      if(existing) {
        if(existing.status.key!==status.key
          || (existing.status.key==="improductive" && String(existing.validated_code)!==String(row.validated_code))) {
          existing.status={key:"review",label:"Registros divergentes · revisar"};
        }
        continue;
      }
      const item={...row,contract,os_number:os,cityKey:city,status};
      seen.set(stable,item);
    }
    for(const item of seen.values()) {
      cities[item.cityKey].rows.push(item);
      cities[item.cityKey].counts[item.status.key]++;
    }
    for(const city of Object.values(cities)){
      city.rows.sort((a,b)=>{
        const priority={review:0,improductive:1,pending:2,productive:3};
        return priority[a.status.key]-priority[b.status.key]
          || String(a.technician||"").localeCompare(String(b.technician||""),"pt-BR")
          || a.contract.localeCompare(b.contract,"pt-BR",{numeric:true});
      });
    }
    const totals=Object.values(cities).reduce((o,c)=>{
      o.records+=c.rows.length;
      for(const [k,v] of Object.entries(c.counts))o[k]+=v;
      return o;
    },{records:0,improductive:0,productive:0,pending:0,review:0});
    totals.unknown=unknown.length;
    return {cities,totals,sourceRows:Array.isArray(rows)?rows.length:0};
  }
  function exportCsv(model,city="all"){
    const selected=city==="all"?CITY_ORDER.flatMap(c=>model.cities[c].rows)
      :model.cities[city]?.rows || [];
    const quote=v=>{
      let value=String(v??"").replace(/[\r\n]/g," ").slice(0,250);
      if (/^\s*[=+@\-]/.test(value)) value="'"+value;
      return '"'+value.replace(/"/g,'""')+'"';
    };
    const lines=[["Cidade","Contrato","OS","Tecnico","Tratativa","Status","Codigo Validado"].map(quote).join(";")];
    for(const row of selected)lines.push([
      LABELS[row.cityKey],row.contract,row.os_number,row.technician,row.treatment,
      row.status.label,row.validated_code,
    ].map(quote).join(";"));
    return "\uFEFF"+lines.join("\r\n");
  }
  return Object.freeze({CITY_ORDER,LABELS,cityFor,statusFor,build,exportCsv});
});
