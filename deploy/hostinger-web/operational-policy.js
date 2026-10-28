'use strict';

// Read-only paths that may pass from the authenticated Hostinger app
// through the private Workers VPC connector to the local Windows backend.
// Mutations have a separate exact policy below; never accept arbitrary paths.
const ROUTES = new Set([
  '/api/orders',
  '/api/toa-contracts',
  '/api/toa-live/status',
  '/api/toa-automation',
  '/api/toa-capture/lots',
  '/api/operational/contracts',
  '/api/auto-improductive-close',
  '/api/health-check',
  '/api/profiles',
  '/api/status',
  '/api/technicians',
  '/api/stock/technicians',
  '/api/monitor/snapshot',
  '/api/failures',
  '/api/intelligence',
  '/api/intelligence/report',
  '/api/intelligence/serial-audit',
  '/api/logs',
  '/api/close-report',
  '/api/stock',
  '/api/stock/serial-owner',
  '/api/serials/consult',
  '/api/disconnect-automation',
  '/api/intelligence/report.pdf',
  '/api/close-report/export.xlsx',
  '/api/toa-datalake/feed',
]);

const DETAIL_ROUTE = /^\/api\/(?:orders\/\d+\/(?:installer|material-inventory|installer-change-preview|serialized-transfer-preview)|operational\/contracts\/[0-9]+|imperium-official\/stocks(?:\/[1-9][0-9]{0,9}\/items)?)$/;

function allowedOperationalRead(method, requestTarget) {
  if (method !== 'GET' || typeof requestTarget !== 'string' ||
      requestTarget.length > 4096 || !requestTarget.startsWith('/api/') ||
      requestTarget.startsWith('//') || requestTarget.includes('#')) return false;
  let url;
  try { url = new URL(requestTarget, 'https://dominium.invalid'); } catch { return false; }
  if (url.origin !== 'https://dominium.invalid' ||
      url.pathname.includes('%') || url.pathname.includes('//')) return false;
  return ROUTES.has(url.pathname) || DETAIL_ROUTE.test(url.pathname);
}
// The live lookup is a read action transported as POST. Keep it separate
// from GET permissions and never allow connect/close routes through it.
function allowedToaLookup(method, requestTarget) {
  return method === 'POST' && typeof requestTarget === 'string' &&
    /^\/api\/toa-live\/lookup\?profile=(?:natal|fortaleza|mossoro|recife)$/.test(requestTarget);
}
function allowedOrderClose(method, requestTarget) {
  return method === 'POST' && typeof requestTarget === 'string' &&
    /^\/api\/orders\/[1-9][0-9]{0,9}\/close\?profile=(?:natal|fortaleza|mossoro|recife)$/.test(requestTarget);
}
function validOfficialCloseBody(body) {
  return Boolean(body && typeof body === 'object' && !Array.isArray(body) &&
    body.transport === 'official_http');
}
function closeTransportFailure() {
  return {ok:false,uncertain:true,safe_to_retry:false,error:'A resposta da baixa nao foi confirmada. Confira o relatorio e o estado da OS no Imperium antes de repetir.'};
}
// Somente GET/POST nesta rota; nenhuma outra gravacao operacional.
function allowedQualityControl(method, requestTarget) {
  return (method === 'GET' || method === 'POST') &&
    requestTarget === '/api/stock/quality-control';
}
function allowedDailyStock(method, target) {
  return (method === 'POST' && target === '/api/stock/daily') ||
    (method === 'GET' && /^\/api\/stock\/daily(?:\?id=[a-fA-F0-9-]{36})?$/.test(target));
}
// Exact operational POST routes. Never proxy arbitrary URL paths to Windows.
const OPERATIONAL_WRITES = new Set([
  '/api/orders/bulk-create',
  '/api/auto-improductive-close/toggle',
  '/api/stock/batch',
  '/api/stock/pdf/batch',
  '/api/stock/writeoff',
  '/api/toa-automation/run',
  '/api/toa-capture/analyze',
  '/api/toa-agenda/import',
  '/api/toa-live/connect',
  '/api/monitor/snapshot/clear',
  '/api/voice/synthesize',
]);
const SCOPED_WRITES = /^\/api\/orders\/[1-9][0-9]{0,9}\/(?:material-paste|move-installer|transfer-serial)\?profile=(?:natal|fortaleza|mossoro|recife)$/;
const DISCONNECT_WRITES = /^\/api\/disconnect-automation\/(?:prepare|action|claim|update)$/;
function allowedOperationalWrite(method,target) {
  if(method!=='POST' || typeof target!=='string' || target.length>512 ||
    !target.startsWith('/api/') || target.startsWith('//') ||
    target.includes('#') || target.includes('\\')) return false;
  let url;
  try {url=new URL(target,'https://dominium.invalid');}catch{return false;}
  if(url.origin!=='https://dominium.invalid'||url.pathname.includes('%')||
    url.pathname.includes('//'))return false;
  if(SCOPED_WRITES.test(target) || DISCONNECT_WRITES.test(target))return true;
  // Only OS creation uses a city-scoped POST. All other routes reject query params.
  if(url.pathname==='/api/orders/bulk-create')
    return /^\/api\/orders\/bulk-create\?profile=(?:natal|fortaleza|mossoro|recife)$/.test(target);
  if (!OPERATIONAL_WRITES.has(url.pathname)) return false;
  // The UI uses apiUrl() to append exactly one selected city.
  return url.search==='' || /^\?profile=(?:natal|fortaleza|mossoro|recife)$/.test(url.search);
}
function validBulkCreateBody(value) {
  return Boolean(value && typeof value==='object' && !Array.isArray(value) &&
    value.confirmed===true && /^[A-Za-z0-9_-]{12,100}$/.test(String(value.request_id||'')) &&
    Number.isSafeInteger(value.technician_id) && value.technician_id>0 &&
    typeof value.service==='string' && value.service.length>0 && value.service.length<=120 &&
    (typeof value.contracts==='string' || Array.isArray(value.contracts)));
}
function operationTransportFailure() {
  return {ok:false,uncertain:true,safe_to_retry:false,
    error:'A resposta do Imperium nao foi confirmada. Confira a OS no sistema antes de repetir esta operacao.'};
}

module.exports = { allowedOperationalRead, allowedToaLookup, allowedOrderClose,
  allowedQualityControl, allowedDailyStock, allowedOperationalWrite, validBulkCreateBody,
  operationTransportFailure, validOfficialCloseBody, closeTransportFailure };
