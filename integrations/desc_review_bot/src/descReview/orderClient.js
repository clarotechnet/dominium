'use strict';
const fs=require('node:fs');
const {day}=require('./core');
function createOrderVerifier({connectionFile,fetchImpl=global.fetch}){
  return async(batch,snapshot)=>{
    let config,origin;
    try{
      config=JSON.parse(fs.readFileSync(connectionFile,'utf8'));
      origin=new URL(config.origin);
      if(origin.protocol!=='https:'||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash||!/^\S{24,256}$/.test(config.token||''))throw new Error('config');
    }catch{throw new Error('Imperium: conexão privada da consulta não configurada');}
    const numbers=[...new Set((snapshot?.tasks||[]).filter(t=>['400','409','430','512','706'].includes(String(t.close_code||t.codigo_baixa||snapshot.current_close_code))).map(t=>String(t.os_number||t.num_os||'')))];
    let response;
    try{response=await fetchImpl(new URL('/internal/order-check',origin),{method:'POST',redirect:'error',signal:AbortSignal.timeout(120000),headers:{'Content-Type':'application/json',Authorization:'Bearer '+config.token,'X-Dominium-Actor':encodeURIComponent('BotDMV DESC leitura')},body:JSON.stringify({profile_key:batch.profile,contract:batch.contract,date:day(batch.created_at),os_numbers:numbers})});}catch{throw new Error('Imperium: consulta da OS indisponível ou excedeu o prazo');}
    if(!response.ok)throw new Error('Imperium: OS e recurso não confirmados (HTTP '+response.status+')');
    let result;try{const raw=await response.text();if(Buffer.byteLength(raw)>65536)throw new Error('large');result=JSON.parse(raw);}catch{throw new Error('Imperium: resposta da consulta inválida');}
    if(result.ok!==true||result.confirmed!==true||result.searched!==true||!Array.isArray(result.orders))throw new Error('Imperium: consulta não confirmada');
    return result;
  };
}
module.exports={createOrderVerifier};
