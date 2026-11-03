"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");

function extract(name) {
  const re = new RegExp("(?:async )?function " + name + "\\(");
  const match = re.exec(source);
  assert.ok(match, "Function absent: " + name);
  const start = match.index;
  const remaining = source.slice(start + match[0].length);
  const next = /\n(?:async )?function [A-Za-z][A-Za-z0-9_]*\(/.exec(remaining);
  assert.ok(next, "Function end absent: " + name);
  return source.slice(start, start + match[0].length + next.index);
}
const actualMethods = ["updateAddress", "renderProfileTabs", "showAllOperations", "switchProfile", "setModule"]
  .map(extract).join("\n");

function setup(activeModule = "dashboard", backlogAllCities = false) {
  const state = {
    profile: "fortaleza",
    profiles: [{ key: "natal", label: "NATAL/PARNAMIRIM" },
      { key: "fortaleza", label: "FORTALEZA" }],
    activeModule,
    allCities: backlogAllCities,
    stockTechnicians: [],
    activeView: "orders",
    stockSource: "datasnap",
    running: false,
    loading: false,
    profileSwitching: false,
    bulkCreateLoading: false,
    stockBatchLoading: false,
    stockWriteoffLoading: false,
    toaLiveLoading: false,
    importLoading: false,
    materialLoading: false,
    materialPasteLoading: false,
  };
  const tabs = { buttons: [], replaceChildren(...buttons) { this.buttons = buttons; } };
  const elements = { profileTabs: tabs, date: { value: "2026-11-03" } };
  const opened = [];
  const events = [];
  const stockOpened = [];
  const win = {
    location: {
      href: "https://dominium.clarotechnet.com.br/?profile=fortaleza#baixar-os",
      hash: "#baixar-os",
    },
    history: {
      replaceState(_a, _b, url) {
        win.location.href = String(url);
        win.location.hash = new URL(String(url)).hash;
      }
    },
    DominiumAllOperations: { activate(args) { opened.push(args); } },
    DominiumStockNavigation: { openAllCityReadOnly() { stockOpened.push("open"); } },
    scrollTo() {}
  };
  const doc = {
    createElement(tag) {
      assert.equal(tag, "button");
      const classSet = new Set();
      return {
        type: "button", className: "", textContent: "", disabled: false, onClick: null,
        classList: { toggle(name, active) {
          if (active) classSet.add(name); else classSet.delete(name);
        }, contains(name) { return classSet.has(name); } },
        setAttribute() {},
        addEventListener(event, fn) { if (event === "click") this.onClick = fn; },
        click() { if (!this.disabled) this.onClick?.(); }
      };
    },
    dispatchEvent(event) { events.push(event.detail); },
    querySelector() { return { scrollTo() {} }; }
  };
  const context = {
    state, elements, window: win, document: doc, URL, CustomEvent: class {
      constructor(type, options) { this.type = type; this.detail = options.detail; }
    },
    disconnectIsRunning: () => false,
    loadStockTechnicians() {}, loadTechnicians() {},
    loadToaAutomation() {}, loadAutoImproductiveClose() {},
    loadAutomationTestData() {}, loadIntelligence() {}, loadHealthCheck() {},
    loadCloseReport() {}, loadOperationalDatabase() {},
    loadServerLogs() {}, loadImportAuditHistory() {},
    apiUrlForProfile() {}, request() {},
  };
  vm.runInNewContext(actualMethods + "\nfunction render(){ renderProfileTabs(); }\n", context);
  context.renderProfileTabs();
  return { context, state, tabs, win, opened, events, stockOpened,
    clickAll() { tabs.buttons[0].click(); },
    clickProfile(key) {
      const button = tabs.buttons.find(b => b.textContent ===
        (key === "fortaleza" ? "FORTALEZA" : "NATAL/PARNAMIRIM"));
      assert.ok(button);
      button.click();
    },
    active() { return tabs.buttons.find(b => b.classList.contains("active")); }
  };
}

test("Todos -> Análise Backlog retains all cities and leaves consolidated screen", () => {
  const app = setup("dashboard");
  app.clickAll();
  assert.equal(app.state.activeModule, "all-operations");
  assert.equal(app.opened.length, 1);
  assert.match(app.win.location.hash, /^#todos$/);
  app.context.setModule("backlog");
  assert.equal(app.state.activeModule, "backlog");
  assert.equal(app.state.allCities, true);
  assert.equal(app.active().className, "profile-tab profile-tab-all");
  assert.equal(app.win.location.hash, "#desconexao-backlog-todos");
  assert.ok(app.events.some(e => e.module === "backlog"));
});

test("clicking Todos while already on Backlog changes only its scope", () => {
  const app = setup("backlog");
  app.clickAll();
  assert.equal(app.state.activeModule, "backlog");
  assert.equal(app.state.allCities, true);
  assert.equal(app.opened.length, 0, "Must not activate all-operations queries");
  assert.equal(app.win.location.hash, "#desconexao-backlog-todos");
  assert.equal(app.active().className, "profile-tab profile-tab-all");
});

test("switching back to already-loaded Fortaleza clears all scope without leaving Backlog", async () => {
  const app = setup("backlog", true);
  app.clickProfile("fortaleza");
  await Promise.resolve();
  assert.equal(app.state.activeModule, "backlog");
  assert.equal(app.state.allCities, false);
  assert.equal(app.win.location.hash, "#desconexao-backlog");
  assert.equal(app.active().textContent, "FORTALEZA");
  assert.equal(app.opened.length, 0);
});

test("Todos persists across modules and dashboard returns to consolidated overview", () => {
  const app = setup("backlog", true);
  app.context.setModule("dashboard");
  assert.equal(app.state.allCities, true);
  assert.equal(app.state.activeModule, "all-operations");
  assert.equal(app.opened.length, 1);
  assert.equal(app.active().className, "profile-tab profile-tab-all");
});

test("Todos -> Estoque opens consolidated equipment analysis without changing operational city", () => {
  const app = setup("dashboard");
  app.clickAll();
  app.context.setModule("stock");
  assert.equal(app.state.activeModule, "stock");
  assert.equal(app.state.allCities, true);
  assert.equal(app.state.profile, "fortaleza");
  assert.equal(app.stockOpened.length, 1);
});

test("Todos in Estoque changes scope without showing consolidated operations screen", () => {
  const app = setup("stock");
  app.clickAll();
  assert.equal(app.state.activeModule, "stock");
  assert.equal(app.state.allCities, true);
  assert.equal(app.opened.length, 0);
  assert.equal(app.stockOpened.length, 1);
});

test("Global Todos remains active on unsupported operational modules", () => {
  const app = setup("backlog", true);
  app.context.setModule("close");
  assert.equal(app.state.activeModule, "close");
  assert.equal(app.state.allCities, true);
  assert.match(app.win.location.href, /scope=all/);
  assert.match(source, /all-city-module-blocked/);
});

test("clicking Todos in a city-only module retains the module and blocks its city-specific workspace", () => {
  const app = setup("close");
  app.clickAll();
  assert.equal(app.state.activeModule, "close");
  assert.equal(app.state.allCities, true);
  assert.equal(app.opened.length, 0);
  assert.equal(app.active().className, "profile-tab profile-tab-all");
  assert.match(app.win.location.href, /scope=all/);
  assert.match(source, /all-city-module-blocked/);
});

test("backlog all-cities URL can be reopened after reload", () => {
  assert.match(source, /allCities:\s*new URLSearchParams\(window\.location\.search\)\.get\("scope"\) === "all"/);
  assert.match(source, /activeModule:\s*\["#desconexao-backlog", "#desconexao-backlog-todos"\]/);
  const app = setup("backlog", true);
  assert.equal(app.active().className, "profile-tab profile-tab-all");
});
