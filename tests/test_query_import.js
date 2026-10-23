'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const importer=require('../static/query-import.js');
const zip=require('../static/fflate.browser.min.js');
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
test('a aba Pendente mostra praca Mossoro e controles de filtro por estado/local',()=>{
 for(const id of ['confrontQueryFile','confrontCity','confrontEquipmentStatus',
  'confrontLocationFilter','confrontAssumeCity','confrontQueryPreview','confrontUseFiltered']){
  assert.ok(html.includes('id="'+id+'"'),id);
 }
 assert.match(html,/<option value="mossoro">Mossoró<\/option>/);
 assert.ok(html.includes('/query-import-ui.js?v=20261023-1'));
});
test('CSV QUERY filtra Mossoro e SUSPEITO sem misturar outras operacoes',()=>{
 const rows=importer.parseCsv(
  'Número Série;Estado;Operação;Nome do Local\n'+
  '000123456789;SUSPEITO;MOSSORÓ;ESTOQUE A\n'+
  '000555555555;SUCATA;MOSSORO;ESTOQUE A\n'+
  '000999999999;SUSPEITO;NATAL;ESTOQUE B\n');
 const data=importer.toRecords(rows);
 assert.equal(data.records.length,3);
 assert.equal(data.hasCity,true);
 assert.deepEqual(importer.filter(data,{city:'MOSSORO',status:'SUSPEITO'}),['000123456789']);
 assert.deepEqual(importer.filter(data,{city:'NATAL',status:'SUSPEITO'}),['000999999999']);
});
test('sem coluna de cidade bloqueia classificacao automatica por praca',()=>{
 const data=importer.toRecords(importer.parseCsv('Serial;Estado\nABCDEF123456;SUSPEITO'));
 assert.equal(data.hasCity,false);
 assert.deepEqual(importer.filter(data,{city:'MOSSORO',status:'SUSPEITO'}),[]);
 assert.deepEqual(importer.filter(data,{city:'MOSSORO',status:'SUSPEITO',assumeCity:true}),['ABCDEF123456']);
});
test('XLSX exportado com strings compartilhadas preserva serial com zero inicial',()=>{
 const strings=['Número Série','Estado','Operação','Nome do Local','000123456789','SUSPEITO','MOSSORÓ','NATAL','SUCATA','ESTOQUE A'];
 const shared='<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+
  strings.map(s=>'<si><t>'+s+'</t></si>').join('')+'</sst>';
 const cell=(ref,i)=>'<c r="'+ref+'" t="s"><v>'+i+'</v></c>';
 const row=(n,values)=>'<row r="'+n+'">'+values.map((v,i)=>cell(String.fromCharCode(65+i)+n,v)).join('')+'</row>';
 const worksheet='<worksheet><sheetData>'+row(1,[0,1,2,3])+row(2,[4,5,6,9])+row(3,[4,8,7,9])+'</sheetData></worksheet>';
 const encoded=zip.zipSync({
  'xl/sharedStrings.xml':new TextEncoder().encode(shared),
  'xl/worksheets/sheet1.xml':new TextEncoder().encode(worksheet)
 });
 const array=encoded.buffer.slice(encoded.byteOffset,encoded.byteOffset+encoded.byteLength);
 const data=importer.toRecords(importer.parseXlsx(array,zip.unzipSync));
 assert.deepEqual(importer.filter(data,{city:'MOSSORO',status:'SUSPEITO'}),['000123456789']);
});
test('CSV com duas colunas e separador de virgula reconhece seriais sem upload',()=>{
 const rows=importer.parseCsv('Serial,Status\nABCDEF123456,SUSPEITO\nABCDEF123456,SUSPEITO');
 const data=importer.toRecords(rows);
 assert.deepEqual(importer.filter(data,{city:'MOSSORO',assumeCity:true}),['ABCDEF123456']);
});
