"""Integracao controlada do gerador original de Fora de Rota ao frontend Dominium.

Mantem os fluxos ja publicados; a base de clientes nao e enviada a outro dominio.
Reexecutar apenas a partir do checkout de homologacao, nunca em producao.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
original = Path(r"C:\Users\Usuario\Documents\analise-backlog-rescue\public\fora-rota.js")
static = root / "static"
source = original.read_text(encoding="utf-8")
assert "function buildClean106Contracts" in source
assert "function parseSafraClaroBacklog" in source

def replace_between(start, end, replacement):
    global source
    a = source.index(start)
    b = source.index(end, a + len(start))
    source = source[:a] + replacement.rstrip() + "\n\n" + source[b:]

source = source.replace("'fora-rota-sent-contracts-v1'", "'dominium-fora-rota-sent-v1'")
source = source.replace("'fora-rota-clean-106-contracts-v1'", "'dominium-fora-rota-106-v1'")
source = source.replace("'fora-rota-clean-106-meta-v1'", "'dominium-fora-rota-meta-v1'")
source = source.replace(
    "  const FIREBASE_COLLECTION = 'imperiumDashboard';",
    "  const CLARO_SESSION_KEY = 'dominium-fora-rota-claro-session-v1';\n  const FIREBASE_COLLECTION = 'imperiumDashboard';"
)
replace_between(
    "  async function markSelectedAsSent() {",
    "  function clearSelection() {",
    '''  // Envio aqui significa SOMENTE registrar no historico do Dominium.
  // Nao dispara WhatsApp, baixa de OS nem operacao no Imperium.
  async function markSelectedAsSent() {
    if (!state.selectedRecords.length) {
      setStatus('Gere as mensagens antes de registrar os envios.', 'error');
      return;
    }
    const button = els.marcar;
    if (button.disabled) return;
    button.disabled = true;
    const cityKey = getSelectedCityKey();
    const profile = cityKey === 'natal_parnamirim' ? 'natal'
      : cityKey === 'pernambuco' ? 'recife' : cityKey;
    const technician = stringValue(els.tecnico.value) || 'A DEFINIR';
    const sentDate = stringValue(els.data.value) || new Date().toLocaleDateString('en-CA');
    const agenda = stringValue(els.agenda.value) || '08:00 - 22:00';
    let registered = 0;
    try {
      // Fonte autoritativa para deduplicacao, inclusive entre navegadores.
      state.sentContracts = await loadDominiumSentContracts();
      for (const record of state.selectedRecords) {
        if (recordWasSent(record)) continue;
        const note = ['Fora Rota', 'Tecnico: ' + technician,
          'Agenda: ' + agenda, 'Data: ' + sentDate].join(' | ').slice(0, 300);
        const reply = await dominiumCall('/api/backlog/year/sent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({profile, contract: record.contract, note})
        });
        if (!reply || reply.ok !== true) {
          throw Error('API nao confirmou registro de ' + record.contract);
        }
        const sentAt = new Date().toISOString();
        state.sentContracts[profile + ':' + record.contract] = {
          contract: record.contract, city: cityKey,
          cityLabel: CITY_LABELS[cityKey] || cityKey,
          name: record.name, technician, sentDate, sentAt, agenda,
          lastMessage: note
        };
        registered++;
      }
      await saveSavedState();
      state.selectedRecords = [];
      els.output.value = '';
      populateNeighborhoods();
      updateStats();
      renderSentTracking();
      setStatus(registered + ' contrato(s) registrados no Dominium. Nenhuma mensagem foi enviada.', 'success');
    } catch (error) {
      populateNeighborhoods();
      updateStats();
      setStatus('Registro parcial (' + registered + ' confirmados): ' + error.message +
        '. Confira Rotas Enviadas antes de repetir.', 'error');
    } finally {
      button.disabled = false;
    }
  }'''
)
replace_between(
    "  async function refreshSentTracking() {",
    "  function renderSentTracking() {",
    '''  async function dominiumCall(path, options = {}) {
    if (typeof request !== 'function') throw Error('Sessao Dominium indisponivel');
    return request(path, { timeoutMs: 120000, ...options });
  }

  function dominiumProfile(cityKey) {
    return cityKey === 'natal' ? 'natal_parnamirim'
      : cityKey === 'recife' ? 'pernambuco' : cityKey;
  }

  async function loadDominiumSentContracts() {
    const response = await dominiumCall('/api/backlog/year/sent');
    if (!Array.isArray(response?.rows)) throw Error('Resposta de envios sem lista');
    const sent = {};
    for (const row of response.rows) {
      const contract = normalizeContract(row.contract);
      if (!contract) continue;
      const profile = stringValue(row.profile).toLowerCase();
      const city = dominiumProfile(profile);
      sent[profile + ':' + contract] = {
        contract, city, cityLabel: CITY_LABELS[city] || profile,
        sentAt: row.sent_at || row.sentAt || '',
        sentDate: row.sent_at || row.sentAt || '',
        technician: 'A DEFINIR',
        lastMessage: stringValue(row.note)
      };
    }
    return sent;
  }

  async function refreshSentTracking() {
    if (els.refreshTracking) els.refreshTracking.disabled = true;
    try {
      state.sentContracts = await loadDominiumSentContracts();
      populateNeighborhoods();
      updateStats();
      setStatus('Historico de envios atualizado do Dominium.', 'success');
    } catch (error) {
      setStatus('Nao foi possivel consultar envios do Dominium: ' + error.message, 'error');
    } finally {
      if (els.refreshTracking) els.refreshTracking.disabled = false;
      renderSentTracking();
    }
  }'''
)
replace_between(
    "  async function loadSavedState() {",
    "  async function saveSavedState(options = {}) {",
    '''  async function loadSavedState() {
    // Dados de clientes sao guardados somente na sessao deste navegador.
    // Nunca migrar a chave Firebase original entre aplicacoes.
    try {
      const savedClean = JSON.parse(sessionStorage.getItem(IMPERIUM_STORAGE_KEY) || '{}');
      state.clean106ByCity = Array.isArray(savedClean)
        ? { natal_parnamirim: savedClean } : savedClean;
      state.clean106MetaByCity = JSON.parse(sessionStorage.getItem(IMPERIUM_META_STORAGE_KEY) || '{}');
      const claro = JSON.parse(sessionStorage.getItem(CLARO_SESSION_KEY) || '{}');
      state.claroRecords = Array.isArray(claro.records) ? claro.records : [];
      state.claroFileName = stringValue(claro.fileName);
      state.claroUpdatedAt = stringValue(claro.updatedAt);
      state.clean106Contracts = state.clean106ByCity[getSelectedCityKey()] || [];
    } catch (error) {
      console.warn('Base de sessao invalida, iniciando sem planilhas.', error);
      state.clean106ByCity = {};
      state.clean106MetaByCity = {};
      state.claroRecords = [];
    }
    populateNeighborhoods();
    updateClaroBadge();
    updateImperiumBadge();
    updateStats();
    try {
      state.sentContracts = await loadDominiumSentContracts();
      populateNeighborhoods();
      updateStats();
    } catch (error) {
      setStatus('Planilhas locais prontas. Historico de envios indisponivel: ' +
        error.message, 'error');
    }
  }'''
)
replace_between(
    "  async function saveSavedState(options = {}) {",
    "  async function saveClaroState(options = {}) {",
    '''  async function saveSavedState(options = {}) {
    try {
      sessionStorage.setItem(IMPERIUM_STORAGE_KEY, JSON.stringify(state.clean106ByCity));
      sessionStorage.setItem(IMPERIUM_META_STORAGE_KEY, JSON.stringify(state.clean106MetaByCity));
    } catch (error) {
      console.warn('Base 106 mantida apenas em memoria ate encerrar esta pagina.', error);
      setStatus('Nao foi possivel guardar a base 106 na sessao: ' + error.message, 'error');
    }
  }'''
)
replace_between(
    "  async function saveClaroState(options = {}) {",
    "  async function loadClean106Chunks(firestore) {",
    '''  async function saveClaroState(options = {}) {
    try {
      sessionStorage.setItem(CLARO_SESSION_KEY, JSON.stringify({
        records: state.claroRecords,
        fileName: state.claroFileName,
        updatedAt: state.claroUpdatedAt
      }));
    } catch (error) {
      console.warn('Backlog Claro mantida apenas na pagina ate fechar.', error);
      setStatus('Arquivo carregado, mas nao foi possivel guardar na sessao: ' +
        error.message, 'error');
    }
  }'''
)
# Remove os helpers legados que faziam chamadas Firebase/Cloudflare.
# O Dominium utiliza exclusivamente sua API autenticada para envios.
replace_between(
    "  async function loadClean106Chunks(firestore) {",
    "  function findSheetWithHeaders(workbook, requiredHeaders) {", ""
)
legacy_consts = (
    "SENT_STORAGE_KEY", "FIREBASE_COLLECTION", "FIREBASE_DOC",
    "CLEAN_106_CHUNKS", "CLARO_CHUNKS", "SENT_CONTRACTS_COLLECTION",
    "CLEAN_106_CHUNK_SIZE", "CLARO_CHUNK_SIZE", "FIRESTORE_BATCH_LIMIT",
    "CLOUDFLARE_SENT_BATCH_LIMIT", "CLOUDFLARE_REQUEST_TIMEOUT_MS"
)
source = "\n".join(line for line in source.split("\n")
    if not any(line.startswith("  const " + name + " =") for name in legacy_consts))
source = source.replace(
    "    const buffer = await file.arrayBuffer();",
    "    if (file.size > 12 * 1024 * 1024) throw Error('Arquivo maior que 12 MB');\n"
    "    if (typeof XLSX === 'undefined') throw Error('Leitor XLSX nao carregou');\n"
    "    const buffer = await file.arrayBuffer();"
)
# O parser XLSX pesa quase 1 MB: carregar somente ao importar planilha.
source = source.replace(
    "  async function readWorkbook(file) {",
    """  let xlsxLoadPromise = null;
  function ensureXlsx() {
    if (typeof XLSX !== 'undefined') return Promise.resolve();
    if (!xlsxLoadPromise) {
      xlsxLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = '/vendor/xlsx.full.min.js?v=20261123-2';
        script.async = true;
        script.onload = () => {
          if (typeof XLSX !== 'undefined') resolve();
          else reject(Error('Leitor XLSX indisponivel'));
        };
        script.onerror = () => {
          xlsxLoadPromise = null;
          reject(Error('Nao foi possivel carregar o leitor Excel'));
        };
        document.head.appendChild(script);
      });
    }
    return xlsxLoadPromise;
  }

  async function readWorkbook(file) {"""
)
source = source.replace(
    "    if (typeof XLSX === 'undefined') throw Error('Leitor XLSX nao carregou');",
    "    await ensureXlsx();"
)
source = source.replace(
    "  function setDefaultDate() {\n    if (els.data) els.data.value = new Date().toISOString().slice(0, 10);\n  }",
    "  function setDefaultDate() {\n    if (els.data) els.data.value = new Date().toLocaleDateString('en-CA');\n  }"
)
source = source.replace(
    "    els.trackingSearch?.addEventListener('input', renderSentTracking);",
    "    els.trackingSearch?.addEventListener('input', renderSentTracking);\n"
    "    document.addEventListener('dominium:module-change', (event) => {\n"
    "      if (event.detail?.module === 'backlog') refreshSentTracking();\n"
    "    });"
)
source = source.replace(
    "    state.sentContracts = await loadDominiumSentContracts();\n      for (const record",
    "    state.sentContracts = await loadDominiumSentContracts();\n      for (const record"
)
source = source.replace(
    "  document.addEventListener('DOMContentLoaded', () => {\n    collectElements();",
    "  document.addEventListener('DOMContentLoaded', () => {\n    if (!document.getElementById('foraRotaInput')) return;\n    collectElements();"
)
source = source.replace(
    "})();\n",
    '''  if (typeof window !== 'undefined' && window.__DOMINIUM_FORA_ROTA_TEST__) {
    globalThis.DominiumForaRotaTestHooks = {
      parseClaroBacklog, parseImperiumBacklog, buildClean106Contracts,
      normalizeContract, extractSafraContract, normalizeText, state, els,
      markSelectedAsSent, availableRecordsForBairro, recordWasSent
    };
  }
})();
'''
)
assert source.endswith("})();\n")
assert "loadDominiumSentContracts" in source
(static / "backlog-fora-rota.js").write_text(source, encoding="utf-8")

file_path = static / "index.html"
html = file_path.read_text(encoding="utf-8")
assert 'id="backlogFindOffRoute"' in html
# Roda sem duplicar quando a interface ja foi integrada.
new_html = """
        <section class="backlog-card dominium-fora-rota" aria-label="Gerador detalhado de Fora de Rota">
          <h3>Gerador detalhado — Claro + Imperium</h3>
          <p>Importe o backlog Claro e o historico Imperium, escolha cidade e bairro e gere uma mensagem por contrato. Sem envio automatico de WhatsApp ou baixa de OS.</p>
          <p class="dfr-note">As planilhas com dados de clientes permanecem somente nesta sessao do navegador. Registros de envio sao gravados pela API autenticada do Dominium.</p>
          <div class="dfr-imports">
            <label class="drop-card">Backlog Claro (.xlsx/.xls/.csv)
              <input id="foraRotaInput" type="file" accept=".xlsx,.xls,.csv">
              <small id="foraRotaFileName">Selecione a planilha Claro</small>
            </label>
            <label class="drop-card">Historico Imperium (.xlsx/.xls/.csv)
              <input id="foraRotaImperiumInput" type="file" accept=".xlsx,.xls,.csv">
              <small id="foraRotaImperiumFileName">Selecione o historico da base 106</small>
            </label>
          </div>
          <div class="dfr-controls">
            <label>Cidade
              <select id="foraRotaCidadeSelect">
                <option value="natal_parnamirim">Natal / Parnamirim</option>
                <option value="fortaleza">Fortaleza</option>
                <option value="pernambuco">Recife / Pernambuco</option>
                <option value="mossoro">Mossoro</option>
              </select>
            </label>
            <button type="button" class="button secondary" id="foraRotaAdicionarCidadeButton">Adicionar base 106 a cidade</button>
            <label>Bairro
              <select id="foraRotaBairroSelect"><option value="">Importe o backlog Claro</option></select>
            </label>
            <label>Quantidade
              <input id="foraRotaQuantidadeInput" type="number" min="1" max="100" value="5">
            </label>
            <label>Tecnico
              <input id="foraRotaTecnicoInput" type="text" placeholder="A DEFINIR" maxlength="100">
            </label>
            <label>Data de envio
              <input id="foraRotaDataInput" type="date">
            </label>
            <label>Agenda
              <input id="foraRotaAgendaInput" type="text" value="08:00 - 22:00" maxlength="80">
            </label>
          </div>
          <div class="dfr-stats" id="foraRotaStats" aria-live="polite"></div>
          <div id="foraRotaSavedBases" class="dfr-saved-bases"></div>
          <details>
            <summary>Gerenciar bases 106 desta sessao</summary>
            <div class="backlog-actions dfr-clear">
              <button type="button" class="button secondary compact" data-clear-fora-rota-city="natal_parnamirim">Limpar Natal</button>
              <button type="button" class="button secondary compact" data-clear-fora-rota-city="fortaleza">Limpar Fortaleza</button>
              <button type="button" class="button secondary compact" data-clear-fora-rota-city="pernambuco">Limpar Recife</button>
              <button type="button" class="button secondary compact" data-clear-fora-rota-city="mossoro">Limpar Mossoro</button>
              <button type="button" class="button secondary compact" data-clear-fora-rota-city="all">Limpar todas</button>
            </div>
          </details>
          <div class="backlog-actions">
            <button type="button" class="button primary" id="foraRotaGerarButton">Gerar mensagem</button>
            <button type="button" class="button secondary" id="foraRotaCopiarButton">Copiar texto</button>
            <button type="button" class="button secondary" id="foraRotaMarcarButton">Registrar como enviado</button>
            <button type="button" class="button secondary" id="foraRotaLimparButton">Limpar selecao</button>
          </div>
          <p role="status" id="foraRotaStatus" class="dfr-status">Importe as planilhas para gerar mensagens.</p>
          <textarea id="foraRotaOutput" rows="11" readonly placeholder="As mensagens geradas aparecerao aqui."></textarea>
          <details>
            <summary>Acompanhamento dos registros de envio no Dominium</summary>
            <div class="dfr-tracking-tools">
              <label>Pesquisar
                <input id="foraRotaTrackingSearchInput" type="search" placeholder="Contrato, cidade ou observacao">
              </label>
              <button type="button" class="button secondary" id="foraRotaRefreshTrackingButton">Atualizar historico</button>
            </div>
            <p class="dfr-note">O registro de envio nao comprova retorno tecnico ou baixa. A verificacao da OS permanece no TOA/Imperium.</p>
            <div id="foraRotaTrackingRoot" class="dfr-tracking"></div>
          </details>
        </section>
"""
if 'id="foraRotaInput"' not in html:
    html = html.replace(
    '      </div>\n      <div class="backlog-panel hidden" data-backlog-pane="sent">',
    new_html + '      </div>\n      <div class="backlog-panel hidden" data-backlog-pane="sent">',
    1
)
assert 'id="foraRotaTrackingRoot"' in html
if '/backlog-fora-rota.css' not in html:
    html = html.replace(
    '<link rel="stylesheet" href="/backlog-analysis.css?v=20261103-image-1">',
    '<link rel="stylesheet" href="/backlog-analysis.css?v=20261103-image-1">\n'
    '  <link rel="stylesheet" href="/backlog-fora-rota.css?v=20261123-1">'
)
if '/backlog-fora-rota.js' not in html:
    html = html.replace(
    '<script src="/backlog-analysis.js?v=20261107-restore-status-1"></script>',
    '<script src="/backlog-analysis.js?v=20261107-restore-status-1"></script>\n'
    '  <script src="/backlog-fora-rota.js?v=20261123-1"></script>'
)
html = html.replace(
    '  <script src="/vendor/xlsx.full.min.js?v=20261123-1"></script>\n', ''
).replace('/backlog-fora-rota.js?v=20261123-1', '/backlog-fora-rota.js?v=20261123-2')
file_path.write_text(html, encoding="utf-8")

css = """
/* Somente a aba Análise Backlog > Fora de Rota. Sem sobrescrever o tema global. */
.dominium-fora-rota { margin-top: 16px; }
.dominium-fora-rota .dfr-note { font-size: 12px; opacity: .74; line-height: 1.5; }
.dominium-fora-rota .dfr-imports { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:16px 0; }
.dominium-fora-rota .drop-card { display:flex; flex-direction:column; gap:9px; padding:14px; border:1px solid var(--border-color,#5d2937); border-radius:13px; min-width:0; }
.dominium-fora-rota .drop-card small { overflow-wrap:anywhere; opacity:.8; }
.dominium-fora-rota .drop-card.has-file { border-color:#29875c; }
.dominium-fora-rota .dfr-controls { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); align-items:end; gap:10px; }
.dominium-fora-rota .dfr-controls label,.dominium-fora-rota .dfr-tracking-tools label { display:flex;flex-direction:column;gap:5px;font-size:12px;min-width:0; }
.dominium-fora-rota select,.dominium-fora-rota input,.dominium-fora-rota textarea { box-sizing:border-box;width:100%;min-width:0;border:1px solid #55303a;background:#101013;color:#eee;border-radius:10px;padding:10px; }
.dominium-fora-rota textarea { resize:vertical; font-family:ui-monospace,monospace; min-height:130px; white-space:pre-wrap; }
.dominium-fora-rota .dfr-stats { display:grid; grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:15px 0; }
.dominium-fora-rota .dfr-stats article { border:1px solid #55303a;border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:7px;min-width:0; }
.dominium-fora-rota .dfr-stats article span { text-transform:uppercase;font-size:10px;opacity:.7; }
.dominium-fora-rota .dfr-stats article strong { font-size:23px; }
.dominium-fora-rota .dfr-saved-bases { margin:12px 0; }
.dominium-fora-rota .dfr-saved-bases>div {display:flex;flex-wrap:wrap;gap:8px;margin-top:7px;}
.dominium-fora-rota .dfr-saved-bases button { border:1px solid #5d2937;background:#111;color:#eee;padding:7px 10px;border-radius:24px;cursor:pointer; }
.dominium-fora-rota .dfr-saved-bases button.active { border-color:#2ca878; }
.dominium-fora-rota .dfr-saved-bases button strong { color:#34cb86; }
.dominium-fora-rota details { border-top:1px solid #4a2930;padding:12px 0; }
.dominium-fora-rota details summary { cursor:pointer; }
.dominium-fora-rota .backlog-actions { margin:12px 0;flex-wrap:wrap; }
.dominium-fora-rota .dfr-status { font-size:12px;min-height:20px; }
.dominium-fora-rota .dfr-status.error { color:#ff8794; }
.dominium-fora-rota .dfr-status.success { color:#68ddb2; }
.dominium-fora-rota .dfr-tracking-tools {display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:12px 0;}
.dominium-fora-rota .dfr-tracking-tools label {flex:1;min-width:170px;}
.dominium-fora-rota .dfr-tracking {overflow:auto;max-height:480px;}
.dominium-fora-rota .dfr-tracking table {width:100%;border-collapse:collapse;min-width:520px;font-size:12px;}
.dominium-fora-rota .dfr-tracking th,.dominium-fora-rota .dfr-tracking td {padding:7px;border-bottom:1px solid #4a2930;text-align:left;}
.dominium-fora-rota .dfr-tracking details {padding-left:6px;}
@media (max-width:1000px) {
  .dominium-fora-rota .dfr-controls {grid-template-columns:repeat(2,minmax(0,1fr));}
  .dominium-fora-rota .dfr-stats {grid-template-columns:repeat(3,minmax(0,1fr));}
}
@media (max-width:640px) {
  .dominium-fora-rota .dfr-imports,.dominium-fora-rota .dfr-controls {grid-template-columns:1fr;}
  .dominium-fora-rota .dfr-stats {grid-template-columns:repeat(2,minmax(0,1fr));}
}
"""
(static / "backlog-fora-rota.css").write_text(css, encoding="utf-8")
print("CREATED frontend", len(source), "chars, inserted HTML and CSS")
