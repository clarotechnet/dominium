/* DOMINIUM — Controle de baixas: motor determinístico, somente planejamento.
 * Sem rede, POST, efeitos colaterais ou dependências externas.
 * Não substitui validação de serviço/bucket/equipamentos/baixa no servidor.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DominiumCloseControlEngine = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const MAX_PAUSE_MIN = 30;
  const INITIATED_BACKOFF_MIN = Object.freeze([15, 20, 30]);
  const NORMALIZED = Object.freeze({
    pendente: "pending", pending: "pending",
    em_rota: "in_route", emrota: "in_route", in_route: "in_route", on_route: "in_route",
    iniciada: "started", iniciado: "started", started: "started", in_progress: "started",
    concluida: "completed", concluido: "completed", completed: "completed",
    baixada: "confirmed", confirmed: "confirmed", finalizada_no_imperium: "confirmed",
    erro: "error", error: "error", falha: "error",
    nao_consultada: "unobserved", unobserved: "unobserved",
  });
  const normalize = value => String(value ?? "").trim().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const statusOf = value => NORMALIZED[normalize(value)] || "unobserved";
  const minutesOf = value => {
    const found = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(String(value ?? ""));
    return found ? Number(found[1]) * 60 + Number(found[2]) : null;
  };
  const clockMinutes = date => date.getHours() * 60 + date.getMinutes();
  const formatAt = timestamp => timestamp == null ? "—"
    : new Date(timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const result = (key, label, extra = {}) => ({
    key, label, nextAt: null, due: false, review: false, ready: false,
    delayMinutes: 0, ...extra,
  });

  function windowDecision(order, now) {
    const start = minutesOf(order?.windowStart);
    const end = minutesOf(order?.windowEnd);
    if (start == null || end == null || end <= start) {
      return result("invalid_window", "Janela ausente ou inválida · tratativa humana", { review: true });
    }
    const clock = clockMinutes(now);
    if (clock < start) return result("future_window", "Aguardar janela " + order.windowStart, {
      nextAt: new Date(now.getFullYear(), now.getMonth(), now.getDate(),
        Math.floor(start / 60), start % 60).getTime(),
    });
    if (clock >= end) return result("expired_window", "Janela encerrada · tratativa humana", {
      review: true,
    });
    return null;
  }

  function decide(order, now = new Date()) {
    if (!(now instanceof Date) || !Number.isFinite(now.getTime())) throw new TypeError("Hora inválida");
    if (!order || typeof order !== "object") return result("invalid_order", "O.S. inválida", { review: true });
    const state = statusOf(order.toaStatus);
    if (order.confirmationState === "confirmed" || state === "confirmed")
      return result("confirmed", "Baixa confirmada no Imperium");
    if (order.confirmationState === "uncertain" || order.confirmationState === "sent")
      return result("uncertain", "Baixa sem confirmação · não reenviar", { review: true });
    if (state === "error" || order.manualReview === true)
      return result("manual_review", "Erro · tratativa humana", { review: true });
    if (!String(order.os || "").trim() || !String(order.contract || "").trim())
      return result("identity_missing", "Contrato/O.S. incompleto · revisar", { review: true });

    // Janela SEM override, inclusive ao clicar em botões de ação.
    const windowGate = windowDecision(order, now);
    if (windowGate) return windowGate;

    // Confirmação real da importação vem de servidor/registro conciliado, não da presença
    // de um item em state.orders. Unknown não é false nem true: bloqueia a automação.
    if (order.routeImported !== true)
      return result("route_not_imported", "Aguardar importação de rota no Imperium");
    if (order.imperiumOrderPresent !== true || order.orderImported !== true)
      return result("order_not_imported", "O.S. não confirmada no Imperium");

    if (state === "completed") {
      const hasProof = order.toaDetailConfirmed === true
        && order.codeConfirmed === true
        && order.materialsValidated === true
        && order.identityValidated === true
        && order.bucketValidated === true
        && String(order.code ?? "").trim() !== "";
      if (!hasProof) return result("review_completed", "Concluída no TOA · falta validar baixa", { review: true });
      if (order.imperiumAlreadyClosed === true) return result("confirmed", "Baixa existente no Imperium");
      if (order.imperiumAlreadyClosed !== false)
        return result("imperium_status_unknown", "Conferir estado da baixa no Imperium", { review: true });
      return result("ready", "Pronta para preparar baixa · requer autorização", {
        ready: true, readyFor: order.productive === true ? "productive" : order.productive === false ? "improductive" : null,
        review: typeof order.productive !== "boolean",
      });
    }

    if (state === "unobserved") {
      // Agenda apenas consulta futura. Sem acionar TOA pela interface.
      return result("due", "Elegível para consulta TOA · só planejamento", { due: true, nextAt: now.getTime() });
    }
    if (state !== "pending" && state !== "in_route" && state !== "started")
      return result("unknown_status", "Estado não reconhecido · revisão", { review: true });

    const readAt = new Date(order.toaObservedAt ?? "");
    if (!Number.isFinite(readAt.getTime()))
      return result("missing_observation", "Falta data da leitura TOA · revisão", { review: true });
    const observedAt = readAt.getTime();
    if (observedAt > now.getTime() + 60_000)
      return result("future_observation", "Leitura TOA no futuro · revisão", { review: true });

    const round = Math.max(1, Math.floor(Number(order.startedObservations) || 1));
    const delayMinutes = state === "started"
      ? INITIATED_BACKOFF_MIN[Math.min(round - 1, INITIATED_BACKOFF_MIN.length - 1)]
      : MAX_PAUSE_MIN;
    const nextAt = observedAt + delayMinutes * 60_000;
    const due = now.getTime() >= nextAt;
    return result(due ? "due" : "cooldown",
      state === "started" ? "Iniciada" : state === "in_route" ? "Em rota" : "Pendente", {
        due, nextAt, delayMinutes, status: state,
      });
  }

  function plan(orders, now = new Date()) {
    const rows = (Array.isArray(orders) ? orders : []).map(order => ({
      order, decision: decide(order, now),
    }));
    const byContract = new Map();
    for (const {order,decision} of rows) {
      if (!decision.due) continue;
      const contract = String(order.contract || "").trim();
      if (!byContract.has(contract)) byContract.set(contract, []);
      byContract.get(contract).push(String(order.os || ""));
    }
    const lookups = [...byContract].map(([contract,os]) => ({ contract, os }));
    const counts = { total: rows.length, due: rows.filter(x=>x.decision.due).length,
      contractsDue: lookups.length, review: rows.filter(x=>x.decision.review).length,
      ready: rows.filter(x=>x.decision.ready && !x.decision.review).length,
      waiting: rows.filter(x=>["cooldown","future_window"].includes(x.decision.key)).length,
      importBlocked: rows.filter(x=>["route_not_imported","order_not_imported"].includes(x.decision.key)).length,
    };
    // "lookups" é sugestão, não requisição. Necessita de orçamento global persistente no backend.
    return { rows, lookups, counts, networkCalls: 0, closesSent: 0 };
  }

  function demoOrders(date = "2026-11-06") {
    const obs = date+"T09:37:00-03:00";
    const base = { city:"mossoro", routeImported:true, orderImported:true,
      imperiumOrderPresent:true, identityValidated:true, bucketValidated:true,
      productive:false, confirmationState:"", imperiumAlreadyClosed:false };
    const make = (i, start, end, status, other={}) => ({
      ...base, os:"DEMO-OS-"+String(i).padStart(2,"0"),
      contract:"DEMO-C"+String(i).padStart(2,"0"),
      technician:"Técnico demonstrativo "+i,
      windowStart:start, windowEnd:end, toaStatus:status, toaObservedAt:obs,
      ...other,
    });
    return [
      make(1,"08:00","11:00","iniciada",{startedObservations:1}),
      make(2,"08:00","11:00","concluida",{code:"430",codeConfirmed:true,
        toaDetailConfirmed:true,materialsValidated:true}),
      make(3,"11:00","14:00","pendente"),
      make(4,"11:00","14:00","em_rota"),
      make(5,"11:00","14:00","iniciada"),
      make(6,"11:00","14:00","pendente"),
      make(7,"12:00","14:00","pendente"),
      make(8,"12:00","14:00","iniciada"),
      make(9,"12:00","14:00","em_rota"),
      make(10,"08:00","22:00","pendente"),
    ];
  }

  return Object.freeze({ decide, plan, demoOrders, windowDecision,
    minutesOf, clockMinutes, formatAt, statusOf });
});
