/* Visão de quatro operações, somente leitura: nenhuma alteração de perfil global. */
(function (scope) {
  "use strict";
  const SOURCES = ["imperium", "toa"];
  const makeRequestJobs = (profiles, date, apiUrl) => profiles.flatMap((p) => [
    { key: p.key, source: "imperium",
      url: apiUrl("/api/orders?status=field&service_type=all&date=" + encodeURIComponent(date), p.key) },
    { key: p.key, source: "toa",
      url: apiUrl("/api/toa-contracts?date=" + encodeURIComponent(date), p.key) },
  ]);
  function validatePayload(source, payload) {
    const key = source === "imperium" ? "orders" : "records";
    if (!Array.isArray(payload?.[key])) throw new Error("Fonte sem dados válidos: " + source);
    return payload[key];
  }
  const sourceSummary = (source) => source?.status === "ok"
    ? String(source.rows.length)
    : source?.status === "error" ? "Indisponível" : "Carregando...";
  function el(tag, txt, css) {
    const n = document.createElement(tag);
    if (txt !== undefined) n.textContent = String(txt);
    if (css) n.className = css;
    return n;
  }
  let context, profiles = [], runId = 0, chosen = "imperium", installed = false;
  const $ = (id) => document.getElementById(id);
  const active = (id) => runId === id && !$("allOperationsWorkspace").classList.contains("hidden");
  function openCity(key) { context?.onOpenProfile(key); }
  function renderCards() {
    const frag = document.createDocumentFragment();
    profiles.forEach((p) => {
      const card = el("article", undefined, "all-ops-card");
      const head = el("div", undefined, "all-ops-card-head");
      head.append(el("h3", p.label));
      const open = el("button", "Abrir operação", "button secondary");
      open.type = "button";
      open.addEventListener("click", () => openCity(p.key));
      head.append(open);
      card.append(head);
      SOURCES.forEach((source) => {
        const data = p[source];
        const line = el("div", undefined, "all-ops-source");
        line.append(el("span", source === "imperium" ? "Imperium • OS em campo" : "TOA • contratos na agenda"));
        line.append(el("strong", sourceSummary(data)));
        card.append(line);
        if (data.status === "error") card.append(el("small",
          "Não foi possível consultar " + source.toUpperCase() + ": " + data.error, "all-ops-error"));
      });
      frag.append(card);
    });
    $("allOperationsCards").replaceChildren(frag);
  }
  function renderMetrics() {
    const frag = document.createDocumentFragment();
    SOURCES.forEach((source) => {
      const sources = profiles.map((p) => p[source]);
      const confirmed = sources.filter((x) => x.status === "ok");
      const complete = confirmed.length === sources.length;
      const card = el("article", undefined, "all-ops-metric");
      card.append(el("span", source === "imperium" ? "Imperium • OS em campo" : "TOA • agenda do dia"));
      card.append(el("strong", complete
        ? confirmed.reduce((sum, x) => sum + x.rows.length, 0).toLocaleString("pt-BR") : "—"));
      card.append(el("small", confirmed.length + " de " + sources.length
        + " praças confirmadas" + (complete ? "" : " • total indisponível")));
      frag.append(card);
    });
    $("allOperationsMetrics").replaceChildren(frag);
  }
  function renderTable() {
    const term = $("allOperationsSearch").value.trim().toLocaleLowerCase("pt-BR");
    const head = el("tr");
    const imperium = chosen === "imperium";
    (imperium ? ["Operação", "OS", "Contrato", "Serviço", "Técnico", "Situação", "Ação"]
      : ["Operação", "Contrato", "Janela", "Origem", "Ação"])
      .forEach((name) => head.append(el("th", name)));
    $("allOperationsTableHead").replaceChildren(head);
    const all = profiles.flatMap((p) => p[chosen].status !== "ok" ? []
      : p[chosen].rows.map((r) => ({ record: r, profile: p })));
    const matched = term ? all.filter(({ record, profile }) =>
      [profile.label, ...Object.values(record)].some((value) =>
        String(value ?? "").toLocaleLowerCase("pt-BR").includes(term))) : all;
    const frag = document.createDocumentFragment();
    matched.slice(0, 400).forEach(({ record: r, profile: p }) => {
      const row = el("tr");
      const values = imperium
        ? [p.label, r.num_os || r.id_os || "—", r.contract || "—", r.service || "—",
          r.technician || "—", r.status || "—"]
        : [p.label, r.contract || "—", r.window || r.windows?.[0] || "—",
          r.agenda_only ? "Importação manual" : "Agenda TOA"];
      values.forEach((value) => row.append(el("td", value)));
      const action = el("td");
      const open = el("button", "Abrir cidade", "button secondary");
      open.type = "button";
      open.addEventListener("click", () => openCity(p.key));
      action.append(open);
      row.append(action);
      frag.append(row);
    });
    $("allOperationsTableBody").replaceChildren(frag);
    $("allOperationsTableInfo").textContent = Math.min(matched.length, 400) + " de "
      + matched.length + " registros exibidos"
      + (profiles.every((p) => p[chosen].status === "ok") ? ""
        : " • Parcial: algumas fontes estão pendentes ou indisponíveis.");
  }
  function render() {
    renderCards(); renderMetrics(); renderTable();
    const completed = profiles.reduce((sum, p) =>
      sum + SOURCES.filter((s) => p[s].status !== "pending").length, 0);
    const failed = profiles.reduce((sum, p) =>
      sum + SOURCES.filter((s) => p[s].status === "error").length, 0);
    $("allOperationsStatus").textContent = completed < profiles.length * 2
      ? "Consultando as fontes separadamente: " + completed + " de " + profiles.length * 2 + "."
      : failed ? "Consulta parcial: " + failed + " fonte(s) indisponível(is). Totais incompletos ocultos."
        : "Todas as praças consultadas para a data selecionada.";
  }
  async function reload() {
    if (!context) return;
    const date = $("allOperationsDate").value;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
    const id = ++runId;
    profiles = context.profiles.map((p) => ({ key: p.key, label: p.label,
      imperium: { status: "pending", rows: [], error: "" },
      toa: { status: "pending", rows: [], error: "" } }));
    render();
    const jobs = makeRequestJobs(context.profiles, date, context.apiUrlForProfile);
    let next = 0;
    async function worker() {
      while (next < jobs.length && active(id)) {
        const job = jobs[next++];
        const target = profiles.find((p) => p.key === job.key)?.[job.source];
        try {
          const payload = await context.request(job.url, { timeoutMs: 90000 });
          if (!active(id)) return;
          target.rows = validatePayload(job.source, payload);
          target.status = "ok";
        } catch (error) {
          if (!active(id)) return;
          target.error = String(error?.message || "Sem resposta").slice(0, 160);
          target.status = "error";
        }
        if (active(id)) render();
      }
    }
    await Promise.all([worker(), worker()]);
  }
  function activate(next) {
    context = next;
    if (!$("allOperationsDate").value) $("allOperationsDate").value = next.date;
    if (!installed) {
      installed = true;
      $("allOperationsRefresh").addEventListener("click", () => { void reload(); });
      $("allOperationsDate").addEventListener("change", () => { void reload(); });
      $("allOperationsSearch").addEventListener("input", renderTable);
      SOURCES.forEach((source) => {
        const button = $("allOperationsFilter" + (source === "toa" ? "Toa" : "Imperium"));
        button.addEventListener("click", () => {
          chosen = source;
          $("allOperationsFilterImperium").classList.toggle("active", source === "imperium");
          $("allOperationsFilterToa").classList.toggle("active", source === "toa");
          renderTable();
        });
      });
    }
    void reload();
  }
  const api = { activate, makeRequestJobs, validatePayload, sourceSummary };
  scope.DominiumAllOperations = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window === "undefined" ? globalThis : window);
