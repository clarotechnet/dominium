'use strict';
// Isolated UI fixtures; no requests reach operational services.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '../static');
const artifactRoot = process.env.DOMINIUM_QA_ARTIFACT_DIR || '/tmp/dominium-workspace-qa';
fs.mkdirSync(artifactRoot, {recursive: true});
let healthMode = 'node';
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const json = payload => {res.writeHead(200, {'Content-Type': 'application/json'});res.end(JSON.stringify(payload));};
  if (url.pathname === '/api/auth/session') return json({authenticated: true, user: {role: 'controller', display_name: 'QA'}, csrf_token: 'fixture'});
  if (url.pathname === '/api/health-check') return json(healthMode === 'node'
    ? {results: [{profile: 'natal', label: 'Natal', online: true, elapsed_ms: 27}, {profile: 'recife', label: 'Recife', online: false, elapsed_ms: 4000}], generated_at: '2026-10-10T13:00:00Z'}
    : {bases: [{label: 'Natal', host: 'qa.local', port: 7777, online: true, latency_ms: 18}], checked_at: '2026-10-10T14:00:00Z'});
  if (url.pathname.startsWith('/api/')) {res.writeHead(url.pathname === '/api/intelligence' ? 404 : 503);return res.end();}
  const local = path.join(root, url.pathname === '/' ? 'index.html' : url.pathname);
  if (!local.startsWith(root + path.sep) || !fs.existsSync(local)) {res.writeHead(404);return res.end();}
  const types = {'.css': 'text/css', '.js': 'application/javascript', '.html': 'text/html', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2'};
  res.writeHead(200, {'Content-Type': types[path.extname(local)] || 'application/octet-stream'});res.end(fs.readFileSync(local));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1325, height: 655}, reducedMotion: 'reduce'});
    const errors = [];page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => document.querySelector('#operatorRole').textContent.includes('Controlador'));
    await page.locator('#termsAcceptButton').click();
    await page.locator('#dashboardModule').click();
    // Initialization is intentionally blocked by this fixture; dismiss its unrelated toast for screenshots.
    await page.locator('#toast').evaluate(el => el.classList.add('hidden'));
    const metrics = await page.locator('.dashboard-metrics').evaluate(el => {
      const wrapper = getComputedStyle(el), card = getComputedStyle(el.firstElementChild);
      return {wrapperBorder: wrapper.borderTopWidth, wrapperBackground: wrapper.backgroundColor, cardBorders: [card.borderTopWidth, card.borderRightWidth, card.borderBottomWidth, card.borderLeftWidth]};
    });
    const gutters = await page.locator('main, .side-nav, .side-nav-scroll, .table-scroll').evaluateAll(els => els.map(el => ({className: el.className, gutter: getComputedStyle(el).scrollbarGutter, color: getComputedStyle(el).scrollbarColor})));
    console.log(JSON.stringify({metrics, gutters}));
    await page.screenshot({path: path.join(artifactRoot, 'dashboard-desktop.png'), fullPage: true});
    assert.equal(metrics.wrapperBorder, '0px');
    assert.equal(metrics.wrapperBackground, 'rgba(0, 0, 0, 0)');
    assert.deepEqual(metrics.cardBorders, ['1px', '1px', '1px', '1px']);
    assert.ok(gutters.every(row => row.gutter === 'auto'), 'Unexpected reserved scrollbar gutters');
    const footer = await page.locator('.side-nav-footer').evaluate(el => {
      const rect = el.getBoundingClientRect();
      return Array.from(el.querySelectorAll('img, .side-nav-assurance, .side-nav-legal')).every(item => {
        const box = item.getBoundingClientRect();return box.left >= rect.left && box.right <= rect.right && box.bottom <= rect.bottom;
      });
    });
    assert.equal(footer, true, 'Footer content clipped');
    await page.locator('#intelligenceModule').click();
    await page.waitForFunction(() => document.querySelector('#intelligenceGenerated').textContent.includes('indisponivel nesta implantacao'));
    assert.equal(await page.locator('#intelligenceSuccessRate').textContent(), '—');
    assert.equal(await page.locator('#intelligencePdf').isDisabled(), true);
    await page.locator('#healthBaseGrid').getByText('27 ms', {exact: true}).waitFor();
    assert.doesNotMatch(await page.locator('#healthBaseGrid').textContent(), /undefined/);
    assert.doesNotMatch(await page.locator('#healthCheckedAt').textContent(), /undefined/);
    await page.screenshot({path: path.join(artifactRoot, 'intelligence-desktop.png'), fullPage: true});
    healthMode = 'python';await page.locator('#healthRefresh').click();
    await page.locator('#healthBaseGrid').getByText('qa.local:7777', {exact: true}).waitFor();
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(artifactRoot, 'intelligence-mobile.png'), fullPage: true});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile overflow');
    assert.deepEqual(errors, []);
    console.log('QA_WORKSPACE_OK: separated cards, scrollbar tracks, footer containment, empty-body 404, both health contracts, mobile');
  } finally {await browser.close();server.close();}
})().catch(error => {console.error(error);process.exitCode = 1;server.close();});
