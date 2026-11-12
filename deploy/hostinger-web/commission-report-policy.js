'use strict';
// Fixed read-only DataSnap commission route. No arbitrary procedures or SQL.
function allowedCommissionReport(method,target){
  return method==='GET' && typeof target==='string' && target.length<180 &&
    !/[\r\n]/.test(target) &&
    /^\/api\/commission-reports\/export\.xlsx\?profile=(natal|fortaleza|mossoro|recife)&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$/.test(target);
}
module.exports={allowedCommissionReport};
