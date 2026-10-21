const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "deploy", "hostinger-web", "server.js"), "utf8");
const start = source.indexOf("async function listOrders(");
const end = source.indexOf('\n}\n\napp.use("/api/toa-agenda/import"', start);
assert.ok(start >= 0 && end > start, "listOrders found");

function packet(length, declaredBytes) {
  const value = Buffer.alloc(length);
  if (length >= 24) value.writeUInt32LE(declaredBytes, 20);
  return value;
}
function runWith(initial, chunks = []) {
  const queue = chunks.slice();
  class FakeClient {
    async connect() {}
    async prepare() { return { result: [{ handle: [1] }] }; }
    async request(method) {
      if (method === "execute") return { result: [null, { data: [0, initial] }] };
      assert.equal(method, "more_blob");
      return { result: [{ data: [0, queue.shift() || Buffer.alloc(0)] }] };
    }
    close() {}
  }
  return vm.runInNewContext(source.slice(start, end + 2) + "\nlistOrders;", {
    Buffer,
    PROFILES: { natal: { port: 212 } },
    HOST: "test.invalid",
    getCredentials: () => ({ username: "test", password: "test" }),
    DataSnapClient: FakeClient,
    buildMainQuery: () => Buffer.alloc(0),
    MAX_FRAGMENTS: 256,
    STATUS_LABELS: { field: "EM CAMPO" },
    parseOrders: (payload) => payload.subarray(0, 3).equals(Buffer.from([0xc0, 0xc0, 0x60]))
      ? [] : [{ id_os: 1 }],
  });
}

test("rejects non-fragmented surplus until MIDAS framing is verified", async () => {
  await assert.rejects(
    runWith(packet(100, 52))("natal", "2026-10-21"),
    /incomplete_order_dataset/,
  );
});
test("accepts an exactly completed fragmented dataset", async () => {
  const orders = await runWith(packet(60, 52), [Buffer.alloc(20)])("natal", "2026-10-21");
  assert.equal(orders.length, 1);
});
test("rejects an oversized follow-on fragment", async () => {
  await assert.rejects(runWith(packet(60, 52), [Buffer.alloc(25)])("natal", "2026-10-21"), /incomplete_order_dataset/);
});
test("rejects a truncated header", async () => {
  await assert.rejects(runWith(Buffer.alloc(22))("natal", "2026-10-21"), /incomplete_order_dataset/);
});
test("accepts MIDAS empty dataset marker", async () => {
  const orders = await runWith(Buffer.from([0xc0, 0xc0, 0x60]))("natal", "2026-10-21");
  assert.equal(orders.length, 0);
});
