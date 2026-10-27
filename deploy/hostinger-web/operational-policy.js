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
module.exports = { allowedOperationalRead, allowedToaLookup, allowedOrderClose,
  allowedQualityControl, validOfficialCloseBody, closeTransportFailure };
