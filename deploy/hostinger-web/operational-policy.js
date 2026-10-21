'use strict';

// Read-only paths that may pass from the authenticated Hostinger app
// through the private Workers VPC connector to the local Windows backend.
// Never accept arbitrary paths or write methods on this relay.
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
]);

const DETAIL_ROUTE = /^\/api\/(?:orders\/\d+\/(?:material-inventory|installer-change-preview|serialized-transfer-preview)|operational\/contracts\/[0-9]+|imperium-official\/stocks(?:\/[0-9]+)?)$/;

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
module.exports = { allowedOperationalRead };
