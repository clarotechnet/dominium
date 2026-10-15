'use strict';
const MAX_IMPORT_BYTES = 12 * 1024 * 1024;
function allowedImportRoute(method, raw) {
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) throw new Error('Rota de importação inválida');
  const url = new URL(raw, 'https://dominium.invalid');
  if (url.hash) throw new Error('Rota de importação inválida');
  const paths = method === 'GET' ? ['/api/import-targets', '/api/import-history'] :
    method === 'POST' ? ['/api/imports/preview', '/api/imports/commit'] : [];
  if (!paths.includes(url.pathname)) throw new Error('Rota de importação não permitida');
  const seen = new Set();
  for (const [key,value] of url.searchParams) {
    if (url.pathname !== '/api/import-history' || seen.has(key)) throw new Error('Parâmetros de importação inválidos');
    seen.add(key);
    const valid = key === 'profile' ? ['natal','fortaleza','mossoro','recife'].includes(value) :
      key === 'date' ? /^\d{4}-\d{2}-\d{2}$/.test(value) : key === 'limit' && /^(?:[1-9]\d{0,2}|1000)$/.test(value);
    if (!valid) throw new Error('Parâmetros de importação inválidos');
  }
  return url.pathname + url.search;
}
module.exports = {allowedImportRoute, MAX_IMPORT_BYTES};
