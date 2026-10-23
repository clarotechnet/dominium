'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {restorePrivateJsonContentType}=require('../deploy/hostinger-web/operational-relay');
const server=fs.readFileSync(path.join(__dirname,'../deploy/hostinger-web/server.js'),'utf8');

const make=(url,method='POST',contentType='application/json')=>({
  method,originalUrl:url,headers:{'content-type':contentType,cookie:'do-not-forward',
   'x-csrf-token':'do-not-forward'}
});

test('Atlas QUERY POST preserves application/json through Hostinger relay',()=>{
 const headers={authorization:'Bearer fake'};
 restorePrivateJsonContentType(make('/api/atlas-query/jobs'),headers,
   JSON.stringify({city:'natal',location:'empreiteira'}));
 assert.equal(headers['content-type'],'application/json');
 assert.equal(headers.authorization,'Bearer fake');
 assert.equal(headers.cookie,undefined);
 assert.equal(headers['x-csrf-token'],undefined);
});
test('confront job POST also preserves JSON media type',()=>{
 const headers={};
 restorePrivateJsonContentType(make('/api/confront/jobs'),headers,'{}');
 assert.equal(headers['content-type'],'application/json');
});
test('GET, forbidden routes, and absent body are not rewritten',()=>{
 for(const [request,body] of [
  [make('/api/atlas-query/jobs','GET'),undefined],
  [make('/api/atlas-query/jobs'),''],
  [make('/api/stock/transfer'),'{}'],
  [make('/api/atlas-query/jobs','POST','text/plain'),'{}'],
  [make('/api/atlas-query/jobs','POST','application/json'),undefined]
 ]){
  const h={};
  restorePrivateJsonContentType(request,h,body);
  if(request.method==='GET'||request.originalUrl!== '/api/atlas-query/jobs' ||
     request.headers['content-type']!=='application/json'||body===undefined)
   assert.equal(h['content-type'],undefined);
 }
});
test('server re-adds JSON header on exact active private relay path',()=>{
 assert.match(server,/restorePrivateJsonContentType\(req,\s*headers,\s*body\)/);
 assert.match(server,/delete headers\['content-type'\]/);
});
