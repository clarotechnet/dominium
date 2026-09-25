// DOMINIUM motion system — command-deck transitions, 2026-09-25
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const transitionTimers = new WeakMap();
let lastAutomationSignature = "";
let lastToaSignature = "";
let lastToaStatus = "";

function motionEnabled() {
  return !reducedMotion.matches;
}

function visibleWorkspace() {
  return document.querySelector(
    "main > section:not(.hidden), main > div:not(.hidden), main .dashboard-workspace:not(.hidden), main .close-workspace:not(.hidden)",
  );
}

function play(element, keyframes, options) {
  if (!motionEnabled() || !(element instanceof Element)) return null;
  try {
    return element.animate(keyframes, { fill: "both", ...options });
  } catch (_) {
    return null;
  }
}

function pulseWorkspaceChrome(workspace) {
  if (!(workspace instanceof Element) || !motionEnabled()) return;
  const previous = transitionTimers.get(workspace);
  if (previous) window.clearTimeout(previous);

  workspace.classList.remove("dominium-transitioning");
  void workspace.offsetWidth;
  workspace.classList.add("dominium-transitioning");

  const timer = window.setTimeout(() => {
    workspace.classList.remove("dominium-transitioning");
    transitionTimers.delete(workspace);
  }, 650);
  transitionTimers.set(workspace, timer);
}

function enterWorkspace() {
  const workspace = visibleWorkspace();
  if (!workspace || !motionEnabled()) return;

  pulseWorkspaceChrome(workspace);
  const heading = workspace.querySelector(".workspace-heading");
  play(heading, [
    { opacity: 0.72, transform: "translateY(-5px)", filter: "blur(2px)" },
    { opacity: 1, transform: "translateY(0)", filter: "blur(0)" },
  ], { duration: 320, easing: "cubic-bezier(.16,1,.3,1)" });

  const groups = [...workspace.querySelectorAll(
    ".dashboard-metrics, .summary, .toolbar, .dashboard-panel, .table-section, .stock-toolbar, .import-toolbar, .bulk-create-form",
  )].slice(0, 6);

  groups.forEach((element, index) => {
    play(element, [
      { opacity: 0.78, transform: "translateY(6px)" },
      { opacity: 1, transform: "translateY(0)" },
    ], {
      duration: 300,
      delay: 34 * index,
      easing: "cubic-bezier(.16,1,.3,1)",
    });
  });
}

function resultSignature(elements) {
  return elements.map((item) => item.textContent?.slice(0, 160) || "").join("|");
}

function revealCards(cards, kind) {
  const elements = [...(cards || [])].filter((item) => item instanceof Element);
  if (!motionEnabled() || !elements.length) return;

  const signature = resultSignature(elements);

  if (kind === "automation") {
    if (signature === lastAutomationSignature) return;
    lastAutomationSignature = signature;
  } else {
    if (signature === lastToaSignature) return;
    lastToaSignature = signature;
  }

  elements.forEach((element, index) => {
    play(element, [
      { opacity: 0, transform: "translateY(8px)", filter: "blur(3px)" },
      { opacity: 1, transform: "translateY(0)", filter: "blur(0)" },
    ], {
      duration: 300,
      delay: 32 * index,
      easing: "cubic-bezier(.16,1,.3,1)",
    });
  });
}

async function toggleDetails(details, expanded) {
  if (!(details instanceof Element)) return;
  if (!motionEnabled()) {
    details.hidden = !expanded;
    return;
  }
  details.style.overflow = "hidden";
  if (expanded) {
    details.hidden = false;
    const player = play(details, [
      { opacity: 0, transform: "translateY(-5px)", clipPath: "inset(0 0 100% 0)" },
      { opacity: 1, transform: "translateY(0)", clipPath: "inset(0 0 0 0)" },
    ], { duration: 240, easing: "cubic-bezier(.16,1,.3,1)" });
    await player?.finished.catch(() => undefined);
    details.style.overflow = "";
    return;
  }

  const player = play(details, [
    { opacity: 1, transform: "translateY(0)", clipPath: "inset(0 0 0 0)" },
    { opacity: 0, transform: "translateY(-4px)", clipPath: "inset(0 0 100% 0)" },
  ], { duration: 180, easing: "cubic-bezier(.4,0,1,1)" });
  await player?.finished.catch(() => undefined);
  details.hidden = true;
  details.style.overflow = "";
}

function animateStatus(element, kind) {
  if (!motionEnabled() || !(element instanceof Element) || kind === lastToaStatus) return;
  lastToaStatus = kind;
  play(element, [
    { opacity: 0.58, transform: "scale(.992)", filter: "brightness(.82)" },
    { opacity: 1, transform: "scale(1)", filter: "brightness(1)" },
  ], { duration: 260, easing: "cubic-bezier(.16,1,.3,1)" });
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

globalThis.DOMINIUM_MOTION = { toggleDetails };

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", enterWorkspace, { once: true });
} else {
  enterWorkspace();
}
