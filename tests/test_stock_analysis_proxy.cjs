const test=require('node:test');
const assert=require('node:assert/strict');
const policy=require('../deploy/hostinger-web/stock-analysis-policy');
const proxy=require('../deploy/hostinger-web/operational-relay');
const fs=require('node:fs');
const path=require('node:path');
const token='z'.repeat(43);
const actor=(method,role='controller',target='/api/stock/analyses/jobs')=>({
 method,originalUrl:target,dominiumSession:{id:1},dominiumUser:{id:77,role,username:'operator'},headers:{'content-type':'application/json'}
});
test('report routes are allowlisted only',()=>{
 assert.equal(policy.allowedStockAnalysisRoute('POST','/api/stock/analyses/jobs'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/available?city=natal'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/available?city=all'),false);
 assert.equal(policy.allowedStockAnalysisRoute('DELETE','/api/stock/analyses/jobs'),false);
 assert.equal(policy.allowedStockAnalysisRoute('POST','/api/stock/analyses/jobs/123'),false);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/jobs/'+('a'.repeat(32))+'/export'),true);
 assert.equal(policy.allowedStockAnalysisRoute('POST','/api/stock/analyses/daily/import'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/daily?city=natal&date=2026-10-29'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/daily?city=all'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/daily?city=natal&start=2026-10-28&end=2026-10-29'),true);
 assert.equal(policy.allowedStockAnalysisRoute('GET','/api/stock/analyses/jobs/'+('a'.repeat(32))+'/data?page=1'),true);
});
test('only authenticated operational actors can generate reports',()=>{
 const call=()=>({token});
 assert.equal(proxy.resolveOperationalRead(actor('POST'),call).headers['x-dominium-actor'],'user-77');
 assert.throws(()=>proxy.resolveOperationalRead(actor('POST','viewer'),call));
 assert.throws(()=>proxy.resolveOperationalRead({...actor('POST'),dominiumSession:null},call));
 const headers={};
 proxy.restorePrivateJsonContentType(actor('POST'),headers,'{}');
 assert.equal(headers['content-type'],'application/json');
});
test('reports can be read by viewer but only admin/controller can start writes',()=>{
 const call=()=>({token});
 assert.doesNotThrow(()=>proxy.resolveOperationalRead(actor('GET','viewer','/api/stock/analyses/daily?city=natal'),call));
 assert.throws(()=>proxy.resolveOperationalRead(actor('POST','viewer','/api/stock/analyses/daily/import'),call));
});
test('frontend offers three report actions in stock navigation',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
 const script=fs.readFileSync(path.join(__dirname,'../static/stock-analysis-ui.js'),'utf8');
 for(const kind of ['query','suspeitos'])
  assert.match(html,new RegExp('data-stock-report="'+kind+'"'));
 assert.match(script,/\/api\/stock\/analyses\/jobs/);
 assert.match(script,/requestBlob\(/);
 assert.match(html,/stockReportsTab/);
 assert.match(html,/id="stockDailyAnalysisOpen"/);
 assert.match(html,/id="stockDailyAnalysisHistory"/);
 for(const kind of ['query','equipamentos','suspeitos'])
  assert.match(html,new RegExp('data-stock-analysis-tab="'+kind+'"'));
 assert.match(html,/id="stockDailyRangeStart"/);
 assert.match(html,/id="stockDailyRangeEnd"/);
 assert.match(html,/id="stockQueryPreviewTable"/);
 assert.match(html,/id="stockSuspectsPreviewTable"/);
});
