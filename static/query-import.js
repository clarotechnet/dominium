/* DOMINIUM: browser-only CSV/XLSX reader for Atlas equipment query exports.
   fflate 0.8.2 MIT is vendored; no uploads, no persistent client data. */
(function(global,factory) {
  const api=factory();
  if(typeof module==="object" && module.exports) module.exports=api;
  else global.DominiumQueryImport=api;
})(typeof window!=="undefined"?window:globalThis,function(){
  "use strict";
  const MAX_BYTES=8*1024*1024,MAX_ROWS=100000;
  const normalize=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase().replace(/[^A-Z0-9]+/g," ").trim();
  const aliases={
    serial:["NUMERO SERIE","NUMERO DE SERIE","NUM SERIE","SERIAL","SERIE","S N","NUMERO SERIAL","SERIAL NUMBER","N SERIE"],
    city:["CIDADE","PRACA","OPERACAO","POLO","REGIONAL","MUNICIPIO","LOCALIDADE"],
    location:["NOME DO LOCAL","LOCAL","ESTOQUE","DEPOSITO","ENDERECO PRINCIPAL","ENDERECO"],
    status:["ESTADO","SITUACAO","STATUS","SITUACAO DO EQUIPAMENTO","ESTADO EQUIPAMENTO"],
    model:["MODELO","DESCRICAO","EQUIPAMENTO","MATERIAL","CODIGO MATERIAL SAP"]
  };
  const exact=(header,list)=>list.some(x=>normalize(x)===normalize(header));
  const getField=(head,names)=>head.findIndex(h=>exact(h,names));
  function parseCsv(source){
    const first=source.replace(/^\uFEFF/,"").slice(0,3500);
    const delimiters=[";","\t",","];
    const score=delimiter=>(first.split(/\r?\n/).slice(0,3).reduce((sum,line)=>sum+line.split(delimiter).length-1,0));
    let sep=delimiters.sort((a,b)=>score(b)-score(a))[0];
    const rows=[],row=[];let field="",inQuotes=false;
    for(let i=0;i<source.length;i++){
      const c=source[i];
      if(c==='"'){
        if(inQuotes && source[i+1]==='"'){field+='"';i++;}else inQuotes=!inQuotes;
      }else if(!inQuotes && c===sep){row.push(field);field="";}
      else if(!inQuotes && (c==="\n"||c==="\r")){
        if(c==="\r"&&source[i+1]==="\n")i++;
        row.push(field);field="";
        if(row.some(x=>x.trim()))rows.push(row.slice());row.length=0;
        if(rows.length>MAX_ROWS+30)throw Error("Planilha acima do limite de linhas");
      }else field+=c;
    }
    row.push(field);if(row.some(x=>x.trim()))rows.push(row);
    return rows;
  }
  function decodeXml(s){
    return String(s??"").replace(/&#(x[0-9a-f]+|\d+);|&(?:amp|lt|gt|quot|apos);/gi,match=>{
      if(match.startsWith("&#")){const v=match.slice(2,-1);const num=v[0].toLowerCase()==="x"?parseInt(v.slice(1),16):parseInt(v,10);return Number.isInteger(num)&&num>0&&num<=0x10ffff?String.fromCodePoint(num):"";}
      return {"&amp;":"&","&lt;":"<","&gt;":">","&quot;":'"',"&apos;":"'"}[match]||match;
    });
  }
  function xmlText(s){return [...String(s||"").matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map(m=>decodeXml(m[1])).join("");}
  function sharedStrings(xml){return [...xml.matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)].map(m=>xmlText(m[1]));}
  function parseSheet(xml,shared){
    const rows=[];let count=0;
    for(const match of xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)){
      const values=[];const row=match[1];
      for(const cell of row.matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)){
        const ref=/\br="([A-Z]+)\d+"/.exec(cell[1]);if(!ref)continue;
        let index=0;for(const chr of ref[1])index=index*26+chr.charCodeAt(0)-64;
        index--;if(index>=150)continue;
        let data=/\b(?:t)="([^"]+)"/.exec(cell[1]);let t=data?data[1]:"";
        const v=/<v\b[^>]*>([\s\S]*?)<\/v>/.exec(cell[2]);
        if(t==="inlineStr")values[index]=xmlText(cell[2]);
        else if(t==="s"&&v)values[index]=shared[Number(v[1])]||"";
        else if(t==="str"&&v)values[index]=decodeXml(v[1]);
        else if(v){values[index]=decodeXml(v[1]);}
      }
      if(values.some(v=>String(v||"").trim()))rows.push(values);
      if(++count>MAX_ROWS+30)throw Error("Planilha excede 100 mil linhas");
    }
    return rows;
  }
  function parseXlsx(buffer,unzip){
    if(typeof unzip!=="function")throw Error("Leitor XLSX indisponível");
    // Only inflate worksheet XML and shared strings; block oversized XML parts.
    let totalExpanded=0;
    const files=unzip(new Uint8Array(buffer),{filter:f=>{
      const n=String(f.name||"");
      const bytes=Number(f.originalSize||0);
      const allowed=/^xl\/(sharedStrings\.xml|worksheets\/sheet\d+\.xml)$/i.test(n)
        && Number.isFinite(bytes) && bytes<=24*1024*1024
        && totalExpanded+bytes<=48*1024*1024;
      if(allowed)totalExpanded+=bytes;
      return allowed;
    }});
    const entries=Object.entries(files).filter(([name])=>/xl\/worksheets\/sheet\d+\.xml$/i.test(name));
    if(!entries.length||entries.length>20)throw Error("Planilha XLSX não possui abas válidas");
    const readXml=bytes=>{
      if(bytes.byteLength>24*1024*1024)throw Error("Conteúdo XLSX acima do limite");
      return new TextDecoder("utf-8").decode(bytes);
    };
    const dict=Object.entries(files).find(([name])=>/xl\/sharedStrings\.xml$/i.test(name));
    const shared=dict?sharedStrings(readXml(dict[1])):[];
    const sheets=entries.map(([name,bytes])=>{
      const rows=parseSheet(readXml(bytes),shared);
      return {name,rows};
    });
    sheets.sort((a,b)=>scoreTable(b.rows)-scoreTable(a.rows));
    return sheets[0].rows;
  }
  function scoreTable(rows){
    return rows.slice(0,25).reduce((s,row)=>s+(getField(row,aliases.serial)>=0?100:0)+
      (getField(row,aliases.status)>=0?5:0)+(getField(row,aliases.city)>=0?4:0),0);
  }
  function toRecords(rows){
    const headIndex=rows.findIndex(row=>getField(row,aliases.serial)>=0);
    if(headIndex<0||headIndex>=30)throw Error("Coluna de serial não identificada. A planilha deve ter 'Número Série' ou 'Serial'.");
    const head=rows[headIndex].map(x=>String(x??"").trim());
    const ix=Object.fromEntries(Object.entries(aliases).map(([key,names])=>[key,getField(head,names)]));
    let records=[],numericRisk=0;
    for(const row of rows.slice(headIndex+1)){
      let raw=String(row[ix.serial]??"").trim();
      if(!raw)continue;
      if(/^\d+(?:\.\d+)?E\+\d+$/i.test(raw)){numericRisk++;continue;}
      const serial=raw.toUpperCase().replace(/\s+/g,"");
      if(!/^[A-Z0-9._/-]{4,50}$/.test(serial))continue;
      const get=key=>ix[key]<0?"":String(row[ix[key]]??"").trim();
      records.push({serial,city:get("city"),location:get("location"),
        status:get("status"),model:get("model")});
      if(records.length>MAX_ROWS)throw Error("Limite de 100 mil equipamentos excedido");
    }
    if(!records.length)throw Error("Nenhum serial reconhecido no arquivo");
    return {records,hasCity:ix.city>=0,hasLocation:ix.location>=0,
      hasStatus:ix.status>=0,numericRisk,header:head};
  }
  async function read(file){
    if(!file||file.size>MAX_BYTES)throw Error("Arquivo deve ter no máximo 8 MB");
    const ext=String(file.name||"").toLowerCase().split(".").pop();
    if(!["xlsx","csv","txt","tsv"].includes(ext))throw Error("Use uma planilha .xlsx ou .csv");
    const bytes=await file.arrayBuffer();let rows;
    if(ext==="xlsx"){
      const unzip=(typeof window!=="undefined"?window.fflate:globalThis.fflate)?.unzipSync;
      rows=parseXlsx(bytes,unzip);
    }else{
      const utf8=new TextDecoder("utf-8").decode(bytes);
      const sample=(utf8.match(/\uFFFD/g)||[]).length;
      const txt=sample>5?new TextDecoder("windows-1252").decode(bytes):utf8;
      rows=parseCsv(txt);
    }
    return toRecords(rows);
  }
  function filter(data,{city="",status="",location="",assumeCity=false}={}){
    const source=data.records||[];
    const requested=normalize(city);
    const result=source.filter(row=>{
      if(status && normalize(row.status)!==normalize(status))return false;
      if(location && normalize(row.location)!==normalize(location))return false;
      if(requested && data.hasCity){
        if(normalize(row.city).includes(requested))return true;
        return false;
      }
      if(requested && !data.hasCity && !assumeCity)return false;
      return true;
    });
    return [...new Set(result.map(x=>x.serial))];
  }
  return {parseCsv,parseXlsx,toRecords,filter,normalize,read};
});
