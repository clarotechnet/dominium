'use strict';
// Authenticated, read-only Atlas report queue; creation launches report generation,
// never transfers, deletes or moves equipment.
const JOB=/^\/api\/atlas-query\/jobs\/[a-f0-9]{32}(?:\/rows\/(?:0|[1-9]\d{0,5})|\/export\.(?:csv|xlsx))?$/;
function allowedAtlasQueryRoute(method,target){
 if(!['GET','POST'].includes(method)||typeof target!=='string'||target.length>200
    ||!target.startsWith('/api/atlas-query/')||target.includes('%')
    ||target.includes('//')||target.includes('#')||target.includes('?'))return false;
 let url;try{url=new URL(target,'https://dominium.invalid')}catch{return false}
 if(url.origin!=='https://dominium.invalid'||url.search||url.hash)return false;
 if(method==='POST')return url.pathname==='/api/atlas-query/jobs';
 return url.pathname==='/api/atlas-query/jobs'||JOB.test(url.pathname);
}
module.exports={allowedAtlasQueryRoute};
