"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "static", "app.js"),
  "utf8",
);

const imperiumMatch = extractFunction("toaLiveImperiumMatch");
assert.match(imperiumMatch, /if \(exact\) return exact;/);
assert.doesNotMatch(imperiumMatch, /matches\.length === 1/);

function extractFunction(name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `${name} not found`);
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  throw new Error(`Could not extract ${name}`);
}

const equipmentFactory = new Function(`
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }
  ${extractFunction("toaLiveSerialLooksLikeChip")}
  ${extractFunction("toaLiveEquipmentType")}
  ${extractFunction("expectedEquipmentType")}
  ${extractFunction("toaLiveEquipmentDraft")}
  return {
    toaLiveSerialLooksLikeChip,
    toaLiveEquipmentType,
    expectedEquipmentType,
    toaLiveEquipmentDraft,
  };
`);
const {
  toaLiveSerialLooksLikeChip,
  toaLiveEquipmentType,
  expectedEquipmentType,
  toaLiveEquipmentDraft,
} = equipmentFactory();

const chipIccid = "89550531860001779845";
const decoderSerial = "241785989807";
assert.equal(toaLiveSerialLooksLikeChip(chipIccid), true);
assert.equal(toaLiveSerialLooksLikeChip(decoderSerial), false);
assert.equal(toaLiveEquipmentType({ serial: chipIccid }), "chip");
assert.equal(toaLiveEquipmentType({ serial: decoderSerial, description: "DECODER" }), "decoder");
assert.equal(expectedEquipmentType("ENVIO DE CHIP VIA TECNICO"), "chip");

const sharedActivityEquipment = [
  { serial: decoderSerial, description: "DECODER" },
  { serial: chipIccid, description: "" },
];
assert.deepEqual(
  toaLiveEquipmentDraft(
    sharedActivityEquipment,
    { service: "ADESAO ENTREGA STREAMING", contract: "1", num_os: "1" },
    [{ service: "ADESAO ENTREGA STREAMING", contract: "1", num_os: "1" }],
  ),
  [{ serial: decoderSerial, type: "decoder" }],
);
assert.deepEqual(
  toaLiveEquipmentDraft(
    sharedActivityEquipment,
    { service: "ENVIO DE CHIP VIA TECNICO", contract: "1", num_os: "2" },
    [{ service: "ENVIO DE CHIP VIA TECNICO", contract: "1", num_os: "2" }],
  ),
  [{ serial: chipIccid, type: "chip" }],
);

const worker = extractFunction("runSemiAutoQueue");
assert.match(worker, /\/api\/toa-live\/lookup/);
assert.match(worker, /semiAutoRefreshActiveOrders/);
assert.match(worker, /semiAutoJobDueNow/);
assert.doesNotMatch(worker, /\/close/);
assert.doesNotMatch(worker, /submitClose/);
assert.doesNotMatch(worker, /processOrders/);
assert.doesNotMatch(worker, /openConfirmation/);
assert.match(worker, /semiAutoRefreshPendingConfirmations/);
assert.match(worker, /semiAutoPromoteDueToaRetries/);
assert.match(worker, /semiAutoNextToaRetryAt/);
assert.match(source, /const SEMI_AUTO_TOA_RETRY_MS = 5 \* 60 \* 1000;/);

const retryFactory = new Function(`
  const state = { semiAutoJobs: [] };
  const SEMI_AUTO_TOA_RETRY_MS = 5 * 60 * 1000;
  ${extractFunction("semiAutoScheduleToaRetry")}
  ${extractFunction("semiAutoPromoteDueToaRetries")}
  ${extractFunction("semiAutoNextToaRetryAt")}
  return { state, semiAutoScheduleToaRetry, semiAutoPromoteDueToaRetries, semiAutoNextToaRetryAt };
`);
const retryTools = retryFactory();
const retryJob = { state: "skipped", skipCategory: "toa_pending" };
retryTools.state.semiAutoJobs.push(retryJob);
assert.equal(retryTools.semiAutoScheduleToaRetry(retryJob, 1000), true);
assert.equal(retryJob.toaRetryAt, 301000);
assert.equal(retryTools.semiAutoNextToaRetryAt(), 301000);
assert.equal(retryTools.semiAutoPromoteDueToaRetries(300999), 0);
assert.equal(retryTools.semiAutoPromoteDueToaRetries(301000), 1);
assert.equal(retryJob.state, "pending");
assert.equal(retryJob.toaRetryAt, 0);

const pendingConfirmer = extractFunction("semiAutoRefreshPendingConfirmations");
assert.match(pendingConfirmer, /\/api\/close-report\?date=/);
assert.match(pendingConfirmer, /semiAutoMarkCandidateConfirmed/);
assert.match(pendingConfirmer, /semiAutoMarkCandidateUncertain/);
assert.match(pendingConfirmer, /status=field&service_type=all/);
assert.doesNotMatch(pendingConfirmer, /method:\s*["']POST["']/);
assert.doesNotMatch(pendingConfirmer, /\/api\/orders\/[^`"']+\/close/);

const confirmedMarker = extractFunction("semiAutoMarkCandidateConfirmed");
assert.match(confirmedMarker, /candidate\.pending = false/);
assert.match(confirmedMarker, /candidate\.closed = true/);
assert.match(confirmedMarker, /candidate\.confirmedByImperium = true/);
const uncertainMarker = extractFunction("semiAutoMarkCandidateUncertain");
assert.match(uncertainMarker, /candidate\.closed = false/);
assert.match(uncertainMarker, /candidate\.humanReview = true/);

const autoCloser = extractFunction("processAutoCloseCandidate");
assert.match(autoCloser, /if \(res\.pending\)[\s\S]*closed: false,[\s\S]*pending: true/);

const renderer = extractFunction("renderSemiAutoQueue");
assert.match(renderer, /data-semi-contract-review/);
assert.match(renderer, /openSemiAutoContractReview/);
assert.match(renderer, /temporaryWaitCategories/);
assert.match(renderer, /semiAutoToaPendingCount/);
assert.match(renderer, /semiAutoAwaitingImperiumCount/);
assert.match(renderer, /Aguardando dependências externas/);
assert.doesNotMatch(renderer, /submitClose/);
assert.doesNotMatch(renderer, /processOrders/);

const contractRenderer = extractFunction("renderSemiAutoContractReview");
assert.match(contractRenderer, /data-contract-review/);
assert.match(contractRenderer, /data-contract-material-owner/);
assert.match(contractRenderer, /prepareToaLiveClose/);
assert.match(contractRenderer, /semiAutoCandidateService/);
assert.doesNotMatch(contractRenderer, /submitClose/);
assert.doesNotMatch(contractRenderer, /processOrders/);

const contractDialogHtml = fs.readFileSync(
  path.join(__dirname, "..", "static", "index.html"),
  "utf8",
);
assert.match(contractDialogHtml, /id="semiAutoContractDialog"/);
assert.match(contractDialogHtml, /id="semiAutoContractActivities"/);
assert.match(contractDialogHtml, /id="semiAutoWindowStatus"/);
assert.match(contractDialogHtml, /id="semiAutoWindowList"/);
assert.match(contractDialogHtml, /id="semiAutoToaPendingCount"/);
assert.match(contractDialogHtml, /id="semiAutoAwaitingImperiumCount"/);
assert.doesNotMatch(contractDialogHtml, /id="countSkippedToaPending"/);

const skippedRenderer = extractFunction("renderSemiAutoSkippedDialog");
assert.match(skippedRenderer, /awaiting_imperium_import/);
assert.match(skippedRenderer, /toa_pending/);
assert.match(skippedRenderer, /!\["toa_pending", "awaiting_imperium_import"\]\.includes/);

const queueBuilder = extractFunction("semiAutoBuildJobs");
assert.match(queueBuilder, /SEMI_AUTO_ROUTE/);
assert.match(queueBuilder, /activeByContract/);
assert.match(queueBuilder, /imperiumSeen: activeOrders\.length > 0/);
assert.doesNotMatch(queueBuilder, /TOA não consultado.*Nenhuma OS em campo/s);
assert.match(queueBuilder, /jobs\.sort\(semiAutoCompareJobs\)/);
assert.match(extractFunction("semiAutoPrioritizeWindowNow"), /windowOverrideMode = "now"/);
assert.match(extractFunction("renderSemiAutoWindowControl"), /Atuar agora/);

const skipClassifier = extractFunction("semiAutoClassifySkip");
assert.match(skipClassifier, /awaiting_imperium_import/);
assert.match(skipClassifier, /Aguardando Importação no Imperium/);

const importCommit = extractFunction("commitImportFile");
assert.match(importCommit, /semiAutoWakeAwaitingImperiumImports/);
const importWake = extractFunction("semiAutoWakeAwaitingImperiumImports");
assert.match(importWake, /awaiting_imperium_import/);
assert.match(importWake, /semiAutoRefreshActiveOrders/);
assert.match(importWake, /runSemiAutoQueue/);

const candidateFilter = extractFunction("semiAutoCandidates");
assert.match(candidateFilter, /route !== SEMI_AUTO_ROUTE/);
assert.match(candidateFilter, /disconnectActivityComplete/);
assert.match(candidateFilter, /disconnectTaskExecuted/);
assert.match(candidateFilter, /eligibleOs\.has/);
assert.doesNotMatch(candidateFilter, /eligibleActivities/);
assert.doesNotMatch(candidateFilter, /submitClose/);
assert.match(candidateFilter, /semiAutoAssignMaterialOwners/);

const exactToaMaterialFactory = new Function(`
  const CANONICAL_MATERIAL_MAP = {
    "22066906": { code: "22026223", name: "CABO COAXIAL RG6 TRISH COM MENSAG PRETO", unit: "M" },
  };
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }
  ${extractFunction("toaLiveMaterialIdentity")}
  return { toaLiveMaterialIdentity };
`);
const exactToaMaterial = exactToaMaterialFactory().toaLiveMaterialIdentity({
  material_code: "22066906",
  description: "22066906_CABO COAXIAL RG6 TRISH COM MENSAG PRETO",
});
assert.equal(exactToaMaterial.code, "22066906");
assert.notEqual(exactToaMaterial.code, "22026223");

const perTaskCodeFactory = new Function(`
  const SEMI_AUTO_ROUTE = "NTL-DMV";
  const state = {
    closeCodes: Array.from({ length: 10 }, (_, index) => ({ code: String(401 + index) })),
    orders: [],
  };
  function automationProviderLabel(provider) { return String(provider?.id || provider || ""); }
  function semiAutoCanonicalRoute(value) { return String(value || ""); }
  function disconnectActivityComplete() { return true; }
  function disconnectTaskExecuted() { return true; }
  function toaLiveImperiumMatch(capture, task) {
    return (capture.imperium_matches || []).find((order) => String(order.num_os) === String(task.os_number));
  }
  function semiAutoAssignMaterialOwners(candidates) { return candidates; }
  ${extractFunction("semiAutoCandidates")}
  return { semiAutoCandidates };
`);
const perTaskCode = perTaskCodeFactory().semiAutoCandidates;
const taskPairs = Array.from({ length: 10 }, (_, index) => ({
  os_number: String(9001 + index), status: "E", close_code: String(401 + index),
}));
const taskOrders = taskPairs.map((task) => ({
  num_os: task.os_number, service: `SERVICO ${task.os_number}`,
}));
const perTaskCandidates = perTaskCode({ results: [{
  route_provider: { id: "NTL-DMV" }, activity_status: "complete",
  tasks: taskPairs,
  imperium_matches: [...taskOrders, { num_os: "9999", service: "OS SEM TAREFA TOA" }],
}] }, { osNumbers: [...taskPairs.map((task) => task.os_number), "9999"] });
assert.deepEqual(
  perTaskCandidates.map((candidate) => [candidate.numOs, candidate.code]),
  taskPairs.map((task) => [task.os_number, task.close_code]),
);
assert.equal(perTaskCandidates.some((candidate) => candidate.numOs === "9999"), false);

const structuredEquipmentBlockStart = source.indexOf("function semiAutoEquipmentSerial(");
const structuredEquipmentBlockEnd = source.indexOf("function semiAutoCandidateEquipmentPlan(", structuredEquipmentBlockStart);
assert.notEqual(structuredEquipmentBlockStart, -1, "semiAutoEquipmentSerial not found");
assert.notEqual(structuredEquipmentBlockEnd, -1, "semiAutoCandidateEquipmentPlan not found");
const structuredEquipmentFactory = new Function(`
  ${source.slice(structuredEquipmentBlockStart, structuredEquipmentBlockEnd)}
  return { semiAutoStructuredEquipmentPlan };
`);
const structuredEquipmentPlan = structuredEquipmentFactory().semiAutoStructuredEquipmentPlan;
const normalFourSerials = structuredEquipmentPlan(
  [
    { serial: "241785999808", type: "decoder" },
    { serial: "24E4CE88F5DE", type: "emta" },
  ],
  [
    { serial: "104121362570", type: "emta" },
    { serial: "B4F2674E8BCB", type: "emta" },
  ],
  { technician_observation: "Troca do equipamento de serial: 104121362570 pelo de serial: B4F2674E8BCB. Troca do equipamento de serial: B4F2674E8BCB pelo de serial: 24E4CE88F5DE." },
);
assert.deepEqual(normalFourSerials.installed.map((item) => item.serial), ["241785999808", "24E4CE88F5DE"]);
assert.deepEqual(normalFourSerials.removed.map((item) => item.serial), ["104121362570", "B4F2674E8BCB"]);
assert.equal(normalFourSerials.correction, null);
assert.equal(normalFourSerials.error, "");

const substitutionPlan = structuredEquipmentPlan(
  [
    { serial: "SERIALX", type: "emta" },
    { serial: "SERIALY", type: "emta" },
  ],
  [{ serial: "SERIALX", type: "emta" }],
  { technician_observation: "Troca do equipamento de serial: SERIALX pelo de serial: SERIALY." },
);
assert.deepEqual(substitutionPlan.installed.map((item) => item.serial), ["SERIALX"]);
assert.deepEqual(substitutionPlan.removed, []);
assert.equal(substitutionPlan.correction.source_serial, "SERIALX");
assert.equal(substitutionPlan.correction.replacement_serial, "SERIALY");
assert.deepEqual(substitutionPlan.correction.materials, []);
assert.deepEqual(substitutionPlan.correction.installed.map((item) => item.serial), ["SERIALY"]);
assert.deepEqual(substitutionPlan.correction.removed.map((item) => item.serial), ["SERIALX"]);

const materialOwnerFactory = new Function(`
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }
  function toaLiveMaterialIdentity(item) {
    return {
      code: String(item.material_code || item.code || ""),
      description: String(item.description || ""),
      ignored: false,
    };
  }
  ${extractFunction("closeCodeAllowsMaterials")}
  ${extractFunction("isNoEquipmentService")}
  ${extractFunction("toaLiveMaterialsDraft")}
  ${extractFunction("semiAutoMaterialGroupKey")}
  ${extractFunction("semiAutoCandidateAcceptsMaterials")}
  ${extractFunction("semiAutoMaterialOwnerScore")}
  ${extractFunction("semiAutoAssignMaterialOwners")}
  ${extractFunction("semiAutoCandidateMaterials")}
  return { semiAutoAssignMaterialOwners, semiAutoCandidateMaterials };
`);
const { semiAutoAssignMaterialOwners, semiAutoCandidateMaterials } = materialOwnerFactory();

const moveCapture = {
  aid: "197700001",
  contract: "1230415",
  scheduled_date: "2026-08-24",
  work_type: "Mudanca de Endereco",
  materials: Array.from({ length: 8 }, (_, index) => ({
    material_code: `22026${String(index).padStart(3, "0")}`,
    description: `MATERIAL ${index + 1}`,
    quantity: index + 1,
  })),
};
const moveCandidates = semiAutoAssignMaterialOwners([
  { capture: moveCapture, order: { service: "MUDANCA DE ENDERECO" }, code: "409", numOs: "2652707142" },
  { capture: moveCapture, order: { service: "MUDANCA DE ENDERECO" }, code: "409", numOs: "2652707153" },
]);
assert.equal(moveCandidates.filter((candidate) => candidate.materialOwner).length, 1);
assert.equal(moveCandidates[0].materialOwner, true);
assert.equal(moveCandidates[1].materialOwner, false);
assert.equal(semiAutoCandidateMaterials(moveCandidates[0]).length, 8);
assert.equal(semiAutoCandidateMaterials(moveCandidates[1]).length, 0);
assert.equal(moveCandidates[0].materialOwnerOs, "2652707142");

const splitActivityCandidates = semiAutoAssignMaterialOwners([
  { capture: { ...moveCapture, aid: "A1" }, order: { service: "MUDANCA DE ENDERECO" }, code: "409", numOs: "1" },
  { capture: { ...moveCapture, aid: "A2" }, order: { service: "MUDANCA DE ENDERECO" }, code: "409", numOs: "2" },
]);
assert.equal(splitActivityCandidates.filter((candidate) => candidate.materialOwner).length, 2);

const adhesionCandidates = semiAutoAssignMaterialOwners([
  { capture: { ...moveCapture, aid: "A3", work_type: "ADESAO" }, order: { service: "ADESAO - INSTALACAO DE ASSINATURA" }, code: "409", numOs: "10" },
  { capture: { ...moveCapture, aid: "A3", work_type: "ADESAO" }, order: { service: "ADESAO - INSTALAR PONTO VIRTUA" }, code: "409", numOs: "11" },
]);
assert.equal(adhesionCandidates[0].materialOwner, false);
assert.equal(adhesionCandidates[1].materialOwner, true);
assert.equal(adhesionCandidates[0].materialEligible, false);

const materialAllocationFactory = new Function(`
  const APPROVED_MATERIAL_EQUIVALENCE_GROUPS = [
    { key: "fiber_connector", codes: ["22065513", "22069613"] },
    { key: "mini_isolador", codes: ["22056364", "22067384"] },
    { key: "cabo_drop_1fo", codes: ["22061736", "22057657"] },
  ];
  ${extractFunction("autoCloseMaterialFamily")}
  ${extractFunction("consolidateAutoCloseMaterials")}
  ${extractFunction("allocateAutoCloseMaterial")}
  return { consolidateAutoCloseMaterials, allocateAutoCloseMaterial };
`);
const { consolidateAutoCloseMaterials, allocateAutoCloseMaterial } = materialAllocationFactory();

const consolidatedFiber = consolidateAutoCloseMaterials([
  { code: "22065513", description: "CONECTOR A", quantity: 1 },
  { code: "22069613", description: "CONECTOR B", quantity: 2 },
]);
assert.equal(consolidatedFiber.length, 2);
assert.deepEqual(
  consolidatedFiber.map((item) => [item.code, item.quantity]),
  [["22065513", 1], ["22069613", 2]],
);

const retornoEquivalent = allocateAutoCloseMaterial(
  { code: "22065513", description: "CONECTOR FO", quantity: 2 },
  [
    { code: "22065513", stock_quantity: 0, return_stock_quantity: 0 },
    { code: "22069613", stock_quantity: 0, return_stock_quantity: 27 },
  ],
);
assert.equal(retornoEquivalent.missingQuantity, 0);
assert.deepEqual(retornoEquivalent.allocated.map((item) => [item.code, item.quantity]), [["22069613", 2]]);

const splitEquivalent = allocateAutoCloseMaterial(
  { code: "22061736", description: "CABO DROP", quantity: 46 },
  [
    { code: "22061736", stock_quantity: 45, return_stock_quantity: 0 },
    { code: "22057657", stock_quantity: 1, return_stock_quantity: 0 },
  ],
);
assert.equal(splitEquivalent.missingQuantity, 0);
assert.deepEqual(splitEquivalent.allocated.map((item) => [item.code, item.quantity]), [
  ["22061736", 45],
  ["22057657", 1],
]);

const partialEquivalent = allocateAutoCloseMaterial(
  { code: "22056364", description: "MINI ISOLADOR", quantity: 3 },
  [{ code: "22067384", stock_quantity: 2, return_stock_quantity: 0 }],
);
assert.equal(partialEquivalent.missingQuantity, 1);
assert.equal(partialEquivalent.allocated[0].quantity, 2);

const ownerSwitchFactory = new Function(`
  function semiAutoUpdateExistingDraft() {}
  ${extractFunction("semiAutoSetMaterialOwner")}
  return { semiAutoSetMaterialOwner };
`);
const { semiAutoSetMaterialOwner } = ownerSwitchFactory();
const switchJob = { profile: "natal", candidates: moveCandidates };
semiAutoSetMaterialOwner(switchJob, 1);
assert.equal(moveCandidates[0].materialOwner, false);
assert.equal(moveCandidates[1].materialOwner, true);
assert.ok(moveCandidates.every((candidate) => candidate.materialOwnerOs === "2652707153"));
assert.ok(moveCandidates.every((candidate) => candidate.reviewed === false));

const contractGroupingFactory = new Function(`
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }
  ${extractFunction("semiAutoMaterialGroupKey")}
  ${extractFunction("semiAutoCandidateService")}
  ${extractFunction("semiAutoCandidateKind")}
  ${extractFunction("semiAutoActivityGroups")}
  ${extractFunction("semiAutoContractServiceSummary")}
  return { semiAutoActivityGroups, semiAutoContractServiceSummary, semiAutoCandidateKind };
`);
const {
  semiAutoActivityGroups,
  semiAutoContractServiceSummary,
  semiAutoCandidateKind,
} = contractGroupingFactory();
const groupedMoveJob = { candidates: moveCandidates };
assert.equal(semiAutoActivityGroups(groupedMoveJob).length, 1);
assert.equal(semiAutoActivityGroups(groupedMoveJob)[0].candidates.length, 2);
assert.equal(semiAutoContractServiceSummary(groupedMoveJob), "Mudanca de Endereco (2)");
assert.equal(semiAutoCandidateKind(adhesionCandidates[0]), "Assinatura");
assert.equal(semiAutoCandidateKind(adhesionCandidates[1]), "Ponto Virtua");

const queueFactory = new Function(`
  const SEMI_AUTO_ROUTE = "NTL-DMV";
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }
  function disconnectActivityComplete(value) {
    const status = normalize(value);
    return ["COMPLETE", "CONCLUID", "EXECUTAD", "FINALIZAD"]
      .some((candidate) => status.includes(candidate));
  }
  ${extractFunction("semiAutoCanonicalRoute")}
  ${extractFunction("semiAutoOrderRoute")}
  ${extractFunction("semiAutoWindow")}
  ${extractFunction("semiAutoOrderWindow")}
  ${extractFunction("semiAutoOrderKey")}
  ${extractFunction("semiAutoEnrichOrders")}
  ${extractFunction("semiAutoCompareJobs")}
  ${extractFunction("semiAutoOriginalWindowKey")}
  ${extractFunction("semiAutoBuildJobs")}
  ${extractFunction("semiAutoJobDueNow")}
  return {
    semiAutoBuildJobs,
    semiAutoCompareJobs,
    semiAutoEnrichOrders,
    semiAutoJobDueNow,
    semiAutoOrderRoute,
  };
`);
const {
  semiAutoBuildJobs,
  semiAutoCompareJobs,
  semiAutoEnrichOrders,
  semiAutoJobDueNow,
  semiAutoOrderRoute,
} = queueFactory();
const orderedJobs = semiAutoBuildJobs([
  { contract: "120012", window: "08:00 - 12:00", window_start: 480, window_end: 720 },
  { contract: "120010", window: "08:00 - 10:00", window_start: 480, window_end: 600 },
  { contract: "120011", window: "08:00 - 11:00", window_start: 480, window_end: 660 },
  { contract: "120099", window: "", window_start: 1440, window_end: 1440 },
  { contract: "120007", window: "08:00 - 09:00", window_start: 480, window_end: 540 },
], [
  { contract: "120012", num_os: "3" },
  { contract: "120010", num_os: "1" },
  { contract: "120011", num_os: "2" },
  { contract: "120099", num_os: "6" },
], "natal");
assert.deepEqual(
  orderedJobs.map((job) => job.contract),
  ["120007", "120010", "120011", "120012", "120099"],
);
assert.ok(orderedJobs.every((job) => job.route === "NTL-DMV"));
assert.equal(orderedJobs[0].state, "pending");
assert.equal(orderedJobs[0].imperiumSeen, false);
assert.equal(orderedJobs[1].state, "pending");
assert.equal(orderedJobs.at(-1).contract, "120099");
assert.equal(orderedJobs.at(-1).state, "skipped");
assert.match(orderedJobs.at(-1).message, /Janela hor[aá]ria/i);

const enrichedOrders = semiAutoEnrichOrders([
  { contract: "120020", num_os: "20", service_window: "" },
], [
  {
    contract: "120020",
    num_os: "20",
    bucket: "NTL-DMV",
    activity_status: "complete",
    activity_id: "A20",
    service_window: "08:00 - 11:00",
  },
]);
assert.equal(enrichedOrders[0].service_window, "08:00 - 11:00");
assert.equal(enrichedOrders[0].route, "NTL-DMV");
assert.equal(enrichedOrders[0].activity_id, "A20");

const csvEnrichedOrders = semiAutoEnrichOrders([
  { contract: "120021", num_os: "21", service_window: "" },
], [
  {
    contract: "120021",
    os_number: "21",
    source_file: "Atividades-NTL-DMV_25_08_26.csv",
    activity_status: "complete",
    service_window: "08:00 - 10:00",
  },
]);
assert.equal(csvEnrichedOrders[0].service_window, "08:00 - 10:00");
assert.equal(semiAutoOrderRoute(csvEnrichedOrders[0]), "NTL-DMV");

const futureJob = { windowStart: 12 * 60, windowEnd: 15 * 60 };
assert.equal(semiAutoJobDueNow(futureJob, new Date(2026, 7, 25, 10, 0)), false);
assert.equal(semiAutoJobDueNow(futureJob, new Date(2026, 7, 25, 12, 0)), true);
assert.equal(
  semiAutoJobDueNow({ ...futureJob, windowOverrideMode: "now" }, new Date(2026, 7, 25, 10, 0)),
  true,
);
const manuallyPrioritized = [
  { contract: "1", windowStart: 660, windowEnd: 840, windowOverrideMode: "", windowOverrideAt: 0 },
  { contract: "2", windowStart: 900, windowEnd: 1080, windowOverrideMode: "now", windowOverrideAt: 100 },
].sort(semiAutoCompareJobs);
assert.equal(manuallyPrioritized[0].contract, "2");
assert.equal(orderedJobs[0].originalWindowLabel, "08:00 - 09:00");
assert.equal(orderedJobs[0].windowOverrideMode, "");
assert.equal(
  semiAutoJobDueNow({ windowStart: 1440, windowEnd: 1440 }, new Date(2026, 7, 25, 13, 0)),
  false,
);

const reconcileFactory = new Function(`
  const state = {
    semiAutoJobs: [{
      contract: "120030",
      osNumbers: ["30"],
      candidates: [{ numOs: "30" }],
      state: "ready",
      imperiumSeen: true,
      windowStart: 480,
      windowEnd: 600,
      windowLabel: "08:00 - 10:00",
    }],
  };
  ${extractFunction("semiAutoWindow")}
  ${extractFunction("semiAutoOrderWindow")}
  ${extractFunction("semiAutoCompareJobs")}
  ${extractFunction("semiAutoReconcileJobsWithOrders")}
  return { state, semiAutoReconcileJobsWithOrders };
`);
const { state: reconcileState, semiAutoReconcileJobsWithOrders } = reconcileFactory();
semiAutoReconcileJobsWithOrders([]);
assert.equal(reconcileState.semiAutoJobs[0].state, "skipped");
assert.match(reconcileState.semiAutoJobs[0].message, /n[aã]o est[aá] mais em campo/i);

reconcileState.semiAutoJobs = [{
  contract: "120031",
  osNumbers: [],
  candidates: [],
  state: "skipped",
  skipCategory: "awaiting_imperium_import",
  imperiumSeen: false,
  agendaWindow: true,
  windowStart: 480,
  windowEnd: 600,
  windowLabel: "08:00 - 10:00",
}];
semiAutoReconcileJobsWithOrders([{ contract: "120031", num_os: "31" }]);
assert.equal(reconcileState.semiAutoJobs[0].state, "pending");
assert.equal(reconcileState.semiAutoJobs[0].imperiumSeen, true);
assert.deepEqual(reconcileState.semiAutoJobs[0].osNumbers, ["31"]);
assert.match(reconcileState.semiAutoJobs[0].message, /retomando baixa automática/i);

console.log("semiautomatic review-only frontend tests: ok");
