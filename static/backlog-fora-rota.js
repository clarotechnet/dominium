(() => {
  const IMPERIUM_STORAGE_KEY = 'dominium-fora-rota-106-v1';
  const IMPERIUM_META_STORAGE_KEY = 'dominium-fora-rota-meta-v1';
  const CLARO_SESSION_KEY = 'dominium-fora-rota-claro-session-v1';
  const CLEAN_CODE = '106';
  const MISSING_BAIRRO_FILTER = '__sem_bairro__';
  const CITY_LABELS = {
    natal_parnamirim: 'Natal/Parnamirim',
    fortaleza: 'Fortaleza',
    pernambuco: 'Pernambuco',
    mossoro: 'Mossoro',
  };

  const SHARED_API = '/api/fora-rota/state';
  const profileKeys = ['natal','fortaleza','mossoro','recife'];
  const state = {
    sharedReady: false, sharedLoading: null, sharedEpoch: 0, revisions: {}, legacySent: {},
    claroRecords: [],
    selectedRecords: [],
    sentContracts: {},
    clean106Contracts: [],
    clean106ByCity: {},
    clean106MetaByCity: {},
    pendingClean106: [],
    pendingFileName: '',
    claroFileName: '',
    claroUpdatedAt: '',
  };

  const els = {};

  document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('foraRotaInput')) return;
    collectElements();
    wireEvents();
    setDefaultDate();
    populateNeighborhoods(); updateStats();
  });

  function collectElements() {
    els.claroInput = document.getElementById('foraRotaInput');
    els.claroFileName = document.getElementById('foraRotaFileName');
    els.imperiumInput = document.getElementById('foraRotaImperiumInput');
    els.imperiumFileName = document.getElementById('foraRotaImperiumFileName');
    els.cidade = document.getElementById('foraRotaCidadeSelect');
    els.adicionarCidade = document.getElementById('foraRotaAdicionarCidadeButton');
    els.bairro = document.getElementById('foraRotaBairroSelect');
    els.quantidade = document.getElementById('foraRotaQuantidadeInput');
    els.tecnico = document.getElementById('foraRotaTecnicoInput');
    els.data = document.getElementById('foraRotaDataInput');
    els.agenda = document.getElementById('foraRotaAgendaInput');
    els.gerar = document.getElementById('foraRotaGerarButton');
    els.copiar = document.getElementById('foraRotaCopiarButton');
    els.marcar = document.getElementById('foraRotaMarcarButton');
    els.limpar = document.getElementById('foraRotaLimparButton');
    els.clearCityButtons = [...document.querySelectorAll('[data-clear-fora-rota-city]')];
    els.output = document.getElementById('foraRotaOutput');
    els.status = document.getElementById('foraRotaStatus');
    els.stats = document.getElementById('foraRotaStats');
    els.trackingRoot = document.getElementById('foraRotaTrackingRoot');
    els.trackingSearch = document.getElementById('foraRotaTrackingSearchInput');
    els.refreshTracking = document.getElementById('foraRotaRefreshTrackingButton');
  }

  function wireEvents() {
    // Selecting the same updated file must trigger `change` again.
    els.claroInput?.addEventListener('click', () => {
      els.claroInput.value = '';
    });
    els.imperiumInput?.addEventListener('click', () => {
      els.imperiumInput.value = '';
    });
    els.claroInput?.addEventListener('change', handleClaroImport);
    els.imperiumInput?.addEventListener('change', handleImperiumImport);
    els.adicionarCidade?.addEventListener('click', addPendingBaseToCity);
    els.cidade?.addEventListener('change', () => {
      state.clean106Contracts = state.clean106ByCity[getSelectedCityKey()] || [];
      populateNeighborhoods();
      updateStats();
      updateImperiumBadge();
    });
    els.bairro?.addEventListener('change', updateStats);
    els.quantidade?.addEventListener('input', updateStats);
    els.gerar?.addEventListener('click', async () => {
      if (!await refreshSentTracking()) return;
      generateMessages();
    });
    els.copiar?.addEventListener('click', async () => {
      if (!state.selectedRecords.length || !els.output.value.trim()) {
        setStatus('Gere a lista antes de copiar.', 'error');
        return;
      }
      if (!await checkSelectionForExport()) return;
      await copyMessages();
    });
    els.marcar?.addEventListener('click', async () => {
      if (!await checkSelectionForExport()) return;
      await markSelectedAsSent();
    });
    [els.cidade, els.bairro, els.quantidade, els.tecnico, els.data, els.agenda,
      els.claroInput, els.imperiumInput, els.adicionarCidade, ...els.clearCityButtons].forEach((control) => {
      control?.addEventListener('change', invalidateSelection);
    });
    els.adicionarCidade?.addEventListener('click', invalidateSelection);
    els.clearCityButtons.forEach((button) => button.addEventListener('click', invalidateSelection));
    els.limpar?.addEventListener('click', clearSelection);
    els.clearCityButtons?.forEach((button) => button.addEventListener('click', () => clearSavedCity(button.dataset.clearForaRotaCity)));
    els.refreshTracking?.addEventListener('click', refreshSentTracking);
    els.trackingSearch?.addEventListener('input', renderSentTracking);
    document.addEventListener('dominium:module-change', (event) => {
      if (event.detail?.module === 'backlog') refreshSentTracking();
    });
    document.addEventListener('dominium:fora-rota-ready', () => refreshSentTracking());
    document.addEventListener('dominium:auth-cleared', () => {
      state.sharedEpoch++; state.sharedLoading=null; state.sharedReady=false; state.revisions={}; state.legacySent={};
      state.claroRecords=[]; state.clean106ByCity={}; state.clean106MetaByCity={}; state.clean106Contracts=[];
      state.sentContracts={}; state.pendingClean106=[]; state.pendingFileName=''; state.claroFileName=''; state.claroUpdatedAt='';
      invalidateSelection(); populateNeighborhoods(); updateImperiumBadge(); updateClaroBadge(); updateStats();
      for (const key of [IMPERIUM_STORAGE_KEY,IMPERIUM_META_STORAGE_KEY,CLARO_SESSION_KEY]) {try{sessionStorage.removeItem(key);}catch{}}
    });
    document.getElementById('foraRotaRefreshSharedButton')?.addEventListener('click', () => refreshSentTracking());
    document.getElementById('foraRotaLegacyImport')?.addEventListener('change', importLegacyHistory);
  }

  function invalidateSelection() {
    state.selectedRecords = [];
    els.output.value = '';
  }

  async function checkSelectionForExport() {
    if (!state.selectedRecords.length || !els.output.value.trim()) {
      setStatus('Gere novamente a lista antes de continuar.', 'error');
      return false;
    }
    if (!await refreshSentTracking()) return false;
    if (state.selectedRecords.some(recordWasSent)) {
      invalidateSelection();
      setStatus('A lista contém contrato já registrado no Dominium. Gere novamente.', 'error');
      return false;
    }
    const eligible = new Set(availableRecordsForBairro(els.bairro.value).map(r=>normalizeContract(r.contract)));
    if (!state.selectedRecords.length || state.selectedRecords.some(r=>!eligible.has(normalizeContract(r.contract)))) {
      invalidateSelection(); setStatus('A base foi atualizada. Gere novamente.', 'error'); return false;
    }
    return window.confirm('Conferiu os contratos no TOA e eventuais retornos recentes no Analise-Backlog? O histórico foi migrado, mas a sincronização do bot ainda não é contínua.');
  }

  function setDefaultDate() {
    if (els.data) els.data.value = new Date().toLocaleDateString('en-CA');
  }

  async function handleClaroImport() {
    const file = els.claroInput?.files?.[0];
    if (!file) return;
    try {
      if (!await refreshSentTracking()) return;
      const epoch=state.sharedEpoch;
      setStatus('Lendo backlog da Claro...', 'loading');
      const imported=parseClaroBacklog(await readWorkbook(file)).filter(isSupportedOperationalCity);
      if (epoch!==state.sharedEpoch) return;
      const groups=profileKeys.map(profile=>({profile,records:imported.filter(r=>operationalProfile(r.city)===profile)}));
      if (!imported.length || groups.some(g=>!g.records.length)) throw Error('A Safra semanal precisa conter as quatro bases atendidas; nenhuma base foi substituída.');
      if (!window.confirm('Substituir as bases Claro das quatro regiões por esta Safra? As versões anteriores serão preservadas.')) return;
      let saved=0;
      try {
        for (const group of groups) {
          if (epoch!==state.sharedEpoch) throw Error('Sessão alterada');
          await putShared(group.profile,'claro',group.records,file.name); saved++;
        }
      } catch(error) { throw Error(saved+' de 4 bases atualizadas. Confira as versões e reimporte se necessário: '+error.message); }
      invalidateSelection();
      if (!await refreshSentTracking()) throw Error('Dados gravados; atualização da tela pendente.');
      setStatus(imported.length+' contratos salvos no banco compartilhado.', 'success');
    } catch(error) {setStatus('Falha na importação: '+error.message,'error');}
    finally {els.claroInput.value='';}
  }

  async function handleImperiumImport() {
    const file = els.imperiumInput?.files?.[0];
    if (!file) return;

    try {
      setStatus('Lendo backlog do Imperium para encontrar 106 limpo...', 'loading');
      setFileBadge(els.imperiumFileName, file.name, true);
      const workbook = await readWorkbook(file);
      const importedHistory = parseImperiumBacklog(workbook);
      state.pendingClean106 = buildClean106Contracts(importedHistory);
      state.pendingFileName = file.name;
      updateImperiumBadge();
      populateNeighborhoods();
      updateStats();
      setStatus(`${state.pendingClean106.length} contrato(s) 106 limpo prontos. Escolha a cidade e clique em Adicionar base da cidade.`, 'success');
    } catch (error) {
      console.error(error);
      setStatus(`Falha ao ler backlog do Imperium: ${error.message}`, 'error');
    }
  }

  let xlsxLoadPromise = null;
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

  async function readWorkbook(file) {
    if (file.size > 32 * 1024 * 1024) throw Error('Arquivo maior que 32 MB');
    await ensureXlsx();
    const buffer = await file.arrayBuffer();
    if (/\.csv$/i.test(file.name)) {
      const text = new TextDecoder('utf-8').decode(buffer).replace(/^\uFEFF/, '');
      return XLSX.read(text, { type: 'string', raw: false, dense: true });
    }
    return XLSX.read(buffer, { type: 'array', cellDates: true, dense: true });
  }

  function parseClaroBacklog(workbook) {
    const safraSheet = findSafraClaroSheet(workbook);
    if (safraSheet) {
      const parsedSafra = parseSafraClaroBacklog(safraSheet);
      if (parsedSafra.length) return parsedSafra;
    }

    const sheet =
      findSheetWithHeaders(workbook, ['base cd net']) ||
      findSheetWithHeaders(workbook, ['base cdnet']) ||
      findSheetWithHeaders(workbook, ['cd net']) ||
      findSheetWithHeaders(workbook, ['contrato']);
    if (sheet) {
      const headerMap = buildHeaderMap(sheet.rows[sheet.headerIndex]);
      const parsedByHeader = sheet.rows
        .slice(sheet.headerIndex + 1)
        .map((row) => normalizeClaroRow(row, headerMap))
        .filter((record) => record.contract);
      if (parsedByHeader.length) return parsedByHeader;
    }

    const fixedRows = parseClaroBacklogByFixedColumns(getAllWorkbookRows(workbook));
    if (fixedRows.length) return fixedRows;

    throw new Error('Nao encontrei coluna BASE_CDNET/CD_NET/contrato na planilha da Claro.');
  }

  function parseSafraClaroBacklog(sheet) {
    const headerMap = buildHeaderMap(sheet.rows[sheet.headerIndex]);
    const merged = new Map();

    for (const row of sheet.rows.slice(sheet.headerIndex + 1)) {
      const baseCdNet = pick(row, headerMap, ['base cd net', 'base cdnet']);
      const contract = extractSafraContract(
        baseCdNet,
        pick(row, headerMap, ['cd net', 'contrato', 'num contrato'])
      );
      if (!contract) continue;

      const city = normalizeDisplay(pick(row, headerMap, ['nm cidade', 'cidade']));
      // CD_NET is not globally unique: the same numeric contract can exist in
      // different Claro bases/cities. Merge equipment rows by BASE_CD_NET
      // (or city+contract fallback) so one city never overwrites another.
      const mergeKey = normalizeText(baseCdNet) || `${city}__${contract}`;

      const current = merged.get(mergeKey) || {
        contract,
        city: '',
        name: '',
        address: '',
        bairro: '',
        cep: '',
        phones: [],
        agenda: '',
        technician: 'A DEFINIR',
        equipment: '',
        altAddress: '',
      };

      const ddd = stringValue(pick(row, headerMap, ['ddd'])).replace(/\D+/g, '').slice(-2);
      const phones = [
        pick(row, headerMap, ['telefone netsms', 'tel netsms', 'telefones', 'telefone', 'tel']),
        pick(row, headerMap, ['telefone tel', 'tel ura', 'tel1', 'telefone 1']),
        pick(row, headerMap, ['tel ura', 'tel agend conf', 'tel2', 'telefone 2']),
      ]
        .flatMap(splitPhones)
        .map((phone) => normalizePhoneWithDdd(phone, ddd));

      const equipmentLabel = pick(row, headerMap, ['nr mac']);

      const altAddress = stringValue(pick(row, headerMap, ['dx22']));

      merged.set(mergeKey, {
        contract,
        baseCdNet: stringValue(baseCdNet),
        city: current.city || city,
        name: current.name || pick(row, headerMap, ['nome', 'nome cliente', 'cliente']),
        address: current.address || pick(row, headerMap, ['endereco', 'endereço', 'logradouro']),
        bairro: current.bairro || pick(row, headerMap, ['bairro']),
        cep: current.cep || pick(row, headerMap, ['cep']) || extractCepFromText(altAddress),
        phones: unique([...(current.phones || []), ...phones]),
        agenda: current.agenda || extractAgendaFromDx22Text(altAddress),
        technician: 'A DEFINIR',
        equipment: mergeEquipmentField(current.equipment, equipmentLabel),
        altAddress: current.altAddress || altAddress,
      });
    }

    return [...merged.values()].filter((record) => record.contract);
  }

  function findSafraClaroSheet(workbook) {
    const preferredNames = ['safra dados epo', 'safra dados', 'safra base', 'planilha1'];
    for (const name of workbook.SheetNames) {
      const normalizedName = normalizeText(name);
      if (!preferredNames.some((preferred) => normalizedName.includes(preferred))) continue;

      const rows = XLSX.utils.sheet_to_json(workbook.Sheets[name], {
        header: 1,
        defval: '',
        raw: true,
        blankrows: false,
      });
      let headerIndex = findHeaderRow(rows, ['base cd net', 'nr mac']);
      if (headerIndex === -1) headerIndex = findHeaderRow(rows, ['base cd net', 'dx22']);
      if (headerIndex === -1) headerIndex = findHeaderRow(rows, ['base cdnet', 'nr mac']);
      if (headerIndex === -1) headerIndex = findHeaderRow(rows, ['base cdnet', 'dx22']);
      if (headerIndex === -1) headerIndex = findHeaderRow(rows, ['cd net', 'nr mac']);
      if (headerIndex !== -1) return { name, rows, headerIndex };
    }

    return (
      findSheetWithHeaders(workbook, ['base cd net', 'nr mac']) ||
      findSheetWithHeaders(workbook, ['base cd net', 'dx22']) ||
      findSheetWithHeaders(workbook, ['base cdnet', 'nr mac']) ||
      findSheetWithHeaders(workbook, ['base cdnet', 'dx22']) ||
      findSheetWithHeaders(workbook, ['cd net', 'nr mac'])
    );
  }

  function getAllWorkbookRows(workbook) {
    return workbook.SheetNames.flatMap((name) =>
      XLSX.utils.sheet_to_json(workbook.Sheets[name], {
        header: 1,
        defval: '',
        raw: true,
        blankrows: false,
      })
    );
  }

  function parseClaroBacklogByFixedColumns(rows) {
    return rows
      .map((row) => {
        const altAddress = stringValue(row[10]);
        return {
          contract: extractSafraContract(row[6]),
          // NM_CIDADE is kept only so the city selector does not mix bases.
          city: normalizeDisplay(row[1]),
          name: stringValue(row[7]),
          address: stringValue(row[8]),
          bairro: stringValue(row[9]),
          cep: extractCepFromText(altAddress),
          phones: unique(
            [row[11], row[12], row[13]].flatMap(splitPhones)
          ),
          agenda: extractAgendaFromDx22Text(altAddress),
          altAddress,
          technician: 'A DEFINIR',
          equipment: stringValue(row[21]),
        };
      })
      .filter((record) => record.contract);
  }

  function parseImperiumBacklog(workbook) {
    const sheet = findSheetWithHeaders(workbook, ['num contrato', 'cod baixa']) || findSheetWithHeaders(workbook, ['contrato', 'cod baixa']);
    if (!sheet) throw new Error('Nao encontrei contrato e cod baixa na backlog do Imperium.');

    const headerMap = buildHeaderMap(sheet.rows[sheet.headerIndex]);
    const history = {};

    for (const [rowIndex, row] of sheet.rows.slice(sheet.headerIndex + 1).entries()) {
      const contract = normalizeContract(pick(row, headerMap, ['num contrato', 'contrato']));
      const code = normalizeCode(pick(row, headerMap, ['cod baixa', 'codigo baixa', 'codigo de baixa']));
      if (!contract || !code) continue;
      if (!history[contract]) history[contract] = [];
      const date = pick(row, headerMap, ['data da baixa', 'data baixa', 'data']);
      history[contract].push({
        code,
        date,
        sortKey: parseImperiumHistoryTimestamp(date),
        rowOrder: rowIndex,
      });
    }

    return history;
  }

  function normalizeClaroRow(row, headerMap) {
    const address = pick(row, headerMap, ['endereco', 'endereço', 'logradouro']) || stringValue(row[11]) || stringValue(row[14]);
    const number = pick(row, headerMap, ['numero', 'número', 'num']);
    const complement = pick(row, headerMap, ['complemento']);
    const bairro = pick(row, headerMap, ['bairro']) || stringValue(row[12]) || stringValue(row[15]);
    const cep = pick(row, headerMap, ['cep', 'cep codigo postal', 'cep/codigo postal']) || stringValue(row[16]);
    const phones = [
      pick(row, headerMap, ['telefones', 'telefone', 'tel', 'tel netsms']) || stringValue(row[14]) || stringValue(row[17]),
      pick(row, headerMap, ['tel1', 'telefone 1', 'tel ura']) || stringValue(row[15]) || stringValue(row[18]),
      pick(row, headerMap, ['tel2', 'telefone 2', 'tel agend conf']) || stringValue(row[16]),
    ].flatMap(splitPhones);

    return {
      contract: extractSafraContract(
        pick(row, headerMap, ['base cdnet']),
        pick(row, headerMap, ['cd net', 'contrato', 'num contrato']) || stringValue(row[7]) || stringValue(row[11])
      ),
      city: normalizeDisplay(pick(row, headerMap, ['nm cidade', 'cidade']) || stringValue(row[1]) || stringValue(row[3])),
      name: pick(row, headerMap, ['nome', 'nome cliente', 'cliente']) || stringValue(row[10]) || stringValue(row[13]),
      address: [address, number, complement].filter(Boolean).join(' '),
      bairro,
      cep,
      phones: unique(phones),
      agenda: pick(row, headerMap, ['agenda confirmada']) || stringValue(row[19]),
      technician: pick(row, headerMap, ['tecnico', 'técnico']) || 'A DEFINIR',
      equipment:
        pick(row, headerMap, ['nr mac', 'equipamentos']) ||
        stringValue(row[23]) ||
        stringValue(row[22]) ||
        stringValue(row[33]) ||
        stringValue(row[32]),
      altAddress:
        pick(row, headerMap, ['dx22', 'end alternativo', 'endereco alternativo', 'endereço alternativo']) ||
        stringValue(row[13]) ||
        stringValue(row[20]),
    };
  }

  function buildClean106Contracts(history) {
    const clean = new Set();
    for (const [contract, entries] of Object.entries(history)) {
      const codes = new Set(entries.map((entry) => normalizeCode(entry?.code)).filter(Boolean));
      if (!codes.has(CLEAN_CODE)) continue;
      if (codes.has('430')) continue;

      const latest = [...entries]
        .filter((entry) => normalizeCode(entry?.code))
        .sort((a, b) => (Number(b?.sortKey) || 0) - (Number(a?.sortKey) || 0) || (Number(b?.rowOrder) || 0) - (Number(a?.rowOrder) || 0))[0];
      if (normalizeCode(latest?.code) === CLEAN_CODE) {
        clean.add(contract);
      }
    }
    return [...clean].sort(compareContract);
  }

  function getClean106Contracts() {
    return new Set(state.clean106ByCity[getSelectedCityKey()] || state.clean106Contracts || []);
  }

  function availableRecordsForBairro(bairro) {
    const clean106 = getClean106Contracts();
    const sent = sentContractIndex();
    const missingBairroOnly = bairro === MISSING_BAIRRO_FILTER;
    const normalizedBairro = missingBairroOnly ? '' : normalizeText(bairro);
    return state.claroRecords.filter((record) => {
      if (!recordMatchesSelectedCity(record)) return false;
      if (!recordMatchesContractSet(record, clean106)) return false;
      if (recordWasSent(record, sent)) return false;
      const recordBairro = normalizeText(record.bairro);
      if (missingBairroOnly) return !recordBairro;
      if (!normalizedBairro) return true;
      return recordBairro === normalizedBairro;
    });
  }

  function getRecordContractKeys(record) {
    const contract = normalizeContract(record?.contract);
    return contract ? [contract] : [];
  }

  function recordMatchesContractSet(record, contracts) {
    return getRecordContractKeys(record).some((contract) => contracts.has(contract));
  }

  function sentContractIndex() {
    const scope = operationalProfile(getSelectedCityKey());
    const contracts = new Set();
    for (const record of Object.values(state.sentContracts || {})) {
      const city = operationalProfile(record?.city || record?.cityLabel);
      if (city && city !== scope) continue;
      const contract = normalizeContract(record?.contract);
      if (contract) contracts.add(contract);
    }
    return contracts;
  }

  function recordWasSent(record, sent = sentContractIndex()) {
    return getRecordContractKeys(record).some(contract => sent.has(contract));
  }

  function sentRecordMatchesSelectedCity(sentRecord) {
    const scope=operationalProfile(sentRecord?.city || sentRecord?.cityLabel);
    return !scope || scope===operationalProfile(getSelectedCityKey());
  }

  async function addPendingBaseToCity() {
    if (!state.pendingClean106.length) {setStatus('Importe o histórico Imperium antes de salvar.','error');return;}
    const city=getSelectedCityKey(), profile=operationalProfile(city), rows=[...state.pendingClean106], name=state.pendingFileName;
    if (!await refreshSentTracking()) return;
    if (!window.confirm('Salvar nova versão da base 106 de '+CITY_LABELS[city]+'?')) return;
    try {
      await putShared(profile,'clean106',rows,name||'Histórico Imperium');
      state.pendingClean106=[]; state.pendingFileName=''; invalidateSelection();
      await refreshSentTracking(); setStatus('Base 106 compartilhada salva: '+CITY_LABELS[city], 'success');
    } catch(error) {setStatus(error.message,'error');}
  }

  function getSelectedCityKey() {
    return els.cidade?.value || 'natal_parnamirim';
  }

  function isSupportedOperationalCity(record) {
    return Boolean(operationalProfile(record?.city));
  }

  function recordMatchesSelectedCity(record) {
    return operationalProfile(record.city) === operationalProfile(getSelectedCityKey());
  }

  async function clearSavedCity(cityKey) {
    setStatus('Para proteger o histórico compartilhado, substitua a base por uma importação validada. A limpeza em massa foi desativada.', 'error');
  }

  function populateNeighborhoods() {
    const allAvailable = availableRecordsForBairro('');
    let missingBairroCount = 0;
    const counts = new Map();
    for (const record of allAvailable) {
      const key = normalizeText(record.bairro);
      if (!key) { missingBairroCount++; continue; }
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    const neighborhoods = [...new Set(
      state.claroRecords
        .filter(recordMatchesSelectedCity)
        .map((record) => normalizeDisplay(record.bairro))
        .filter(Boolean)
    )]
      .map(bairro => ({ bairro, total: counts.get(normalizeText(bairro)) || 0 }))
      .filter(item => item.total > 0)
      .sort((a, b) => a.bairro.localeCompare(b.bairro, 'pt-BR'));

    const missingOption = missingBairroCount
      ? `<option value="${MISSING_BAIRRO_FILTER}">SEM BAIRRO (${missingBairroCount})</option>`
      : '';
    els.bairro.innerHTML = allAvailable.length
      ? `<option value="">Todos os bairros disponiveis (${allAvailable.length})</option>${missingOption}${neighborhoods
          .map((item) => `<option value="${escapeHtml(item.bairro)}">${escapeHtml(item.bairro)} (${item.total})</option>`)
          .join('')}`
      : '<option value="">Nenhum bairro disponivel</option>';
  }

  function generateMessages() {
    const selected = selectRecords();
    state.selectedRecords = selected;
    els.output.value = selected.map(formatMessage).join('\n\n');
    updateStats();
    setStatus(selected.length ? `${selected.length} mensagem(ns) gerada(s).` : 'Nenhum 106 limpo disponivel para esse filtro.', selected.length ? 'success' : 'error');
  }

  function selectRecords() {
    const limit = Math.max(1, Number(els.quantidade.value || 1));
    return availableRecordsForBairro(els.bairro.value).slice(0, limit);
  }

  function formatMessage(record) {
    const agenda = stringValue(els.agenda.value) || record.agenda || '08:00 - 22:00';
    const tecnico = stringValue(els.tecnico.value) || record.technician || 'A DEFINIR';
    const rawAddressLine = `${record.address}${record.bairro ? ` - ${record.bairro}` : ''}`;
    const addressLine = `${formatAddressNumbers(rawAddressLine)}${record.cep ? ` / ${record.cep}` : ''}`;
    const lines = [
      '⭕ *FORA ROTA* ⭕',
      `*CONTRATO:* ${record.contract}`,
      `*NOME:* ${record.name || '-'}`,
      `*END:* ${addressLine || '-'}`,
    ];
    if (record.altAddress) lines.push(`*Ret em outro end:* ${record.altAddress}`);
    lines.push(
      `*AGENDA:* ${agenda}`,
      `*TEL:* ${record.phones.length ? record.phones.join(' / ') : '-'}`,
      `*Técnico:* ${tecnico}`,
      `*Equipamentos:* ${record.equipment || '-'}`,
    );
    return lines.join('\n');
  }

  function formatAddressNumbers(value) {
    const text = stringValue(value);
    if (!text) return '';
    return text.replace(/\b\d{1,3}\b/g, (match) => match.padStart(4, '0'));
  }

  async function copyMessages() {
    if (!els.output.value.trim()) generateMessages();
    if (!els.output.value.trim()) return;
    await navigator.clipboard.writeText(els.output.value);
    setStatus('Texto copiado para a area de transferencia.', 'success');
  }

  // Envio aqui significa SOMENTE registrar no historico do Dominium.
  // Nao dispara WhatsApp, baixa de OS nem operacao no Imperium.
  async function markSelectedAsSent() {
    if (!state.selectedRecords.length || els.marcar.disabled) return;
    const button=els.marcar; button.disabled=true;
    const profile=operationalProfile(getSelectedCityKey()), selected=[...state.selectedRecords];
    const technician=stringValue(els.tecnico.value)||'A DEFINIR', sentDate=stringValue(els.data.value), agenda=stringValue(els.agenda.value)||'08:00 - 22:00';
    try {
      if (!await refreshSentTracking()) return;
      if (!state.selectedRecords.length || profile!==operationalProfile(getSelectedCityKey()) || selected.some(record => recordWasSent(record))) throw Error('Histórico ou cidade alterado. Gere novamente.');
      const rows=selected.map(r=>({contract:normalizeContract(r.contract),city:r.city,technician,sentDate,agenda}));
      const result=await dominiumCall(SHARED_API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'mark_sent',profile,kind:'legacy_sent',expected_revision:state.revisions[profile+':legacy_sent']||0,records:rows})});
      if (result?.ok!==true) throw Error('Registro não confirmado');
      invalidateSelection();
      await refreshSentTracking();
      setStatus(result.count+' contratos registrados no banco compartilhado. Nenhuma mensagem foi enviada.', 'success');
    } catch(error) {invalidateSelection();setStatus('Confira o histórico antes de repetir: '+error.message,'error');}
    finally {button.disabled=false;}
  }

  function clearSelection() {
    state.selectedRecords = [];
    els.output.value = '';
    updateStats();
    setStatus('Selecao limpa.', 'success');
  }

  function updateStats() {
    if (!els.stats) return;
    const clean106 = getClean106Contracts();
    const available = availableRecordsForBairro(els.bairro?.value || '').length;
    const sent = Object.values(state.sentContracts || {}).filter(sentRecordMatchesSelectedCity).length;
    const claroCity = state.claroRecords.filter(recordMatchesSelectedCity);
    const inClaroAndClean = claroCity.filter((record) => recordMatchesContractSet(record, clean106)).length;
    els.stats.innerHTML = `
      <article><span>Backlog Claro</span><strong>${claroCity.length || '-'}</strong></article>
      <article><span>106 limpo Imperium</span><strong>${clean106.size || '-'}</strong></article>
      <article><span>Claro + 106 limpo</span><strong>${inClaroAndClean || '-'}</strong></article>
      <article><span>Disponiveis</span><strong>${available || '-'}</strong></article>
      <article><span>Ja enviados na cidade</span><strong>${sent || '-'}</strong></article>
    `;
    renderSavedBases();
    renderSentTracking();
  }

  async function dominiumCall(path, options = {}) {
    if (typeof request !== 'function') throw Error('Sessao Dominium indisponivel');
    return request(path, { timeoutMs: 120000, ...options });
  }

  function dominiumProfile(cityKey) {
    return cityKey === 'natal' ? 'natal_parnamirim'
      : cityKey === 'recife' ? 'pernambuco' : cityKey;
  }

  async function loadDominiumSentContracts() {
    const response=await dominiumCall('/api/backlog/year/sent');
    if (!Array.isArray(response?.rows)) throw Error('Resposta de envios sem lista');
    const sent={...state.legacySent};
    for (const row of response.rows) {
      const contract=normalizeContract(row.contract), profile=stringValue(row.profile).toLowerCase();
      if (!contract) continue;
      const city=dominiumProfile(profile), key=profile+':'+contract;
      if (!sent[key]) sent[key]={contract,city,cityLabel:CITY_LABELS[city]||profile,sentAt:row.sent_at||row.sentAt||'',sentDate:row.sent_at||row.sentAt||'',technician:'A DEFINIR',lastMessage:stringValue(row.note)};
    }
    return sent;
  }

  async function refreshSentTracking() {
    if (els.refreshTracking) els.refreshTracking.disabled=true;
    try {
      const epoch=state.sharedEpoch;
      await loadSharedState();
      // Make migrated data visible even if the old sidecar is temporarily down.
      state.sentContracts={...state.legacySent};
      populateNeighborhoods(); updateClaroBadge(); updateImperiumBadge(); updateStats();
      const combined=await loadDominiumSentContracts();
      if(epoch!==state.sharedEpoch)return false;
      state.sentContracts=combined; state.sharedReady=true;
      populateNeighborhoods(); updateClaroBadge(); updateImperiumBadge(); updateStats();
      setStatus('Bases compartilhadas e histórico atualizados.', 'success'); return true;
    } catch(error) {state.sharedReady=false;invalidateSelection();setStatus('Não foi possível atualizar as bases: '+error.message,'error');return false;}
    finally {if(els.refreshTracking)els.refreshTracking.disabled=false;renderSentTracking();}
  }

  function renderSentTracking() {
    if (!els.trackingRoot) return;

    const allRecords = Object.values(state.sentContracts || {}).filter((record) => normalizeContract(record?.contract));
    if (!allRecords.length) {
      els.trackingRoot.innerHTML = '<div class="empty-state">Nenhuma rota enviada marcada ainda.</div>';
      return;
    }

    const search = normalizeText(els.trackingSearch?.value || '');
    const records = search ? allRecords.filter((record) => sentRecordMatchesSearch(record, search)) : allRecords;

    if (!records.length) {
      els.trackingRoot.innerHTML = '<div class="empty-state">Nenhuma rota enviada encontrada para essa busca.</div>';
      return;
    }

    const byCity = groupSentRecords(records);
    const searchMeta = search
      ? `<div class="sent-search-meta">Mostrando ${records.length} de ${allRecords.length} rota(s) enviada(s).</div>`
      : '';

    els.trackingRoot.innerHTML = `${searchMeta}${Object.entries(byCity)
      .map(([cityLabel, techGroups], cityIndex) => renderCityTracking(cityLabel, techGroups, cityIndex === 0))
      .join('')}`;
  }

  function sentRecordMatchesSearch(record, search) {
    return [
      record.contract,
      record.cityLabel,
      record.city,
      record.groupName,
      record.technician,
      record.returnedByTechnician,
      record.lastReturnCode,
      record.lastMessage,
      record.sentDate,
      record.sentAt,
      record.returnedAt,
    ]
      .map((value) => normalizeText(value))
      .some((value) => value.includes(search));
  }

  function groupSentRecords(records) {
    const grouped = {};
    records
      .slice()
      .sort((a, b) => compareSentRecords(a, b))
      .forEach((record) => {
        const cityLabel = normalizeCityLabel(record.cityLabel || CITY_LABELS[record.city] || record.groupName || 'Sem cidade');
        const technician = normalizeTechnicianName(record.returnedByTechnician || record.technician || 'A DEFINIR');
        if (!grouped[cityLabel]) grouped[cityLabel] = {};
        if (!grouped[cityLabel][technician]) grouped[cityLabel][technician] = [];
        grouped[cityLabel][technician].push(record);
      });
    return grouped;
  }

  function renderCityTracking(cityLabel, techGroups, open) {
    const total = Object.values(techGroups).reduce((sum, items) => sum + items.length, 0);
    const returned = Object.values(techGroups).flat().filter((record) => record.lastReturnCode).length;
    return `
      <details class="sent-city" ${open ? 'open' : ''}>
        <summary>
          <strong>${escapeHtml(cityLabel)}</strong>
          <span>${total} enviada(s) • ${returned} com baixa</span>
        </summary>
        <div class="sent-tech-list">
          ${Object.entries(techGroups)
            .map(([technician, records]) => renderTechnicianTracking(technician, records))
            .join('')}
        </div>
      </details>
    `;
  }

  function renderTechnicianTracking(technician, records) {
    const returned = records.filter((record) => record.lastReturnCode).length;
    return `
      <details class="sent-tech">
        <summary>
          <strong>${escapeHtml(technician)}</strong>
          <span>${records.length} OS • ${returned} baixa(s)</span>
        </summary>
        <div class="table-wrap sent-table-wrap">
          <table class="sent-routes-table">
            <thead>
              <tr>
                <th>Contrato</th>
                <th>Data enviada</th>
                <th>Cod baixa</th>
                <th>Retorno</th>
                <th>OBS</th>
              </tr>
            </thead>
            <tbody>
              ${records.map(renderSentRecordRow).join('')}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }

  function renderSentRecordRow(record) {
    const code = normalizeCode(record.lastReturnCode) || '-';
    const returnedAt = formatShortDateTime(record.returnedAt);
    const sentDate = formatSentDate(record.sentDate || record.sentAt);
    const message = stringValue(record.lastMessage).slice(0, 240);
    const statusClass = code !== '-' ? 'good' : 'muted';
    return `
      <tr>
        <td><strong>${escapeHtml(record.contract)}</strong></td>
        <td>${escapeHtml(sentDate || '-')}</td>
        <td><span class="sent-code ${statusClass}">${escapeHtml(code)}</span></td>
        <td>${escapeHtml(returnedAt || 'Aguardando')}</td>
        <td>${escapeHtml(message || '-')}</td>
      </tr>
    `;
  }

  function compareSentRecords(a, b) {
    return (
      stringValue(b.returnedAt || b.updatedAt || b.sentAt).localeCompare(stringValue(a.returnedAt || a.updatedAt || a.sentAt)) ||
      compareContract(a.contract, b.contract)
    );
  }

  function normalizeCityLabel(value) {
    const normalized = normalizeText(value);
    if (normalized.includes('fortaleza')) return 'FORTALEZA';
    if (normalized.includes('pernambuco') || normalized.includes('recife')) return 'RECIFE';
    if (normalized.includes('mossoro')) return 'MOSSORO';
    if (normalized.includes('natal') || normalized.includes('parnamirim')) return 'NATAL/PARNAMIRIM';
    return normalizeDisplay(value || 'Sem cidade');
  }

  function normalizeTechnicianName(value) {
    return normalizeDisplay(value || 'A DEFINIR');
  }

  function formatSentDate(value) {
    const text = stringValue(value);
    if (!text) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
      const [year, month, day] = text.split('-');
      return `${day}/${month}/${year}`;
    }
    return formatShortDateTime(text) || text;
  }

  function renderSavedBases() {
    const target = document.getElementById('foraRotaSavedBases');
    if (!target) return;

    target.innerHTML = `
      <span>Bases 106 salvas</span>
      <div>
        ${Object.entries(CITY_LABELS)
          .map(([cityKey, label]) => {
            const total = state.clean106ByCity[cityKey]?.length || 0;
            const active = cityKey === getSelectedCityKey() ? ' active' : '';
            return `<button class="saved-base-chip${active}" type="button" data-select-fora-rota-city="${cityKey}">${escapeHtml(label)} <strong>${total}</strong></button>`;
          })
          .join('')}
      </div>
    `;

    target.querySelectorAll('[data-select-fora-rota-city]').forEach((button) => {
      button.addEventListener('click', () => {
        if (!els.cidade) return;
        els.cidade.value = button.dataset.selectForaRotaCity;
        els.cidade.dispatchEvent(new Event('change'));
      });
    });
  }

  function updateImperiumBadge() {
    const clean106 = getClean106Contracts();
    if (!els.imperiumFileName) return;
    if (state.pendingClean106.length && state.pendingFileName) {
      setFileBadge(
        els.imperiumFileName,
        `${state.pendingFileName} • ${state.pendingClean106.length} contrato(s) prontos para ${CITY_LABELS[getSelectedCityKey()]}`,
        true
      );
      return;
    }
    if (clean106.size) {
      const meta = state.clean106MetaByCity[getSelectedCityKey()] || {};
      const source = meta.fileName ? ` • ${meta.fileName}` : '';
      const updated = meta.updatedAt ? ` • ${formatShortDateTime(meta.updatedAt)}` : '';
      setFileBadge(
        els.imperiumFileName,
        `${clean106.size} contrato(s) 106 limpo em ${CITY_LABELS[getSelectedCityKey()]}${source}${updated}`,
        true
      );
    } else {
      setFileBadge(els.imperiumFileName, 'Usando base salva, se existir', false);
    }
  }

  function updateClaroBadge() {
    if (!els.claroFileName) return;
    if (state.claroRecords.length) {
      const suffix = state.claroUpdatedAt ? ` • ${formatShortDateTime(state.claroUpdatedAt)}` : '';
      setFileBadge(els.claroFileName, `${state.claroRecords.length} OS na base compartilhada${suffix}`, true);
    } else {
      setFileBadge(els.claroFileName, 'Nenhuma backlog da Claro salva', false);
    }
  }

  function operationalProfile(city) {
    const key=normalizeText(city).replace(/[^a-z0-9]+/g,' ').trim();
    if (['natal','parnamirim','natal parnamirim'].includes(key))return 'natal';
    if (key==='fortaleza')return 'fortaleza';
    if (key==='mossoro')return 'mossoro';
    if (['recife','pernambuco','recife pernambuco','jaboatao','jaboatao dos guararapes','olinda'].includes(key))return 'recife';
    return '';
  }
  async function loadSharedState() {
    if (state.sharedLoading)return state.sharedLoading;
    const epoch=state.sharedEpoch;
    const promise=(async()=>{
      const payload=await dominiumCall(SHARED_API);
      if(epoch!==state.sharedEpoch)throw Error('Sessão alterada');
      if(!Array.isArray(payload?.snapshots)||payload.snapshots.length!==13)throw Error('Bases compartilhadas incompletas');
      const revisions={}, clean={}, meta={}, legacy={}, claro=[];
      let latestDate='';
      for(const snapshot of payload.snapshots){
        const {profile,kind,records,revision}=snapshot;
        if(!Array.isArray(records)||!Number.isInteger(revision)||revision<0)throw Error('Versão inválida');
        revisions[profile+':'+kind]=revision;
        const city=dominiumProfile(profile);
        if(kind==='claro'){
          claro.push(...records); if(snapshot.created_at>latestDate)latestDate=snapshot.created_at;
        }else if(kind==='clean106'){
          clean[city]=records;meta[city]={fileName:snapshot.source_name,updatedAt:snapshot.created_at,count:records.length};
        }else if(kind==='legacy_sent'){
          for(const row of records){
            const contract=normalizeContract(row.contract);if(!contract)continue;
            const key=profile+':'+contract;
            const old=legacy[key];
            if(!old||(!old.lastReturnCode&&row.lastReturnCode)||((!old.lastReturnCode||row.lastReturnCode)&&String(row.returnedAt||row.updatedAt||'')>String(old.returnedAt||old.updatedAt||'')))legacy[key]={...row,contract,city:row.city||row.cityLabel||'',cityLabel:row.cityLabel||CITY_LABELS[city]||'Sem cidade'};
          }
        }
      }
      if(Object.keys(revisions).length!==13)throw Error('Escopo de bases incompleto');
      state.revisions=revisions;state.clean106ByCity=clean;state.clean106MetaByCity=meta;state.claroRecords=claro;state.claroUpdatedAt=latestDate;state.legacySent=legacy;
      state.clean106Contracts=clean[getSelectedCityKey()]||[];
      state.sharedReady=true;
    })();
    state.sharedLoading=promise;
    try{await promise;}finally{if(state.sharedLoading===promise)state.sharedLoading=null;}
  }
  async function putShared(profile,kind,records,source_name) {
    if(!state.sharedReady)throw Error('Atualize as bases antes de importar');
    const result=await dominiumCall(SHARED_API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'put',profile,kind,records,source_name:source_name.slice(0,200),expected_revision:state.revisions[profile+':'+kind]||0})});
    if(result?.ok!==true)throw Error('Gravação não confirmada');
    state.revisions[profile+':'+kind]=result.revision;
    return result;
  }
  async function importLegacyHistory(event) {
    const input=event.target,file=input.files?.[0];if(!file)return;
    try{
      if(file.size>32*1024*1024)throw Error('Arquivo acima do limite');
      const data=JSON.parse(await file.text());
      if(data.schema!=='fora-rota-legacy-export-v1'||!Array.isArray(data.firestoreSent)||!Array.isArray(data.cloudflareSent))throw Error('Exportação inválida');
      if(!await refreshSentTracking())return;
      if(!window.confirm('Importar os retornos deste arquivo? O histórico já existente será preservado.'))return;
      const groups=Object.fromEntries([...profileKeys,'unassigned'].map(p=>[p,new Map()]));
      for(const row of [...data.firestoreSent,...data.cloudflareSent]){
        const contract=normalizeContract(row.contract);if(!contract)throw Error('Contrato inválido no histórico');
        const profile=operationalProfile(row.city||row.cityLabel)||'unassigned';
        const key=contract, prev=groups[profile].get(key);
        if(prev&&prev.lastReturnCode&&row.lastReturnCode&&String(prev.lastReturnCode)!==String(row.lastReturnCode)&&String(prev.returnedAt||'')===String(row.returnedAt||''))throw Error('Conflito de retorno no arquivo');
        const newer=!prev||String(row.returnedAt||row.updatedAt||'')>=String(prev.returnedAt||prev.updatedAt||'');
        const best=(!prev||(!prev.lastReturnCode&&row.lastReturnCode)||(newer&&(!prev.lastReturnCode||row.lastReturnCode)))?row:prev;
        const history=new Map([...(prev?.returnHistory||[]),...(row.returnHistory||[])].map(h=>[JSON.stringify(h),h]));
        groups[profile].set(key,{...prev,...best,contract,returnHistory:[...history.values()]});
      }
      for(const [profile,records] of Object.entries(groups))if(records.size)await putShared(profile,'legacy_sent',[...records.values()],file.name);
      await refreshSentTracking();setStatus('Histórico do legado atualizado. Nenhuma OS foi baixada.','success');
    }catch(error){setStatus('Importação de histórico: '+error.message,'error');}
    finally{input.value='';}
  }

  async function saveSavedState() { throw Error('Use a gravação de bases compartilhadas'); }

  async function saveClaroState() { throw Error('Use a gravação de bases compartilhadas'); }



  function findSheetWithHeaders(workbook, requiredHeaders) {
    for (const name of workbook.SheetNames) {
      const rows = XLSX.utils.sheet_to_json(workbook.Sheets[name], {
        header: 1,
        defval: '',
        raw: true,
        blankrows: false,
      });
      const headerIndex = findHeaderRow(rows, requiredHeaders);
      if (headerIndex !== -1) return { name, rows, headerIndex };
    }
    return null;
  }

  function findHeaderRow(rows, requiredHeaders) {
    const normalizedRequiredHeaders = requiredHeaders.map(normalizeText).filter(Boolean);
    for (let index = 0; index < Math.min(rows.length, 60); index += 1) {
      const line = rows[index].map(normalizeText).filter(Boolean);
      if (normalizedRequiredHeaders.every((required) => line.some((cell) => headerMatches(cell, required)))) {
        return index;
      }
    }
    return -1;
  }

  function buildHeaderMap(headerRow) {
    const map = new Map();
    headerRow.forEach((header, index) => {
      const normalized = normalizeText(header);
      if (!normalized) return;
      if (!map.has(normalized)) map.set(normalized, []);
      map.get(normalized).push(index);
    });
    return map;
  }

  function pick(row, headerMap, candidates) {
    const normalizedCandidates = candidates.map(normalizeText).filter(Boolean);

    for (const candidate of normalizedCandidates) {
      const indexes = headerMap.get(candidate) || [];
      for (const index of indexes) {
        const value = stringValue(row[index]);
        if (value) return value;
      }
    }

    for (const normalizedCandidate of normalizedCandidates) {
      for (const [header, indexes] of headerMap.entries()) {
        if (!headerMatches(header, normalizedCandidate)) continue;
        for (const index of indexes) {
          const value = stringValue(row[index]);
          if (value) return value;
        }
      }
    }
    return '';
  }

  function mergeEquipmentField(current, incoming) {
    const currentText = stringValue(current);
    const nextText = stringValue(incoming);
    if (!nextText) return currentText;
    if (!currentText) return nextText;

    const existing = new Set(
      currentText
        .split(' || ')
        .map((part) => normalizeText(part))
        .filter(Boolean)
    );
    if (existing.has(normalizeText(nextText))) return currentText;
    return `${currentText} || ${nextText}`;
  }

  function extractCepFromText(value) {
    const match = stringValue(value).match(/\b\d{5}-?\d{3}\b/);
    return match ? match[0] : '';
  }

  function extractAgendaFromDx22Text(value) {
    const match = stringValue(value).match(/\b\d{2}\/\d{2}\/\d{4}\s*\((\d{2}:\d{2}\s*-\s*\d{2}:\d{2})\)/i);
    return match ? match[1].replace(/\s+/g, ' ').trim() : '';
  }

  function headerMatches(header, candidate) {
    if (!header || !candidate) return false;
    return header === candidate || header.includes(candidate);
  }

  function splitPhones(value) {
    return stringValue(value)
      .split(/[\/;,|_]+/)
      .flatMap(splitPhoneToken)
      .filter((phone) => phone.length >= 8);
  }

  function splitPhoneToken(value) {
    let digits = stringValue(value).replace(/\D+/g, '');
    if (!digits) return [];
    if ((digits.length === 12 || digits.length === 13) && digits.startsWith('55')) {
      digits = digits.slice(2);
    }
    if (digits.length <= 11) return [digits];

    const phones = [];
    let cursor = 0;
    while (cursor < digits.length) {
      const remaining = digits.length - cursor;
      if (remaining < 8) break;
      const thirdDigit = digits[cursor + 2];
      const size = thirdDigit === '9' && remaining >= 11 ? 11 : remaining >= 10 ? 10 : remaining;
      phones.push(digits.slice(cursor, cursor + size));
      cursor += size;
    }

    return phones;
  }

  function normalizePhoneWithDdd(value, ddd) {
    const digits = stringValue(value).replace(/\D+/g, '');
    if ((digits.length === 8 || digits.length === 9) && /^\d{2}$/.test(ddd)) return `${ddd}${digits}`;
    return digits;
  }

  function unique(items) {
    return [...new Set(items.filter(Boolean))];
  }

  function chunkArray(items, size) {
    const chunks = [];
    for (let index = 0; index < items.length; index += size) {
      chunks.push(items.slice(index, index + size));
    }
    return chunks;
  }

  function compareContract(a, b) {
    return String(a).localeCompare(String(b), 'pt-BR', { numeric: true });
  }

  function normalizeContract(value) {
    const digits = stringValue(value).replace(/\D+/g, '');
    return digits.length >= 5 ? digits : '';
  }

  function extractSafraContract(baseCdnetValue, fallbackValue = '') {
    const baseCdnet = stringValue(baseCdnetValue);
    if (baseCdnet) {
      const suffix = baseCdnet.includes('_') ? baseCdnet.slice(baseCdnet.lastIndexOf('_') + 1) : baseCdnet;
      const contract = normalizeContract(suffix);
      if (contract) return contract;
    }
    return normalizeContract(fallbackValue);
  }

  function normalizeCode(value) {
    return stringValue(value).replace(/\D+/g, '');
  }

  function parseImperiumHistoryTimestamp(value) {
    const text = stringValue(value);
    if (!text) return 0;
    const match = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?/);
    if (!match) return 0;
    const [, dayRaw, monthRaw, yearRaw, hourRaw = '0', minuteRaw = '0'] = match;
    const year = Number(yearRaw.length === 2 ? `20${yearRaw}` : yearRaw);
    const month = Number(monthRaw) - 1;
    const day = Number(dayRaw);
    const hour = Number(hourRaw);
    const minute = Number(minuteRaw);
    const time = new Date(year, month, day, hour, minute).getTime();
    return Number.isFinite(time) ? time : 0;
  }

  function normalizeDisplay(value) {
    return stringValue(value).replace(/\s+/g, ' ').trim().toUpperCase();
  }

  function normalizeText(value) {
    return stringValue(value)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  function stringValue(value) {
    if (value == null) return '';
    return String(value).trim();
  }

  function escapeHtml(value) {
    return stringValue(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function setFileBadge(target, text, hasFile) {
    if (!target) return;
    target.textContent = text;
    target.closest('.drop-card')?.classList.toggle('has-file', hasFile);
  }

  function setStatus(message, type = '') {
    if (!els.status) return;
    els.status.textContent = message;
    const trackingStatus=document.getElementById('foraRotaTrackingStatus');
    if(trackingStatus){trackingStatus.textContent=message;trackingStatus.className=('status-line '+type).trim();}
    els.status.className = `status-line ${type}`.trim();
  }

  function formatShortDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  if (typeof window !== 'undefined' && window.__DOMINIUM_FORA_ROTA_TEST__) {
    globalThis.DominiumForaRotaTestHooks = {
      parseClaroBacklog, parseImperiumBacklog, buildClean106Contracts,
      normalizeContract, extractSafraContract, normalizeText, state, els,
      markSelectedAsSent, availableRecordsForBairro, recordWasSent,
      isSupportedOperationalCity, splitPhones, loadSharedState, refreshSentTracking, operationalProfile, putShared, populateNeighborhoods
    };
  }
})();
