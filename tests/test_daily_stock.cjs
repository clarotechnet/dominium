const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const parser=require('../static/daily-stock-parser.js');
const policy=require('../deploy/hostinger-web/operational-policy.js');
const relay=require('../deploy/hostinger-web/operational-relay.js');
const file=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');
test('normaliza zero sem danificar codigo SAP',()=>{
 assert.equal(parser.normalizeMaterial('000000000022025245'),'22025245');
 assert.equal(parser.normalizeMaterial('000000000022024780'),'22024780');
 assert.throws(()=>parser.normalizeMaterial('=2+2'));
});
test('trata qtd no formato brasileiro ou numerico',()=>{
 assert.equal(parser.parseQuantity('2.082'),2082);
 assert.equal(parser.parseQuantity('2.082',true),2.082);
 assert.equal(parser.parseQuantity('1.234,50'),1234.5);
 assert.equal(parser.parseQuantity('0'),0);
 assert.throws(()=>parser.parseQuantity('-7'));
});
test('consolida materiais repetidos e ignora colunas A B E G',()=>{
 const stringValues=['Material','Descr. Material','Qtd - Utilização Livre',
   '000000000022025245','Marcador apto','2','3','000000000022024780','Cabo','0'];
 const strings='<sst>'+stringValues.map(v=>'<si><t>'+v+'</t></si>').join('')+'</sst>';
 const row=(i,vals)=>'<row r="'+i+'">'+Object.entries(vals).map(([c,n])=>
   '<c r="'+c+i+'" t="s"><v>'+n+'</v></c>').join('')+'</row>';
 const sheet='<worksheet><sheetData>'+row(1,{C:0,D:1,F:2})+
   row(2,{C:3,D:4,F:5})+row(3,{C:3,D:4,F:6})+row(4,{C:7,D:8,F:9})+
   '</sheetData></worksheet>';
 const result=parser.readExcelXml(sheet,strings);
 assert.equal(result.linhas_origem,3);
 assert.equal(result.materiais_distintos,2);
 assert.equal(result.quantidade_total,'5.000');
 const target=result.items.find(x=>x.material==='22025245');
 assert.equal(target.quantidade_livre,'5.000');
});
test('recusa descricao divergente e cabecalho alterado',()=>{
 assert.throws(()=>parser.readExcelXml('<sheet><row r="1"><c r="C1" t="s"><v>0</v></c></row></sheet>','<sst><si><t>Not material</t></si></sst>'));
});
test('somente leitura e gravacao exata via ponte autentica',()=>{
 const path='/api/stock/daily';
 assert.equal(policy.allowedDailyStock('GET',path),true);
 assert.equal(policy.allowedDailyStock('POST',path),true);
 assert.equal(policy.allowedDailyStock('GET',path+'?id=123e4567-e89b-12d3-a456-426614174000'),true);
 assert.equal(policy.allowedDailyStock('GET',path+'?foo=1'),false);
 assert.equal(policy.allowedDailyStock('DELETE',path),false);
 const connection=()=>({token:'q'.repeat(43)});
 const req=(method,role)=>({method,originalUrl:path,dominiumSession:{id:2},
   dominiumUser:{role,id:4,username:'test'}});
 assert.ok(relay.resolveOperationalRead(req('GET','viewer'),connection));
 assert.throws(()=>relay.resolveOperationalRead(req('POST','viewer'),connection));
 assert.ok(relay.resolveOperationalRead(req('POST','admin'),connection));
 const headers={};
 relay.restorePrivateJsonContentType({method:'POST',originalUrl:path,headers:{'content-type':'application/json'}},headers,'{}');
 assert.equal(headers['content-type'],'application/json');
});
test('SQL is append-only and RLS enabled',()=>{
 const sql=file('supabase/migrations/20261028153000_estoque_diario.sql');
 assert.match(sql,/enable row level security/g);
 assert.match(sql,/unique \(data_estoque, hash_arquivo\)/);
 assert.match(sql,/on delete restrict/);
 assert.match(sql,/security invoker/);
 assert.doesNotMatch(sql,/truncate table|delete from public\.estoque_diario/i);
});
