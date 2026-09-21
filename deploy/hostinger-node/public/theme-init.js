try {
  document.documentElement.dataset.theme =
    localStorage.getItem("dominium-theme") || "dark";
} catch (_) {
  document.documentElement.dataset.theme = "dark";
}

document.documentElement.classList.add("auth-pending");
