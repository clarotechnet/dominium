import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const EDGE_KEY_HASHES = new Set([
  "f2ba8a5fc5d118bb7b1c35ac2e90555baacbc6d1e3b1eab8022b405721e9bd6c",
  "1e0b8e5f7841138b0f0cc73a63a68da14c12f0402515f8cf56e836b14125bb7d",
]);
const AUTH_EMAIL_DOMAIN = "auth.dominium.invalid";
const VALID_ROLES = new Set(["admin", "controller", "viewer"]);
const PROFILE_CONFIG: Record<string, number> = {
  natal: 313101,
  fortaleza: 49127,
  mossoro: 20857,
  recife: 1766,
};

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { autoRefreshToken: false, persistSession: false },
});

async function validEdgeKey(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return EDGE_KEY_HASHES.has(hex);
}

function json(data: unknown, status = 200) {
  return Response.json(data, {
    status,
    headers: {
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function normalizeUsername(value: unknown) {
  const username = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{2,47}$/.test(username)) {
    throw new Error("Use de 3 a 48 caracteres: letras, numeros, ponto, hifen ou sublinhado");
  }
  return username;
}

function validatePassword(value: unknown, username: string) {
  const password = String(value || "");
  if (password.length < 6 || password.length > 128) {
    throw new Error("A senha do DOMINIUM deve ter entre 6 e 128 caracteres");
  }
  if (password.toLowerCase() === username.toLowerCase()) {
    throw new Error("A senha nao pode ser igual ao usuario");
  }
  return password;
}

function normalizeName(body: any) {
  const first = String(body?.first_name || "").trim().replace(/\s+/g, " ");
  const last = String(body?.last_name || "").trim().replace(/\s+/g, " ");
  const fallback = String(body?.display_name || "").trim().replace(/\s+/g, " ");
  const display = (first || last) ? `${first} ${last}`.trim() : fallback;
  if (display.length < 3 || display.length > 80) {
    throw new Error("Informe o nome do operador, entre 3 e 80 caracteres");
  }
  return display;
}

function normalizeContactEmail(value: unknown) {
  const email = String(value || "").trim();
  if (!email) return null;
  if (email.length > 320 || !/^[^@\s]{1,64}@[^@\s]{1,253}$/.test(email)) {
    throw new Error("Formato de e-mail de contato invalido");
  }
  return email;
}

async function fetchPublicUser(userId: number) {
  const { data: profile, error } = await admin
    .from("dominium_profiles")
    .select("*")
    .eq("id", userId)
    .maybeSingle();
  if (error || !profile) throw new Error("Usuario nao encontrado");

  const { data: identities, error: identityError } = await admin
    .from("dominium_imperium_identities")
    .select("profile_key,imperium_username,controller_id,verified_at")
    .eq("user_id", userId);
  if (identityError) throw identityError;

  const mapped: Record<string, unknown> = {};
  for (const row of identities || []) {
    mapped[String(row.profile_key)] = {
      linked: true,
      username: String(row.imperium_username),
      controller_id: Number(row.controller_id),
      verified_at: String(row.verified_at || ""),
    };
  }

  return {
    id: Number(profile.id),
    username: String(profile.username),
    display_name: String(profile.display_name),
    role: String(profile.role),
    status: String(profile.status),
    contact_email: profile.contact_email ? String(profile.contact_email) : "",
    created_at: String(profile.created_at || ""),
    approved_at: String(profile.approved_at || ""),
    rejected_at: String(profile.rejected_at || ""),
    rejection_reason: String(profile.rejection_reason || ""),
    last_login_at: String(profile.last_login_at || ""),
    imperium_identities: mapped,
    imperium_identity: {
      linked: Object.keys(mapped).length > 0,
      profiles: Object.keys(mapped).sort(),
    },
  };
}

async function requireAdmin(req: Request, body: any = {}) {
  const bridgeActorId = Number(body?.actor_user_id);
  if (Number.isInteger(bridgeActorId) && bridgeActorId > 0) {
    const { data: bridgeProfile, error: bridgeError } = await admin
      .from("dominium_profiles")
      .select("id,username,role,status")
      .eq("id", bridgeActorId)
      .maybeSingle();
    if (bridgeError || !bridgeProfile || bridgeProfile.role !== "admin" || bridgeProfile.status !== "active") {
      throw new Error("forbidden");
    }
    return bridgeProfile;
  }
  const authHeader = req.headers.get("authorization") || "";
  const token = authHeader.toLowerCase().startsWith("bearer ")
    ? authHeader.slice(7).trim()
    : "";
  if (!token) throw new Error("unauthorized");

  const { data: authData, error: authError } = await admin.auth.getUser(token);
  if (authError || !authData.user) throw new Error("unauthorized");

  const { data: profile, error: profileError } = await admin
    .from("dominium_profiles")
    .select("id,username,role,status")
    .eq("auth_user_id", authData.user.id)
    .maybeSingle();

  if (
    profileError ||
    !profile ||
    profile.role !== "admin" ||
    profile.status !== "active"
  ) {
    throw new Error("forbidden");
  }
  return profile;
}

async function audit(
  actor: any,
  action: string,
  result: string,
  target = "",
  metadata: Record<string, unknown> = {},
) {
  try {
    await admin.from("dominium_operator_audit").insert({
      user_id: actor?.id ?? null,
      username: String(actor?.username || "system"),
      action,
      result,
      request_id: "",
      channel: "dominium-web",
      target,
      technician: "",
      external_actor: "",
      metadata_json: JSON.stringify(metadata),
    });
  } catch {
    // Audit failure must not expose internals to the caller.
  }
}

async function register(body: any) {
  const username = normalizeUsername(body?.username);
  const password = validatePassword(body?.password, username);
  const displayName = normalizeName(body);
  const contactEmail = normalizeContactEmail(body?.contact_email);

  const { data: existing } = await admin
    .from("dominium_profiles")
    .select("id")
    .eq("username", username)
    .maybeSingle();
  if (existing) throw new Error("Este usuario ja foi cadastrado");

  const syntheticEmail = `${username}@${AUTH_EMAIL_DOMAIN}`;
  const { data: created, error: createError } = await admin.auth.admin.createUser({
    email: syntheticEmail,
    password,
    email_confirm: true,
    user_metadata: {
      dominium_username: username,
      display_name: displayName,
    },
  });

  if (createError || !created.user) {
    if (String(createError?.message || "").toLowerCase().includes("already")) {
      throw new Error("Este usuario ja foi cadastrado");
    }
    throw new Error("Nao foi possivel criar o cadastro agora");
  }

  try {
    const { data: inserted, error: insertError } = await admin
      .from("dominium_profiles")
      .insert({
        auth_user_id: created.user.id,
        username,
        display_name: displayName,
        role: "viewer",
        status: "pending",
        contact_email: contactEmail,
        created_at: new Date().toISOString(),
      })
      .select("id")
      .single();

    if (insertError || !inserted) throw insertError || new Error("profile_create_failed");
    await audit(
      { id: inserted.id, username },
      "auth.register_request",
      "pending",
      username,
      {},
    );
    return fetchPublicUser(Number(inserted.id));
  } catch (error) {
    await admin.auth.admin.deleteUser(created.user.id).catch(() => {});
    throw error;
  }
}

async function approve(body: any, actor: any) {
  const userId = Number(body?.user_id);
  const role = String(body?.role || "viewer").trim().toLowerCase();
  if (!Number.isInteger(userId) || userId <= 0) throw new Error("Usuario invalido");
  if (!VALID_ROLES.has(role)) throw new Error("Cargo invalido");

  const now = new Date().toISOString();
  const { data, error } = await admin
    .from("dominium_profiles")
    .update({
      role,
      status: "active",
      approved_at: now,
      approved_by: actor.id,
      rejected_at: null,
      rejected_by: null,
      rejection_reason: null,
      failed_attempts: 0,
      locked_until: null,
    })
    .eq("id", userId)
    .select("id,username")
    .maybeSingle();
  if (error || !data) throw new Error("Usuario nao encontrado");

  await audit(actor, "auth.user.approve", "success", String(data.username), { role });
  return fetchPublicUser(userId);
}

async function reject(body: any, actor: any) {
  const userId = Number(body?.user_id);
  const reason = String(body?.reason || "").trim().slice(0, 500);
  if (!Number.isInteger(userId) || userId <= 0) throw new Error("Usuario invalido");
  if (userId === Number(actor.id)) throw new Error("Nao e permitido recusar o proprio usuario");

  const now = new Date().toISOString();
  const { data, error } = await admin
    .from("dominium_profiles")
    .update({
      status: "rejected",
      role: "viewer",
      approved_at: null,
      approved_by: null,
      rejected_at: now,
      rejected_by: actor.id,
      rejection_reason: reason || null,
    })
    .eq("id", userId)
    .select("id,username")
    .maybeSingle();
  if (error || !data) throw new Error("Usuario nao encontrado");

  await audit(actor, "auth.user.reject", "success", String(data.username), { reason });
  return fetchPublicUser(userId);
}

async function linkIdentity(body: any, actor: any) {
  const userId = Number(body?.user_id);
  const profileKey = String(body?.profile || "").trim().toLowerCase();
  const imperiumUsername = String(body?.imperium_username || "").trim().toUpperCase();
  const controllerId = PROFILE_CONFIG[profileKey];

  if (!Number.isInteger(userId) || userId <= 0) throw new Error("Usuario invalido");
  if (!controllerId) throw new Error("Base Imperium invalida");
  if (imperiumUsername.length < 2 || imperiumUsername.length > 80) {
    throw new Error("Usuario Imperium invalido");
  }

  const { data: target, error: targetError } = await admin
    .from("dominium_profiles")
    .select("id,username")
    .eq("id", userId)
    .maybeSingle();
  if (targetError || !target) throw new Error("Usuario nao encontrado");

  const { error } = await admin
    .from("dominium_imperium_identities")
    .upsert({
      user_id: userId,
      profile_key: profileKey,
      imperium_username: imperiumUsername,
      controller_id: controllerId,
      verified_at: new Date().toISOString(),
      verified_by: actor.id,
    }, { onConflict: "user_id,profile_key" });
  if (error) throw new Error("Nao foi possivel vincular a identidade Imperium");

  await audit(
    actor,
    "auth.imperium_identity.link",
    "success",
    String(target.username),
    { profile: profileKey, controller_id: controllerId },
  );
  return fetchPublicUser(userId);
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!(await validEdgeKey(req.headers.get("x-dominium-edge-key") || ""))) {
    return json({ ok: false, error: "forbidden" }, 403);
  }

  const body = await req.json().catch(() => ({}));
  const action = String(body?.action || "");

  try {
    if (action === "health") {
      return json({
        ok: true,
        service_role_configured: Boolean(SERVICE_ROLE),
        supabase_url_configured: Boolean(SUPABASE_URL),
      });
    }

    if (action === "register") {
      const user = await register(body);
      return json({ ok: true, authenticated: false, user });
    }

    const actor = await requireAdmin(req, body);
    if (action === "approve") {
      return json({ ok: true, user: await approve(body, actor) });
    }
    if (action === "reject") {
      return json({ ok: true, user: await reject(body, actor) });
    }
    if (action === "link_identity") {
      return json({ ok: true, user: await linkIdentity(body, actor) });
    }

    return json({ ok: false, error: "unknown_action" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : "internal_error";
    if (message === "unauthorized") return json({ ok: false, error: "Entre no DOMINIUM para continuar" }, 401);
    if (message === "forbidden") return json({ ok: false, error: "Esta acao exige um administrador" }, 403);

    const safe = new Set([
      "Use de 3 a 48 caracteres: letras, numeros, ponto, hifen ou sublinhado",
      "A senha do DOMINIUM deve ter entre 6 e 128 caracteres",
      "A senha nao pode ser igual ao usuario",
      "Informe o nome do operador, entre 3 e 80 caracteres",
      "Formato de e-mail de contato invalido",
      "Este usuario ja foi cadastrado",
      "Nao foi possivel criar o cadastro agora",
      "Usuario invalido",
      "Cargo invalido",
      "Usuario nao encontrado",
      "Nao e permitido recusar o proprio usuario",
      "Base Imperium invalida",
      "Usuario Imperium invalido",
      "Nao foi possivel vincular a identidade Imperium",
    ]);
    return json({ ok: false, error: safe.has(message) ? message : "Falha temporaria na operacao" }, 400);
  }
});
