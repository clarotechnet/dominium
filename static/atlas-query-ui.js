/* DOMINIUM / Pendente — automated Atlas equipment QUERY (read only). */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const ui={city:$('atlasQueryCity'),location:$('atlasQueryLocation'),
    start:$('atlasQueryStart'),status:$('atlasQueryStatus'),
    id:$('atlasQueryId'),times:$('atlasQueryTimestamps'),
    table:$('atlasQueryGrid'),
    progress:$('atlasQueryProgress'),page:$('atlasQueryPage'),
    prev:$('atlasQueryPrev'),next:$('atlasQueryNext'),
    csv:$('atlasQueryCsv'),xlsx:$('atlasQueryXlsx'),
    refresh:$('atlasQueryRefresh'),reconcile:$('atlasQueryReconcile'),
    summary:$('atlasQuerySummary')};
  if(Object.values(ui).some(value=>!value))return;
  let active=null;let fetching=false;let busy=false;let offset=0;let total=0;
  let selectedProfile='';
  let lastBackendError='';
  let relatedJobs=[];
  let checkedAt=null;
  let refreshPending=false;
  // Reuse DOMINIUM's existing animated orb HUD during the entire QUERY job.
  // A registered HTTP 202 only means queued, not that the Excel is ready.
  let hudToken='';
  let hudMarker='';
  let hudCounter=0;
  function queryHud(phase,label,detail='',marker=''){
    const key=String(marker||'')+'|'+phase+'|'+label+'|'+detail;
    if(key===hudMarker)return;
    hudMarker=key;
    const motion=window.DOMINIUM_MOTION;
    if(!motion||typeof motion.operation!=='function')return;
    if(!hudToken)hudToken='atlas-query-'+Date.now()+'-'+(++hudCounter);
    motion.operation({token:hudToken,phase,label,detail});
    if(phase==='error'||phase==='success')hudToken='';
  }
  function updateQueryHud(){
    if(!active)return;
    const id=active.id||'unknown';
    if(active.error_code==='manually_closed_unconfirmed'){
      queryHud('error','Solicitação antiga encerrada',
        'A conferência manual foi registrada. Uma nova QUERY exige outro clique.',
        id+'|manual-reconciled');
    } else if(active.error_code==='atlas_submit_unconfirmed'){
      queryHud('error','Envio Atlas não confirmado',
        'Não tente novamente sem verificar a fila existente.',id+'|uncertain-error');
    } else if(active.state==='atlas_auth_required'||active.error_code==='atlas_auth_required'){
      queryHud('error','Sessão Atlas expirada',
        active.remote_queue_id
          ? 'A fila '+active.remote_queue_id+' foi preservada. Renove o login do Atlas.'
          : 'Renove o login na sessão Atlas.',id+'|auth');
    } else if(active.error_code==='attachment_transport_timeout'){
      queryHud('solving','Servidor de arquivos demorando',
        'A fila '+(active.remote_queue_id||'Atlas')+
        ' foi preservada. Nova tentativa programada; não gere outra QUERY.',
        id+'|attachment-transport-timeout');
    } else if(['failed','format_review'].includes(active.state)){
      queryHud('error','QUERY precisa de atenção',
        statusLabels[active.state]||'Consulte o histórico para detalhes.',id+'|'+active.state);
    } else if(active.state==='ready'){
      queryHud('success','QUERY pronta',
        'Tabela e exportações CSV/XLSX estão disponíveis.',id+'|ready');
    } else if(['attachment_wait','attachment_missing'].includes(active.state)){
      queryHud('solving','Aguardando arquivo do Atlas',
        'Fila concluída: verificando anexo e possíveis atrasos de publicação.',id+'|'+active.state);
    } else if(active.state==='download_ready'){
      queryHud('solving','Preparando planilha',
        'Arquivo recebido: validando e organizando as colunas.',id+'|download');
    } else if(active.state==='queued'||active.state==='processing'){
      queryHud('working','Consultando fila da QUERY',
        active.remote_queue_id?'Fila Atlas '+active.remote_queue_id+' — '+statusLabels[active.state]:
          'Aguardando ID e processamento da fila.',id+'|'+active.state);
    } else if(active.state==='submission_uncertain'){
      queryHud('searching','Aguardando resposta do Atlas',
        'Pedido registrado. O sistema não enviará uma segunda solicitação.',id+'|uncertain');
    }
  }
  const activity=document.getElementById('atlasQueryActivity');
  function writeNotice(message,kind='info'){
    const stamp=new Date().toLocaleTimeString('pt-BR');
    const profile=String(state.profile||'').toUpperCase();
    const summary=stamp+(profile?' ['+profile+']':'')+' — '+String(message||'');
    ui.status.textContent=summary;
    ui.status.dataset.level=kind;
    if(activity){
      const item=document.createElement('li');
      item.textContent=summary;
      item.className='atlas-query-activity-'+kind;
      activity.prepend(item);
      while(activity.children.length>12)activity.lastElementChild.remove();
    }
  }

  const statusLabels={
    submission_uncertain:'Solicitação registrada; confirmação do Atlas pendente (não reenviar)',
    atlas_auth_required:'Autenticação do Atlas necessária; nenhuma fila confirmada',
    queued:'ID recebido; aguardando processamento',
    processing:'Relatório sendo processado no Atlas',
    attachment_missing:'Fila concluída; anexo ainda não publicado',
    attachment_wait:'Fila concluída; aguardando a disponibilidade do anexo (404 pode ser temporário)',
    download_ready:'Arquivo obtido; preparando as colunas',
    format_review:'Arquivo obtido; formato precisa de revisão',
    ready:'QUERY disponível para consulta',
    failed:'Atlas informou falha no relatório'
  };
  const allowed=()=>['admin','controller'].includes(String(state.authUser?.role||''));
  const formatCount=n=>Number(n||0).toLocaleString('pt-BR');
  const formatMoment=value=>{
    const millis=typeof value==='number' ? value*1000 : value;
    const date=new Date(millis);
    return Number.isFinite(date.getTime())
      ? date.toLocaleString('pt-BR',{timeZone:'America/Fortaleza',
          day:'2-digit',month:'2-digit',year:'numeric',
          hour:'2-digit',minute:'2-digit',second:'2-digit'})
      : '—';
  };
  function selectLatestGroup(jobs){
    const root=jobs.find(job=>!job.fallback_of)||jobs[0]||null;
    if(!root){relatedJobs=[];return null;}
    const reserve=jobs.find(job=>job.fallback_of===root.id)||null;
    relatedJobs=reserve?[root,reserve]:[root];
    // The oldest confirmed report within the newest generation pair wins.
    // Never display a reserve 'queued' in place of a READY principal.
    return root.state==='ready'?root:
      reserve?.state==='ready'?reserve:
      reserve||root;
  }
  const safeError=(error)=>String(error?.message||'Falha ao acessar a QUERY');
  const jobStatus=job=>job?.error_code==='manually_closed_unconfirmed'
    ? 'Tentativa antiga encerrada após conferência manual; nova QUERY liberada.'
    : statusLabels[job?.state]||job?.state||'';
  // An unconfirmed Atlas submission is not a confirmed failure or a retryable job.
  // Stop background polling and keep manual reconciliation available.
  const pollingComplete=job=>Boolean(job && (
    ['ready','failed','format_review','atlas_auth_required'].includes(job.state)||
    job.error_code==='atlas_submit_unconfirmed'||job.error_code==='atlas_auth_required'));
  function retryFamilyId(){
    const primary=relatedJobs.find(job=>!job.fallback_of);
    if(!primary || relatedJobs.length!==2)return '';
    return relatedJobs.every(job=>job.state==='attachment_wait' &&
      /^\d{5,15}$/.test(String(job.remote_queue_id||'')) &&
      job.error_code==='attachment_http_404' && job.attachment_failures>=2 &&
      typeof job.created_at==='number' && Number.isFinite(job.created_at) &&
      Date.now()-job.created_at*1000>=120000) ? primary.id : '';
  }
  function canCreateQuery(){
    if(!active || ['ready','failed','format_review'].includes(active.state))return true;
    if(retryFamilyId())return true;
    // Match the backend's eight-hour reuse window. Recovery is an explicit
    // operator action and requires every existing attempt to have a confirmed ID.
    return relatedJobs.length>0 && relatedJobs.every(job=>
      ['attachment_wait','attachment_missing'].includes(job.state) &&
      ['attachment_http_404','attachment_not_listed','atlas_auth_required'].includes(job.error_code) &&
      /^\d{5,15}$/.test(String(job.remote_queue_id||'')) &&
      typeof job.created_at==='number' && Number.isFinite(job.created_at) &&
      Date.now()-job.created_at*1000>=8*3600*1000);
  }
  function renderStatus(){
    ui.city.value=state.profile;
    ui.start.disabled=busy||!allowed()||!canCreateQuery();
    ui.start.textContent=retryFamilyId()?'Gerar nova QUERY após falha dos anexos':'Gerar QUERY no Atlas';
    ui.refresh.disabled=fetching;
    ui.reconcile.hidden=!(active?.state==='submission_uncertain'&&
      active?.error_code==='atlas_submit_unconfirmed');
    ui.reconcile.style.display=ui.reconcile.hidden?'none':'inline-flex';
    ui.reconcile.disabled=busy||fetching||!allowed()||ui.reconcile.hidden;
    const primary=relatedJobs.find(job=>!job.fallback_of);
    const reserve=relatedJobs.find(job=>job.fallback_of);
    ui.id.textContent=primary&&reserve
      ? 'Principal: '+(primary.remote_queue_id||'aguardando ID')+
        ' • Reserva: '+(reserve.remote_queue_id||'aguardando ID')
      : active?.remote_queue_id?'Fila Atlas: '+active.remote_queue_id:
        active?'Solicitação '+active.id.slice(0,8):'Nenhuma fila criada';
    ui.times.textContent=active
      ? 'Principal solicitada: '+formatMoment(primary?.created_at||active.created_at)+
        (reserve?' • Reserva solicitada: '+formatMoment(reserve.created_at):'')+
        ' • Última atualização: '+formatMoment(active.updated_at)+
        (checkedAt?' • Consultada: '+formatMoment(checkedAt):'')
      : 'Sem consulta registrada para esta praça.';
    ui.progress.textContent=active?.error_code==='attachment_transport_timeout'
      ? 'A consulta do anexo expirou. A fila foi preservada; nova tentativa automática programada.'
      : active?.error_code==='atlas_submit_unconfirmed'
      ? 'Confirmação do Atlas não obtida. Verifique a fila antes de qualquer novo envio.'
      : active?.error_code==='atlas_auth_required'
      ? 'Sessão Atlas expirada. Fila preservada; renove o login para continuar a consulta.'
      : active?jobStatus(active):
      'Selecione a praça e clique em Gerar QUERY no Atlas.';
    // NEVER clear status/last action during automatic polling.
    const serverError=String(active?.error_code||'');
    if(serverError && serverError!==lastBackendError){
      const message=serverError==='attachment_transport_timeout'
        ? 'O servidor do anexo demorou a responder. O ID existente foi preservado; nova tentativa programada, sem segunda geração.'
        : serverError==='attachment_http_404'
        ? 'O anexo respondeu 404. Verificando o ID principal e a reserva autorizada, quando aplicável.'
        : serverError==='atlas_auth_required'
        ? (active?.remote_queue_id
            ? 'Sessão de consulta Atlas expirada. A fila existente foi preservada; faça login para retomar.'
            : 'A sessão Atlas requer autenticação. Nenhuma geração de relatório foi confirmada.')
        : serverError==='atlas_submit_unconfirmed'
        ? 'O Atlas não confirmou a geração. Não repita o clique sem verificar a fila.'
        : serverError==='report_parse_not_confirmed'
        ? 'Arquivo obtido, mas o formato precisa de revisão. Nenhuma linha foi descartada.'
        : serverError==='manually_closed_unconfirmed'
        ? 'Solicitação anterior encerrada após conferência manual. Nova QUERY requer outro clique.'
        : 'O serviço registrou uma pendência ('+serverError+').';
      writeNotice(message,'warning');
    }
    lastBackendError=serverError;
    const ready=active?.state==='ready';
    ui.csv.disabled=!ready;ui.xlsx.disabled=!ready;
    ui.prev.disabled=!ready||offset<=0;
    ui.next.disabled=!ready||offset+100>=total;
    ui.page.textContent=ready?'Linhas '+formatCount(total?offset+1:0)+'–'+
      formatCount(Math.min(offset+100,total))+' de '+formatCount(total):'';
    if(!allowed()){
      ui.start.disabled=true;
      ui.progress.textContent=state.authReady===false
        ? 'Validando sessão e permissões do operador...'
        : 'Este recurso exige perfil administrador ou controlador.';
    }
  }
  function syncProfile(){
    if(selectedProfile===state.profile)return false;
    selectedProfile=state.profile;
    active=null;relatedJobs=[];checkedAt=null;lastBackendError='';
    offset=0;total=0;
    ui.table.replaceChildren();ui.summary.textContent='';
    renderStatus();
    return true;
  }
  function cell(value,tag='td'){
    const element=document.createElement(tag);
    element.textContent=String(value??'');
    return element;
  }
  async function loadPage(){
    if(!active||active.state!=='ready')return;
    const expectedJob=active.id,expectedProfile=state.profile;
    const data=await request('/api/atlas-query/jobs/'+expectedJob+'/rows/'+offset,
      {timeoutMs:25000});
    if(active?.id!==expectedJob||state.profile!==expectedProfile)return;
    total=Number(data.total||0);
    const table=document.createElement('table');
    table.className='confront-preview-table';
    const head=document.createElement('thead'),titles=document.createElement('tr');
    for(const col of data.columns||[])titles.append(cell(col.title,'th'));
    head.append(titles);table.append(head);
    const body=document.createElement('tbody');
    for(const row of data.rows||[]){
      const tr=document.createElement('tr');
      for(const col of data.columns||[])tr.append(cell(row[col.id]||''));
      body.append(tr);
    }
    table.append(body);
    ui.table.replaceChildren(table);
    ui.summary.textContent=formatCount(total)+' equipamentos no relatório Atlas';
    renderStatus();
  }
  async function refresh({quiet=false}={}){
    if(!allowed()||state.activeModule!=='confront')return;
    if(fetching){
      if(selectedProfile!==state.profile)refreshPending=true;
      return;
    }
    syncProfile();
    const targetProfile=state.profile;
    fetching=true;
    if(!quiet){
      writeNotice('Consultando andamento da QUERY...');
      queryHud('searching','Consultando fila Atlas',
        'Verificando o ID e a situação do processamento.','refresh-'+Date.now());
    }
    try{
      // Re-read the listing every cycle: a reserve ID is created by the
      // server after a confirmed 404, not by another browser POST.
      const data=await request('/api/atlas-query/jobs',{timeoutMs:18000});
      if(targetProfile!==state.profile){refreshPending=true;return;}
      const jobs=(data.jobs||[]).filter(job=>job.city===targetProfile);
      const previouslyActive=active;
      if(jobs.length)active=selectLatestGroup(jobs);
      else{active=null;relatedJobs=[];}
      if(active){
        if(previouslyActive?.id!==active.id){
          offset=0;total=0;ui.table.replaceChildren();ui.summary.textContent='';
        }
        const requestedId=active.id;
        const item=await request('/api/atlas-query/jobs/'+requestedId,{timeoutMs:18000});
        if(targetProfile!==state.profile){refreshPending=true;return;}
        const previous=previouslyActive?.id===requestedId?previouslyActive?.state:null;
        active=item.job||active;
        const related=relatedJobs.findIndex(job=>job.id===active.id);
        if(related>=0)relatedJobs[related]=active;
        checkedAt=new Date();
        updateQueryHud();
        if(active.state==='ready'&&(previous!=='ready'||!ui.table.firstChild)){
          offset=0;await loadPage();
        }
      }
      if(!quiet)writeNotice(active ? ('Consulta atualizada: '+jobStatus(active)+'.') : 'Nenhuma QUERY registrada nesta praça.');
      if(!active&&!quiet)queryHud('success','Consulta finalizada',
        'Não existe QUERY registrada nesta praça.','no-jobs-'+Date.now());
    }catch(error){
      if(targetProfile!==state.profile){refreshPending=true;return;}
      if(!quiet){
        writeNotice('Não foi possível consultar a fila: '+safeError(error),'error');
        queryHud('error','Consulta da fila falhou',safeError(error),'refresh-error-'+Date.now());
      }
    }finally{
      fetching=false;
      if(refreshPending){
        refreshPending=false;
        void refresh({quiet:true});
      }else renderStatus();
    }
  }
  async function create(){
    if(busy||fetching||!allowed()||!canCreateQuery())return;
    const retryId=retryFamilyId();
    busy=true;renderStatus();
    writeNotice('Pedido recebido no navegador. Enviando ao servidor...');
    queryHud('searching','Gerando QUERY no Atlas',
      'Enviando a praça e a localização ao servidor.','post-'+Date.now());
    try{
      const data=await request('/api/atlas-query/jobs',{
        method:'POST',
        headers:{'content-type':'application/json'},
        body:JSON.stringify({city:state.profile,location:ui.location.value,
          ...(retryId?{retry_job_id:retryId}:{})}),
        timeoutMs:25000
      });
      active=data.job;relatedJobs=active?[active]:[];
      checkedAt=null;offset=0;total=0;
      ui.table.replaceChildren();ui.summary.textContent='';
      selectedProfile=state.profile;
      writeNotice(data.reused
        ? 'Reutilizando a solicitação '+active.id.slice(0,8)+'. Nenhuma fila nova foi enviada.'
        : 'O servidor registrou a solicitação '+active.id.slice(0,8)+'. Aguardando confirmação do ID Atlas.',
        data.reused?'warning':'success');
      updateQueryHud();
    }catch(error){
      writeNotice('Falha ao solicitar QUERY: '+safeError(error),'error');
      queryHud('error','Falha ao gerar QUERY',safeError(error),'post-error-'+Date.now());
    }
    finally{busy=false;renderStatus()}
  }
  async function reconcileOld(){
    if(!active||busy||fetching||!allowed()||
       active.state!=='submission_uncertain'||
       active.error_code!=='atlas_submit_unconfirmed')return;
    const checked=window.confirm(
      'Você verificou no Atlas que a solicitação antiga NÃO criou nenhuma fila? '+
      'Confirme apenas após consultar o histórico do Atlas. '+
      'O registro será preservado e uma nova QUERY só será enviada se você clicar em Gerar QUERY.');
    if(!checked)return;
    busy=true;renderStatus();
    try{
      const result=await request('/api/atlas-query/jobs',{
        method:'POST',headers:{'content-type':'application/json'},
        body:JSON.stringify({reconcile_job_id:active.id,atlas_checked_no_queue:true}),
        timeoutMs:20000
      });
      active=result.job||active;
      const i=relatedJobs.findIndex(job=>job.id===active.id);
      if(i>=0)relatedJobs[i]=active;
      writeNotice('Tentativa antiga encerrada após conferência. Nova geração disponível, sem envio automático.','success');
      updateQueryHud();
    }catch(error){
      writeNotice('Não foi possível reconciliar a tentativa: '+safeError(error),'error');
    }finally{busy=false;renderStatus()}
  }
  async function exportAs(ext){
    if(active?.state!=='ready')return;
    try{
      const result=await requestBlob('/api/atlas-query/jobs/'+active.id+'/export.'+ext,
          {timeoutMs:120000});
      saveBlob(result.blob,'dominium-query-'+active.city+'-'+localDate()+'.'+ext);
    }catch(error){
      writeNotice('Falha ao exportar planilha: '+safeError(error),'error');
      queryHud('error','Falha ao exportar planilha',safeError(error),'export-error-'+Date.now());
    }
  }
  ui.start.addEventListener('click',()=>void create());
  ui.refresh.addEventListener('click',()=>void refresh());
  ui.reconcile.addEventListener('click',()=>void reconcileOld());
  ui.csv.addEventListener('click',()=>void exportAs('csv'));
  ui.xlsx.addEventListener('click',()=>void exportAs('xlsx'));
  ui.prev.addEventListener('click',()=>{offset=Math.max(0,offset-100);void loadPage()});
  ui.next.addEventListener('click',()=>{offset+=100;void loadPage()});
  ui.city.addEventListener('change',async()=>{
    if(ui.city.value!==state.profile)await switchProfile(ui.city.value);
    syncProfile();
    await refresh();
  });
  document.addEventListener('dominium:module-change',({detail})=>{
    if(detail?.module==='confront'){
      syncProfile();
      void refresh();
    }
  });
  setInterval(()=>{
    if(state.activeModule==='confront'){
      if(selectedProfile!==state.profile || !active || !pollingComplete(active))
        void refresh({quiet:true});
    }
  },6500);
  renderStatus();
  if(state.activeModule==='confront')void refresh();
})();
