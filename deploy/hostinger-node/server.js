const express = require("express");
const net = require("net");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const app = express();
app.disable("x-powered-by");

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

const SUPABASE_URL = String(process.env.SUPABASE_URL || "https://haqzzxpocwzntyudrbch.supabase.co").replace(/\/+$/, "");
const SUPABASE_PUBLISHABLE_KEY = String(
  process.env.SUPABASE_PUBLISHABLE_KEY || "sb_publishable_s__p_R64LRUZ_Vk4Cid5BQ_ajAJkSn7",
);
const AUTH_EMAIL_DOMAIN = "auth.dominium.invalid";
const DOMINIUM_EDGE_KEY = String(process.env.DOMINIUM_EDGE_KEY || "").trim();
const DOMINIUM_AUTH_OPS_URL = SUPABASE_URL + "/functions/v1/dominium-auth-ops";
const ACCESS_COOKIE = "__Host-dominium_session";
const REFRESH_COOKIE = "__Host-dominium_refresh";
const CSRF_COOKIE = "__Host-dominium_csrf";
const STATIC_DIR = path.join(__dirname, "static");

const IMPORT_TARGETS = [
  { key: "rn", label: "RN", profile: "natal", description: "Natal e Parnamirim", routes: ["NTL", "PWM"] },
  { key: "ftz", label: "FTZ", profile: "fortaleza", description: "Rota Fortaleza", routes: ["FTZ"] },
  { key: "jcr", label: "JCR", profile: "recife", description: "Rota Recife", routes: ["JCR"] },
  { key: "mro", label: "MRO", profile: "mossoro", description: "Rota Mossoro", routes: ["MRO"] },
];

function parseCookies(req) {
  const out = {};
  const raw = String(req.headers.cookie || "");
  for (const part of raw.split(";")) {
    const index = part.indexOf("=");
    if (index <= 0) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if (!key) continue;
    try {
      out[key] = decodeURIComponent(value);
    } catch {
      out[key] = value;
    }
  }
  return out;
}

function appendCookie(res, cookie) {
  const current = res.getHeader("Set-Cookie");
  if (!current) res.setHeader("Set-Cookie", [cookie]);
  else if (Array.isArray(current)) res.setHeader("Set-Cookie", current.concat([cookie]));
  else res.setHeader("Set-Cookie", [String(current), cookie]);
}

function setCookie(res, name, value, options = {}) {
  const maxAge = Number(options.maxAge || 0);
  const httpOnly = options.httpOnly !== false;
  let cookie = name + "=" + encodeURIComponent(String(value || "")) + "; Path=/; Secure; SameSite=Strict";
  if (httpOnly) cookie += "; HttpOnly";
  if (maxAge > 0) cookie += "; Max-Age=" + Math.floor(maxAge);
  appendCookie(res, cookie);
}

function clearCookie(res, name) {
  appendCookie(res, name + "=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0");
}

function secureEqual(left, right) {
  const a = Buffer.from(String(left || ""), "utf8");
  const b = Buffer.from(String(right || ""), "utf8");
  if (!a.length || a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function authState(extra = {}) {
  return Object.assign({
    registration_enabled: false,
    bootstrap_required: false,
    bootstrap_allowed: false,
    auth_backend: "supabase",
  }, extra);
}

async function supabaseJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  return { response, payload };
}

async function authToken(grantType, body) {
  return supabaseJson(
    SUPABASE_URL + "/auth/v1/token?grant_type=" + encodeURIComponent(grantType),
    {
      method: "POST",
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
}

async function currentUser(accessToken) {
  if (!accessToken) return null;
  const result = await supabaseJson(
    SUPABASE_URL + "/rest/v1/rpc/dominium_current_user",
    {
      method: "POST",
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
        authorization: "Bearer " + accessToken,
        "content-type": "application/json",
      },
      body: "{}",
    },
  );
  const payload = result.payload;
  if (!result.response.ok || !payload || typeof payload !== "object") return null;
  if (String(payload.status || "") !== "active") return null;
  return payload;
}

async function adminUsers(accessToken) {
  const result = await supabaseJson(
    SUPABASE_URL + "/rest/v1/rpc/dominium_admin_users",
    {
      method: "POST",
      headers: {
        apikey: SUPABASE_PUBLISHABLE_KEY,
        authorization: "Bearer " + accessToken,
        "content-type": "application/json",
      },
      body: "{}",
    },
  );
  if (!result.response.ok || !Array.isArray(result.payload)) {
    throw new Error("forbidden");
  }
  return result.payload;
}

async function edgeAuthAction(action, body = {}, accessToken = "") {
  if (!DOMINIUM_EDGE_KEY) throw new Error("auth_ops_not_configured");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = {
      apikey: SUPABASE_PUBLISHABLE_KEY,
      "content-type": "application/json",
      "x-dominium-edge-key": DOMINIUM_EDGE_KEY,
    };
    if (accessToken) headers.authorization = "Bearer " + accessToken;
    const response = await fetch(DOMINIUM_AUTH_OPS_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(Object.assign({ action }, body)),
      signal: controller.signal,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok || !payload || payload.ok !== true) {
      const message = String(payload?.error || "Falha temporaria na operacao");
      const error = new Error(message);
      error.statusCode = response.status || 500;
      throw error;
    }
    return payload;
  } finally {
    clearTimeout(timer);
  }
}

function setSessionCookies(res, authPayload, csrfToken) {
  const expiresIn = Number((authPayload && authPayload.expires_in) || 3600);
  setCookie(res, ACCESS_COOKIE, (authPayload && authPayload.access_token) || "", {
    maxAge: Math.max(60, Math.min(expiresIn, 3600)),
  });
  setCookie(res, REFRESH_COOKIE, (authPayload && authPayload.refresh_token) || "", {
    maxAge: 30 * 24 * 60 * 60,
  });
  setCookie(res, CSRF_COOKIE, csrfToken, {
    maxAge: 12 * 60 * 60,
  });
}

function clearSessionCookies(res) {
  clearCookie(res, ACCESS_COOKIE);
  clearCookie(res, REFRESH_COOKIE);
  clearCookie(res, CSRF_COOKIE);
}

async function resolveSession(req, res) {
  const cookies = parseCookies(req);
  let accessToken = cookies[ACCESS_COOKIE] || "";
  let refreshToken = cookies[REFRESH_COOKIE] || "";
  let user = await currentUser(accessToken);

  if (!user && refreshToken) {
    const refreshed = await authToken("refresh_token", { refresh_token: refreshToken });
    if (refreshed.response.ok && refreshed.payload && refreshed.payload.access_token) {
      accessToken = String(refreshed.payload.access_token);
      refreshToken = String(refreshed.payload.refresh_token || refreshToken);
      user = await currentUser(accessToken);
      if (user) {
        const csrf = cookies[CSRF_COOKIE] || crypto.randomBytes(32).toString("base64url");
        setSessionCookies(
          res,
          Object.assign({}, refreshed.payload, { refresh_token: refreshToken }),
          csrf,
        );
        cookies[CSRF_COOKIE] = csrf;
      }
    }
  }

  if (!user) return null;
  let csrfToken = cookies[CSRF_COOKIE] || "";
  if (!csrfToken) {
    csrfToken = crypto.randomBytes(32).toString("base64url");
    setCookie(res, CSRF_COOKIE, csrfToken, { maxAge: 12 * 60 * 60 });
  }
  return { user, accessToken, csrfToken };
}

function requireRole(session, roles) {
  return Boolean(session && session.user && roles.includes(String(session.user.role || "")));
}

app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  res.setHeader("Referrer-Policy", "same-origin");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
  res.setHeader("Cross-Origin-Resource-Policy", "same-origin");
  res.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests",
  );
  next();
});

app.get("/api/auth/bootstrap", (_req, res) => {
  res.set("cache-control", "no-store").json(Object.assign({ ok: true }, authState()));
});

app.get("/api/auth/session", async (req, res) => {
  try {
    const session = await resolveSession(req, res);
    res.set("cache-control", "no-store").json(Object.assign({
      ok: true,
      authenticated: Boolean(session),
      user: session ? session.user : null,
      csrf_token: session ? session.csrfToken : "",
    }, authState()));
  } catch {
    clearSessionCookies(res);
    res.set("cache-control", "no-store").json(Object.assign({
      ok: true,
      authenticated: false,
      user: null,
      csrf_token: "",
    }, authState()));
  }
});

app.post("/api/auth/login", async (req, res) => {
  const username = String((req.body && req.body.username) || "").trim().toLowerCase();
  const password = String((req.body && req.body.password) || "");
  if (!/^[a-z0-9][a-z0-9._-]{2,47}$/.test(username) || !password) {
    return res.status(401).json({
      ok: false,
      error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado",
    });
  }

  try {
    const auth = await authToken("password", {
      email: username + "@" + AUTH_EMAIL_DOMAIN,
      password,
    });
    if (!auth.response.ok || !auth.payload || !auth.payload.access_token) {
      return res.status(401).json({
        ok: false,
        error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado",
      });
    }

    const user = await currentUser(String(auth.payload.access_token));
    if (!user) {
      return res.status(401).json({
        ok: false,
        error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado",
      });
    }

    const csrfToken = crypto.randomBytes(32).toString("base64url");
    setSessionCookies(res, auth.payload, csrfToken);
    res.set("cache-control", "no-store").json(Object.assign({
      ok: true,
      authenticated: true,
      user,
      csrf_token: csrfToken,
    }, authState()));
  } catch {
    res.status(503).json({ ok: false, error: "Falha temporaria ao autenticar no DOMINIUM" });
  }
});

app.post("/api/auth/register", (_req, res) => {
  res.status(403).json({
    ok: false,
    error: "Novos cadastros estao temporariamente desabilitados na versao web",
  });
});

app.use(async (req, res, next) => {
  if (!req.path.startsWith("/api/")) return next();
  const publicPaths = new Set([
    "/api/auth/bootstrap",
    "/api/auth/session",
    "/api/auth/login",
    "/api/auth/register",
  ]);
  if (publicPaths.has(req.path)) return next();

  let session = null;
  try {
    session = await resolveSession(req, res);
  } catch {
    session = null;
  }
  if (!session) {
    return res.status(401).json({
      ok: false,
      error: "Entre no DOMINIUM para continuar",
      authentication_required: true,
    });
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(req.method)) {
    const cookies = parseCookies(req);
    const supplied = String(req.headers["x-csrf-token"] || "");
    if (!secureEqual(supplied, cookies[CSRF_COOKIE] || "")) {
      return res.status(403).json({ ok: false, error: "Sessao de seguranca invalida" });
    }
  }

  req.dominiumSession = session;
  next();
});

app.post("/api/auth/logout", (_req, res) => {
  clearSessionCookies(res);
  res.set("cache-control", "no-store").json({ ok: true });
});

app.get("/api/auth/pending-count", async (req, res) => {
  if (!requireRole(req.dominiumSession, ["admin"])) {
    return res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }
  try {
    const users = await adminUsers(req.dominiumSession.accessToken);
    const pendingCount = users.filter((user) => user.status === "pending").length;
    res.set("cache-control", "no-store").json({ ok: true, pending_count: pendingCount });
  } catch {
    res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }
});

app.get("/api/auth/users", async (req, res) => {
  if (!requireRole(req.dominiumSession, ["admin"])) {
    return res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }
  try {
    const users = await adminUsers(req.dominiumSession.accessToken);
    res.set("cache-control", "no-store").json({ ok: true, users });
  } catch {
    res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }
});

app.post(/^\/api\/auth\/users\/\d+\/(approve|reject|imperium-identity)$/, async (req, res) => {
  if (!requireRole(req.dominiumSession, ["admin"])) {
    return res.status(403).json({ ok: false, error: "Esta acao exige um administrador" });
  }

  const match = req.path.match(/^\/api\/auth\/users\/(\d+)\/(approve|reject|imperium-identity)$/);
  if (!match) return res.status(404).json({ ok: false, error: "Operacao invalida" });

  const userId = Number(match[1]);
  const operation = match[2];
  const action = operation === "imperium-identity" ? "link_identity" : operation;

  try {
    const payload = await edgeAuthAction(
      action,
      Object.assign({}, req.body || {}, { user_id: userId }),
      req.dominiumSession.accessToken,
    );
    res.set("cache-control", "no-store").json({
      ok: true,
      user: payload.user || null,
    });
  } catch (error) {
    const status = Number(error?.statusCode || 400);
    res.status(status >= 400 && status < 600 ? status : 400).json({
      ok: false,
      error: String(error?.message || "Falha temporaria na operacao"),
    });
  }
});

app.get("/api/profiles", (_req, res) => {
  res.json({
    ok: true,
    default: "natal",
    profiles: Object.entries(PROFILES).map(([key, item]) => ({
      key,
      label: item.label,
      close_enabled: false,
      official_close_enabled: false,
      material_writeoff_enabled: false,
      native_creation_enabled: false,
      installer_change_enabled: false,
      serialized_transfer_enabled: false,
      native_creation_services: [],
    })),
  });
});

app.get("/api/status", (req, res) => {
  const key = String(req.query.profile || "natal").toLowerCase();
  const profile = PROFILES[key] || PROFILES.natal;
  res.json({
    ok: true,
    label: profile.label,
    company: profile.label,
    close_enabled: false,
    official_close_enabled: false,
    material_writeoff_enabled: false,
    native_creation_enabled: false,
    installer_change_enabled: false,
    serialized_transfer_enabled: false,
    native_creation_services: [],
    default_code: "106",
    codes: [],
    web_mode: true,
    datasnap_read_only: true,
  });
});

app.get("/api/import-targets", (_req, res) => {
  res.json({ ok: true, targets: IMPORT_TARGETS });
});

app.get("/api/toa-automation", (_req, res) => {
  res.json({
    ok: true,
    enabled: false,
    credentials_configured: false,
    running: false,
    times: [],
    next_run: null,
    current_route: "",
    last_run: null,
    routes: [],
    mode: "web",
    message: "Automacao TOA permanece no servidor operacional",
  });
});

app.get("/api/monitor/snapshot", (_req, res) => {
  res.json({ ok: true, active: false, snapshot: null });
});

app.get("/api/toa-live/status", (_req, res) => {
  res.json({
    ok: true,
    connected: false,
    authenticated: false,
    web_remote: true,
    last_error: "Sessao TOA local nao anexada neste backend web",
  });
});

app.get("/api/toa-contracts", (_req, res) => {
  res.json({ ok: true, records: [] });
});

app.get("/api/close-report", (_req, res) => {
  res.json({ ok: true, records: [], summary: {} });
});

app.get("/api/failures", (_req, res) => {
  res.json({ ok: true, failures: [] });
});

app.get("/api/diagnostics", (req, res) => {
  if (!requireRole(req.dominiumSession, ["admin", "controller"])) {
    return res.status(403).json({ ok: false, error: "Esta consulta exige perfil operacional" });
  }
  res.set("cache-control", "no-store").json({
    ok: true,
    credentials_configured: Boolean(getCredentials()),
    host: HOST,
    profiles: Object.keys(PROFILES),
    web_mode: true,
  });
});

app.get("/api/orders", async (req, res) => {
  const profile = String(req.query.profile || "natal").toLowerCase();
  const date = String(req.query.date || new Date().toISOString().slice(0, 10));
  const status = String(req.query.status || "field").toLowerCase();
  const serviceType = String(req.query.service_type || "all").toLowerCase();

  if (!PROFILES[profile]) return res.status(400).json({ ok: false, error: "Perfil invalido" });
  if (!STATUS_VALUES[status]) return res.status(400).json({ ok: false, error: "Status invalido" });
  if (!SERVICE_VALUES[serviceType]) return res.status(400).json({ ok: false, error: "Tipo de servico invalido" });

  try {
    const orders = await listOrders(profile, date, status, serviceType);
    res.set("cache-control", "no-store").json({
      ok: true,
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
    res.status(statusCode).json({
      ok: false,
      error: message === "datasnap_credentials_not_configured"
        ? "Credencial DataSnap do Imperium ainda nao configurada no backend web"
        : "Falha ao consultar o Imperium",
    });
  }
});

app.use(express.static(STATIC_DIR, {
  index: false,
  etag: true,
  maxAge: "5m",
  setHeaders(res, filePath) {
    if (filePath.endsWith(".html")) res.setHeader("Cache-Control", "no-store");
  },
}));

app.use((req, res) => {
  if (req.path.startsWith("/api/")) {
    return res.status(404).json({ ok: false, error: "Rota nao encontrada" });
  }
  res.setHeader("Cache-Control", "no-store");
  res.sendFile(path.join(STATIC_DIR, "index.html"));
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () => {
  console.log("DOMINIUM web backend listening on " + port);
});
