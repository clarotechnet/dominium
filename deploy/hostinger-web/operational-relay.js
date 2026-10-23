'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { allowedOperationalRead } = require('./operational-policy');
const { allowedConfrontRoute } = require('./confront-policy');
const {allowedAtlasQueryRoute}=require('./atlas-query-policy');

const WORKER_ORIGIN = 'https://dominium-import-bridge.jogador743.workers.dev';
function readPrivateConnection() {
  const filename = path.join(__dirname, '.desc-review-connection.json');
  const stored = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : {};
  return { token: process.env.DOMINIUM_DESC_REVIEW_TOKEN || stored.token };
}

function resolveOperationalRead(req, connection = readPrivateConnection) {
  const confrontation = allowedConfrontRoute(req.method, req.originalUrl) ||
    allowedAtlasQueryRoute(req.method, req.originalUrl);
  if (!confrontation && !allowedOperationalRead(req.method, req.originalUrl)) return null;
  if (!req.dominiumSession || (confrontation
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
module.exports = { resolveOperationalRead };
