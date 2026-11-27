"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { createDailyOrders } = require("../deploy/hostinger-web/daily-orders");
const { fetchScheduledOrders } = require("../deploy/hostinger-web/operational-relay");

test("reads share one collection per base every five minutes, starting at 08h Brasília", async () => {
  let instant = new Date("2026-11-27T10:59:00Z");
  const calls = [];
  const orders = createDailyOrders({
    profiles: ["natal", "fortaleza"],
    now: () => instant,
    fetchOrders: async (profile, date) => {
      calls.push([profile, date]);
      return { date, orders: [{ id_os: calls.length }] };
    },
  });
  await orders.tick();
  assert.deepEqual(calls, []);
  assert.equal(orders.read("natal").snapshot_status, "closed");
  instant = new Date("2026-11-27T11:00:00Z");
  assert.equal(orders.read("natal").snapshot_status, "waiting");
  await Promise.all([orders.tick(), orders.tick()]);
  assert.deepEqual(orders.read("natal").orders, [{ id_os: 1 }]);
  assert.equal(orders.read("fortaleza").updated_at, "2026-11-27T11:00:00.000Z");
  orders.read("natal");
  instant = new Date("2026-11-27T11:04:59Z");
  await orders.tick();
  assert.equal(calls.length, 2);
  instant = new Date("2026-11-27T11:05:00Z");
  await orders.tick();
  assert.equal(calls.length, 4);
  assert.deepEqual(orders.read("natal").orders, [{ id_os: 3 }]);
});

test("unconfirmed data does not replace the last valid list or turn into a confirmed zero", async () => {
  let instant = new Date("2026-11-27T11:00:00Z");
  let fail = true;
  const orders = createDailyOrders({
    profiles: ["natal"],
    now: () => instant,
    fetchOrders: async (_profile, date) => ({ date, stale: fail, orders: [] }),
  });
  await orders.tick();
  assert.equal(orders.read("natal").snapshot_status, "unavailable");
  assert.equal(orders.read("natal").updated_at, null);
  fail = false;
  instant = new Date("2026-11-27T11:05:00Z");
  await orders.tick();
  assert.equal(orders.read("natal").snapshot_status, "ready");
  fail = true;
  instant = new Date("2026-11-27T11:10:00Z");
  await orders.tick();
  assert.equal(orders.read("natal").updated_at, "2026-11-27T11:05:00.000Z");
  assert.equal(orders.read("natal").stale, true);
});

test("midnight clears the list and rejects a late response from yesterday", async () => {
  let instant = new Date("2026-11-28T02:55:00Z");
  const orders = createDailyOrders({
    profiles: ["natal"],
    now: () => instant,
    fetchOrders: async (_profile, date) => {
      if (instant.getUTCMinutes() === 55) instant = new Date("2026-11-28T03:00:00Z");
      return { date, orders: [{ id_os: 987 }] };
    },
  });
  await orders.tick();
  assert.equal(orders.read("natal").date, "2026-11-28");
  assert.equal(orders.read("natal").snapshot_status, "closed");
  assert.deepEqual(orders.read("natal").orders, []);
});

test("scheduled collection goes through the private relay as a read-only viewer", async () => {
  const response = await fetchScheduledOrders("natal", "2026-11-27", () => ({ token: "x".repeat(44) }),
    async (url, options) => {
      const parsed = new URL(url);
      assert.equal(parsed.pathname, "/api/orders");
      assert.deepEqual(Object.fromEntries(parsed.searchParams), {
        profile: "natal", date: "2026-11-27", status: "field", service_type: "all",
      });
      assert.equal(options.method || "GET", "GET");
      assert.equal(options.headers["x-dominium-role"], "viewer");
      assert.equal(options.headers.cookie, undefined);
      return { ok: true, json: async () => ({ date: "2026-11-27", orders: [] }) };
    });
  assert.deepEqual(response.orders, []);
});
