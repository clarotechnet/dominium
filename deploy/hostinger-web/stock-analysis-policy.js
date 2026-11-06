'use strict';
// Read-only report generation; POST starts a local analysis of an already-ready Atlas QUERY.
// It NEVER submits a new Atlas queue or writes to equipment/stock/order systems.
const JOB = /^\/api\/stock\/analyses\/jobs\/[a-f0-9]{32}(?:\/export)?$/;
function allowedStockAnalysisRoute(method,target){
 if(!['GET','POST'].includes(method)||typeof target!=='string'||target.length>180||
    target.includes('%')||target.includes('#')||target.includes('//'))return false;
 if(method==='POST')return target==='/api/stock/analyses/jobs'||target==='/api/stock/analyses/daily/import'||target==='/api/stock/analyses/imperium/extract'||target==='/api/stock/analyses/imperium/live'||target==='/api/stock/analyses/imperium/serial-treatment/next'||target==='/api/stock/analyses/imperium/atlas-video/next';
 if(target==='/api/stock/analyses/jobs'||JOB.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/atlas-video\/status\?city=(natal|mossoro|recife)&run=[a-f0-9-]{36}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/serial-treatment\/(?:status|export)\?city=(natal|mossoro|recife)&run=[a-f0-9-]{36}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/live\?city=(natal|fortaleza|mossoro|recife)&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/live\/[a-f0-9-]{36}\/data\?city=(natal|fortaleza|mossoro|recife)&category=(consolidado|por_os|seriais_tratados)&page=[1-9][0-9]{0,2}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/runs\?city=(natal|fortaleza|mossoro|recife)&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/imperium\/runs\/[a-f0-9]{32}\/(?:sheets\/[01]|export)$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/jobs\/[a-f0-9]{32}\/data\?page=[1-9][0-9]{0,3}$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/daily\?city=(natal|fortaleza|mossoro|recife|all)(?:&date=\d{4}-\d{2}-\d{2}|&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2})?$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/daily\/[a-f0-9]{32}\/(?:sheets\/[0-5]|export)$/.test(target))return true;
 return /^\/api\/stock\/analyses\/available\?city=(natal|fortaleza|mossoro|recife)$/.test(target);
}
module.exports={allowedStockAnalysisRoute};
