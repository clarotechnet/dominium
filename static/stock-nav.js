/* Navegacao consolidada de Estoque (mantem os modulos existentes). */
(() => {
  const group = document.getElementById("stockGroupToggle");
  const children = document.getElementById("stockNavChildren");
  const inventory = document.getElementById("stockModule");
  const serials = document.getElementById("serialsModule");
  const quality = document.getElementById("stockQualityModule");
  const inventoryTab = document.getElementById("stockInventoryTab");
  const qualityTab = document.getElementById("stockQualityTab");
  if (!group || !children || !inventory || !serials || !quality || !inventoryTab || !qualityTab) return;

  function expand(open) {
    group.setAttribute("aria-expanded", String(open));
    children.hidden = !open;
  }
  function isQuality() {
    return state.activeModule === "stock" && qualityTab.getAttribute("aria-selected") === "true";
  }
  function updateHighlight() {
    const stockActive = state.activeModule === "stock";
    const serialActive = state.activeModule === "serials";
    const qcActive = isQuality();
    group.classList.toggle("active", stockActive || serialActive);
    inventory.classList.toggle("active", stockActive && !qcActive);
    quality.classList.toggle("active", qcActive);
    serials.classList.toggle("active", serialActive);
    if (stockActive || serialActive) expand(true);
  }
  function setQualityAddress(active) {
    if (state.activeModule !== "stock") return;
    const target = active ? "#controle-qualidade" : "#estoque";
    if (window.location.hash !== target) {
      const url = new URL(window.location.href);
      url.hash = target;
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  }
  group.addEventListener("click", () => expand(children.hidden));
  inventory.addEventListener("click", () => {
    inventoryTab.click();
    updateHighlight();
  });
  quality.addEventListener("click", () => {
    inventory.click();
    qualityTab.click();
    updateHighlight();
  });
  serials.addEventListener("click", updateHighlight);
  inventoryTab.addEventListener("click", () => {
    setQualityAddress(false);
    updateHighlight();
  });
  qualityTab.addEventListener("click", () => {
    setQualityAddress(true);
    updateHighlight();
  });
  document.addEventListener("dominium:module-change", updateHighlight);
  window.addEventListener("hashchange", () => {
    if (window.location.hash === "#controle-qualidade") qualityTab.click();
    updateHighlight();
  });
  if (window.location.hash === "#controle-qualidade") qualityTab.click();
  updateHighlight();
})();