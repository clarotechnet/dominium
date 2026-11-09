/* Controle de baixas — leitura do estado EXISTENTE do worker, sem chamadas TOA.
 * Nenhuma ação de baixa/POST; DOMINIUM auth aplica-se ao endpoint já utilizado.
 */
(() => {
  "use strict";
  const root = document.getElementById("closeControlWorkspace");
  const status = document.getElementById("ccWorkerStatus");
  const grid = document.getElementById("ccWorkerMetrics");
  const mossoro = document.getElementById("ccMossoroProductive");
  const refresh = document.getElementById("ccWorkerRefresh");
  if (!root || !status || !grid || !mossoro || !refresh) return;
  let loading = false;
  const create = (tag, content, cls = "") => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (content != null) e.textContent = String(content);
    return e;
  };
  function card(label, value, focus = false) {
    const e = create("div", null, "cc-worker-metric" + (focus ? " focus" : ""));
    e.append(create("span",label),create("strong",value));
    return e;
  }
  function printDate(value) {
    const d = new Date(value || "");
    return Number.isFinite(d.getTime()) ? d.toLocaleString("pt-BR") : "data indisponível";
  }
  function render(state) {
    grid.replaceChildren();
    grid.append(
      card("Produtivas guardadas · total", state.productiveCacheCount),
      card("Mossoró · em cache", state.profiles.mossoro.productiveCached, true),
      card("Mossoró · candidatas improdutivas", state.profiles.mossoro.candidates, true),
      card("Mossoró · baixas registradas no último ciclo", state.profiles.mossoro.closed, true)
    );
    const list = state.entries
      .filter(item => item.kind === "productive_ignored" && item.profile === "mossoro");
    mossoro.replaceChildren();
    if (!list.length) mossoro.append(create("p",
      "Nenhuma produtiva de Mossoró guardada na amostra atual. A captura existente pode estar vazia ou expirada.",
      "cc-subtle"));
    for (const entry of list) {
      const item = create("article", null, "cc-product-card");
      const valid = Number.isFinite(new Date(entry.expiresAt).getTime())
        && new Date(entry.expiresAt).getTime() > Date.now();
      item.append(
        create("strong", "Contrato " + (entry.contract || "não informado")),
        create("span", "O.S. " + (entry.os || "não informada")),
        create("small", "Código capturado: " + (entry.code || "não informado")),
        create("small", valid ? "Em cache · não autorizada para baixa" : "Cache vencido · exige nova validação"),
        create("small", "Capturada: " + printDate(entry.cachedAt))
      );
      mossoro.append(item);
    }
    status.textContent = "Fonte: worker existente do DOMINIUM · última rodada " +
      printDate(state.updatedAt) + " · " +
      (state.running ? "worker em execução" : state.enabled ? "worker habilitado" : "worker pausado") +
      " · baixa produtiva " + (state.productiveAutoEnabled ? "habilitada (verifique controles)" : "desabilitada") +
      " · consulta somente leitura. Cache não significa O.S. validada.";
  }
  async function load() {
    if (loading || root.classList.contains("hidden")) return;
    const bridge = window.DominiumCloseControlBridge;
    if (typeof bridge?.getWorkerStatus !== "function") {
      status.textContent = "Ponte de monitoramento indisponível nesta versão do DOMINIUM.";
      return;
    }
    loading = true;
    refresh.disabled = true;
    status.textContent = "Consultando estado já registrado pelo worker. Nenhuma pesquisa TOA iniciada.";
    try {
      render(await bridge.getWorkerStatus());
    } catch (err) {
      status.textContent = "Não foi possível consultar o estado do worker. " +
        "Nenhuma baixa foi enviada e os dados anteriores não devem ser considerados atuais.";
      grid.replaceChildren();
      mossoro.replaceChildren(create("p","Dados indisponíveis nesta sessão.","cc-subtle"));
    } finally {
      loading = false;
      refresh.disabled = false;
    }
  }
  refresh.addEventListener("click", load);
  document.addEventListener("dominium:module-change",ev => {
    if (ev.detail?.module === "close-control") {
      // The event precedes the next render; defer until the workspace is visible.
      queueMicrotask(load);
    }
  });
  if (!root.classList.contains("hidden")) queueMicrotask(load);
})();
