'use strict';
// Isolated UI fixtures. This file is never shipped with the product.
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../static');
const photo='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jpg';
const second='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jpg';
const batch={id:'fixture-one',contract:'1234567',state:'buffering',revision:1,created_at:Date.now(),deadline:Date.now()+60000,messages:[{text:'1234567 · 430',photo},{photo:second}],plan:{blockers:[],atlas:[],operations:[]}};
let lookupCount=0,applyCount=0,lookupDelay=0,stateDelay=0,historyDelay=0,fail='',failApply='',expiryDuration=300000,mismatch=false,canApply=true,role='controller';
let fixture={mode:'test',capabilities:{manual_serial:true},groups:{},batches:[batch]};
let applyBody;
const section=fs.readFileSync(path.join(root,'index.html'),'utf8').match(/<section class="disconnection-workspace[\s\S]*?<\/section>\s*<section class="dashboard-workspace/)[0].replace(/\s*<section class="dashboard-workspace$/,'').replace('disconnection-workspace hidden','disconnection-workspace');
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');
 const json=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
 if(url.pathname==='/') {res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});return res.end(`<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/workspace.css"></head><body>${section}<script src="/disconnection.js"></script><script>window.qaRole='${role}';window.qaRequests=[];window.qaController=DominiumDisconnection.mount({getUser:()=>window.qaRole?{role:window.qaRole}:null,requestBlob:()=>{},request:async(url,options={})=>{qaRequests.push({url,...options});const response=await fetch(url,{...options,headers:{'Content-Type':'application/json'}});const data=await response.json();if(!response.ok)throw new Error(data.error);return data;}});qaController.activate();</script></body></html>`);}
 if(url.pathname==='/api/disconnection/state'){const snapshot=structuredClone(fixture);setTimeout(()=>json(200,snapshot),stateDelay);return;}
 if(url.pathname==='/api/disconnection/history'){const snapshot={...structuredClone(fixture),view:'history'};setTimeout(()=>json(200,snapshot),historyDelay);return;}
 if(url.pathname==='/api/disconnection/serial-lookup') {
  lookupCount++;const local={fail,mismatch,canApply};let body='';req.on('data',chunk=>body+=chunk);req.on('end',()=>setTimeout(()=>{
   if(local.fail)return json(422,{error:local.fail});
   const payload=JSON.parse(body);json(200,{ok:true,query_token:'fixture-token',serial:payload.serial.toUpperCase(),equipment:{serial:payload.serial.toUpperCase(),contract:local.mismatch?'7654321':'1234567',type:'EMTA <script>unsafe</script>',state:'CLIENTE',date:'10/10/2026',history:[{numero_contrato:'1234567',data_alteracao:'10/10/2026',estado:'CLIENTE'}],source:'ATLAS'},matches_contract:!local.mismatch,can_apply:local.canApply,expires_at:Date.now()+expiryDuration});
  },lookupDelay));return;
 }
 if(url.pathname==='/api/disconnection/serial-apply') {applyCount++;let body='';req.on('data',chunk=>body+=chunk);req.on('end',()=>{applyBody=JSON.parse(body);if(failApply)return json(409,{error:failApply});batch.revision++;batch.plan.atlas=[{serial:'ABC123456',contract:'1234567',type:'EMTA'}];json(200,{ok:true,batch});});return;}
 if(url.pathname.startsWith('/api/disconnection/photo/')) {res.writeHead(200,{'Content-Type':'image/svg+xml'});return res.end('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="#34343c"/><text x="400" y="450" fill="white" font-size="90">ABC123456</text></svg>');}
 const local=path.join(root,url.pathname);if(!local.startsWith(root)||!fs.existsSync(local)){res.writeHead(404);return res.end();}
 res.writeHead(200,{'Content-Type':url.pathname.endsWith('.css')?'text/css':'application/javascript'});res.end(fs.readFileSync(local));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const open=async(index=0)=>{await page.locator('[data-photo]').nth(index).click();await page.locator('#descSerialInput').waitFor();};
  const lookup=async(serial='abc123456')=>{await page.locator('#descSerialInput').fill(serial);await page.locator('#descSerialLookup').click();};
  await open();assert.equal(await page.locator('#descSerialInput').isVisible(),true);
  assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'100%');
  await page.locator('#descPhotoZoomIn').click();assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'125%');
  await page.locator('#descPhotoViewport').focus();await page.keyboard.press('+');assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'150%');
  await page.keyboard.press('0');assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'100%');
  await page.locator('#descPhotoViewport').click({position:{x:200,y:180}});assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'200%');
  await page.locator('#descPhotoReset').click();
  const transform=()=>page.locator('#descPhotoLarge').evaluate(el=>{const m=new DOMMatrix(getComputedStyle(el).transform);return {scale:m.a,x:m.e,y:m.f};});
  const beforeWheel=await transform();
  await page.locator('#descPhotoViewport').evaluate(el=>el.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,clientX:el.getBoundingClientRect().left+200,clientY:el.getBoundingClientRect().top+300,bubbles:true,cancelable:true})));
  assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'125%');
  const afterWheel=await transform();assert.ok(Math.abs((200-beforeWheel.x)/beforeWheel.scale-(200-afterWheel.x)/afterWheel.scale)<.001,'wheel zoom preserves horizontal label anchor');assert.ok(Math.abs((300-beforeWheel.y)/beforeWheel.scale-(300-afterWheel.y)/afterWheel.scale)<.001,'wheel zoom preserves vertical label anchor');
  const viewBounds=await page.locator('#descPhotoViewport').boundingBox();await page.mouse.move(viewBounds.x+300,viewBounds.y+300);await page.mouse.down();await page.mouse.move(viewBounds.x+350,viewBounds.y+300,{steps:4});await page.mouse.up();assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'125%');assert.ok((await transform()).x>afterWheel.x,'drag pans the zoomed photo without toggling zoom');
  for(let i=0;i<11;i++)await page.locator('#descPhotoZoomIn').click();assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'400%');assert.equal(await page.locator('#descPhotoZoomIn').isDisabled(),true);
  await lookup();await page.locator('#descSerialResult').getByText('ABC123456',{exact:true}).waitFor();
  assert.equal(await page.locator('#descSerialResult script').count(),0);
  if(process.env.QA_SCREENSHOT_DIR){fs.mkdirSync(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.QA_SCREENSHOT_DIR,'photo-assist-desktop.png')});}
  assert.equal(await page.locator('#descSerialApply').isDisabled(),true);
  await page.locator('#descSerialConfirm').check();assert.equal(await page.locator('#descSerialApply').isEnabled(),true);
  assert.equal(applyCount,0);await page.locator('#descSerialApply').click();await page.locator('#descSerialStatus').getByText('Serial aplicado').waitFor();
  assert.deepEqual(applyBody,{id:'fixture-one',photo,revision:1,query_token:'fixture-token'});assert.equal(applyCount,1);
  assert.match(await page.locator('#descDetail').textContent(),/ABC123456/);
  await page.keyboard.press('Escape');assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.open),false);
  mismatch=true;await open();await lookup();await page.locator('#descSerialStatus').getByText('diverge').waitFor();assert.equal(await page.locator('#descSerialApply').isVisible(),false);assert.equal(applyCount,1);
  await page.locator('#descPhotoClose').click();mismatch=false;fail='Serial não encontrado no Atlas';await open();await lookup();await page.locator('#descSerialStatus').getByText(fail).waitFor();assert.equal(await page.locator('#descSerialApply').isVisible(),false);
  fail='';lookupDelay=250;await lookup('oldserial');await page.locator('#descPhotoClose').click();await open(1);await page.waitForTimeout(350);assert.doesNotMatch(await page.locator('#descSerialResult').textContent(),/OLDSERIAL/);assert.equal(await page.locator('#descSerialInput').inputValue(),'');
  lookupDelay=0;canApply=false;await lookup();await page.locator('#descSerialResult').getByText('ABC123456',{exact:true}).waitFor();assert.equal(await page.locator('#descSerialApply').isVisible(),false);canApply=true;
  expiryDuration=400;await lookup();await page.locator('#descSerialConfirm').check();await page.locator('#descSerialStatus').getByText('Consulta expirada').waitFor();assert.equal(await page.locator('#descSerialApply').isVisible(),false);assert.equal(applyCount,1);expiryDuration=300000;
  failApply='Lote mudou. Consulte novamente.';await lookup();await page.locator('#descSerialConfirm').check();await page.locator('#descSerialApply').click();await page.locator('#descSerialStatus').getByText(failApply).waitFor();assert.equal(await page.locator('#descSerialApply').isVisible(),false);failApply='';
  await lookup();await page.locator('#descSerialConfirm').check();stateDelay=250;await page.evaluate(()=>document.querySelector('#descReload').click());await page.locator('#descSerialApply').click();await page.locator('#descSerialStatus').getByText('Serial aplicado').waitFor();await page.waitForTimeout(350);assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.open),true,'an older poll response must not replace the applied batch revision');stateDelay=0;
  await page.locator('#descPhotoClose').click();batch.contract='';await page.locator('#descReload').click();await page.locator('#descDetail').getByText('Contrato não identificado',{exact:true}).waitFor();await open();await lookup();await page.locator('#descSerialStatus').getByText('será vinculado ao contrato 1234567').waitFor();assert.equal(await page.locator('#descSerialApply').isDisabled(),true);await page.locator('#descPhotoClose').click();batch.contract='1234567';await page.locator('#descReload').click();await page.locator('#descDetail').getByText('Contrato 1234567',{exact:true}).waitFor();await open();
  await page.locator('#descPhotoClose').click();stateDelay=250;await page.locator('#descReload').click();await page.locator('#descHistoryOpen').click();assert.equal(await page.locator('#descDetail [data-link-tech]:enabled').count(),0,'history selection immediately removes writable queue controls');await page.waitForTimeout(350);
  assert.match(await page.locator('#descMode').textContent(),/somente leitura/,'a history selection during an older queue fetch must load the selected history');
  assert.equal(await page.locator('[data-link-tech]').isDisabled(),true,'a history selection cannot retain queue write controls');
  assert.ok((await page.evaluate(()=>qaRequests)).some(item=>item.url.startsWith('/api/disconnection/history?date=')),'busy queue fetch must schedule the selected history fetch');stateDelay=0;
  await open();assert.equal(await page.locator('#descSerialInput').isDisabled(),true);assert.equal(await page.locator('#descSerialLookup').isDisabled(),true);await page.locator('#descPhotoZoomIn').click();assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'125%');
  await page.evaluate(()=>document.querySelector('#descReload').click());await page.waitForTimeout(100);assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.open),true,'refreshing read-only history preserves the open photo');await page.locator('#descPhotoClose').click();
  historyDelay=250;await page.locator('#descReload').click();await page.locator('#descHistoryToday').click();await page.waitForTimeout(350);await page.locator('#descMode').getByText('baixas em teste').waitFor();assert.equal(await page.locator('[data-link-tech]').isEnabled(),true,'returning to today during a history fetch restores current queue actions');historyDelay=0;
  await page.evaluate(()=>window.qaRole='viewer');await open();assert.equal(await page.locator('#descSerialLookup').isDisabled(),true);await page.locator('#descPhotoClose').click();await page.evaluate(()=>window.qaRole='controller');
  delete fixture.capabilities;await page.locator('#descReload').click();await page.waitForTimeout(100);await open();assert.equal(await page.locator('#descSerialInput').isDisabled(),true,'unsupported manual serial capability must disable the field');assert.equal(await page.locator('#descSerialLookup').isDisabled(),true);await page.locator('#descSerialReadOnly').getByText('Consulta manual indisponível no momento.').waitFor();const priorLookups=lookupCount;await page.locator('#descSerialForm').evaluate(el=>el.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await page.waitForTimeout(100);assert.equal(lookupCount,priorLookups,'unsupported backend must receive no serial requests');await page.locator('#descPhotoZoomIn').click();assert.equal(await page.locator('#descPhotoZoomLevel').textContent(),'125%');await page.locator('#descPhotoClose').click();fixture.capabilities={manual_serial:true};await page.locator('#descReload').click();await page.waitForTimeout(100);
  await page.setViewportSize({width:390,height:844});await open();assert.equal(await page.locator('#descSerialInput').isVisible(),true);
  assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.scrollWidth<=el.clientWidth),true,'mobile dialog horizontal overflow');
  await lookup();await page.locator('#descSerialConfirm').check();const closeBounds=await page.locator('#descPhotoClose').boundingBox();assert.ok(closeBounds.y>=0&&closeBounds.y+closeBounds.height<=844,'mobile close button remains available when confirming serial');if(process.env.QA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.QA_SCREENSHOT_DIR,'photo-assist-mobile.png')});await page.locator('#descSerialInput').fill('changed');assert.equal(await page.locator('#descSerialApply').isVisible(),false,'editing invalidates token');
  lookupDelay=250;await lookup('secret');await page.evaluate(()=>{window.qaRole=null;document.dispatchEvent(new CustomEvent('dominium:auth-cleared'));});await page.waitForTimeout(350);assert.equal(await page.locator('#descPhotoDialog').evaluate(el=>el.open),false);assert.equal(await page.locator('#descSerialResult').textContent(),'');assert.equal(await page.locator('#descPhotoLarge').getAttribute('src'),null);
  assert.deepEqual(errors,[]);assert.ok(lookupCount>=5);console.log('QA_PHOTO_ASSIST_OK: zoom, keyboard, Atlas lookup, explicit apply, mismatch, errors, stale modal, read-only history, roles, mobile, logout');
 } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
