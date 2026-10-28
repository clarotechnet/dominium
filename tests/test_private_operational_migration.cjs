'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {
  allowedOperationalWrite,allowedOperationalRead,validBulkCreateBody,operationTransportFailure
}=require('../deploy/hostinger-web/operational-policy');
const {resolveOperationalRead,restorePrivateJsonContentType}=require('../deploy/hostinger-web/operational-relay');

const token='s'.repeat(43);
const request=(url,role='controller',method='POST')=>({
  method,originalUrl:url,dominiumSession:{csrf_hash:'set'},
  dominiumUser:{id:7,role,display_name:'Controlador Teste'},headers:{'content-type':'application/json'}
});

test('explicit private write allowlist supports existing operational commands, but not arbitrary writes',()=>{
 const accepted=[
  '/api/orders/bulk-create?profile=fortaleza',
  '/api/stock/writeoff',
  '/api/stock/writeoff?profile=fortaleza',
  '/api/stock/batch',
  '/api/stock/batch?profile=natal',
  '/api/toa-agenda/import?profile=mossoro',
  '/api/stock/pdf/batch',
  '/api/auto-improductive-close/toggle',
  '/api/toa-agenda/import',
  '/api/toa-automation/run',
  '/api/toa-capture/analyze',
  '/api/toa-live/connect',
  '/api/monitor/snapshot/clear',
  '/api/voice/synthesize',
  '/api/disconnect-automation/prepare',
  '/api/disconnect-automation/action',
  '/api/disconnect-automation/claim',
  '/api/disconnect-automation/update',
  '/api/orders/123/material-paste?profile=natal',
  '/api/orders/123/move-installer?profile=recife',
  '/api/orders/123/transfer-serial?profile=mossoro',
 ];
 for(const url of accepted)assert.equal(allowedOperationalWrite('POST',url),true,url);
 for(const url of [
  '/api/orders/bulk-create',
  '/api/orders/bulk-create?profile=unknown',
  '/api/orders/bulk-create?profile=natal&profile=recife',
  '/api/orders/0/transfer-serial?profile=natal',
  '/api/orders/123/transfer-serial?profile=unknown',
  '/api/orders/123/close?profile=natal',
  '/api/orders/123/delete?profile=natal',
  '/api/orders/%31/transfer-serial?profile=natal',
  '/api/stock/writeoff?redirect=evil',
  '/api/stock/writeoff#frag',
  '/api/stock/writeoff/again',
  '//outside.example/api/stock/writeoff',
  'https://outside.example/api/stock/writeoff',
  '/api/disconnect-automation/delete',
  '/api/disconnect-automation/start',
  '/api/disconnect-automation/pause',
 ])assert.equal(allowedOperationalWrite('POST',url),false,url);
 assert.equal(allowedOperationalWrite('GET','/api/orders/bulk-create?profile=natal'),false);
});

test('order create body requires explicit confirmation, unique id and plausible service scope',()=>{
 const good={confirmed:true,request_id:'f1d082e9facc',technician_id:52299,
   service:'RETIRADA FORA TOA',contracts:['5394655']};
 assert.equal(validBulkCreateBody(good),true);
 for(const bad of [
  {...good,confirmed:false},{...good,request_id:'a'},
  {...good,request_id:'a\nother'},{...good,technician_id:0},
  {...good,technician_id:'52299'},{...good,service:''},
  {...good,contracts:undefined},[],null,
 ])assert.equal(validBulkCreateBody(bad),false,String(bad?.request_id));
 const uncertain=operationTransportFailure();
 assert.equal(uncertain.uncertain,true);
 assert.equal(uncertain.safe_to_retry,false);
});

test('private connection forwards exact city and JSON, never browser credentials',()=>{
 const url='/api/orders/bulk-create?profile=fortaleza';
 const result=resolveOperationalRead(request(url),()=>({token}));
 assert.equal(result.url,'https://dominium-import-bridge.jogador743.workers.dev'+url);
 assert.equal(result.headers.authorization,'Bearer '+token);
 assert.equal(result.headers['x-dominium-role'],'controller');
 assert.equal(result.headers.cookie,undefined);
 const headers={'x-csrf-token':'secret','content-type':'text/plain',cookie:'private'};
 restorePrivateJsonContentType(request(url),headers,'{"confirmed":true}');
 assert.equal(headers['content-type'],'application/json');
 assert.equal(allowedOperationalRead('GET','/api/toa-datalake/feed?profile=natal'),true);
});

test('write relay refuses viewer, anonymous and arbitrary request path',()=>{
 assert.throws(()=>resolveOperationalRead(request('/api/orders/bulk-create?profile=natal','viewer'),()=>({token})),/session/);
 assert.throws(()=>resolveOperationalRead({...request('/api/orders/bulk-create?profile=natal'),dominiumSession:null},()=>({token})),/session/);
 assert.equal(resolveOperationalRead(request('/api/orders/drop-database?profile=natal'),()=>({token})),null);
});
