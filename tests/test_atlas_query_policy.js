'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {allowedAtlasQueryRoute}=require('../deploy/hostinger-web/atlas-query-policy');
const {resolveOperationalRead}=require('../deploy/hostinger-web/operational-relay');
const req=(method,url,role)=>({method,originalUrl:url,dominiumSession:{id:1},
 dominiumUser:{id:5,role,username:'fixture'}});
test('allow only exact GET reports and one POST creation',()=>{
 const id='a'.repeat(32);
 for(const url of ['/api/atlas-query/jobs','/api/atlas-query/jobs/'+id,
 '/api/atlas-query/jobs/'+id+'/rows/0','/api/atlas-query/jobs/'+id+'/rows/100',
 '/api/atlas-query/jobs/'+id+'/export.csv','/api/atlas-query/jobs/'+id+'/export.xlsx']){
 assert.equal(allowedAtlasQueryRoute('GET',url),true,url);
 }
 assert.equal(allowedAtlasQueryRoute('POST','/api/atlas-query/jobs'),true);
 for(const url of ['/api/atlas-query/jobs/'+id+'/../../.env','/api/atlas-query/jobs/'+id+'/rows/-1',
 '/api/atlas-query/jobs/'+id+'/export.php','/api/atlas-query/jobs?actor=5',
 '/api/atlas-query/%6aobs','//evil/api/atlas-query/jobs',
 '/api/atlas-query/jobs/'+id+'/submit']){
 assert.equal(allowedAtlasQueryRoute('GET',url),false,url);
 }
 assert.equal(allowedAtlasQueryRoute('POST','/api/atlas-query/jobs/'+id),false);
});
test('Atlas QUERY transport requires a valid admin/controller session',()=>{
 const cfg=()=>({token:'z'.repeat(43)});
 for(const role of ['admin','controller']){
  const value=resolveOperationalRead(req('POST','/api/atlas-query/jobs',role),cfg);
  assert.match(value.url,/\/api\/atlas-query\/jobs$/);
  assert.equal(value.headers['x-dominium-actor'],'user-5');
 }
 assert.throws(()=>resolveOperationalRead(req('GET','/api/atlas-query/jobs','viewer'),cfg),
    /operational_session_required/);
});
