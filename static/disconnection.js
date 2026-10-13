(function (global) {
  'use strict';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const stateLabel = state => ({buffering:'Recebendo evidências',processing:'Consultando',review:'Pronta para revisão',blocked:'Precisa de conferência',simulated:'Simulada',rejected:'Recusada',executed:'Baixa confirmada'}[state] || 'Aguardando');
  const photoUrl = name => /^[a-f0-9-]{36}\.jpg$/.test(String(name || '')) ? '/api/disconnection/photo/' + name : '';
  function photoTransform(prior, scale, point, bounds) {
    scale = Math.max(1, Math.min(4, scale));
    const offset = (value, size, viewport) => size <= viewport ? (viewport-size)/2 : Math.max(viewport-size, Math.min(0,value));
    return {scale,
      x:offset(point.x-(point.x-prior.x)*scale/prior.scale,bounds.imageWidth*scale,bounds.width),
      y:offset(point.y-(point.y-prior.y)*scale/prior.scale,bounds.imageHeight*scale,bounds.height)};
  }
  function visibleBatches(rows, {search = '', state = 'all', group = ''} = {}) {
    const term = norm(search);
    return (rows || []).filter(batch => (state === 'all' || batch.state === state) && (!group || batch.group === group) && (!term || norm([batch.contract,batch.technician?.name,batch.city,batch.plan?.operations?.map(item=>item.os).join(' '),(batch.plan?.atlas||batch.atlas||[]).map(item=>(item.serial||item.resultado?.serial_baixavel||'')).join(' '),batch.messages?.map(m=>m.text).join(' ')].join(' ')).includes(term)));
  }
  let controller;
  function mount({request, requestBlob, getUser}) {
    const root = document.getElementById('disconnectionWorkspace');
    if (!root || controller) return controller;
    let data = null, selected = '', active = false, busy = false, pendingLoad = false, timer = null, error = '', authEpoch = 0, dataEpoch = 0, updatedAt = null, historyDate = '';
    const find = id => root.querySelector('#' + id);
    const notes = new Map();
    let photoContext=null, photoEpoch=0, serialResult=null, serialBusy='', expiryTimer=null;
    let photoView={scale:1,x:0,y:0}, photoBounds={width:0,height:0,imageWidth:0,imageHeight:0}, drag=null, dragged=false;
    const photoDialog=find('descPhotoDialog'), viewport=find('descPhotoViewport'), photoImage=find('descPhotoLarge');
    const canEditBatch=()=>data?.view!=='history' && !historyDate && ['admin','controller'].includes(getUser()?.role);
    const canAssist=()=>canEditBatch() && data?.capabilities?.manual_serial===true;
    function photoCurrent(context, epoch) {
      return photoDialog.open && photoContext===context && photoEpoch===epoch && context.authEpoch===authEpoch &&
        selected===context.id && data?.batches?.some(batch=>batch.id===context.id && batch.revision===context.revision) && canAssist();
    }
    function serialStatus(message='') {find('descSerialStatus').textContent=message;find('descSerialStatus').classList.toggle('hidden',!message);}
    function clearSerialResult() {
      clearTimeout(expiryTimer);expiryTimer=null;serialResult=null;find('descSerialResult').innerHTML='';find('descSerialConfirm').checked=false;find('descSerialApplyArea').classList.add('hidden');
    }
    function updateSerialControls() {
      const allowed=canAssist();find('descSerialInput').disabled=!allowed || !!serialBusy;find('descSerialLookup').disabled=!allowed || !!serialBusy;
      find('descSerialLookup').textContent=serialBusy==='lookup'?'Consultando Atlas…':'Consultar Atlas';
      find('descSerialConfirm').disabled=!!serialBusy;
      find('descSerialApply').disabled=!allowed || !!serialBusy || !serialResult || serialResult.expires_at<=Date.now() || !find('descSerialConfirm').checked;
      find('descSerialApply').textContent=serialBusy==='apply'?'Aplicando serial…':'Aplicar serial ao lote';
      find('descSerialReadOnly').textContent=allowed?'':data?.view==='history'||historyDate?'Histórico: somente leitura. Volte à fila atual para consultar e aplicar um serial.':!canEditBatch()?'A consulta manual está disponível para administradores e controladores.':'Consulta manual indisponível no momento.';
    }
    function clearPhoto() {
      photoEpoch++;photoContext=null;serialBusy='';clearSerialResult();serialStatus();find('descSerialForm').reset();photoImage.removeAttribute('src');photoImage.style.transform='';drag=null;updateSerialControls();
    }
    function closePhoto() {if(photoDialog.open)photoDialog.close();clearPhoto();}
    function drawPhoto() {
      photoImage.style.width=photoBounds.imageWidth+'px';photoImage.style.height=photoBounds.imageHeight+'px';
      photoImage.style.transform=`translate(${photoView.x}px, ${photoView.y}px) scale(${photoView.scale})`;
      viewport.classList.toggle('zoomed',photoView.scale>1);find('descPhotoZoomLevel').textContent=Math.round(photoView.scale*100)+'%';
      find('descPhotoZoomOut').disabled=photoView.scale<=1;find('descPhotoZoomIn').disabled=photoView.scale>=4;
    }
    function fitPhoto() {
      if(!photoDialog.open||!photoImage.naturalWidth)return;
      const width=viewport.clientWidth,height=viewport.clientHeight,fit=Math.min(width/photoImage.naturalWidth,height/photoImage.naturalHeight);
      photoBounds={width,height,imageWidth:photoImage.naturalWidth*fit,imageHeight:photoImage.naturalHeight*fit};
      photoView=photoTransform({scale:1,x:0,y:0},1,{x:0,y:0},photoBounds);drawPhoto();
    }
    function zoomPhoto(scale, point={x:photoBounds.width/2,y:photoBounds.height/2}) {
      photoView=photoTransform(photoView,scale,point,photoBounds);drawPhoto();
    }
    function openPhoto(name) {
      const batch=data?.batches?.find(item=>item.id===selected);
      if(!batch||!batch.messages?.some(message=>message.photo===name)||!photoUrl(name))return;
      closePhoto();photoContext={id:batch.id,photo:name,revision:batch.revision,contract:batch.contract,authEpoch,historyDate,view:data?.view};
      find('descPhotoContext').textContent=batch.contract?'Contrato '+batch.contract:'Contrato a identificar';
      photoView={scale:1,x:0,y:0};drawPhoto();photoImage.src=photoUrl(name);photoDialog.showModal();updateSerialControls();fitPhoto();find('descSerialInput').focus();
    }
    function showSerialResult(result, context) {
      clearSerialResult();serialResult=result;
      const item=result.equipment||{};
      find('descSerialResult').innerHTML=`<article class="desc-equipment"><span>ATLAS · ${escape(item.type||'Equipamento')}</span><strong>${escape(item.serial||result.serial)}</strong><small>Contrato ${escape(item.contract||'Não informado')}</small><small>${escape(item.state||'Estado não informado')} · ${escape(item.date||'Data não informada')}</small>${item.embratel?'<span class="desc-state">EMBRATEL · proposta 400</span>':''}${item.history?.length?`<details><summary>Histórico Atlas</summary>${item.history.map(row=>`<p class="desc-muted">${escape(row.data_alteracao||row.date)} · ${escape(row.numero_contrato||row.contract||'Sem contrato')} · ${escape(row.tipo_localizacao||row.localizacao||'')} · ${escape(row.estado||row.state||'')}</p>`).join('')}</details>`:''}</article>`;
      const applicable=result.matches_contract===true && result.can_apply===true && typeof result.query_token==='string' && result.expires_at>Date.now();
      find('descSerialApplyArea').classList.toggle('hidden',!applicable);
      serialStatus(result.matches_contract!==true?`O contrato ${item.contract||'não informado'} do Atlas diverge do contrato ${context.contract||'do lote'}. Este serial não pode ser aplicado.`:!applicable?'Equipamento encontrado. A aplicação está indisponível para o estado atual deste lote.':context.contract?'Equipamento encontrado no contrato deste lote. Confira a etiqueta antes de aplicar.':`Equipamento encontrado. Ao confirmar, o lote será vinculado ao contrato ${item.contract||'identificado no Atlas'}.`);
      if(applicable)expiryTimer=setTimeout(()=>{if(serialResult===result){clearSerialResult();serialStatus('Consulta expirada. Consulte o serial novamente antes de aplicar.');updateSerialControls();}},Math.min(2147483647,result.expires_at-Date.now()));
      updateSerialControls();
    }
    async function lookupSerial(event) {
      event.preventDefault();const context=photoContext,serial=find('descSerialInput').value.trim();
      if(!context||!canAssist()||serialBusy||!serial)return;
      clearSerialResult();const epoch=++photoEpoch;serialBusy='lookup';serialStatus('Consultando equipamento no Atlas…');updateSerialControls();
      try {
        const result=await request('/api/disconnection/serial-lookup',{method:'POST',body:JSON.stringify({id:context.id,photo:context.photo,serial,revision:context.revision}),timeoutMs:45000});
        if(!photoCurrent(context,epoch))return;showSerialResult(result,context);
      } catch(failure) {if(photoCurrent(context,epoch))serialStatus(failure.message||'Não foi possível consultar o Atlas.');}
      finally {if(photoContext===context&&photoEpoch===epoch){serialBusy='';updateSerialControls();}}
    }
    async function applySerial() {
      const context=photoContext,result=serialResult,epoch=photoEpoch;
      if(!context||!photoCurrent(context,epoch)||serialBusy||!result||result.matches_contract!==true||result.can_apply!==true||!find('descSerialConfirm').checked)return;
      if(result.expires_at<=Date.now()){clearSerialResult();serialStatus('Consulta expirada. Consulte o serial novamente antes de aplicar.');updateSerialControls();return;}
      serialBusy='apply';serialStatus('Aplicando serial confirmado ao lote…');updateSerialControls();
      try {
        const response=await request('/api/disconnection/serial-apply',{method:'POST',body:JSON.stringify({id:context.id,photo:context.photo,revision:context.revision,query_token:result.query_token}),timeoutMs:120000});
        if(!photoCurrent(context,epoch))return;
        if(response.batch){dataEpoch++;data.batches=data.batches.map(batch=>batch.id===context.id?response.batch:batch);context.revision=response.batch.revision;context.contract=response.batch.contract;find('descPhotoContext').textContent=context.contract?'Contrato '+context.contract:'Contrato a identificar';render();}
        clearSerialResult();serialStatus('Serial aplicado ao lote. '+(data?.mode==='test'?'A baixa permanece em modo de teste.':'Revise as evidências antes de aprovar a baixa.'));
      } catch(failure) {if(photoCurrent(context,epoch)){clearSerialResult();serialStatus(failure.message||'Não foi possível aplicar o serial. Consulte novamente.');}}
      finally {if(photoContext===context&&photoEpoch===epoch){serialBusy='';updateSerialControls();}}
    }
    const filters = () => ({search:find('descSearch').value,state:find('descState').value,group:find('descGroup').value});
    function render() {
      const rows = data?.batches || [];
      find('descMode').textContent = historyDate || data?.view === 'history' ? 'Histórico · somente leitura' : data?.mode === 'test' ? 'Revisão · baixas em teste' : data?.mode === 'production' ? 'Operação ativa' : 'Conectando ao Bot';
      find('descHistoryLabel').textContent = historyDate ? 'Fotos de '+historyDate.split('-').reverse().join('/')+' · somente leitura · até 7 dias' : 'Fila atual · fotos preservadas por 7 dias';
      find('descError').textContent = error;
      find('descError').classList.toggle('hidden', !error);
      find('descUpdated').textContent = updatedAt ? 'Atualizado às ' + updatedAt.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}) : 'Aguardando conexão';
      for (const [key, states] of Object.entries({Received:['buffering','processing'],Ready:['review'],Blocked:['blocked'],Done:['simulated','executed']})) find('desc'+key).textContent = data ? rows.filter(row=>states.includes(row.state)).length : '—';
      const filtered = visibleBatches(rows, filters());
      if (!filtered.some(batch=>batch.id===selected)) selected = filtered[0]?.id || '';
      find('descCount').textContent = filtered.length + ' lotes';
      find('descList').innerHTML = filtered.length ? filtered.map(batch=>{
        const photo = batch.messages?.find(message=>photoUrl(message.photo));
        return `<button type="button" class="desc-batch ${batch.id===selected?'selected':''}" data-batch="${escape(batch.id)}" aria-pressed="${batch.id===selected}">
          ${photo?`<img src="${photoUrl(photo.photo)}" alt="Foto do equipamento" loading="lazy">`:'<span class="desc-contract-icon" aria-hidden="true">#</span>'}
          <span><strong>${escape(batch.contract || 'Contrato a identificar')}</strong><small>${escape(batch.technician?.name || batch.sender_name || 'Técnico a vincular')}</small><span class="desc-state ${escape(batch.state)}">${escape(stateLabel(batch.state))}</span></span>
          <time>${new Date(batch.created_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time></button>`;
      }).join('') : `<div class="desc-empty"><i data-lucide="inbox"></i><h3>${data?'Nenhum lote neste filtro':'Conectando à DESCONEXÃO'}</h3><p>${data?'As mensagens dos técnicos aparecem aqui com suas fotos e evidências.':'Os dados serão exibidos quando o serviço responder.'}</p></div>`;
      const batch = rows.find(row=>row.id===selected);
      if(photoContext && (photoContext.id!==selected || !batch || batch.revision!==photoContext.revision || photoContext.historyDate!==historyDate || photoContext.view!==data?.view))closePhoto();
      if(photoContext){if(!canAssist()){clearSerialResult();serialStatus();}updateSerialControls();}
      const detail = find('descDetail');
      if (!batch) { detail.innerHTML = '<div class="desc-empty"><i data-lucide="scan-line"></i><h3>Conferência do contrato</h3><p>Selecione um lote para ver a mensagem, as fotos e o resultado do Atlas.</p></div>'; global.lucide?.createIcons(); return; }
      const plan = batch.plan, canWrite = canEditBatch(), blockers = plan?.blockers || batch.capture_errors || [];
      const date = new Date(batch.created_at).toLocaleString('pt-BR');
      const evidence = plan?.atlas || [];
      detail.innerHTML = `<header class="desc-detail-heading"><div><p class="section-label">${escape(batch.city || 'DESCONEXÃO')}</p><h3>Contrato ${escape(batch.contract || 'não identificado')}</h3><p>${escape(batch.technician?.name || 'Técnico a vincular')} <span>· ${escape(date)}</span></p></div><span class="desc-state ${escape(batch.state)}">${escape(stateLabel(batch.state))}</span></header>
        ${batch.demo?'<p class="desc-alert">Demonstração: este lote não corresponde a uma OS real.</p>':''}
        ${batch.state==='buffering'?`<p class="desc-alert soft">Recebendo evidências deste técnico e contrato até ${new Date(batch.deadline).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}.</p>`:''}
        <section class="desc-section"><h4>Vínculo do técnico e OS</h4><p class="desc-muted">WhatsApp: ${escape(batch.sender || 'Não informado')}<br>Recurso Imperium: ${escape(batch.technician?.imperium_id || 'A vincular')}</p>${batch.imperium?.confirmed===true?`<p class="desc-muted">Consultado em ${escape(new Date(batch.imperium.checked_at).toLocaleString('pt-BR'))}</p>${batch.imperium.orders?.length?batch.imperium.orders.map(order=>`<p>OS ${escape(order.num_os)} · ${escape(order.installer_name || 'Técnico')} · recurso ${escape(order.installer_id)} ${String(order.installer_id)===String(batch.technician?.imperium_id)?'· coincide com o remetente':'· diverge do remetente'}</p>`).join(''):'<p class="desc-muted">Nenhuma OS aberta encontrada no contrato nesta consulta.</p>'}`:'<p class="desc-muted">Reconsulte as evidências para conferir a OS aberta no Imperium.</p>'}</section>
        <section class="desc-section"><h4>Mensagem e fotos</h4><div class="desc-messages">${(batch.messages||[]).map(message=>`<article class="desc-message">${message.text?`<p>${escape(message.text)}</p>`:''}${photoUrl(message.photo)?`<button class="desc-photo-button" type="button" data-photo="${escape(message.photo)}"><img src="${photoUrl(message.photo)}" alt="Foto enviada pelo técnico — ampliar" loading="lazy"></button><small>${escape(message.reading?.message || 'Foto preservada para conferência')}</small>`:''}</article>`).join('')}</div></section>
        <section class="desc-section"><h4>Identificação no Atlas <span>${evidence.length} equipamentos</span></h4>${evidence.length?`<div class="desc-equipment-grid">${evidence.map(item=>`<article class="desc-equipment"><span>${escape(item.type)}</span><strong>${escape(item.serial)}</strong><small>Contrato ${escape(item.contract)} · ${escape(item.state || 'Estado não informado')}</small><small>${escape(item.date || '')}</small>${item.embratel?'<span class="desc-state">EMBRATEL · proposta 400</span>':''}${item.history?.length?`<details><summary>Histórico Atlas</summary>${item.history.map(row=>`<p class="desc-muted">${escape(row.data_alteracao)} · ${escape(row.numero_contrato || 'Sem contrato')} · ${escape(row.tipo_localizacao || row.localizacao)} · ${escape(row.estado)}</p>`).join('')}</details>`:''}</article>`).join('')}</div>`:'<p class="desc-muted">A identificação confirmada aparece após a leitura da foto e a consulta no Atlas.</p>'}</section>
        <section class="desc-section"><h4>Movimentação da baixa</h4>${(plan?.operations||[]).map(operation=>`<article class="desc-operation"><header><strong>${escape(operation.code)} · ${escape(operation.service)}</strong><small>${operation.os?'OS '+escape(operation.os):'Proposta de criação de OS'}</small></header><div class="desc-movements"><div><span>SAINDO</span>${equipmentList(operation.outgoing)}</div><div><span>ENTRANDO</span>${equipmentList(operation.incoming)}</div></div>${operation.materials?.length?`<p>Materiais: ${operation.materials.map(item=>escape(item.description)+' × '+escape(item.quantity)).join(', ')}</p>`:''}<small>${escape(operation.reason)}</small></article>`).join('') || '<p class="desc-muted">Aguardando evidências e consulta TOA dos controladores.</p>'}</section>
        ${blockers.length?`<section class="desc-alert"><h4>Precisa de conferência</h4><ul>${blockers.map(item=>`<li>${escape(item)}</li>`).join('')}</ul></section>`:''}
        ${plan?.warnings?.length?`<p class="desc-muted">${plan.warnings.map(escape).join(' · ')}</p>`:''}
        ${batch.decision?`<p class="desc-muted">${escape(stateLabel(batch.state))} por ${escape(batch.decision.actor)} · ${escape(new Date(batch.decision.at).toLocaleString('pt-BR'))}${batch.decision.note?' · '+escape(batch.decision.note):''}</p>`:''}
        <label class="desc-note">Observação da revisão<textarea data-review-note rows="2" maxlength="1000" placeholder="Opcional" ${!canWrite?'disabled':''}>${escape(notes.get(batch.id)||'')}</textarea></label>
        <footer class="desc-detail-actions"><div><button type="button" class="button secondary" data-action="refresh" ${!canWrite || ['buffering','processing','simulated','executed','rejected'].includes(batch.state)?'disabled':''}><i data-lucide="refresh-cw"></i>Reconsultar evidências</button><button type="button" class="button secondary" data-link-tech ${!canWrite?'disabled':''}>Vincular técnico</button></div><div><button type="button" class="button secondary" data-action="reject" ${!canWrite || !['review','blocked'].includes(batch.state)?'disabled':''}>Recusar</button><button type="button" class="button primary" data-action="approve" ${!canWrite || batch.state!=='review' || blockers.length?'disabled':''}>${data?.mode==='test'?'Aprovar simulação':'Aprovar baixa'}</button></div></footer>
        ${data?.mode==='test'?'<p class="desc-muted">Neste modo, aprovar registra a simulação. Nenhuma baixa é enviada ao Imperium.</p>':''}`;
      global.lucide?.createIcons();
    }
    function equipmentList(items) { return items?.length ? '<ul>'+items.map(item=>`<li><strong>${escape(item.serial)}</strong><small>${escape(item.type || item.equipment_type || '')}</small></li>`).join('')+'</ul>' : '<p>Nenhum movimento registrado</p>'; }
    async function load({preserveError = false} = {}) {
      if (!getUser()) return;
      if (busy) {pendingLoad=true;return;}
      pendingLoad=false;
      const epoch = authEpoch, snapshotEpoch=dataEpoch, requestedDate=historyDate;
      busy = true;
      find('descReload').disabled = true;
      try {
        const route=requestedDate?'/api/disconnection/history?date='+encodeURIComponent(requestedDate):'/api/disconnection/state';
        const response = await request(route, {timeoutMs:25000});
        if(epoch !== authEpoch || snapshotEpoch !== dataEpoch || requestedDate !== historyDate) return;
        data = response; updatedAt = new Date(); if(!preserveError) error='';
        const select = find('descGroup'), prior = select.value;
        select.innerHTML = '<option value="">Todos os grupos</option>'+Object.entries(data.groups||{}).map(([id,group])=>`<option value="${escape(id)}">${escape(group.label || group.name || group.city || id)}</option>`).join(''); select.value=prior;
      } catch (failure) { if(epoch === authEpoch && snapshotEpoch === dataEpoch && requestedDate === historyDate) error=failure.message; }
      finally { busy=false;find('descReload').disabled=false;render();if(pendingLoad){pendingLoad=false;void load();} }
    }
    async function act(action) {
      const batch = data?.batches.find(item=>item.id===selected);
      if (!batch || busy || serialBusy==='apply' || !canEditBatch()) return;
      busy=true; root.classList.add('desc-busy');
      try {
        await request('/api/disconnection/'+(action==='refresh'?'refresh':'decision'), {method:'POST',body:JSON.stringify({id:batch.id,revision:batch.revision,action,note:notes.get(batch.id)||''}),timeoutMs:120000});error='';
      } catch (failure) { error=failure.message; }
      finally { busy=false;root.classList.remove('desc-busy');await load({preserveError:!!error}); }
    }
    for (const name of ['descSearch','descState','descGroup']) find(name).addEventListener(name==='descSearch'?'input':'change',render);
    const dateBox=find('descHistoryDate');const today=()=>new Date(Date.now()-3*3600000).toISOString().slice(0,10);dateBox.max=today();dateBox.min=new Date(Date.now()-7*86400000).toISOString().slice(0,10);dateBox.value=today();
    function selectHistory(date) {closePhoto();find('descTechDialog').close();dataEpoch++;historyDate=date;data=null;selected='';error='';updatedAt=null;render();void load();}
    find('descHistoryOpen').addEventListener('click',()=>{if(dateBox.value)selectHistory(dateBox.value);});
    find('descHistoryToday').addEventListener('click',()=>selectHistory(''));
    find('descReload').addEventListener('click',()=>load());
    find('descList').addEventListener('click',event=>{const button=event.target.closest('[data-batch]');if(button){selected=button.dataset.batch;render();}});
    find('descDetail').addEventListener('click',event=>{
      const link=event.target.closest('[data-link-tech]');if(link&&!link.disabled&&canEditBatch()){const batch=data?.batches.find(item=>item.id===selected),form=find('descTechForm');if(!batch)return;for(const name of ['sender','name','imperium_id','toa_login'])form.elements[name].value=name==='sender'?batch.sender||'':batch.technician?.[name]||'';form.elements.freelancer.checked=batch.technician?.freelancer===true;find('descTechError').classList.add('hidden');find('descTechDialog').showModal();return;}
      const action=event.target.closest('[data-action]');if(action&&!action.disabled){void act(action.dataset.action);return;}
      const photo=event.target.closest('[data-photo]');if(photo)openPhoto(photo.dataset.photo);
    });
    find('descDetail').addEventListener('input',event=>{if(event.target.matches('[data-review-note]'))notes.set(selected,event.target.value);});
    find('descTechCancel').addEventListener('click',()=>find('descTechDialog').close());
    find('descTechForm').addEventListener('submit',async event=>{event.preventDefault();if(!canEditBatch())return;const form=event.target,button=form.querySelector('[type="submit"]');button.disabled=true;try{const payload=Object.fromEntries(new FormData(form));payload.freelancer=form.elements.freelancer.checked;await request('/api/disconnection/technician',{method:'POST',body:JSON.stringify(payload)});find('descTechDialog').close();await load();}catch(failure){find('descTechError').textContent=failure.message;find('descTechError').classList.remove('hidden');}finally{button.disabled=false;}});
    find('descPhotoClose').addEventListener('click',closePhoto);
    photoDialog.addEventListener('close',()=>{if(!photoDialog.open)clearPhoto();});
    photoDialog.addEventListener('cancel',()=>{closePhoto();});
    photoImage.addEventListener('load',fitPhoto);
    photoImage.addEventListener('error',()=>{if(photoContext)serialStatus('Não foi possível carregar a foto. Feche e tente novamente.');});
    new ResizeObserver(()=>{if(photoDialog.open)fitPhoto();}).observe(viewport);
    find('descPhotoZoomIn').addEventListener('click',()=>zoomPhoto(photoView.scale+.25));
    find('descPhotoZoomOut').addEventListener('click',()=>zoomPhoto(photoView.scale-.25));
    find('descPhotoReset').addEventListener('click',fitPhoto);
    viewport.addEventListener('wheel',event=>{event.preventDefault();const rect=viewport.getBoundingClientRect();zoomPhoto(photoView.scale+(event.deltaY<0?.25:-.25),{x:event.clientX-rect.left,y:event.clientY-rect.top});},{passive:false});
    viewport.addEventListener('keydown',event=>{if(['+','=','-','0','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();if(event.key==='0')fitPhoto();else if(['+','=','-'].includes(event.key))zoomPhoto(photoView.scale+(event.key==='-'?-.25:.25));else {photoView.x+=event.key==='ArrowLeft'?40:event.key==='ArrowRight'?-40:0;photoView.y+=event.key==='ArrowUp'?40:event.key==='ArrowDown'?-40:0;zoomPhoto(photoView.scale);}}});
    viewport.addEventListener('pointerdown',event=>{if(event.button!==0)return;drag={x:event.clientX,y:event.clientY,view:{...photoView},id:event.pointerId};dragged=false;viewport.setPointerCapture(event.pointerId);});
    viewport.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>5)dragged=true;if(dragged&&photoView.scale>1){photoView={...drag.view,x:drag.view.x+dx,y:drag.view.y+dy};zoomPhoto(photoView.scale);}});
    viewport.addEventListener('pointerup',()=>{drag=null;});viewport.addEventListener('pointercancel',()=>{drag=null;dragged=true;});
    viewport.addEventListener('click',event=>{if(dragged){dragged=false;return;}const rect=viewport.getBoundingClientRect();zoomPhoto(photoView.scale===1?2:1,{x:event.clientX-rect.left,y:event.clientY-rect.top});});
    find('descSerialForm').addEventListener('submit',lookupSerial);
    find('descSerialInput').addEventListener('input',()=>{photoEpoch++;clearSerialResult();serialStatus();updateSerialControls();});
    find('descSerialConfirm').addEventListener('change',updateSerialControls);
    find('descSerialApply').addEventListener('click',()=>void applySerial());
    find('descExport').addEventListener('click',async()=>{
      try {const parts=new Intl.DateTimeFormat('en',{year:'numeric',month:'2-digit',timeZone:'America/Sao_Paulo'}).formatToParts(new Date());const month=parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value;const blob=await requestBlob('/api/disconnection/report.xlsx?month='+month);const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download='DESCONEXAO_'+month+'.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}catch(failure){error=failure.message;render();}
    });
    const schedule=()=>{clearTimeout(timer);if(active)timer=setTimeout(async()=>{if(!document.hidden)await load();schedule();},15000);};
    controller={activate(){active=true;void load();schedule();},deactivate(){active=false;pendingLoad=false;clearTimeout(timer);closePhoto();}};
    document.addEventListener('dominium:module-change',event=>event.detail.module==='disconnection'?controller.activate():controller.deactivate());
    document.addEventListener('dominium:auth-cleared',()=>{authEpoch++;controller.deactivate();data=null;selected='';historyDate='';error='';updatedAt=null;notes.clear();find('descPhotoDialog').close();find('descPhotoLarge').removeAttribute('src');find('descTechDialog').close();find('descTechForm').reset();render();});
    render();return controller;
  }
  const api={mount,visibleBatches,stateLabel,photoUrl,escape,photoTransform};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else global.DominiumDisconnection=api;
})(globalThis);
