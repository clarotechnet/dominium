const action = String(process.argv[2] || "").trim().toLowerCase();
const route = String(process.argv[3] || "").trim().toUpperCase();
const date = String(process.argv[4] || "").trim();

if (!["list", "export"].includes(action)) throw new Error("invalid action");
if (action === "export" && !/^(?:NTL|PWM|FTZ|JCR|MRO)-DMV(?:_[A-Z0-9]+)*$/i.test(route)) {
  throw new Error("invalid route");
}
if (action === "export" && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
  throw new Error("invalid date");
}

const targets = await (await fetch("http://127.0.0.1:9341/json")).json();
const page = targets.find(
  (item) =>
    item.type === "page"
    && String(item.url || "").includes("clarobrasil.etadirect.com"),
);
if (!page) throw new Error("TOA page not found");

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.onopen = resolve;
  ws.onerror = reject;
});

let nextId = 1;
function evaluate(expression, options = {}) {
  const id = nextId++;
  const awaitPromise = options.awaitPromise !== false;
  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      ws.removeEventListener("message", onMessage);
      if (message.error) {
        reject(new Error(message.error.message || "CDP evaluate failed"));
        return;
      }
      if (message.result && message.result.exceptionDetails) {
        const details = message.result.exceptionDetails;
        reject(new Error(
          (details.exception && details.exception.description)
          || details.text
          || "CDP evaluate failed",
        ));
        return;
      }
      resolve(message.result && message.result.result ? message.result.result.value : undefined);
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({
      id,
      method: "Runtime.evaluate",
      params: {
        expression,
        awaitPromise,
        returnByValue: true,
      },
    }));
  });
}

try {
  const available = await evaluate(
    "typeof globalThis.TNTOAAutoExport === 'object' && typeof globalThis.TNTOAAutoExport.discoverBuckets === 'function'",
    { awaitPromise: false },
  );
  if (!available) throw new Error("TNTOAAutoExport not loaded in TOA page");

  if (action === "list") {
    const buckets = await evaluate(
      "globalThis.TNTOAAutoExport.discoverBuckets()",
      { awaitPromise: false },
    );
    console.log(JSON.stringify({ ok: true, buckets: Array.isArray(buckets) ? buckets : [] }));
  } else {
    const expression =
      "globalThis.TNTOAAutoExport.exportRoute("
      + JSON.stringify(route)
      + ","
      + JSON.stringify(date)
      + ")";
    const result = await evaluate(expression, { awaitPromise: true });
    if (!result || typeof result !== "object") throw new Error("invalid TOA export result");
    console.log(JSON.stringify({ ok: true, result }));
  }
} finally {
  ws.close();
}
