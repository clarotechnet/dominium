const express = require("express");
const net = require("net");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const app = express();
app.disable("x-powered-by");
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
  next();
});

const HOST = "www.sistemaimperium.com.br";
const PROFILES = {
  natal: { label: "NATAL / PARNAMIRIM", port: 212 },
  fortaleza: { label: "FORTALEZA", port: 596 },
  mossoro: { label: "MOSSORÓ", port: 579 },
  recife: { label: "RECIFE", port: 599 },
};
const STATUS_VALUES = {
  field: "1",
  completed: "2",
  canceled: "3",
  rescheduled: "4",
};
const STATUS_LABELS = {
  field: "EM CAMPO",
  completed: "CONCLUIDA",
  canceled: "CANCELADA",
  rescheduled: "REAGENDADA",
};
const SERVICE_VALUES = {
  all: "%",
  installation: "1",
  technical: "2",
  disconnection: "3",
  stock: "7",
};
const MAX_FRAGMENTS = 256;

const templates = JSON.parse(
  fs.readFileSync(path.join(__dirname, "protocol_templates.json"), "ascii"),
);
if (templates.version !== 1) throw new Error("unsupported_protocol_templates");

function getCredentials() {
  const username = String(process.env.IMPERIUM_DATASNAP_USERNAME || "").trim();
  const password = String(process.env.IMPERIUM_DATASNAP_PASSWORD || "");
  return username && password ? { username, password } : null;
}

function packU32(value) {
  const out = Buffer.allocUnsafe(4);
  out.writeUInt32LE(value >>> 0, 0);
  return out;
}

function packDouble(value) {
  const out = Buffer.allocUnsafe(8);
  out.writeDoubleLE(value, 0);
  return out;
}

function automationDate(isoDate, endOfDay = false) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) throw new Error("invalid_date");
  const [, y, m, d] = match.map(Number);
  const epoch = Date.UTC(1899, 11, 30);
  const current = Date.UTC(y, m - 1, d);
  let days = (current - epoch) / 86400000;
  if (endOfDay) days += 1 - (1 / 86400000);
  return packDouble(days);
}

function utf16le(value) {
  return Buffer.from(value, "utf16le");
}

function replaceOnce(buffer, needle, replacement, label) {
  const index = buffer.indexOf(needle);
  if (index < 0 || buffer.indexOf(needle, index + 1) >= 0) {
    throw new Error("invalid_" + label + "_marker");
  }
  return Buffer.concat([
    buffer.subarray(0, index),
    replacement,
    buffer.subarray(index + needle.length),
  ]);
}

function buildMainQuery(isoDate, status, serviceType) {
  const statusValue = STATUS_VALUES[status];
  const serviceValue = SERVICE_VALUES[serviceType];
  if (!statusValue) throw new Error("invalid_status");
  if (!serviceValue) throw new Error("invalid_service_type");

  const capturedDate = String(templates.captured_date);
  let query = Buffer.from(templates.main_query, "base64");
  query = replaceOnce(
    query,
    automationDate(capturedDate),
    automationDate(isoDate),
    "date_start",
  );
  query = replaceOnce(
    query,
    automationDate(capturedDate, true),
    automationDate(isoDate, true),
    "date_end",
  );

  const statusNeedle = Buffer.concat([
    utf16le("Status"), packU32(8), packU32(1), Buffer.from("1", "ascii"),
  ]);
  const statusReplacement = Buffer.concat([
    utf16le("Status"), packU32(8), packU32(1), Buffer.from(statusValue, "ascii"),
  ]);
  query = replaceOnce(query, statusNeedle, statusReplacement, "status");

  const serviceNeedle = Buffer.concat([
    utf16le("IdTipoServico"), packU32(8), packU32(1), Buffer.from("3", "ascii"),
  ]);
  const serviceReplacement = Buffer.concat([
    utf16le("IdTipoServico"), packU32(8), packU32(1), Buffer.from(serviceValue, "ascii"),
  ]);
  return replaceOnce(query, serviceNeedle, serviceReplacement, "service");
}

function encodeWireValue(value) {
  if (Buffer.isBuffer(value)) {
    return Buffer.concat([
      Buffer.from('{"data":[' + value.length + ',', "ascii"),
      value,
      Buffer.from("]}", "ascii"),
    ]);
  }
  if (Array.isArray(value)) {
    const parts = [Buffer.from("[")];
    value.forEach((item, index) => {
      if (index) parts.push(Buffer.from(","));
      parts.push(encodeWireValue(item));
    });
    parts.push(Buffer.from("]"));
    return Buffer.concat(parts);
  }
  if (value && typeof value === "object") {
    const parts = [Buffer.from("{")];
    let first = true;
    for (const [key, item] of Object.entries(value)) {
      if (!first) parts.push(Buffer.from(","));
      first = false;
      parts.push(Buffer.from(JSON.stringify(String(key)) + ":", "utf8"));
      parts.push(encodeWireValue(item));
    }
    parts.push(Buffer.from("}"));
    return Buffer.concat(parts);
  }
  return Buffer.from(JSON.stringify(value), "utf8");
}

function skipWs(buffer, index) {
  while (index < buffer.length && [9, 10, 13, 32].includes(buffer[index])) index++;
  return index;
}

function matchDataHeader(buffer, index) {
  const literal = Buffer.from('"data"', "ascii");
  if (buffer[index] !== 34) return false;
  if (index + literal.length > buffer.length) {
    const remaining = buffer.subarray(index);
    return literal.subarray(0, remaining.length).equals(remaining) ? null : false;
  }
  if (!buffer.subarray(index, index + literal.length).equals(literal)) return false;
  let p = index + literal.length;
  p = skipWs(buffer, p);
  if (p >= buffer.length) return null;
  if (buffer[p++] !== 58) return false;
  p = skipWs(buffer, p);
  if (p >= buffer.length) return null;
  if (buffer[p++] !== 91) return false;
  p = skipWs(buffer, p);
  if (p >= buffer.length) return null;

  let sign = 1;
  if (buffer[p] === 45) {
    sign = -1;
    p++;
  }
  const startDigits = p;
  while (p < buffer.length && buffer[p] >= 48 && buffer[p] <= 57) p++;
  if (p === startDigits) return false;
  if (p >= buffer.length) return null;
  const length = sign * Number(buffer.subarray(startDigits, p).toString("ascii"));
  p = skipWs(buffer, p);
  if (p >= buffer.length) return null;
  if (buffer[p++] !== 44) return false;
  return { blobLength: Math.abs(length), blobStart: p };
}

function replaceBlobMarkers(value, blobs) {
  if (typeof value === "string" && blobs.has(value)) return blobs.get(value);
  if (Array.isArray(value)) return value.map((item) => replaceBlobMarkers(item, blobs));
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      out[key] = replaceBlobMarkers(item, blobs);
    }
    return out;
  }
  return value;
}

function decodeWireMessage(buffer) {
  const normalized = [];
  const blobs = new Map();
  let started = false;
  let depth = 0;
  let inString = false;
  let escaped = false;
  let index = 0;
  let copiedFrom = 0;

  const flushTo = (end) => {
    if (end > copiedFrom) normalized.push(buffer.subarray(copiedFrom, end));
    copiedFrom = end;
  };

  while (index < buffer.length) {
    const byte = buffer[index];

    if (!started) {
      if ([9, 10, 13, 32].includes(byte)) {
        index++;
        continue;
      }
      if (byte !== 123) throw new Error("invalid_datasnap_response");
      started = true;
    }

    if (inString) {
      if (escaped) escaped = false;
      else if (byte === 92) escaped = true;
      else if (byte === 34) inString = false;
      index++;
      continue;
    }

    const header = matchDataHeader(buffer, index);
    if (header === null) return null;
    if (header && header !== false) {
      const blobEnd = header.blobStart + header.blobLength;
      if (blobEnd > buffer.length) return null;
      flushTo(header.blobStart);
      const marker = "__datasnap_blob_" + blobs.size + "__";
      blobs.set(marker, Buffer.from(buffer.subarray(header.blobStart, blobEnd)));
      normalized.push(Buffer.from(JSON.stringify(marker), "ascii"));
      copiedFrom = blobEnd;
      depth += 1;
      index = blobEnd;
      continue;
    }

    if (byte === 34) inString = true;
    else if (byte === 123 || byte === 91) depth += 1;
    else if (byte === 125 || byte === 93) {
      depth -= 1;
      if (started && depth === 0) {
        flushTo(index + 1);
        const decoded = JSON.parse(Buffer.concat(normalized).toString("utf8"));
        return {
          consumed: index + 1,
          value: replaceBlobMarkers(decoded, blobs),
        };
      }
    }
    index++;
  }
  return null;
}

class DataSnapClient {
  constructor(host, port, username, password, timeoutMs = 25000) {
    this.host = host;
    this.port = port;
    this.username = username;
    this.password = password;
    this.timeoutMs = timeoutMs;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.waiters = [];
    this.error = null;
  }

  _notify() {
    const waiters = this.waiters.splice(0);
    waiters.forEach((resolve) => resolve());
  }

  async _wait(previousLength) {
    if (this.error) throw this.error;
    await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error);
        else resolve();
      };
      const timer = setTimeout(
        () => finish(new Error("datasnap_timeout")),
        this.timeoutMs,
      );
      this.waiters.push(() => finish());
      if (this.error) finish(this.error);
      else if (this.buffer.length !== previousLength) finish();
    });
    if (this.error) throw this.error;
  }

  async connect() {
    if (this.socket) return;
    const socket = net.createConnection({ host: this.host, port: this.port });
    socket.setNoDelay(true);
    socket.on("data", (chunk) => {
      this.buffer = Buffer.concat([this.buffer, chunk]);
      this._notify();
    });
    socket.on("error", (error) => {
      this.error = error;
      this._notify();
    });
    socket.on("close", () => {
      if (!this.error) this.error = new Error("datasnap_socket_closed");
      this._notify();
    });

    await new Promise((resolve, reject) => {
      socket.once("connect", resolve);
      socket.once("error", reject);
    });
    this.socket = socket;
    socket.write(Buffer.alloc(5, 5));
    const greeting = await this.readExact(5);
    if (!greeting.equals(Buffer.from([6, 0, 0, 0, 0]))) {
      throw new Error("unexpected_datasnap_greeting");
    }

    const response = await this.request("connect", [{
      DriverName: "DataSnap",
      DriverUnit: "Data.DBXDataSnap",
      Port: String(this.port),
      CommunicationProtocol: "tcp/ip",
      DatasnapContext: "datasnap/",
      DriverAssemblyLoader:
        "Borland.Data.TDBXClientDriverLoader,Borland.Data.DbxClientDriver,Version=24.0.0.0,Culture=neutral,PublicKeyToken=91d62ebb5b0d1b1b",
      HostName: this.host,
      DSAuthenticationUser: this.username,
      DSAuthenticationPassword: this.password,
      UNLICENSED_DRIVERS: "0",
    }]);
    if (!Array.isArray(response.result) || response.result[0] !== 0) {
      throw new Error("datasnap_authentication_rejected");
    }
  }

  close() {
    try { this.socket?.destroy(); } catch {}
    this.socket = null;
  }

  async readExact(length) {
    while (this.buffer.length < length) {
      const previousLength = this.buffer.length;
      await this._wait(previousLength);
    }
    const out = this.buffer.subarray(0, length);
    this.buffer = this.buffer.subarray(length);
    return out;
  }

  async readMessage() {
    while (true) {
      const decoded = decodeWireMessage(this.buffer);
      if (decoded) {
        this.buffer = this.buffer.subarray(decoded.consumed);
        if (decoded.value?.error) throw new Error(String(decoded.value.error));
        return decoded.value;
      }
      const previousLength = this.buffer.length;
      await this._wait(previousLength);
    }
  }

  async request(method, params) {
    if (!this.socket) throw new Error("datasnap_not_connected");
    this.socket.write(encodeWireValue({ method, params }));
    return this.readMessage();
  }

  async prepare(methodName) {
    return this.request("prepare", [-1, false, "DataSnap.ServerMethod", methodName]);
  }
}

function parseOrders(payload) {
  if (payload.length < 3) throw new Error("invalid_order_dataset");
  if (payload.length >= 3 && payload[0] === 0xc0 && payload[1] === 0xc0 && payload[2] === 0x60) {
    return [];
  }
  if (payload.length < 46) throw new Error("invalid_order_dataset_header");

  const orders = [];
  const seen = new Set();
  for (let i = 0; i < payload.length - 2; i++) {
    const n = payload[i];
    if (n < 1 || n > 20 || i + 1 + n > payload.length) continue;
    const osBytes = payload.subarray(i + 1, i + 1 + n);
    let digits = true;
    for (const byte of osBytes) {
      if (byte < 48 || byte > 57) { digits = false; break; }
    }
    if (!digits) continue;

    const idPos = i - 4;
    if (idPos < 0) continue;
    const idOs = payload.readUInt32LE(idPos);
    if (idOs <= 0 || idOs > 0x0fffffff || seen.has(idOs)) continue;

    let pos = i + 1 + n;
    if (pos >= payload.length) continue;
    const contractLength = payload[pos++];
    if (contractLength <= 0 || contractLength > 20 || pos + contractLength + 5 > payload.length) continue;
    const contractBytes = payload.subarray(pos, pos + contractLength);
    pos += contractLength;
    if (![...contractBytes].every((b) => b >= 48 && b <= 57)) continue;

    const idService = payload.readUInt32LE(pos);
    pos += 4;
    if (idService <= 0 || idService > 1000000 || pos >= payload.length) continue;

    const serviceLength = payload[pos++];
    if (serviceLength <= 0 || serviceLength > 120 || pos + serviceLength > payload.length) continue;
    const serviceBytes = payload.subarray(pos, pos + serviceLength);
    if ([...serviceBytes].some((b) => b < 0x20 || b === 0x7f)) continue;

    seen.add(idOs);
    orders.push({
      id_os: idOs,
      num_os: osBytes.toString("ascii"),
      contract: contractBytes.toString("ascii"),
      id_service: idService,
      service: serviceBytes.toString("latin1"),
    });
  }
  if (!orders.length) throw new Error("no_valid_orders_parsed");
  return orders;
}

async function listOrders(profileKey, isoDate, status = "field", serviceType = "all") {
  const profile = PROFILES[profileKey];
  if (!profile) throw new Error("invalid_profile");
  const credentials = getCredentials();
  if (!credentials) throw new Error("datasnap_credentials_not_configured");

  const client = new DataSnapClient(
    HOST,
    profile.port,
    credentials.username,
    credentials.password,
    90000,
  );
  try {
    await client.connect();
    const prepared = await client.prepare("TDtmOrdemServico.AS_GetRecords");
    const handle = Number(prepared?.result?.[0]?.handle?.[0]);
    if (!Number.isInteger(handle)) throw new Error("invalid_datasnap_handle");

    const response = await client.request("execute", [
      { handle: [handle] },
      buildMainQuery(isoDate, status, serviceType),
    ]);
    const initial = response?.result?.[1]?.data?.[1];
    if (!Buffer.isBuffer(initial)) throw new Error("missing_order_dataset");
    let payload = Buffer.from(initial);
    if (payload.length < 24) throw new Error("incomplete_order_dataset");
    const expectedLength = payload.readUInt32LE(20) + 28;

    let fragments = 0;
    while (expectedLength > payload.length) {
      fragments++;
      if (fragments > MAX_FRAGMENTS) throw new Error("too_many_order_fragments");
      const remainder = await client.request("more_blob", [handle, 1, 0, 7, true, 0]);
      const chunk = remainder?.result?.[0]?.data?.[1];
      if (!Buffer.isBuffer(chunk) || !chunk.length) throw new Error("invalid_order_fragment");
      payload = Buffer.concat([payload, chunk]);
    }
    if (payload.length !== expectedLength) throw new Error("incomplete_order_dataset");
    return parseOrders(payload).map((order) => ({
      ...order,
      status: STATUS_LABELS[status],
    }));
  } finally {
    client.close();
  }
}

app.use(express.json({ limit: "256kb" }));

const SUPABASE_URL = "https://haqzzxpocwzntyudrbch.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_s__p_R64LRUZ_Vk4Cid5BQ_ajAJkSn7";
const AUTH_EMAIL_DOMAIN = "auth.dominium.invalid";
const DOMINIUM_AUTH_OPS_URL = SUPABASE_URL + "/functions/v1/dominium-auth-ops";
const SESSION_IDLE_MS = 8 * 60 * 60 * 1000;
const SESSION_ABSOLUTE_MS = 12 * 60 * 60 * 1000;
const AUTH_COOKIE = "__Host-dominium_session";
const PUBLIC_AUTH_PATHS = new Set([
  "/api/auth/bootstrap",
  "/api/auth/session",
  "/api/auth/login",
  "/api/auth/register",
]);

function sha256(value) {
  return crypto.createHash("sha256").update(String(value || ""), "utf8").digest("hex");
}

function randomToken(bytes = 32) {
  return crypto.randomBytes(bytes).toString("base64url");
}

function bridgeToken() {
  const value = String(process.env.DOMINIUM_SUPABASE_BRIDGE_TOKEN || "").trim();
  if (!value) throw new Error("dominium_bridge_not_configured");
  return value;
}

function normalizeUsername(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{2,47}$/.test(normalized)) return "";
  return normalized;
}

function cookieValue(req, name) {
  const raw = String(req.headers.cookie || "");
  for (const part of raw.split(";")) {
    const idx = part.indexOf("=");
    if (idx < 0) continue;
    if (part.slice(0, idx).trim() === name) {
      return decodeURIComponent(part.slice(idx + 1).trim());
    }
  }
  return "";
}

function queueSessionCookie(res, token) {
  res.setHeader(
    "Set-Cookie",
    AUTH_COOKIE + "=" + encodeURIComponent(token) + "; Path=/; HttpOnly; Secure; SameSite=Strict",
  );
}

function clearSessionCookie(res) {
  res.setHeader(
    "Set-Cookie",
    AUTH_COOKIE + "=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0",
  );
}

async function supabaseRpc(name, body) {
  const response = await fetch(SUPABASE_URL + "/rest/v1/rpc/" + name, {
    method: "POST",
    headers: {
      apikey: SUPABASE_PUBLISHABLE_KEY,
      "content-type": "application/json",
      accept: "application/json",
    },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error("supabase_rpc_failed:" + response.status + ":" + message.slice(0, 180));
  }
  const raw = await response.text();
  if (!raw) return null;
  return JSON.parse(raw);
}

async function edgeAuthAction(action, body = {}, actorUserId = 0) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const requestBody = { action, ...(body || {}) };
    if (actorUserId) requestBody.actor_user_id = Number(actorUserId);
    const response = await fetch(DOMINIUM_AUTH_OPS_URL, {
      method: "POST",
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
        "content-type": "application/json",
        "x-dominium-edge-key": bridgeToken(),
      },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
    let payload = null;
    try { payload = await response.json(); } catch {}
    if (!response.ok || !payload || payload.ok !== true) {
      const error = new Error(String(payload?.error || "Falha temporaria na operacao"));
      error.statusCode = response.status || 500;
      throw error;
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

async function profileLookup(username) {
  return supabaseRpc("dominium_web_profile_lookup", {
    p_username: username,
    p_bridge_token: bridgeToken(),
  });
}

async function recordLoginFailure(userId) {
  if (!userId) return;
  await supabaseRpc("dominium_web_login_failure", {
    p_user_id: Number(userId),
    p_bridge_token: bridgeToken(),
  }).catch(() => null);
}

async function recordLoginSuccess(userId) {
  return supabaseRpc("dominium_web_login_success", {
    p_user_id: Number(userId),
    p_bridge_token: bridgeToken(),
  });
}

async function createDominiumSession(user, userAgent) {
  const token = randomToken(32);
  const csrf = randomToken(32);
  const now = Date.now();
  await supabaseRpc("dominium_web_session_create", {
    p_token_hash: sha256(token),
    p_user_id: Number(user.id),
    p_csrf_hash: sha256(csrf),
    p_csrf_token: csrf,
    p_user_agent_hash: sha256(userAgent || ""),
    p_expires_at: new Date(now + SESSION_IDLE_MS).toISOString(),
    p_absolute_expires_at: new Date(now + SESSION_ABSOLUTE_MS).toISOString(),
    p_bridge_token: bridgeToken(),
  });
  return { token, csrf };
}

async function currentSession(req, { touch = true } = {}) {
  const token = cookieValue(req, AUTH_COOKIE);
  if (!token) return null;
  return supabaseRpc("dominium_web_session_get", {
    p_token_hash: sha256(token),
    p_user_agent_hash: sha256(String(req.headers["user-agent"] || "")),
    p_touch: Boolean(touch),
    p_bridge_token: bridgeToken(),
  });
}

async function revokeCurrentSession(req) {
  const token = cookieValue(req, AUTH_COOKIE);
  if (!token) return;
  await supabaseRpc("dominium_web_session_revoke", {
    p_token_hash: sha256(token),
    p_bridge_token: bridgeToken(),
  }).catch(() => null);
}

async function auditAuth(user, action, result, req, target = "", metadata = {}) {
  await supabaseRpc("dominium_web_audit", {
    p_user_id: user?.id ? Number(user.id) : null,
    p_username: String(user?.username || ""),
    p_action: action,
    p_result: result,
    p_request_id: String(req.headers["x-request-id"] || ""),
    p_target: String(target || ""),
    p_metadata_json: JSON.stringify(metadata || {}),
    p_bridge_token: bridgeToken(),
  }).catch(() => null);
}

function authPublicState() {
  return {
    auth_backend: "supabase",
    registration_enabled: true,
    bootstrap_required: false,
    bootstrap_allowed: false,
  };
}

const loginAttempts = new Map();
function loginRateLimited(req, username) {
  const key = String(req.ip || req.socket?.remoteAddress || "") + "|" + username;
  const now = Date.now();
  const row = loginAttempts.get(key) || { count: 0, start: now };
  if (now - row.start > 60_000) {
    row.count = 0;
    row.start = now;
  }
  row.count += 1;
  loginAttempts.set(key, row);
  return row.count > 12;
}

const registrationAttempts = new Map();
function registrationRateLimited(req) {
  const key = String(req.ip || req.socket?.remoteAddress || "");
  const now = Date.now();
  const row = registrationAttempts.get(key) || { count: 0, start: now };
  if (now - row.start > 15 * 60_000) { row.count = 0; row.start = now; }
  row.count += 1;
  registrationAttempts.set(key, row);
  return row.count > 8;
}

app.get("/api/auth/bootstrap", (_req, res) => {
  res.set("cache-control", "no-store").json({ ok: true, ...authPublicState() });
});

app.get("/api/auth/session", async (req, res) => {
  try {
    const session = await currentSession(req);
    res.set("cache-control", "no-store").json({
      ok: true,
      authenticated: Boolean(session),
      ...authPublicState(),
      user: session?.user || null,
      csrf_token: session?.csrf_token || "",
    });
  } catch {
    res.status(503).json({ ok: false, error: "Autenticacao temporariamente indisponivel" });
  }
});

app.post("/api/auth/register", async (req, res) => {
  if (registrationRateLimited(req)) {
    return res.status(429).json({ ok: false, error: "Muitas tentativas de cadastro; tente novamente em alguns minutos" });
  }
  try {
    const payload = await edgeAuthAction("register", req.body || {});
    res.set("cache-control", "no-store").status(201).json({
      ok: true, authenticated: false, user: payload.user || null, csrf_token: "", ...authPublicState(),
    });
  } catch (error) {
    const status = Number(error?.statusCode || 400);
    res.status(status >= 400 && status < 600 ? status : 400).json({
      ok: false, error: String(error?.message || "Nao foi possivel criar o cadastro agora"),
    });
  }
});

app.post("/api/auth/login", async (req, res) => {
  const username = normalizeUsername(req.body?.username);
  const supplied = String(req.body?.password || "");
  const denied = () => res.status(401).json({
    ok: false,
    error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado",
  });

  if (!username || !supplied || loginRateLimited(req, username)) return denied();

  try {
    const profile = await profileLookup(username);
    if (!profile || profile.status !== "active") {
      if (profile?.id) await recordLoginFailure(profile.id);
      return denied();
    }
    if (profile.locked_until && new Date(profile.locked_until).getTime() > Date.now()) return denied();

    const authResponse = await fetch(SUPABASE_URL + "/auth/v1/token?grant_type=password", {
      method: "POST",
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        email: username + "@" + AUTH_EMAIL_DOMAIN,
        password: supplied,
      }),
    });
    if (!authResponse.ok) {
      await recordLoginFailure(profile.id);
      await auditAuth(null, "auth.login", "denied", req, username);
      return denied();
    }

    const user = await recordLoginSuccess(profile.id);
    const session = await createDominiumSession(user, String(req.headers["user-agent"] || ""));
    queueSessionCookie(res, session.token);
    await auditAuth(user, "auth.login", "success", req, username);
    res.set("cache-control", "no-store").json({
      ok: true,
      authenticated: true,
      user,
      csrf_token: session.csrf,
    });
  } catch {
    res.status(503).json({ ok: false, error: "Autenticacao temporariamente indisponivel" });
  }
});

app.post("/api/auth/logout", async (req, res) => {
  const session = await currentSession(req, { touch: false }).catch(() => null);
  if (session) {
    const suppliedCsrf = String(req.headers["x-csrf-token"] || "");
    if (!suppliedCsrf || sha256(suppliedCsrf) !== String(session.csrf_hash || "")) {
      return res.status(403).json({ ok: false, error: "Sessao invalida; atualize e entre novamente" });
    }
  }
  await revokeCurrentSession(req);
  clearSessionCookie(res);
  res.set("cache-control", "no-store").json({ ok: true });
});

app.use(async (req, res, next) => {
  if (!req.path.startsWith("/api/")) return next();
  if (PUBLIC_AUTH_PATHS.has(req.path)) return next();
  if (req.path === "/api/auth/logout") return next();

  try {
    const session = await currentSession(req);
    if (!session) {
      clearSessionCookie(res);
      return res.status(401).json({
        ok: false,
        error: "Entre no DOMINIUM para continuar",
        authentication_required: true,
      });
    }

    req.dominiumSession = session;
    req.dominiumUser = session.user;

    if (req.path === "/api/auth/users" || req.path === "/api/auth/pending-count") {
      if (session.user?.role !== "admin") {
        return res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
      }
    }

    if (req.method !== "GET" && req.method !== "HEAD") {
      const suppliedCsrf = String(req.headers["x-csrf-token"] || "");
      if (!suppliedCsrf || sha256(suppliedCsrf) !== String(session.csrf_hash || "")) {
        return res.status(403).json({ ok: false, error: "Sessao invalida; atualize e entre novamente" });
      }
      if (!["admin", "controller"].includes(String(session.user?.role || ""))) {
        return res.status(403).json({ ok: false, error: "Esta operacao exige perfil operacional" });
      }
    }

    next();
  } catch {
    res.status(503).json({ ok: false, error: "Autenticacao temporariamente indisponivel" });
  }
});

app.get("/api/auth/users", async (_req, res) => {
  try {
    const users = await supabaseRpc("dominium_web_list_users", { p_bridge_token: bridgeToken() });
    res.set("cache-control", "no-store").json({ ok: true, users: Array.isArray(users) ? users : [] });
  } catch {
    res.status(503).json({ ok: false, error: "Usuarios indisponiveis" });
  }
});

app.get("/api/auth/pending-count", async (_req, res) => {
  try {
    const count = await supabaseRpc("dominium_web_pending_count", { p_bridge_token: bridgeToken() });
    res.set("cache-control", "no-store").json({ ok: true, pending_count: Number(count || 0) });
  } catch {
    res.status(503).json({ ok: false, error: "Contagem indisponivel" });
  }
});

app.post(/^\/api\/auth\/users\/\d+\/(approve|reject|imperium-identity)$/, async (req, res) => {
  if (req.dominiumUser?.role !== "admin") {
    return res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }
  const match = req.path.match(/^\/api\/auth\/users\/(\d+)\/(approve|reject|imperium-identity)$/);
  if (!match) return res.status(404).json({ ok: false, error: "Operacao invalida" });
  const userId = Number(match[1]);
  const action = match[2] === "imperium-identity" ? "link_identity" : match[2];
  try {
    const payload = await edgeAuthAction(
      action,
      { ...(req.body || {}), user_id: userId },
      Number(req.dominiumUser.id),
    );
    res.set("cache-control", "no-store").json({ ok: true, user: payload.user || null });
  } catch (error) {
    const status = Number(error?.statusCode || 400);
    res.status(status >= 400 && status < 600 ? status : 400).json({
      ok: false, error: String(error?.message || "Falha temporaria na operacao"),
    });
  }
});

app.get("/api/status", (req, res) => {
  const key = String(req.query.profile || "natal").toLowerCase();
  const profile = PROFILES[key] || PROFILES.natal;
  res.json({
    ok: true,
    profile: key in PROFILES ? key : "natal",
    label: profile.label,
    company: profile.label,
    close_enabled: false,
    official_close_enabled: false,
    material_writeoff_enabled: false,
    native_creation_enabled: false,
    installer_change_enabled: false,
    serialized_transfer_enabled: false,
    read_only_web: true,
  });
});

app.get("/api/import-targets", (_req, res) => {
  res.json({
    ok: true,
    targets: [
      { key: "rn", label: "RN", enabled: false },
      { key: "ftz", label: "FTZ", enabled: false },
      { key: "jcr", label: "JCR", enabled: false },
      { key: "mro", label: "MRO", enabled: false },
    ],
  });
});

app.get("/api/toa-live/status", (_req, res) => {
  res.json({
    ok: true,
    connected: false,
    authenticated: false,
    web_mode: true,
    last_error: "TOA local ainda nao foi migrado para a hospedagem web",
  });
});

app.get("/api/toa-automation", (_req, res) => {
  res.json({
    ok: true,
    running: false,
    enabled: false,
    web_mode: true,
    routes: [],
    message: "Automacao TOA permanece no servidor operacional durante a migracao",
  });
});

app.get("/api/technicians", (_req, res) => {
  res.json({ ok: true, technicians: [], teams: {}, source: { web_mode: true, available: false } });
});

app.get("/api/health-check", async (_req, res) => {
  const results = [];
  for (const [key, profile] of Object.entries(PROFILES)) {
    const started = Date.now();
    let socket;
    try {
      socket = net.createConnection({ host: HOST, port: profile.port });
      const healthy = await new Promise((resolve) => {
        let received = Buffer.alloc(0);
        const finish = (value) => {
          try { socket.destroy(); } catch {}
          resolve(Boolean(value));
        };
        const timer = setTimeout(() => finish(false), 4000);
        socket.on("connect", () => socket.write(Buffer.alloc(5, 5)));
        socket.on("data", (chunk) => {
          received = Buffer.concat([received, chunk]);
          if (received.length >= 5) {
            clearTimeout(timer);
            finish(received.subarray(0, 5).equals(Buffer.from([6, 0, 0, 0, 0])));
          }
        });
        socket.on("error", () => {
          clearTimeout(timer);
          finish(false);
        });
      });
      results.push({ profile: key, label: profile.label, online: healthy, elapsed_ms: Date.now() - started });
    } catch {
      try { socket?.destroy(); } catch {}
      results.push({ profile: key, label: profile.label, online: false, elapsed_ms: Date.now() - started });
    }
  }
  res.json({
    ok: true,
    offline: results.filter((item) => !item.online).length,
    online: results.filter((item) => item.online).length,
    results,
    generated_at: new Date().toISOString(),
  });
});

app.get("/api/diagnostics", async (_req, res) => {
  const configured = Boolean(getCredentials());
  const results = [];
  for (const [key, profile] of Object.entries(PROFILES)) {
    const started = Date.now();
    try {
      const socket = net.createConnection({ host: HOST, port: profile.port });
      const result = await new Promise((resolve) => {
        let buffer = Buffer.alloc(0);
        const finish = (value) => { socket.destroy(); resolve(value); };
        socket.setTimeout(5000);
        socket.on("connect", () => socket.write(Buffer.alloc(5, 5)));
        socket.on("data", (chunk) => {
          buffer = Buffer.concat([buffer, chunk]);
          if (buffer.length >= 5) {
            finish(buffer.subarray(0, 5).equals(Buffer.from([6, 0, 0, 0, 0])));
          }
        });
        socket.on("error", () => finish(false));
        socket.on("timeout", () => finish(false));
      });
      results.push({ profile: key, port: profile.port, tcp: result, elapsed_ms: Date.now() - started });
    } catch {
      results.push({ profile: key, port: profile.port, tcp: false, elapsed_ms: Date.now() - started });
    }
  }
  res.set("cache-control", "no-store").json({
    ok: results.every((item) => item.tcp),
    credentials_configured: configured,
    host: HOST,
    results,
  });
});

app.get("/api/profiles", (_req, res) => {
  res.json({
    default: "natal",
    profiles: Object.entries(PROFILES).map(([key, item]) => ({
      key,
      label: item.label,
      close_enabled: false,
      material_writeoff_enabled: false,
      native_creation_enabled: false,
      installer_change_enabled: false,
      serialized_transfer_enabled: false,
      native_creation_services: [],
    })),
  });
});

app.get("/api/orders", async (req, res) => {
  const profile = String(req.query.profile || "natal").toLowerCase();
  const date = String(req.query.date || new Date().toISOString().slice(0, 10));
  const status = String(req.query.status || "field").toLowerCase();
  const serviceType = String(req.query.service_type || "all").toLowerCase();
  if (!PROFILES[profile]) return res.status(400).json({ ok: false, error: "Perfil inválido" });
  if (!STATUS_VALUES[status]) return res.status(400).json({ ok: false, error: "Status inválido" });
  if (!SERVICE_VALUES[serviceType]) return res.status(400).json({ ok: false, error: "Tipo de serviço inválido" });
  try {
    const orders = await listOrders(profile, date, status, serviceType);
    res.set("cache-control", "no-store").json({
      date,
      count: orders.length,
      status_filter: status,
      service_type_filter: serviceType,
      read_only: true,
      orders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "datasnap_error";
    const statusCode = message === "datasnap_credentials_not_configured" ? 503 : 502;
    res.status(statusCode).json({ ok: false, error: message });
  }
});


const staticDir = path.join(__dirname, "static");
app.use(express.static(staticDir, {
  index: false,
  etag: true,
  maxAge: "1h",
  setHeaders(res, filePath) {
    if (filePath.endsWith("index.html")) {
      res.setHeader("Cache-Control", "no-store");
    }
  },
}));

app.use((req, res, next) => {
  if (req.path.startsWith("/api/")) return next();
  if (req.method !== "GET" && req.method !== "HEAD") return next();
  res.set("Cache-Control", "no-store");
  res.sendFile(path.join(staticDir, "index.html"));
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () => {
  console.log("DOMINIUM web listening on " + port);
});
