/* Four-base DataSnap commissions; exports only authorized read-only reports. */
(function (root) {
  'use strict';
  const labels = {
    natal: 'Natal / Parnamirim',
    fortaleza: 'Fortaleza',
    mossoro: 'Mossoró',
    recife: 'Recife / JCR',
  };
  function mount({getContext, requestBlob}) {
    const panel=document.getElementById('commissionReportsWorkspace');
    if(!panel)return;
    const city=panel.querySelector('#commissionReportCity');
    const start=panel.querySelector('#commissionReportStart');
    const end=panel.querySelector('#commissionReportEnd');
    const button=panel.querySelector('#commissionReportDownload');
    const status=panel.querySelector('#commissionReportStatus');
    const localDate=date=>[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),
      String(date.getDate()).padStart(2,'0')].join('-');
    const yesterday=new Date();
    yesterday.setDate(yesterday.getDate()-1);
    end.value=localDate(yesterday);
    start.value=localDate(new Date(yesterday.getFullYear(),yesterday.getMonth(),1));
    start.max=end.max=localDate(new Date());
    let busy=false;
    function render() {
      const context=getContext();
      const blocked=context.allCities || context.switching || !labels[context.profile];
      city.textContent=context.allCities ? 'Escolha uma cidade no topo' :
        labels[context.profile] || 'Selecione uma cidade';
      button.disabled=busy||blocked;
      start.disabled=end.disabled=busy;
      panel.setAttribute('aria-busy',String(busy));
    }
    async function download() {
      if(busy)return;
      const context={...getContext()};
      if(context.allCities||context.switching||!labels[context.profile])return;
      status.classList.remove('order-report-error');
      try {
        if(!start.value||!end.value||start.value>end.value||end.value>end.max)
          throw new Error('Selecione um período válido até hoje.');
        const span=(Date.parse(end.value)-Date.parse(start.value))/86400000;
        if(span>=31)throw new Error('Selecione no máximo 31 dias por consulta.');
        busy=true;render();
        status.textContent='Consultando comissões de '+labels[context.profile]+' pelo DataSnap…';
        const params=new URLSearchParams({profile:context.profile,start:start.value,end:end.value});
        const result=await requestBlob('/api/commission-reports/export.xlsx?'+params,{timeoutMs:180000});
        if(!result.blob||result.blob.size<100)
          throw new Error('O Imperium não retornou um arquivo completo.');
        const url=URL.createObjectURL(result.blob);
        const anchor=document.createElement('a');
        anchor.href=url;
        anchor.download='Comissoes_'+context.profile+'_'+start.value+'_'+end.value+'.xlsx';
        document.body.append(anchor);
        anchor.click();anchor.remove();
        setTimeout(()=>URL.revokeObjectURL(url),60000);
        status.textContent='Excel gerado: Sintético, Analítico e Contratos · '+
          labels[context.profile]+' · '+start.value.split('-').reverse().join('/')+
          ' a '+end.value.split('-').reverse().join('/')+'.';
      }catch(error){
        status.textContent=error.message||'Falha na consulta de comissões.';
        status.classList.add('order-report-error');
      }finally{busy=false;render();}
    }
    button.addEventListener('click',download);
    document.addEventListener('dominium:scope-change',render);
    document.addEventListener('dominium:module-change',render);
    document.addEventListener('dominium:auth-cleared',()=>{
      status.textContent='';render();
    });
    render();
    return {render,download};
  }
  root.DominiumCommissionReports={mount};
})(globalThis);
