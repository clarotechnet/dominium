'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createPhotoLookup}=require('../photoLookup');
const evidence={serial_consultado:'ABC123456789',serial_baixavel:'ABC123456789',enderecaveis:['ABC123456789'],enderecaveis_negrito:['ABC123456789'],serial_encontrado:true,numero_contrato:'1234567',tipo_equipamento:'EMTA',historico:[{numero_contrato:'1234567',tipo_localizacao:'CLIENTE'}]};
test('confirmed existing Atlas reader is reused without a second OCR or query',async()=>{
 const read=createPhotoLookup({primaryLookup:async()=>({seriaisDetectados:['ABC123456789'],resultadosAtlas:[{resultado:evidence}],retorno:{ok:true,resultado:evidence}}),readBarcode:async()=>{throw Error('second scan forbidden');},readOcr:async()=>{throw Error('OCR must be unnecessary');},lookupSerials:async()=>{throw Error('duplicate Atlas query');}});
 const result=await read(Buffer.from('photo'));
 assert.equal(result.photoReading.stage,'confirmed');
 assert.equal(result.photoReading.source,'existing-atlas-reader');
 assert.equal(result.resultadosAtlas[0].resultado.serial_baixavel,'ABC123456789');
});
test('a returned equipment unrelated to the photo cannot bypass verification',async()=>{
 const read=createPhotoLookup({primaryLookup:async()=>({seriaisDetectados:['OTHER123456789'],resultadosAtlas:[{resultado:evidence}],retorno:{ok:true,resultado:evidence}}),readBarcode:async()=>[],readOcr:async()=>({candidates:[],attempts:1}),lookupSerials:async()=>({retorno:{ok:false}})});
 const result=await read(Buffer.from('photo'));
 assert.notEqual(result.photoReading.stage,'confirmed');
});
test('a failed barcode reading falls back to OCR and canonical Atlas evidence',async()=>{
 const read=createPhotoLookup({primaryLookup:async()=>({seriaisDetectados:[],retorno:{ok:false,error:'barcode_nao_lido_na_imagem'}}),readBarcode:async()=>[],readOcr:async()=>({candidates:[{value:'ABC123456789',source:'ocr'}],attempts:1}),lookupSerials:async()=>({resultadosAtlas:[{resultado:evidence}],retorno:{ok:true,resultado:evidence}})});
 const result=await read(Buffer.from('photo'));
 assert.equal(result.photoReading.stage,'confirmed');
});
