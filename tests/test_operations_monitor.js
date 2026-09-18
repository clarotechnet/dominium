"use strict";

const assert = require("node:assert/strict");
const {
  VIEW_DEFINITIONS,
  bucketFromSource,
  buildMeetingExamples,
  buildMonitorModel,
  buildTec1ContractAlerts,
  buildTec1VoiceMessage,
  buildTvDashboard,
  normalizeOrder,
  routeState,
  speechPronunciationText,
  statusKind,
  tec1State,
} = require("../static/operations-monitor.js");

const orders = [
  {
    num_os: "2648000001",
    contract: "4200001",
    service: "INSTALACAO",
    city: "NATAL",
    technician: "ANA",
    status: "EM CAMPO",
    date: "2026-08-03",
    inicio: "08:00",
    termino: "10:30",
    node: "NTL01",
  },
  {
    num_os: "2648000002",
    contract: "4200002",
    service: "RETORNO CREDENCIADA",
    city: "NATAL",
    technician: "ANA",
    status: "CONCLUIDA",
    date: "2026-08-03",
    inicio: "08:00",
    termino: "11:00",
    node: "NTL01",
    is_revisita: true,
    ofensor_revisita: "ANA",
    observacao: "Retorno apos atendimento anterior.",
  },
  {
    num_os: "2648000003",
    contract: "4200003",
    service: "DESCONEXAO IC / RETIRADA DE EQUIPAMENTO",
    city: "PARNAMIRIM",
    technician: "BRUNO",
    status: "PENDENTE",
    date: "2026-08-03",
    inicio: "08:00",
    termino: "09:00",
    node: "PWM02",
  },
  {
    num_os: "2648000004",
    contract: "4200004",
    service: "URA BAIXA 100",
    city: "NATAL",
    technician: "CARLA",
    status: "CANCELADA",
    date: "2026-08-03",
    inicio: "11:00",
    termino: "14:00",
    node: "NTL03",
    close_code: "100",
  },
];

const original = JSON.stringify(orders);
const model = buildMonitorModel(orders, {
  now: new Date("2026-08-03T10:00:00-03:00"),
  selectedDate: "2026-08-03",
});

assert.equal(VIEW_DEFINITIONS.length, 12);
assert.deepEqual(model.kpis, {
  total: 4,
  field: 1,
  completed: 1,
  pending: 1,
  canceled: 1,
  revisits: 1,
  closedWithCode: 1,
  routeAlerts: 0,
});
assert.equal(model.views.teams.rows.find((row) => row.team === "ANA").total, 2);
assert.equal(model.views.routes.rows.find((row) => row.route === "NTL01").total, 2);
assert.equal(model.views.capacity.rows.find((row) => row.technician === "ANA").active, 1);
assert.equal(model.views.returns.rows.length, 1);
assert.equal(model.views.disconnects.rows.length, 1);
assert.equal(model.views.revisits.rows.length, 1);
assert.equal(model.views.baixa100.rows.length, 1);
assert.equal(model.views.field.rows.length, 1);
assert.equal(model.views.pending.rows.length, 1);
assert.equal(model.views.completed.rows.length, 1);
assert.equal(model.views.revisits.rows[0].observation, "Retorno apos atendimento anterior.");
assert.equal(statusKind("EM CAMPO"), "field");
assert.equal(routeState("concluido"), "completed");
assert.equal(routeState("iniciado"), "started");
assert.equal(routeState("em rota"), "enroute");
assert.equal(routeState("pendente"), "pending");
assert.equal(
  tec1State(normalizeOrder(orders[0], "2026-08-03"), new Date("2026-08-03T10:00:00-03:00")).key,
  "risk",
);
const toaWindow = normalizeOrder({
  num_os: "500",
  contract: "900",
  service_window: "08:00 - 12:00",
  toa_os_status: "EM CAMPO",
}, "2026-08-03");
assert.equal(toaWindow.startRaw, "08:00");
assert.equal(toaWindow.endRaw, "12:00");
assert.equal(toaWindow.statusKind, "field");
assert.equal(tec1State(toaWindow, new Date("2026-08-03T09:30:00-03:00")).key, "safe");

const groupedTec1Alerts = buildTec1ContractAlerts([
  { os: "T1", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 29, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
  { os: "T2", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 29, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
  { os: "T3", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 29, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
  { os: "T4", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 29, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
  { os: "T5", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 29, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
  { os: "DONE", contract: "4253494", technician: "GUILHERME", status_kind: "completed", tec1_minutes: 10, tec1_deadline: "2026-08-03T10:40:00-03:00" },
]);
assert.equal(groupedTec1Alerts.length, 1, "cinco tarefas devem gerar um aviso por contrato");
assert.equal(groupedTec1Alerts[0].contract, "4253494");
assert.equal(groupedTec1Alerts[0].task_count, 5);
assert.equal(groupedTec1Alerts[0].threshold, 30);
assert.equal(groupedTec1Alerts[0].window_start, "08:00");
const tec1VoiceText = buildTec1VoiceMessage(groupedTec1Alerts[0]);
assert.match(tec1VoiceText, /^Atenção\./);
assert.match(tec1VoiceText, /téqui um/);
assert.match(tec1VoiceText, /Técnico GUILHERME/);
assert.match(tec1VoiceText, /Janela das 8 horas às 11 horas/);
assert.doesNotMatch(tec1VoiceText, /TEC um|Atencao|Tecnico/);
assert.equal(
  speechPronunciationText("ATENCAO: MUDANCA, TEC1, TEC um, INSTALACAO, DESCONEXAO, NAO"),
  "atenção: mudança, téqui um, téqui um, instalação, desconexão, não",
);
assert.equal(buildTec1ContractAlerts([
  { os: "T1", contract: "4253494", technician: "GUILHERME", status_kind: "field", tec1_minutes: 14, tec1_deadline: "2026-08-03T11:00:00-03:00", window_start: "08:00", window_end: "11:00" },
])[0].threshold, 15);
assert.equal(buildTec1ContractAlerts([
  { os: "LATE", contract: "4253494", status_kind: "field", tec1_minutes: -1 },
]).length, 0, "contrato estourado nao deve repetir os avisos preventivos");
assert.equal(JSON.stringify(orders), original, "o monitor nao pode modificar as OS de entrada");

assert.equal(
  bucketFromSource("Atividades-FTZ-DMV_01_VT_08_08_26.csv"),
  "FTZ-DMV_01_VT",
);
assert.equal(
  bucketFromSource("Atividades-NTL-DMV_08_08_26 (1).csv"),
  "NTL-DMV",
);
const bucketModel = buildMonitorModel([
  { num_os: "B1", source_file: "Atividades-NTL-DMV_08_08_26.csv", status: "PENDENTE" },
  { num_os: "B2", source_file: "Atividades-NTL-DMV_08_08_26.csv", status: "EM CAMPO" },
  { num_os: "B3", source_file: "Atividades-PWM-DMV_VT_08_08_26.csv", status: "CONCLUIDA" },
], { selectedDate: "2026-08-08" });
assert.deepEqual(bucketModel.buckets, [
  { name: "NTL-DMV", count: 2 },
  { name: "PWM-DMV_VT", count: 1 },
]);
assert.equal(bucketModel.views.monitor.rows[0].bucket, "NTL-DMV");
assert.equal(
  bucketModel.views.routes.console.technicians
    .flatMap((technician) => technician.activities)
    .filter((activity) => activity.bucket === "NTL-DMV").length,
  2,
);

const routeModel = buildMonitorModel([
  {
    num_os: "7001", contract: "8001", activity_id: "ACT-1", technician: "KASSIO",
    toa_status: "concluido", service: "ADESAO", date: "08/08/26",
    service_window: "07:30 - 08:30", started_at: "07:57", ended_at: "08:56", close_code: "409",
  },
  {
    num_os: "7002", contract: "8001", activity_id: "ACT-1", technician: "KASSIO",
    toa_status: "concluido", service: "INSTALACAO", date: "08/08/26",
    service_window: "07:30 - 08:30", started_at: "07:57", ended_at: "08:56", close_code: "106",
  },
  {
    num_os: "7003", contract: "8002", activity_id: "ACT-OLD", technician: "CAUE",
    toa_status: "suspenso", service: "INSTALACAO", date: "08/08/26",
    service_window: "08:00 - 09:00", started_at: "08:10", ended_at: "08:35",
  },
  {
    num_os: "7003", contract: "8002", activity_id: "ACT-2", technician: "ELVIS",
    toa_status: "iniciado", service: "INSTALACAO", date: "08/08/26",
    service_window: "09:00 - 10:00", started_at: "09:10",
  },
  {
    num_os: "7004", contract: "8003", activity_id: "ACT-3", technician: "ANA",
    toa_status: "em rota", service: "INSTALACAO", date: "08/08/26",
    service_window: "09:30 - 10:30",
  },
  {
    num_os: "7005", contract: "8004", activity_id: "ACT-4", technician: "BRUNO",
    toa_status: "pendente", service: "INSTALACAO", date: "08/08/26",
    service_window: "08:00 - 09:00",
  },
], {
  now: new Date("2026-08-08T10:15:00-03:00"),
  selectedDate: "2026-08-08",
  timelineActivities: [{
    activity_id: "timeline:KASSIO:7",
    technician: "KASSIO",
    service: "REFEICAO",
    date: "08/08/26",
    started_at: "12:00",
    ended_at: "14:00",
    duration: "02:00",
    auxiliary_type: "meal",
    is_auxiliary: true,
  }],
});
const routeConsole = routeModel.views.routes.console;
assert.equal(routeConsole.totalOrders, 5);
assert.equal(routeConsole.totalActivities, 6, "a alocacao suspensa deve permanecer como historico sem duplicar a OS");
assert.equal(routeConsole.auxiliaryActivities, 1);
assert.equal(routeConsole.suspendedActivities, 1);
assert.equal(routeConsole.alerts.length, 3);
assert.ok(routeConsole.alerts.every((alert) => "bucket" in alert && "contract" in alert && "activity_id" in alert));
assert.equal(routeModel.kpis.routeAlerts, 3);
assert.equal(routeModel.kpis.total, 5, "refeicao nao pode alterar os indicadores de OS");
assert.equal(routeModel.views.reallocations.rows.length, 1);
assert.equal(routeModel.views.reallocations.rows[0].reallocated_to, "ELVIS");
const kassioActivity = routeConsole.technicians.find((item) => item.technician === "KASSIO").activities[0];
assert.equal(kassioActivity.route_state, "completed");
assert.equal(kassioActivity.os_count, 2);
assert.match(kassioActivity.os, /7001.*7002/);
const kassioMeal = routeConsole.technicians.find((item) => item.technician === "KASSIO")
  .activities.find((item) => item.is_auxiliary);
assert.equal(kassioMeal.route_state, "auxiliary");
assert.equal(kassioMeal.route_state_label, "Refeicao");
assert.equal(routeConsole.technicians.find((item) => item.technician === "ELVIS").activities[0].route_state, "started");
assert.equal(routeConsole.technicians.find((item) => item.technician === "CAUE").activities[0].route_state, "suspended");
assert.equal(routeConsole.technicians.find((item) => item.technician === "ANA").activities[0].route_state, "enroute");

const meetingExamples = buildMeetingExamples(new Date("2026-08-07T10:30:00-03:00"));
const meetingModel = buildMonitorModel(meetingExamples, {
  now: new Date("2026-08-07T10:30:00-03:00"),
  selectedDate: "2026-08-07",
});
assert.equal(meetingModel.isDemo, true);
assert.equal(meetingModel.kpis.total, 8);
assert.equal(meetingModel.kpis.field, 3);
assert.equal(meetingModel.kpis.completed, 2);
assert.equal(meetingModel.kpis.pending, 2);
assert.equal(meetingModel.kpis.canceled, 1);
assert.ok(VIEW_DEFINITIONS.every(({ key }) => meetingModel.views[key].rows.length > 0), "cada visao deve ter um cenario de exemplo");
assert.ok(Object.values(meetingModel.views).every((view) => view.rows.every((row) => row.example)), "todo registro de demonstracao deve estar marcado");
const tvDashboard = buildTvDashboard(meetingModel);
assert.equal(tvDashboard.isDemo, true);
assert.ok(tvDashboard.tec1Rows.length > 0);
assert.ok(tvDashboard.tec1Rows.every((row) => "tec1_deadline" in row && "tec1_minutes" in row));
assert.equal(tvDashboard.missingApi.find((item) => item.key === "next-technician").value, "Sem informação");
assert.ok(tvDashboard.kpis.tec1Risk > 0, "a TV deve destacar a contagem regressiva do TEC1");

console.log("Monitor de O.S.: console de rotas, cores, agrupamento por atividade e alertas validados.");
