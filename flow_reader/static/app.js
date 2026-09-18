// =============================================================================
// DOMINIUM | MAPA DE RESPONSABILIDADE
//
// IMPERIUM
// - SIM - protocolo, baixa, estoque ou operacao do Imperium.
//
// TOA
// - NAO - este arquivo nao consulta nem automatiza o TOA.
//
// DOMINIUM COMPARTILHADO
// - Apoio local apenas quando necessario ao fluxo Imperium.
//
// Categoria deste arquivo: IMPERIUM.
// Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
// A ordem executavel abaixo foi preservada para evitar regressao.
// =============================================================================
const state = {
  fileA: null,
  fileB: null,
  resultA: null,
  resultB: null,
  visibleLimit: 120,
  filtered: [],
};

const elements = Object.fromEntries([
  "uploadView", "loadingView", "loadingTitle", "resultsView", "fileA", "fileB",
  "fileNameA", "fileNameB", "dropzoneA", "dropzoneB", "compareToggle",
  "secondaryUpload", "analyzeButton", "newAnalysisButton", "captureTitle",
  "captureMeta", "captureHash", "metrics", "methodBars", "methodCount",
  "comparisonSection", "comparisonGrid", "comparisonBadge", "searchFilter",
  "categoryFilter", "portFilter", "interestingOnly", "visibleCount", "flowBody",
  "emptyState", "loadMoreButton", "exportButton", "flowDialog", "dialogClose",
  "dialogCategory", "dialogTitle", "dialogSubtitle", "dialogContent", "toast",
].map((id) => [id, document.querySelector(`#${id}`)]));

const categoryLabels = {
  write: "Escrita",
  action: "Ação",
  query: "Consulta",
  prepare: "Preparação",
  session: "Sessão",
  transport: "Transporte",
};

function node(tag, className = "", text = "") {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== "") item.textContent = text;
  return item;
}

function formatBytes(value) {
  if (!Number.isFinite(Number(value))) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let amount = Number(value);
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toLocaleString("pt-BR", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
}

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = Math.floor(value % 60);
  if (hours) return `${hours}h ${minutes}min`;
  if (minutes) return `${minutes}min ${secs}s`;
  return `${secs}s`;
}

function localTime(iso, withDate = false) {
  if (!iso) return "—";
  const date = new Date(iso);
  return new Intl.DateTimeFormat("pt-BR", {
    ...(withDate ? { dateStyle: "short" } : {}),
    timeStyle: "medium",
  }).format(date);
}

let toastTimer;
function toast(message, kind = "") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast ${kind}`.trim();
  toastTimer = setTimeout(() => elements.toast.classList.add("hidden"), 5000);
}

function validFile(file) {
  return file && /\.(zip|pcapng)$/i.test(file.name);
}

function setFile(slot, file) {
  if (!validFile(file)) {
    toast("Selecione um arquivo ZIP ou PCAPNG.", "error");
    return;
  }
  if (file.size > 256 * 1024 * 1024) {
    toast("A captura ultrapassa o limite de 256 MB.", "error");
    return;
  }
  state[`file${slot}`] = file;
  const name = elements[`fileName${slot}`];
  const zone = elements[`dropzone${slot}`];
  name.textContent = `${file.name} · ${formatBytes(file.size)}`;
  name.classList.remove("hidden");
  zone.classList.add("has-file");
  elements.analyzeButton.disabled = !state.fileA;
}

function wireDropzone(slot) {
  const input = elements[`file${slot}`];
  const zone = elements[`dropzone${slot}`];
  input.addEventListener("change", () => setFile(slot, input.files[0]));
  ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (event) => {
    event.preventDefault();
    zone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, (event) => {
    event.preventDefault();
    zone.classList.remove("dragging");
  }));
  zone.addEventListener("drop", (event) => setFile(slot, event.dataTransfer.files[0]));
}

async function analyzeFile(file, label) {
  elements.loadingTitle.textContent = `${label}: reconstruindo pacotes TCP...`;
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Filename": encodeURIComponent(file.name),
    },
    body: file,
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`O leitor respondeu com erro HTTP ${response.status}.`);
  }
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Falha ao analisar captura.");
  return payload;
}

async function runAnalysis() {
  if (!state.fileA) return;
  elements.uploadView.classList.add("hidden");
  elements.resultsView.classList.add("hidden");
  elements.loadingView.classList.remove("hidden");
  try {
    state.resultA = await analyzeFile(state.fileA, "Captura A");
    state.resultB = state.fileB ? await analyzeFile(state.fileB, "Captura B") : null;
    elements.loadingTitle.textContent = "Organizando a linha do tempo...";
    await new Promise((resolve) => setTimeout(resolve, 280));
    renderResults();
    elements.loadingView.classList.add("hidden");
    elements.resultsView.classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    elements.loadingView.classList.add("hidden");
    elements.uploadView.classList.remove("hidden");
    toast(error.message, "error");
  }
}

function metric(label, value, detail, accent) {
  const card = node("article", "metric");
  card.style.setProperty("--accent", accent);
  card.append(node("span", "", label), node("strong", "", value), node("small", "", detail));
  return card;
}

function renderMetrics() {
  const { summary, capture, source } = state.resultA;
  elements.metrics.replaceChildren(
    metric("FLUXOS", summary.flow_count.toLocaleString("pt-BR"), `${capture.stream_count} conexões TCP`, "#38e7d0"),
    metric("CONSULTAS", summary.query_count.toLocaleString("pt-BR"), "leituras reconhecidas", "#55a8ff"),
    metric("ESCRITAS", summary.write_count.toLocaleString("pt-BR"), `${summary.prepared_write_count || 0} preparadas sem execução`, "#ff6577"),
    metric("AÇÕES", summary.action_count.toLocaleString("pt-BR"), "métodos executáveis", "#ffb95c"),
    metric("PACOTES", capture.packet_count.toLocaleString("pt-BR"), formatBytes(source.size_bytes), "#9a7cff"),
    metric("DURAÇÃO", formatDuration(summary.duration_seconds), `${summary.error_count} erros detectados`, "#62e6a2"),
  );
}

function renderMethods() {
  const methods = state.resultA.summary.top_methods.slice(0, 14);
  const maximum = Math.max(1, ...methods.map((item) => item.count));
  elements.methodCount.textContent = `${state.resultA.summary.top_methods.length} métodos agrupados`;
  elements.methodBars.replaceChildren(...methods.map((item) => {
    const row = node("div", "method-row");
    const name = node("span", "method-name", item.method);
    name.title = item.method;
    const track = node("span", "bar-track");
    const bar = node("i");
    bar.style.width = `${Math.max(2, (item.count / maximum) * 100)}%`;
    track.append(bar);
    row.append(name, track, node("strong", "", item.count.toLocaleString("pt-BR")));
    return row;
  }));
}

function methodMap(result) {
  return new Map(result.summary.top_methods.map((item) => [item.method, item.count]));
}

function compareEntry(label, value, detail, accent = "") {
  const card = node("article", "compare-card");
  if (accent) card.style.borderColor = accent;
  card.append(node("span", "", label), node("strong", "", value), node("small", "", detail));
  return card;
}

function differenceList(title, items) {
  const article = node("article");
  article.append(node("h3", "", title));
  const list = node("ul");
  const values = items.slice(0, 10);
  if (!values.length) list.append(node("li", "", "Nenhuma diferença relevante"));
  values.forEach((item) => {
    const row = node("li");
    row.append(node("span", "", item.method), node("b", "", item.delta > 0 ? `+${item.delta}` : String(item.delta)));
    list.append(row);
  });
  article.append(list);
  return article;
}

function renderComparison() {
  if (!state.resultB) {
    elements.comparisonSection.classList.add("hidden");
    return;
  }
  const a = state.resultA.summary;
  const b = state.resultB.summary;
  const mapA = methodMap(state.resultA);
  const mapB = methodMap(state.resultB);
  const methods = new Set([...mapA.keys(), ...mapB.keys()]);
  const deltas = [...methods].map((method) => ({
    method,
    delta: (mapB.get(method) || 0) - (mapA.get(method) || 0),
  }));
  const appeared = deltas.filter((item) => !mapA.has(item.method) && item.delta > 0).sort((x, y) => y.delta - x.delta);
  const changed = deltas.filter((item) => mapA.has(item.method) && mapB.has(item.method) && item.delta).sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta));
  const flowDelta = b.flow_count - a.flow_count;
  const writeDelta = b.write_count - a.write_count;
  elements.comparisonBadge.textContent = `${state.resultA.source.filename} × ${state.resultB.source.filename}`;
  const list = node("div", "compare-list");
  list.append(differenceList("Métodos novos na captura B", appeared), differenceList("Maiores mudanças de volume", changed));
  elements.comparisonGrid.replaceChildren(
    compareEntry("FLUXOS B − A", flowDelta > 0 ? `+${flowDelta}` : String(flowDelta), `${a.flow_count} na A · ${b.flow_count} na B`),
    compareEntry("ESCRITAS B − A", writeDelta > 0 ? `+${writeDelta}` : String(writeDelta), `${a.write_count} na A · ${b.write_count} na B`, "rgba(255,101,119,.2)"),
    compareEntry("MÉTODOS NOVOS", String(appeared.length), "presentes apenas na captura B", "rgba(154,124,255,.25)"),
    list,
  );
  elements.comparisonSection.classList.remove("hidden");
}

function evidenceChips(flow) {
  const values = [];
  flow.close_codes.forEach((item) => values.push({ value: `CÓD ${item.code}`, type: "code" }));
  Object.entries(flow.filters).slice(0, 3).forEach(([key, value]) => values.push({ value: `${key}=${value}`, type: "filter" }));
  flow.order_numbers.slice(0, 2).forEach((value) => values.push({ value: `OS? ${value}`, type: "" }));
  flow.serials.slice(0, 2).forEach((value) => values.push({ value: `SERIAL? ${value}`, type: "" }));
  if (!values.length && flow.handle !== null) values.push({ value: `HANDLE ${flow.handle}`, type: "" });
  return values;
}

function searchable(flow) {
  return [
    flow.label, flow.method, flow.server_method, flow.base, flow.port,
    ...flow.close_codes.flatMap((item) => [item.code, item.description]),
    ...Object.entries(flow.filters).flat(), ...flow.contracts, ...flow.order_numbers,
    ...flow.serials, ...flow.text_fragments,
  ].join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
}

function filteredFlows() {
  const term = elements.searchFilter.value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
  const category = elements.categoryFilter.value;
  const port = elements.portFilter.value;
  const interesting = elements.interestingOnly.checked;
  return state.resultA.flows.filter((flow) => {
    if (category && flow.category !== category) return false;
    if (port && String(flow.port) !== port) return false;
    if (interesting && !["write", "action"].includes(flow.category)
      && !flow.close_codes.length && !Object.keys(flow.filters).length && flow.status !== "error") return false;
    return !term || searchable(flow).includes(term);
  });
}

function flowRow(flow) {
  const row = node("tr");
  row.tabIndex = 0;
  row.addEventListener("click", () => openFlow(flow));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter") openFlow(flow);
  });
  row.append(node("td", "time-cell", localTime(flow.timestamp)));
  const baseCell = node("td", "base-cell");
  baseCell.append(node("span", "", flow.base), node("small", "", `porta ${flow.port}`));
  row.append(baseCell);
  const typeCell = node("td");
  typeCell.append(node("span", `type-badge type-${flow.category}`, categoryLabels[flow.category] || flow.category));
  row.append(typeCell);
  const main = node("td", "flow-main");
  main.append(node("strong", "", flow.label), node("code", "", flow.server_method || flow.method));
  row.append(main);
  const chipsCell = node("td");
  const chips = node("div", "chips");
  evidenceChips(flow).forEach((item) => chips.append(node("span", `chip ${item.type}`.trim(), item.value)));
  chipsCell.append(chips);
  row.append(chipsCell);
  const response = node("td", "status-cell");
  response.append(node("i", `status-dot status-${flow.status}`), node("span", "", flow.status === "ok" ? "OK" : flow.status === "error" ? "Erro" : "Pendente"));
  row.append(response, node("td", "row-arrow", "›"));
  return row;
}

function renderFlows({ resetLimit = false } = {}) {
  if (resetLimit) state.visibleLimit = 120;
  state.filtered = filteredFlows();
  const visible = state.filtered.slice(0, state.visibleLimit);
  elements.flowBody.replaceChildren(...visible.map(flowRow));
  elements.visibleCount.textContent = `${visible.length.toLocaleString("pt-BR")} de ${state.filtered.length.toLocaleString("pt-BR")} fluxos`;
  elements.emptyState.classList.toggle("hidden", state.filtered.length !== 0);
  elements.loadMoreButton.classList.toggle("hidden", visible.length >= state.filtered.length);
}

function addDetailItem(parent, label, value) {
  const item = node("div", "detail-item");
  item.append(node("span", "", label), node("strong", "", value || "—"));
  parent.append(item);
}

function detailSection(title, values, className = "") {
  const section = node("section", "detail-section");
  section.append(node("h3", "", title));
  const content = node("div", className || "evidence-list");
  if (className === "detail-code") {
    content.textContent = values || "Sem dados";
  } else {
    const list = Array.isArray(values) ? values : [];
    if (!list.length) content.append(node("span", "", "Nenhuma evidência extra"));
    list.forEach((value) => content.append(node("span", "", value)));
  }
  section.append(content);
  return section;
}

function payloadSection(flow) {
  const section = node("section", "detail-section payload-section");
  section.append(node("h3", "", "Payload exato para desenvolvimento"));
  const description = node("p", "payload-note", "A requisição reconstruída pode ser copiada em Base64 ou recuperada pela exportação JSON.");
  const hashes = node("div", "payload-hashes");
  hashes.append(
    node("code", "", `REQ ${flow.request_sha256}`),
    node("code", "", `RES ${flow.response_sha256 || "sem resposta"}`),
  );
  const actions = node("div", "payload-actions");
  const copy = node("button", "ghost-button", "Copiar requisição Base64");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(flow.request_base64);
      toast("Payload Base64 copiado.");
    } catch {
      toast("O navegador não permitiu copiar o payload.", "error");
    }
  });
  const save = node("button", "ghost-button", "Salvar payload .b64");
  save.type = "button";
  save.addEventListener("click", () => {
    const blob = new Blob([flow.request_base64], { type: "text/plain;charset=ascii" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `fluxo-${flow.id}-${flow.category}.b64`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
  actions.append(copy, save);
  section.append(description, hashes, actions);
  return section;
}

function openFlow(flow) {
  elements.dialogCategory.textContent = `${categoryLabels[flow.category] || flow.category} · ${flow.status.toUpperCase()}`;
  elements.dialogTitle.textContent = flow.label;
  elements.dialogSubtitle.textContent = flow.server_method || flow.method;
  const grid = node("div", "detail-grid");
  addDetailItem(grid, "Horário", localTime(flow.timestamp, true));
  addDetailItem(grid, "Base", `${flow.base} · ${flow.port}`);
  addDetailItem(grid, "Conexão", `stream ${flow.stream_id} · handle ${flow.handle ?? "—"}`);
  addDetailItem(grid, "Duração", `${flow.duration_ms.toLocaleString("pt-BR")} ms`);
  addDetailItem(grid, "Cliente", flow.client);
  addDetailItem(grid, "Servidor", flow.server);
  addDetailItem(grid, "Requisição", formatBytes(flow.request_bytes));
  addDetailItem(grid, "Resposta", `${formatBytes(flow.response_bytes)} · ${flow.status_detail}`);
  const evidence = [
    ...flow.close_codes.map((item) => `${item.code} — ${item.description} (${item.confidence})`),
    ...Object.entries(flow.filters).map(([key, value]) => `${key} = ${value}`),
    ...flow.order_numbers.map((value) => `OS candidata: ${value}`),
    ...flow.contracts.map((value) => `Contrato candidato: ${value}`),
    ...flow.serials.map((value) => `Serial candidato: ${value}`),
  ];
  elements.dialogContent.replaceChildren(
    grid,
    detailSection("Evidências reconhecidas", evidence),
    detailSection("Textos encontrados no pacote", flow.text_fragments),
    detailSection("Prévia da requisição", flow.request_preview, "detail-code"),
    detailSection("Prévia da resposta", flow.response_preview, "detail-code"),
    payloadSection(flow),
  );
  elements.flowDialog.showModal();
}

function renderPorts() {
  const current = elements.portFilter.value;
  const options = [new Option("Todas as bases", "")];
  Object.keys(state.resultA.summary.port_counts).sort().forEach((port) => {
    const flow = state.resultA.flows.find((item) => String(item.port) === port);
    options.push(new Option(`${flow?.base || "Base"} · ${port}`, port));
  });
  elements.portFilter.replaceChildren(...options);
  elements.portFilter.value = options.some((item) => item.value === current) ? current : "";
}

function renderResults() {
  const { source, summary } = state.resultA;
  elements.captureTitle.textContent = source.filename;
  elements.captureMeta.textContent = `${summary.flow_count.toLocaleString("pt-BR")} fluxos · ${formatDuration(summary.duration_seconds)} · início ${localTime(summary.started_at, true)}`;
  elements.captureHash.textContent = source.sha256.slice(0, 16);
  renderMetrics();
  renderMethods();
  renderComparison();
  renderPorts();
  renderFlows({ resetLimit: true });
}

function resetAnalysis() {
  state.resultA = null;
  state.resultB = null;
  state.visibleLimit = 120;
  elements.resultsView.classList.add("hidden");
  elements.uploadView.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function exportResult() {
  if (!state.resultA) return;
  const payload = state.resultB
    ? { capture_a: state.resultA, capture_b: state.resultB }
    : state.resultA;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `flowscope-${state.resultA.source.filename.replace(/\.(zip|pcapng)$/i, "")}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

wireDropzone("A");
wireDropzone("B");
elements.compareToggle.addEventListener("click", () => {
  elements.secondaryUpload.classList.toggle("hidden");
  elements.compareToggle.classList.toggle("open");
});
elements.analyzeButton.addEventListener("click", runAnalysis);
elements.newAnalysisButton.addEventListener("click", resetAnalysis);
elements.exportButton.addEventListener("click", exportResult);
elements.dialogClose.addEventListener("click", () => elements.flowDialog.close());
elements.flowDialog.addEventListener("click", (event) => {
  if (event.target === elements.flowDialog) elements.flowDialog.close();
});
[elements.searchFilter, elements.categoryFilter, elements.portFilter, elements.interestingOnly]
  .forEach((control) => control.addEventListener("input", () => renderFlows({ resetLimit: true })));
elements.loadMoreButton.addEventListener("click", () => {
  state.visibleLimit += 150;
  renderFlows();
});
