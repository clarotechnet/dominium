'use strict';

// Only constrained operations for the private Atlas x Imperium read-only job queue.
// POST creates a report job; it never changes equipment, stock or orders.
const JOB = /^\/api\/confront\/jobs\/[a-f0-9]{32}(?:\/export)?$/;
function allowedConfrontRoute(method, target) {
  if (!['GET','POST'].includes(method) || typeof target !== 'string' ||
      target.length > 2048 || !target.startsWith('/api/confront/') ||
      target.includes('#') || target.includes('//')) return false;
  let url;
  try { url = new URL(target, 'https://dominium.invalid'); } catch {return false;}
  if (url.origin !== 'https://dominium.invalid' || url.pathname.includes('%') ||
      url.search || url.hash) return false;
  if (method === 'POST') return url.pathname === '/api/confront/jobs';
  return url.pathname === '/api/confront/status' ||
    url.pathname === '/api/confront/jobs' || JOB.test(url.pathname);
}
module.exports = {allowedConfrontRoute};
