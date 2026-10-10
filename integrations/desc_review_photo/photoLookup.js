'use strict';
const {resolveAtlas}=require('./core');
const {compact,validCandidate}=require('./serialCandidates');
function entriesOf(result){return result?.resultadosAtlas?.length?result.resultadosAtlas:result?.retorno?.ok&&result.retorno.resultado?[{serialSolicitado:result.serialUsado,resultado:result.retorno.resultado}]:[];}
function createPhotoLookup({readBarcode,readOcr,lookupSerials,primaryLookup}){
 return async function lookup(buffer){
  if(!Buffer.isBuffer(buffer)||!buffer.length||buffer.length>15*1024*1024)throw new Error('Foto ausente ou maior que 15 MB');
  const started=Date.now(),reading={stage:'pending',source:'barcode',candidates:[],confirmed:[],attempts:0,errors:[]};
  const seen=new Set();let last=null,entries=[],invalid=false,atlasFailed=false;
  const finish=(stage,message)=>({...(last||{}),resultadosAtlas:entries,photoReading:{...reading,stage,message,elapsed_ms:Date.now()-started},retorno:entries.length?last?.retorno:{ok:false,error:message}});
  if(primaryLookup){
   try{
    last=await primaryLookup(buffer);
    const candidates=[...new Set((last?.seriaisDetectados||[]).map(compact).filter(validCandidate))];
    const found=entriesOf(last);
    reading.source='existing-atlas-reader';
    reading.candidates=candidates.map(value=>({value,source:'barcode'}));
    if(found.length){
     const covered=new Set();
     for(const entry of found){
      const a=entry.resultado||entry;
      const identifiers=[a.serial_baixavel,...(a.enderecaveis||[]),...(a.serial_encontrado===true?[a.serial_consultado]:[])].map(compact);
      const matched=candidates.find(value=>identifiers.includes(value));
      if(!matched){invalid=true;reading.errors.push('Atlas: resultado não pertence aos identificadores desta foto');continue;}
      try{const resolved=resolveAtlas(entry);entries.push(entry);identifiers.forEach(value=>covered.add(value));reading.confirmed.push({candidate:matched,serial:resolved.serial,contract:resolved.contract,type:resolved.type});}
      catch(error){invalid=true;reading.errors.push(error.message);}
     }
     const incomplete=(last?.tentativas||[]).some(attempt=>attempt.ok===false&&/offline|timeout|indispon|conex[aã]o/i.test(String(attempt.error||'')));
     if(incomplete)return finish('atlas_error','Consulta Atlas incompleta; reconsulte as evidências');
     if(!invalid&&entries.length&&candidates.every(value=>covered.has(value)))return finish('confirmed','Equipamento confirmado pelo leitor Atlas existente');
     return finish('atlas_unconfirmed','Atlas não confirmou todos os identificadores da foto; confira as evidências');
    }
    const error=String(last?.retorno?.error||'');
    if(/offline|timeout|indispon|conex[aã]o/i.test(error))return finish('atlas_error','Atlas indisponível; reconsulte as evidências');
    reading.candidates=[];
   }catch(error){reading.errors.push('Leitor Atlas: '+error.message);}
  }
  async function consult(candidates){
   const fresh=candidates.filter(c=>validCandidate(c.value)&&!seen.has(compact(c.value))).slice(0,Math.max(0,12-reading.candidates.length));
   if(!fresh.length)return;
   fresh.forEach(c=>{c.value=compact(c.value);seen.add(c.value);reading.candidates.push(c);});
   try{last=await lookupSerials(fresh.map(c=>c.value));}catch(e){atlasFailed=true;reading.errors.push('Atlas: '+e.message);return;}
   if(!entriesOf(last).length){const error=last?.retorno?.error||'nenhum registro confirmado';if(/offline|timeout|tempo limite|indispon|interrompid|conex[aã]o/i.test(error))atlasFailed=true;reading.errors.push('Atlas: '+error);return;}
   for(const entry of entriesOf(last)){
    const a=entry.resultado||entry;
    // A query echo does not prove equipment identity. Use fetched addressables.
    const identifiers=[a.serial_baixavel,...(a.enderecaveis||[])].map(compact);
    if(a.serial_encontrado===true)identifiers.push(compact(a.serial_consultado));
    const matched=fresh.find(c=>identifiers.includes(c.value));
    if(!matched){invalid=true;reading.errors.push('Atlas: resposta não corresponde aos candidatos desta foto');continue;}
    entries.push(entry);
    identifiers.filter(Boolean).forEach(v=>seen.add(v));
    try{const confirmed=resolveAtlas(entry);reading.confirmed.push({candidate:matched.value,serial:confirmed.serial,contract:confirmed.contract,type:confirmed.type});}
    catch(e){invalid=true;reading.errors.push(e.message);}
   }
   const covered=new Set(entriesOf(last).flatMap(entry=>{const a=entry.resultado||entry;return [a.serial_baixavel,...(a.enderecaveis||[]),...(a.serial_encontrado===true?[a.serial_consultado]:[])].map(compact);}));
   for(const attempt of last?.tentativas||[]){
    if(attempt.ok!==false||covered.has(compact(attempt.serial))||!fresh.some(c=>c.value===compact(attempt.serial)))continue;
    if(/offline|timeout|tempo limite|indispon|interrompid|conex[aã]o|bridge.*(?:caiu|congestionado)/i.test(String(attempt.error||''))){atlasFailed=true;reading.errors.push('Atlas: '+attempt.serial+': '+attempt.error);}
   }
  }
  let bars;
  try{bars=primaryLookup?[]:await readBarcode(buffer);}catch(e){reading.errors.push('Código de barras: '+e.message);}
  if(Array.isArray(bars))await consult(bars.map(x=>({value:compact(x.valor),source:'barcode'})));
  else if(bars?.error)reading.errors.push('Código de barras: '+bars.error);
  if(!entries.length&&/offline|timeout|tempo limite|bridge.*indispon/i.test(reading.errors.join(' '))&&reading.candidates.length)return finish('atlas_error','Atlas indisponível ou consulta excedeu o tempo; reconsulte as evidências');
  reading.source=entries.length?'barcode+ocr':'ocr';let ocr;
  try{ocr=await readOcr(buffer);reading.attempts=ocr.attempts||0;reading.partial=ocr.partial===true;}
  catch(e){reading.errors.push('OCR: '+e.message);return finish('ocr_error','Falha ao processar OCR: '+e.message);}
  await consult(ocr.candidates||[]);
  if(atlasFailed)return finish('atlas_error','Consulta Atlas incompleta; reconsulte as evidências');
  if(reading.partial)return finish('ocr_partial','Tempo de leitura esgotado antes de conferir todos os recortes; revise ou reconsulte a foto');
  if(entries.length)return finish(invalid?'atlas_unconfirmed':'confirmed',invalid?'Atlas retornou equipamento sem confirmação única; confira as evidências':'Equipamento confirmado no Atlas');
  if(invalid)return finish('atlas_unconfirmed','Atlas não confirmou que o resultado pertence aos identificadores desta foto');
  if(!reading.candidates.length)return finish(ocr.error?'ocr_error':'no_identifier',ocr.error?'Falha ao processar OCR: '+ocr.error:'Nenhum identificador de equipamento legível; foto preservada para revisão');
  return finish(/offline|timeout|tempo limite|indispon/i.test(reading.errors.join(' '))?'atlas_error':'atlas_not_found','Identificadores lidos, mas Atlas não confirmou o equipamento');
 };
}
module.exports={createPhotoLookup,entriesOf};
