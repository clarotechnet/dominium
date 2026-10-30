'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {allowedBacklogRoute}=require('../deploy/hostinger-web/operational-policy');
const {resolveOperationalRead}=require('../deploy/hostinger-web/operational-relay');

const allowedReads=[
  '/api/backlog/year/status',
  '/api/backlog/year/sent',
  '/api/backlog/year/compare?limit=300&codes=101%2C306%2C404%2C430',
  '/api/backlog/year/fora-rota?profile=natal&limit=150'
];
const allowedWrites=[
  '/api/backlog/year/start',
  '/api/backlog/year/pause',
  '/api/backlog/year/routes',
  '/api/backlog/year/sent'
];

test('read-only Backlog routes require exact paths and bounded queries',()=>{
 for(const url of allowedReads)assert.equal(allowedBacklogRoute('GET',url),true,url);
 for(const url of allowedWrites.filter(u=>u!=='/api/backlog/year/sent'))assert.equal(allowedBacklogRoute('GET',url),false,url);
 for(const url of [
  '/api/backlog/year/secret', '/api/backlog/year/start?x=1',
  '/api/backlog/year/compare?limit=999999',
  '/api/backlog/year/compare?codes=430%2C99',
  '/api/backlog/year/status?unexpected=yes',
  '/api/backlog/year/fora-rota?profile=bogus',
  '//api/backlog/year/status',
  '/api/backlog/year/%2e%2e/status',
  '/api/backlog/year/compare#fragment'
 ])assert.equal(allowedBacklogRoute('GET',url),false,url);
});

test('Backlog mutations use exact POST allowlist',()=>{
 for(const url of allowedWrites)assert.equal(allowedBacklogRoute('POST',url),true,url);
 for(const url of [
  '/api/backlog/year/routes?profile=natal',
  '/api/backlog/year/remove',
  '/api/backlog/year/start/extra',
  '/api/backlog/year/start?anything=1',
  '/api/backlog/year/%2fstart'
 ])assert.equal(allowedBacklogRoute('POST',url),false,url);
});

test('private relay rejects viewers for writes but permits roles for reads',()=>{
 const connection=()=>({token:'A'.repeat(50)});
 function request(role,method,url) {
  return {method,originalUrl:url,dominiumSession:{id:1},
    dominiumUser:{id:7,role,display_name:'Operator'}};
 }
 assert.ok(resolveOperationalRead(request('controller','GET',allowedReads[0]),connection));
 assert.throws(()=>resolveOperationalRead(request('viewer','GET',allowedReads[0]),connection));
 assert.ok(resolveOperationalRead(request('admin','POST',allowedWrites[0]),connection));
 assert.throws(()=>resolveOperationalRead(request('viewer','POST',allowedWrites[0]),connection));
 assert.equal(resolveOperationalRead(request('admin','GET','/api/backlog/year/not-allowed'),connection),null);
});
