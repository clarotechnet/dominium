(() => {
  "use strict";
  const el = id => document.getElementById(id);
  if (!el("materialAuditPanel")) return;
  const uri = "/api/stock/analyses/material-audit";
  const batchSize = 50;
  const labels = {
    conferiu: "Conferiu",
    codigo_ausente: "Código ausente",
    saldo_insuficiente: "Saldo insuficiente",
    sem_referencia: "Sem referência",
    local_sem_vinculo: "Local sem vínculo",
    dados_incompletos: "Dados incompletos",
    data_sem_confirmacao: "Data sem confirmação",
    anterior_ao_estoque_salvo: "Baixa anterior à coleta",
    unidade_ambigua: "Unidade precisa de revisão",
    ordem_sem_confirmacao: "Lançamentos no mesmo horário",
  };
  let capture = null, report = null, page = 0, busy = false, timer;
  let todayLabel = "", previousReady = false, activeScope = "";
  const city = () => state.allCities ? "" : state.profile;
  const write = () => ["admin", "controller"].includes(state.authUser?.role);
  const number = value => value == null ? "—" : Number(value).toLocaleString("pt-BR", {maximumFractionDigits: 6});
  const date = value => value?.split("-").reverse().join("/") || "";
  const time = value => value ? new Date(value).toLocaleTimeString("pt-BR", {timeZone:"America/Sao_Paulo"}) : "";
  const status = (message, failure = false) => {
    el("materialAuditStatus").textContent = message;
    el("materialAuditStatus").classList.toggle("quality-error", failure);
  };
  function buttons() {
    const running = capture?.state === "running";
    el("materialAuditCapture").disabled = busy || running || !city() || !write() || capture?.state === "complete";
    el("materialAuditVerify").disabled = busy || running || city() !== "natal" || !write() || !previousReady;
  }
  function addRow(fragment, values) {
    const tr = document.createElement("tr");
    for (const value of values) {
      const td = document.createElement("td");
      td.textContent = value ?? "—";
      tr.append(td);
    }
    fragment.append(tr);
  }
  function renderRows() {
    const term = el("materialAuditSearch").value.trim().toLocaleLowerCase("pt-BR");
    const rows = (report?.rows || []).filter(row => !term ||
      [row.technician, row.os, row.material, row.sap_material]
        .some(value => String(value || "").toLocaleLowerCase("pt-BR").includes(term)));
    const frag = document.createDocumentFragment();
    for (const row of rows.slice(page * batchSize, (page + 1) * batchSize)) {
      addRow(frag, [row.os, row.technician,
        [row.material, row.description].filter(Boolean).join(" · "),
        number(row.quantity) + (row.unit ? " " + row.unit : ""),
        number(row.opening_balance), number(row.balance_before), number(row.current_balance),
        number(row.balance_change),
        number(row.excess), labels[row.technician_check], number(row.company_balance),
        labels[row.company_check] + (row.sap_material && row.sap_material !== row.material ? " · " + row.sap_material : "")]);
    }
    el("materialAuditRows").replaceChildren(frag);
    el("materialAuditPrevious").disabled = page === 0;
    el("materialAuditNext").disabled = (page + 1) * batchSize >= rows.length;
    el("materialAuditPage").textContent = rows.length
      ? `${page * batchSize + 1}–${Math.min((page + 1) * batchSize, rows.length)} de ${rows.length}`
      : "Nenhuma baixa encontrada";
  }
  function showReport(result) {
    report = result;
    page = 0;
    el("materialAuditSearch").value = "";
    el("materialAuditResult").hidden = false;
    const rankings = document.createDocumentFragment();
    for (const row of report.ranking) {
      addRow(rankings, [row.technician, row.checked, row.divergent,
        (row.divergent / row.checked).toLocaleString("pt-BR", {style:"percent", maximumFractionDigits:1})]);
    }
    el("materialAuditRanking").replaceChildren(rankings);
    el("materialAuditSummary").textContent = date(report.day) + " · " + report.rows.length +
      " lançamentos de materiais · " + (report.company
        ? "Empresa: " + report.company.nome_arquivo
        : "Sem Excel do estoque da empresa nessa data.") +
      (report.skipped_other_day ? " · " + report.skipped_other_day + " lançamentos de outras datas excluídos" : "");
    renderRows();
  }
  function poll(scope, verify = false) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (scope !== city() || el("stockDailyPane").classList.contains("hidden")) return;
      if (!await refresh()) return;
      if (capture?.state === "running") poll(scope, verify);
      else if (verify && capture?.state === "complete") void action("verify");
    }, 3000);
  }
  async function refresh() {
    const scope = city();
    if (activeScope !== scope) {
      activeScope = scope;
      capture = null;
      report = null;
      previousReady = false;
      el("materialAuditResult").hidden = true;
    }
    if (!scope) {
      status("Selecione uma base para consultar os estoques.");
      buttons();
      return false;
    }
    try {
      const data = await request(uri + "?city=" + encodeURIComponent(scope), {timeoutMs:30000});
      if (scope !== city()) return false;
      capture = data.today;
      todayLabel = date(data.date);
      previousReady = data.yesterday?.state === "complete";
      if (capture?.state === "running") {
        status("Consultando estoques no Imperium · " + capture.collected + " de " + (capture.expected || "…") + " locais.");
      } else if (capture?.state === "failed") {
        status(capture.error, true);
      } else {
        const saved = capture?.state === "complete"
          ? todayLabel + " · Estoques salvos às " + time(capture.updated_at) + " · " + capture.collected + " locais."
          : "Ainda não há estoques de técnicos salvos em " + todayLabel + ".";
        const verify = scope !== "natal" ? " Vistoria disponível inicialmente em Natal/Parnamirim."
          : !previousReady ? " Estoque de " + date(data.reference_date) + " ainda não foi salvo." : "";
        status(saved + verify);
      }
      buttons();
      return true;
    } catch (error) {
      if (scope !== city()) return false;
      status(error.message || "Vistoria indisponível.", true);
      buttons();
      return false;
    }
  }
  async function action(kind) {
    const scope = city();
    if (!scope || !write() || busy) return;
    busy = true;
    buttons();
    status(kind === "verify" ? "Consultando as baixas de ontem no Imperium..." : "Iniciando a coleta de estoque...");
    try {
      const data = await request(uri + "/" + kind, {
        method: "POST", timeoutMs:115000, body: JSON.stringify({city:scope}),
      });
      if (scope !== city()) return;
      if (data.report) {
        showReport(data.report);
        status("Vistoria de " + date(data.report.day) + " concluída.");
      } else {
        await refresh();
        if (capture?.state === "running") poll(scope, kind === "verify");
        else if (kind === "verify" && capture?.state === "complete") poll(scope, true);
      }
    } catch (error) {
      if (scope === city()) status(error.message || "Vistoria indisponível.", true);
    } finally {
      busy = false;
      buttons();
    }
  }
  function opened() {
    if (el("stockDailyPane").classList.contains("hidden")) return;
    void refresh().then(ok => { if (ok && capture?.state === "running") poll(city()); });
  }
  el("materialAuditCapture").addEventListener("click", () => void action("capture"));
  el("materialAuditVerify").addEventListener("click", () => void action("verify"));
  el("materialAuditSearch").addEventListener("input", () => {page = 0; renderRows();});
  el("materialAuditPrevious").addEventListener("click", () => {page--; renderRows();});
  el("materialAuditNext").addEventListener("click", () => {page++; renderRows();});
  document.addEventListener("dominium:stock-tab-change", event => {
    if (event.detail?.tab === "daily") opened();
  });
  document.addEventListener("dominium:scope-change", opened);
  buttons();
  opened();
})();
