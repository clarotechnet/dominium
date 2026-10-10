(function (global) {
  'use strict';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const stateLabel = state => ({buffering:'Recebendo evidências',processing:'Consultando',review:'Pronta para revisão',blocked:'Precisa de conferência',simulated:'Simulada',rejected:'Recusada',executed:'Baixa confirmada'}[state] || 'Aguardando');
  const photoUrl = name => /^[a-f0-9-]{36}\.jpg$/.test(String(name || '')) ? '/api/disconnection/photo/' + name : '';
  function visibleBatches(rows, {search = '', state = 'all', group = ''} = {}) {
    const term = norm(search);
    return (rows || []).filter(batch => (state === 'all' || batch.state === state) && (!group || batch.group === group) && (!term || norm([batch.contract,batch.technician?.name,batch.city,batch.plan?.operations?.map(item=>item.os).join(' ')].join(' ')).includes(term)));
  }
  let controller;
  function mount({request, requestBlob, getUser}) {
    const root = document.getElementById('disconnectionWorkspace');
    if (!root || controller) return controller;
    let data = null, selected = '', active = false, busy = false, timer = null, error = '', authEpoch = 0, updatedAt = null;
    const find = id => root.querySelector('#' + id);
    const notes = new Map();
    const filters = () => ({search:find('descSearch').value,state:find('descState').value,group:find('descGroup').value});
    function render() {
      const rows = data?.batches || [];
      find('descMode').textContent = data?.mode === 'test' ? 'Revisão · baixas em teste' : data?.mode === 'production' ? 'Operação ativa' : 'Conectando ao Bot';
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
      const detail = find('descDetail');
      if (!batch) { detail.innerHTML = '<div class="desc-empty"><i data-lucide="scan-line"></i><h3>Conferência do contrato</h3><p>Selecione um lote para ver a mensagem, as fotos e o resultado do Atlas.</p></div>'; global.lucide?.createIcons(); return; }
      const plan = batch.plan, canWrite = ['admin','controller'].includes(getUser()?.role), blockers = plan?.blockers || batch.capture_errors || [];
      const date = new Date(batch.created_at).toLocaleString('pt-BR');
      const evidence = plan?.atlas || [];
      detail.innerHTML = `<header class="desc-detail-heading"><div><p class="section-label">${escape(batch.city || 'DESCONEXÃO')}</p><h3>Contrato ${escape(batch.contract || 'não identificado')}</h3><p>${escape(batch.technician?.name || 'Técnico a vincular')} <span>· ${escape(date)}</span></p></div><span class="desc-state ${escape(batch.state)}">${escape(stateLabel(batch.state))}</span></header>
        ${batch.demo?'<p class="desc-alert">Demonstração: este lote não corresponde a uma OS real.</p>':''}
        ${batch.state==='buffering'?`<p class="desc-alert soft">Recebendo evidências deste técnico e contrato até ${new Date(batch.deadline).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}.</p>`:''}
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
      if (busy || !getUser()) return;
      const epoch = authEpoch;
      busy = true;
      find('descReload').disabled = true;
      try {
        const response = await request('/api/disconnection/state', {timeoutMs:25000});
        if(epoch !== authEpoch) return;
        data = response; updatedAt = new Date(); if(!preserveError) error='';
        const select = find('descGroup'), prior = select.value;
        select.innerHTML = '<option value="">Todos os grupos</option>'+Object.entries(data.groups||{}).map(([id,group])=>`<option value="${escape(id)}">${escape(group.label || group.name || group.city || id)}</option>`).join(''); select.value=prior;
      } catch (failure) { if(epoch === authEpoch) error=failure.message; }
      finally { busy=false;find('descReload').disabled=false;render(); }
    }
    async function act(action) {
      const batch = data?.batches.find(item=>item.id===selected);
      if (!batch || busy) return;
      busy=true; root.classList.add('desc-busy');
      try {
        await request('/api/disconnection/'+(action==='refresh'?'refresh':'decision'), {method:'POST',body:JSON.stringify({id:batch.id,revision:batch.revision,action,note:notes.get(batch.id)||''}),timeoutMs:120000});error='';
      } catch (failure) { error=failure.message; }
      finally { busy=false;root.classList.remove('desc-busy');await load({preserveError:!!error}); }
    }
    for (const name of ['descSearch','descState','descGroup']) find(name).addEventListener(name==='descSearch'?'input':'change',render);
    find('descReload').addEventListener('click',()=>load());
    find('descList').addEventListener('click',event=>{const button=event.target.closest('[data-batch]');if(button){selected=button.dataset.batch;render();}});
    find('descDetail').addEventListener('click',event=>{
      const link=event.target.closest('[data-link-tech]');if(link&&!link.disabled){const batch=data?.batches.find(item=>item.id===selected),form=find('descTechForm');if(!batch)return;for(const name of ['sender','name','imperium_id','toa_login'])form.elements[name].value=name==='sender'?batch.sender||'':batch.technician?.[name]||'';form.elements.freelancer.checked=batch.technician?.freelancer===true;find('descTechError').classList.add('hidden');find('descTechDialog').showModal();return;}
      const action=event.target.closest('[data-action]');if(action&&!action.disabled){void act(action.dataset.action);return;}
      const photo=event.target.closest('[data-photo]');if(photo){find('descPhotoLarge').src=photoUrl(photo.dataset.photo);find('descPhotoDialog').showModal();}
    });
    find('descDetail').addEventListener('input',event=>{if(event.target.matches('[data-review-note]'))notes.set(selected,event.target.value);});
    find('descTechCancel').addEventListener('click',()=>find('descTechDialog').close());
    find('descTechForm').addEventListener('submit',async event=>{event.preventDefault();const form=event.target,button=form.querySelector('[type="submit"]');button.disabled=true;try{const payload=Object.fromEntries(new FormData(form));payload.freelancer=form.elements.freelancer.checked;await request('/api/disconnection/technician',{method:'POST',body:JSON.stringify(payload)});find('descTechDialog').close();await load();}catch(failure){find('descTechError').textContent=failure.message;find('descTechError').classList.remove('hidden');}finally{button.disabled=false;}});
    find('descPhotoClose').addEventListener('click',()=>find('descPhotoDialog').close());
    find('descExport').addEventListener('click',async()=>{
      try {const parts=new Intl.DateTimeFormat('en',{year:'numeric',month:'2-digit',timeZone:'America/Sao_Paulo'}).formatToParts(new Date());const month=parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value;const blob=await requestBlob('/api/disconnection/report.xlsx?month='+month);const href=URL.createObjectURL(blob);const link=document.createElement('a');link.href=href;link.download='DESCONEXAO_'+month+'.xlsx';link.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}catch(failure){error=failure.message;render();}
    });
    const schedule=()=>{clearTimeout(timer);if(active)timer=setTimeout(async()=>{if(!document.hidden)await load();schedule();},15000);};
    controller={activate(){active=true;void load();schedule();},deactivate(){active=false;clearTimeout(timer);}};
    document.addEventListener('dominium:module-change',event=>event.detail.module==='disconnection'?controller.activate():controller.deactivate());
    document.addEventListener('dominium:auth-cleared',()=>{authEpoch++;controller.deactivate();data=null;selected='';error='';updatedAt=null;notes.clear();find('descPhotoDialog').close();find('descPhotoLarge').removeAttribute('src');find('descTechDialog').close();find('descTechForm').reset();render();});
    render();return controller;
  }
  const api={mount,visibleBatches,stateLabel,photoUrl,escape};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else global.DominiumDisconnection=api;
})(globalThis);
