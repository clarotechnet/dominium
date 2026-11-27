/* Workspace navigation delegates to the existing module buttons. */
(() => {
  const sidebar = document.getElementById("primarySidebar");
  const shell = document.querySelector(".app-shell");
  const menu = document.getElementById("workspaceMenu");
  const menuOpen = document.getElementById("workspaceMenuOpen");
  const search = document.getElementById("workspaceSearch");
  const searchInput = document.getElementById("workspaceSearchInput");
  const searchResults = document.getElementById("workspaceSearchResults");
  const mobile = window.matchMedia("(max-width: 860px)");

  function positionMenu() {
    if (mobile.matches) menu.append(sidebar);
    else {
      if (menu.open) menu.close();
      shell.prepend(sidebar);
    }
  }

  function refreshGroups() {
    sidebar.querySelectorAll(".side-nav-item:not([aria-controls])").forEach((button) => {
      const active = button.classList.contains("active");
      if (active && !button.hasAttribute("data-sidebar-action")) {
        button.setAttribute("aria-current", "page");
        const group = button.closest("details");
        if (group) group.open = true;
      } else button.removeAttribute("aria-current");
    });
  }

  menuOpen.addEventListener("click", () => {
    refreshGroups();
    menu.showModal();
    menuOpen.setAttribute("aria-expanded", "true");
  });
  document.getElementById("workspaceMenuClose").addEventListener("click", () => menu.close());
  menu.addEventListener("click", (event) => {
    if (event.target === menu) menu.close();
  });
  menu.addEventListener("close", () => menuOpen.setAttribute("aria-expanded", "false"));
  sidebar.addEventListener("click", (event) => {
    const summary = event.target.closest("summary");
    const button = event.target.closest(".side-nav-item");
    if (menu.open && button && !button.hasAttribute("aria-controls")) menu.close();
    if (!mobile.matches && document.body.classList.contains("sidebar-collapsed")
      && (summary || button?.hasAttribute("aria-controls"))) {
      document.getElementById("sidebarToggle").click();
      if (summary) {
        event.preventDefault();
        summary.parentElement.open = true;
      }
    }
  }, true);
  mobile.addEventListener("change", positionMenu);
  const navigation = sidebar.querySelector(".side-nav-scroll");
  new MutationObserver(refreshGroups).observe(navigation, {
    subtree: true, attributes: true, attributeFilter: ["class"],
  });
  positionMenu();
  refreshGroups();

  function searchable(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  }

  function renderSearch() {
    const query = searchable(searchInput.value.trim()).split(/\s+/).filter(Boolean);
    const results = [...sidebar.querySelectorAll(
      ".side-nav-item:not([aria-controls]):not(.hidden):not([aria-hidden='true']):not(:disabled):not(#sidebarLogout)",
    )].filter((module) => query.every((word) => searchable(module.textContent).includes(word)));
    searchResults.replaceChildren();
    if (!results.length) {
      const empty = document.createElement("p");
      empty.textContent = "Nenhum módulo encontrado.";
      searchResults.append(empty);
      return;
    }
    for (const module of results) {
      const result = document.createElement("button");
      result.type = "button";
      result.textContent = module.querySelector("strong").textContent;
      result.addEventListener("click", () => {
        search.close();
        module.click();
      });
      searchResults.append(result);
    }
  }

  function openSearch(event) {
    if (document.documentElement.classList.contains("auth-pending") || document.querySelector("dialog[open]")) return;
    event?.preventDefault();
    searchInput.value = "";
    renderSearch();
    search.showModal();
  }

  document.getElementById("workspaceSearchOpen").addEventListener("click", openSearch);
  document.getElementById("workspaceSearchClose").addEventListener("click", () => search.close());
  searchInput.addEventListener("input", renderSearch);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchResults.querySelector("button")?.click();
    if (event.key === "ArrowDown") {
      event.preventDefault();
      searchResults.querySelector("button")?.focus();
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      openSearch(event);
    }
  });
})();
