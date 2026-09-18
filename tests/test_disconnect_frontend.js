const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "static", "app.js"),
  "utf8",
);

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

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .trim();
}

function extractObjectConstant(name) {
  const marker = `const ${name} = {`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `${name} not found`);
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return Function(`return (${source.slice(bodyStart, index + 1)})`)();
  }
  throw new Error(`Could not extract ${name}`);
}

function disconnectManualError(message) {
  const error = new Error(message);
  error.manualReview = true;
  return error;
}

const CANONICAL_MATERIAL_MAP = extractObjectConstant("CANONICAL_MATERIAL_MAP");

eval(extractFunction("toaLiveMaterialIdentity"));
eval(extractFunction("disconnectMaterialsDraft"));
eval(extractFunction("disconnectAutomationMaterialDraft"));
eval(extractFunction("disconnectQueueItemHasAdmScope"));
eval(extractFunction("disconnectTaskExecuted"));
eval(extractFunction("disconnectTransientToaError"));
eval(extractFunction("disconnectCaptureBlockers"));
eval(extractFunction("disconnectConsolidateStreamingPackage"));

assert.equal(disconnectQueueItemHasAdmScope({
  source_files: ["Atividades-NTL-DMV_ADM_29_07_26.csv"],
}), true);
assert.equal(disconnectQueueItemHasAdmScope({
  source_files: ["Atividades-PWM-DMV_ADM_29_07_26.csv"],
}), true);
assert.equal(disconnectQueueItemHasAdmScope({
  source_files: ["Atividades-PWM-DMV_VT_29_07_26.csv"],
}), false);
assert.equal(disconnectQueueItemHasAdmScope({
  source_files: [
    "Atividades-NTL-DMV_ADM_29_07_26.csv",
    "Atividades-NTL-DMV_VT_29_07_26.csv",
  ],
}), false);
assert.equal(disconnectQueueItemHasAdmScope({
  source_files: ["Atividades-FTZ-DMV_ADM_29_07_26.csv"],
}), false);

assert.equal(disconnectTaskExecuted("E"), true);
assert.equal(disconnectTaskExecuted("N"), true);
assert.equal(disconnectTaskExecuted("concluido"), true);
assert.equal(disconnectTaskExecuted("P"), false);

assert.equal(
  disconnectTransientToaError(new Error("A sessao TOA nao esta autenticada")),
  true,
);
assert.equal(disconnectTransientToaError(new Error("Failed to fetch")), true);
assert.equal(disconnectTransientToaError(new Error("unknown_close_code:312")), false);
assert.deepEqual(
  disconnectCaptureBlockers({
    operation_blockers: ["activity_not_complete", "route_aid_missing"],
    validation_errors: ["activity_not_complete"],
  }),
  ["route_aid_missing"],
);

const sixDigit = toaLiveMaterialIdentity({
  material_code: "433135",
  description: "SAPATILHA DESCARTAVEL ELAS",
});
assert.equal(sixDigit.code, "433135");

const embedded = toaLiveMaterialIdentity({
  description: "22069613_CONECTOR FO CAMPO FAST SC/APC",
});
assert.equal(embedded.code, "22069613");
assert.equal(embedded.description, "CONECTOR FO CAMPO FAST SC/APC");

const draft = disconnectMaterialsDraft([
  {
    material_code: "433135",
    description: "SAPATILHA DESCARTAVEL ELAS",
    used_quantity: "2",
  },
  {
    material_code: "22057705",
    description: "FONTE CX DIG HD",
    used_quantity: "1",
  },
]);
assert.deepEqual(draft.materials, []);
assert.equal(draft.ignored.length, 2);
assert.ok(draft.ignored.every((item) => item.reason === "acessorio_nao_baixado"));

assert.throws(
  () => disconnectMaterialsDraft([
    {
      material_code: "CODIGO INVALIDO",
      description: "MATERIAL SEM CODIGO CONCRETO",
      used_quantity: "1",
    },
  ]),
  /material_code_invalid/,
);

const disconnectMaterials = disconnectAutomationMaterialDraft([
  {
    code: "22069613",
    description: "CONECTOR FO CAMPO FAST SC APC",
    quantity: "15",
  },
  {
    description: "material sem codigo que nao deve bloquear desconexao",
    quantity: "1",
  },
]);
assert.deepStrictEqual(disconnectMaterials.materials, []);
assert.strictEqual(disconnectMaterials.ignored.length, 2);
assert.ok(disconnectMaterials.ignored.every(
  (item) => item.reason === "disconnect_does_not_use_materials",
));

const packagePlan = {
  num_os: "2648934172",
  service: "MUD PACOTE ENTREGA STREAMING",
  code: "409",
  installed_equipment: [],
  removed_equipment: [],
};
const retirarPontoPlan = {
  num_os: "2648932215",
  service: "RETIRAR PONTO",
  code: "430",
  installed_equipment: [],
  removed_equipment: [],
};
const consolidated = disconnectConsolidateStreamingPackage(
  [retirarPontoPlan, packagePlan],
  [
    { serial: "229859131022", type: "decoder" },
    { serial: "246641136178", type: "smart" },
  ],
  [{ serial: "241773515155", type: "decoder" }],
);
assert.deepEqual(consolidated.plans, [packagePlan]);
assert.deepEqual(packagePlan.installed_equipment.map((item) => item.serial), [
  "229859131022",
  "246641136178",
]);
assert.deepEqual(packagePlan.removed_equipment.map((item) => item.serial), [
  "241773515155",
]);
assert.deepEqual(consolidated.skipped, [{
  num_os: "2648932215",
  service: "RETIRAR PONTO",
  reason: "retirar_ponto_kept_open",
}]);
assert.throws(
  () => disconnectConsolidateStreamingPackage(
    [
      packagePlan,
      { ...packagePlan, num_os: "2648934173" },
      retirarPontoPlan,
    ],
    [{ serial: "229859131022", type: "decoder" }],
    [],
  ),
  /streaming_package_target_ambiguous/,
);
assert.throws(
  () => disconnectConsolidateStreamingPackage(
    [retirarPontoPlan, { ...packagePlan, installed_equipment: [], removed_equipment: [] }],
    [],
    [{ serial: "241773515155", type: "decoder" }],
  ),
  /close_409_without_incoming_equipment/,
);

console.log("disconnect frontend material tests: ok");
