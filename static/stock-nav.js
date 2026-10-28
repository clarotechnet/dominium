/* Navegacao consolidada de Estoque (mantem os modulos existentes). */
(() => {
  const group = document.getElementById("stockGroupToggle");
  const children = document.getElementById("stockNavChildren");
  const inventory = document.getElementById("stockModule");
  const serials = document.getElementById("serialsModule");
  const quality = document.getElementById("stockQualityModule");
  const daily = document.getElementById("stockDailyModule");
  const dailyTab = document.getElementById("stockDailyTab");
  const inventoryTab = document.getElementById("stockInventoryTab");
  const qualityTab = document.getElementById("stockQualityTab");
  const inventoryPane = document.getElementById("stockInventoryPane");
  const qualityPane = document.getElementById("stockQualityPane");
  const dailyPane = document.getElementById("stockDailyPane");
  if (!group || !children || !inventory || !serials || !quality || !inventoryTab || !qualityTab) return;

  function expand(open) {
    group.setAttribute("aria-expanded", String(open));
    children.hidden = !open;
  }
  function isQuality() {
    return state.activeModule === "stock" && qualityTab.getAttribute("aria-selected") === "true";
  }
  function exclusiveTab() {
    const views = [
      { name: "inventory", tab: inventoryTab, pane: inventoryPane },
      { name: "quality", tab: qualityTab, pane: qualityPane },
      { name: "daily", tab: dailyTab, pane: dailyPane },
    ].filter((view) => view.tab && view.pane);
    // Visible pane is authoritative; a stale .active class is not.
    const chosen = views.find((view) => !view.pane.classList.contains("hidden"))
      || views.find((view) => view.tab.getAttribute("aria-selected") === "true")
      || views[0];
    for (const view of views) {
      const active = view === chosen;
      view.tab.classList.toggle("active", active);
      view.tab.setAttribute("aria-selected", String(active));
      view.pane.classList.toggle("hidden", !active);
    }
    return chosen.name;
  }
  function updateHighlight() {
    const selected = exclusiveTab();
    const stockActive = state.activeModule === "stock";
    const serialActive = state.activeModule === "serials";
    const qcActive = stockActive && selected === "quality";
    const dailyActive = stockActive && selected === "daily";
    group.classList.toggle("active", stockActive || serialActive);
    inventory.classList.toggle("active", stockActive && !qcActive && !dailyActive);
    daily?.classList.toggle("active", dailyActive);
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
    if (state.activeModule !== "stock") inventory.click();
    qualityTab.click();
    updateHighlight();
  });
  serials.addEventListener("click", updateHighlight);
  daily?.addEventListener("click", () => {
    if (state.activeModule !== "stock") inventory.click();
    dailyTab?.click();
    updateHighlight();
  });
  dailyTab?.addEventListener("click", updateHighlight);
  inventoryTab.addEventListener("click", () => {
    setQualityAddress(false);
    updateHighlight();
  });
  qualityTab.addEventListener("click", () => {
    setQualityAddress(true);
    updateHighlight();
  });
  document.addEventListener("dominium:module-change", updateHighlight);
  document.addEventListener("dominium:stock-tab-change", updateHighlight);
  window.DominiumStockNavigation = { sync: updateHighlight };
  window.addEventListener("hashchange", () => {
    if (window.location.hash === "#controle-qualidade") qualityTab.click();
    if (window.location.hash === "#estoque-diario") dailyTab?.click();
    updateHighlight();
  });
  if (window.location.hash === "#controle-qualidade") qualityTab.click();
  if (window.location.hash === "#estoque-diario") dailyTab?.click();
  updateHighlight();
})();