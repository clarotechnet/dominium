// =============================================================================
// DOMINIUM | MAPA DE RESPONSABILIDADE
//
// IMPERIUM
// - NAO DIRETO - infraestrutura comum, sem regra de negocio Imperium.
//
// TOA
// - NAO DIRETO - infraestrutura comum, sem regra de negocio TOA.
//
// DOMINIUM COMPARTILHADO
// - SIM - seguranca, interface, voz, empacotamento ou inicializacao.
//
// Categoria deste arquivo: COMPARTILHADO.
// Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
// A ordem executavel abaixo foi preservada para evitar regressao.
// =============================================================================
function stagger(seconds) {
  return (_element, index) => seconds * index;
}

function animationFrames(properties) {
  const values = Object.values(properties);
  const length = Math.max(1, ...values.map((value) => (Array.isArray(value) ? value.length : 1)));
  return Array.from({ length }, (_, index) => {
    const frame = {};
    const at = (key, fallback) => {
      const value = properties[key];
      if (Array.isArray(value)) return value[Math.min(index, value.length - 1)];
      return value === undefined ? fallback : value;
    };
    if (properties.opacity !== undefined) frame.opacity = at("opacity", 1);
    if (properties.height !== undefined) frame.height = `${at("height", 0)}px`;
    if (properties.y !== undefined || properties.scale !== undefined) {
      frame.transform = `translateY(${at("y", 0)}px) scale(${at("scale", 1)})`;
    }
    return frame;
  });
}

function animate(targets, properties, options = {}) {
  const elements = targets instanceof Element ? [targets] : [...(targets || [])];
  const players = elements.map((element, index) => element.animate(
    animationFrames(properties),
    {
      duration: Number(options.duration || 0) * 1000,
      delay: Number(typeof options.delay === "function" ? options.delay(element, index) : options.delay || 0) * 1000,
      easing: options.easing || "linear",
      fill: "forwards",
    },
  ));
  return {
    finished: Promise.all(players.map((player) => player.finished.catch(() => undefined))),
  };
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let lastAutomationSignature = "";
let lastToaSignature = "";
let lastToaStatus = "";

function enabled() {
  return !reducedMotion.matches;
}

function visibleWorkspace() {
  return document.querySelector(
    "main > section:not(.hidden), main .dashboard-workspace:not(.hidden), main .close-workspace:not(.hidden)",
  );
}

function enterWorkspace() {
  if (!enabled()) return;
  const workspace = visibleWorkspace();
  if (!workspace) return;
  animate(
    workspace,
    { opacity: [0.72, 1], y: [7, 0] },
    { duration: 0.2, easing: "ease-out" },
  );
}

function revealCards(cards, kind) {
  const elements = [...(cards || [])].filter((item) => item instanceof Element);
  if (!enabled() || !elements.length) return;
  const signature = elements.map((item) => item.textContent?.slice(0, 160)).join("|");
  if (kind === "automation") {
    if (signature === lastAutomationSignature) return;
    lastAutomationSignature = signature;
  } else {
    if (signature === lastToaSignature) return;
    lastToaSignature = signature;
  }
  animate(
    elements,
    { opacity: [0, 1], y: [8, 0] },
    { duration: 0.22, delay: stagger(0.035), easing: "ease-out" },
  );
}

async function toggleDetails(details, expanded) {
  if (!details) return;
  if (!enabled()) {
    details.hidden = !expanded;
    return;
  }
  details.style.overflow = "hidden";
  if (expanded) {
    details.hidden = false;
    const height = details.scrollHeight;
    await animate(
      details,
      { height: [0, height], opacity: [0, 1] },
      { duration: 0.2, easing: "ease-out" },
    ).finished;
    details.style.height = "auto";
    details.style.overflow = "";
    return;
  }
  await animate(
    details,
    { height: [details.scrollHeight, 0], opacity: [1, 0] },
    { duration: 0.16, easing: "ease-in" },
  ).finished;
  details.hidden = true;
  details.style.height = "";
  details.style.opacity = "";
  details.style.overflow = "";
}

function animateStatus(element, kind) {
  if (!enabled() || !element || kind === lastToaStatus) return;
  lastToaStatus = kind;
  animate(
    element,
    { opacity: [0.55, 1], scale: [0.985, 1] },
    { duration: 0.18, easing: "ease-out" },
  );
}

document.addEventListener("dominium:module-change", enterWorkspace);
document.addEventListener("dominium:automation-results", (event) => {
  revealCards(event.detail?.cards, "automation");
});
document.addEventListener("dominium:toa-results", (event) => {
  revealCards(event.detail?.cards, "toa");
});
document.addEventListener("dominium:toa-status", (event) => {
  animateStatus(event.detail?.element, event.detail?.kind || "");
});

let operationHud;
let operationHudHideTimer;
let activeOperationToken = "";

function ensureOperationHud() {
  if (operationHud?.isConnected) return operationHud;

  const hud = document.createElement("aside");
  hud.className = "operation-orb-hud hidden";
  hud.id = "operationOrbHud";
  hud.setAttribute("role", "status");
  hud.setAttribute("aria-live", "polite");
  hud.setAttribute("aria-atomic", "true");

  const visual = document.createElement("div");
  visual.className = "operation-orb-visual";
  visual.setAttribute("aria-hidden", "true");

  const orb = document.createElement("div");
  orb.className = "thinking-orb";
  ["a", "b", "c"].forEach((name) => {
    const ring = document.createElement("span");
    ring.className = `orb-ring orb-ring-${name}`;
    orb.append(ring);
  });

  const cloud = document.createElement("span");
  cloud.className = "orb-particle-cloud";
  const particleCount = 28;
  for (let index = 0; index < particleCount; index += 1) {
    const particle = document.createElement("i");
    particle.className = "orb-particle";
    const angle = (index / particleCount) * Math.PI * 2;
    const band = ((index * 7) % 11) / 10;
    const radius = 13 + (band * 23);
    particle.style.setProperty("--orb-x", (Math.cos(angle) * radius).toFixed(2));
    particle.style.setProperty("--orb-y", (Math.sin(angle) * radius * (0.58 + (band * 0.28))).toFixed(2));
    particle.style.setProperty("--orb-delay", `${-(index * 43)}ms`);
    particle.style.setProperty("--orb-scale", (0.62 + (band * 0.72)).toFixed(2));
    cloud.append(particle);
  }
  orb.append(cloud);

  const core = document.createElement("span");
  core.className = "orb-core";
  const glyph = document.createElement("span");
  glyph.className = "orb-core-glyph";
  core.append(glyph);
  orb.append(core);
  visual.append(orb);

  const copy = document.createElement("div");
  copy.className = "operation-orb-copy";
  const eyebrow = document.createElement("span");
  eyebrow.className = "operation-orb-eyebrow";
  eyebrow.textContent = "DOMINIUM EM AÇÃO";
  const label = document.createElement("strong");
  label.className = "operation-orb-label";
  const detail = document.createElement("small");
  detail.className = "operation-orb-detail";
  copy.append(eyebrow, label, detail);

  hud.append(visual, copy);
  document.body.append(hud);
  operationHud = hud;
  return hud;
}

function renderOperationState(payload = {}) {
  const hud = ensureOperationHud();
  const phase = ["searching", "working", "solving", "busy", "success", "error"].includes(payload.phase)
    ? payload.phase
    : "working";
  clearTimeout(operationHudHideTimer);

  if (["searching", "working", "solving"].includes(phase)) {
    activeOperationToken = payload.token || activeOperationToken;
  } else if (payload.token && activeOperationToken && payload.token !== activeOperationToken) {
    return;
  }

  hud.dataset.phase = phase;
  hud.querySelector(".operation-orb-label").textContent = payload.label || "Processando operação";
  hud.querySelector(".operation-orb-detail").textContent = payload.detail || (
    phase === "searching" ? "Buscando dados em tempo real"
      : phase === "working" ? "Executando a etapa solicitada"
        : phase === "solving" ? "Validando respostas e consistência"
          : phase === "busy" ? "Outra rotina segura está usando o Imperium"
            : phase === "success" ? "Operação confirmada"
              : "A operação precisa de atenção"
  );
  hud.querySelector(".orb-core-glyph").textContent = phase === "success" ? "✓" : phase === "error" ? "×" : phase === "busy" ? "…" : "";
  hud.classList.remove("hidden", "operation-orb-leaving");
  hud.classList.add("operation-orb-visible");

  if (phase === "success" || phase === "error" || phase === "busy") {
    const delay = phase === "success" ? 1100 : phase === "busy" ? 1450 : 1800;
    operationHudHideTimer = window.setTimeout(() => {
      if (payload.token && activeOperationToken && payload.token !== activeOperationToken) return;
      hud.classList.add("operation-orb-leaving");
      window.setTimeout(() => {
        hud.classList.add("hidden");
        hud.classList.remove("operation-orb-visible", "operation-orb-leaving");
        activeOperationToken = "";
      }, 320);
    }, delay);
  }
}

document.addEventListener("dominium:operation-state", (event) => {
  renderOperationState(event.detail || {});
});

document.addEventListener("pointerover", (event) => {
  if (!enabled() || event.pointerType === "touch") return;
  const button = event.target.closest("button:not(:disabled)");
  if (!button || button.contains(event.relatedTarget)) return;
  animate(button, { scale: 1.012 }, { duration: 0.1 });
});

document.addEventListener("pointerout", (event) => {
  if (!enabled() || event.pointerType === "touch") return;
  const button = event.target.closest("button:not(:disabled)");
  if (!button || button.contains(event.relatedTarget)) return;
  animate(button, { scale: 1 }, { duration: 0.1 });
});

globalThis.DOMINIUM_MOTION = {
  toggleDetails,
  operation(payload = {}) {
    renderOperationState(payload);
  },
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", enterWorkspace, { once: true });
} else {
  enterWorkspace();
}
