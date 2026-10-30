'use strict';
// Read-only report generation; POST starts a local analysis of an already-ready Atlas QUERY.
// It NEVER submits a new Atlas queue or writes to equipment/stock/order systems.
const JOB = /^\/api\/stock\/analyses\/jobs\/[a-f0-9]{32}(?:\/export)?$/;
function allowedStockAnalysisRoute(method,target){
 if(!['GET','POST'].includes(method)||typeof target!=='string'||target.length>180||
    target.includes('%')||target.includes('#')||target.includes('//'))return false;
 if(method==='POST')return target==='/api/stock/analyses/jobs'||target==='/api/stock/analyses/daily/import';
 if(target==='/api/stock/analyses/jobs'||JOB.test(target))return true;
 if(/^\/api\/stock\/analyses\/daily\?city=(natal|fortaleza|mossoro|recife)(?:&date=\d{4}-\d{2}-\d{2})?$/.test(target))return true;
 if(/^\/api\/stock\/analyses\/daily\/[a-f0-9]{32}\/(?:sheets\/[0-5]|export)$/.test(target))return true;
 return /^\/api\/stock\/analyses\/available\?city=(natal|fortaleza|mossoro|recife)$/.test(target);
}
module.exports={allowedStockAnalysisRoute};
