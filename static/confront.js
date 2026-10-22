/* DOMINIUM / Recursos / Pendente — secure UI for Atlas × Imperium jobs. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const ui = {
    nav: $("confrontModule"), input: $("confrontInput"), mode: $("confrontMode"),
    start: $("confrontRun"), refresh: $("confrontRefresh"), export: $("confrontExport"),
    status: $("confrontStatus"), notice: $("confrontNotice"),
    atlas: $("confrontAtlasStatus"), summary: $("confrontSummary"),
    results: $("confrontResults")
  };
  if (Object.values(ui).some((value) => !value)) return;
  let busy = false;
  let selected = null;
  let currentJob = null;
  let lastProfile = "";
  let fetching = false;
  let initialized = false;
  const statuses = {
    pending_imperium: "Consultando IMPERIUM",
    pending_atlas: "Aguardando consulta Atlas",
    submitting_atlas: "Confirmando envio Atlas",
    awaiting_atlas: "Aguardando retorno Atlas",
    complete: "Concluído",
    review_needed: "Revisão manual"
  };
  const labels = {
    convergente: "Convergente", divergente: "Divergente",
    revisao: "Revisar", inconclusivo: "Inconclusivo"
  };
  const alertLabel = {
    atlas_sinaliza_suspeito_exige_analise_humana: "Atlas sinalizou SUSPEITO: revisar",
    contratos_historicos_diferentes_revisar_datas: "Contratos históricos distintos: verificar datas"
  };
  function showError(error) {
    ui.notice.textContent = String(error?.message || error || "Falha na consulta.");
    ui.notice.classList.remove("hidden");
  }
  function clearError() {
    ui.notice.textContent = "";
    ui.notice.classList.add("hidden");
  }
  function render() {
    const operator = ["admin", "controller"].includes(String(state.authUser?.role || ""));
    ui.start.disabled = busy || !operator || Boolean(currentJob && currentJob.done < currentJob.total);
    ui.refresh.disabled = busy;
    ui.export.disabled = !currentJob || currentJob.done !== currentJob.total;
    ui.start.textContent = busy ? "Processando..." : "Iniciar confronto";
    if (!operator) {
      ui.status.textContent = "Este recurso exige perfil operacional.";
      ui.summary.replaceChildren();
      ui.results.textContent = "Entre com uma conta operacional para consultar relatórios.";
      currentJob = null;
      selected = null;
      initialized = false;
      return;
    }
    if (!currentJob) {
      ui.status.textContent = "Informe os seriais para iniciar um trabalho somente leitura.";
      ui.summary.replaceChildren();
      ui.results.textContent = "Nenhum confronto selecionado nesta praça.";
      return;
    }
    ui.status.textContent = currentJob.done + " de " + currentJob.total +
      " seriais finalizados · " + currentJob.profile.toUpperCase();
    const states = currentJob.states || {};
    const stats = [
      ["Finalizados", currentJob.done], ["Total", currentJob.total],
      ["Revisão necessária", states.review_needed || 0],
      ["Em processamento", currentJob.total - currentJob.done]
    ];
    ui.summary.replaceChildren(...stats.map(([label,value]) => {
      const item = document.createElement("div");
      item.className = "serials-stat";
      const t = document.createElement("span"), n = document.createElement("strong");
      t.textContent = label;
      n.textContent = String(value);
      item.append(t, n);
      return item;
    }));
    if (!Array.isArray(currentJob.rows)) return;
    const cards = currentJob.rows.map((row) => {
      const card = document.createElement("article");
      card.className = "serial-result-card confront-item";
      const header = document.createElement("header");
      header.className = "serial-result-header";
      const title = document.createElement("div");
      const label = document.createElement("span");
      label.className = "serial-result-eyebrow";
      label.textContent = "SERIAL CONSULTADO";
      const serial = document.createElement("h3");
      serial.textContent = row.serial || "";
      title.append(label, serial);
      const badge = document.createElement("span");
      const situacao = row.resultado?.situacao || row.state;
      badge.className = "serial-result-badge " +
        (situacao === "convergente" ? "ok" : situacao === "divergente" ? "error" : "");
      badge.textContent = labels[situacao] || statuses[situacao] || "Em fila";
      header.append(title, badge);
      card.append(header);
      const facts = document.createElement("div");
      facts.className = "serial-result-facts";
      const details = [
        ["Estado Atlas", row.resultado?.atlas?.estado || "Não confirmado"],
        ["Localização Atlas", row.resultado?.atlas?.localizacao || "Não confirmada"],
        ["Técnico IMPERIUM", row.resultado?.imperium?.tecnico || "Não confirmado"],
        ["Destino histórico", row.resultado?.imperium?.ultima_localizacao_nao_confirmada || "Sem registro"]
      ];
      details.forEach(([k,v]) => {
        const box = document.createElement("div");
        const name = document.createElement("span"), value = document.createElement("strong");
        name.textContent = k;
        value.textContent = v;
        box.append(name,value);
        facts.append(box);
      });
      card.append(facts);
      const notes = [...(row.resultado?.motivos || []),
        ...(row.resultado?.alertas || []).map(code => alertLabel[code] || code)];
      if (row.error_code) notes.push(row.error_code);
      if (notes.length) {
        const n = document.createElement("footer");
        n.className = "serial-result-footer";
        n.textContent = notes.join(" · ");
        card.append(n);
      }
      return card;
    });
    ui.results.replaceChildren(...cards);
  }
  async function refresh({silent = false} = {}) {
    if (fetching || !["admin","controller"].includes(String(state.authUser?.role || ""))) return;
    fetching = true;
    if (!silent) busy = true;
    clearError();
    try {
      const status = await request("/api/confront/status", {timeoutMs:16000});
      ui.atlas.textContent = status.atlas_online ? "Atlas conectado" : "Atlas indisponível";
      if (!selected) {
        const listed = await request("/api/confront/jobs", {timeoutMs:16000});
        const mine = (listed.jobs || []).find(job => job.profile === state.profile);
        selected = mine?.id || null;
      }
      if (selected) {
        const response = await request("/api/confront/jobs/" + selected, {timeoutMs:16000});
        currentJob = response.job || null;
      }
      initialized = true;
      render();
    } catch (error) {
      ui.atlas.textContent = "Não foi possível verificar Atlas";
      if (!silent) showError(error);
    } finally {
      fetching = false;
      busy = false;
      render();
    }
  }
  async function create() {
    if (busy || !["admin","controller"].includes(String(state.authUser?.role || ""))) return;
    const serials = serialConsultValues(ui.input.value);
    if (!serials.length || serials.length > 500 ||
        serials.some(s => !/^[A-Z0-9._/-]{4,50}$/.test(s))) {
      showError("Informe de 1 a 500 seriais válidos (4 a 50 caracteres).");
      return;
    }
    busy = true;
    clearError();
    render();
    try {
      const response = await request("/api/confront/jobs", {
        method: "POST",
        headers: {"content-type": "application/json"},
        body: JSON.stringify({serials, profile: state.profile, mode: ui.mode.value}),
        timeoutMs:20000
      });
      selected = response.job.job_id;
      currentJob = response.job;
      ui.input.value = "";
      await refresh();
    } catch (error) {
      showError(error);
    } finally {
      busy = false;
      render();
    }
  }
  async function exportCsv() {
    if (!selected || !currentJob || currentJob.done !== currentJob.total) return;
    try {
      const result = await requestBlob("/api/confront/jobs/" + selected + "/export", {timeoutMs:60000});
      saveBlob(result.blob, "dominium-confronto-" + currentJob.profile + "-" + localDate() + ".csv");
    } catch (error) {
      showError(error);
    }
  }
  ui.nav.addEventListener("click", () => setModule("confront"));
  ui.start.addEventListener("click", () => void create());
  ui.refresh.addEventListener("click", () => void refresh());
  ui.export.addEventListener("click", () => void exportCsv());
  document.addEventListener("dominium:module-change", ({detail}) => {
    if (lastProfile !== state.profile) {
      selected = null;
      currentJob = null;
      lastProfile = state.profile;
      initialized = false;
    }
    if (detail?.module === "confront") void refresh();
  });
  setInterval(() => {
    if (state.activeModule !== "confront") return;
    if (lastProfile !== state.profile) {
      selected = null;
      currentJob = null;
      lastProfile = state.profile;
      initialized = false;
    }
    if (!initialized || (currentJob && currentJob.done < currentJob.total)) {
      void refresh({silent:true});
    }
  }, 5000);
  render();
  if (state.activeModule === "confront") void refresh();
})();
