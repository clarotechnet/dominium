const fs = require('fs');
const path = require('path');

const {
  DisconnectPilotError,
  extractTOATaskObservation,
  parseDisconnectFollowUp,
  parseDisconnectMessage,
  assertAfterActivation,
  buildTOADisconnectLookup,
  buildDisconnectJob,
  buildWhatsAppCreationJob,
  buildSuccessReaction,
  scopeForChat,
  normalizeProfileCity,
  sha256,
} = require('./disconnectPilot');

// Recognized by the installed Imperium direct protocol; recognition alone does
// not authorize a write. Productive/unsupported codes still require preflight.
const SUPPORTED_CLOSE_CODES = new Set([
  '101', '106', '125', '306', '312', '404', '409', '430', '511', '512', '706',
]);
const AUTOMATIC_CLOSE_CODES = new Set(['409', '430', '706']);
const TOA_DEFINITIVE_NOT_FOUND = new Set([
  'toa_sem_resultados',
  'no_results',
  'toa_activity_not_found',
  // Extensão do TOA retornou resposta inválida/inesperada → trata como não encontrado
  // e tenta criar a OS com o técnico que enviou o contrato no grupo.
  'toa_resposta_busca_invalida',
]);
const RETRYABLE_BLOCKERS = new Set([
  'missing_close_code',
  'waiting_close_code',
  'toa_lookup_timeout',
  'toa_lookup_failed',
  'toa_sem_resultados',
  'no_results',
  'improductive_close_prerequisite_unavailable',
  'toa_template_detalhes_indisponivel',
  'toa_snapshot_missing',
  'toa_snapshot_incomplete',
  'toa_activity_not_complete',
  'toa_task_missing',
  'typed_toa_snapshot_required',
  'equipment_identity_mismatch',
  'equipment_direction_mismatch',
  'close_409_without_incoming_equipment',
  'close_430_without_outgoing_equipment',
  'disconnect_queue_publish_failed',
  'manual_os_creation_failed',
  'unsupported_close_code',
  'productive_close_protocol_unavailable',
  'productive_close_prerequisite_unavailable',
]);

function readJson(filePath, fallback = {}) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporary = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  fs.renameSync(temporary, filePath);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const DESC_BUCKETS = Object.freeze({
  natal: Object.freeze(['NTL-DMV_ADM', 'PWM-DMV_ADM']),
  fortaleza: Object.freeze(['FTZ-DMV_ADM']),
  recife: Object.freeze(['JCR-DMV_ADM']),
  mossoro: Object.freeze(['MRO-DMV']),
});
function assertDescSectorGroup(event, snapshot) {
  // Group and exact TOA bucket are both mandatory: _ADM differs from ADESAO.
  // e.g. a DESC technician can handle a numbered installation-type OS.
  const scope = scopeForChat(event?.chat_id);
  if (!scope || scope.profile_key !== event?.profile_key) {
    throw new DisconnectPilotError(['desc_group_not_authorized', 'operation_blocked']);
  }
  if (normalizeProfileCity(event.profile_key, snapshot?.city) !== scope.city ||
      String(snapshot?.profile_key || '').toLowerCase() !== scope.profile_key) {
    throw new DisconnectPilotError(['city_scope_mismatch', 'operation_blocked']);
  }
  const bucket=String(snapshot?.bucket || snapshot?.route_bucket || '').trim().toUpperCase();
  if (!DESC_BUCKETS[scope.profile_key]?.includes(bucket)) {
    throw new DisconnectPilotError(['toa_bucket_not_confirmed_as_desc', 'operation_blocked']);
  }
  if (!String(snapshot?.activity_id || '').trim() ||
      !String(snapshot?.activity_type || '').trim()) {
    throw new DisconnectPilotError(['toa_snapshot_missing', 'operation_blocked']);
  }
  return true;
}

function createDisconnectPilotCoordinator(options = {}) {
  const toaBridge = options.toaBridge;
  const queueClient = options.queueClient;
  const configPath = options.configPath;
  const statePath = options.statePath;
  const sleep = options.sleep || delay;
  const onBackgroundResult = typeof options.onBackgroundResult === 'function'
    ? options.onBackgroundResult
    : async () => {};
  const configuredAdminMentions = Array.isArray(options.adminMentions)
    ? options.adminMentions.filter(Boolean)
    : [];
  const pollIntervalMs = Math.max(100, Number(options.pollIntervalMs || 2000));
  const deliveryDedupMs = Math.max(1000, Number(options.deliveryDedupMs || 30000));
  const followUpWindowMs = Math.max(1000, Number(options.followUpWindowMs || 120000));
  const followUpGraceMs = Math.max(0, Number(options.followUpGraceMs ?? 1500));
  const retryDelayMs = Math.max(1000, Number(options.retryDelayMs || 5 * 60 * 1000));
  const pendingMaxAgeMs = Math.max(
    retryDelayMs,
    Number(options.pendingMaxAgeMs || 30 * 60 * 1000)
  );
  // Quantidade de repeticoes APOS a tentativa inicial.
  const pendingMaxAttempts = Math.max(1, Number(options.pendingMaxAttempts || 2));
  const retryScanIntervalMs = Math.max(
    1000,
    Number(options.retryScanIntervalMs || 30000)
  );
  const pendingRetryEnabled = options.pendingRetryEnabled !== false;
  const publishRetryDelaysMs = Array.isArray(options.publishRetryDelaysMs)
    ? options.publishRetryDelaysMs
    : [1000, 2000, 4000, 8000, 15000];
  const recentDeliveries = new Map();
  let processingTail = Promise.resolve();
  let retrySweepRunning = false;

  if (!toaBridge || !queueClient || !configPath || !statePath) {
    throw new Error('Coordenador de desconexao incompleto.');
  }

  function loadConfig() {
    return readJson(configPath, {});
  }

  function loadState() {
    const state = readJson(statePath, {
      completed: {}, pending: {}, manual_orders: {}, manual_review: {},
    });
    state.completed = state.completed || {};
    state.pending = state.pending || {};
    state.manual_orders = state.manual_orders || {};
    state.manual_review = state.manual_review || {};
    return state;
  }

  function operationDate(value) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return new Date().toISOString().slice(0, 10);
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Fortaleza', year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(date);
  }

  function manualOrderKey(event) {
    return [event.profile_key, event.contract, operationDate(event.received_at)].join('|');
  }

  function manualReviewKey(event) {
    return manualOrderKey(event);
  }

  function activeConfig(chatId) {
    const config = loadConfig();
    const configuredGroup = Array.isArray(config.groups)
      ? config.groups.find((group) => (
          group?.enabled === true && String(group.group_id || '') === chatId
        ))
      : null;
    const legacyNatalEnabled = (
      !Array.isArray(config.groups) && config.allowed_chat_id === chatId
    );
    if (
      config.pilot_enabled !== true ||
      config.execution_enabled !== true ||
      (!configuredGroup && !legacyNatalEnabled)
    ) {
      return null;
    }
    if (!config.pilot_started_at || !config.activation_cursor) {
      throw new DisconnectPilotError(['pilot_not_activated', 'operation_blocked']);
    }
    const adminMentions = (
      Array.isArray(config.admin_mentions) && config.admin_mentions.length
        ? config.admin_mentions
        : configuredAdminMentions
    );
    if (!adminMentions.length) {
      throw new DisconnectPilotError([
        'admin_configuration_missing',
        'operation_blocked',
      ]);
    }
    return { ...config, active_group: configuredGroup, admin_mentions: adminMentions };
  }

  function enqueue(task) {
    const current = processingTail.then(task, task);
    processingTail = current.catch(() => {});
    return current;
  }

  function savePending(event, input, reason = 'queued', previous = null) {
    const state = loadState();
    const now = new Date();
    const attempts = Number(previous?.attempts || 0) + (reason === 'queued' ? 0 : 1);
    state.pending[event.message_id] = {
      event,
      message_key: input?.messageKey || previous?.message_key || null,
      attempts,
      first_seen_at: previous?.first_seen_at || now.toISOString(),
      updated_at: now.toISOString(),
      next_retry_at: reason === 'queued'
        ? (previous?.next_retry_at || now.toISOString())
        : new Date(now.getTime() + retryDelayMs).toISOString(),
      last_reason: reason,
    };
    writeJsonAtomic(statePath, state);
    return state.pending[event.message_id];
  }

  function removePending(messageId) {
    const state = loadState();
    if (state.pending[messageId]) {
      delete state.pending[messageId];
      writeJsonAtomic(statePath, state);
    }
  }

  function moveToManualReview(event, input, reason, attempts) {
    const state = loadState();
    const key = manualReviewKey(event);
    state.manual_review[key] = {
      contract: event.contract,
      profile_key: event.profile_key,
      city: event.city,
      chat_id: event.chat_id,
      sender_id: event.sender_id,
      message_id: event.message_id,
      message_key: input?.messageKey || state.pending[event.message_id]?.message_key || null,
      first_seen_at: state.pending[event.message_id]?.first_seen_at || event.received_at,
      finalized_at: new Date().toISOString(),
      attempts: Number(attempts || 0),
      last_reason: String(reason || 'automatic_close_not_completed'),
      manual_order: state.manual_orders[manualOrderKey(event)] || null,
    };
    delete state.pending[event.message_id];
    writeJsonAtomic(statePath, state);
    console.log(
      `[DISCONNECT-PILOT] manual_review contract=${event.contract} ` +
      `reason=${reason} attempts=${attempts}`
    );
    return {
      consumed: true,
      state: 'manual_review',
      contract: event.contract,
      reason,
      attempts: Number(attempts || 0),
    };
  }

  function activePendingRecords(now = Date.now()) {
    const state = loadState();
    const active = [];
    let changed = false;
    for (const [messageId, record] of Object.entries(state.pending)) {
      const firstSeenAt = Date.parse(record?.first_seen_at || '');
      const ageMs = Number.isFinite(firstSeenAt) ? now - firstSeenAt : pendingMaxAgeMs + 1;
      const attempts = Number(record?.attempts || 0);
      if (ageMs > pendingMaxAgeMs || attempts > pendingMaxAttempts) {
        const event = record?.event || {};
        state.manual_review[manualReviewKey(event)] = {
          contract: event.contract || '',
          profile_key: event.profile_key || '',
          city: event.city || '',
          chat_id: event.chat_id || '',
          sender_id: event.sender_id || '',
          message_id: event.message_id || messageId,
          message_key: record?.message_key || null,
          first_seen_at: record?.first_seen_at || event.received_at || '',
          finalized_at: new Date(now).toISOString(),
          attempts,
          last_reason: ageMs > pendingMaxAgeMs ? 'retry_window_expired' : (record?.last_reason || 'retry_limit_reached'),
          manual_order: state.manual_orders[manualOrderKey(event)] || null,
        };
        delete state.pending[messageId];
        changed = true;
        console.log(
          `[DISCONNECT-PILOT] pending -> manual_review contract=${event.contract || '-'} ` +
          `reason=${record?.last_reason || '-'} attempts=${attempts} age_ms=${Math.max(0, ageMs)}`
        );
        continue;
      }
      active.push(record);
    }
    if (changed) writeJsonAtomic(statePath, state);
    return active;
  }

  function attachFollowUp(input) {
    const followUp = parseDisconnectFollowUp(input.text);
    if (!followUp) return null;
    const receivedAtMs = Date.parse(input.receivedAt);
    if (!Number.isFinite(receivedAtMs)) return null;
    const state = loadState();
    const candidates = Object.values(state.pending)
      .filter((record) => {
        const event = record?.event;
        const eventAtMs = Date.parse(event?.received_at || '');
        return (
          event?.chat_id === input.chatId &&
          event?.sender_id === input.senderId &&
          (!event.requested_close_code || event.requested_close_code === followUp.requested_close_code) &&
          Number.isFinite(eventAtMs) &&
          receivedAtMs >= eventAtMs &&
          receivedAtMs - eventAtMs <= followUpWindowMs
        );
      })
      .sort((left, right) => (
        Date.parse(right.event.received_at) - Date.parse(left.event.received_at)
      ));
    const record = candidates[0];
    if (!record) return null;
    const event = {
      ...record.event,
      raw_text: [record.event.raw_text, input.text].filter(Boolean).join('\n'),
      requested_close_code: followUp.requested_close_code,
      observation: followUp.observation,
    };
    state.pending[event.message_id] = {
      ...record,
      event,
      updated_at: new Date().toISOString(),
      last_reason: 'follow_up_attached',
    };
    writeJsonAtomic(statePath, state);
    console.log(
      `[DISCONNECT-PILOT] observacao anexada contract=${event.contract} ` +
      `code=${event.requested_close_code}`
    );
    return {
      consumed: true,
      state: 'follow_up_attached',
      contract: event.contract,
    };
  }

  function latestPendingEvent(event) {
    return loadState().pending[event.message_id]?.event || event;
  }

  function scheduleRetry(event, input, reason) {
    const state = loadState();
    const record = savePending(event, input, reason, state.pending[event.message_id]);
    if (record.attempts > pendingMaxAttempts) {
      return moveToManualReview(event, input, reason, record.attempts);
    }
    console.log(
      `[DISCONNECT-PILOT] pending contract=${event.contract} reason=${reason} ` +
      `retry=${record.attempts}/${pendingMaxAttempts} next=${record.next_retry_at}`
    );
    return {
      consumed: true,
      state: 'pending_retry',
      contract: event.contract,
      reason,
      retry: record.attempts,
      retries_allowed: pendingMaxAttempts,
      next_retry_at: record.next_retry_at,
    };
  }

  function isRetryable(error) {
    const blockers = Array.isArray(error?.blockers) ? error.blockers : [];
    return blockers.some((blocker) => RETRYABLE_BLOCKERS.has(String(blocker)));
  }

  async function waitForTOA(lookup) {
    const deadline = Date.parse(lookup.timeout_at);
    while (Date.now() < deadline) {
      const result = toaBridge.getDisconnectLookupResult(lookup.job_id);
      if (result) return result;
      await sleep(pollIntervalMs);
    }
    throw new DisconnectPilotError(['toa_lookup_timeout', 'operation_blocked']);
  }

  async function waitForOLLAMA(job) {
    const deadline = Date.parse(job.expires_at);
    while (Date.now() < deadline) {
      let response;
      try {
        response = await queueClient.result(job.job_id);
      } catch (error) {
        const status = Number(error?.status) || 0;
        console.error(
          `[DISCONNECT-PILOT] queue result failed job=${job.job_id} ` +
          `status=${status} type=${error?.name || 'Error'} ` +
          `cause=${error?.cause?.code || '-'}`
        );
        if (!status || status >= 500) {
          await sleep(pollIntervalMs);
          continue;
        }
        throw new DisconnectPilotError([
          'disconnect_queue_result_failed',
          'operation_blocked',
        ]);
      }
      if (response.ready === true) {
        if (!response.result || response.resultHash !== sha256(response.result)) {
          throw new DisconnectPilotError([
            'result_hash_mismatch',
            'operation_blocked',
          ]);
        }
        return response.result;
      }
      await sleep(pollIntervalMs);
    }
    throw new DisconnectPilotError(['disconnect_job_expired', 'operation_blocked']);
  }

  async function publishAndWait(job) {
    let published = false;
    for (let attempt = 0; attempt <= publishRetryDelaysMs.length; attempt += 1) {
      try {
        await queueClient.publish(job);
        published = true;
        break;
      } catch (error) {
        const status = Number(error?.status) || 0;
        console.error(
          `[DISCONNECT-PILOT] queue publish failed job=${job.job_id} ` +
          `attempt=${attempt + 1} status=${status} type=${error?.name || 'Error'}`
        );
        if (status > 0 && status < 500) {
          throw new DisconnectPilotError(['disconnect_job_rejected', 'operation_blocked']);
        }
        if (attempt >= publishRetryDelaysMs.length) {
          throw new DisconnectPilotError(['disconnect_queue_publish_failed', 'operation_blocked']);
        }
        await sleep(Math.max(0, Number(publishRetryDelaysMs[attempt]) || 0));
      }
    }
    if (!published) {
      throw new DisconnectPilotError(['disconnect_queue_publish_failed', 'operation_blocked']);
    }
    return waitForOLLAMA(job);
  }

  async function ensureManualOrder(event) {
    const key = manualOrderKey(event);
    const state = loadState();
    const existing = state.manual_orders[key];
    if (existing && ['os_created', 'os_already_open'].includes(existing.state)) {
      return existing;
    }
    const stableMessageId = `DESC-MANUAL-${sha256(key).slice(0, 24).toUpperCase()}`;
    const creationEvent = Object.freeze({
      ...event,
      message_id: stableMessageId,
      requested_close_code: '430',
      observation: 'RETIRADA FORA TOA - CRIADA AUTOMATICAMENTE PELO WHATSAPP',
    });
    const lookup = buildTOADisconnectLookup(creationEvent);
    const job = buildWhatsAppCreationJob(creationEvent, lookup, 'whatsapp_desc_anchor');
    let result;
    try {
      result = await publishAndWait(job);
    } catch (error) {
      console.error(`[DISCONNECT-PILOT] manual OS failed contract=${event.contract}: ${error.message}`);
      throw new DisconnectPilotError(['manual_os_creation_failed', 'operation_blocked']);
    }
    if (
      !['os_created', 'os_already_open'].includes(String(result?.state || '')) ||
      result?.os_confirmed !== true
    ) {
      throw new DisconnectPilotError(['manual_os_creation_failed', 'operation_blocked']);
    }
    const fresh = loadState();
    fresh.manual_orders[key] = {
      state: result.state,
      contract: event.contract,
      profile_key: event.profile_key,
      operation_date: operationDate(event.received_at),
      os_numbers: Array.isArray(result.os_numbers) ? result.os_numbers : [],
      created_at: new Date().toISOString(),
      source_message_id: event.message_id,
    };
    writeJsonAtomic(statePath, fresh);
    return fresh.manual_orders[key];
  }

  function persistCompletion(config, event, job, result) {
    const nextConfig = {
      ...config,
      last_processed_message_timestamp: event.received_at,
      last_processed_message_id: event.message_id,
      execution_enabled:
        config.pause_after_job === false ? config.execution_enabled : false,
      activation_cursor:
        config.pause_after_job === false ? config.activation_cursor : null,
    };
    delete nextConfig.active_group;
    writeJsonAtomic(configPath, nextConfig);
    const state = loadState();
    delete state.pending[event.message_id];
    state.completed[event.message_id] = {
      contract: event.contract,
      job_id: job.job_id,
      idempotency_key: job.idempotency_key,
      state: String(result?.state || ''),
      completed_at: new Date().toISOString(),
    };
    writeJsonAtomic(statePath, state);
  }

  function effectiveEventFromTOA(event, snapshot) {
    assertDescSectorGroup(event, snapshot);
    const toaCloseCode = String(snapshot?.current_close_code || '').trim();
    const requestedCloseCode = String(event?.requested_close_code || '').trim();
    // The TOA is authoritative. A WhatsApp code cannot override a different
    // TOA code, and no equipment-based inferred code is substituted.
    const effectiveCloseCode = toaCloseCode;
    if (!effectiveCloseCode) {
      throw new DisconnectPilotError(['missing_close_code', 'operation_blocked']);
    }
    if (!SUPPORTED_CLOSE_CODES.has(effectiveCloseCode)) {
      throw new DisconnectPilotError(['unsupported_close_code', 'operation_blocked']);
    }
    if (!AUTOMATIC_CLOSE_CODES.has(effectiveCloseCode)) {
      const blocker = ['511', '512'].includes(effectiveCloseCode)
        ? 'productive_close_protocol_unavailable'
        : (['101', '106', '125', '306', '312', '404'].includes(effectiveCloseCode)
          ? 'improductive_close_prerequisite_unavailable'
          : 'productive_close_prerequisite_unavailable');
      throw new DisconnectPilotError([blocker, 'operation_blocked']);
    }
    if ((requestedCloseCode && requestedCloseCode !== toaCloseCode) ||
        (event.unsupported_close_code && event.unsupported_close_code !== toaCloseCode)) {
      throw new DisconnectPilotError(['close_code_mismatch', 'operation_blocked']);
    }
    const observation = extractTOATaskObservation(
      snapshot?.task_observation ||
      snapshot?.activity_observation ||
      snapshot?.observation
    );
    return Object.freeze({
      ...event,
      requested_close_code: effectiveCloseCode,
      observation: observation || event.observation,
    });
  }

  function effectiveEventWithoutTOA(_event) {
    // Never invent a 430 or create an artificial OS on lookup failures.
    throw new DisconnectPilotError(['toa_activity_not_found', 'operation_blocked']);
  }

  async function processEvent(event, input, config) {
    const lookup = buildTOADisconnectLookup(event);
    if (!toaBridge.queueDisconnectLookup(lookup)) {
      throw new DisconnectPilotError(['duplicate_message', 'operation_blocked']);
    }
    if (!event.observation && followUpGraceMs > 0) {
      await sleep(followUpGraceMs);
    }

    let toaResult;
    try {
      toaResult = await waitForTOA(lookup);
    } catch (error) {
      error.job_id = lookup.job_id;
      throw error;
    }

    const toaReason = String(toaResult.reason || 'toa_lookup_failed');
    // Missing/invalid TOA output is not proof of a valid disconnected OS.
    // This flow only executes against a confirmed TOA snapshot.
    const creationOnly = false;
    if (toaResult.ok !== true || !toaResult.snapshot) {
      throw new DisconnectPilotError([toaReason, 'operation_blocked']);
    }

    const effectiveEvent = creationOnly
      ? effectiveEventWithoutTOA(latestPendingEvent(event))
      : effectiveEventFromTOA(latestPendingEvent(event), toaResult.snapshot);
    const job = creationOnly
      ? buildWhatsAppCreationJob(effectiveEvent, lookup, toaReason)
      : buildDisconnectJob(effectiveEvent, lookup, toaResult.snapshot);

    let result;
    try {
      result = await publishAndWait(job);
    } catch (error) {
      error.job_id = job.job_id;
      throw error;
    }

    if (creationOnly) {
      if (
        !['os_created', 'os_already_open'].includes(String(result?.state || '')) ||
        result?.os_confirmed !== true
      ) {
        const error = new DisconnectPilotError(
          Array.isArray(result?.blockers) && result.blockers.length
            ? result.blockers
            : ['os_creation_not_confirmed', 'operation_blocked']
        );
        error.job_id = job.job_id;
        throw error;
      }
      persistCompletion(config, effectiveEvent, job, result);
      return {
        consumed: true,
        state: result.state,
        job,
        result,
        reaction: {
          chat_id: job.chat_id,
          message_id: job.message_id,
          emoji: result.state === 'os_created' ? '🆕' : '☑️',
          job_id: job.job_id,
        },
        admin_mentions: config.admin_mentions,
      };
    }

    if (
      result?.state !== 'completed' ||
      result?.os_confirmed !== true ||
      result?.equipments_confirmed !== true
    ) {
      const error = new DisconnectPilotError(
        Array.isArray(result?.blockers) && result.blockers.length
          ? result.blockers
          : ['success_not_confirmed', 'operation_blocked']
      );
      error.job_id = job.job_id;
      throw error;
    }

    const reaction = buildSuccessReaction(job, result);
    persistCompletion(config, effectiveEvent, job, result);
    return {
      consumed: true,
      state: 'completed',
      job,
      result,
      reaction,
      admin_mentions: config.admin_mentions,
    };
  }

  async function attemptEvent(event, input, config) {
    try {
      return await processEvent(event, input, config);
    } catch (error) {
      if (isRetryable(error)) {
        return scheduleRetry(
          event,
          input,
          String(error.blockers.find((blocker) => RETRYABLE_BLOCKERS.has(blocker)))
        );
      }
      removePending(event.message_id);
      throw error;
    }
  }

  async function handleMessage(input) {
    const config = activeConfig(input.chatId);
    if (!config) return { consumed: false, state: 'pilot_inactive' };
    const state = loadState();
    if (state.completed[input.messageId]) {
      throw new DisconnectPilotError(['duplicate_message', 'operation_blocked']);
    }
    if (state.pending[input.messageId]) {
      return {
        consumed: true,
        state: 'pending_retry_already_scheduled',
        contract: state.pending[input.messageId]?.event?.contract || '',
      };
    }
    let event;
    try {
      event = parseDisconnectMessage({
        messageId: input.messageId,
        chatId: input.chatId,
        senderId: input.senderId,
        receivedAt: input.receivedAt,
        text: input.text,
      });
    } catch (error) {
      if (error?.blockers?.includes('missing_contract')) {
        const attached = attachFollowUp(input);
        if (attached) return attached;
      }
      throw error;
    }
    assertAfterActivation(event, config);
    const receivedAtMs = Date.parse(event.received_at);
    const deliveryKey = [event.chat_id, event.sender_id, event.contract].join('|');
    for (const [key, seenAt] of recentDeliveries.entries()) {
      if (receivedAtMs - seenAt > deliveryDedupMs) recentDeliveries.delete(key);
    }
    const duplicateSeenAt = recentDeliveries.get(deliveryKey);
    if (
      Number.isFinite(duplicateSeenAt) &&
      Math.abs(receivedAtMs - duplicateSeenAt) <= deliveryDedupMs
    ) {
      return {
        consumed: false,
        state: 'duplicate_delivery_ignored',
        contract: event.contract,
      };
    }
    recentDeliveries.set(deliveryKey, receivedAtMs);
    savePending(event, input, 'queued');
    return enqueue(() => attemptEvent(event, input, config));
  }

  async function retryPendingNow({ force = true } = {}) {
    if (retrySweepRunning) return [];
    retrySweepRunning = true;
    try {
      const now = Date.now();
      const records = activePendingRecords(now)
        .filter((record) => (
          record?.event?.message_id &&
          (force || Date.parse(record.next_retry_at || '') <= now)
        ))
        .sort((left, right) => (
          Date.parse(left.first_seen_at || '') - Date.parse(right.first_seen_at || '')
        ));
      const outcomes = [];
      for (const record of records) {
        const config = activeConfig(record.event.chat_id);
        if (!config) continue;
        const outcome = await enqueue(async () => {
          try {
            const result = await attemptEvent(
              record.event,
              { messageKey: record.message_key },
              config
            );
            if (result?.state === 'completed') {
              await onBackgroundResult({ record, result, error: null });
            }
            return result;
          } catch (error) {
            await onBackgroundResult({ record, result: null, error });
            return {
              consumed: true,
              state: 'pending_retry_failed',
              contract: record.event.contract,
              blockers: Array.isArray(error?.blockers) ? error.blockers : [],
            };
          }
        });
        outcomes.push(outcome);
      }
      return outcomes;
    } finally {
      retrySweepRunning = false;
    }
  }

  const retryTimer = pendingRetryEnabled
    ? setInterval(() => {
        void retryPendingNow({ force: false }).catch((error) => {
          console.error(`[DISCONNECT-PILOT] pending sweep failed: ${error.message}`);
        });
      }, retryScanIntervalMs)
    : null;
  if (retryTimer && typeof retryTimer.unref === 'function') retryTimer.unref();

  function listDescPending({ limit = 50 } = {}) {
    const state = loadState();
    const pending = Object.values(state.pending || {})
      .map((record) => ({
        kind: 'pending',
        contract: String(record?.event?.contract || ''),
        profile_key: String(record?.event?.profile_key || ''),
        city: String(record?.event?.city || ''),
        attempts: Number(record?.attempts || 0),
        next_retry_at: String(record?.next_retry_at || ''),
        last_reason: String(record?.last_reason || ''),
        first_seen_at: String(record?.first_seen_at || ''),
        manual_order: state.manual_orders[manualOrderKey(record?.event || {})] || null,
      }));
    const manual = Object.values(state.manual_review || {})
      .map((record) => ({ ...record, kind: 'manual_review' }));
    return [...manual, ...pending]
      .sort((left, right) => Date.parse(right.finalized_at || right.first_seen_at || 0) - Date.parse(left.finalized_at || left.first_seen_at || 0))
      .slice(0, Math.max(1, Number(limit) || 50));
  }

  function stop() {
    if (retryTimer) clearInterval(retryTimer);
  }

  return Object.freeze({
    handleMessage,
    loadConfig,
    listDescPending,
    retryPendingNow,
    stop,
  });
}

module.exports = {
  createDisconnectPilotCoordinator,
  assertDescSectorGroup,
  writeJsonAtomic,
};
