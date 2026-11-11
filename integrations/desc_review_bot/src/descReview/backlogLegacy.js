'use strict';
// Read-only adapter: Matheus's Backlog/Imperium historical comparison is evidence,
// never authority to create or close an OS. Keep its importer/UI untouched.
const {buildPlan, resolveAtlas, serial} = require('./core');

const VALID_PROFILES = new Set(['natal', 'fortaleza', 'mossoro', 'recife']);
const TERMINAL_CODES = new Set(['101', '106', '125', '306', '312', '404', '409', '430', '512', '706']);
const TOO_OLD_MS = 300000;
const normalize = value => String(value ?? '').normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
const digits = value => typeof value === 'string' ? value.trim() : '';
const fresh = (value, now) => {
  if (typeof value !== 'string') return false;
  const ms = Date.parse(value);
  return Number.isFinite(ms) && ms <= now + 30000 && now - ms <= TOO_OLD_MS;
};

function historyForContract(rows, contract, profile) {
  if (!Array.isArray(rows)) return [];
  // The annual history may include repeated attempts/OS records. Retain them;
  // never treat the first historical close as the current state of the OS.
  return rows.filter(row => row && typeof row === 'object' &&
      digits(row.contract) === contract &&
      (!row.profile_key || row.profile_key === profile) &&
      (!row.profile || row.profile === profile))
    .map(row => ({
      code: String(row.historical_code ?? row.code ?? '').trim(),
      date: String(row.historical_date ?? row.activity_date ?? '').trim(),
      classification: String(row.classification ?? '').trim(),
      os_number: String(row.os_number ?? '').trim(),
      source: String(row.route_file ?? row.source ?? '').trim().slice(0, 160)
    }));
}

function prepareBacklogDescReview(input, now = Date.now()) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return {state:'blocked', blockers:['Dados de backlog inválidos'], executed:false};
  }
  const contract = digits(input.contract);
  const profile = String(input.profile ?? '').toLowerCase().trim();
  const blockers = [], warnings = [];
  if (!/^\d{7}$/.test(contract)) blockers.push('Contrato deve ter exatamente 7 dígitos');
  if (!VALID_PROFILES.has(profile)) blockers.push('Cidade do contrato não confirmada');

  const history = historyForContract(input.historicalRows, contract, profile);
  if (history.length) warnings.push('Histórico do Imperium encontrado: não é prova de uma nova O.S. aberta');
  if (history.some(row => row.code && !TERMINAL_CODES.has(row.code))) {
    warnings.push('Histórico contém código não identificado; revisar antes de criar O.S.');
  }

  const toa = input.toaLookup;
  if (toa?.status === 'found' && toa.ok === true && fresh(toa.checked_at, now)) {
    return {
      state:'use_toa',contract,profile,history,warnings,
      blockers,create_os:false,executed:false,
      reason:'TOA atual encontrado: usar a rotina de baixa TOA, nunca criar outra O.S.'
    };
  }
  if (toa?.ok !== true || toa.status !== 'not_found' ||
      toa.contract !== contract || toa.profile_key !== profile ||
      !fresh(toa.checked_at, now)) {
    blockers.push('TOA não confirmou ausência do contrato em consulta atual');
  }

  const evidence = input.imperium;
  if (!evidence || evidence.ok !== true || evidence.confirmed !== true ||
      evidence.searched !== true || evidence.contract !== contract ||
      evidence.profile_key !== profile || !fresh(evidence.checked_at, now) ||
      !Array.isArray(evidence.orders)) {
    blockers.push('Imperium: consulta atual do contrato não confirmada');
  } else if (evidence.orders.length) {
    blockers.push('Imperium: já existe O.S. aberta; selecionar essa O.S. antes de criar outra');
  } else if (evidence.source !== 'open_orders_no_match') {
    blockers.push('Imperium: resposta sem O.S. aberta não foi confirmada pelo leitor');
  }

  // A contract absent from the *imported routes* alone is never proof it is
  // absent from live TOA. A route containing it conflicts with a no-TOA claim.
  if (Array.isArray(input.routeRows) && input.routeRows.some(row =>
      row && digits(row.contract) === contract)) {
    blockers.push('Contrato presente em rota importada; conferir a divergência com TOA ao vivo');
  }

  const photos = Array.isArray(input.photos) ? input.photos : [];
  const photographed = new Set();
  for (const photo of photos) {
    const s = serial(photo?.serial);
    if (!s || photo?.verified_label !== true ||
        typeof photo?.message_id !== 'string' || !photo.message_id.trim() ||
        digits(photo?.contract) !== contract) {
      blockers.push('Foto/legenda sem serial e contrato comprovados');
      continue;
    }
    if (photographed.has(s)) blockers.push('Serial duplicado entre as fotos');
    photographed.add(s);
  }
  if (!photographed.size) blockers.push('Aguardando foto do equipamento com serial legível');

  const atlas = Array.isArray(input.atlas) ? input.atlas : [];
  const linked = new Set();
  for (const entry of atlas) {
    try {
      const item = resolveAtlas(entry);
      if (item.contract !== contract || !photographed.has(item.serial)) {
        blockers.push('Atlas: serial da foto não pertence ao contrato informado');
      } else if (linked.has(item.serial)) {
        blockers.push('Atlas: consulta duplicada do mesmo serial');
      } else linked.add(item.serial);
    } catch {
      blockers.push('Atlas: consulta de serial incompleta ou não comprovada');
    }
  }
  if (linked.size !== photographed.size) {
    blockers.push('Atlas: todos os seriais fotografados precisam corresponder ao contrato');
  }

  const technician = input.technician || {};
  const batch = {
    profile,contract,technician,atlas,
    requested_code:'430', // Only RETIRADA FORA TOA for legacy DESC
    require_imperium_verification:true,imperium:evidence,
    capture_errors:[],previously_seen:[],previously_seen_os:[],
    late_collection:false
  };
  const plan = buildPlan(batch, null, now);
  blockers.push(...plan.blockers);
  if (plan.operations.some(op =>
      op.code !== '430' || op.create_os !== true ||
      op.source !== 'WHATSAPP/ATLAS' ||
      op.materials.length !== 0 || op.incoming.length !== 0)) {
    blockers.push('Operação fora do protocolo RETIRADA FORA TOA 430; exige revisão');
  }
  if (!plan.operations.length || plan.operations.some(op => op.outgoing.some(item =>
      !linked.has(serial(item.serial))))) {
    blockers.push('Movimentações não conferem com as fotos e consultas do Atlas');
  }

  const unique = [...new Set(blockers)];
  return {
    state:unique.length?'blocked':'review',
    contract,profile,history,warnings,blockers:unique,
    create_os:unique.length===0,
    // Existing bulk_orders.py already generates this same number for a new OS.
    os_number_preview:unique.length===0?contract+' '+contract:null,
    service:unique.length===0?'RETIRADA FORA TOA':null,
    plan:unique.length===0?plan:null,
    executed:false,
    requires_human_approval:true,
    source:'BACKLOG_HISTORICO + WHATSAPP/ATLAS + IMPERIUM'
  };
}

module.exports={prepareBacklogDescReview,historyForContract};
