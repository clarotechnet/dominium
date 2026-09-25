document.documentElement.dataset.theme = "dark";

try {
  localStorage.setItem("dominium-theme", "dark");
} catch (_) {
  // Storage can be unavailable in hardened browser contexts.
}

document.documentElement.classList.add("auth-pending");
