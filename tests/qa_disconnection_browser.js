'use strict';
// Integration QA only: isolated fixtures; never included in the product/release.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname,'../static');
const photo = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg';
const fixture = {mode:'test',groups:{'fixture@g.us':{city:'FORTALEZA'}},batches:[
  {id:'fixture-one',contract:'1234567',group:'fixture@g.us',city:'FORTALEZA',state:'review',revision:1,created_at:Date.now(),technician:{name:'Técnico de teste'},messages:[{text:'1234567 · 430\nEquipamento recolhido <script>unsafe</script>',photo,reading:{message:'Equipamento confirmado pelo leitor Atlas'}}],plan:{blockers:[],atlas:[{serial:'C85D38E6C2AE',type:'EMTA',contract:'1234567',state:'CLIENTE'}],operations:[{code:'430',service:'DESCONEXÃO',os:'0000000001',outgoing:[{serial:'C85D38E6C2AE',type:'EMTA'}],incoming:[],reason:'Evidência de teste'}]}},
  {id:'fixture-two',contract:'7654321',group:'fixture@g.us',state:'blocked',created_at:Date.now(),messages:[],plan:{blockers:['Consulta incompleta'],atlas:[],operations:[]}}
]};
let offline=false,decisionFailed=false,reads=0;
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  const json=(status,payload)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(payload));};
  if(url.pathname==='/api/auth/session')return json(200,{authenticated:true,user:{role:'controller',display_name:'Controlador de teste'},csrf_token:'fixture'});
  if(url.pathname==='/api/disconnection/state'){reads++;return offline?json(503,{error:'Serviço indisponível — evidências preservadas'}):json(200,fixture);}
  if(url.pathname==='/api/disconnection/decision')return decisionFailed?json(409,{error:'Lote mudou durante a conferência'}):json(200,{ok:true});
  if(url.pathname==='/api/disconnection/report.xlsx'){assert.match(url.searchParams.get('month'),/^\d{4}-\d{2}$/);res.writeHead(200,{'Content-Type':'application/octet-stream'});return res.end('fixture-report');}
  if(url.pathname.startsWith('/api/disconnection/photo/')){res.writeHead(200,{'Content-Type':'image/png'});return res.end(fs.readFileSync(path.join(root,'assets/brands/technet-concrete.png')));}
  // Stop unrelated backend initialization without making external connections.
  if(url.pathname.startsWith('/api/'))return json(503,{error:'Backend isolado para QA da interface'});
  const local=path.join(root,url.pathname==='/'?'index.html':url.pathname);
  if(!local.startsWith(root)||!fs.existsSync(local)){res.writeHead(404);return res.end();}
  const types={'.css':'text/css','.js':'application/javascript','.html':'text/html','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2'};
  res.writeHead(200,{'Content-Type':types[path.extname(local)]||'application/octet-stream'});res.end(fs.readFileSync(local));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/#desconexao`);
    await page.locator('#descDetail').getByText('C85D38E6C2AE').first().waitFor();
    await page.locator('#termsAcceptButton').click();
    assert.equal(await page.locator('#disconnectionWorkspace').isVisible(),true);
    assert.match(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundImage),/technet-concrete/);
    await page.evaluate(()=>document.documentElement.dataset.theme='light');
    assert.match(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundImage),/technet-concrete/);
    assert.match(await page.locator('#authGate').evaluate(el=>getComputedStyle(el).backgroundImage),/technet-concrete/);
    await page.evaluate(()=>document.documentElement.dataset.theme='dark');
    assert.equal(await page.locator('#descDetail script').count(),0);
    await page.screenshot({path:'/workspace/scratch/ac5a0d0f766e/inspection/dominium-desconexao-desktop.png',fullPage:true});
    await page.locator('[data-photo]').click();assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.open),true);await page.locator('#descPhotoClose').click();
    await page.locator('#descSearch').fill('7654321');assert.match(await page.locator('#descDetail').textContent(),/7654321/);assert.doesNotMatch(await page.locator('#descDetail').textContent(),/C85D38/);
    await page.locator('#descSearch').fill('');await page.locator('[data-batch="fixture-one"]').click();decisionFailed=true;await page.locator('[data-action="approve"]').click();await page.locator('#descError').getByText('Lote mudou durante a conferência').waitFor();
    offline=true;await page.locator('#descReload').click();await page.locator('#descError').getByText('Serviço indisponível').waitFor();assert.match(await page.locator('#descDetail').textContent(),/C85D38/);offline=false;
    const download=page.waitForEvent('download');await page.locator('#descExport').click();assert.match((await download).suggestedFilename(),/^DESCONEXAO_\d{4}-\d{2}\.xlsx$/);
    for(const id of ['dashboardModule','ordersModule','stockModule','techniciansModule','bulkCreateModule','importsModule','closeModule','reportModule','databaseModule','historyModule','intelligenceModule','disconnectionModule']){await page.locator('#'+id).click();await page.waitForTimeout(30);}
    assert.equal(await page.locator('#disconnectionWorkspace').isVisible(),true);
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/workspace/scratch/ac5a0d0f766e/inspection/dominium-desconexao-mobile.png',fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'mobile horizontal overflow');
    const prior=reads;await page.evaluate(()=>document.dispatchEvent(new CustomEvent('dominium:auth-cleared')));assert.doesNotMatch(await page.locator('#descDetail').textContent(),/C85D38/);assert.equal(reads,prior);
    assert.deepEqual(errors,[]);
    console.log('QA_BROWSER_OK: navigation, filters, photos, failure preservation, report, logout, mobile, original background');
  }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
