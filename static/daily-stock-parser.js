/* Parser local de planilhas SAPUI5: usa apenas C(Material), D(Descr.) e F(Utilizacao Livre). */
(function(root) {
  "use strict";
  const dec = new TextDecoder("utf-8");
  const escapeDecode = (s) => String(s || "")
    .replace(/&#(x[0-9a-f]+|[0-9]+);/gi, (_,code) =>
      String.fromCodePoint(code[0].toLowerCase()==="x"?parseInt(code.slice(1),16):Number(code)))
    .replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,"<")
    .replace(/&gt;/g,">").replace(/&amp;/g,"&");
  function innerText(xml) {
    return [...String(xml).matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)]
      .map(m=>escapeDecode(m[1])).join("");
  }
  function parseQuantity(source, numericCell=false) {
    const raw=String(source??"").trim().replace(/\s/g,"");
    if (!raw) throw Error("Quantidade em branco");
    let text=raw;
    if (!numericCell) {
      if (/^\d{1,3}(?:\.\d{3})+(?:,\d{1,3})?$/.test(text))
        text=text.replace(/\./g,"").replace(",",".");
      else if (/^\d+(?:,\d{1,3})?$/.test(text))
        text=text.replace(",",".");
    }
    if (!/^\d+(?:\.\d{1,3})?$/.test(text)) throw Error("Quantidade inválida: "+raw);
    const value=Number(text);
    if (!Number.isFinite(value) || value>999999999999 || value<0) throw Error("Quantidade fora do limite");
    return Math.round(value*1000)/1000;
  }
  function normalizeMaterial(raw) {
    const s=String(raw??"").trim();
    if (!/^\d{1,32}$/.test(s)) throw Error("Código do material inválido: "+s);
    return s.replace(/^0+/,"")||"0";
  }
  function readExcelXml(sheetXml,sharedXml) {
    const strings=[...String(sharedXml||"").matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)]
      .map(m=>innerText(m[1]));
    const rows=[];
    for (const match of String(sheetXml).matchAll(/<row\b([^>]*)>([\s\S]*?)<\/row>/g)) {
      const record={};
      for(const m of match[2].matchAll(/<c\b([^>]*?)>([\s\S]*?)<\/c>/g)) {
        const ref=m[1].match(/\br="([A-Z]+)\d+"/);
        if(!ref || !["C","D","F"].includes(ref[1])) continue;
        if(/<f\b/.test(m[2])) throw Error("Fórmula não permitida nas três colunas obrigatórias");
        const type=m[1].match(/\bt="([^"]+)"/)?.[1]||"n";
        const value=m[2].match(/<v(?:\s[^>]*)?>([\s\S]*?)<\/v>/)?.[1]||"";
        record[ref[1]]={
          value:type==="s"?strings[Number(value)]:type==="inlineStr"?innerText(m[2]):escapeDecode(value),
          numeric:type==="n"
        };
      }
      rows.push(record);
    }
    if(!rows.length ||
       String(rows[0].C?.value||"").trim().toLowerCase()!=="material" ||
       !String(rows[0].D?.value||"").toLowerCase().includes("descr.") ||
       !String(rows[0].F?.value||"").toLowerCase().includes("utilização livre")) {
      throw Error("Cabeçalho diferente do esperado: Material (C), Descr. Material (D), Qtd - Utilização Livre (F)");
    }
    const unique=new Map(); let rowCount=0;let totalMillis=0;
    rows.slice(1).forEach((row,index)=>{
      if(!row.C?.value && !row.D?.value && !row.F?.value) return;
      try {
        const material=normalizeMaterial(row.C?.value);
        const descricao=String(row.D?.value??"").trim().replace(/\s+/g," ");
        if(!descricao || descricao.length>500) throw Error("Descrição ausente ou longa demais");
        const quant=parseQuantity(row.F?.value,row.F?.numeric);
        const millis=Math.round(quant*1000);
        const previous=unique.get(material);
        if(previous && previous.descricao_material!==descricao)
          throw Error("Descrição divergente para o material "+material);
        if(previous) previous.millis+=millis;
        else unique.set(material,{material,descricao_material:descricao,millis});
        totalMillis+=millis;rowCount++;
      } catch(error){throw Error("Linha "+(index+2)+": "+error.message);}
    });
    if(!rowCount || unique.size>10000) throw Error("Planilha vazia ou muito grande");
    const items=[...unique.values()].map(row=>({
      material:row.material,descricao_material:row.descricao_material,
      quantidade_livre:(row.millis/1000).toFixed(3)
    })).sort((a,b)=>a.material.localeCompare(b.material, "pt-BR", {numeric:true}));
    return {items,linhas_origem:rowCount,materiais_distintos:items.length,
      quantidade_total:(totalMillis/1000).toFixed(3)};
  }
  async function parseXlsx(file,unzip) {
    if(!/\.xlsx$/i.test(file.name||"")) throw Error("Envie uma planilha .xlsx");
    if(file.size>8*1024*1024) throw Error("Arquivo maior que 8 MB");
    const buf=await file.arrayBuffer();
    const bytes=new Uint8Array(buf);
    if(bytes[0]!==0x50||bytes[1]!==0x4b) throw Error("Arquivo Excel inválido");
    const entries=(unzip||root.fflate?.unzipSync)?.(bytes);
    if(!entries) throw Error("Leitor Excel indisponível (fflate)");
    const sheet=entries["xl/worksheets/sheet1.xml"];
    if(!sheet) throw Error("A primeira aba do Excel não foi encontrada");
    const report=readExcelXml(dec.decode(sheet),entries["xl/sharedStrings.xml"]
      ?dec.decode(entries["xl/sharedStrings.xml"]):"");
    const hash=await crypto.subtle.digest("SHA-256",bytes);
    report.hash_arquivo=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,"0")).join("");
    report.nome_arquivo=String(file.name).slice(0,180);
    return report;
  }
  const api={readExcelXml,parseQuantity,normalizeMaterial,parseXlsx};
  root.DominiumDailyStockParser=api;
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window==="undefined"?globalThis:window);
