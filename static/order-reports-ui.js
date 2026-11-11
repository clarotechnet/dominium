/* Native Imperium OS reports: scope and request are fixed when download begins. */
(function (root) {
  'use strict';
  function mount({ getContext, requestBlob }) {
    const panel = document.getElementById('orderReportsWorkspace');
    if (!panel) return;
    const start = document.getElementById('orderReportStart');
    const end = document.getElementById('orderReportEnd');
    const status = document.getElementById('orderReportStatus');
    const city = document.getElementById('orderReportCity');
    const buttons = [...panel.querySelectorAll('[data-order-report]')];
    const labels = { natal: 'Natal / Parnamirim', fortaleza: 'Fortaleza', mossoro: 'Mossoró', recife: 'Recife' };
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const localDate = d => [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-');
    start.value = end.value = localDate(yesterday);
    start.max = end.max = localDate(new Date());
    let busy = false;
    function render() {
      const context = getContext();
      const blocked = context.allCities || !labels[context.profile] || context.switching;
      city.textContent = context.allCities ? 'Selecione uma cidade no topo' : labels[context.profile] || 'Selecione uma cidade';
      buttons.forEach(button => { button.disabled = busy || blocked; });
      start.disabled = end.disabled = busy;
      panel.setAttribute('aria-busy', String(busy));
    }
    async function download(type, variant = 'raw') {
      if (busy) return;
      const context = { ...getContext() };
      if (context.allCities || context.switching || !labels[context.profile]) return;
      status.classList.remove('order-report-error');
      try {
        if (!start.value || !end.value || start.value > end.value || end.value > end.max) {
          throw new Error('Selecione um período válido até hoje.');
        }
        const days = (Date.parse(end.value) - Date.parse(start.value)) / 86400000;
        if (days >= 31) throw new Error('Selecione até 31 dias por download.');
        busy = true;
        render();
        status.textContent = 'Consultando ' + labels[context.profile] + ' no Imperium e preparando o Excel ' + (variant === 'treated' ? 'tratado' : 'bruto') + '…';
        const query = new URLSearchParams({profile:context.profile, start:start.value, end:end.value, type});
        if (variant === 'treated') query.set('variant', 'treated');
        const result = await requestBlob('/api/order-reports/export.xlsx?' + query, {timeoutMs:180000});
        const url = URL.createObjectURL(result.blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'OS_' + (type === 'all' ? 'Todos' : 'Manutencao') + (variant === 'treated' ? '_Tratado' : '') + '_' + context.profile + '_' + query.get('start') + '_' + query.get('end') + '.xlsx';
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        status.textContent = 'Excel ' + (variant === 'treated' ? 'tratado' : 'bruto') + ' pronto: ' + (type === 'all' ? 'Todos os serviços' : 'Manutenção / Visita Técnica') + ' · ' + labels[context.profile] + ' · ' + query.get('start').split('-').reverse().join('/') + ' a ' + query.get('end').split('-').reverse().join('/') + '.';
      } catch (error) {
        status.textContent = error.message || 'Não foi possível gerar o relatório. Tente novamente.';
        status.classList.add('order-report-error');
      } finally {
        busy = false;
        render();
      }
    }
    buttons.forEach(button => button.addEventListener('click', () => download(button.dataset.orderReport, button.dataset.orderVariant || 'raw')));
    document.addEventListener('dominium:scope-change', render);
    document.addEventListener('dominium:module-change', render);
    document.addEventListener('dominium:auth-cleared', () => { status.textContent = ''; render(); });
    render();
    return { render, download };
  }
  root.DominiumOrderReports = { mount };
})(globalThis);
