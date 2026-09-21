const express = require("express");
const crypto = require("crypto");
const net = require("net");
const fs = require("fs");
const path = require("path");

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

const SUPABASE_URL = String(process.env.SUPABASE_URL || "").trim().replace(/\/+$/, "");
const SUPABASE_PUBLISHABLE_KEY = String(process.env.SUPABASE_PUBLISHABLE_KEY || "").trim();
const AUTH_EMAIL_DOMAIN = String(process.env.DOMINIUM_AUTH_EMAIL_DOMAIN || "auth.dominium.invalid").trim().toLowerCase();
const SESSION_SECRET = String(process.env.DOMINIUM_SESSION_SECRET || "").trim();
const ACCESS_COOKIE = "__Host-dominium_access";
const REFRESH_COOKIE = "__Host-dominium_refresh";
const CSRF_COOKIE = "__Host-dominium_csrf";
const BIND_COOKIE = "__Host-dominium_bind";
const SESSION_SECONDS = 12 * 60 * 60;
const loginFailures = new Map();

if (!SUPABASE_URL.startsWith("https://")) throw new Error("SUPABASE_URL_missing");
if (!SUPABASE_PUBLISHABLE_KEY) throw new Error("SUPABASE_PUBLISHABLE_KEY_missing");
if (SESSION_SECRET.length < 32) throw new Error("DOMINIUM_SESSION_SECRET_too_short");

function parseCookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie || "").split(";")) {
    const pos = part.indexOf("=");
    if (pos < 0) continue;
    const key = part.slice(0, pos).trim();
    const raw = part.slice(pos + 1).trim();
    if (!key) continue;
    try { out[key] = decodeURIComponent(raw); } catch { out[key] = raw; }
  }
  return out;
}

function appendCookie(res, name, value, maxAge) {
  res.append("Set-Cookie", `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${Math.max(0, Number(maxAge || 0))}`);
}

function clearAuthCookies(res) {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, BIND_COOKIE]) {
    res.append("Set-Cookie", `${name}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`);
  }
}

function digest(value) {
  return crypto.createHash("sha256").update(String(value || ""), "utf8").digest("hex");
}

function equalText(a, b) {
  const left = Buffer.from(String(a || ""));
  const right = Buffer.from(String(b || ""));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function createBinding(req) {
  const payload = Buffer.from(JSON.stringify({ ua: digest(req.headers["user-agent"] || ""), iat: Date.now() })).toString("base64url");
  const sig = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  return `${payload}.${sig}`;
}

function validBinding(req, raw) {
  const [payload, sig] = String(raw || "").split(".", 2);
  if (!payload || !sig) return false;
  const expected = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  if (!equalText(sig, expected)) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    const age = Date.now() - Number(data.iat || 0);
    return equalText(data.ua, digest(req.headers["user-agent"] || "")) && age >= 0 && age <= SESSION_SECONDS * 1000;
  } catch { return false; }
}

function normalizeUsername(value) {
  const username = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{2,47}$/.test(username)) throw new Error("invalid_username");
  return username;
}

function supabaseHeaders(access = "") {
  const headers = { apikey: SUPABASE_PUBLISHABLE_KEY, "content-type": "application/json" };
  if (access) headers.authorization = `Bearer ${access}`;
  return headers;
}

async function supabaseLogin(username, password) {
  const email = `${normalizeUsername(username)}@${AUTH_EMAIL_DOMAIN}`;
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: supabaseHeaders(), body: JSON.stringify({ email, password: String(password || "") }),
  });
  return response.ok ? response.json() : null;
}

async function supabaseRefresh(refreshToken) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
    method: "POST", headers: supabaseHeaders(), body: JSON.stringify({ refresh_token: String(refreshToken || "") }),
  });
  return response.ok ? response.json() : null;
}

async function supabaseRpc(name, access, body = {}) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST", headers: supabaseHeaders(access), body: JSON.stringify(body),
  });
  if (!response.ok) return null;
  return response.json();
}

async function currentProfile(access) {
  const profile = await supabaseRpc("dominium_web_current_profile", access);
  return profile && profile.status === "active" ? profile : null;
}

function installSession(res, req, tokens, csrf = "") {
  const csrfToken = csrf || crypto.randomBytes(32).toString("base64url");
  appendCookie(res, ACCESS_COOKIE, tokens.access_token, Math.max(300, Math.min(Number(tokens.expires_in || 3600), 3600)));
  appendCookie(res, REFRESH_COOKIE, tokens.refresh_token, SESSION_SECONDS);
  appendCookie(res, CSRF_COOKIE, csrfToken, SESSION_SECONDS);
  appendCookie(res, BIND_COOKIE, createBinding(req), SESSION_SECONDS);
  return csrfToken;
}

async function resolveSession(req, res) {
  const cookies = parseCookies(req);
  if (!validBinding(req, cookies[BIND_COOKIE])) {
    if (cookies[ACCESS_COOKIE] || cookies[REFRESH_COOKIE]) clearAuthCookies(res);
    return null;
  }
  let access = cookies[ACCESS_COOKIE] || "";
  let profile = access ? await currentProfile(access) : null;
  if (!profile && cookies[REFRESH_COOKIE]) {
    const fresh = await supabaseRefresh(cookies[REFRESH_COOKIE]);
    if (fresh?.access_token && fresh?.refresh_token) {
      access = fresh.access_token;
      installSession(res, req, fresh, cookies[CSRF_COOKIE] || "");
      profile = await currentProfile(access);
    }
  }
  if (!profile) { clearAuthCookies(res); return null; }
  let csrf = cookies[CSRF_COOKIE] || "";
  if (!csrf) { csrf = crypto.randomBytes(32).toString("base64url"); appendCookie(res, CSRF_COOKIE, csrf, SESSION_SECONDS); }
  return { user: profile, access, csrf };
}

function validCsrf(req, session) {
  if (String(req.method || "GET").toUpperCase() !== "POST") return true;
  return equalText(req.headers["x-csrf-token"] || "", session.csrf || "");
}

app.use((_req, res, next) => {
  res.set({
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests",
  });
  next();
});

app.get("/api/auth/session", async (req, res) => {
  const session = await resolveSession(req, res);
  res.set("cache-control", "no-store").json({
    ok: true, authenticated: Boolean(session), registration_enabled: false, bootstrap_required: false, bootstrap_allowed: false,
    user: session?.user || null, csrf_token: session?.csrf || "",
  });
});

app.post("/api/auth/login", async (req, res) => {
  const username = String(req.body?.username || "").trim();
  const password = String(req.body?.password || "");
  const key = `${String(req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "unknown").split(",")[0]}|${username.toLowerCase()}`;
  const now = Date.now();
  const failure = loginFailures.get(key);
  if (failure && now - failure.started < 300000 && failure.count >= 8) {
    return res.status(429).json({ ok: false, error: "Muitas tentativas. Aguarde alguns minutos." });
  }
  try {
    const tokens = await supabaseLogin(username, password);
    const profile = tokens?.access_token ? await currentProfile(tokens.access_token) : null;
    if (!tokens?.access_token || !tokens?.refresh_token || !profile) {
      const item = failure && now - failure.started < 300000 ? failure : { count: 0, started: now };
      item.count += 1; loginFailures.set(key, item);
      clearAuthCookies(res);
      return res.status(401).json({ ok: false, error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado" });
    }
    loginFailures.delete(key);
    const csrf = installSession(res, req, tokens);
    return res.json({ ok: true, authenticated: true, user: profile, csrf_token: csrf });
  } catch {
    return res.status(401).json({ ok: false, error: "Usuario ou senha invalidos, ou cadastro ainda nao aprovado" });
  }
});

app.post("/api/auth/register", (_req, res) => {
  res.status(403).json({ ok: false, error: "Novos cadastros estao temporariamente desabilitados na versao web." });
});

app.post("/api/auth/logout", async (req, res) => {
  const session = await resolveSession(req, res);
  if (session && !validCsrf(req, session)) return res.status(403).json({ ok: false, error: "Sessao invalida. Atualize a pagina." });
  clearAuthCookies(res);
  res.json({ ok: true });
});

app.use("/api", async (req, res, next) => {
  const session = await resolveSession(req, res);
  if (!session) return res.status(401).json({ ok: false, error: "Entre no DOMINIUM para continuar", authentication_required: true });
  if (!validCsrf(req, session)) return res.status(403).json({ ok: false, error: "Sessao invalida. Atualize a pagina." });
  req.dominiumSession = session;
  next();
});

app.get("/api/auth/pending-count", (req, res) => {
  if (req.dominiumSession?.user?.role !== "admin") return res.status(403).json({ ok: false, error: "Esta consulta exige administrador." });
  res.json({ ok: true, pending_count: 0 });
});

app.get("/api/auth/users", async (req, res) => {
  if (req.dominiumSession?.user?.role !== "admin") return res.status(403).json({ ok: false, error: "Esta consulta exige administrador." });
  const users = await supabaseRpc("dominium_web_admin_users", req.dominiumSession.access);
  res.json({ ok: true, users: Array.isArray(users) ? users : [] });
});

const IMPORT_TARGETS = [
  { key: "rn", label: "RN", profile: "natal", description: "Natal e Parnamirim", routes: ["NTL", "PWM"] },
  { key: "ftz", label: "FTZ", profile: "fortaleza", description: "Rota Fortaleza", routes: ["FTZ"] },
  { key: "jcr", label: "JCR", profile: "recife", description: "Rota Recife", routes: ["JCR"] },
  { key: "mro", label: "MRO", profile: "mossoro", description: "Rota Mossoro", routes: ["MRO"] },
];

app.get("/api/import-targets", (_req, res) => res.json({ ok: true, targets: IMPORT_TARGETS }));

app.get("/api/status", (req, res) => {
  const key = String(req.query.profile || "natal").toLowerCase();
  const profile = PROFILES[key] || PROFILES.natal;
  res.json({
    ok: true, company: profile.label, label: profile.label, profile: key, web_mode: true,
    close_enabled: false, official_close_enabled: false, material_writeoff_enabled: false,
    native_creation_enabled: false, installer_change_enabled: false, serialized_transfer_enabled: false,
    native_creation_services: [], default_code: "106", codes: [],
  });
});

app.get("/api/toa-automation", (_req, res) => res.json({
  ok: true, credentials_configured: false, running: false, current_route: "",
  times: [], next_run: null, last_run: null, history: [],
  routes: IMPORT_TARGETS.flatMap((target) => target.routes.map((route) => ({ route, label: target.description, status: "aguardando" }))),
}));

app.get("/api/toa-live/status", (_req, res) => res.json({
  ok: true, connected: false, authenticated: false, remote: false, busy: false,
  last_error: "TOA local indisponivel nesta etapa da versao web",
}));

app.get("/api/toa-contracts", (_req, res) => res.json({ ok: true, records: [] }));
app.get("/api/close-report", (_req, res) => res.json({
  ok: true, records: [], summary: { confirmed: 0, pending: 0, uncertain: 0, failed: 0 },
}));
app.get("/api/monitor/snapshot", (_req, res) => res.json({ ok: true, available: false, records: [], generated_at: null }));



const publicDir = path.join(__dirname, "public");
app.use(express.static(publicDir, {
  index: false,
  etag: true,
  maxAge: "5m",
}));

app.get("/", (_req, res) => {
  res.set("Cache-Control", "no-store");
  res.sendFile(path.join(publicDir, "index.html"));
});

app.get("/api/auth-test", async (req, res) => {
  if (req.dominiumSession?.user?.role !== "admin") {
    return res.status(403).json({ ok: false, error: "Esta consulta exige administrador." });
  }
  const credentials = getCredentials();
  if (!credentials) {
    return res.status(503).json({ ok: false, error: "datasnap_credentials_not_configured" });
  }

  const requested = String(req.query.profile || "all").toLowerCase();
  const targets = requested === "all"
    ? Object.entries(PROFILES)
    : (PROFILES[requested] ? [[requested, PROFILES[requested]]] : []);

  if (!targets.length) {
    return res.status(400).json({ ok: false, error: "Perfil inválido" });
  }

  const results = [];
  for (const [key, profile] of targets) {
    const started = Date.now();
    const client = new DataSnapClient(
      HOST,
      profile.port,
      credentials.username,
      credentials.password,
      15000,
    );
    try {
      await client.connect();
      results.push({
        profile: key,
        port: profile.port,
        authenticated: true,
        elapsed_ms: Date.now() - started,
      });
    } catch (error) {
      results.push({
        profile: key,
        port: profile.port,
        authenticated: false,
        error: error instanceof Error ? error.message : "datasnap_error",
        elapsed_ms: Date.now() - started,
      });
    } finally {
      client.close();
    }
  }

  res.set("cache-control", "no-store").json({
    ok: results.every((item) => item.authenticated),
    results,
  });
});

app.get("/api/diagnostics", async (req, res) => {
  if (req.dominiumSession?.user?.role !== "admin") {
    return res.status(403).json({ ok: false, error: "Esta consulta exige administrador." });
  }
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

app.use("/api", (_req, res) => {
  res.status(501).json({
    ok: false,
    error: "Funcao ainda nao migrada para a versao web hospedada.",
    category: "WEB_MIGRATION",
  });
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () => {
  console.log("DOMINIUM Hostinger web listening on " + port);
});
