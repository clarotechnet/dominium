/* Controle de qualidade: pesquisa no painel, cadastro/edicao em modal. */
(() => {
  const byId = (id) => document.getElementById(id);
  const inventoryTab = byId("stockInventoryTab");
  const qualityTab = byId("stockQualityTab");
  const inventoryPane = byId("stockInventoryPane");
  const qualityPane = byId("stockQualityPane");
  const body = byId("qualityBody");
  const dialog = byId("qualityFormWrap");
  const form = byId("qualityForm");
  const notice = byId("qualityNotice");
  const formNotice = byId("qualityFormNotice");
  const formTitle = byId("qualityFormTitle");
  const search = byId("qualitySearch");
  const count = byId("qualityCount");
  const add = byId("qualityAdd");
  const save = byId("qualitySave");
  const cancel = byId("qualityCancel");
  const closeButton = byId("qualityDialogClose");
  const refresh = byId("qualityRefresh");
  const material = byId("qualityMaterial");
  const description = byId("qualityDescription");
  const rule = byId("qualityRule");
  if (!qualityTab || !form || !body || !dialog || !add || !dialog.showModal) return;

  let items = [];
  let editId = null;
  let editVersion = "";
  let loading = false;
  let saving = false;
  let loaded = false;
  let returnFocus = null;

  const canEdit = () => ["admin", "controller"].includes(state.authUser?.role);
  const displayMessage = (message, failure = false) => {
    notice.textContent = message;
    notice.classList.toggle("quality-error", Boolean(failure));
  };
  const showFormError = (message) => {
    formNotice.textContent = message;
    formNotice.hidden = !message;
  };

  function resetForm() {
    form.reset();
    editId = null;
    editVersion = "";
    formTitle.textContent = "Adicionar material";
    save.textContent = "Adicionar";
    showFormError("");
  }

  function closeDialog() {
    if (saving || !dialog.open) return;
    dialog.close();
  }

  function openDialog(item = null, trigger = null) {
    if (saving || !canEdit()) return;
    resetForm();
    returnFocus = trigger || document.activeElement;
    if (item) {
      editId = item.id;
      editVersion = item.atualizado_em || "";
      material.value = item.material;
      description.value = item.descricao_material;
      rule.value = item.qtd_controle_qualidade;
      formTitle.textContent = "Editar material";
      save.textContent = "Salvar alterações";
    }
    if (!dialog.open) dialog.showModal();
    material.focus();
  }

  function updateTabs(isQuality) {
    inventoryTab.classList.toggle("active", !isQuality);
    qualityTab.classList.toggle("active", isQuality);
    inventoryTab.setAttribute("aria-selected", String(!isQuality));
    qualityTab.setAttribute("aria-selected", String(isQuality));
    inventoryPane.classList.toggle("hidden", isQuality);
    qualityPane.classList.toggle("hidden", !isQuality);
    const dailyTab = document.getElementById("stockDailyTab");
    const dailyPane = document.getElementById("stockDailyPane");
    dailyTab?.classList.remove("active");
    dailyTab?.setAttribute("aria-selected", "false");
    dailyPane?.classList.add("hidden");
    document.dispatchEvent(new Event("dominium:stock-tab-change"));
    if (!isQuality) {
      if (dialog.open) closeDialog();
      return;
    }
    add.hidden = !canEdit();
    if (!loaded && !loading) void loadQuality();
  }

  function cell(row, value, className = "") {
    const td = document.createElement("td");
    td.textContent = String(value ?? "");
    if (className) td.className = className;
    row.appendChild(td);
    return td;
  }

  function renderQuality() {
    add.hidden = !canEdit();
    const term = normalize(search.value.trim());
    const filtered = items.filter((item) =>
      !term || normalize(item.material + " " + item.descricao_material + " " + item.qtd_controle_qualidade).includes(term)
    );
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
        button.addEventListener("click", () => openDialog(item, button));
        action.appendChild(button);
      } else {
        action.textContent = "Somente leitura";
      }
      frag.appendChild(tr);
    });
    body.replaceChildren(frag);
    count.textContent = filtered.length + " de " + items.length + " materiais";
    if (loaded && !loading && !filtered.length) {
      displayMessage(items.length ? "Nenhum material corresponde à pesquisa." : "Nenhum material cadastrado.");
    }
  }

  async function loadQuality() {
    if (loading) return;
    loading = true;
    refresh.disabled = true;
    displayMessage("Carregando materiais do Supabase...");
    try {
      const payload = await request("/api/stock/quality-control", { timeoutMs: 20000 });
      items = Array.isArray(payload.items) ? payload.items : [];
      loaded = true;
      displayMessage(items.length + " materiais carregados. As alterações são salvas no Supabase.");
    } catch (error) {
      displayMessage(error.message || "Erro ao consultar o Supabase.", true);
    } finally {
      loading = false;
      refresh.disabled = false;
      renderQuality();
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving || !dialog.open || !canEdit()) return;
    saving = true;
    save.disabled = true;
    cancel.disabled = true;
    closeButton.disabled = true;
    showFormError("");
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
      saving = false;
      dialog.close();
      loaded = false;
      await loadQuality();
      showToast("Controle de qualidade salvo", "success");
    } catch (error) {
      const message = error.message || "Não foi possível salvar o material.";
      showFormError(message);
      showToast(message, "error");
    } finally {
      saving = false;
      save.disabled = false;
      cancel.disabled = false;
      closeButton.disabled = false;
    }
  });

  add.addEventListener("click", () => openDialog(null, add));
  cancel.addEventListener("click", closeDialog);
  closeButton.addEventListener("click", closeDialog);
  dialog.addEventListener("cancel", (event) => {
    if (saving) event.preventDefault();
  });
  dialog.addEventListener("close", () => {
    resetForm();
    if (returnFocus?.isConnected && !returnFocus.disabled) returnFocus.focus();
    returnFocus = null;
  });
  inventoryTab.addEventListener("click", () => updateTabs(false));
  qualityTab.addEventListener("click", () => updateTabs(true));
  refresh.addEventListener("click", loadQuality);
  search.addEventListener("input", renderQuality);
  resetForm();
  updateTabs(false);
})();
