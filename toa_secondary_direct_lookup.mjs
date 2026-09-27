const contract = String(process.argv[2] || '').replace(/\D/g, '');
if (!/^\d{5,18}$/.test(contract)) throw new Error('invalid contract');
const targets = await (await fetch('http://127.0.0.1:9341/json')).json();
const page = targets.find(x => x.type === 'page' && String(x.url || '').includes('clarobrasil.etadirect.com'));
if (!page) throw new Error('TOA page not found');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
const id = 1;
const value = await new Promise((resolve, reject) => {
  ws.onmessage = event => {
    const msg = JSON.parse(event.data);
    if (msg.id !== id) return;
    if (msg.error) reject(new Error(msg.error.message));
    else if (msg.result?.exceptionDetails) reject(new Error(msg.result.exceptionDetails.text || 'evaluate failed'));
    else resolve(msg.result?.result?.value);
  };
  const expression = `window.__TN_TOA_DIRECT_LOOKUP__(${JSON.stringify(contract)})`;
  ws.send(JSON.stringify({id, method:'Runtime.evaluate', params:{expression, awaitPromise:true, returnByValue:true}}));
});
console.log(JSON.stringify(value));
ws.close();