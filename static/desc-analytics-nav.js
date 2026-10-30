/* Submenu de desconexao, independente dos fluxos de baixa existentes. */
(() => {
  const group = document.getElementById("disconnectionGroupToggle");
  const children = document.getElementById("disconnectionNavChildren");
  const review = document.getElementById("disconnectionModule");
  const analytics = document.getElementById("descAnalyticsModule");
  const backlog = document.getElementById("backlogModule");
  if (!group || !children || !review || !analytics) return;

  function expand(open) {
    group.setAttribute("aria-expanded", String(open));
    children.hidden = !open;
  }
  function updateHighlight() {
    const reviewActive = state.activeModule === "disconnection";
    const analyticsActive = state.activeModule === "descAnalytics";
    const backlogActive = state.activeModule === "backlog";
    group.classList.toggle("active", reviewActive || analyticsActive || backlogActive);
    review.classList.toggle("active", reviewActive);
    analytics.classList.toggle("active", analyticsActive);
    backlog?.classList.toggle("active", backlogActive);
    if (reviewActive || analyticsActive || backlogActive) expand(true);
  }
  group.addEventListener("click", () => expand(children.hidden));
  document.addEventListener("dominium:module-change", updateHighlight);
  window.addEventListener("hashchange", updateHighlight);
  updateHighlight();
})();
