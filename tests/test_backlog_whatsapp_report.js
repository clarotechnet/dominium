'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const r=require('../static/backlog-report');

const rows=[
 {contract:'1111111',technician:'SAULO EURIPIS',route_file:'Atividades-NTL-DMV_ADM_03_11_26.csv',city:'NATAL/PARNAMIRIM',classification:'SEGURAR',historical_code:'430',historical_date:'2026-09-21'},
 {contract:'2222222',technician:'ALLAN JAYVERSON',route_file:'Atividades-PWM-DMV_ADM_03_11_26.csv',city:'NATAL/PARNAMIRIM',classification:'SEGURAR',historical_code:'404',historical_date:'2026-10-01'},
 {contract:'3333333',technician:'ROMARIO PEREIRA',route_file:'Atividades-FTZ-DMV_ADM_03_11_26.csv',city:'FORTALEZA',classification:'SEGURAR',historical_code:'101',historical_date:'2026-08-01'},
 {contract:'4444444',technician:'ELVIS AARON',route_file:'Atividades-JCR-DMV_ADM_03_11_26.csv',city:'RECIFE',classification:'OUTRO HISTÓRICO',historical_code:'106'},
 {contract:'5555555',technician:'MARCOS WENDELL',route_file:'Atividades-MRO-DMV_03_11_26.csv',city:'MOSSORO',classification:'SEGURAR',historical_code:'306',historical_date:'2026-02-01'},
 {contract:'1111111',technician:'SAULO EURIPIS',route_file:'Atividades-NTL-DMV_ADM_03_11_26.csv',city:'NATAL/PARNAMIRIM',classification:'SEGURAR',historical_code:'430',historical_date:'2026-09-21'},
];
test('top-city scope uses Natal and Parnamirim only, not Fortaleza',()=>{
 const result=r.build(rows,'natal');
 assert.equal(result.total,2);
 assert.deepEqual(result.groups.map(x=>x.city),['NATAL','PARNAMIRIM']);
 assert.equal(result.groups[0].codeCounts['430'],1);
 assert.equal(result.groups[1].codeCounts['404'],1);
 assert.doesNotMatch(r.toWhatsApp(result),/FORTALEZA/);
});
test('all scope includes each of five route buckets and excludes unmatched historical code',()=>{
 const result=r.build(rows,'all');
 assert.equal(result.total,4);
 assert.deepEqual(result.groups.map(x=>x.city),['NATAL','PARNAMIRIM','FORTALEZA','MOSSORO']);
 assert.equal(r.build(rows,'fortaleza').total,1);
 assert.equal(r.build(rows,'recife').total,0);
 assert.equal(r.build(rows,'mossoro').total,1);
});
test('text for copying is grouped by technician, contract and historical code, not today close',()=>{
 const text=r.toWhatsApp(r.build(rows,'natal'));
 assert.match(text,/RELATÓRIO DE CONTRATOS PARA SEGURAR/);
 assert.match(text,/SAULO EURIPIS/);
 assert.match(text,/Contrato: 1111111/);
 assert.match(text,/Baixa histórica: 430/);
 assert.match(text,/Data: 21\/09\/2026/);
 assert.match(text,/código 430 é retirada produtiva/);
 assert.doesNotMatch(text,/3333333/);
 assert.equal((text.match(/Contrato: 1111111/g)||[]).length,1);
});
test('csv route identity takes priority over normalized combined city',()=>{
 assert.equal(r.reportCity({city:'NATAL/PARNAMIRIM',route_file:'Atividades-PWM-DMV_ADM_03_11_26.csv'}),'PARNAMIRIM');
 assert.equal(r.reportCity({city:'NATAL/PARNAMIRIM',route_file:'Atividades-NTL-DMV_ADM_03_11_26.csv'}),'NATAL');
 assert.equal(r.formatDate('2026-11-03'),'03/11/2026');
 assert.equal(r.formatDate('2026-11-03T15:42:19'),'03/11/2026 15:42');
});
