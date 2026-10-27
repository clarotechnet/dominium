/* Controle de qualidade: aba independente do estoque do tecnico. */
(() => {
  const byId = (id) => document.getElementById(id);
  const inventoryTab = byId("stockInventoryTab");
  const qualityTab = byId("stockQualityTab");
  const inventoryPane = byId("stockInventoryPane");
  const qualityPane = byId("stockQualityPane");
  const body = byId("qualityBody");
  const form = byId("qualityForm");
  const notice = byId("qualityNotice");
  const formWrap = byId("qualityFormWrap");
  const formTitle = byId("qualityFormTitle");
  const search = byId("qualitySearch");
  const count = byId("qualityCount");
  const save = byId("qualitySave");
  const material = byId("qualityMaterial");
  const description = byId("qualityDescription");
  const rule = byId("qualityRule");
  if (!qualityTab || !form || !body) return;

  let items = [];
  let editId = null;
  let editVersion = "";
  let loading = false;
  let saving = false;
  let loaded = false;
  const canEdit = () => ["admin", "controller"].includes(state.authUser?.role);

  const displayMessage = (message, failure = false) => {
    notice.textContent = message;
    notice.classList.toggle("quality-error", Boolean(failure));
  };

  function updateTabs(isQuality) {
    inventoryTab.classList.toggle("active", !isQuality);
    qualityTab.classList.toggle("active", isQuality);
    inventoryTab.setAttribute("aria-selected", String(!isQuality));
    qualityTab.setAttribute("aria-selected", String(isQuality));
    inventoryPane.classList.toggle("hidden", isQuality);
    qualityPane.classList.toggle("hidden", !isQuality);
    if (isQuality) {
      formWrap.classList.toggle("hidden", !canEdit());
      if (!loaded && !loading) void loadQuality();
    }
  }

  function resetForm() {
    form.reset();
    editId = null;
    editVersion = "";
    formTitle.textContent = "Adicionar material";
    save.textContent = "Adicionar";
  }

  function editItem(item) {
    editId = item.id;
    editVersion = item.atualizado_em || "";
    material.value = item.material;
    description.value = item.descricao_material;
    rule.value = item.qtd_controle_qualidade;
    formTitle.textContent = "Editar material " + item.material;
    save.textContent = "Salvar alteracoes";
    formWrap.scrollIntoView({ behavior: "smooth", block: "center" });
    material.focus();
  }

  function cell(row, value, className = "") {
    const td = document.createElement("td");
    td.textContent = String(value ?? "");
    if (className) td.className = className;
    row.appendChild(td);
    return td;
  }

  function renderQuality() {
    const term = normalize(search.value.trim());
    const filtered = items.filter((item) =>
      !term || normalize(item.material + " " + item.descricao_material + " " + item.qtd_controle_qualidade).includes(term)
    );
    body.replaceChildren();
    const frag = document.createDocumentFragment();
    filtered.forEach((item) => {
      const tr = document.createElement("tr");
      cell(tr, item.material, "quality-code");
      cell(tr, item.descricao_material);
      cell(tr, item.qtd_controle_qualidade, "quality-rule");
      cell(tr, item.atualizado_em ? new Date(item.atualizado_em).toLocaleString("pt-BR") : "-");
      const action = cell(tr, "");
      if (canEdit()) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button secondary quality-edit";
        button.textContent = "Editar";
        button.disabled = saving;
        button.addEventListener("click", () => editItem(item));
        action.appendChild(button);
      } else {
        action.textContent = "Somente leitura";
      }
      frag.appendChild(tr);
    });
    body.appendChild(frag);
    count.textContent = filtered.length + " de " + items.length + " materiais";
    if (loaded && !loading && !filtered.length) {
      displayMessage(items.length ? "Nenhum material corresponde a pesquisa." : "Nenhum material cadastrado.");
    }
  }

  async function loadQuality() {
    if (loading) return;
    loading = true;
    displayMessage("Carregando materiais do Supabase...");
    byId("qualityRefresh").disabled = true;
    try {
      const payload = await request("/api/stock/quality-control", { timeoutMs: 20000 });
      items = Array.isArray(payload.items) ? payload.items : [];
      loaded = true;
      displayMessage(items.length + " materiais carregados. As alteracoes sao salvas no Supabase.");
    } catch (error) {
      displayMessage(error.message || "Erro ao consultar o Supabase.", true);
    } finally {
      loading = false;
      byId("qualityRefresh").disabled = false;
      renderQuality();
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving || !canEdit()) return;
    saving = true;
    save.disabled = true;
    displayMessage("Salvando no Supabase...");
    try {
      const payload = {
        material: material.value.trim(),
        descricao_material: description.value.trim(),
        qtd_controle_qualidade: rule.value.trim(),
      };
      if (editId !== null) {
        payload.id = editId;
        payload.atualizado_em = editVersion;
      }
      await request("/api/stock/quality-control", { method: "POST", body: JSON.stringify(payload), timeoutMs: 20000 });
      resetForm();
      loaded = false;
      await loadQuality();
      showToast("Controle de qualidade salvo", "success");
    } catch (error) {
      displayMessage(error.message || "Falha ao salvar o material.", true);
      showToast(error.message || "Falha ao salvar", "error");
    } finally {
      saving = false;
      save.disabled = false;
    }
  });
  inventoryTab.addEventListener("click", () => updateTabs(false));
  qualityTab.addEventListener("click", () => updateTabs(true));
  byId("qualityRefresh").addEventListener("click", loadQuality);
  byId("qualityCancel").addEventListener("click", resetForm);
  search.addEventListener("input", renderQuality);
  resetForm();
  updateTabs(false);
})();
