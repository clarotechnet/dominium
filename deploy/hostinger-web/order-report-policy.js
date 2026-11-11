'use strict';
// Shared by Hostinger and the Worker; no arbitrary provider, status or partner.
function allowedOrderReport(method, target) {
  return method === 'GET' && typeof target === 'string' && target.length < 180 && !/[\r\n]/.test(target) &&
    /^\/api\/order-reports\/export\.xlsx\?profile=(natal|fortaleza|mossoro|recife)&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}&type=(all|maintenance)(?:&variant=treated)?$/.test(target);
}
module.exports = { allowedOrderReport };
