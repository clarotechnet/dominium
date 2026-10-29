const crypto = require('crypto');

const PROJECT_ID = 'IMPERIUM_OLLAMA';
const NATAL_CHAT_ID = '120363028547806621@g.us';
const FORTALEZA_CHAT_ID = '120363397790697942@g.us';
const MOSSORO_CHAT_ID = '120363420013377509@g.us';
const RECIFE_CHAT_ID = '120363425385335332@g.us';
const ALLOWED_CODES = new Set([
  '409', '430', '511', '512', '706',
]);
const KNOWN_NON_AUTOMATIC_CODES = new Set([
  '101', '106', '125', '301', '306', '312', '404', '479',
]);
const KNOWN_CLOSE_CODES = new Set([
  ...ALLOWED_CODES,
  ...KNOWN_NON_AUTOMATIC_CODES,
]);
const CHAT_SCOPES = Object.freeze({
  [NATAL_CHAT_ID]: Object.freeze({ import_origin: 'NTL', city: 'NATAL', profile_key: 'natal', toa_cities: new Set(['NATAL', 'PARNAMIRIM']) }),
  [FORTALEZA_CHAT_ID]: Object.freeze({ import_origin: 'FTZ', city: 'FORTALEZA', profile_key: 'fortaleza', toa_cities: new Set(['FORTALEZA']) }),
  [MOSSORO_CHAT_ID]: Object.freeze({ import_origin: 'MRO', city: 'MOSSORO', profile_key: 'mossoro', toa_cities: new Set(['MOSSORO', 'MOSSORÓ']) }),
  [RECIFE_CHAT_ID]: Object.freeze({ import_origin: 'JCR', city: 'RECIFE', profile_key: 'recife', toa_cities: new Set(['RECIFE', 'PERNAMBUCO']) }),
});

function scopeForChat(chatId) {
  return CHAT_SCOPES[String(chatId || '')] || null;
}

function normalizeProfileCity(profileKey, value) {
  const city = String(value || '').trim().toUpperCase();
  const scope = Object.values(CHAT_SCOPES).find((item) => item.profile_key === profileKey);
  return scope?.toa_cities.has(city) ? scope.city : city;
}

class DisconnectPilotError extends Error {
  constructor(blockers) {
    const unique = [...new Set((blockers || []).filter(Boolean))];
    super(unique.join(', '));
    this.blockers = unique;
  }
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonical(value[key])])
    );
  }
  return value;
}

function sha256(value) {
  // Igual a disconnect_contracts.canonical_hash no OLLAMA: até strings são
  // serializadas como JSON antes do SHA-256.
  const serialized = JSON.stringify(canonical(value)).replace(
    /[\u007f-\uffff]/g,
    (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`
  );
  return crypto
    .createHash('sha256')
    .update(serialized)
    .digest('hex');
}

function cleanObservation(value) {
  return String(value || '')
    .replace(/^[\s:;,|\-\u2013\u2014]+/, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 2000);
}

function observationKey(value) {
  return cleanObservation(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function extractTOATaskObservation(value) {
  const automaticPatterns = [
    /^\[?(?:re)?agendamento para\b/,
    /\bfeito por ops\$/,
    /^baixa realizada com sucesso\b/,
    /^tarefa \d+\s*:\s*baixa realizada com sucesso\b/,
    /^movimentacoes da ultima solicitacao de encerramento\b/,
    /^sem movimentacao de equipamentos\b/,
    /\bgerada automaticamente pela baixa\b/,
  ];
  const unique = new Map();
  for (const part of String(value || '').split(/\s*\|\s*/)) {
    const cleaned = cleanObservation(part);
    const key = observationKey(cleaned);
    if (!key || automaticPatterns.some((pattern) => pattern.test(key))) continue;
    if (!unique.has(key)) unique.set(key, cleaned);
  }
  return cleanObservation([...unique.values()].join(' | '));
}

const FORA_ROTA_PATTERN = /\b(?:FR|FRT|FRTA|F[\s._\/-]*R[\s._\/-]*T(?:A)?|FORA(?:[\s._\/-]+DA)?[\s._\/-]*ROTA|FORA[\s._\/-]*R|F[\s._\/-]*ROTA)\b/i;

function extractObservation(source, contract, closeCode) {
  let remainder = String(source || '');
  if (contract) {
    remainder = remainder.replace(
      new RegExp(`(?<!\\d)${String(contract)}(?!\\d)`),
      ' '
    );
  }
  if (closeCode) {
    remainder = remainder.replace(
      new RegExp(`(?<!\\d)${String(closeCode)}(?!\\d)`),
      ' '
    );
  }
  remainder = remainder.replace(FORA_ROTA_PATTERN, ' ');
  return cleanObservation(remainder);
}

function parseDisconnectFollowUp(text) {
  const source = String(text || '');
  const allowedPattern = [...ALLOWED_CODES].join('|');
  const match = source.match(new RegExp(`^\\s*(${allowedPattern})(?!\\d)([\\s\\S]*)$`));
  if (!match) return null;
  const contracts = [...source.matchAll(/(?<!\d)(\d{7,9})(?!\d)/g)];
  if (contracts.length) return null;
  return Object.freeze({
    requested_close_code: match[1],
    observation: cleanObservation(match[2]),
  });
}

function parseDisconnectMessage({ messageId, chatId, senderId, receivedAt, text }) {
  const scope = scopeForChat(chatId);
  if (!scope) {
    throw new DisconnectPilotError(['unknown_whatsapp_group', 'operation_blocked']);
  }
  const source = String(text || '');
  if (/^\s*[!/]/.test(source)) {
    throw new DisconnectPilotError(['command_not_contract_message', 'operation_blocked']);
  }

  // Regra operacional DESC:
  // - contrato candidato tem de 7 a 9 digitos (Recife usa 9);
  // - codigo de baixa tem exatamente 3 digitos.
  // Isso impede telefone/serial de virar contrato e impede contrato+codigo
  // de serem tratados como um unico numero.
  const standaloneContracts = [...source.matchAll(/(?<![A-Za-z0-9])(\d{7,9})(?![A-Za-z0-9])/g)]
    .map((match) => match[1]);

  // Tolerancia para tecnico que cola sem separador:
  // - 3902235430 -> contrato 3902235 + codigo 430
  // - 4303902235 -> codigo 430 + contrato 3902235
  // So aceitamos exatamente 10 digitos e quando o bloco de 3 for um codigo conhecido.
  const compact = [];
  for (const match of source.matchAll(/(?<!\d)(\d{10})(?!\d)/g)) {
    const raw = match[1];
    if (KNOWN_CLOSE_CODES.has(raw.slice(7))) {
      compact.push({raw, contract:raw.slice(0,7), code:raw.slice(7)});
    }
    if (KNOWN_CLOSE_CODES.has(raw.slice(0,3))) {
      compact.push({raw, contract:raw.slice(3), code:raw.slice(0,3)});
    }
  }

  const contracts = [...new Set([...standaloneContracts,...compact.map(item=>item.contract)])];
  if (!contracts.length) {
    throw new DisconnectPilotError(['missing_contract', 'operation_blocked']);
  }
  if (contracts.length !== 1) {
    throw new DisconnectPilotError(['multiple_contracts', 'operation_blocked']);
  }

  // Endereços, agenda e quantidades têm números. Só ler código próximo
  // do contrato, em linha própria ou com marcador explícito.
  const standaloneCodes = [];
  const patterns = [
    /\b(?:c[oó]d(?:igo)?\.?(?:\s+de\s+baixa)?|motivo|bx)\s*[:.\-]?\s*(\d{3})(?!\d)/gi,
    /^\s*(\d{3})\s*$/gm,
    new RegExp(`(?<!\\d)${contracts[0]}[\\s:|/–—-]+(\\d{3})(?!\\d)`, 'g'),
    new RegExp(`(?<!\\d)(\\d{3})[\\s:|/–—-]+${contracts[0]}(?!\\d)`, 'g'),
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) standaloneCodes.push(match[1]);
  }

  const closeCodeTokens = [
    ...standaloneCodes,
    ...compact.map(item=>item.code),
  ];
  const uniqueCloseCodeTokens = [...new Set(closeCodeTokens)];
  if (uniqueCloseCodeTokens.length > 1) {
    throw new DisconnectPilotError(['message_format_invalid', 'operation_blocked']);
  }
  const explicitCloseCode = uniqueCloseCodeTokens[0] || '';
  const codes = explicitCloseCode && ALLOWED_CODES.has(explicitCloseCode)
    ? [explicitCloseCode]
    : [];
  const unsupportedCode = explicitCloseCode && !ALLOWED_CODES.has(explicitCloseCode)
    ? explicitCloseCode
    : '';
  if (!messageId || !senderId || !receivedAt) {
    throw new DisconnectPilotError(['message_identity_missing', 'operation_blocked']);
  }
  const requestedCode = codes[0] || null;
  return Object.freeze({
    schema_version: 1,
    project_id: PROJECT_ID,
    message_id: String(messageId),
    chat_id: chatId,
    sender_id: String(senderId),
    received_at: String(receivedAt),
    raw_text: source,
    // Candidato único; TOA, técnico e bucket ainda precisam confirmá-lo.
    contract: contracts[0],
    requested_close_code: requestedCode,
    unsupported_close_code: unsupportedCode || '',
    observation: extractObservation(
      compact.reduce((text,item)=>text.replace(item.raw, ' '),source),
      contracts[0],
      codes[0] || unsupportedCode || ''
    ),
    import_origin: scope.import_origin,
    city: scope.city,
    profile_key: scope.profile_key,
  });
}

function assertAfterActivation(event, cursor) {
  if (!cursor?.pilot_started_at || !cursor?.activation_cursor) {
    throw new DisconnectPilotError(['pilot_not_activated', 'operation_blocked']);
  }
  const received = Date.parse(event.received_at);
  const started = Date.parse(cursor.pilot_started_at);
  if (!Number.isFinite(received) || !Number.isFinite(started)) {
    throw new DisconnectPilotError(['timestamp_invalid', 'operation_blocked']);
  }
  if (received <= started) {
    throw new DisconnectPilotError(['message_before_pilot_activation', 'operation_blocked']);
  }
  if (
    cursor.last_processed_message_id === event.message_id &&
    cursor.last_processed_message_timestamp === event.received_at
  ) {
    throw new DisconnectPilotError(['duplicate_message', 'operation_blocked']);
  }
  return true;
}

function buildTOADisconnectLookup(event, { jobId, timeoutMs = 240000 } = {}) {
  const created = new Date();
  return Object.freeze({
    job_id: String(jobId || crypto.randomUUID()),
    job_type: 'DISCONNECT_ACTIVITY_LOOKUP',
    message_id: event.message_id,
    chat_id: event.chat_id,
    sender_id: event.sender_id,
    contract: event.contract,
    requested_close_code: event.requested_close_code || '',
    expected_city: event.city,
    expected_profile_key: event.profile_key,
    created_at: created.toISOString(),
    timeout_at: new Date(created.getTime() + timeoutMs).toISOString(),
    retry_count: 0,
  });
}

function normalizeSnapshotEquipment(values, direction) {
  if (!Array.isArray(values)) return [];
  return values.map((item) => {
    const serial = String(item?.serial || '').toUpperCase().replace(/[^A-Z0-9]+/g, '');
    const equipmentType = String(item?.equipment_type || '').trim();
    if (!serial || !equipmentType) {
      throw new DisconnectPilotError(['equipment_identity_mismatch', 'operation_blocked']);
    }
    return {
      serial,
      equipment_type: equipmentType,
      direction,
    };
  });
}

function isServiceWithoutMaterial(value) {
  const normalized = String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase();
  return normalized.includes('SERVICO SEM MATERIAL');
}

function assertExactInventoryPools(snapshot) {
  if (String(snapshot?.direction_source || '') !== 'oracle_inventory_pool') return;
  const checks = [
    ['installed_equipments', 'install'],
    ['added_equipments', 'install'],
    ['removed_equipments', 'deinstall'],
  ];
  for (const [field, expectedPool] of checks) {
    const values = Array.isArray(snapshot?.[field]) ? snapshot[field] : [];
    for (const item of values) {
      const actualPool = String(item?.inventory_pool || item?.pool || '').toLowerCase();
      if (actualPool !== expectedPool) {
        throw new DisconnectPilotError([
          'equipment_direction_mismatch',
          'operation_blocked',
        ]);
      }
    }
  }
}

function buildTypedTOASnapshot(event, toaJob, snapshot) {
  const identity = {
    project_id: PROJECT_ID,
    profile_key: String(snapshot?.profile_key || '').toLowerCase(),
    city: normalizeProfileCity(event.profile_key, snapshot?.city),
    contract: String(snapshot?.contract || '').replace(/\D+/g, ''),
    activity_id: String(snapshot?.activity_id || ''),
  };
  const source = {
    ...identity,
    activity_type: String(snapshot?.activity_type || ''),
    activity_status: String(snapshot?.activity_status || snapshot?.status || ''),
    current_close_code: String(snapshot?.current_close_code || '') || null,
    observation: extractTOATaskObservation(
      snapshot?.task_observation ||
      snapshot?.activity_observation ||
      snapshot?.observation
    ),
    installed_equipments: normalizeSnapshotEquipment(
      snapshot?.installed_equipments,
      'incoming'
    ),
    removed_equipments: normalizeSnapshotEquipment(
      snapshot?.removed_equipments,
      'outgoing'
    ),
    added_equipments: normalizeSnapshotEquipment(
      snapshot?.added_equipments,
      'incoming'
    ),
    materials: (Array.isArray(snapshot?.materials) ? snapshot.materials : [])
      .map((item) => String(item || '').trim())
      .filter((item) => item && !isServiceWithoutMaterial(item)),
    unknown_equipments: normalizeSnapshotEquipment(
      snapshot?.unknown_equipments,
      'incoming'
    ),
    materials_complete: snapshot?.materials_complete === true,
    direction_source: String(snapshot?.direction_source || ''),
    installer_id: String(
      snapshot?.installer_id ||
      snapshot?.technician_external_id ||
      snapshot?.assigned_technician?.external_id ||
      ''
    ),
    task_os_numbers: [...new Set(
      (Array.isArray(snapshot?.tasks) ? snapshot.tasks : [])
        .map((task) => String(task?.os_number || '').trim())
        .filter((value) => /^\d+$/.test(value))
    )],
    technician_name: String(
      snapshot?.responsibility?.route_provider?.name ||
      snapshot?.responsibility?.inventory_providers?.[0]?.name ||
      snapshot?.responsibility?.assigned_technician?.name ||
      snapshot?.technician_name ||
      ''
    ).trim(),
    technician_login: String(
      snapshot?.responsibility?.route_provider?.external_id ||
      snapshot?.responsibility?.inventory_providers?.[0]?.external_id ||
      snapshot?.responsibility?.assigned_technician?.external_id ||
      snapshot?.technician_external_id ||
      ''
    ).trim().toUpperCase(),
    source_reference: (
      String(snapshot?.source_reference || 'toa-extension-direct')
      + '|bucket=' + String(snapshot?.bucket || snapshot?.route_bucket || '').trim().toUpperCase()
    ),
  };
  const statePayload = { ...source };
  delete statePayload.source_reference;
  return {
    ...source,
    fetched_at: String(snapshot?.fetched_at || new Date().toISOString()),
    source_hash: sha256(source),
    state_hash: sha256(statePayload),
    job_id: toaJob.job_id,
    message_id: event.message_id,
    group_id: event.chat_id,
    processing_id: event.message_id,
  };
}

function buildDisconnectJob(event, toaJob, snapshot, { ttlMs = 300000 } = {}) {
  if (!snapshot || typeof snapshot !== 'object') {
    throw new DisconnectPilotError(['toa_snapshot_missing', 'operation_blocked']);
  }
  if (
    String(snapshot.job_id || '') !== toaJob.job_id ||
    String(snapshot.contract || '') !== event.contract
  ) {
    throw new DisconnectPilotError(['toa_job_correlation_mismatch', 'operation_blocked']);
  }
  const activityId = String(snapshot.activity_id || '');
  if (!activityId) {
    throw new DisconnectPilotError(['missing_activity_id', 'operation_blocked']);
  }
  if (normalizeProfileCity(event.profile_key, snapshot.city) !== event.city) {
    throw new DisconnectPilotError(['city_scope_mismatch', 'operation_blocked']);
  }
  if (String(snapshot.profile_key || '').toLowerCase() !== event.profile_key) {
    throw new DisconnectPilotError(['profile_scope_mismatch', 'operation_blocked']);
  }
  assertExactInventoryPools(snapshot);
  const incomingCount = (
    (Array.isArray(snapshot.installed_equipments) ? snapshot.installed_equipments.length : 0) +
    (Array.isArray(snapshot.added_equipments) ? snapshot.added_equipments.length : 0)
  );
  const outgoingCount = Array.isArray(snapshot.removed_equipments)
    ? snapshot.removed_equipments.length
    : 0;
  const inferredCloseCode = incomingCount > 0
    ? '409'
    : (outgoingCount > 0 ? '430' : '');
  if (!inferredCloseCode && !event.requested_close_code) {
    throw new DisconnectPilotError([
      'equipment_identity_mismatch',
      'operation_blocked',
    ]);
  }
  const requestedCloseCode = event.requested_close_code || inferredCloseCode;
  const typedSnapshot = buildTypedTOASnapshot(event, toaJob, snapshot);
  const created = new Date();
  const snapshotHash = typedSnapshot.state_hash;
  const idempotencyKey = sha256(
    PROJECT_ID +
    event.chat_id +
    event.message_id +
    event.contract +
    activityId +
    requestedCloseCode
  );
  return Object.freeze({
    schema_version: 1,
    project_id: PROJECT_ID,
    job_id: toaJob.job_id,
    idempotency_key: idempotencyKey,
    message_id: event.message_id,
    chat_id: event.chat_id,
    sender_id: event.sender_id,
    received_at: event.received_at,
    contract: event.contract,
    requested_close_code: requestedCloseCode,
    observation: String(event.observation || ''),
    import_origin: event.import_origin,
    city: event.city,
    profile_key: event.profile_key,
    activity_id: activityId,
    toa_snapshot: canonical(typedSnapshot),
    toa_snapshot_hash: snapshotHash,
    created_at: created.toISOString(),
    expires_at: new Date(created.getTime() + ttlMs).toISOString(),
  });
}

function buildWhatsAppCreationJob(event, toaJob, reason = 'toa_sem_resultados') {
  if (!event?.requested_close_code) {
    throw new DisconnectPilotError(['missing_close_code', 'operation_blocked']);
  }
  const digest = sha256({
    chat_id: event.chat_id,
    message_id: event.message_id,
    contract: event.contract,
  });
  const numeric = BigInt(`0x${digest.slice(0, 16)}`) % 1000000000n;
  const activityId = `9${numeric.toString().padStart(9, '0')}`;
  const baseJob = buildDisconnectJob(event, toaJob, {
    job_id: toaJob.job_id,
    contract: event.contract,
    activity_id: activityId,
    activity_type: 'CRIACAO MANUAL WHATSAPP',
    status: 'not_found',
    city: event.city,
    profile_key: event.profile_key,
    current_close_code: event.requested_close_code,
    installed_equipments: [],
    removed_equipments: [],
    added_equipments: [],
    unknown_equipments: [],
    materials: [],
    materials_complete: true,
    direction_source: 'whatsapp_sender_toa_not_found',
    tasks: [{ os_number: activityId }],
    technician_name: '',
    technician_login: '',
    source_reference: 'whatsapp_sender_toa_not_found',
  });
  return Object.freeze({
    ...baseJob,
    creation_only: true,
    creation_reason: String(reason || 'toa_sem_resultados'),
  });
}

function buildSuccessReaction(job, result) {
  if (
    result?.state !== 'completed' ||
    result?.os_confirmed !== true ||
    result?.equipments_confirmed !== true
  ) {
    throw new DisconnectPilotError(['success_not_confirmed', 'operation_blocked']);
  }
  return Object.freeze({
    chat_id: job.chat_id,
    message_id: job.message_id,
    emoji: '✅',
    job_id: job.job_id,
  });
}

module.exports = {
  PROJECT_ID,
  NATAL_CHAT_ID,
  FORTALEZA_CHAT_ID,
  MOSSORO_CHAT_ID,
  RECIFE_CHAT_ID,
  CHAT_SCOPES,
  scopeForChat,
  normalizeProfileCity,
  DisconnectPilotError,
  cleanObservation,
  extractObservation,
  extractTOATaskObservation,
  parseDisconnectFollowUp,
  parseDisconnectMessage,
  assertAfterActivation,
  buildTOADisconnectLookup,
  buildTypedTOASnapshot,
  buildDisconnectJob,
  buildWhatsAppCreationJob,
  buildSuccessReaction,
  sha256,
};
