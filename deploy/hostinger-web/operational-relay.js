'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { allowedOperationalRead, allowedToaLookup, allowedQualityControl, allowedDailyStock, allowedOperationalWrite, allowedBacklogRoute } = require('./operational-policy');
const { allowedConfrontRoute } = require('./confront-policy');
const {allowedAtlasQueryRoute}=require('./atlas-query-policy');
const {allowedStockAnalysisRoute}=require('./stock-analysis-policy');

const WORKER_ORIGIN = 'https://dominium-import-bridge.jogador743.workers.dev';
function readPrivateConnection() {
  const filename = path.join(__dirname, '.desc-review-connection.json');
  const stored = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : {};
  return { token: process.env.DOMINIUM_DESC_REVIEW_TOKEN || stored.token };
}

function resolveOperationalRead(req, connection = readPrivateConnection) {
  const confrontation = allowedConfrontRoute(req.method, req.originalUrl) ||
    allowedAtlasQueryRoute(req.method, req.originalUrl) ||
    allowedStockAnalysisRoute(req.method, req.originalUrl);
  const toaLookup = allowedToaLookup(req.method, req.originalUrl);
  const quality = allowedQualityControl(req.method, req.originalUrl);
  const daily = allowedDailyStock(req.method, req.originalUrl);
  const write = allowedOperationalWrite(req.method, req.originalUrl);
  const backlog = allowedBacklogRoute(req.method,req.originalUrl);
  if (!backlog && !confrontation && !toaLookup && !quality && !daily && !allowedOperationalRead(req.method, req.originalUrl) && !allowedOperationalWrite(req.method,req.originalUrl)) return null;
  const analysisRead=allowedStockAnalysisRoute(req.method,req.originalUrl) && req.method==='GET';
  if (!req.dominiumSession || (((confrontation && !analysisRead) || backlog || toaLookup || ((quality || daily || backlog) && req.method === 'POST') || write)
    ? !['admin','controller'].includes(req.dominiumUser?.role)
    : !['admin','controller','viewer'].includes(req.dominiumUser?.role))) {
    throw new Error('operational_session_required');
  }
  const actor = confrontation
    ? ('user-' + String(req.dominiumUser.id || ''))
    : String(req.dominiumUser.display_name || req.dominiumUser.username || req.dominiumUser.id || '').slice(0,100);
  const { token } = connection();
  if (!actor || !/^[A-Za-z0-9_-]{43,128}$/.test(String(token || ''))) {
    throw new Error('operational_private_relay_not_configured');
  }
  return {
    url: WORKER_ORIGIN + req.originalUrl,
    headers: {
      authorization: 'Bearer ' + token,
      'x-dominium-role': req.dominiumUser.role,
      'x-dominium-actor': encodeURIComponent(actor),
    },
  };
}
// A proxy POST body must retain its media type across Hostinger -> Worker.
// Do not forward browser CSRF/cookie; preserve only the safe JSON media type
// for explicit allowlisted jobs routes.
function restorePrivateJsonContentType(req, headers, body) {
  if (!headers || !req || req.method !== 'POST' || body === undefined) return;
  const url=String(req.originalUrl||'');
  if (!allowedConfrontRoute('POST',url) && !allowedAtlasQueryRoute('POST',url) && !allowedStockAnalysisRoute('POST',url) &&
      !allowedToaLookup('POST',url) && !allowedQualityControl('POST',url) && !allowedDailyStock('POST',url) && !allowedOperationalWrite('POST',url) && !allowedBacklogRoute('POST',url)) return;
  const original=String(req.headers?.['content-type']||'').toLowerCase();
  if (!original.startsWith('application/json')) return;
  headers['content-type']='application/json';
}
module.exports = { resolveOperationalRead, restorePrivateJsonContentType };
