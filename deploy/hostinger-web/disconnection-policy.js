'use strict';
function allowedRoute(method,raw){
  const url=new URL(raw,'http://dominium.invalid');
  const route=url.pathname.slice('/api/disconnection/'.length);
  if(!url.pathname.startsWith('/api/disconnection/')||url.hash)throw new Error('Rota DESC inválida');
  const allowed=method==='GET'?['state','history','report.xlsx','reports']:method==='POST'?['decision','refresh','technician','manual','serial-lookup','serial-apply','reports']:[];
  if(!allowed.includes(route)&&!(method==='GET'&&/^photo\/[a-f0-9-]{36}\.jpg$/.test(route)))throw new Error('Rota DESC não permitida');
  const params=[...url.searchParams];
  if(route==='history'&&!(params.length===1&&params[0][0]==='date'&&/^\d{4}-\d{2}-\d{2}$/.test(params[0][1])))throw new Error('Data de histórico inválida');
  if(route!=='history'&&params.length&&(route!=='report.xlsx'||params.length!==1||params[0][0]!=='month'||!/^\d{4}-(0[1-9]|1[0-2])$/.test(params[0][1])))throw new Error('Parâmetros DESC inválidos');
  return url.pathname+url.search;
}
module.exports={allowedRoute};
