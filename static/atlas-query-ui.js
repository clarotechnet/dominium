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
  const statusLabels={
    submission_uncertain:'Envio ao Atlas em verificação; não reenviar automaticamente',
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
  function renderStatus(){
    ui.city.value=state.profile;
    ui.start.disabled=busy||!allowed()||
      Boolean(active && !['ready','failed','format_review'].includes(active.state));
    ui.refresh.disabled=fetching;
    ui.id.textContent=active?.remote_queue_id?'Fila Atlas: '+active.remote_queue_id:
      active?'Solicitação '+active.id.slice(0,8):'Nenhuma fila criada';
    ui.progress.textContent=active?statusLabels[active.state]||'Estado: '+active.state:
      'Selecione a praça e clique em Gerar QUERY no Atlas.';
    ui.status.textContent=active?.error_code==='attachment_http_404'?
      'Anexo ainda retorna 404; o sistema verifica novamente sem gerar outra fila.':
      (active?.error_code==='report_parse_not_confirmed'?
      'O arquivo não foi convertido; nenhuma informação foi descartada.':'');
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
    if(!quiet)ui.status.textContent='Consultando andamento da QUERY...';
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
        if(active.state==='ready'&&(previous!=='ready'||!ui.table.firstChild)){
          offset=0;await loadPage();
        }
      }
      if(!quiet && !active)ui.status.textContent='Nenhuma QUERY gerada nesta praça.';
    }catch(error){
      if(!quiet)ui.status.textContent=safeError(error);
    }finally{fetching=false;renderStatus()}
  }
  async function create(){
    if(busy||fetching||!allowed())return;
    busy=true;renderStatus();
    ui.status.textContent='Solicitando relatório ao Atlas...';
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
      ui.status.textContent=data.reused?'Consulta anterior reutilizada; nenhuma nova fila enviada.':
        'Solicitação registrada. Acompanhe o ID da fila abaixo.';
    }catch(error){ui.status.textContent=safeError(error)}
    finally{busy=false;renderStatus()}
  }
  async function exportAs(ext){
    if(active?.state!=='ready')return;
    try{
      const result=await requestBlob('/api/atlas-query/jobs/'+active.id+'/export.'+ext,
          {timeoutMs:120000});
      saveBlob(result.blob,'dominium-query-'+active.city+'-'+localDate()+'.'+ext);
    }catch(error){ui.status.textContent=safeError(error)}
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
      if(selectedProfile!==state.profile || !active ||
         !['ready','failed','format_review'].includes(active.state))
        void refresh({quiet:true});
    }
  },6500);
  renderStatus();
  if(state.activeModule==='confront')void refresh();
})();
