/* Contratos do gerador original de Fora de Rota, sem acesso a dados reais. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const root=path.join(__dirname,"..");
const src=fs.readFileSync(path.join(root,"static","backlog-fora-rota.js"),"utf8");
const ctx={
  document:{addEventListener(){}},
  window:{__DOMINIUM_FORA_ROTA_TEST__:true},
  XLSX:{utils:{sheet_to_json(sheet){return sheet.rows;}}},
  console
};
ctx.globalThis=ctx;
vm.runInNewContext(src,ctx,{filename:"backlog-fora-rota.js",timeout:3000});
const api=ctx.DominiumForaRotaTestHooks;
assert.ok(api,"test hooks for pure parser functions");
const sorted=api.buildClean106Contracts({
 "123456":[{code:"101",sortKey:10,rowOrder:0},{code:"106",sortKey:20,rowOrder:1}],
 "234567":[{code:"430",sortKey:1,rowOrder:0},{code:"106",sortKey:25,rowOrder:1}],
 "345678":[{code:"106",sortKey:10,rowOrder:0},{code:"101",sortKey:30,rowOrder:1}],
 "456789":[{code:"106",sortKey:50,rowOrder:0}],
 "567890":[{code:"101",sortKey:50,rowOrder:2},{code:"106",sortKey:50,rowOrder:3}],
 "678901":[{code:"106",sortKey:50,rowOrder:0},{code:"430",sortKey:60,rowOrder:1}]
});
assert.deepEqual(Array.from(sorted),["123456","456789","567890"],
  "106 must be latest and contracts with ANY 430 are excluded");
const claroSheet={
  rows:[
    ["BASE_CD_NET","CD_NET","NM_CIDADE","NOME","ENDERECO","BAIRRO","CEP","NR_MAC","DDD","TEL NETSMS","DX22"],
    ["NTL_123456","123456","Natal","Cliente A","Rua 1","Alecrim","59000000","EQ01","84","999998888",""],
    ["NTL_123456","123456","Natal","Cliente A","Rua 1","Alecrim","59000000","EQ02","84","999998888",""],
    ["FZE_123456","123456","Fortaleza","Cliente B","Rua 2","Centro","60000000","EQ03","85","988887777",""]
  ]
};
const records=api.parseClaroBacklog({SheetNames:["Safra dados EPO"],Sheets:{"Safra dados EPO":claroSheet}});
assert.equal(records.length,2,"same contract in different bases must remain distinct");
const natal=records.find(r=>r.city==="NATAL"),fortaleza=records.find(r=>r.city==="FORTALEZA");
assert.ok(natal&&fortaleza);
assert.equal(natal.contract,"123456");
assert.match(natal.equipment,/EQ01/);
assert.match(natal.equipment,/EQ02/);
assert.equal(fortaleza.equipment,"EQ03");
assert.equal(api.extractSafraContract("NTL_123456"),"123456");
assert.equal(api.normalizeContract("12.345-6"),"123456");
const workbook={
  SheetNames:["Historico"],
  Sheets:{Historico:{rows:[
    ["Num Contrato","Cod Baixa","Data da Baixa"],
    ["123456","101","20/11/2026 08:00"],
    ["123456","106","21/11/2026 08:00"],
    ["234567","430","20/11/2026 08:00"],
    ["234567","106","21/11/2026 08:00"],
  ]}}
};
const hist=api.parseImperiumBacklog(workbook);
assert.deepEqual(Array.from(api.buildClean106Contracts(hist)),["123456"]);
const html=fs.readFileSync(path.join(root,"static","index.html"),"utf8");
for(const id of ["foraRotaInput","foraRotaImperiumInput","foraRotaCidadeSelect",
  "foraRotaBairroSelect","foraRotaQuantidadeInput","foraRotaTecnicoInput",
  "foraRotaGerarButton","foraRotaMarcarButton","foraRotaOutput","foraRotaTrackingRoot"])
  assert.ok(html.includes('id="'+id+'"'),"missing id "+id);
assert.ok(html.includes("/backlog-fora-rota.js"));
assert.ok(src.includes("/vendor/xlsx.full.min.js"));
assert.ok(src.includes("'/api/backlog/year/sent'"));
assert.ok(!src.includes("fetch('/api/fora-rota/sent"),"must not call legacy API");
console.log("OK: 106 limpo, no 430, BASE_CD_NET, city isolation, HTML and API wiring");

(async()=>{
  // Teste da chamada real de registro atraves de um servidor falso; nenhuma OS real.
  const writes=[],serverRows=[];
  ctx.sessionStorage={setItem(){},getItem(){return null;}};
  ctx.request=async(path,options={})=>{
    assert.equal(path,"/api/backlog/year/sent");
    if(!options.method) return {rows:serverRows.slice()};
    assert.equal(options.method,"POST");
    const body=JSON.parse(options.body);
    writes.push(body);
    serverRows.push({profile:body.profile,contract:body.contract,note:body.note,sent_at:"2026-11-23T12:00:00Z"});
    return {ok:true};
  };
  Object.assign(api.state,{
    claroRecords:records,
    clean106ByCity:{natal_parnamirim:["123456"],fortaleza:["123456"]},
    selectedRecords:[natal],
    sentContracts:{}
  });
  Object.assign(api.els,{
    cidade:{value:"natal_parnamirim"},
    bairro:{value:"",innerHTML:""},
    tecnico:{value:"TECNICO TESTE"},
    data:{value:"2026-11-23"},
    agenda:{value:"08:00 - 22:00"},
    marcar:{disabled:false},
    output:{value:"mensagem simulada"}
  });
  assert.equal(api.availableRecordsForBairro("").length,1);
  await api.markSelectedAsSent();
  assert.equal(writes.length,1,"register once using authenticated API");
  assert.equal(writes[0].profile,"natal");
  assert.equal(writes[0].contract,"123456");
  assert.equal(api.availableRecordsForBairro("").length,0,"sent record excluded");
  api.state.selectedRecords=[natal];
  await api.markSelectedAsSent();
  assert.equal(writes.length,1,"remote duplicate must be skipped");
  api.els.cidade.value="fortaleza";
  assert.equal(api.availableRecordsForBairro("").length,1,"Natal sent must not hide Fortaleza contract");
  api.els.cidade.value="natal_parnamirim";
  api.state.selectedRecords=[natal];
  const numberBefore=writes.length;
  ctx.request=async()=>{throw Error("sessao indisponivel")};
  await api.markSelectedAsSent();
  assert.equal(writes.length,numberBefore,"failed GET must not register sends");
  console.log("OK: register sent, no duplicate, city boundary and safe API failure");
})().catch(error=>{console.error(error);process.exitCode=1});
