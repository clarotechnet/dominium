"use strict";

const INTERVAL = 5 * 60_000;
const brasilia = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Sao_Paulo",
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
});

function collectionWindow(now) {
  const parts = Object.fromEntries(brasilia.formatToParts(now).map(({ type, value }) => [type, value]));
  return {
    date: [parts.year, parts.month, parts.day].join("-"),
    collecting: Number(parts.hour) >= 8,
    slot: Math.floor(now.getTime() / INTERVAL),
  };
}

function createDailyOrders({ profiles, fetchOrders, now = () => new Date(), onError = () => {} }) {
  const entries = new Map();
  let activeDate;
  let lastSlot;
  let inFlight;
  let timer;

  function currentWindow() {
    const window = collectionWindow(now());
    if (activeDate !== window.date) {
      activeDate = window.date;
      entries.clear();
    }
    return window;
  }

  async function refresh(window) {
    for (const profile of profiles) {
      if (currentWindow().date !== window.date) return;
      try {
        const payload = await fetchOrders(profile, window.date);
        if (payload.date !== window.date || payload.stale || !Array.isArray(payload.orders)) {
          throw new Error("O Imperium não confirmou uma lista nova");
        }
        if (currentWindow().date === window.date) {
          entries.set(profile, { rows: payload.orders, updatedAt: now(), failed: false });
        }
      } catch (error) {
        if (currentWindow().date === window.date) {
          entries.set(profile, { ...entries.get(profile), failed: true });
        }
        onError(profile, error);
      }
    }
  }

  function tick() {
    const window = currentWindow();
    if (!window.collecting || lastSlot === window.slot || inFlight) return inFlight;
    lastSlot = window.slot;
    inFlight = refresh(window).finally(() => { inFlight = undefined; });
    return inFlight;
  }

  function schedule() {
    void tick();
    timer = setTimeout(schedule, INTERVAL - now().getTime() % INTERVAL);
    timer.unref();
  }

  return {
    start() { if (!timer) schedule(); },
    tick,
    read(profile) {
      const window = currentWindow();
      const entry = window.collecting ? entries.get(profile) : undefined;
      const rows = entry?.rows || [];
      const status = !window.collecting ? "closed" : entry?.rows ? "ready" : entry?.failed ? "unavailable" : "waiting";
      return {
        date: window.date,
        count: rows.length,
        status_filter: "field",
        service_type_filter: "all",
        orders: rows,
        snapshot_status: status,
        updated_at: entry?.updatedAt?.toISOString() || null,
        stale: Boolean(entry?.rows && (entry.failed || now() - entry.updatedAt >= INTERVAL * 2)),
      };
    },
  };
}

module.exports = { collectionWindow, createDailyOrders };
