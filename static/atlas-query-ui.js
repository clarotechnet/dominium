/* DOMINIUM / Pendente — automated Atlas equipment QUERY (read only). */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const ui={city:$('atlasQueryCity'),location:$('atlasQueryLocation'),
    start:$('atlasQueryStart'),status:$('atlasQueryStatus'),
    id:$('atlasQueryId'),table:$('atlasQueryGrid'),
    progress:$('atlasQueryProgress'),page:$('atlasQueryPage'),
    prev:$('atlasQueryPrev'),next:$('atlasQueryNext'),
    csv:$('atlasQueryCsv'),xlsx:$('atlasQueryXlsx'),
    refresh:$('atlasQueryRefresh'),summary:$('atlasQuerySummary')};
  if(Object.values(ui).some(value=>!value))return;
  let active=null;let fetching=false;let busy=false;let offset=0;let total=0;
  let selectedProfile='';
  let lastBackendError='';
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
    if(active.error_code==='atlas_submit_unconfirmed'){
      queryHud('error','Envio Atlas não confirmado',
        'Não tente novamente sem verificar a fila existente.',id+'|uncertain-error');
    } else if(active.state==='atlas_auth_required'){
      queryHud('error','Atlas precisa de login',
        'Faça login na sessão do watchdog; nenhuma fila foi confirmada.',id+'|auth');
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
    const summary=stamp+' — '+String(message||'');
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
  const safeError=(error)=>String(error?.message||'Falha ao acessar a QUERY');
  // An unconfirmed Atlas submission is not a confirmed failure or a retryable job.
  // Stop background polling and keep manual reconciliation available.
  const pollingComplete=job=>Boolean(job && (
    ['ready','failed','format_review','atlas_auth_required'].includes(job.state)||
    job.error_code==='atlas_submit_unconfirmed'));
  function renderStatus(){
    ui.city.value=state.profile;
    ui.start.disabled=busy||!allowed()||
      Boolean(active && !['ready','failed','format_review'].includes(active.state));
    ui.refresh.disabled=fetching;
    ui.id.textContent=active?.remote_queue_id?'Fila Atlas: '+active.remote_queue_id:
      active?'Solicitação '+active.id.slice(0,8):'Nenhuma fila criada';
    ui.progress.textContent=active?.error_code==='atlas_submit_unconfirmed'
      ? 'Confirmação do Atlas não obtida. Verifique a fila antes de qualquer novo envio.'
      : active?statusLabels[active.state]||'Estado: '+active.state:
      'Selecione a praça e clique em Gerar QUERY no Atlas.';
    // NEVER clear status/last action during automatic polling.
    const serverError=String(active?.error_code||'');
    if(serverError && serverError!==lastBackendError){
      const message=serverError==='attachment_http_404'
        ? 'O anexo respondeu 404. Vamos consultar o MESMO ID; nenhuma fila nova foi criada.'
        : serverError==='atlas_auth_required'
        ? 'A sessão Atlas requer autenticação. Nenhuma geração de relatório foi confirmada.'
        : serverError==='atlas_submit_unconfirmed'
        ? 'O Atlas não confirmou a geração. Não repita o clique sem verificar a fila.'
        : serverError==='report_parse_not_confirmed'
        ? 'Arquivo obtido, mas o formato precisa de revisão. Nenhuma linha foi descartada.'
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
      ui.progress.textContent='Este recurso exige perfil administrador ou controlador.';
    }
  }
  function cell(value,tag='td'){
    const element=document.createElement(tag);
    element.textContent=String(value??'');
    return element;
  }
  async function loadPage(){
    if(!active||active.state!=='ready')return;
    const data=await request('/api/atlas-query/jobs/'+active.id+'/rows/'+offset,
      {timeoutMs:25000});
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
    if(fetching||!allowed()||state.activeModule!=='confront')return;
    fetching=true;
    if(!quiet){
      writeNotice('Consultando andamento da QUERY...');
      queryHud('searching','Consultando fila Atlas',
        'Verificando o ID e a situação do processamento.','refresh-'+Date.now());
    }
    try{
      if(!active||selectedProfile!==state.profile){
        selectedProfile=state.profile;active=null;offset=0;total=0;
        ui.table.replaceChildren();
        const data=await request('/api/atlas-query/jobs',{timeoutMs:18000});
        const jobs=(data.jobs||[]).filter(j=>j.city===state.profile);
        active=jobs[0]||null;
      }
      if(active){
        const item=await request('/api/atlas-query/jobs/'+active.id,{timeoutMs:18000});
        const previous=active.state;active=item.job||active;
        updateQueryHud();
        if(active.state==='ready'&&(previous!=='ready'||!ui.table.firstChild)){
          offset=0;await loadPage();
        }
      }
      if(!quiet)writeNotice(active ? ('Consulta atualizada: '+(statusLabels[active.state]||active.state)+'.') : 'Nenhuma QUERY registrada nesta praça.');
      if(!active&&!quiet)queryHud('success','Consulta finalizada',
        'Não existe QUERY registrada nesta praça.','no-jobs-'+Date.now());
    }catch(error){
      if(!quiet){
        writeNotice('Não foi possível consultar a fila: '+safeError(error),'error');
        queryHud('error','Consulta da fila falhou',safeError(error),'refresh-error-'+Date.now());
      }
    }finally{fetching=false;renderStatus()}
  }
  async function create(){
    if(busy||fetching||!allowed())return;
    busy=true;renderStatus();
    writeNotice('Pedido recebido no navegador. Enviando ao servidor...');
    queryHud('searching','Gerando QUERY no Atlas',
      'Enviando a praça e a localização ao servidor.','post-'+Date.now());
    try{
      const data=await request('/api/atlas-query/jobs',{
        method:'POST',
        headers:{'content-type':'application/json'},
        body:JSON.stringify({city:state.profile,location:ui.location.value}),
        timeoutMs:25000
      });
      active=data.job;offset=0;total=0;
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
  ui.csv.addEventListener('click',()=>void exportAs('csv'));
  ui.xlsx.addEventListener('click',()=>void exportAs('xlsx'));
  ui.prev.addEventListener('click',()=>{offset=Math.max(0,offset-100);void loadPage()});
  ui.next.addEventListener('click',()=>{offset+=100;void loadPage()});
  ui.city.addEventListener('change',async()=>{
    if(ui.city.value!==state.profile)await switchProfile(ui.city.value);
    await refresh();
  });
  document.addEventListener('dominium:module-change',({detail})=>{
    if(detail?.module==='confront')void refresh();
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
