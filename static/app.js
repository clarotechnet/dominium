// =============================================================================
// DOMINIUM | MAPA DE RESPONSABILIDADE
//
// IMPERIUM
// - SIM - contem validacao, consulta ou operacao ligada ao Imperium.
//
// TOA
// - SIM - contem captura, contexto, importacao ou evidencia vinda do TOA.
//
// DOMINIUM COMPARTILHADO
// - Ponte entre os dois dominios; alterar com testes dos dois lados.
//
// Categoria deste arquivo: MISTO.
// Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
// A ordem executavel abaixo foi preservada para evitar regressao.
// =============================================================================
const state = {
  authUser: null,
  authCsrfToken: "",
  authReady: false,
  profiles: [],
  profile: new URLSearchParams(window.location.search).get("profile") || "natal",
  profileEpoch: 0,
  closeEnabled: false,
  officialCloseEnabled: false,
  materialWriteoffEnabled: false,
  nativeCreationEnabled: false,
  installerChangeEnabled: false,
  serializedTransferEnabled: false,
  nativeCreationServices: [],
  orders: [],
  selected: new Set(),
  completed: 0,
  loading: false,
  profileSwitching: false,
  running: false,
  paused: false,
  stopped: false,
  pendingConfirmation: [],
  pendingProductive: null,
  productiveDrafts: {},
  pendingCode: "106",
  pendingCloseExtra: {},
  closeCode: "106",
  closeCodes: [
    { code: "106", description: "CLIENTE AUSENTE", productive: false },
    { code: "0", description: "CANCELAMENTO", productive: false },
  ],
  failures: [],
  activeModule: window.location.hash === "#monitor"
    ? "close"
    : window.location.hash === "#inteligencia"
      ? "intelligence"
      : window.location.hash === "#importacao"
          ? "imports"
          : window.location.hash === "#tecnicos"
            ? "technicians"
            : window.location.hash === "#estoque"
              ? "stock"
              : window.location.hash === "#criar-os"
                ? "bulk"
                : window.location.hash === "#baixar-os"
                  ? "close"
                  : window.location.hash === "#relatorio"
                    ? "report"
                    : window.location.hash === "#historico"
                      ? "history"
                      : window.location.hash === "#base-operacional"
                        ? "database"
                      : window.location.hash === "#ordens" || window.location.hash === "#falhas"
                        ? "orders"
                        : "close",
  activeView: window.location.hash === "#falhas" ? "failures" : "orders",
  importTargets: [],
  importTarget: "rn",
  importFile: null,
  importPreview: null,
  selectedImportOs: null,
  importResult: null,
  importLoading: false,
  toaAutomation: null,
  toaAutomationLoading: false,
  automationTestLots: [],
  automationTestLotKey: "",
  automationTestRegistry: null,
  automationTestResult: null,
  automationTestLoading: false,
  automationTestMessage: "",
  toaLiveStatus: null,
  toaLiveConnecting: false,
  toaLiveLoading: false,
  toaLiveResult: null,
  semiAutoJobs: [],
  semiAutoRunning: false,
  semiAutoPaused: false,
  semiAutoStopRequested: false,
  semiAutoWorker: false,
  semiAutoPendingConfirmationWorker: false,
  semiAutoProfile: "",
  semiAutoCurrentContract: "",
  semiAutoWaitingWindow: "",
  semiAutoToaRetryWaitingUntil: 0,
  semiAutoRefreshing: false,
  semiAutoLastImperiumCheckAt: 0,
  semiAutoJobsSinceImperiumCheck: 0,
  semiAutoReviewJobIndex: -1,
  semiAutoAgenda: null,
  semiAutoAgendaLoading: false,
  disconnectAutomation: null,
  disconnectAutomationLoading: false,
  disconnectAutomationWorker: false,
  disconnectAutomationStopRequested: false,
  disconnectToaHealthy: false,
  disconnectAutoPausing: false,
  stockTechnicians: [],
  stockTechniciansLoading: false,
  stockSource: "datasnap",
  stockSelectedId: "",
  stockData: null,
  stockLoading: false,
  stockBatchSelected: new Set(),
  stockBatchLoading: false,
  stockWriteoffLoading: false,
  pendingStockWriteoff: null,
  stockWriteoffBasket: new Map(),
  stockWriteoffRequestId: null,
  stockWriteoffBlocked: new Set(),
  technicians: [],
  technicianTeams: {},
  technicianSource: {},
  techniciansLoading: false,
  bulkCreateLoading: false,
  bulkCreateResult: null,
  bulkCreateRequestId: null,
  closeWorkspaceOrderId: null,
  closeInstallerChecks: {},
  closeReport: { records: [], summary: {} },
  closeReportLoading: false,
  operationalDatabase: { contracts: [], total: 0 },
  operationalDatabaseLoading: false,
  operationalContract: null,
  serverLogs: [],
  serverLogLoading: false,
  serverLogUpdatedAt: "",
  importAuditHistory: [],
  importAuditLoading: false,
  importAuditLoaded: false,
  importAuditMalformed: 0,
  materialInventory: [],
  materialLoading: false,
  materialPasteLoading: false,
  materialError: "",
  materialNotice: "",
  currentMaterialPasteKey: "",
  materialEquivalenceConfirmed: false,
  serialOwnerLookup: null,
  installerMovePreview: null,
  installerMoveLoading: false,
  installerMoveError: "",
  serializedTransferPreview: null,
  serializedTransferLoading: false,
  serializedTransferError: "",
  monitorView: "monitor",
  monitorDemoMode: false,
  monitorNotifications: localStorage.getItem("dominium-monitor-notifications") === "1",
  monitorAlerted: new Set(),
  monitorVoiceEnabled: localStorage.getItem("dominium-monitor-voice") === "1",
  monitorVoiceAlerted: loadTec1VoiceAlertKeys(),
  monitorVoiceQueue: [],
  monitorVoiceSpeaking: false,
  monitorVoiceAbort: null,
  monitorVoiceAudio: null,
  monitorVoiceAudioUrl: "",
  monitorExportRows: [],
  monitorExportColumns: [],
  monitorLastUpdatedAt: "",
  monitorSnapshotStale: false,
  monitorCsvSnapshot: null,
  monitorCsvLoading: false,
  monitorAttentionIndex: 0,
  monitorAttentionPaused: false,
  monitorAttentionSignature: "",
  monitorAttentionTimer: null,
  monitorAttentionPoints: [],
  monitorTvActive: false,
  monitorTvDemo: true,
  monitorTvDemoOrders: null,
  monitorTvSlideIndex: 0,
  monitorTvPaused: false,
  monitorTvSlideTimer: null,
  monitorTvClockTimer: null,
  sidebarCollapsed: localStorage.getItem("dominium-sidebar-collapsed") === "1",
  intelligence: null,
  intelligenceLoading: false,
  healthCheck: null,
  healthLoading: false,
  serialAudit: null,
  serialAuditLoading: false,
};

const DOMINIUM_THEME_KEY = "dominium-theme";

function currentTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function syncThemeControls() {
  const light = currentTheme() === "light";
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    const action = light ? "Alternar para tema escuro" : "Alternar para tema claro";
    button.setAttribute("aria-label", action);
    button.setAttribute("title", action);
    const label = button.querySelector("[data-theme-label]");
    if (label) label.textContent = light ? "Tema claro" : "Tema escuro";
  });
}

function applyTheme(theme) {
  const selected = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = selected;
  localStorage.setItem(DOMINIUM_THEME_KEY, selected);
  syncThemeControls();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-theme-toggle]");
  if (!button) return;
  applyTheme(currentTheme() === "light" ? "dark" : "light");
});

const elements = {
  authGate: document.querySelector("#authGate"),
  authMascots: document.querySelector("#authMascots"),
  authLoginTab: document.querySelector("#authLoginTab"),
  authRegisterTab: document.querySelector("#authRegisterTab"),
  authLoginForm: document.querySelector("#authLoginForm"),
  authRegisterForm: document.querySelector("#authRegisterForm"),
  authLoginUsername: document.querySelector("#authLoginUsername"),
  authLoginPassword: document.querySelector("#authLoginPassword"),
  authLoginSubmit: document.querySelector("#authLoginSubmit"),
  authRegisterName: document.querySelector("#authRegisterFirstName"),  // kept for legacy focus ref
  authRegisterFirstName: document.querySelector("#authRegisterFirstName"),
  authRegisterLastName: document.querySelector("#authRegisterLastName"),
  authRegisterUsername: document.querySelector("#authRegisterUsername"),
  authRegisterPassword: document.querySelector("#authRegisterPassword"),
  authRegisterEmail: document.querySelector("#authRegisterEmail"),
  authRegisterSubmit: document.querySelector("#authRegisterSubmit"),
  authMessage: document.querySelector("#authMessage"),
  authTitle: document.querySelector("#authTitle"),
  authSubtitle: document.querySelector("#authSubtitle"),
  notificationBell: document.querySelector("#notificationBell"),
  notificationBadge: document.querySelector("#notificationBadge"),
  approveUserDialog: document.querySelector("#approveUserDialog"),
  approveUserForm: document.querySelector("#approveUserForm"),
  approveRoleSelect: document.querySelector("#approveRoleSelect"),
  approveUserCancel: document.querySelector("#approveUserCancel"),
  approveUserConfirm: document.querySelector("#approveUserConfirm"),
  approveUserDialogDesc: document.querySelector("#approveUserDialogDesc"),
  rejectUserDialog: document.querySelector("#rejectUserDialog"),
  rejectUserForm: document.querySelector("#rejectUserForm"),
  rejectReasonInput: document.querySelector("#rejectReasonInput"),
  rejectUserCancel: document.querySelector("#rejectUserCancel"),
  rejectUserConfirm: document.querySelector("#rejectUserConfirm"),
  rejectUserDialogDesc: document.querySelector("#rejectUserDialogDesc"),
  operatorButton: document.querySelector("#operatorButton"),
  operatorName: document.querySelector("#operatorName"),
  operatorRole: document.querySelector("#operatorRole"),
  operatorAvatar: document.querySelector("#operatorAvatar"),
  accountDialog: document.querySelector("#accountDialog"),
  accountClose: document.querySelector("#accountClose"),
  accountLogout: document.querySelector("#accountLogout"),
  accountName: document.querySelector("#accountName"),
  accountMeta: document.querySelector("#accountMeta"),
  accountAvatar: document.querySelector("#accountAvatar"),
  accountDatasnapActor: document.querySelector("#accountDatasnapActor"),
  accountAuditActor: document.querySelector("#accountAuditActor"),
  accountAdminSection: document.querySelector("#accountAdminSection"),
  accountUsersRefresh: document.querySelector("#accountUsersRefresh"),
  accountUsersList: document.querySelector("#accountUsersList"),
  product: document.querySelector("#productName"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  sidebar: document.querySelector("#primarySidebar"),
  profileTabs: document.querySelector("#profileTabs"),
  connection: document.querySelector("#connectionStatus"),
  pendingLabel: document.querySelector("#pendingLabel"),
  pendingCount: document.querySelector("#pendingCount"),
  selectedCount: document.querySelector("#selectedCount"),
  completedCount: document.querySelector("#completedCount"),
  codeOptions: [...document.querySelectorAll("[data-close-code]")],
  date: document.querySelector("#dateFilter"),
  search: document.querySelector("#searchFilter"),
  status: document.querySelector("#statusFilter"),
  service: document.querySelector("#serviceFilter"),
  transport: document.querySelector("#transportFilter"),
  refresh: document.querySelector("#refreshButton"),
  batch: document.querySelector("#batchButton"),
  selectAll: document.querySelector("#selectAll"),
  body: document.querySelector("#ordersBody"),
  loading: document.querySelector("#loadingState"),
  empty: document.querySelector("#emptyState"),
  ordersTab: document.querySelector("#ordersTab"),
  failuresTab: document.querySelector("#failuresTab"),
  failureCount: document.querySelector("#failureCount"),
  ordersSection: document.querySelector("#ordersSection"),
  failuresSection: document.querySelector("#failuresSection"),
  failuresBody: document.querySelector("#failuresBody"),
  failuresEmpty: document.querySelector("#failuresEmpty"),
  runbar: document.querySelector("#runbar"),
  runTitle: document.querySelector("#runTitle"),
  runDetail: document.querySelector("#runDetail"),
  progress: document.querySelector("#progressFill"),
  pause: document.querySelector("#pauseButton"),
  stop: document.querySelector("#stopButton"),
  dashboardModule: document.querySelector("#dashboardModule"),
  monitorModule: document.querySelector("#monitorModule"),
  ordersModule: document.querySelector("#ordersModule"),
  stockModule: document.querySelector("#stockModule"),
  techniciansModule: document.querySelector("#techniciansModule"),
  intelligenceModule: document.querySelector("#intelligenceModule"),
  bulkCreateModule: document.querySelector("#bulkCreateModule"),
  importsModule: document.querySelector("#importsModule"),
  automationTestModule: document.querySelector("#automationTestModule"),
  closeModule: document.querySelector("#closeModule"),
  reportModule: document.querySelector("#reportModule"),
  databaseModule: document.querySelector("#databaseModule"),
  historyModule: document.querySelector("#historyModule"),
  dashboardWorkspace: document.querySelector("#dashboardWorkspace"),
  monitorWorkspace: document.querySelector("#monitorWorkspace"),
  ordersWorkspace: document.querySelector("#ordersWorkspace"),
  stockWorkspace: document.querySelector("#stockWorkspace"),
  techniciansWorkspace: document.querySelector("#techniciansWorkspace"),
  intelligenceWorkspace: document.querySelector("#intelligenceWorkspace"),
  bulkCreateWorkspace: document.querySelector("#bulkCreateWorkspace"),
  importWorkspace: document.querySelector("#importWorkspace"),
  automationTestWorkspace: document.querySelector("#automationTestWorkspace"),
  closeWorkspace: document.querySelector("#closeWorkspace"),
  reportWorkspace: document.querySelector("#reportWorkspace"),
  databaseWorkspace: document.querySelector("#databaseWorkspace"),
  historyWorkspace: document.querySelector("#historyWorkspace"),
  databaseSearch: document.querySelector("#databaseSearch"),
  databaseDate: document.querySelector("#databaseDate"),
  databaseRefresh: document.querySelector("#databaseRefresh"),
  databaseList: document.querySelector("#databaseList"),
  databaseDetail: document.querySelector("#databaseDetail"),
  databaseContractCount: document.querySelector("#databaseContractCount"),
  databaseOsCount: document.querySelector("#databaseOsCount"),
  databaseEquipmentCount: document.querySelector("#databaseEquipmentCount"),
  databaseMaterialCount: document.querySelector("#databaseMaterialCount"),
  monitorNotify: document.querySelector("#monitorNotify"),
  monitorVoice: document.querySelector("#monitorVoice"),
  monitorTvOpen: document.querySelector("#monitorTvOpen"),
  monitorTv: document.querySelector("#monitorTv"),
  monitorDemo: document.querySelector("#monitorDemo"),
  monitorDemoBanner: document.querySelector("#monitorDemoBanner"),
  monitorCsvInput: document.querySelector("#monitorCsvInput"),
  monitorCsvOpen: document.querySelector("#monitorCsvOpen"),
  monitorCsvSource: document.querySelector("#monitorCsvSource"),
  monitorCsvSourceTitle: document.querySelector("#monitorCsvSourceTitle"),
  monitorCsvSourceDetail: document.querySelector("#monitorCsvSourceDetail"),
  monitorCsvReplace: document.querySelector("#monitorCsvReplace"),
  monitorCsvClear: document.querySelector("#monitorCsvClear"),
  monitorAttentionStage: document.querySelector("#monitorAttentionStage"),
  monitorExport: document.querySelector("#monitorExport"),
  monitorRefresh: document.querySelector("#monitorRefresh"),
  monitorFreshness: document.querySelector("#monitorFreshness"),
  monitorTotal: document.querySelector("#monitorTotal"),
  monitorField: document.querySelector("#monitorField"),
  monitorCompleted: document.querySelector("#monitorCompleted"),
  monitorPending: document.querySelector("#monitorPending"),
  monitorRevisits: document.querySelector("#monitorRevisits"),
  monitorClosedWithCode: document.querySelector("#monitorClosedWithCode"),
  monitorRouteAlerts: document.querySelector("#monitorRouteAlerts"),
  monitorTabs: document.querySelector("#monitorTabs"),
  monitorViewTitle: document.querySelector("#monitorViewTitle"),
  monitorViewSubtitle: document.querySelector("#monitorViewSubtitle"),
  monitorSearch: document.querySelector("#monitorSearch"),
  monitorBucket: document.querySelector("#monitorBucket"),
  monitorStatus: document.querySelector("#monitorStatus"),
  monitorNotice: document.querySelector("#monitorNotice"),
  monitorRouteConsole: document.querySelector("#monitorRouteConsole"),
  monitorTableWrap: document.querySelector("#monitorTableWrap"),
  monitorTableHead: document.querySelector("#monitorTableHead"),
  monitorTableBody: document.querySelector("#monitorTableBody"),
  healthNavStatus: document.querySelector("#healthNavStatus"),
  intelligenceDate: document.querySelector("#intelligenceDate"),
  intelligenceDays: document.querySelector("#intelligenceDays"),
  intelligenceRefresh: document.querySelector("#intelligenceRefresh"),
  intelligencePdf: document.querySelector("#intelligencePdf"),
  intelligenceSuccessRate: document.querySelector("#intelligenceSuccessRate"),
  intelligenceScoreRing: document.querySelector("#intelligenceScoreRing"),
  intelligencePeriodLabel: document.querySelector("#intelligencePeriodLabel"),
  intelligenceGenerated: document.querySelector("#intelligenceGenerated"),
  intelligenceConfirmed: document.querySelector("#intelligenceConfirmed"),
  intelligenceProblems: document.querySelector("#intelligenceProblems"),
  intelligenceAverageTime: document.querySelector("#intelligenceAverageTime"),
  intelligenceTechnicianSearch: document.querySelector("#intelligenceTechnicianSearch"),
  intelligenceTechnicianBody: document.querySelector("#intelligenceTechnicianBody"),
  intelligenceTechnicianEmpty: document.querySelector("#intelligenceTechnicianEmpty"),
  basePerformanceList: document.querySelector("#basePerformanceList"),
  healthRefresh: document.querySelector("#healthRefresh"),
  healthBaseGrid: document.querySelector("#healthBaseGrid"),
  healthCheckedAt: document.querySelector("#healthCheckedAt"),
  serialAuditRun: document.querySelector("#serialAuditRun"),
  serialAuditSummary: document.querySelector("#serialAuditSummary"),
  serialAuditBody: document.querySelector("#serialAuditBody"),
  serialAuditEmpty: document.querySelector("#serialAuditEmpty"),
  automationTestLot: document.querySelector("#automationTestLot"),
  automationTestContracts: document.querySelector("#automationTestContracts"),
  automationTestContractCount: document.querySelector("#automationTestContractCount"),
  automationTestAnalyze: document.querySelector("#automationTestAnalyze"),
  automationTestMessage: document.querySelector("#automationTestMessage"),
  automationTestLotMeta: document.querySelector("#automationTestLotMeta"),
  automationTestSummary: document.querySelector("#automationTestSummary"),
  automationTestResults: document.querySelector("#automationTestResults"),
  automationTestEmpty: document.querySelector("#automationTestEmpty"),
  automationWindowButtons: [...document.querySelectorAll("[data-automation-slot]")],
  automationSlot0900: document.querySelector("#automationSlot0900"),
  automationSlot1400: document.querySelector("#automationSlot1400"),
  automationSlot1720: document.querySelector("#automationSlot1720"),
  dashboardUpdated: document.querySelector("#dashboardUpdated"),
  dashboardOpenCount: document.querySelector("#dashboardOpenCount"),
  dashboardFieldCount: document.querySelector("#dashboardFieldCount"),
  dashboardCompletedCount: document.querySelector("#dashboardCompletedCount"),
  dashboardFailureCount: document.querySelector("#dashboardFailureCount"),
  dashboardTotalLabel: document.querySelector("#dashboardTotalLabel"),
  dashboardFieldBar: document.querySelector("#dashboardFieldBar"),
  dashboardSelectedBar: document.querySelector("#dashboardSelectedBar"),
  dashboardFailureBar: document.querySelector("#dashboardFailureBar"),
  dashboardCompletedBar: document.querySelector("#dashboardCompletedBar"),
  dashboardFieldLabel: document.querySelector("#dashboardFieldLabel"),
  dashboardSelectedLabel: document.querySelector("#dashboardSelectedLabel"),
  dashboardFailureLabel: document.querySelector("#dashboardFailureLabel"),
  dashboardCompletedLabel: document.querySelector("#dashboardCompletedLabel"),
  dashboardCityBars: document.querySelector("#dashboardCityBars"),
  dashboardAttentionCount: document.querySelector("#dashboardAttentionCount"),
  dashboardAttentionList: document.querySelector("#dashboardAttentionList"),
  dashboardRecentBody: document.querySelector("#dashboardRecentBody"),
  dashboardOpenOrders: document.querySelector("#dashboardOpenOrders"),
  stockSource: document.querySelector("#stockSource"),
  stockTechnicianSearch: document.querySelector("#stockTechnicianSearch"),
  stockTechnicianSelect: document.querySelector("#stockTechnicianSelect"),
  stockConsult: document.querySelector("#stockConsultButton"),
  stockPdf: document.querySelector("#stockPdfButton"),
  stockBatch: document.querySelector("#stockBatchButton"),
  stockShowZero: document.querySelector("#stockShowZero"),
  stockTechnicianName: document.querySelector("#stockTechnicianName"),
  stockPositiveCount: document.querySelector("#stockPositiveCount"),
  stockQuantityTotal: document.querySelector("#stockQuantityTotal"),
  stockSerialLabel: document.querySelector("#stockSerialLabel"),
  stockSerialCount: document.querySelector("#stockSerialCount"),
  stockItemSearch: document.querySelector("#stockItemSearch"),
  stockGroupFilter: document.querySelector("#stockGroupFilter"),
  stockBody: document.querySelector("#stockBody"),
  stockEmpty: document.querySelector("#stockEmpty"),
  stockLoading: document.querySelector("#stockLoading"),
  stockWriteoffOpen: document.querySelector("#stockWriteoffOpen"),
  stockWriteoffCount: document.querySelector("#stockWriteoffCount"),
  technicianSource: document.querySelector("#technicianSource"),
  technicianCount: document.querySelector("#technicianCount"),
  technicianPlateCount: document.querySelector("#technicianPlateCount"),
  technicianTeamCount: document.querySelector("#technicianTeamCount"),
  technicianVisibleCount: document.querySelector("#technicianVisibleCount"),
  technicianSearch: document.querySelector("#technicianSearch"),
  technicianTeamFilter: document.querySelector("#technicianTeamFilter"),
  technicianBody: document.querySelector("#technicianBody"),
  technicianEmpty: document.querySelector("#technicianEmpty"),
  technicianLoading: document.querySelector("#technicianLoading"),
  stockWriteoffDialog: document.querySelector("#stockWriteoffDialog"),
  stockWriteoffForm: document.querySelector("#stockWriteoffForm"),
  stockWriteoffTechnician: document.querySelector("#stockWriteoffTechnician"),
  stockWriteoffDialogCount: document.querySelector("#stockWriteoffDialogCount"),
  stockWriteoffItems: document.querySelector("#stockWriteoffItems"),
  stockWriteoffStatus: document.querySelector("#stockWriteoffStatus"),
  stockWriteoffCancel: document.querySelector("#stockWriteoffCancel"),
  stockWriteoffConfirm: document.querySelector("#stockWriteoffConfirm"),
  stockBatchDialog: document.querySelector("#stockBatchDialog"),
  stockBatchSearch: document.querySelector("#stockBatchSearch"),
  stockBatchCount: document.querySelector("#stockBatchCount"),
  stockBatchSelectVisible: document.querySelector("#stockBatchSelectVisible"),
  stockBatchClear: document.querySelector("#stockBatchClear"),
  stockBatchList: document.querySelector("#stockBatchList"),
  stockBatchIncludeZero: document.querySelector("#stockBatchIncludeZero"),
  stockBatchIncludeSerials: document.querySelector("#stockBatchIncludeSerials"),
  stockBatchStatus: document.querySelector("#stockBatchStatus"),
  stockBatchPrint: document.querySelector("#stockBatchPrint"),
  stockBatchPdf: document.querySelector("#stockBatchPdf"),
  bulkTechnicianSearch: document.querySelector("#bulkTechnicianSearch"),
  bulkTechnicianSelect: document.querySelector("#bulkTechnicianSelect"),
  bulkService: document.querySelector("#bulkService"),
  bulkCreateDate: document.querySelector("#bulkCreateDate"),
  bulkCloseCode: document.querySelector("#bulkCloseCode"),
  bulkContracts: document.querySelector("#bulkContracts"),
  bulkContractCount: document.querySelector("#bulkContractCount"),
  bulkCreateReview: document.querySelector("#bulkCreateReview"),
  bulkCreateResult: document.querySelector("#bulkCreateResult"),
  bulkCreateResultTitle: document.querySelector("#bulkCreateResultTitle"),
  bulkCreateResultDetail: document.querySelector("#bulkCreateResultDetail"),
  bulkCreateBody: document.querySelector("#bulkCreateBody"),
  bulkCreateEmpty: document.querySelector("#bulkCreateEmpty"),
  bulkCreateLoading: document.querySelector("#bulkCreateLoading"),
  bulkCreateDialog: document.querySelector("#bulkCreateDialog"),
  bulkConfirmTechnician: document.querySelector("#bulkConfirmTechnician"),
  bulkConfirmClient: document.querySelector("#bulkConfirmClient"),
  bulkConfirmCount: document.querySelector("#bulkConfirmCount"),
  bulkConfirmService: document.querySelector("#bulkConfirmService"),
  bulkConfirmCloseCode: document.querySelector("#bulkConfirmCloseCode"),
  manualTechnicianSearch: document.querySelector("#manualTechnicianSearch"),
  manualTechnicianSelect: document.querySelector("#manualTechnicianSelect"),
  manualService: document.querySelector("#manualService"),
  manualContract: document.querySelector("#manualContract"),
  manualCloseCode: document.querySelector("#manualCloseCode"),
  manualCreateReview: document.querySelector("#manualCreateReview"),
  importTargets: document.querySelector("#importTargets"),
  importFile: document.querySelector("#importFile"),
  importDropzone: document.querySelector("#importDropzone"),
  importSelectedFile: document.querySelector("#importSelectedFile"),
  chooseImportFile: document.querySelector("#chooseImportFile"),
  importFileName: document.querySelector("#importFileName"),
  commitImport: document.querySelector("#commitImport"),
  importSourceRows: document.querySelector("#importSourceRows"),
  importOrderCount: document.querySelector("#importOrderCount"),
  importCities: document.querySelector("#importCities"),
  importTargetLabel: document.querySelector("#importTargetLabel"),
  importSelectAll: document.querySelector("#importSelectAll"),
  importPreviewBody: document.querySelector("#importPreviewBody"),
  importEmpty: document.querySelector("#importEmpty"),
  importLoading: document.querySelector("#importLoading"),
  importResult: document.querySelector("#importResult"),
  importResultTitle: document.querySelector("#importResultTitle"),
  importResultDetail: document.querySelector("#importResultDetail"),
  toaAutomationPanel: document.querySelector("#toaAutomationPanel"),
  toaAutomationStatus: document.querySelector("#toaAutomationStatus"),
  toaAutomationStatusText: document.querySelector("#toaAutomationStatusText"),
  toaAutomationSchedule: document.querySelector("#toaAutomationSchedule"),
  toaAutomationNext: document.querySelector("#toaAutomationNext"),
  toaAutomationCurrent: document.querySelector("#toaAutomationCurrent"),
  toaAutomationLast: document.querySelector("#toaAutomationLast"),
  toaAutomationRun: document.querySelector("#toaAutomationRun"),
  toaAutomationRoutes: document.querySelector("#toaAutomationRoutes"),
  toaAutomationHistory: document.querySelector("#toaAutomationHistory"),
  closeQueueBadge: document.querySelector("#closeQueueBadge"),
  toaLiveSession: document.querySelector("#toaLiveSession"),
  toaLiveSessionText: document.querySelector("#toaLiveSessionText"),
  toaLiveOpen: document.querySelector("#toaLiveOpen"),
  headerToaOpen: document.querySelector("#headerToaOpen"),
  toaLoginDialog: document.querySelector("#toaLoginDialog"),
  toaLoginForm: document.querySelector("#toaLoginForm"),
  toaLoginUsername: document.querySelector("#toaLoginUsername"),
  toaLoginPassword: document.querySelector("#toaLoginPassword"),
  toaLoginError: document.querySelector("#toaLoginError"),
  toaLoginClose: document.querySelector("#toaLoginClose"),
  toaLoginCancel: document.querySelector("#toaLoginCancel"),
  toaLoginSubmit: document.querySelector("#toaLoginSubmit"),
  toaLiveContract: document.querySelector("#toaLiveContract"),
  toaLiveLookup: document.querySelector("#toaLiveLookup"),
  toaLiveLookupMessage: document.querySelector("#toaLiveLookupMessage"),
  toaLiveResult: document.querySelector("#toaLiveResult"),
  semiAutoStart: document.querySelector("#semiAutoStart"),
  autoCloseStart: document.querySelector("#autoCloseStart"),
  semiAutoPanel: document.querySelector("#semiAutoPanel"),
  semiAutoHeadline: document.querySelector("#semiAutoHeadline"),
  semiAutoPause: document.querySelector("#semiAutoPause"),
  semiAutoStop: document.querySelector("#semiAutoStop"),
  semiAutoProcessed: document.querySelector("#semiAutoProcessed"),
  semiAutoImperiumOpenCount: document.querySelector("#semiAutoImperiumOpenCount"),
  semiAutoImperiumClosedCount: document.querySelector("#semiAutoImperiumClosedCount"),
  semiAutoToaConsultedCount: document.querySelector("#semiAutoToaConsultedCount"),
  semiAutoClosedCount: document.querySelector("#semiAutoClosedCount"),
  semiAutoHumanCount: document.querySelector("#semiAutoHumanCount"),
  semiAutoToaPendingCount: document.querySelector("#semiAutoToaPendingCount"),
  semiAutoAwaitingImperiumCount: document.querySelector("#semiAutoAwaitingImperiumCount"),
  semiAutoReady: document.querySelector("#semiAutoReady"),
  semiAutoSkipped: document.querySelector("#semiAutoSkipped"),
  semiAutoSkippedCard: document.querySelector("#semiAutoSkippedCard"),
  semiAutoSkippedDialog: document.querySelector("#semiAutoSkippedDialog"),
  semiAutoSkippedClose: document.querySelector("#semiAutoSkippedClose"),
  semiAutoSkippedBottomClose: document.querySelector("#semiAutoSkippedBottomClose"),
  semiAutoSkippedList: document.querySelector("#semiAutoSkippedList"),
  semiAutoSkippedSearch: document.querySelector("#semiAutoSkippedSearch"),
  semiAutoSkippedFilters: document.querySelector("#semiAutoSkippedFilters"),
  semiAutoSkippedCopyBtn: document.querySelector("#semiAutoSkippedCopyBtn"),
  semiAutoSkippedCount: document.querySelector("#semiAutoSkippedCount"),
  semiAutoPending: document.querySelector("#semiAutoPending"),
  semiAutoCurrent: document.querySelector("#semiAutoCurrent"),
  semiAutoWindowControl: document.querySelector("#semiAutoWindowControl"),
  semiAutoWindowStatus: document.querySelector("#semiAutoWindowStatus"),
  semiAutoWindowList: document.querySelector("#semiAutoWindowList"),
  semiAutoReadyList: document.querySelector("#semiAutoReadyList"),
  semiAutoContractDialog: document.querySelector("#semiAutoContractDialog"),
  semiAutoContractTitle: document.querySelector("#semiAutoContractTitle"),
  semiAutoContractMeta: document.querySelector("#semiAutoContractMeta"),
  semiAutoContractActivities: document.querySelector("#semiAutoContractActivities"),
  semiAutoContractClose: document.querySelector("#semiAutoContractClose"),
  semiAutoAgendaFile: document.querySelector("#semiAutoAgendaFile"),
  semiAutoAgendaChoose: document.querySelector("#semiAutoAgendaChoose"),
  semiAutoAgendaName: document.querySelector("#semiAutoAgendaName"),
  semiAutoAgendaMessage: document.querySelector("#semiAutoAgendaMessage"),
  semiAutoAgendaContracts: document.querySelector("#semiAutoAgendaContracts"),
  semiAutoAgendaBlank: document.querySelector("#semiAutoAgendaBlank"),
  semiAutoAgendaNoWindow: document.querySelector("#semiAutoAgendaNoWindow"),
  semiAutoAgendaDuplicates: document.querySelector("#semiAutoAgendaDuplicates"),
  disconnectAutomation: document.querySelector("#disconnectAutomation"),
  disconnectAutomationMessage: document.querySelector("#disconnectAutomationMessage"),
  disconnectToaStatus: document.querySelector("#disconnectToaStatus"),
  disconnectToaStatusText: document.querySelector("#disconnectToaStatusText"),
  disconnectPrepare: document.querySelector("#disconnectPrepare"),
  disconnectStart: document.querySelector("#disconnectStart"),
  disconnectPause: document.querySelector("#disconnectPause"),
  disconnectResume: document.querySelector("#disconnectResume"),
  disconnectStop: document.querySelector("#disconnectStop"),
  disconnectQueueCount: document.querySelector("#disconnectQueueCount"),
  disconnectQueueStatus: document.querySelector("#disconnectQueueStatus"),
  disconnectWaitingCount: document.querySelector("#disconnectWaitingCount"),
  disconnectCompletedCount: document.querySelector("#disconnectCompletedCount"),
  disconnectReviewCount: document.querySelector("#disconnectReviewCount"),
  disconnectCurrentStage: document.querySelector("#disconnectCurrentStage"),
  disconnectCurrentWindow: document.querySelector("#disconnectCurrentWindow"),
  disconnectCurrentContract: document.querySelector("#disconnectCurrentContract"),
  disconnectCurrentOs: document.querySelector("#disconnectCurrentOs"),
  disconnectCurrentTechnician: document.querySelector("#disconnectCurrentTechnician"),
  disconnectCurrentAppointment: document.querySelector("#disconnectCurrentAppointment"),
  disconnectCurrentCode: document.querySelector("#disconnectCurrentCode"),
  disconnectCurrentService: document.querySelector("#disconnectCurrentService"),
  disconnectCurrentInstalled: document.querySelector("#disconnectCurrentInstalled"),
  disconnectCurrentRemoved: document.querySelector("#disconnectCurrentRemoved"),
  disconnectCurrentMaterials: document.querySelector("#disconnectCurrentMaterials"),
  disconnectCurrentResult: document.querySelector("#disconnectCurrentResult"),
  disconnectQueuePreview: document.querySelector("#disconnectQueuePreview"),
  closeQueueCount: document.querySelector("#closeQueueCount"),
  closeQueueSearch: document.querySelector("#closeQueueSearch"),
  closeQueue: document.querySelector("#closeQueue"),
  closeDetailEyebrow: document.querySelector("#closeDetailEyebrow"),
  closeDetailTitle: document.querySelector("#closeDetailTitle"),
  closeDetailStatus: document.querySelector("#closeDetailStatus"),
  closeDetailClient: document.querySelector("#closeDetailClient"),
  closeDetailLocation: document.querySelector("#closeDetailLocation"),
  closeDetailTechnician: document.querySelector("#closeDetailTechnician"),
  closeWorkspaceCode: document.querySelector("#closeWorkspaceCode"),
  closeWorkspaceDescription: document.querySelector("#closeWorkspaceDescription"),
  closeTransport: document.querySelector("#closeTransport"),
  closeObservationField: document.querySelector("#closeObservationField"),
  closeWorkspaceObservation: document.querySelector("#closeWorkspaceObservation"),
  closeMovementRule: document.querySelector("#closeMovementRule"),
  closeInstalledSummary: document.querySelector("#closeInstalledSummary"),
  closeRemovedSummary: document.querySelector("#closeRemovedSummary"),
  closeWorkspaceContinue: document.querySelector("#closeWorkspaceContinue"),
  closeOpenOrders: document.querySelector("#closeOpenOrders"),
  closeDetailEmpty: document.querySelector("#closeDetailEmpty"),
  reportDate: document.querySelector("#reportDate"),
  reportSearch: document.querySelector("#reportSearch"),
  reportState: document.querySelector("#reportState"),
  reportRefresh: document.querySelector("#reportRefresh"),
  reportExportXlsx: document.querySelector("#reportExportXlsx"),
  reportConfirmedCount: document.querySelector("#reportConfirmedCount"),
  reportPendingCount: document.querySelector("#reportPendingCount"),
  reportUncertainCount: document.querySelector("#reportUncertainCount"),
  reportFailedCount: document.querySelector("#reportFailedCount"),
  reportBody: document.querySelector("#reportBody"),
  reportEmpty: document.querySelector("#reportEmpty"),
  reportLoading: document.querySelector("#reportLoading"),
  historyDateLabel: document.querySelector("#historyDateLabel"),
  historyList: document.querySelector("#historyList"),
  historyLoadedCount: document.querySelector("#historyLoadedCount"),
  historyCompletedCount: document.querySelector("#historyCompletedCount"),
  historyFailureCount: document.querySelector("#historyFailureCount"),
  historyImportCount: document.querySelector("#historyImportCount"),
  historyImportAuditStatus: document.querySelector("#historyImportAuditStatus"),
  historyImportAuditDate: document.querySelector("#historyImportAuditDate"),
  historyImportAuditRefresh: document.querySelector("#historyImportAuditRefresh"),
  historyImportAuditList: document.querySelector("#historyImportAuditList"),
  serverLogStatus: document.querySelector("#serverLogStatus"),
  serverLogOutput: document.querySelector("#serverLogOutput"),
  refreshServerLog: document.querySelector("#refreshServerLog"),
  closePickerDialog: document.querySelector("#closePickerDialog"),
  closePickerOrder: document.querySelector("#closePickerOrder"),
  rowCloseCode: document.querySelector("#rowCloseCode"),
  dialog: document.querySelector("#confirmDialog"),
  confirmMessage: document.querySelector("#confirmMessage"),
  confirmCode: document.querySelector("#confirmCode"),
  confirmDescription: document.querySelector("#confirmDescription"),
  confirm: document.querySelector("#confirmButton"),
  serialOwnerDialog: document.querySelector("#serialOwnerDialog"),
  serialOwnerSerial: document.querySelector("#serialOwnerSerial"),
  serialOwnerLoading: document.querySelector("#serialOwnerLoading"),
  serialOwnerResult: document.querySelector("#serialOwnerResult"),
  serialOwnerCurrent: document.querySelector("#serialOwnerCurrent"),
  serialOwnerExpected: document.querySelector("#serialOwnerExpected"),
  serialOwnerEquipment: document.querySelector("#serialOwnerEquipment"),
  serialOwnerCode: document.querySelector("#serialOwnerCode"),
  serialOwnerScan: document.querySelector("#serialOwnerScan"),
  serialOwnerWarning: document.querySelector("#serialOwnerWarning"),
  serialOwnerError: document.querySelector("#serialOwnerError"),
  serialOwnerViewStock: document.querySelector("#serialOwnerViewStock"),
  serialOwnerTransfer: document.querySelector("#serialOwnerTransfer"),
  serialOwnerMoveOrder: document.querySelector("#serialOwnerMoveOrder"),
  installerMoveDialog: document.querySelector("#installerMoveDialog"),
  installerMoveMessage: document.querySelector("#installerMoveMessage"),
  installerMoveContract: document.querySelector("#installerMoveContract"),
  installerMoveTarget: document.querySelector("#installerMoveTarget"),
  installerMoveCount: document.querySelector("#installerMoveCount"),
  installerMoveOrders: document.querySelector("#installerMoveOrders"),
  installerMoveError: document.querySelector("#installerMoveError"),
  installerMoveCancel: document.querySelector("#installerMoveCancel"),
  installerMoveConfirm: document.querySelector("#installerMoveConfirm"),
  serializedTransferDialog: document.querySelector("#serializedTransferDialog"),
  serializedTransferMessage: document.querySelector("#serializedTransferMessage"),
  serializedTransferSerial: document.querySelector("#serializedTransferSerial"),
  serializedTransferSource: document.querySelector("#serializedTransferSource"),
  serializedTransferTarget: document.querySelector("#serializedTransferTarget"),
  serializedTransferEquipment: document.querySelector("#serializedTransferEquipment"),
  serializedTransferCode: document.querySelector("#serializedTransferCode"),
  serializedTransferError: document.querySelector("#serializedTransferError"),
  serializedTransferCancel: document.querySelector("#serializedTransferCancel"),
  serializedTransferConfirm: document.querySelector("#serializedTransferConfirm"),
  equipmentDialog: document.querySelector("#equipmentDialog"),
  equipmentOrder: document.querySelector("#equipmentOrder"),
  equipmentCode: document.querySelector("#equipmentCode"),
  equipmentDescription: document.querySelector("#equipmentDescription"),
  movementField: document.querySelector("#movementField"),
  movement: document.querySelector("#movementType"),
  installedSection: document.querySelector("#installedEquipmentSection"),
  removedSection: document.querySelector("#removedEquipmentSection"),
  installedRows: document.querySelector("#installedEquipmentRows"),
  removedRows: document.querySelector("#removedEquipmentRows"),
  addInstalled: document.querySelector("#addInstalledEquipment"),
  addRemoved: document.querySelector("#addRemovedEquipment"),
  materialSection: document.querySelector("#materialSection"),
  materialRows: document.querySelector("#materialRows"),
  materialStatus: document.querySelector("#materialStatus"),
  addMaterial: document.querySelector("#addMaterial"),
  materialPaste: document.querySelector("#materialPaste"),
  processMaterialPaste: document.querySelector("#processMaterialPaste"),
  materialEquivalenceReview: document.querySelector("#materialEquivalenceReview"),
  materialEquivalenceSummary: document.querySelector("#materialEquivalenceSummary"),
  materialEquivalenceConfirm: document.querySelector("#materialEquivalenceConfirm"),
  equipmentConfirm: document.querySelector("#equipmentConfirm"),
  termsOpen: document.querySelector("#termsOpenButton"),
  termsDialog: document.querySelector("#termsDialog"),
  termsClose: document.querySelector("#termsCloseButton"),
  termsDismiss: document.querySelector("#termsDismissButton"),
  termsAccept: document.querySelector("#termsAcceptButton"),
  toast: document.querySelector("#toast"),
};

const SIDEBAR_STORAGE_KEY = "dominium-sidebar-collapsed";

function renderSidebarState() {
  const collapsed = Boolean(state.sidebarCollapsed);
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  elements.sidebar?.setAttribute("data-collapsed", collapsed ? "true" : "false");
  elements.sidebarToggle?.setAttribute("aria-expanded", collapsed ? "false" : "true");
  const actionLabel = collapsed ? "Expandir menu lateral" : "Recolher menu lateral";
  elements.sidebarToggle?.setAttribute("aria-label", actionLabel);
  elements.sidebarToggle?.setAttribute("title", actionLabel);

  elements.sidebar?.querySelectorAll(".side-nav-item").forEach((item) => {
    const label = item.querySelector("strong")?.textContent?.trim() || "Abrir modulo";
    if (collapsed) item.setAttribute("title", label);
    else item.removeAttribute("title");
  });
  if (elements.termsOpen) {
    if (collapsed) elements.termsOpen.setAttribute("title", "Termos de uso");
    else elements.termsOpen.removeAttribute("title");
  }
}

function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, state.sidebarCollapsed ? "1" : "0");
  } catch (error) {
    console.warn("Nao foi possivel salvar o estado do menu lateral.", error);
  }
  renderSidebarState();
}

const TERMS_STORAGE_KEY = "dominium.terms.accepted.v1";

function openTermsDialog() {
  if (elements.termsDialog && !elements.termsDialog.open) {
    elements.termsDialog.showModal();
  }
}

function closeTermsDialog() {
  if (elements.termsDialog?.open) elements.termsDialog.close();
}

function acceptTerms() {
  try {
    window.localStorage.setItem(TERMS_STORAGE_KEY, "1");
  } catch (error) {
    console.warn("Nao foi possivel registrar a ciencia dos termos neste navegador.", error);
  }
  closeTermsDialog();
}

function showTermsOnFirstVisit() {
  let accepted = false;
  try {
    accepted = window.localStorage.getItem(TERMS_STORAGE_KEY) === "1";
  } catch (error) {
    console.warn("Nao foi possivel consultar a ciencia dos termos neste navegador.", error);
  }
  if (!accepted) openTermsDialog();
}

function localDate() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function normalize(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
}

function apiUrl(path) {
  return apiUrlForProfile(path, state.profile);
}

function apiUrlForProfile(path, profile) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("profile", profile);
  return `${url.pathname}${url.search}`;
}

function updateAddress() {
  const url = new URL(window.location.href);
  url.searchParams.set("profile", state.profile);
  url.hash = state.activeModule === "monitor"
    ? "monitor"
    : state.activeModule === "intelligence"
      ? "inteligencia"
      : state.activeModule === "imports"
          ? "importacao"
          : state.activeModule === "automation-test"
            ? "teste-automacao"
            : state.activeModule === "technicians"
              ? "tecnicos"
              : state.activeModule === "stock"
                ? "estoque"
                : state.activeModule === "bulk"
                  ? "criar-os"
                  : state.activeModule === "close"
                    ? "baixar-os"
                    : state.activeModule === "report"
                      ? "relatorio"
                      : state.activeModule === "database"
                        ? "base-operacional"
                      : state.activeModule === "history"
                        ? "historico"
                        : state.activeModule === "orders"
                          ? state.activeView === "failures" ? "falhas" : "ordens"
                          : "";
  window.history.replaceState(null, "", url);
}

// =============================================================================
// IMPERIUM | CODIGOS, REGRAS E ESTADO DA BAIXA
// =============================================================================
function closeDefinition(code = state.closeCode) {
  return state.closeCodes.find((item) => item.code === code)
    || state.closeCodes.find((item) => item.code === "106")
    || state.closeCodes[0];
}

function renderCreationCloseCodes() {
  const selectedBulk = elements.bulkCloseCode.value;
  const selectedManual = elements.manualCloseCode.value;
  const options = state.closeCodes.map((item) => new Option(
    `${item.code} - ${item.description}`,
    item.code,
  ));
  elements.bulkCloseCode.replaceChildren(
    new Option("Selecione o codigo", ""),
    ...options.map((option) => option.cloneNode(true)),
  );
  elements.manualCloseCode.replaceChildren(
    new Option("Selecione o codigo", ""),
    ...options,
  );
  elements.bulkCloseCode.value = state.closeCodes.some(
    (item) => item.code === selectedBulk,
  ) ? selectedBulk : "";
  elements.manualCloseCode.value = state.closeCodes.some(
    (item) => item.code === selectedManual,
  ) ? selectedManual : "";
}

function findCloseDefinition(code) {
  const codeStr = String(code || "").trim();
  if (!codeStr) return null;
  return state.closeCodes.find((item) => String(item.code) === codeStr) || null;
}

function productiveClose(code = state.closeCode) {
  const def = findCloseDefinition(code) || closeDefinition(code);
  return Boolean(def?.productive);
}

function closeCodeAllowsMaterials(code) {
  const codeStr = String(code || "").trim();
  if (!codeStr) return false;
  if (codeStr === "430" || codeStr === "706") return false;
  if (codeStr === "409") return true;
  const def = findCloseDefinition(codeStr);
  return Boolean(def?.productive);
}

// =============================================================================
// DOMINIUM COMPARTILHADO | IDENTIDADE DO OPERADOR E SESSAO
// =============================================================================
const AUTH_ROLE_LABELS = {
  admin: "Administrador",
  controller: "Controlador",
  viewer: "Somente visualizacao",
};
const AUTH_STATUS_LABELS = {
  pending: "Pendente",
  active: "Ativo",
  disabled: "Desativado",
};

function authInitials(name) {
  return String(name || "OP").trim().split(/\s+/).slice(0, 2)
    .map((part) => part[0] || "").join("").toUpperCase() || "OP";
}

function setAuthMessage(message = "", kind = "") {
  elements.authMessage.textContent = message;
  elements.authMessage.classList.toggle("hidden", !message);
  elements.authMessage.classList.toggle("success", kind === "success");
}

function switchAuthMode(mode) {
  const register = mode === "register";
  elements.authLoginTab.classList.toggle("active", !register);
  elements.authRegisterTab.classList.toggle("active", register);
  elements.authLoginTab.setAttribute("aria-selected", String(!register));
  elements.authRegisterTab.setAttribute("aria-selected", String(register));
  elements.authLoginForm.classList.toggle("hidden", register);
  elements.authRegisterForm.classList.toggle("hidden", !register);
  elements.authTitle.textContent = register ? "Criar acesso ao DOMINIUM" : "Entre no DOMINIUM";
  elements.authSubtitle.textContent = register
    ? "Novos controladores aguardam aprovacao de um administrador."
    : "Cada operacao fica vinculada ao controlador que a executou.";
  setAuthMessage();
  window.setTimeout(() => (
    register ? elements.authRegisterFirstName : elements.authLoginUsername
  ).focus(), 30);
}

function refreshAuthFormState() {
  const loginPasswordLength = elements.authLoginPassword.value.length;
  const loginReady = elements.authLoginUsername.value.trim().length >= 3
    && loginPasswordLength >= 4 && loginPasswordLength <= 128;
  elements.authLoginSubmit.disabled = !loginReady;
  elements.authLoginSubmit.closest(".auth-submit-track")?.classList.toggle("ready", loginReady);
  const registerPasswordLength = elements.authRegisterPassword.value.length;
  const registerReady = elements.authRegisterFirstName.value.trim().length >= 2
    && elements.authRegisterLastName.value.trim().length >= 2
    && elements.authRegisterUsername.value.trim().length >= 3
    && registerPasswordLength >= 12 && registerPasswordLength <= 128;
  elements.authRegisterSubmit.disabled = !registerReady;
}

async function authApi(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`Resposta invalida da autenticacao (${response.status})`);
  }
  if (!response.ok || payload.ok === false) throw new Error(payload.error || "Acesso negado");
  return payload;
}

function formatOperatorHeaderName(fullName) {
  const parts = String(fullName || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "Operador";
  if (parts.length <= 2) return fullName;
  return `${parts[0]} ${parts[parts.length - 1]}`;
}

function applyAuthUser(user, csrfToken = "") {
  state.authUser = user;
  state.authCsrfToken = csrfToken || state.authCsrfToken;
  const displayName = user?.display_name || user?.username || "Operador";
  const initials = authInitials(displayName);
  const headerName = formatOperatorHeaderName(displayName);
  elements.operatorName.textContent = headerName;
  const roleLabel = AUTH_ROLE_LABELS[user?.role] || "Operador";
  elements.operatorButton?.setAttribute("title", `${displayName} (${roleLabel})`);
  elements.operatorAvatar?.setAttribute("title", `${displayName} (${roleLabel})`);
  elements.operatorRole.textContent = roleLabel;
  elements.operatorAvatar.textContent = initials;
  elements.accountName.textContent = displayName;
  elements.accountMeta.textContent = `${user?.username || "-"} · ${roleLabel}`;
  elements.accountAvatar.textContent = initials;
  elements.accountAuditActor.textContent = displayName;
  elements.accountAdminSection.classList.toggle("hidden", user?.role !== "admin");
  // Bell notification: visible only to admins, with polling
  const isAdmin = user?.role === "admin";
  showAdminBell(isAdmin);
  if (isAdmin) {
    startPendingBadgePoll();
  } else {
    stopPendingBadgePoll();
  }
}

function updateAccountAttribution() {
  const identity = state.authUser?.imperium_identities?.[state.profile];
  elements.accountDatasnapActor.textContent = identity
    ? `${identity.username} · ID ${identity.controller_id}`
    : `Nao vinculado em ${state.profile.toUpperCase()}`;
}

function hideAuthGate() {
  elements.authGate.classList.add("hidden");
  document.documentElement.classList.remove("auth-pending");
}

function showAuthGate(message = "") {
  elements.authGate.classList.remove("hidden");
  document.documentElement.classList.add("auth-pending");
  if (message) setAuthMessage(message);
}

// ── Notificações de cadastros pendentes (admin only) ─────────────────────────

let _pendingPollTimer = null;

async function refreshPendingBadge() {
  if (state.authUser?.role !== "admin") return;
  try {
    const payload = await request("/api/auth/pending-count", { timeoutMs: 10000 });
    const count = Number(payload.pending_count || 0);
    if (elements.notificationBadge) {
      elements.notificationBadge.textContent = count;
      elements.notificationBadge.classList.toggle("hidden", count === 0);
    }
  } catch {
    // Silently ignored — badge just won't update
  }
}

function startPendingBadgePoll() {
  stopPendingBadgePoll();
  void refreshPendingBadge();
  _pendingPollTimer = window.setInterval(refreshPendingBadge, 30_000);
  window.addEventListener("focus", refreshPendingBadge, { passive: true });
}

function stopPendingBadgePoll() {
  if (_pendingPollTimer !== null) {
    window.clearInterval(_pendingPollTimer);
    _pendingPollTimer = null;
  }
  window.removeEventListener("focus", refreshPendingBadge);
}

function showAdminBell(visible) {
  if (!elements.notificationBell) return;
  elements.notificationBell.classList.toggle("hidden", !visible);
  elements.notificationBell.setAttribute("aria-hidden", String(!visible));
  elements.notificationBell.tabIndex = visible ? 0 : -1;
}

// ── Modais de aprovação e rejeição ──────────────────────────────────────────

function openApproveModal(user, onDone) {
  if (!elements.approveUserDialog) return;
  elements.approveUserDialogDesc.textContent =
    `Aprovando: ${user.display_name} (${user.username})`;
  elements.approveRoleSelect.value = "viewer";
  elements.approveUserDialog.returnValue = "";
  elements.approveUserDialog.showModal();
  elements.approveUserDialog._onDone = onDone;
  elements.approveUserDialog._targetUser = user;
}

function openRejectModal(user, onDone) {
  if (!elements.rejectUserDialog) return;
  elements.rejectUserDialogDesc.textContent =
    `Recusando: ${user.display_name} (${user.username})`;
  elements.rejectReasonInput.value = "";
  elements.rejectUserDialog.returnValue = "";
  elements.rejectUserDialog.showModal();
  elements.rejectUserDialog._onDone = onDone;
  elements.rejectUserDialog._targetUser = user;
}

if (elements.approveUserCancel) {
  elements.approveUserCancel.addEventListener("click", () =>
    elements.approveUserDialog.close("cancel")
  );
}
if (elements.rejectUserCancel) {
  elements.rejectUserCancel.addEventListener("click", () =>
    elements.rejectUserDialog.close("cancel")
  );
}

if (elements.approveUserForm) {
  elements.approveUserForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const user = elements.approveUserDialog._targetUser;
    const onDone = elements.approveUserDialog._onDone;
    if (!user) { elements.approveUserDialog.close(); return; }
    elements.approveUserConfirm.disabled = true;
    try {
      await request(`/api/auth/users/${user.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ role: elements.approveRoleSelect.value }),
      });
      elements.approveUserDialog.close("confirm");
      showToast(`${user.display_name} aprovado com sucesso.`, "success");
      await refreshPendingBadge();
      if (typeof onDone === "function") await onDone();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      elements.approveUserConfirm.disabled = false;
    }
  });
}

if (elements.rejectUserForm) {
  elements.rejectUserForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const user = elements.rejectUserDialog._targetUser;
    const onDone = elements.rejectUserDialog._onDone;
    if (!user) { elements.rejectUserDialog.close(); return; }
    elements.rejectUserConfirm.disabled = true;
    try {
      await request(`/api/auth/users/${user.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: elements.rejectReasonInput.value.trim() }),
      });
      elements.rejectUserDialog.close("confirm");
      showToast(`Cadastro de ${user.display_name} recusado.`, "warning");
      await refreshPendingBadge();
      if (typeof onDone === "function") await onDone();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      elements.rejectUserConfirm.disabled = false;
    }
  });
}

if (elements.notificationBell) {
  elements.notificationBell.addEventListener("click", () => {
    // operatorButton ja abre o painel e carrega os cadastros para admins.
    elements.operatorButton.click();
  });
}

let _accountUsersLoadSeq = 0;

async function loadAccountUsers() {
  const loadSeq = ++_accountUsersLoadSeq;
  if (state.authUser?.role !== "admin") return;
  elements.accountUsersList.replaceChildren();
  try {
    const payload = await request("/api/auth/users", { timeoutMs: 15000 });
    if (loadSeq !== _accountUsersLoadSeq) return;
    payload.users.forEach((user) => {
      const row = document.createElement("article");
      row.className = "account-user";
      const copy = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = user.display_name;
      const meta = document.createElement("small");
      meta.textContent = `${user.username} · ${user.status} · ${AUTH_ROLE_LABELS[user.role] || user.role}`;
      copy.append(name, meta);
      const actions = document.createElement("div");
      actions.className = "account-user-actions";
      if (user.status === "pending") {
        const approve = document.createElement("button");
        approve.type = "button";
        approve.className = "button primary";
        approve.textContent = "Aprovar";
        approve.addEventListener("click", () => openApproveModal(user, loadAccountUsers));

        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "button danger";
        reject.textContent = "Recusar";
        reject.addEventListener("click", () => openRejectModal(user, loadAccountUsers));

        actions.append(approve, reject);
      }
      if (user.status === "active") {
        const currentIdentity = user.imperium_identities?.[state.profile];
        const link = document.createElement("button");
        link.type = "button";
        link.className = "button secondary";
        link.textContent = currentIdentity ? "Alterar vinculo" : "Vincular Imperium";
        link.title = currentIdentity
          ? `${currentIdentity.username} · ID ${currentIdentity.controller_id}`
          : `Vincular identidade Imperium em ${state.profile.toUpperCase()}`;
        link.addEventListener("click", async () => {
          const supplied = window.prompt(
            `Usuario do Imperium para ${state.profile.toUpperCase()}:`,
            currentIdentity?.username || user.username.toUpperCase(),
          );
          if (supplied === null) return;
          const imperiumUsername = supplied.trim().toUpperCase();
          if (imperiumUsername.length < 2) {
            showToast("Informe um usuario Imperium valido.", "error");
            return;
          }
          link.disabled = true;
          try {
            const payload = await request(`/api/auth/users/${user.id}/imperium-identity`, {
              method: "POST",
              body: JSON.stringify({
                profile: state.profile,
                imperium_username: imperiumUsername,
              }),
            });
            if (user.id === state.authUser?.id) applyAuthUser(payload.user);
            updateAccountAttribution();
            await loadAccountUsers();
            showToast(`Identidade ${imperiumUsername} vinculada em ${state.profile.toUpperCase()}.`, "success");
          } catch (error) {
            showToast(error.message, "error");
            link.disabled = false;
          }
        });
        actions.append(link);
      }
      row.append(copy, actions);
      elements.accountUsersList.append(row);
    });
  } catch (error) {
    if (loadSeq !== _accountUsersLoadSeq) return;
    const message = document.createElement("p");
    message.className = "auth-message";
    message.textContent = error.message;
    elements.accountUsersList.append(message);
  }
}

async function bootstrapAuthentication() {
  try {
    const payload = await authApi("/api/auth/session");
    const registrationAvailable = payload.registration_enabled !== false
      && (!payload.bootstrap_required || payload.bootstrap_allowed);
    elements.authRegisterTab.classList.toggle("hidden", !registrationAvailable);
    if (!registrationAvailable) switchAuthMode("login");
    if (!payload.authenticated) {
      showAuthGate();
      if (payload.bootstrap_required && payload.bootstrap_allowed) {
        switchAuthMode("register");
        elements.authTitle.textContent = "Criar administrador inicial";
        elements.authSubtitle.textContent = "Primeiro acesso local: esta conta administrara os proximos cadastros.";
      } else if (payload.bootstrap_required) {
        elements.authTitle.textContent = "Configuracao inicial pendente";
        elements.authSubtitle.textContent = "O administrador inicial deve ser criado diretamente no servidor.";
      }
      return;
    }
    applyAuthUser(payload.user, payload.csrf_token);
    hideAuthGate();
    state.authReady = true;
    await initialize();
  } catch (error) {
    showAuthGate(error.message);
  }
}

elements.authLoginTab.addEventListener("click", () => switchAuthMode("login"));
elements.authRegisterTab.addEventListener("click", () => switchAuthMode("register"));
[elements.authLoginUsername, elements.authLoginPassword,
  elements.authRegisterFirstName, elements.authRegisterLastName,
  elements.authRegisterUsername, elements.authRegisterPassword]
  .forEach((input) => input.addEventListener("input", refreshAuthFormState));
[elements.authLoginPassword, elements.authRegisterPassword].forEach((input) => {
  input.addEventListener("focus", () => elements.authMascots.classList.add("password-active"));
  input.addEventListener("blur", () => elements.authMascots.classList.remove("password-active"));
});
document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-password-toggle]");
  if (!toggle) return;
  const selector = toggle.getAttribute("data-password-toggle");
  const input = selector ? document.querySelector(selector) : null;
  if (!input) return;
  const reveal = input.type === "password";
  input.type = reveal ? "text" : "password";
  toggle.textContent = reveal ? "Ocultar" : "Mostrar";
  toggle.setAttribute("aria-pressed", String(reveal));
  input.focus({ preventScroll: true });
});
elements.authLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (elements.authLoginSubmit.disabled) return;
  elements.authLoginSubmit.disabled = true;
  setAuthMessage();
  try {
    const payload = await authApi("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: elements.authLoginUsername.value.trim(),
        password: elements.authLoginPassword.value,
      }),
    });
    elements.authLoginPassword.value = "";
    applyAuthUser(payload.user, payload.csrf_token);
    hideAuthGate();
    if (!state.authReady) {
      state.authReady = true;
      await initialize();
    }
  } catch (error) {
    setAuthMessage(error.message);
  } finally {
    refreshAuthFormState();
  }
});
elements.authRegisterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (elements.authRegisterSubmit.disabled) return;
  elements.authRegisterSubmit.disabled = true;
  setAuthMessage();
  try {
    const payload = await authApi("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        first_name: elements.authRegisterFirstName.value.trim(),
        last_name: elements.authRegisterLastName.value.trim(),
        username: elements.authRegisterUsername.value.trim(),
        password: elements.authRegisterPassword.value,
        contact_email: elements.authRegisterEmail.value.trim() || undefined,
      }),
    });
    elements.authRegisterPassword.value = "";
    if (payload.authenticated) {
      applyAuthUser(payload.user, payload.csrf_token);
      hideAuthGate();
      if (!state.authReady) {
        state.authReady = true;
        await initialize();
      }
    } else {
      setAuthMessage("Solicitacao de cadastro enviada. Aguarde a aprovacao de um administrador.", "success");
      elements.authRegisterForm.reset();
    }
  } catch (error) {
    setAuthMessage(error.message);
  } finally {
    refreshAuthFormState();
  }
});
elements.operatorButton.addEventListener("click", () => {
  updateAccountAttribution();
  elements.accountDialog.showModal();
  if (state.authUser?.role === "admin") loadAccountUsers();
});
elements.operatorAvatar?.addEventListener("click", () => elements.operatorButton?.click());
elements.accountClose.addEventListener("click", () => elements.accountDialog.close());
elements.accountUsersRefresh.addEventListener("click", loadAccountUsers);

function clearSensitiveBrowserState() {
  state.authCsrfToken = "";
  const sensitivePrefixes = ["imperium-toa-misc-", "dominium-tec1-voice-alerts-"];
  for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = sessionStorage.key(index) || "";
    if (sensitivePrefixes.some((prefix) => key.startsWith(prefix))) {
      sessionStorage.removeItem(key);
    }
  }
  sensitivePrefixes.forEach((prefix) => {
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index) || "";
      if (key.startsWith(prefix)) localStorage.removeItem(key);
    }
  });
}

elements.accountLogout.addEventListener("click", async () => {
  try {
    await request("/api/auth/logout", { method: "POST", body: "{}", timeoutMs: 15000 });
  } finally {
    clearSensitiveBrowserState();
    window.location.reload();
  }
});

function secureRequestOptions(options = {}) {
  const normalized = { ...options };
  if (String(normalized.method || "GET").toUpperCase() === "POST") {
    const headers = new Headers(normalized.headers || {});
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (state.authCsrfToken && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", state.authCsrfToken);
    }
    normalized.headers = headers;
    if (normalized.body === undefined) normalized.body = "{}";
  }
  normalized.credentials = "same-origin";
  return normalized;
}

async function request(url, options = {}) {
  const controller = new AbortController();
  const { timeoutMs = 120000, ...fetchOptions } = options;
  const securedOptions = secureRequestOptions(fetchOptions);
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...securedOptions, signal: controller.signal });
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`Resposta inválida do painel (${response.status})`);
    }
    if (!response.ok || payload.ok === false) {
      if (response.status === 401 && payload.authentication_required) {
        state.authUser = null;
        state.authCsrfToken = "";
        showAuthGate("Sua sessao terminou. Entre novamente para continuar.");
      }
      const error = new Error(payload.error || `Falha HTTP ${response.status}`);
      error.status = response.status;
      error.category = payload.category || "API";
      error.categoryLabel = payload.category_label || "API Imperium";
      error.detail = payload.detail || error.message;
      error.uncertain = Boolean(payload.uncertain);
      error.stage = payload.stage || "";
      error.safeToRetry = payload.safe_to_retry !== false;
      error.payload = payload;
      throw error;
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      const timeoutSeconds = Math.ceil(timeoutMs / 1000);
      throw new Error(`O painel excedeu ${timeoutSeconds} segundos; consulte o terminal`);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function requestBlob(url, options = {}) {
  const controller = new AbortController();
  const { timeoutMs = 1800000, ...fetchOptions } = options;
  const securedOptions = secureRequestOptions(fetchOptions);
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...securedOptions, signal: controller.signal });
    if (!response.ok) {
      let message = `Falha HTTP ${response.status}`;
      try {
        const payload = await response.json();
        message = payload.error || message;
      } catch {
        // Binary endpoints can return a non-JSON error on an unexpected failure.
      }
      throw new Error(message);
    }
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(response.headers.get("Content-Disposition")),
    };
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("A consulta em massa excedeu o tempo limite; consulte o terminal");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function operationalStatusLabel(value) {
  const normalized = String(value || "").toLowerCase();
  return ({
    confirmed: "Confirmada",
    uncertain: "Incerta",
    failed: "Falhou",
    pending: "Processando",
    sending: "Enviando",
  })[normalized] || value || "Sem tentativa";
}

// =============================================================================
// DOMINIUM COMPARTILHADO | HISTORICO E VISAO OPERACIONAL DO CONTRATO
// =============================================================================
function renderOperationalContract() {
  const contract = state.operationalContract;
  elements.databaseContractCount.textContent = state.operationalDatabase.total || 0;
  elements.databaseOsCount.textContent = contract?.summary?.os_count || 0;
  elements.databaseEquipmentCount.textContent = contract
    ? (contract.summary.installed_count || 0) + (contract.summary.removed_count || 0)
    : 0;
  elements.databaseMaterialCount.textContent = contract?.summary?.material_count || 0;
  if (!contract) {
    elements.databaseDetail.innerHTML = '<div class="database-empty">Selecione um contrato para ver a ficha completa.</div>';
    return;
  }
  const inventorySection = (title, items, icon) => `
    <section class="database-detail-section">
      <header><h3><i data-lucide="${icon}" aria-hidden="true"></i>${escapeHtml(title)}</h3><span>${items.length}</span></header>
      <div class="database-chip-list">${items.length ? items.map((item) => `
        <div class="database-inventory-chip">
          <strong>${escapeHtml(item.serial || item.code || item.description || "Item")}</strong>
          <span>${escapeHtml(item.description || item.code || "Sem descricao")}</span>
          <small>${escapeHtml(item.quantity || "")} ${escapeHtml(item.unit || "")}</small>
        </div>`).join("") : '<span class="database-muted">Nenhum registro.</span>'}
      </div>
    </section>`;
  const attempts = contract.close_attempts || [];
  elements.databaseDetail.innerHTML = `
    <header class="database-contract-head">
      <div><span>CONTRATO</span><h2>${escapeHtml(contract.contract)}</h2><p>${escapeHtml(contract.customer_name || "Cliente nao informado")}</p></div>
      <span class="database-contract-status">${escapeHtml(contract.status || "Sem status")}</span>
    </header>
    <div class="database-facts">
      <div><span>Data agendada</span><strong>${escapeHtml(contract.scheduled_date || "-")}</strong></div>
      <div><span>Janela</span><strong>${escapeHtml(contract.service_window || "-")}</strong></div>
      <div><span>Tecnico</span><strong>${escapeHtml(contract.technician_name || "-")}</strong><small>${escapeHtml(contract.technician_login || "")}</small></div>
      <div><span>Local</span><strong>${escapeHtml([contract.city, contract.district].filter(Boolean).join(" / ") || "-")}</strong></div>
      <div class="database-observation"><span>Observacao do tecnico</span><strong>${escapeHtml(contract.observation || "Sem observacao registrada")}</strong></div>
    </div>
    <section class="database-detail-section">
      <header><h3><i data-lucide="list-checks" aria-hidden="true"></i>Ordens e tarefas</h3><span>${contract.orders.length}</span></header>
      <div class="database-order-list">${contract.orders.map((order) => `
        <div><strong>OS ${escapeHtml(order.os_number)}</strong><span>${escapeHtml(order.service || "Servico nao informado")}</span><small>TOA: ${escapeHtml(order.toa_status || "-")} · IMPERIUM: ${escapeHtml(order.imperium_status || "-")} · Codigo: ${escapeHtml(order.close_code || "-")}</small></div>
      `).join("")}</div>
    </section>
    ${inventorySection("Equipamentos instalados", contract.inventory.installed || [], "package-plus")}
    ${inventorySection("Equipamentos retirados", contract.inventory.removed || [], "package-minus")}
    ${inventorySection("Miscelaneas e materiais", contract.inventory.material || [], "cable")}
    <section class="database-detail-section">
      <header><h3><i data-lucide="send" aria-hidden="true"></i>Tentativas de baixa</h3><span>${attempts.length}</span></header>
      <div class="database-attempt-list">${attempts.length ? attempts.map((attempt) => `
        <div class="database-attempt ${escapeHtml(attempt.state)}">
          <strong>OS ${escapeHtml(attempt.os_number)} · ${escapeHtml(attempt.close_code)}</strong>
          <span>${escapeHtml(operationalStatusLabel(attempt.state))} — ${escapeHtml(attempt.message || attempt.category_label)}</span>
          <small>${escapeHtml(formatDateTime(attempt.updated_at))} · ${escapeHtml(attempt.transport || "-")}</small>
        </div>`).join("") : '<span class="database-muted">Nenhuma tentativa registrada.</span>'}</div>
    </section>`;
  window.lucide?.createIcons();
}

async function selectOperationalContract(contract) {
  try {
    const payload = await request(apiUrl(`/api/operational/contracts/${encodeURIComponent(contract)}`));
    state.operationalContract = payload.contract;
    renderOperationalDatabase();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderOperationalDatabase() {
  const selected = state.operationalContract?.contract;
  const rows = state.operationalDatabase.contracts || [];
  elements.databaseList.innerHTML = rows.length ? rows.map((contract) => `
    <button class="database-contract-row ${selected === contract.contract ? "active" : ""}" type="button" data-contract="${escapeHtml(contract.contract)}">
      <span><strong>${escapeHtml(contract.contract)}</strong><small>${escapeHtml(contract.customer_name || contract.city || "Sem identificacao")}</small></span>
      <span><b>${escapeHtml(contract.os_count)} OS</b><small>${escapeHtml(contract.technician_name || "Tecnico nao informado")}</small></span>
      <i>${escapeHtml(operationalStatusLabel(contract.last_attempt_state))}</i>
    </button>`).join("") : '<div class="database-empty">Nenhum contrato encontrado.</div>';
  elements.databaseList.querySelectorAll("[data-contract]").forEach((button) => {
    button.addEventListener("click", () => selectOperationalContract(button.dataset.contract));
  });
  renderOperationalContract();
}

async function loadOperationalDatabase({ quiet = false } = {}) {
  if (state.operationalDatabaseLoading) return;
  state.operationalDatabaseLoading = true;
  if (!quiet) elements.databaseList.innerHTML = '<div class="database-empty">Carregando base operacional...</div>';
  try {
    const url = new URL("/api/operational/contracts", window.location.origin);
    url.searchParams.set("profile", state.profile);
    if (elements.databaseSearch.value.trim()) url.searchParams.set("q", elements.databaseSearch.value.trim());
    if (elements.databaseDate.value) url.searchParams.set("date", elements.databaseDate.value);
    url.searchParams.set("limit", "300");
    state.operationalDatabase = await request(`${url.pathname}${url.search}`);
    const stillVisible = state.operationalDatabase.contracts.some(
      (item) => item.contract === state.operationalContract?.contract,
    );
    if (!stillVisible) state.operationalContract = null;
    renderOperationalDatabase();
  } catch (error) {
    elements.databaseList.innerHTML = `<div class="database-empty">${escapeHtml(error.message)}</div>`;
  } finally {
    state.operationalDatabaseLoading = false;
  }
}

function filenameFromDisposition(value) {
  const match = /filename="?([^";]+)"?/i.exec(value || "");
  return match?.[1] || "estoque-tecnicos.pdf";
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function setDownloadMotion(button, phase = "idle") {
  if (!button) return;
  button.classList.toggle("download-running", phase === "running");
  button.classList.toggle("download-complete", phase === "complete");
  if (phase === "complete") {
    window.setTimeout(() => button.classList.remove("download-complete"), 900);
  }
}

function escapeHtml(value) {
  return String(value ?? "-")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setConnection(label, kind = "") {
  if (!elements.connection) return;
  elements.connection.className = `connection ${kind}`.trim();
  elements.connection.querySelector("span:last-child").textContent = label;
}

let toastTimer;
function showToast(message, kind = "") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast ${kind}`.trim();
  toastTimer = setTimeout(() => elements.toast.classList.add("hidden"), 4500);
}

function visibleOrders() {
  const term = normalize(elements.search.value.trim());
  return state.orders.filter((order) => {
    if (!term) return true;
    return normalize(`${order.num_os} ${order.contract} ${order.service}`).includes(term);
  });
}

function updateServiceOptions() {
  const current = elements.service.value;
  const options = [
    ["Todos", "all"],
    ["Instalação / alteração", "installation"],
    ["Visita técnica / manutenção", "technical"],
    ["Desconexão / retirada", "disconnection"],
    ["Correção de estoque", "stock"],
  ];
  elements.service.replaceChildren(
    ...options.map(([label, value]) => new Option(label, value)),
  );
  elements.service.value = options.some(([, value]) => value === current)
    ? current
    : "all";
}

function rowFor(order) {
  const row = document.createElement("tr");
  const pendingReport = activeCloseReportRecord(order.id_os);
  const retryReport = retryableCloseReportRecord(order.id_os);
  row.dataset.id = order.id_os;
  if (state.selected.has(order.id_os)) row.classList.add("selected");
  if (pendingReport) row.classList.add("pending-close-row");

  const checkCell = document.createElement("td");
  checkCell.className = "check-cell";
  const check = document.createElement("input");
  check.type = "checkbox";
  check.checked = state.selected.has(order.id_os);
  const readOnly = Boolean(order.read_only)
    || normalize(order.status) !== "EM CAMPO";
  check.disabled = readOnly || state.running || state.loading || !state.closeEnabled
    || productiveClose() || Boolean(pendingReport);
  check.setAttribute("aria-label", `Selecionar OS ${order.num_os}`);
  check.addEventListener("change", () => {
    if (check.checked) state.selected.add(order.id_os);
    else state.selected.delete(order.id_os);
    render();
  });
  checkCell.append(check);

  const osCell = document.createElement("td");
  osCell.className = "os-number";
  osCell.textContent = order.num_os;
  const contractCell = document.createElement("td");
  contractCell.textContent = order.contract;
  const serviceCell = document.createElement("td");
  serviceCell.className = "service-name";
  serviceCell.textContent = order.service;
  serviceCell.title = order.service;
  const cityCell = document.createElement("td");
  cityCell.textContent = order.city || "-";
  const technicianCell = document.createElement("td");
  technicianCell.className = "technician-name";
  technicianCell.textContent = order.technician || "-";
  const statusCell = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = "status-badge";
  badge.textContent = order.status;
  statusCell.append(badge);
  const actionCell = document.createElement("td");
  actionCell.className = "action-cell";
  const action = document.createElement("button");
  action.className = "button secondary row-action";
  action.type = "button";
  action.textContent = retryReport
    ? "Revisar nova tentativa"
    : pendingReport
      ? reportState(pendingReport) === "uncertain" ? "Nao confirmada" : "Processando"
      : state.closeEnabled && !readOnly ? "Baixar" : "Consulta";
  action.disabled = readOnly || state.running || state.loading || !state.closeEnabled
    || Boolean(pendingReport && !retryReport);
  if (retryReport) {
    action.title = "A OS continua aberta; revise os dados antes da repeticao controlada";
  } else if (pendingReport) {
    action.title = pendingReport.message || "Aguardando confirmacao";
  }
  action.addEventListener("click", () => {
    if (retryReport) {
      openConfirmation(
        [order],
        retryReport.close_code || state.closeCode,
        closeRetryExtra(retryReport),
      );
      return;
    }
    openClosePicker(order);
  });
  actionCell.append(action);

  row.append(
    checkCell,
    osCell,
    contractCell,
    serviceCell,
    cityCell,
    technicianCell,
    statusCell,
    actionCell,
  );
  return row;
}

function formatDateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

function formatAutomationTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function failureRowFor(failure) {
  const row = document.createElement("tr");
  const osCell = document.createElement("td");
  osCell.className = "os-number";
  osCell.textContent = failure.num_os;

  const serviceCell = document.createElement("td");
  serviceCell.className = "service-name";
  serviceCell.textContent = failure.service;
  serviceCell.title = failure.service;

  const codeCell = document.createElement("td");
  codeCell.className = "attempts-cell";
  codeCell.textContent = failure.close_code || "106";

  const categoryCell = document.createElement("td");
  const category = document.createElement("span");
  category.className = `failure-badge category-${String(failure.category).toLowerCase()}`;
  category.textContent = failure.category_label;
  categoryCell.append(category);

  const attemptsCell = document.createElement("td");
  attemptsCell.className = "attempts-cell";
  attemptsCell.textContent = failure.attempts;

  const timeCell = document.createElement("td");
  timeCell.textContent = formatDateTime(failure.last_at);

  const errorCell = document.createElement("td");
  errorCell.className = "failure-message";
  errorCell.textContent = failure.error;
  errorCell.title = failure.detail || failure.error;

  const actionCell = document.createElement("td");
  actionCell.className = "action-cell";
  const action = document.createElement("button");
  action.className = "button secondary row-action";
  action.type = "button";
  action.textContent = "Tentar novamente";
  action.disabled = state.running || state.loading || !state.closeEnabled;
  action.addEventListener("click", () => {
    openConfirmation([failure], failure.close_code || "106");
  });
  actionCell.append(action);

  row.append(
    osCell,
    serviceCell,
    codeCell,
    categoryCell,
    attemptsCell,
    timeCell,
    errorCell,
    actionCell,
  );
  return row;
}

function upsertFailure(order, error, closeCode) {
  const previous = state.failures.find((failure) => failure.id_os === order.id_os);
  const now = new Date().toISOString();
  const failure = {
    ...order,
    close_code: closeCode,
    category: error.category || "API",
    category_label: error.categoryLabel || "API Imperium",
    error: error.message,
    detail: error.detail || error.message,
    attempts: (previous?.attempts || 0) + 1,
    first_at: previous?.first_at || now,
    last_at: now,
  };
  state.failures = [
    failure,
    ...state.failures.filter((item) => item.id_os !== order.id_os),
  ];
}

async function loadFailures(profileKey = state.profile) {
  try {
    const payload = await request(apiUrl("/api/failures"));
    if (profileKey !== state.profile) return;
    state.failures = payload.failures;
  } catch (error) {
    console.error("Falha ao carregar a lista de não baixadas", error);
  }
}

function reportState(record) {
  const value = String(record?.state || "");
  return value === "sending" ? "pending" : value;
}

function activeCloseReportRecord(idOs) {
  return (state.closeReport.records || []).find((record) => (
    Number(record.id_os) === Number(idOs)
    && ["sending", "pending", "uncertain"].includes(String(record.state))
  ));
}

function retryableCloseReportRecord(idOs) {
  const record = activeCloseReportRecord(idOs);
  if (
    reportState(record) !== "uncertain"
    || Number(record?.confirmation_checks || 0) < 7
  ) {
    return null;
  }
  return record;
}

function closeRetryExtra(record) {
  if (!record) return {};
  return {
    retry_of_request_id: String(record.request_id || ""),
  };
}

function filteredCloseReport() {
  const term = normalize(elements.reportSearch.value.trim());
  const selectedState = elements.reportState.value;
  return (state.closeReport.records || []).filter((record) => {
    const currentState = reportState(record);
    if (selectedState && currentState !== selectedState) return false;
    if (!term) return true;
    return normalize([
      record.num_os,
      record.contract,
      record.service,
      record.close_code,
      record.close_description,
      record.category_label,
      record.message,
      record.detail,
      record.transport,
    ].join(" ")).includes(term);
  });
}

function renderCloseReport() {
  const summary = state.closeReport.summary || {};
  elements.reportConfirmedCount.textContent = Number(summary.confirmed || 0);
  elements.reportPendingCount.textContent = Number(summary.pending || 0);
  elements.reportUncertainCount.textContent = Number(summary.uncertain || 0);
  elements.reportFailedCount.textContent = Number(summary.failed || 0);
  elements.reportRefresh.disabled = state.closeReportLoading;
  elements.reportLoading.classList.toggle("hidden", !state.closeReportLoading);
  const records = filteredCloseReport();
  elements.reportEmpty.classList.toggle(
    "hidden", state.closeReportLoading || records.length > 0,
  );
  elements.reportBody.innerHTML = records.map((record) => {
    const currentState = reportState(record);
    const resultLabel = currentState === "confirmed"
      ? "Confirmada"
      : currentState === "pending"
        ? "Processando"
        : currentState === "uncertain"
          ? "Incerta"
          : "Falha";
    const transport = "Integração IMPERIUM";
    const detail = record.message || record.detail || record.category_label || "-";
    return `<tr>
      <td class="os-number">${escapeHtml(record.num_os || "-")}</td>
      <td>${escapeHtml(record.contract || "-")}</td>
      <td class="service-name" title="${escapeHtml(record.service || "")}">${escapeHtml(record.service || "-")}</td>
      <td><strong>${escapeHtml(record.close_code || "-")}</strong><small>${escapeHtml(record.close_description || "")}</small></td>
      <td><span class="report-status report-status-${currentState}">${resultLabel}</span></td>
      <td class="report-detail" title="${escapeHtml(record.detail || detail)}"><strong>${escapeHtml(record.category_label || "-")}</strong><span>${escapeHtml(detail)}</span></td>
      <td>${escapeHtml(formatDateTime(record.confirmed_at || record.updated_at || record.created_at || "-"))}</td>
      <td>${escapeHtml(transport)}</td>
    </tr>`;
  }).join("");
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function loadCloseReport({ quiet = false } = {}) {
  if (state.closeReportLoading) return;
  const profileKey = state.profile;
  state.closeReportLoading = true;
  renderCloseReport();
  try {
    const date = elements.reportDate.value || localDate();
    const payload = await request(apiUrl(`/api/close-report?date=${encodeURIComponent(date)}`));
    if (profileKey !== state.profile) return;
    state.closeReport = {
      records: Array.isArray(payload.records) ? payload.records : [],
      summary: payload.summary || {},
    };
  } catch (error) {
    if (!quiet) showToast(error.message, "error");
    console.error("Falha ao carregar relatorio de baixas", error);
  } finally {
    if (profileKey !== state.profile) return;
    state.closeReportLoading = false;
    renderCloseReport();
    render();
  }
}

function exportCloseReportXlsx() {
  const date = elements.reportDate?.value || localDate();
  const url = apiUrl(`/api/close-report/export.xlsx?date=${encodeURIComponent(date)}`);
  window.location.href = url;
}

function renderProfileTabs() {
  const tabs = state.profiles.map((profile) => {
    const button = document.createElement("button");
    button.className = "profile-tab";
    button.type = "button";
    button.textContent = profile.label;
    button.title = profile.close_enabled
      ? profile.label
      : `${profile.label} - somente consulta`;
    button.classList.toggle("active", profile.key === state.profile);
    button.setAttribute("aria-pressed", String(profile.key === state.profile));
    button.disabled = state.running || state.loading || state.profileSwitching
      || state.bulkCreateLoading
      || state.stockBatchLoading || state.stockWriteoffLoading
      || disconnectIsRunning();
    button.addEventListener("click", () => switchProfile(profile.key));
    return button;
  });
  elements.profileTabs.replaceChildren(...tabs);
}

async function loadProfiles() {
  const payload = await request("/api/profiles");
  state.profiles = Array.isArray(payload.profiles) ? payload.profiles : [];
  if (!state.profiles.some((profile) => profile.key === state.profile)) {
    state.profile = payload.default || state.profiles[0]?.key || "natal";
  }
  const profile = state.profiles.find((item) => item.key === state.profile);
  state.closeEnabled = Boolean(profile?.close_enabled);
  state.materialWriteoffEnabled = Boolean(profile?.material_writeoff_enabled);
  state.nativeCreationEnabled = Boolean(profile?.native_creation_enabled);
  state.installerChangeEnabled = Boolean(profile?.installer_change_enabled);
  state.serializedTransferEnabled = Boolean(profile?.serialized_transfer_enabled);
  state.nativeCreationServices = Array.isArray(profile?.native_creation_services)
    ? profile.native_creation_services.map(String) : [];
  updateAddress();
  renderProfileTabs();
}

async function loadImportTargets() {
  const payload = await request("/api/import-targets");
  state.importTargets = Array.isArray(payload.targets) ? payload.targets : [];
  if (!state.importTargets.some((target) => target.key === state.importTarget)) {
    state.importTarget = state.importTargets[0]?.key || "rn";
  }
}

function automationRouteLabel(item) {
  const status = String(item?.status || "aguardando");
  if (status === "concluida") {
    const imported = Number(item.imported || 0);
    const notImported = Number(item.not_imported || 0);
    return `${imported} importadas${notImported ? `; ${notImported} nao importadas` : ""}`;
  }
  if (status === "vazia") return "Sem atividades no TOA";
  if (status === "erro") return item.error || "Tratativa humana necessaria";
  if (status === "executando") return "Exportando e importando";
  return "Aguardando proxima rodada";
}

function automationHistoryDetail(run) {
  if (run.error) return run.error;
  const routes = Array.isArray(run.routes) ? run.routes : [];
  const imported = routes.reduce((total, item) => total + Number(item.imported || 0), 0);
  const empty = routes.filter((item) => item.status === "vazia").length;
  const failed = routes.filter((item) => item.status === "erro").length;
  const pieces = [`${imported} OS importadas`];
  if (empty) pieces.push(`${empty} rotas sem atividades`);
  if (failed) pieces.push(`${failed} rotas com erro`);
  return pieces.join("; ");
}

// =============================================================================
// TOA | AUTOMACAO, SESSAO E DADOS COLETADOS
// =============================================================================
function renderToaAutomation() {
  const automation = state.toaAutomation;
  if (!automation) {
    elements.toaAutomationStatus.className = "toa-automation-state loading";
    elements.toaAutomationStatusText.textContent = "Carregando";
    elements.toaAutomationRun.disabled = true;
    return;
  }

  const configured = Boolean(automation.credentials_configured);
  const running = Boolean(automation.running);
  const lastRun = automation.last_run;
  const statusKind = !configured ? "error" : running ? "running" : lastRun?.ok === false ? "warning" : "online";
  const statusText = !configured
    ? "Credencial pendente"
    : running ? "Executando"
      : lastRun?.ok === false ? "Ultima rodada com falhas" : "Agendamento ativo";
  elements.toaAutomationStatus.className = `toa-automation-state ${statusKind}`;
  elements.toaAutomationStatusText.textContent = statusText;
  elements.toaAutomationSchedule.textContent = (automation.times || []).join(" / ") || "-";
  elements.toaAutomationNext.textContent = formatAutomationTime(automation.next_run);
  elements.toaAutomationCurrent.textContent = running
    ? automation.current_route || "Abrindo sessao TOA"
    : "Aguardando";
  elements.toaAutomationLast.textContent = lastRun
    ? `${formatAutomationTime(lastRun.completed_at)} - ${lastRun.ok ? "Concluida" : "Com falhas"}`
    : "Ainda nao executada";
  elements.toaAutomationRun.disabled = state.toaAutomationLoading || running || !configured;
  elements.toaAutomationRun.classList.toggle("loading", state.toaAutomationLoading || running);

  const lastRoutes = new Map(
    (lastRun?.routes || []).map((item) => [item.route, item]),
  );
  const routeRows = (automation.routes || []).map((route) => {
    const previous = lastRoutes.get(route.route);
    const isCurrent = running && automation.current_route === route.route;
    const item = isCurrent ? { ...route, status: "executando" } : { ...route, ...previous };
    const row = document.createElement("div");
    row.className = "toa-route-row";

    const identity = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = route.label;
    const code = document.createElement("small");
    code.textContent = route.route;
    identity.append(label, code);

    const status = document.createElement("span");
    status.className = `toa-route-status ${item.status || "aguardando"}`;
    status.textContent = item.status === "concluida" ? "Importada"
      : item.status === "vazia" ? "Sem atividades"
        : item.status === "erro" ? "Tratativa humana"
          : item.status === "executando" ? "Executando" : "Aguardando";

    const detail = document.createElement("p");
    detail.textContent = automationRouteLabel(item);
    detail.title = detail.textContent;
    row.append(identity, status, detail);
    return row;
  });
  elements.toaAutomationRoutes.replaceChildren(...routeRows);

  const historyRows = (automation.history || []).slice(0, 5).map((run) => {
    const row = document.createElement("div");
    row.className = "toa-history-row";
    const heading = document.createElement("div");
    const time = document.createElement("strong");
    time.textContent = formatAutomationTime(run.completed_at || run.started_at);
    const source = document.createElement("span");
    source.textContent = run.source === "agendada" ? "Agendada" : "Manual";
    source.className = `toa-history-result ${run.ok ? "success" : "error"}`;
    heading.append(time, source);
    const detail = document.createElement("p");
    detail.textContent = automationHistoryDetail(run);
    detail.title = detail.textContent;
    row.append(heading, detail);
    return row;
  });
  if (!historyRows.length) {
    const empty = document.createElement("p");
    empty.className = "toa-automation-empty";
    empty.textContent = "A primeira rodada esta programada para 09:00.";
    historyRows.push(empty);
  }
  elements.toaAutomationHistory.replaceChildren(...historyRows);
}

async function loadToaAutomation({ quiet = false } = {}) {
  try {
    state.toaAutomation = await request("/api/toa-automation", { timeoutMs: 15000 });
    renderToaAutomation();
  } catch (error) {
    if (!quiet) {
      showToast(error.message, "error");
      console.error("Falha ao consultar automacao TOA", error);
    }
  }
}

async function runToaAutomation() {
  if (state.toaAutomationLoading || state.toaAutomation?.running) return;
  state.toaAutomationLoading = true;
  renderToaAutomation();
  try {
    state.toaAutomation = await request("/api/toa-automation/run", {
      method: "POST",
      timeoutMs: 15000,
    });
    showToast("Importacao automatica iniciada. Acompanhe as rotas nesta tela.", "success");
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao iniciar automacao TOA", error);
  } finally {
    state.toaAutomationLoading = false;
    renderToaAutomation();
  }
}

function automationTestContracts() {
  const seen = new Set();
  return elements.automationTestContracts.value
    .split(/[\s,;]+/)
    .map((value) => value.trim())
    .filter((value) => value && !seen.has(value) && seen.add(value));
}

function automationDecisionLabel(decision) {
  return {
    candidate_after_validation: "Candidata apos validacao",
    no_inventory_movement: "Sem movimentacao de estoque",
    blocked_manual_review: "Bloqueada",
    manual_review: "Revisao manual",
  }[decision] || "Revisao manual";
}

function automationNode(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

function automationProviderLabel(provider) {
  return String(provider?.name || provider?.external_id || provider?.id || "Nao informado");
}

function automationInventoryLabel(item) {
  const identity = item.serial || item.material_code || item.code || "Sem identificador";
  const description = item.description || item.model || item.equipment_type || item.type || "";
  const quantity = item.quantity ?? 1;
  return `${identity}${description ? ` - ${description}` : ""} | qtd. ${quantity}`;
}

function automationListSection(title, items, formatter = (item) => String(item)) {
  const section = automationNode("section", "automation-detail-section");
  const heading = automationNode("header");
  heading.append(
    automationNode("h4", "", title),
    automationNode("span", "", String(items.length)),
  );
  const list = automationNode("div", "automation-detail-list");
  if (!items.length) {
    list.append(automationNode("p", "automation-detail-none", "Nenhum item"));
  } else {
    items.forEach((item) => list.append(automationNode("p", "", formatter(item))));
  }
  section.append(heading, list);
  return section;
}

function automationOrderCard(order) {
  const card = automationNode("article", "automation-result-card");
  const heading = automationNode("header", "automation-result-heading");
  const title = automationNode("div");
  title.append(
    automationNode("span", "", `CONTRATO ${order.contract}`),
    automationNode("h3", "", order.work_type || "Tipo nao informado"),
  );
  const status = automationNode(
    "strong", `automation-decision ${order.decision}`,
    automationDecisionLabel(order.decision),
  );
  const headingActions = automationNode("div", "automation-heading-actions");
  const toggle = automationNode("button", "icon-button automation-detail-toggle");
  toggle.type = "button";
  toggle.title = "Recolher detalhes";
  toggle.setAttribute("aria-label", "Recolher detalhes");
  toggle.setAttribute("aria-expanded", "true");
  const detailId = `automation-detail-${String(order.aid || order.contract).replace(/\W/g, "-")}`;
  toggle.setAttribute("aria-controls", detailId);
  const toggleIcon = automationNode("i");
  toggleIcon.dataset.lucide = "chevron-up";
  toggleIcon.setAttribute("aria-hidden", "true");
  toggle.append(toggleIcon);
  headingActions.append(status, toggle);
  heading.append(title, headingActions);

  const identity = automationNode("div", "automation-identity-grid");
  [
    ["AID", order.aid || "-"],
    ["Cidade", order.city || "Nao informada"],
    ["Status", order.activity_status || "Nao informado"],
    ["Classificacao", order.operational_classification || "Nao mapeada"],
  ].forEach(([label, value]) => {
    const item = automationNode("div");
    item.append(automationNode("span", "", label), automationNode("strong", "", value));
    identity.append(item);
  });

  const tasks = automationNode("section", "automation-detail-section automation-task-section");
  const taskHeading = automationNode("header");
  taskHeading.append(
    automationNode("h4", "", "Tarefas e codigos"),
    automationNode("span", "", String((order.tasks || []).length)),
  );
  const taskList = automationNode("div", "automation-task-list");
  if (!(order.tasks || []).length) {
    taskList.append(automationNode("p", "automation-detail-none", "Nenhuma tarefa"));
  } else {
    (order.tasks || []).forEach((task) => {
      const row = automationNode("div");
      row.append(
        automationNode("strong", "", `OS ${task.os_number || "-"}`),
        automationNode("span", "automation-task-contract", `Contrato ${order.contract || "-"}`),
        automationNode("span", "", `Indice ${task.index || "-"}`),
        automationNode("span", "", `Status ${task.status || "-"}`),
        automationNode("b", "", `Codigo ${task.close_code || "-"}`),
      );
      taskList.append(row);
    });
  }
  tasks.append(taskHeading, taskList);

  const inventory = automationNode("div", "automation-inventory-grid");
  inventory.append(
    automationListSection("Equipamentos instalados", order.installed_equipment || [], automationInventoryLabel),
    automationListSection("Equipamentos retirados", order.removed_equipment || [], automationInventoryLabel),
    automationListSection("Pool customer", order.customer_equipment || [], automationInventoryLabel),
    automationListSection("Materiais e miscelaneas", order.materials || [], automationInventoryLabel),
  );

  const responsibility = automationNode("section", "automation-responsibility");
  responsibility.append(automationNode("h4", "", "Responsabilidades"));
  const responsibilityGrid = automationNode("div");
  const responsibilityValues = [
    ["Tecnico atribuido", automationProviderLabel(order.assigned_technician)],
    ["Provedor da rota", automationProviderLabel(order.route_provider)],
    ["Donos do inventario", (order.inventory_providers || []).map(automationProviderLabel).join(", ") || "Nao informado"],
    ["Remetentes dos formularios", (order.form_submitters || []).map(automationProviderLabel).join(", ") || "Nao informado"],
  ];
  responsibilityValues.forEach(([label, value]) => {
    const item = automationNode("div");
    item.append(automationNode("span", "", label), automationNode("strong", "", value));
    responsibilityGrid.append(item);
  });
  responsibility.append(responsibilityGrid);

  const diagnostics = automationNode("div", "automation-diagnostics");
  [
    ["Campos ausentes / erros", order.validation_errors || [], "error"],
    ["Alertas", order.validation_warnings || [], "warning"],
    ["Motivos da decisao", order.decision_reasons || [], "reason"],
  ].forEach(([label, values, kind]) => {
    const block = automationNode("section", kind);
    block.append(automationNode("h4", "", label));
    block.append(automationNode("p", "", values.length ? values.join(" | ") : "Nenhum"));
    diagnostics.append(block);
  });

  const footer = automationNode("footer");
  footer.append(
    automationNode("span", "", `Pools: ${(order.pools || []).join(", ") || "nenhum"}`),
    automationNode("strong", "", order.dry_run_only ? "DRY-RUN CONFIRMADO" : "DRY-RUN INVALIDO"),
  );
  const details = automationNode("div", "automation-card-details");
  details.id = detailId;
  details.append(identity, tasks, inventory, responsibility, diagnostics, footer);
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.title = expanded ? "Recolher detalhes" : "Expandir detalhes";
    toggle.setAttribute("aria-label", toggle.title);
    toggleIcon.dataset.lucide = expanded ? "chevron-up" : "chevron-down";
    if (globalThis.lucide) globalThis.lucide.createIcons();
    if (globalThis.DOMINIUM_MOTION?.toggleDetails) {
      globalThis.DOMINIUM_MOTION.toggleDetails(details, expanded);
    } else {
      details.hidden = !expanded;
    }
  });
  card.append(heading, details);
  return card;
}

function renderAutomationTest() {
  const contracts = automationTestContracts();
  elements.automationTestContractCount.textContent = `${contracts.length} contrato${contracts.length === 1 ? "" : "s"}`;
  const selectedKey = state.automationTestLotKey || state.automationTestLots[0]?.key || "";
  if (elements.automationTestLot.options.length !== state.automationTestLots.length
    || elements.automationTestLot.dataset.version !== state.automationTestLots.map((lot) => lot.key).join("|")) {
    elements.automationTestLot.replaceChildren(
      ...state.automationTestLots.map((lot) => new Option(
        `${lot.name} - ${lot.aid_count} AIDs`, lot.key,
      )),
    );
    elements.automationTestLot.dataset.version = state.automationTestLots.map((lot) => lot.key).join("|");
  }
  elements.automationTestLot.value = selectedKey;
  elements.automationTestLot.disabled = state.automationTestLoading || !state.automationTestLots.length;
  elements.automationTestContracts.disabled = state.automationTestLoading;
  elements.automationTestAnalyze.disabled = state.automationTestLoading
    || !selectedKey || !contracts.length;
  elements.automationTestAnalyze.classList.toggle("loading", state.automationTestLoading);
  elements.automationTestMessage.textContent = state.automationTestMessage;

  const counts = state.automationTestRegistry?.counts_by_slot || {};
  elements.automationSlot0900.textContent = String(counts["09:00"] || 0);
  elements.automationSlot1400.textContent = String(counts["14:00"] || 0);
  elements.automationSlot1720.textContent = String(counts["17:20"] || 0);
  elements.automationWindowButtons.forEach((button) => {
    button.disabled = state.automationTestLoading || !Number(counts[button.dataset.automationSlot] || 0);
  });

  const selectedLot = state.automationTestLots.find((lot) => lot.key === selectedKey);
  elements.automationTestLotMeta.textContent = selectedLot
    ? `${selectedLot.aid_count} AIDs | TECHCAP ${selectedLot.version}`
    : "Nenhum lote TECHCAP disponivel";

  const results = state.automationTestResult?.results || [];
  const orders = results.flatMap((item) => item.found ? [item] : []);
  const summary = {};
  orders.forEach((order) => { summary[order.decision] = (summary[order.decision] || 0) + 1; });
  elements.automationTestSummary.replaceChildren(
    ...Object.entries(summary).map(([decision, count]) => automationNode(
      "span", `automation-decision ${decision}`, `${count} ${automationDecisionLabel(decision)}`,
    )),
  );
  const cards = results.map((item) => {
    if (item.found) return automationOrderCard(item);
    const missing = automationNode("article", "automation-result-card missing");
    const heading = automationNode("header", "automation-result-heading");
    const title = automationNode("div");
    title.append(
      automationNode("span", "", `CONTRATO ${item.contract}`),
      automationNode("h3", "", "Contrato nao encontrado no lote"),
    );
    heading.append(
      title,
      automationNode("strong", "automation-decision manual_review", "Revisao manual"),
    );
    missing.append(
      heading,
      automationNode("p", "automation-missing-reason", (item.decision_reasons || []).join(" | ")),
    );
    return missing;
  });
  elements.automationTestResults.replaceChildren(...cards);
  document.dispatchEvent(new CustomEvent("dominium:automation-results", {
    detail: { cards },
  }));
  elements.automationTestEmpty.classList.toggle(
    "hidden", Boolean(results.length) || state.automationTestLoading,
  );
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function loadAutomationTestData() {
  state.automationTestLoading = true;
  state.automationTestMessage = "Carregando lotes e contratos registrados...";
  renderAutomationTest();
  try {
    const [lots, registry] = await Promise.all([
      request("/api/toa-capture/lots", { timeoutMs: 30000 }),
      request(apiUrl(`/api/toa-contracts?date=${encodeURIComponent(elements.date.value)}`), { timeoutMs: 30000 }),
    ]);
    state.automationTestLots = Array.isArray(lots.lots) ? lots.lots : [];
    state.automationTestLotKey = state.automationTestLots.some(
      (lot) => lot.key === state.automationTestLotKey,
    ) ? state.automationTestLotKey : lots.default_lot || "";
    state.automationTestRegistry = registry;
    state.automationTestMessage = state.automationTestLots.length
      ? "Pronto para analisar em modo somente leitura."
      : "Nenhum lote TECHCAP V5.6 foi localizado.";
  } catch (error) {
    state.automationTestMessage = error.message;
    showToast(error.message, "error");
    console.error("Falha ao preparar teste de automacao", error);
  } finally {
    state.automationTestLoading = false;
    renderAutomationTest();
  }
}

async function analyzeAutomationTest() {
  const contracts = automationTestContracts();
  if (!contracts.length || !state.automationTestLotKey || state.automationTestLoading) return;
  state.automationTestLoading = true;
  state.automationTestMessage = `Analisando ${contracts.length} contratos sem escrita...`;
  state.automationTestResult = null;
  renderAutomationTest();
  try {
    const result = await request("/api/toa-capture/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lot_key: state.automationTestLotKey,
        contracts,
      }),
      timeoutMs: 120000,
    });
    if (!result.dry_run_only || result.imperium_write_enabled) {
      throw new Error("O painel recusou uma resposta que nao confirma o dry-run");
    }
    state.automationTestResult = result;
    state.automationTestMessage = `${result.results.length} resultado(s). Nenhuma operacao foi enviada ao Imperium.`;
  } catch (error) {
    state.automationTestMessage = error.message;
    showToast(error.message, "error");
    console.error("Falha no teste de automacao", error);
  } finally {
    state.automationTestLoading = false;
    renderAutomationTest();
  }
}

async function loadProfile() {
  const profileKey = state.profile;
  try {
    const payload = await request(apiUrl("/api/status"));
    if (profileKey !== state.profile) return;
    const company = String(payload.label || payload.company || "").trim() || "NATAL";
    state.closeEnabled = Boolean(payload.close_enabled);
    state.officialCloseEnabled = Boolean(payload.official_close_enabled);
    state.materialWriteoffEnabled = Boolean(payload.material_writeoff_enabled);
    state.nativeCreationEnabled = Boolean(payload.native_creation_enabled);
    state.installerChangeEnabled = Boolean(payload.installer_change_enabled);
    state.serializedTransferEnabled = Boolean(payload.serialized_transfer_enabled);
    const officialOpt = elements.closeTransport.querySelector('[value="official_http"]');
    if (officialOpt) {
      officialOpt.disabled = !state.officialCloseEnabled;
      officialOpt.textContent = "API oficial IMPERIUM (padrão)";
    }
    const hasDataSnapIdentity = Boolean(
      state.authUser?.imperium_identities?.[state.profile],
    );
    const dataSnapOpt = elements.closeTransport.querySelector('[value="datasnap"]');
    if (dataSnapOpt) {
      dataSnapOpt.disabled = !hasDataSnapIdentity;
      dataSnapOpt.textContent = "DataSnap (protocolo direto)";
    }
    elements.closeTransport.value = state.officialCloseEnabled
      ? "official_http"
      : hasDataSnapIdentity
        ? "datasnap"
        : "official_http";
    state.nativeCreationServices = Array.isArray(payload.native_creation_services)
      ? payload.native_creation_services.map(String) : [];
    elements.bulkService.replaceChildren(
      ...state.nativeCreationServices.map((service) => new Option(service)),
    );
    elements.manualService.replaceChildren(
      ...state.nativeCreationServices.map((service) => new Option(service)),
    );
    if (!state.nativeCreationServices.includes(elements.bulkService.value.trim())) {
      elements.bulkService.value = state.nativeCreationServices[0] || "";
    }
    if (!state.nativeCreationServices.includes(elements.manualService.value.trim())) {
      elements.manualService.value = state.nativeCreationServices[0] || "";
    }
    if (Array.isArray(payload.codes) && payload.codes.length) {
      state.closeCodes = payload.codes.map((item) => ({
        code: String(item.code),
        description: String(item.description),
        productive: Boolean(item.productive),
        requiresObservation: Boolean(item.requires_observation),
      }));
    }
    const defaultCode = String(payload.default_code || "106");
    if (state.closeCodes.some((item) => item.code === defaultCode)) {
      state.closeCode = defaultCode;
    }
    renderCreationCloseCodes();
    elements.product.textContent = "TECHNET - DOMINIUM";
    document.title = `DOMINIUM - ${company}`;
  } catch (error) {
    console.error("Falha ao identificar a empresa", error);
  }
}

async function switchProfile(profileKey) {
  if (
    state.running || state.loading || state.profileSwitching
    || state.bulkCreateLoading || state.stockBatchLoading
    || state.stockWriteoffLoading || state.toaLiveLoading || state.importLoading
    || state.materialLoading || state.materialPasteLoading
    || disconnectIsRunning()
    || profileKey === state.profile
  ) return;
  const profile = state.profiles.find((item) => item.key === profileKey);
  if (!profile) return;
  state.profileEpoch += 1;
  resetProfileOperationalState();
  state.profile = profileKey;
  state.profileSwitching = true;
  state.monitorCsvSnapshot = null;
  state.closeEnabled = Boolean(profile.close_enabled);
  state.officialCloseEnabled = Boolean(profile.official_close_enabled);
  state.materialWriteoffEnabled = Boolean(profile.material_writeoff_enabled);
  state.nativeCreationEnabled = Boolean(profile.native_creation_enabled);
  state.installerChangeEnabled = Boolean(profile.installer_change_enabled);
  state.serializedTransferEnabled = Boolean(profile.serialized_transfer_enabled);
  state.nativeCreationServices = Array.isArray(profile.native_creation_services)
    ? profile.native_creation_services.map(String) : [];
  state.orders = [];
  state.selected.clear();
  state.failures = [];
  state.completed = 0;
  state.stockTechnicians = [];
  state.stockSource = "datasnap";
  if (elements.stockSource) elements.stockSource.value = "datasnap";
  state.stockSelectedId = "";
  state.stockData = null;
  state.stockLoading = false;
  state.stockTechniciansLoading = false;
  state.stockBatchSelected.clear();
  state.stockBatchLoading = false;
  state.stockWriteoffLoading = false;
  state.pendingStockWriteoff = null;
  state.stockWriteoffBasket.clear();
  state.stockWriteoffRequestId = null;
  state.stockWriteoffBlocked.clear();
  state.bulkCreateLoading = false;
  state.bulkCreateResult = null;
  state.bulkCreateRequestId = null;
  state.automationTestRegistry = null;
  state.automationTestResult = null;
  state.automationTestMessage = "";
  elements.search.value = "";
  elements.stockTechnicianSearch.value = "";
  elements.stockItemSearch.value = "";
  elements.bulkTechnicianSearch.value = "";
  elements.bulkTechnicianSelect.value = "";
  elements.bulkService.value = state.nativeCreationServices[0] || "";
  elements.bulkContracts.value = "";
  elements.manualTechnicianSearch.value = "";
  elements.manualTechnicianSelect.value = "";
  elements.manualService.value = state.nativeCreationServices[0] || "";
  elements.manualContract.value = "";
  state.closeWorkspaceOrderId = null;
  state.closeInstallerChecks = {};
  state.closeReport = { records: [], summary: {} };
  state.closeReportLoading = false;
  state.operationalDatabase = { contracts: [], total: 0 };
  state.operationalContract = null;
  state.serialAudit = null;
  elements.stockGroupFilter.replaceChildren(new Option("Todos", ""));
  elements.status.value = "field";
  updateServiceOptions();
  elements.runbar.classList.add("hidden");
  updateAddress();
  render();
  try {
    await loadProfile();
    await loadMonitorCsvSnapshot({ quiet: true });
    await loadOrders();
    await loadSemiAutoAgenda({ quiet: true });
    await loadCloseReport({ quiet: true });
    if (state.activeModule === "database") await loadOperationalDatabase({ quiet: true });
    if (["stock", "bulk"].includes(state.activeModule)) await loadStockTechnicians();
    if (state.activeModule === "automation-test") await loadAutomationTestData();
  } finally {
    if (profileKey === state.profile) {
      state.profileSwitching = false;
      renderProfileTabs();
      render();
    }
  }
}

function closeDialogIfOpen(dialog) {
  if (dialog?.open) dialog.close();
}

function resetProfileOperationalState() {
  state.pendingConfirmation = [];
  state.pendingProductive = null;
  state.productiveDrafts = {};
  state.pendingCode = "106";
  state.pendingCloseExtra = {};
  state.importFile = null;
  state.importPreview = null;
  state.importResult = null;
  state.toaLiveResult = null;
  state.toaLiveLoading = false;
  state.semiAutoStopRequested = true;
  state.semiAutoJobs = [];
  state.semiAutoRunning = false;
  state.semiAutoPaused = false;
  state.semiAutoProfile = "";
  state.semiAutoCurrentContract = "";
  state.semiAutoWaitingWindow = "";
  state.semiAutoRefreshing = false;
  state.semiAutoLastImperiumCheckAt = 0;
  state.semiAutoJobsSinceImperiumCheck = 0;
  state.semiAutoAgenda = null;
  state.semiAutoAgendaLoading = false;
  state.automationTestResult = null;
  state.currentMaterialPasteKey = "";
  state.materialInventory = [];
  state.materialError = "";
  state.materialNotice = "";
  state.serialOwnerLookup = null;
  state.installerMovePreview = null;
  state.serializedTransferPreview = null;
  [
    elements.dialog,
    elements.closePickerDialog,
    elements.equipmentDialog,
    elements.serialOwnerDialog,
    elements.installerMoveDialog,
    elements.serializedTransferDialog,
  ].forEach(closeDialogIfOpen);
}

function setModule(module) {
  if (module === "monitor") module = "close";
  if (
    state.running || state.bulkCreateLoading || state.stockBatchLoading
    || state.stockWriteoffLoading
    || ![
      "dashboard", "monitor", "orders", "stock", "technicians", "bulk", "imports",
      "automation-test", "close", "report", "history", "intelligence", "database",
    ].includes(module)
  ) return;
  if (module !== "stock" && state.stockSource === "official") {
    state.stockSource = "datasnap";
    elements.stockSource.value = "datasnap";
    state.stockTechnicians = [];
    state.stockSelectedId = "";
    state.stockData = null;
    state.stockWriteoffBasket.clear();
    state.stockBatchSelected.clear();
  }
  state.activeModule = module;
  updateAddress();
  render();
  document.dispatchEvent(new CustomEvent("dominium:module-change", { detail: { module } }));
  window.scrollTo({ top: 0, left: 0 });
  document.querySelector("main").scrollTo({ top: 0, left: 0 });
  if (["stock", "bulk"].includes(module) && !state.stockTechnicians.length) {
    loadStockTechnicians();
  }
  if (module === "technicians" && !state.technicians.length) loadTechnicians();
  if (module === "imports") loadToaAutomation({ quiet: true });
  if (module === "automation-test") loadAutomationTestData();
  if (module === "intelligence") {
    loadIntelligence();
    loadHealthCheck();
  }
  if (module === "monitor" && state.disconnectToaHealthy && !state.loading) {
    void loadOrders({ preserveSelection: true, quiet: true });
  }
  if (module === "report") loadCloseReport();
  if (module === "database") loadOperationalDatabase();
  if (module === "history") {
    loadServerLogs({ quiet: true });
    loadImportAuditHistory({ quiet: true });
  }
}

// =============================================================================
// TOA -> IMPERIUM | PREVIA E DESTINO DA IMPORTACAO DE O.S.
// =============================================================================
function renderImportTargets() {
  const buttons = state.importTargets.map((target) => {
    const button = document.createElement("button");
    button.className = "import-target";
    button.type = "button";
    button.textContent = target.label;
    button.title = target.description;
    const active = target.key === state.importTarget;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    button.disabled = state.importLoading;
    button.addEventListener("click", () => {
      state.importTarget = target.key;
      state.importPreview = null;
      state.importResult = null;
      if (state.importFile) previewImportFile();
      else render();
    });
    return button;
  });
  elements.importTargets.replaceChildren(...buttons);
}

function selectImportTargetForFile(file) {
  const route = file?.name.match(/^Atividades-([A-Z0-9]+)-/i)?.[1]?.toUpperCase();
  if (!route) return;
  const target = state.importTargets.find((item) =>
    Array.isArray(item.routes) && item.routes.includes(route),
  );
  if (target) state.importTarget = target.key;
}

function importPreviewRow(order) {
  const row = document.createElement("tr");
  const checkCell = document.createElement("td");
  checkCell.style.textAlign = "center";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "import-row-checkbox";
  const osNum = String(order.os_number);
  const isSelected = state.selectedImportOs ? state.selectedImportOs.has(osNum) : true;
  checkbox.checked = isSelected;
  checkbox.addEventListener("change", () => {
    if (!state.selectedImportOs) {
      state.selectedImportOs = new Set((state.importPreview?.orders || []).map((o) => String(o.os_number)));
    }
    if (checkbox.checked) {
      state.selectedImportOs.add(osNum);
    } else {
      state.selectedImportOs.delete(osNum);
    }
    renderImportPreview();
  });
  checkCell.append(checkbox);
  row.append(checkCell);

  [
    order.os_number,
    order.contract,
    order.city,
    order.technician,
    order.os_type,
    order.activity_status,
    order.import_status || "Pronta para importar",
  ].forEach((value, index) => {
    const cell = document.createElement("td");
    if (index === 3 && order.technician_name) {
      const identity = document.createElement("div");
      identity.className = "import-technician";
      const name = document.createElement("strong");
      name.textContent = order.technician_name;
      const login = document.createElement("small");
      login.textContent = order.technician_login || order.technician;
      identity.append(name, login);
      cell.append(identity);
    } else {
      cell.textContent = value || "-";
    }
    if (index === 0) cell.className = "os-number";
    if (index === 4) {
      cell.classList.add("service-name");
      cell.title = value || "";
    }
    if (index === 6) {
      cell.className = order.import_status
        ? order.imported ? "import-status success" : "import-status warning"
        : "import-status";
    }
    row.append(cell);
  });
  return row;
}

function filteredDirectoryTechnicians() {
  const term = normalize(elements.technicianSearch.value);
  const team = elements.technicianTeamFilter.value;
  return state.technicians.filter((technician) => {
    const teamMatch = !team || technician.teams.includes(team);
    const searchMatch = !term || normalize(
      `${technician.name} ${technician.login} ${technician.plate} ${technician.teams.join(" ")} `
      + `${technician.city || ""} ${technician.bucket || ""} `
      + `${technician.toa?.resource_id || ""} ${technician.toa?.user_id || ""}`,
    ).includes(term);
    return teamMatch && searchMatch;
  });
}

function directoryTechnicianRow(technician) {
  const row = document.createElement("tr");
  const name = document.createElement("td");
  name.className = "technician-identity";
  const nameStrong = document.createElement("strong");
  nameStrong.textContent = technician.name;
  const coverage = document.createElement("small");
  coverage.textContent = technician.city
    ? [technician.city, technician.bucket].filter(Boolean).join(" • ")
    : technician.city_status === "pending"
      ? "Cidade pendente no TOA"
      : technician.profiles.length
        ? technician.profiles.map((profile) => profile.toUpperCase()).join(" / ")
        : "Equipe compartilhada";
  name.append(nameStrong, coverage);

  const login = document.createElement("td");
  const loginCode = document.createElement("code");
  loginCode.textContent = technician.login;
  login.append(loginCode);

  const plate = document.createElement("td");
  plate.textContent = technician.plate || "Sem placa";
  if (!technician.plate) plate.className = "muted-cell";

  const teams = document.createElement("td");
  teams.className = "technician-teams";
  teams.textContent = technician.teams.join(" / ") || "Sem equipe informada";

  const action = document.createElement("td");
  action.className = "action-cell";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "icon-button directory-copy";
  copy.title = `Copiar login ${technician.login}`;
  copy.setAttribute("aria-label", copy.title);
  copy.innerHTML = '<i data-lucide="copy" aria-hidden="true"></i>';
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(technician.login);
      showToast(`Login ${technician.login} copiado.`, "success");
    } catch {
      showToast(`Nao foi possivel copiar ${technician.login}.`, "error");
    }
  });
  action.append(copy);
  row.append(name, login, plate, teams, action);
  return row;
}

function renderTechnicians() {
  const selectedTeam = elements.technicianTeamFilter.value;
  const teamOptions = [new Option("Todas", "")];
  Object.keys(state.technicianTeams).forEach((team) => teamOptions.push(
    new Option(`${team} (${state.technicianTeams[team]})`, team),
  ));
  elements.technicianTeamFilter.replaceChildren(...teamOptions);
  if (state.technicianTeams[selectedTeam]) elements.technicianTeamFilter.value = selectedTeam;

  const visible = filteredDirectoryTechnicians();
  elements.technicianCount.textContent = state.technicians.length;
  elements.technicianPlateCount.textContent = state.technicians.filter((item) => item.plate).length;
  elements.technicianTeamCount.textContent = Object.keys(state.technicianTeams).length;
  elements.technicianVisibleCount.textContent = visible.length;
  elements.technicianBody.replaceChildren(...visible.map(directoryTechnicianRow));
  elements.technicianEmpty.classList.toggle(
    "hidden",
    state.techniciansLoading || visible.length > 0,
  );
  elements.technicianLoading.classList.toggle("hidden", !state.techniciansLoading);
  const importedAt = state.technicianSource.imported_at
    ? new Date(state.technicianSource.imported_at).toLocaleString("pt-BR")
    : "";
  elements.technicianSource.textContent = importedAt
    ? `Cadastro atualizado em ${importedAt}`
    : state.technicians.length ? "Cadastro local carregado" : "Cadastro indisponivel";
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function loadTechnicians() {
  if (state.techniciansLoading) return;
  state.techniciansLoading = true;
  renderTechnicians();
  try {
    const payload = await request("/api/technicians");
    state.technicians = Array.isArray(payload.technicians) ? payload.technicians : [];
    state.technicianTeams = payload.teams || {};
    state.technicianSource = payload.source || {};
  } catch (error) {
    state.technicians = [];
    state.technicianTeams = {};
    state.technicianSource = {};
    showToast(error.message, "error");
    console.error("Falha ao carregar tecnicos", error);
  } finally {
    state.techniciansLoading = false;
    renderTechnicians();
  }
}

function renderImportPreview() {
  const preview = state.importPreview;
  const target = state.importTargets.find((item) => item.key === state.importTarget);
  const retryCount = Array.isArray(state.importResult?.retry_os_numbers)
    ? state.importResult.retry_os_numbers.length : 0;
  const totalOrders = preview?.orders?.length || 0;
  const selectedCount = state.selectedImportOs ? state.selectedImportOs.size : totalOrders;

  elements.importFileName.textContent = state.importFile?.name || "Nenhum arquivo selecionado";
  elements.importSelectedFile.classList.toggle("has-file", Boolean(state.importFile));
  elements.importDropzone.classList.toggle("has-file", Boolean(state.importFile));
  elements.importSourceRows.textContent = preview?.source_rows || 0;
  elements.importOrderCount.textContent = preview?.count || 0;
  elements.importCities.textContent = preview ? Object.keys(preview.cities || {}).length : 0;
  elements.importTargetLabel.textContent = target?.label || state.importTarget.toUpperCase();
  elements.importPreviewBody.replaceChildren(
    ...(preview?.orders || []).map(importPreviewRow),
  );
  if (elements.importSelectAll) {
    elements.importSelectAll.checked = totalOrders > 0 && selectedCount === totalOrders;
    elements.importSelectAll.indeterminate = selectedCount > 0 && selectedCount < totalOrders;
  }
  elements.importEmpty.classList.toggle("hidden", Boolean(preview) || state.importLoading);
  elements.importLoading.classList.toggle("hidden", !state.importLoading);
  elements.commitImport.disabled = !preview || state.importLoading || !preview.import_enabled
    || selectedCount === 0
    || Boolean(state.importResult && !retryCount);
  elements.commitImport.textContent = state.importLoading
    ? "Processando..."
    : retryCount
      ? `Reprocessar ${retryCount} ausentes`
      : selectedCount < totalOrders
        ? `Importar ${selectedCount} OS selecionadas`
        : `Importar ${selectedCount} OS`;
  elements.importResult.classList.toggle("hidden", !state.importResult);
  if (state.importResult) {
    elements.importResultTitle.textContent = state.importResult.partial
      ? "Importacao parcial confirmada"
      : "Resultado confirmado pelo Imperium";
    elements.importResultDetail.textContent = state.importResult.partial
      ? `${state.importResult.imported} presentes no Imperium; ${retryCount} aguardando reprocessamento seletivo`
      : `${state.importResult.imported} importadas; ${state.importResult.not_imported} nao importadas`;
  }
  renderImportTargets();
}

async function fileAsBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

async function previewImportFile() {
  if (!state.importFile || state.importLoading) return;
  state.importLoading = true;
  state.importPreview = null;
  state.selectedImportOs = null;
  renderImportPreview();
  try {
    const payload = await request("/api/imports/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: state.importTarget,
        filename: state.importFile.name,
        content_base64: await fileAsBase64(state.importFile),
      }),
    });
    state.importPreview = payload;
    state.selectedImportOs = new Set((payload.orders || []).map((o) => String(o.os_number)));
    state.importResult = null;
    if (payload.target?.key) {
      state.importTarget = payload.target.key;
    }
    const savedContracts = Number(payload.agenda_registry?.recorded || 0);
    const savedMessage = savedContracts
      ? ` ${savedContracts} contrato(s) e suas janelas ficaram salvos para a esteira.`
      : "";
    showToast(
      payload.excluded_count
        ? `${payload.count} OS validas; ${payload.excluded_count} ignoradas (fora da cidade ou canceladas no TOA).${savedMessage}`
        : `${payload.count} OS encontradas no arquivo.${savedMessage}`,
      payload.excluded_count ? "warning" : "success",
    );
    if (payload.excluded_count) {
      console.warn("OS excluidas por escopo de cidade ou status", payload.scope_exclusions);
    }
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao ler CSV/ZIP TOA", error);
  } finally {
    state.importLoading = false;
    renderImportPreview();
  }
}

async function commitImportFile() {
  if (!state.importFile || !state.importPreview || state.importLoading) return;
  const previousOrders = [...(state.importPreview.orders || [])];
  const retryOsNumbers = Array.isArray(state.importResult?.retry_os_numbers)
    ? [...state.importResult.retry_os_numbers] : [];
  const selectedOsNumbers = state.selectedImportOs
    ? Array.from(state.selectedImportOs)
    : (state.importPreview.orders || []).map((o) => String(o.os_number));
  const osNumbersToSend = retryOsNumbers.length ? retryOsNumbers : selectedOsNumbers;
  if (!osNumbersToSend.length) {
    showToast("Nenhuma OS selecionada para importação.", "error");
    return;
  }
  state.importLoading = true;
  renderImportPreview();
  try {
    const payload = await request("/api/imports/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: state.importTarget,
        filename: state.importFile.name,
        content_base64: await fileAsBase64(state.importFile),
        approved_source_hash: state.importPreview.import_scope?.source_hash || "",
        approved_batch_id: state.importPreview.import_scope?.batch_id || "",
        batch_id: state.importPreview.import_scope?.batch_id || "",
        only_os_numbers: osNumbersToSend,
      }),
      timeoutMs: 300000,
    });
    const returned = new Map((payload.orders || []).map((order) => [
      `${order.os_number}|${order.contract}`,
      order,
    ]));
    const mergedOrders = previousOrders.map((order) => returned.get(
      `${order.os_number}|${order.contract}`,
    ) || order);
    const remaining = Array.isArray(payload.retry_os_numbers)
      ? payload.retry_os_numbers : [];
    const imported = mergedOrders.filter((order) => order.imported).length;
    state.importResult = {
      ...payload,
      count: mergedOrders.length,
      imported,
      not_imported: mergedOrders.length - imported,
      partial: Boolean(remaining.length),
      retry_os_numbers: remaining,
      orders: mergedOrders,
    };
    state.importPreview = {
      ...state.importPreview,
      orders: mergedOrders,
      count: mergedOrders.length,
    };
    if (remaining.length) {
      state.selectedImportOs = new Set(remaining);
    }
    showToast(
      remaining.length
        ? `${imported} confirmadas; ${remaining.length} ausentes podem ser reprocessadas sem repetir o lote.`
        : `${imported} confirmadas no Imperium.`,
      remaining.length ? "error" : "success",
    );
    // Uma nova importacao pode fazer aparecer no Imperium contratos que o TOA
    // ja tinha localizado durante a esteira. Acorda somente essa fila de espera.
    void semiAutoWakeAwaitingImperiumImports();
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao importar CSV TOA", error);
  } finally {
    state.importLoading = false;
    renderImportPreview();
  }
}

// =============================================================================
// IMPERIUM | ESTOQUE, EQUIPAMENTOS E TECNICOS
// =============================================================================
function stockTechnicianLabel(technician) {
  if (state.stockSource === "official" || technician.official_source) {
    const stockId = technician.stock_id ? ` · estoque ${technician.stock_id}` : "";
    const responsible = technician.installer_id
      ? ` · responsavel ${technician.installer_id}` : "";
    return `${technician.stock_name || technician.technician_name}${stockId}${responsible}`;
  }
  return technician.stock_name === technician.technician_name
    ? technician.technician_name
    : `${technician.technician_name} - ${technician.stock_name}`;
}

function filteredStockTechnicians() {
  const term = normalize(elements.stockTechnicianSearch.value.trim());
  if (!term) return state.stockTechnicians;
  return state.stockTechnicians.filter((technician) =>
    normalize(
      `${technician.technician_name} ${technician.stock_name} ${technician.installer_id}`,
    ).includes(term),
  );
}

function renderStockTechnicians() {
  const current = state.stockSelectedId;
  const options = [new Option(
    state.stockTechniciansLoading
      ? "Carregando tecnicos..."
      : state.stockTechnicians.length
        ? "Selecione um tecnico"
        : "Nenhum tecnico encontrado",
    "",
  )];
  filteredStockTechnicians().forEach((technician) => {
    options.push(
      new Option(stockTechnicianLabel(technician), String(technician.stock_id)),
    );
  });
  elements.stockTechnicianSelect.replaceChildren(...options);
  if (
    [...elements.stockTechnicianSelect.options]
      .some((option) => option.value === current)
  ) {
    elements.stockTechnicianSelect.value = current;
  } else {
    elements.stockTechnicianSelect.value = "";
    state.stockSelectedId = "";
  }
  elements.stockTechnicianSelect.disabled = state.stockTechniciansLoading
    || state.stockLoading || state.stockBatchLoading || state.bulkCreateLoading;
}

async function loadStockTechnicians() {
  if (
    state.stockTechniciansLoading || state.stockLoading || state.stockBatchLoading
    || state.bulkCreateLoading
  ) return;
  const profileKey = state.profile;
  state.stockTechniciansLoading = true;
  renderStock();
  try {
    const officialSource = state.stockSource === "official";
    const payload = await request(
      apiUrl(officialSource ? "/api/imperium-official/stocks" : "/api/stock/technicians"),
      { timeoutMs: 120000 },
    );
    if (profileKey !== state.profile) return;
    state.stockTechnicians = officialSource
      ? (payload.stocks || []).map((stock) => ({
        stock_id: stock.stock_id,
        installer_id: stock.installer_id,
        stock_name: stock.name || `Estoque ${stock.stock_id}`,
        technician_name: stock.name || `Estoque ${stock.stock_id}`,
        active: stock.active,
        official_source: true,
      }))
      : (payload.technicians || []);
    if (
      !state.stockTechnicians.some(
        (item) => String(item.stock_id) === state.stockSelectedId,
      )
    ) {
      state.stockSelectedId = "";
      state.stockData = null;
    }
  } catch (error) {
    if (profileKey !== state.profile) return;
    state.stockTechnicians = [];
    state.stockSelectedId = "";
    state.stockData = null;
    showToast(error.message, "error");
    console.error("Falha ao carregar tecnicos", error);
  } finally {
    if (profileKey !== state.profile) return;
    state.stockTechniciansLoading = false;
    renderStock();
    renderBulkCreate();
    renderManualCreate();
  }
}

function updateStockGroupOptions() {
  const current = elements.stockGroupFilter.value;
  const groups = [
    ...new Set((state.stockData?.items || []).map((item) => item.group)),
  ].sort((a, b) => a.localeCompare(b, "pt-BR"));
  elements.stockGroupFilter.replaceChildren(new Option("Todos", ""));
  groups.forEach((group) => {
    elements.stockGroupFilter.add(new Option(group, group));
  });
  elements.stockGroupFilter.value = groups.includes(current) ? current : "";
}

function visibleStockItems() {
  const term = normalize(elements.stockItemSearch.value.trim());
  const group = elements.stockGroupFilter.value;
  const showZero = elements.stockShowZero.checked;
  return (state.stockData?.items || []).filter((item) => {
    if (!showZero && Number(item.quantity || 0) <= 0) return false;
    if (group && item.group !== group) return false;
    if (!term) return true;
    const serialText = (item.serials || [])
      .map((serial) => `${serial.serial} ${serial.smart || ""}`)
      .join(" ");
    return normalize(
      `${item.group} ${item.code} ${item.equipment} ${item.brand} `
      + `${item.quantity_label} ${serialText}`,
    ).includes(term);
  });
}

function stockItemRow(item) {
  const row = document.createElement("tr");
  const group = document.createElement("td");
  group.textContent = item.group;
  const code = document.createElement("td");
  code.className = "stock-code";
  code.textContent = item.code;
  const equipment = document.createElement("td");
  equipment.className = "stock-equipment";
  equipment.textContent = item.equipment;
  equipment.title = item.equipment;
  const brand = document.createElement("td");
  brand.textContent = item.brand || "-";
  const quantity = document.createElement("td");
  const quantityBadge = document.createElement("span");
  quantityBadge.className = `stock-quantity ${Number(item.quantity || 0) > 0 ? "positive" : "zero"
    }`;
  quantityBadge.textContent = item.quantity_label || `${item.quantity} ${item.unit}`;
  quantity.append(quantityBadge);
  const serialCell = document.createElement("td");
  const serials = item.serials || [];
  if (state.stockSource === "official" && item.serialized) {
    serialCell.textContent = "Serializado";
  } else if (!serials.length) {
    serialCell.textContent = "-";
  } else {
    const details = document.createElement("details");
    details.className = "stock-serials";
    const summary = document.createElement("summary");
    summary.textContent = `${serials.length} ${serials.length === 1 ? "serial" : "seriais"
      }`;
    const list = document.createElement("div");
    list.className = "stock-serial-list";
    serials.forEach((serial) => {
      const value = document.createElement("code");
      value.textContent = serial.smart
        ? `${serial.serial} / SMART ${serial.smart}`
        : serial.serial;
      list.append(value);
    });
    details.append(summary, list);
    serialCell.append(details);
  }
  const action = document.createElement("td");
  action.className = "action-cell stock-writeoff-action";
  const actionButton = document.createElement("button");
  actionButton.type = "button";
  actionButton.className = "button secondary compact stock-writeoff-button";
  const available = Number(item.quantity || 0);
  const materialWithoutSerial = String(item.identified || "").toUpperCase() === "N"
    && serials.length === 0;
  const writeoffKey = `${state.stockSelectedId}:${item.equipment_id}`;
  const blockedForVerification = state.stockWriteoffBlocked.has(writeoffKey);
  const selectedForWriteoff = state.stockWriteoffBasket.has(
    String(item.equipment_id),
  );
  row.classList.toggle("stock-writeoff-selected", selectedForWriteoff);
  const officialReadOnly = state.stockSource === "official";
  actionButton.disabled = officialReadOnly || !state.materialWriteoffEnabled
    || state.stockWriteoffLoading || state.stockLoading || state.stockBatchLoading
    || available <= 0 || !materialWithoutSerial || blockedForVerification;
  if (officialReadOnly) {
    actionButton.textContent = "Somente consulta";
    actionButton.title = "A API oficial do Imperium esta habilitada somente para consulta.";
  } else if (blockedForVerification) {
    actionButton.textContent = "Verificar OS";
    actionButton.title = "A tentativa ficou pendente. Confira a OS no Imperium antes de reiniciar o painel.";
  } else if (!state.materialWriteoffEnabled) {
    actionButton.textContent = "Indisponivel";
    actionButton.title = "A baixa rapida de material foi validada inicialmente na base Natal";
  } else if (available <= 0) {
    actionButton.textContent = "Sem saldo";
  } else if (!materialWithoutSerial) {
    actionButton.textContent = "Com serial";
    actionButton.title = "Equipamentos identificados precisam da baixa por serial";
  } else {
    actionButton.classList.toggle("primary", selectedForWriteoff);
    actionButton.classList.toggle("secondary", !selectedForWriteoff);
    actionButton.textContent = selectedForWriteoff ? "Selecionado" : "Adicionar";
    actionButton.addEventListener("click", () => toggleStockWriteoffItem(item));
  }
  action.append(actionButton);
  row.append(group, code, equipment, brand, quantity, serialCell, action);
  return row;
}

function createWriteoffRequestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `baixa-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function toggleStockWriteoffItem(item) {
  if (
    state.stockWriteoffLoading || !state.stockData
    || !state.materialWriteoffEnabled
  ) return;
  const key = String(item.equipment_id);
  if (state.stockWriteoffBasket.has(key)) {
    state.stockWriteoffBasket.delete(key);
    state.stockWriteoffRequestId = null;
    renderStock();
    return;
  }
  if (state.stockWriteoffBasket.size >= 30) {
    showToast("Uma baixa permite no maximo 30 materiais.", "error");
    return;
  }
  const available = Number(item.quantity || 0);
  const serials = item.serials || [];
  if (available <= 0) {
    showToast("Este material esta sem saldo.", "error");
    return;
  }
  if (String(item.identified || "").toUpperCase() !== "N" || serials.length) {
    showToast("Este item precisa da baixa por serial.", "error");
    return;
  }
  state.stockWriteoffBasket.set(key, item);
  state.stockWriteoffRequestId = null;
  renderStock();
}

function renderStockWriteoffItems() {
  const items = state.pendingStockWriteoff || [];
  elements.stockWriteoffDialogCount.textContent =
    `${items.length} ${items.length === 1 ? "selecionado" : "selecionados"}`;
  elements.stockWriteoffItems.replaceChildren(...items.map((item) => {
    const row = document.createElement("div");
    row.className = "stock-writeoff-item";
    row.dataset.equipmentId = String(item.equipment_id);
    const identity = document.createElement("div");
    const code = document.createElement("strong");
    code.textContent = item.code || "-";
    const name = document.createElement("span");
    name.textContent = item.equipment || "-";
    const balance = document.createElement("small");
    balance.textContent = `Saldo ${item.quantity_label || `${item.quantity} ${item.unit}`}`;
    identity.append(code, name, balance);
    const quantity = document.createElement("input");
    quantity.type = "number";
    quantity.min = "0.01";
    quantity.step = "0.01";
    quantity.max = String(Number(item.quantity || 0));
    quantity.value = String(Math.min(1, Number(item.quantity || 0)));
    quantity.inputMode = "decimal";
    quantity.required = true;
    quantity.dataset.writeoffQuantity = String(item.equipment_id);
    quantity.setAttribute("aria-label", `Quantidade de ${item.equipment}`);
    const unit = document.createElement("b");
    unit.textContent = item.unit || "UN";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon-button";
    remove.title = "Remover da baixa";
    remove.setAttribute("aria-label", `Remover ${item.equipment}`);
    remove.innerHTML = '<i data-lucide="x" aria-hidden="true"></i>';
    remove.addEventListener("click", () => {
      if (state.stockWriteoffLoading) return;
      state.stockWriteoffBasket.delete(String(item.equipment_id));
      state.pendingStockWriteoff = [...state.stockWriteoffBasket.values()];
      if (!state.pendingStockWriteoff.length) {
        elements.stockWriteoffDialog.close();
      } else {
        renderStockWriteoffItems();
      }
      renderStock();
    });
    row.append(identity, quantity, unit, remove);
    return row;
  }));
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

function openStockWriteoffDialog() {
  if (
    state.stockWriteoffLoading || !state.stockData
    || !state.materialWriteoffEnabled || !state.stockWriteoffBasket.size
  ) return;
  state.pendingStockWriteoff = [...state.stockWriteoffBasket.values()];
  state.stockWriteoffRequestId = null;
  elements.stockWriteoffTechnician.textContent =
    state.stockData.technician?.technician_name || "-";
  elements.stockWriteoffStatus.textContent = "";
  elements.stockWriteoffStatus.classList.add("hidden");
  elements.stockWriteoffStatus.classList.remove("error", "success");
  elements.stockWriteoffConfirm.textContent = "Criar OS e baixar";
  elements.stockWriteoffConfirm.disabled = false;
  elements.stockWriteoffCancel.disabled = false;
  renderStockWriteoffItems();
  elements.stockWriteoffDialog.showModal();
  setTimeout(() => {
    const first = elements.stockWriteoffItems.querySelector("input");
    first?.focus();
    first?.select();
  }, 0);
}

async function submitStockWriteoff(event) {
  event.preventDefault();
  const items = state.pendingStockWriteoff || [];
  const stockId = Number(state.stockSelectedId);
  if (!items.length || !stockId || state.stockWriteoffLoading) return;
  const materials = [];
  for (const item of items) {
    const input = elements.stockWriteoffItems.querySelector(
      `[data-writeoff-quantity="${item.equipment_id}"]`,
    );
    const quantity = Number(String(input?.value || "").replace(",", "."));
    const available = Number(item.quantity || 0);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      showToast(`Informe uma quantidade valida para ${item.code}.`, "error");
      input?.focus();
      return;
    }
    if (quantity > available + 0.000001) {
      showToast(
        `Saldo insuficiente para ${item.code}. Disponivel: ${item.quantity_label}.`,
        "error",
      );
      input?.focus();
      return;
    }
    materials.push({
      equipment_id: Number(item.equipment_id),
      quantity: String(quantity),
    });
  }

  state.stockWriteoffLoading = true;
  state.stockWriteoffRequestId ||= createWriteoffRequestId();
  elements.stockWriteoffConfirm.disabled = true;
  elements.stockWriteoffCancel.disabled = true;
  elements.stockWriteoffItems.querySelectorAll("input, button").forEach(
    (control) => { control.disabled = true; },
  );
  elements.stockWriteoffConfirm.textContent = "Criando OS e baixando...";
  elements.stockWriteoffStatus.textContent =
    "Aguarde. Nao feche o painel nem repita a operacao.";
  elements.stockWriteoffStatus.classList.remove("hidden", "error", "success");
  renderStock();
  try {
    const result = await request(apiUrl("/api/stock/writeoff"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stock_id: stockId,
        materials,
        confirmed: true,
        request_id: state.stockWriteoffRequestId,
      }),
      timeoutMs: 420000,
    });
    elements.stockWriteoffStatus.textContent =
      `OS ${result.num_os} criada e baixa confirmada.`;
    elements.stockWriteoffStatus.classList.add("success");
    showToast(
      result.stock_confirmed
        ? `OS ${result.num_os} criada. Novo saldo confirmado no estoque.`
        : `OS ${result.num_os} criada. Atualize o estoque para conferir o saldo.`,
      "success",
    );
    state.stockWriteoffRequestId = null;
    state.pendingStockWriteoff = null;
    state.stockWriteoffBasket.clear();
    elements.stockWriteoffDialog.close();
    state.stockWriteoffLoading = false;
    await loadTechnicianStock();
  } catch (error) {
    const normalizedMessage = normalize(error.message);
    const uncertain = Boolean(error.uncertain)
      || (normalizedMessage.includes("A OS ")
        && normalizedMessage.includes("FOI CRIADA"));
    if (uncertain) {
      items.forEach((item) => {
        state.stockWriteoffBlocked.add(`${stockId}:${item.equipment_id}`);
      });
    }
    elements.stockWriteoffStatus.textContent = uncertain
      ? `${error.message} Verifique a OS no Imperium antes de qualquer nova tentativa.`
      : error.message;
    elements.stockWriteoffStatus.classList.remove("hidden", "success");
    elements.stockWriteoffStatus.classList.add("error");
    showToast(error.message, "error");
    console.error("Falha na baixa rapida de material", error);
    state.stockWriteoffLoading = false;
  } finally {
    const blocked = items.some((item) => state.stockWriteoffBlocked.has(
      `${stockId}:${item.equipment_id}`,
    ));
    elements.stockWriteoffConfirm.disabled = state.stockWriteoffLoading || blocked;
    elements.stockWriteoffCancel.disabled = state.stockWriteoffLoading;
    elements.stockWriteoffItems.querySelectorAll("input, button").forEach(
      (control) => {
        control.disabled = state.stockWriteoffLoading || blocked;
      },
    );
    elements.stockWriteoffConfirm.textContent = state.stockWriteoffLoading
      ? "Criando OS e baixando..."
      : blocked ? "Verifique a OS" : "Criar OS e baixar";
    renderStock();
  }
}

function renderStock() {
  renderStockTechnicians();
  renderBulkTechnicians();
  const officialSource = state.stockSource === "official";
  const officialOption = elements.stockSource?.querySelector('option[value="official"]');
  if (officialOption) {
    officialOption.disabled = !["natal", "fortaleza"].includes(state.profile);
  }
  const summary = state.stockData?.summary;
  elements.stockTechnicianName.textContent =
    state.stockData?.technician?.technician_name || "-";
  elements.stockPositiveCount.textContent = summary?.positive_item_count || 0;
  elements.stockQuantityTotal.textContent = summary?.quantity_total || 0;
  elements.stockSerialLabel.textContent = officialSource ? "Itens serializados" : "Seriais";
  elements.stockSerialCount.textContent = officialSource
    ? (summary?.serialized_item_count || 0)
    : (summary?.serial_count || 0);
  const selectedMaterialCount = state.stockWriteoffBasket.size;
  elements.stockWriteoffCount.textContent = String(selectedMaterialCount);
  elements.stockWriteoffOpen.disabled = officialSource || !state.materialWriteoffEnabled
    || !state.stockData || !selectedMaterialCount || state.stockWriteoffLoading
    || state.stockLoading || state.stockBatchLoading;
  elements.stockWriteoffOpen.querySelector("span").textContent =
    selectedMaterialCount
      ? "Baixar selecionados"
      : "Selecionar materiais";
  const rows = visibleStockItems();
  elements.stockBody.replaceChildren(...rows.map(stockItemRow));
  elements.stockLoading.classList.toggle("hidden", !state.stockLoading);
  elements.stockEmpty.classList.toggle(
    "hidden", state.stockLoading || rows.length > 0,
  );
  if (!state.stockLoading) {
    if (!state.stockData) {
      elements.stockEmpty.textContent = state.stockTechniciansLoading
        ? "Carregando tecnicos..."
        : "Selecione um tecnico e consulte o estoque.";
    } else if (!rows.length) {
      elements.stockEmpty.textContent = officialSource && state.stockData.items.length === 0
        ? "Estoque vazio confirmado pela API oficial."
        : "Nenhum item corresponde aos filtros.";
    }
  }
  elements.stockConsult.disabled = !state.stockSelectedId
    || state.stockLoading || state.stockTechniciansLoading || state.stockBatchLoading
    || state.stockWriteoffLoading;
  elements.stockConsult.textContent = state.stockLoading
    ? "Consultando..." : "Consultar estoque";
  elements.stockTechnicianSearch.disabled = state.stockTechniciansLoading
    || state.stockLoading || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockTechnicianSelect.disabled = state.stockTechniciansLoading
    || state.stockLoading || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockSource.disabled = state.stockTechniciansLoading
    || state.stockLoading || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockItemSearch.disabled = state.stockLoading || !state.stockData
    || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockGroupFilter.disabled = state.stockLoading || !state.stockData
    || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockShowZero.disabled = state.stockLoading || !state.stockData
    || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockPdf.disabled = officialSource || !state.stockData || state.stockLoading
    || state.stockBatchLoading || state.stockWriteoffLoading;
  elements.stockPdf.textContent = state.stockBatchLoading
    ? "Gerando relatorio..." : "PDF deste tecnico";
  elements.stockBatch.disabled = officialSource || state.stockTechniciansLoading || state.stockLoading
    || state.stockBatchLoading || state.stockWriteoffLoading
    || state.stockTechnicians.length === 0;
  elements.stockBatch.textContent = state.stockBatchLoading
    ? "Processando lote..." : "Impressao em massa";
  renderStockBatchDialog();
}

async function loadTechnicianStock() {
  const stockId = Number(state.stockSelectedId);
  if (
    !stockId || state.stockLoading || state.stockBatchLoading
    || state.stockWriteoffLoading
  ) return;
  const profileKey = state.profile;
  state.stockLoading = true;
  state.stockData = null;
  state.stockWriteoffBasket.clear();
  state.pendingStockWriteoff = null;
  state.stockWriteoffRequestId = null;
  elements.stockItemSearch.value = "";
  elements.stockGroupFilter.replaceChildren(new Option("Todos", ""));
  renderStock();
  try {
    const officialSource = state.stockSource === "official";
    const payload = await request(
      apiUrl(officialSource
        ? `/api/imperium-official/stocks/${encodeURIComponent(stockId)}/items`
        : `/api/stock?stock_id=${encodeURIComponent(stockId)}`),
      { timeoutMs: 180000 },
    );
    if (
      profileKey !== state.profile
      || String(stockId) !== state.stockSelectedId
    ) return;
    if (officialSource) {
      const selectedStock = state.stockTechnicians.find(
        (item) => String(item.stock_id) === String(stockId),
      );
      const items = (payload.items || []).map((item) => {
        const rawQuantity = Number(String(item.quantity ?? 0).replace(",", "."));
        const quantity = Number.isFinite(rawQuantity) ? rawQuantity : 0;
        return {
          ...item,
          equipment: item.description || "",
          quantity,
          quantity_label: `${quantity} ${item.unit || ""}`.trim(),
          serials: [],
          identified: item.serialized ? "S" : "N",
        };
      });
      state.stockData = {
        ok: true,
        source: "imperium_official_http",
        read_only: true,
        technician: {
          stock_id: stockId,
          installer_id: selectedStock?.installer_id || null,
          technician_name: selectedStock?.stock_name || `Estoque ${stockId}`,
        },
        summary: {
          positive_item_count: items.filter((item) => item.quantity > 0).length,
          quantity_total: items.reduce((total, item) => total + item.quantity, 0),
          serialized_item_count: items.filter((item) => item.serialized).length,
          serial_count: 0,
        },
        items,
      };
    } else {
      state.stockData = payload;
    }
    updateStockGroupOptions();
    showToast(
      officialSource
        ? (state.stockData.summary.positive_item_count > 0
          ? `${state.stockData.summary.positive_item_count} itens com saldo pela API oficial.`
          : "Estoque vazio confirmado pela API oficial.")
        : `${payload.summary.positive_item_count} itens com saldo e ${payload.summary.serial_count} seriais.`,
      "success",
    );
  } catch (error) {
    if (profileKey !== state.profile) return;
    state.stockData = null;
    showToast(error.message, "error");
    console.error("Falha ao consultar estoque", error);
  } finally {
    if (profileKey !== state.profile) return;
    state.stockLoading = false;
    renderStock();
  }
}

function filteredStockBatchTechnicians() {
  const term = normalize(elements.stockBatchSearch.value.trim());
  if (!term) return state.stockTechnicians;
  return state.stockTechnicians.filter((technician) =>
    normalize(
      `${technician.technician_name} ${technician.stock_name} `
      + `${technician.installer_id} ${technician.stock_id}`,
    ).includes(term),
  );
}

function renderStockBatchDialog({ force = false } = {}) {
  if (!force && !elements.stockBatchDialog.open) return;
  const technicians = filteredStockBatchTechnicians();
  const rows = technicians.map((technician) => {
    const label = document.createElement("label");
    label.className = "stock-batch-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.stockBatchSelected.has(String(technician.stock_id));
    checkbox.disabled = state.stockBatchLoading;
    checkbox.addEventListener("change", () => {
      const key = String(technician.stock_id);
      if (checkbox.checked) state.stockBatchSelected.add(key);
      else state.stockBatchSelected.delete(key);
      renderStockBatchDialog();
    });
    const details = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = technician.technician_name;
    const stock = document.createElement("small");
    stock.textContent = technician.stock_name || "Estoque sem nome";
    details.append(name, stock);
    const id = document.createElement("span");
    id.className = "stock-batch-id";
    id.textContent = `#${technician.stock_id}`;
    label.append(checkbox, details, id);
    return label;
  });
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "stock-batch-empty";
    empty.textContent = "Nenhum tecnico corresponde a pesquisa.";
    rows.push(empty);
  }
  elements.stockBatchList.replaceChildren(...rows);
  const count = state.stockBatchSelected.size;
  elements.stockBatchCount.textContent = `${count} ${count === 1 ? "selecionado" : "selecionados"
    }`;
  elements.stockBatchPdf.disabled = state.stockBatchLoading || count === 0;
  elements.stockBatchPrint.disabled = state.stockBatchLoading || count === 0;
  elements.stockBatchSelectVisible.disabled =
    state.stockBatchLoading || technicians.length === 0;
  elements.stockBatchClear.disabled = state.stockBatchLoading || count === 0;
  elements.stockBatchSearch.disabled = state.stockBatchLoading;
  elements.stockBatchIncludeZero.disabled = state.stockBatchLoading;
  elements.stockBatchIncludeSerials.disabled = state.stockBatchLoading;
  elements.stockBatchStatus.classList.toggle("hidden", !state.stockBatchLoading);
  if (state.stockBatchLoading) {
    elements.stockBatchStatus.textContent =
      `Consultando ${count} tecnico${count === 1 ? "" : "s"}. Nao feche o painel.`;
  }
}

function openStockBatchDialog() {
  if (!state.stockTechnicians.length || state.stockBatchLoading) return;
  if (!state.stockBatchSelected.size && state.stockSelectedId) {
    state.stockBatchSelected.add(state.stockSelectedId);
  }
  elements.stockBatchSearch.value = "";
  elements.stockBatchIncludeZero.checked = elements.stockShowZero.checked;
  elements.stockBatchIncludeSerials.checked = true;
  elements.stockBatchDialog.showModal();
  renderStockBatchDialog({ force: true });
}

function selectedStockIds() {
  return [...state.stockBatchSelected]
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function stockBatchRequestBody(stockIds) {
  return {
    stock_ids: stockIds,
    include_zero: elements.stockBatchIncludeZero.checked,
    include_serials: elements.stockBatchIncludeSerials.checked,
  };
}

async function generateStockPdf(stockIds, { individual = false } = {}) {
  if (!stockIds.length || state.stockBatchLoading) return;
  const downloadButton = individual ? elements.stockPdf : elements.stockBatchPdf;
  setDownloadMotion(downloadButton, "running");
  state.stockBatchLoading = true;
  renderStock();
  try {
    const body = individual
      ? {
        stock_ids: stockIds,
        include_zero: elements.stockShowZero.checked,
        include_serials: true,
      }
      : stockBatchRequestBody(stockIds);
    const result = await requestBlob(apiUrl("/api/stock/pdf/batch"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: 1800000,
    });
    saveBlob(result.blob, result.filename);
    setDownloadMotion(downloadButton, "complete");
    showToast(
      individual
        ? "PDF do tecnico gerado."
        : `PDF unico gerado para ${stockIds.length} tecnicos.`,
      "success",
    );
    if (!individual) elements.stockBatchDialog.close();
  } catch (error) {
    setDownloadMotion(downloadButton, "idle");
    showToast(error.message, "error");
    console.error("Falha ao gerar PDF de estoque", error);
  } finally {
    state.stockBatchLoading = false;
    renderStock();
  }
}

function printableStockHtml(stocks, { includeZero, includeSerials }) {
  const generatedAt = new Date().toLocaleString("pt-BR");
  const sections = stocks.map((stock, index) => {
    const technician = stock.technician || {};
    const summary = stock.summary || {};
    const items = (stock.items || []).filter(
      (item) => includeZero || Number(item.quantity || 0) > 0,
    );
    const rows = items.map((item) => {
      const serials = (item.serials || []).map((serial) => {
        const smart = serial.smart
          ? ` / SMART ${escapeHtml(serial.smart)}` : "";
        return `<div>${escapeHtml(serial.serial)}${smart}</div>`;
      }).join("") || "-";
      return `<tr>
        <td>${escapeHtml(item.group)}</td>
        <td class="code">${escapeHtml(item.code)}</td>
        <td>${escapeHtml(item.equipment)}</td>
        <td>${escapeHtml(item.brand || "-")}</td>
        <td class="quantity">${escapeHtml(item.quantity_label || item.quantity || "0")}</td>
        ${includeSerials ? `<td class="serials">${serials}</td>` : ""}
      </tr>`;
    }).join("") || `<tr><td colspan="${includeSerials ? 6 : 5
      }" class="empty">Nenhum item encontrado.</td></tr>`;
    const profileLabel = state.profiles.find(
      (item) => item.key === state.profile,
    )?.label || state.profile;
    return `<section class="stock-report ${index === stocks.length - 1 ? "last" : ""
      }">
      <header>
        <div>
          <h1>Relatorio de estoque do tecnico</h1>
          <h2>${escapeHtml(technician.technician_name || technician.stock_name || "Tecnico")}</h2>
          <p>Estoque: ${escapeHtml(technician.stock_name || "-")} | ID: ${escapeHtml(technician.stock_id || "-")}</p>
        </div>
        <div class="meta"><strong>${escapeHtml(profileLabel)}</strong><br>Gerado em ${escapeHtml(generatedAt)}</div>
      </header>
      <div class="summary">
        <div><span>Itens com saldo</span><strong>${escapeHtml(summary.positive_item_count || 0)}</strong></div>
        <div><span>Quantidade total</span><strong>${escapeHtml(summary.quantity_total || 0)}</strong></div>
        <div><span>Seriais</span><strong>${escapeHtml(summary.serial_count || 0)}</strong></div>
        <div><span>Grupos</span><strong>${escapeHtml(summary.group_count || 0)}</strong></div>
      </div>
      <table>
        <thead><tr><th>Grupo</th><th>Codigo</th><th>Equipamento</th><th>Marca</th><th>Saldo</th>${includeSerials ? "<th>Seriais</th>" : ""
      }</tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <footer>Consulta somente leitura - DOMINIUM</footer>
    </section>`;
  }).join("");
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Impressao de estoques</title><style>
    @page { size: A4 landscape; margin: 10mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #182633; font-family: Arial, sans-serif; font-size: 9px; }
    .stock-report { break-after: page; page-break-after: always; }
    .stock-report.last { break-after: auto; page-break-after: auto; }
    header { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 10px; }
    h1 { margin: 0 0 5px; font-size: 17px; text-transform: uppercase; }
    h2 { margin: 0 0 3px; font-size: 14px; }
    p { margin: 0; }
    .meta { text-align: right; line-height: 1.45; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 10px 0; }
    .summary div { padding: 7px 9px; border: 1px solid #c9d1d7; background: #f3f5f6; }
    .summary span { display: block; color: #5e6b76; font-size: 8px; }
    .summary strong { display: block; margin-top: 2px; font-size: 14px; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    thead { display: table-header-group; }
    th, td { padding: 5px 6px; border: 1px solid #cbd2d8; vertical-align: top; overflow-wrap: anywhere; }
    th { background: #e7ebee; text-align: left; font-size: 8px; }
    th:nth-child(1) { width: 13%; } th:nth-child(2) { width: 10%; }
    th:nth-child(3) { width: ${includeSerials ? "29%" : "48%"}; } th:nth-child(4) { width: 13%; }
    th:nth-child(5) { width: 8%; } ${includeSerials ? "th:nth-child(6) { width: 27%; }" : ""}
    tr { break-inside: avoid; page-break-inside: avoid; }
    .code { font-family: Consolas, monospace; font-weight: bold; }
    .quantity { text-align: center; font-weight: bold; }
    .serials div { margin-bottom: 2px; font-family: Consolas, monospace; font-size: 8px; }
    .empty { padding: 18px; text-align: center; }
    footer { margin-top: 8px; color: #66737e; font-size: 8px; }
  </style></head><body>${sections}</body></html>`;
}

async function printSelectedStocks() {
  const stockIds = selectedStockIds();
  if (!stockIds.length || state.stockBatchLoading) return;
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    showToast(
      "O navegador bloqueou a janela de impressao. Permita pop-ups para este painel.",
      "error",
    );
    return;
  }
  printWindow.document.write(
    "<!doctype html><title>Preparando impressao</title>"
    + "<p style='font-family:Arial;padding:30px'>"
    + "Consultando os estoques selecionados...</p>",
  );
  printWindow.document.close();
  state.stockBatchLoading = true;
  renderStock();
  try {
    const body = stockBatchRequestBody(stockIds);
    const payload = await request(apiUrl("/api/stock/batch"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: 1800000,
    });
    printWindow.document.open();
    printWindow.document.write(printableStockHtml(payload.stocks || [], {
      includeZero: body.include_zero,
      includeSerials: body.include_serials,
    }));
    printWindow.document.close();
    setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 500);
    showToast(
      `Impressao preparada para ${stockIds.length} tecnicos.`,
      "success",
    );
    elements.stockBatchDialog.close();
  } catch (error) {
    printWindow.close();
    showToast(error.message, "error");
    console.error("Falha ao preparar impressao de estoque", error);
  } finally {
    state.stockBatchLoading = false;
    renderStock();
  }
}

function filteredBulkTechnicians() {
  const term = normalize(elements.bulkTechnicianSearch.value.trim());
  if (!term) return state.stockTechnicians;
  return state.stockTechnicians.filter((technician) =>
    normalize(
      `${technician.technician_name} ${technician.stock_name} ${technician.installer_id}`,
    ).includes(term),
  );
}

function renderBulkTechnicians() {
  const current = elements.bulkTechnicianSelect.value;
  const options = [new Option(
    state.stockTechniciansLoading
      ? "Carregando tecnicos..."
      : state.stockTechnicians.length
        ? "Selecione um tecnico"
        : "Nenhum tecnico encontrado",
    "",
  )];
  filteredBulkTechnicians().forEach((technician) => {
    options.push(new Option(
      stockTechnicianLabel(technician),
      String(technician.installer_id),
    ));
  });
  elements.bulkTechnicianSelect.replaceChildren(...options);
  if (
    [...elements.bulkTechnicianSelect.options]
      .some((option) => option.value === current)
  ) {
    elements.bulkTechnicianSelect.value = current;
  }
  elements.bulkTechnicianSelect.disabled = state.stockTechniciansLoading
    || state.bulkCreateLoading || !state.nativeCreationEnabled;
  elements.bulkTechnicianSearch.disabled = state.stockTechniciansLoading
    || state.bulkCreateLoading || !state.nativeCreationEnabled;
}

function selectedBulkTechnician() {
  const installerId = Number(elements.bulkTechnicianSelect.value);
  return state.stockTechnicians.find(
    (technician) => Number(technician.installer_id) === installerId,
  ) || null;
}

function bulkContractValues() {
  const candidates = elements.bulkContracts.value.trim().split(/[\s,;]+/);
  const contracts = [];
  const invalid = [];
  const seen = new Set();
  candidates.forEach((value) => {
    const contract = value.trim();
    if (!contract) return;
    if (!/^\d{7}$/.test(contract)) {
      invalid.push(contract);
      return;
    }
    if (!seen.has(contract)) {
      seen.add(contract);
      contracts.push(contract);
    }
  });
  return { contracts, invalid };
}

function bulkResultRow(order) {
  const row = document.createElement("tr");
  const satisfied = Boolean(order.imported || order.already_existed);
  row.classList.toggle("bulk-created", satisfied);
  row.classList.toggle("bulk-not-created", !satisfied);
  [
    order.contract,
    order.os_number,
    order.technician,
    order.os_type,
    order.import_status || "SEM RESULTADO",
  ].forEach((value) => {
    const cell = document.createElement("td");
    cell.textContent = String(value || "-");
    row.append(cell);
  });
  const action = document.createElement("td");
  action.className = "action-cell";
  if (satisfied && order.os_number) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button secondary compact";
    button.textContent = "Preparar baixa";
    button.addEventListener("click", () => prepareCreatedOrderClose(
      order,
      state.bulkCreateResult?.close_code,
    ));
    action.append(button);
  } else {
    action.textContent = "-";
  }
  row.append(action);
  return row;
}

function creationFailureReasons(result, limit = 3) {
  const rows = Array.isArray(result?.orders) ? result.orders : [];
  const reasons = [];
  rows.forEach((row) => {
    if (row.imported || row.already_existed) return;
    const status = String(row.import_status || "").trim();
    if (status && !reasons.includes(status)) reasons.push(status);
  });
  return reasons.slice(0, limit);
}

async function prepareCreatedOrderClose(order, requestedCode) {
  const definition = state.closeCodes.find(
    (item) => item.code === String(requestedCode || ""),
  );
  if (!definition) {
    showToast("Selecione um codigo de baixa valido.", "error");
    return;
  }
  await loadOrders();
  const match = state.orders.find((candidate) =>
    String(candidate.num_os) === String(order.os_number)
    && String(candidate.contract) === String(order.contract)
  );
  if (!match) {
    showToast(
      `A OS ${order.os_number} ainda nao apareceu na lista de hoje.`,
      "error",
    );
    return;
  }
  state.closeCode = definition.code;
  setModule("close");
  selectCloseWorkspaceOrder(match.id_os);
  showToast(
    `OS ${match.num_os} preparada com o codigo ${definition.code}.`,
    "success",
  );
}

function renderBulkCreate() {
  renderBulkTechnicians();
  elements.bulkCreateDate.value = localDate();
  const { contracts, invalid } = bulkContractValues();
  const service = elements.bulkService.value.trim();
  const serviceSupported = state.nativeCreationServices.includes(service.toUpperCase());
  const closeCodeSupported = Boolean(closeDefinition(elements.bulkCloseCode.value));
  elements.bulkContractCount.textContent = invalid.length
    ? `${contracts.length} / ${invalid.length} invalidos`
    : String(contracts.length);
  elements.bulkContractCount.classList.toggle("invalid", invalid.length > 0);
  const uncertain = Boolean(state.bulkCreateResult?.uncertain);
  elements.bulkCreateReview.disabled = state.bulkCreateLoading
    || state.stockTechniciansLoading || !state.nativeCreationEnabled || uncertain
    || !selectedBulkTechnician() || !serviceSupported
    || !closeCodeSupported || !contracts.length || invalid.length > 0;
  elements.bulkCreateReview.textContent = state.bulkCreateLoading
    ? "Criando ordens..." : "Revisar criacao";
  elements.bulkContracts.disabled = state.bulkCreateLoading || !state.nativeCreationEnabled;
  elements.bulkService.disabled = state.bulkCreateLoading || !state.nativeCreationEnabled;
  elements.bulkCloseCode.disabled = state.bulkCreateLoading || !state.nativeCreationEnabled;
  elements.bulkCreateLoading.classList.toggle("hidden", !state.bulkCreateLoading);

  const result = state.bulkCreateResult;
  const rows = Array.isArray(result?.orders) ? result.orders : [];
  elements.bulkCreateBody.replaceChildren(...rows.map(bulkResultRow));
  elements.bulkCreateEmpty.classList.toggle(
    "hidden", state.bulkCreateLoading || rows.length > 0,
  );
  elements.bulkCreateResult.classList.toggle("hidden", !result);
  const failures = creationFailureReasons(result);
  const hasFailures = Boolean(result && (
    !result.ok || Number(result.not_imported || 0) > 0
  ));
  elements.bulkCreateResult.classList.toggle("error", hasFailures);
  if (result) {
    if (result.ok) {
      elements.bulkCreateResultTitle.textContent = hasFailures
        ? "Criacao concluida com rejeicoes" : "Criacao finalizada";
      const totals =
        `${result.imported || 0} criadas; ${result.already_existing || 0} ja existentes; `
        + `${result.not_imported || 0} nao criadas`;
      elements.bulkCreateResultDetail.textContent = failures.length
        ? `${totals}. Motivo: ${failures.join(" | ")}`
        : totals;
    } else {
      elements.bulkCreateResultTitle.textContent = result.uncertain
        ? "Resultado precisa ser conferido" : "Criacao nao concluida";
      elements.bulkCreateResultDetail.textContent = result.error
        || failures.join(" | ") || "Falha nao informada";
    }
  }
}

function openBulkCreateDialog() {
  const { contracts, invalid } = bulkContractValues();
  const technician = selectedBulkTechnician();
  const service = elements.bulkService.value.trim().toUpperCase();
  const definition = closeDefinition(elements.bulkCloseCode.value);
  if (
    state.bulkCreateLoading || invalid.length || !contracts.length
    || !technician || !state.nativeCreationServices.includes(service) || !definition
  ) return;
  elements.bulkConfirmTechnician.textContent = technician.technician_name;
  elements.bulkConfirmClient.textContent = state.profile === "natal"
    ? "CLIENTE 123" : "Cadastro do contrato";
  elements.bulkConfirmCount.textContent = String(contracts.length);
  elements.bulkConfirmService.textContent = service;
  elements.bulkConfirmCloseCode.textContent =
    `${definition.code} - ${definition.description}`;
  elements.bulkCreateDialog.showModal();
}

async function createBulkOrders() {
  const { contracts, invalid } = bulkContractValues();
  const technician = selectedBulkTechnician();
  const service = elements.bulkService.value.trim().toUpperCase();
  const definition = closeDefinition(elements.bulkCloseCode.value);
  if (
    state.bulkCreateLoading || invalid.length || !contracts.length
    || !technician || !state.nativeCreationServices.includes(service) || !definition
  ) return;

  state.bulkCreateLoading = true;
  state.bulkCreateResult = null;
  state.bulkCreateRequestId = state.bulkCreateRequestId
    || (globalThis.crypto?.randomUUID?.() ?? `bulk-${Date.now()}-${contracts.length}`);
  render();
  try {
    const result = await request(apiUrl("/api/orders/bulk-create"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: state.bulkCreateRequestId,
        confirmed: true,
        technician_id: technician.installer_id,
        technician: technician.technician_name,
        service,
        contracts,
        client_mode: state.profile === "natal" ? "fixed_123" : "registered",
      }),
      timeoutMs: 300000,
    });
    result.close_code = elements.bulkCloseCode.value;
    state.bulkCreateResult = result;
    state.bulkCreateRequestId = null;
    const failures = creationFailureReasons(result, 1);
    showToast(
      failures.length
        ? failures[0]
        : `${result.imported || 0} OS criadas; `
        + `${result.already_existing || 0} ja existentes; `
        + `${result.not_imported || 0} nao criadas.`,
      result.not_imported ? "error" : "success",
    );
  } catch (error) {
    state.bulkCreateResult = {
      ok: false,
      uncertain: Boolean(error.uncertain),
      error: error.message,
      orders: Array.isArray(error.payload?.orders) ? error.payload.orders : [],
      close_code: elements.bulkCloseCode.value,
    };
    if (!error.uncertain && error.status !== 409) {
      state.bulkCreateRequestId = null;
    }
    showToast(error.message, "error");
    console.error("Falha ao criar OS em massa", error);
  } finally {
    state.bulkCreateLoading = false;
    render();
  }
}

function setProgressWidth(element, value, maximum) {
  const percentage = maximum > 0 ? Math.min(100, Math.max(0, value / maximum * 100)) : 0;
  element.style.width = `${percentage}%`;
}

function renderDashboard() {
  const total = state.orders.length;
  const field = state.orders.filter((order) => normalize(order.status) === "EM CAMPO").length;
  const failures = state.failures.length;
  const selected = state.selected.size;
  const completed = state.completed;
  const scale = Math.max(total, selected, failures, completed, 1);

  elements.dashboardOpenCount.textContent = total;
  elements.dashboardFieldCount.textContent = field;
  elements.dashboardCompletedCount.textContent = completed;
  elements.dashboardFailureCount.textContent = failures;
  elements.dashboardTotalLabel.textContent = `${total} OS`;
  elements.dashboardFieldLabel.textContent = field;
  elements.dashboardSelectedLabel.textContent = selected;
  elements.dashboardFailureLabel.textContent = failures;
  elements.dashboardCompletedLabel.textContent = completed;
  elements.dashboardAttentionCount.textContent = `${failures} pendencia${failures === 1 ? "" : "s"}`;
  elements.dashboardUpdated.textContent = `Atualizado ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  setProgressWidth(elements.dashboardFieldBar, field, scale);
  setProgressWidth(elements.dashboardSelectedBar, selected, scale);
  setProgressWidth(elements.dashboardFailureBar, failures, scale);
  setProgressWidth(elements.dashboardCompletedBar, completed, scale);

  const cityCounts = new Map();
  state.orders.forEach((order) => {
    const city = String(order.city || "SEM CIDADE").trim().toUpperCase();
    cityCounts.set(city, (cityCounts.get(city) || 0) + 1);
  });
  const cities = [...cityCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const cityMaximum = Math.max(...cities.map((entry) => entry[1]), 1);
  elements.dashboardCityBars.innerHTML = cities.length
    ? cities.map(([city, count]) => `<div class="city-bar">
        <div><span>${escapeHtml(city)}</span><strong>${count}</strong></div>
        <div class="city-track"><i style="width:${Math.max(5, count / cityMaximum * 100)}%"></i></div>
      </div>`).join("")
    : '<div class="dashboard-empty">Nenhuma OS carregada nesta praca.</div>';

  elements.dashboardAttentionList.innerHTML = state.failures.length
    ? state.failures.slice(0, 5).map((failure) => `<button type="button" class="attention-row" data-failure-os="${escapeHtml(failure.num_os)}">
        <span><strong>OS ${escapeHtml(failure.num_os)}</strong><small>${escapeHtml(failure.service || "Servico nao informado")}</small></span>
        <b>${escapeHtml(failure.category_label || "Falha")}</b>
      </button>`).join("")
    : '<div class="dashboard-empty success-empty"><i data-lucide="circle-check-big"></i><span>Nenhuma falha pendente.</span></div>';
  elements.dashboardAttentionList.querySelectorAll("[data-failure-os]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeModule = "orders";
      state.activeView = "failures";
      updateAddress();
      render();
    });
  });

  elements.dashboardRecentBody.innerHTML = state.orders.slice(0, 8).map((order) => `<tr>
    <td class="os-number">${escapeHtml(order.num_os)}</td>
    <td>${escapeHtml(order.contract)}</td>
    <td class="service-name">${escapeHtml(order.service)}</td>
    <td>${escapeHtml(order.city || "-")}</td>
    <td>${escapeHtml(order.technician || "-")}</td>
    <td><span class="status-badge">${escapeHtml(order.status || "EM CAMPO")}</span></td>
  </tr>`).join("") || '<tr><td colspan="6" class="dashboard-empty-cell">Nenhuma ordem carregada.</td></tr>';

  if (globalThis.lucide) globalThis.lucide.createIcons();
}

function formatOperationalDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 60) return `${Math.round(value)}s`;
  const minutes = Math.floor(value / 60);
  const remainder = Math.round(value % 60);
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function renderHealthCheck() {
  const payload = state.healthCheck;
  elements.healthRefresh.disabled = state.healthLoading;
  elements.healthRefresh.classList.toggle("is-spinning", state.healthLoading);
  if (!payload) {
    elements.healthBaseGrid.innerHTML = `<div class="intelligence-empty">${state.healthLoading ? "Testando conectividade..." : "Teste ainda nao executado."}</div>`;
    elements.healthNavStatus.textContent = state.healthLoading ? "Testando bases" : "Bases e produtividade";
    return;
  }
  elements.healthNavStatus.textContent = payload.offline
    ? `${payload.offline} base${payload.offline === 1 ? "" : "s"} offline`
    : `${payload.online} bases online`;
  elements.healthNavStatus.dataset.tone = payload.offline ? "danger" : "success";
  elements.healthBaseGrid.innerHTML = (payload.bases || []).map((base) => `
    <article class="health-base ${base.online ? "online" : "offline"}">
      <span class="health-pulse" aria-hidden="true"></span>
      <div><strong>${escapeHtml(base.label)}</strong><small>${escapeHtml(base.host)}:${escapeHtml(base.port)}</small></div>
      <div class="health-latency"><b>${base.online ? `${escapeHtml(base.latency_ms)} ms` : "OFFLINE"}</b><small>${base.online ? "DataSnap respondeu" : escapeHtml(base.error || "Sem resposta")}</small></div>
    </article>
  `).join("");
  elements.healthCheckedAt.textContent = `${payload.cached ? "Leitura em cache" : "Teste direto"} · ${formatDateTime(payload.checked_at)}`;
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

function renderIntelligence() {
  const payload = state.intelligence;
  elements.intelligenceRefresh.disabled = state.intelligenceLoading;
  elements.intelligencePdf.disabled = state.intelligenceLoading;
  elements.intelligenceRefresh.classList.toggle("is-loading", state.intelligenceLoading);
  renderHealthCheck();
  if (!payload) return;
  const summary = payload.summary || {};
  const success = Number(summary.success_rate || 0);
  elements.intelligenceSuccessRate.textContent = `${success.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  elements.intelligenceScoreRing.style.setProperty("--score", `${Math.min(100, Math.max(0, success)) * 3.6}deg`);
  elements.intelligenceConfirmed.textContent = Number(summary.confirmed || 0).toLocaleString("pt-BR");
  elements.intelligenceProblems.textContent = Number(summary.failed || 0) + Number(summary.uncertain || 0);
  elements.intelligenceAverageTime.textContent = formatOperationalDuration(summary.average_confirmation_seconds);
  elements.intelligencePeriodLabel.textContent = payload.days === 1
    ? `Operacao de ${new Date(`${payload.end_date}T12:00:00`).toLocaleDateString("pt-BR")}`
    : `${payload.days} dias · ${new Date(`${payload.start_date}T12:00:00`).toLocaleDateString("pt-BR")} a ${new Date(`${payload.end_date}T12:00:00`).toLocaleDateString("pt-BR")}`;
  elements.intelligenceGenerated.textContent = `Atualizado ${formatDateTime(payload.generated_at)}`;

  elements.basePerformanceList.innerHTML = (payload.bases || []).map((base) => `
    <article class="base-performance-row">
      <div class="base-performance-title"><strong>${escapeHtml(base.label)}</strong><span>${escapeHtml(base.confirmed)} confirmadas · ${escapeHtml(base.failed + base.uncertain)} pendencias criticas</span></div>
      <div class="base-performance-track"><i style="width:${Math.max(2, Number(base.success_rate || 0))}%"></i></div>
      <b>${Number(base.success_rate || 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</b>
    </article>
  `).join("") || '<div class="intelligence-empty">Sem dados por base.</div>';

  const term = normalize(elements.intelligenceTechnicianSearch.value);
  const technicians = (payload.technicians || []).filter((item) => normalize(
    `${item.technician} ${(item.bases || []).join(" ")}`,
  ).includes(term));
  elements.intelligenceTechnicianBody.innerHTML = technicians.slice(0, 40).map((item, index) => `
    <tr>
      <td><span class="rank-number ${index < 3 ? "top" : ""}">${index + 1}</span></td>
      <td><strong>${escapeHtml(item.technician)}</strong></td>
      <td>${escapeHtml((item.bases || []).map((base) => base.toUpperCase()).join(" / ") || "-")}</td>
      <td class="metric-positive">${escapeHtml(item.confirmed)}</td>
      <td class="${item.failed || item.uncertain ? "metric-negative" : ""}">${escapeHtml(Number(item.failed || 0) + Number(item.uncertain || 0))}</td>
      <td><div class="rate-cell"><span><i style="width:${Math.max(2, Number(item.success_rate || 0))}%"></i></span><b>${Number(item.success_rate || 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</b></div></td>
      <td><span class="code-chip">${escapeHtml(item.top_code)}</span></td>
    </tr>
  `).join("");
  elements.intelligenceTechnicianEmpty.classList.toggle("hidden", technicians.length > 0);
}

function serialAuditStatusLabel(status) {
  return {
    mismatch: ["Divergencia", "danger"],
    not_found: ["Nao localizado", "warning"],
    expected_stock_missing: ["Tecnico sem estoque", "warning"],
    ok: ["Correto", "success"],
  }[status] || [status || "-", "neutral"];
}

function renderSerialAudit() {
  const payload = state.serialAudit;
  elements.serialAuditRun.disabled = state.serialAuditLoading;
  elements.serialAuditRun.querySelector("span").textContent = state.serialAuditLoading
    ? "Cruzando estoques..." : "Auditar seriais";
  if (!payload) return;
  const summary = payload.summary || {};
  elements.serialAuditSummary.classList.remove("hidden");
  elements.serialAuditSummary.innerHTML = `
    <span><b>${escapeHtml(summary.mismatch || 0)}</b> divergencias</span>
    <span><b>${escapeHtml(summary.not_found || 0)}</b> nao localizados</span>
    <span><b>${escapeHtml(summary.ok || 0)}</b> corretos</span>
    <small>${escapeHtml(payload.capture_count || 0)} atividades · ${escapeHtml(payload.serial_count || 0)} seriais</small>`;
  elements.serialAuditBody.innerHTML = (payload.rows || []).map((row) => {
    const [label, tone] = serialAuditStatusLabel(row.status);
    return `<tr class="serial-audit-row ${tone}">
      <td><span class="audit-status ${tone}">${escapeHtml(label)}</span></td>
      <td><strong class="serial-value">${escapeHtml(row.serial)}</strong></td>
      <td><strong>${escapeHtml((row.os_numbers || []).join(" / ") || "-")}</strong><small>${escapeHtml(row.contract)}</small></td>
      <td>${escapeHtml(row.expected_technician || "Nao identificado")}</td>
      <td>${escapeHtml(row.owner_technician || "Nao localizado")}<small>${escapeHtml(row.owner_stock || "")}</small></td>
      <td>${escapeHtml(row.equipment || "-")}<small>${escapeHtml(row.equipment_code || "")}</small></td>
    </tr>`;
  }).join("");
  elements.serialAuditEmpty.classList.toggle("hidden", (payload.rows || []).length > 0);
  if (!(payload.rows || []).length) {
    elements.serialAuditEmpty.textContent = payload.capture_count
      ? "Nenhum serial instalado foi encontrado nas capturas desta data."
      : "Nao ha captura do TOA para esta base e data.";
  }
}

async function loadIntelligence({ quiet = false } = {}) {
  if (state.intelligenceLoading) return;
  state.intelligenceLoading = true;
  renderIntelligence();
  try {
    state.intelligence = await request(
      `/api/intelligence?date=${encodeURIComponent(elements.intelligenceDate.value || localDate())}&days=${encodeURIComponent(elements.intelligenceDays.value || "7")}`,
      { timeoutMs: 20000 },
    );
  } catch (error) {
    if (!quiet) showToast(`Nao foi possivel montar a inteligencia: ${error.message}`, "error");
  } finally {
    state.intelligenceLoading = false;
    renderIntelligence();
  }
}

async function loadHealthCheck({ fresh = false, quiet = false } = {}) {
  if (state.healthLoading) return;
  state.healthLoading = true;
  renderHealthCheck();
  try {
    state.healthCheck = await request(`/api/health-check${fresh ? "?refresh=1" : ""}`, { timeoutMs: 20000 });
    if (fresh && !quiet) showToast(
      state.healthCheck.offline ? `${state.healthCheck.offline} base(s) sem resposta.` : "As quatro bases estao online.",
      state.healthCheck.offline ? "warning" : "success",
    );
  } catch (error) {
    if (!quiet) showToast(`Health check indisponivel: ${error.message}`, "error");
  } finally {
    state.healthLoading = false;
    renderHealthCheck();
  }
}

async function runSerialAudit() {
  if (state.serialAuditLoading) return;
  state.serialAuditLoading = true;
  renderSerialAudit();
  try {
    state.serialAudit = await request(apiUrl("/api/intelligence/serial-audit"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: elements.intelligenceDate.value || localDate() }),
      timeoutMs: 480000,
    });
    const mismatches = Number(state.serialAudit.summary?.mismatch || 0);
    showToast(mismatches ? `${mismatches} divergencia(s) de serial encontrada(s).` : "Auditoria concluida sem divergencias.", mismatches ? "warning" : "success");
  } catch (error) {
    showToast(`Auditoria de serial falhou: ${error.message}`, "error");
  } finally {
    state.serialAuditLoading = false;
    renderSerialAudit();
  }
}

function filteredCloseOrders() {
  const term = normalize(elements.closeQueueSearch.value.trim());
  if (!term) return state.orders;
  return state.orders.filter((order) => normalize(
    `${order.num_os} ${order.contract} ${order.service} ${order.technician} ${order.city}`,
  ).includes(term));
}

function selectedCloseWorkspaceOrder() {
  return state.orders.find((order) => order.id_os === state.closeWorkspaceOrderId) || null;
}

function selectCloseWorkspaceOrder(idOs) {
  state.closeWorkspaceOrderId = Number(idOs);
  const definition = closeDefinition(state.closeCode);
  elements.closeWorkspaceCode.value = definition?.code || "";
  elements.closeWorkspaceObservation.value = "";
  renderCloseWorkspace();
  verifyCloseOrderInstaller(Number(idOs), true);
}

async function verifyCloseOrderInstaller(idOs, force = false) {
  const key = String(Number(idOs));
  const previous = state.closeInstallerChecks[key];
  if (!force && (previous?.status === "loading" || previous?.status === "verified")) return;
  state.closeInstallerChecks[key] = { status: "loading", error: "" };
  renderCloseWorkspace();
  try {
    let result;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        result = await request(apiUrl(`/api/orders/${idOs}/installer`), { timeoutMs: 45000 });
        break;
      } catch (error) {
        if (error.status !== 409 || attempt === 2) throw error;
        await sleep((attempt + 1) * 1000);
      }
    }
    state.orders = state.orders.map((order) => Number(order.id_os) === Number(idOs)
      ? {
        ...order,
        technician: result.installer_name,
        installer_id: result.installer_id,
        technician_source: result.source,
      }
      : order);
    state.closeInstallerChecks[key] = { status: "verified", error: "" };
  } catch (error) {
    state.closeInstallerChecks[key] = { status: "error", error: error.message };
    showToast(`Nao foi possivel validar o tecnico da OS: ${error.message}`, "error");
    console.error("Falha ao validar instalador da OS", error);
  } finally {
    renderCloseWorkspace();
  }
}

function closeWorkspaceDefinition() {
  const code = elements.closeWorkspaceCode.value.trim();
  return state.closeCodes.find((item) => item.code === code) || null;
}

function renderCloseWorkspace() {
  const visible = filteredCloseOrders();
  const order = selectedCloseWorkspaceOrder();
  elements.closeQueueBadge.textContent = `${state.orders.length} aguardando`;
  elements.closeQueueCount.textContent = state.orders.length;
  elements.closeQueue.innerHTML = visible.map((item) => `<button type="button" class="close-queue-item ${item.id_os === order?.id_os ? "active" : ""}" data-close-order="${item.id_os}">
    <span><strong>OS ${escapeHtml(item.num_os)}</strong><em>CONTRATO ${escapeHtml(item.contract)}</em><b>${escapeHtml(item.service)}</b></span>
    <small>${escapeHtml(item.technician || item.city || item.contract)}</small>
  </button>`).join("") || '<div class="close-queue-empty">Nenhuma OS encontrada.</div>';
  elements.closeQueue.querySelectorAll("[data-close-order]").forEach((button) => {
    button.addEventListener("click", () => selectCloseWorkspaceOrder(button.dataset.closeOrder));
  });

  elements.closeDetailEmpty.classList.toggle("hidden", Boolean(order));
  if (!order) {
    elements.closeWorkspaceContinue.disabled = true;
    return;
  }
  let definition = closeWorkspaceDefinition();
  const pendingReport = activeCloseReportRecord(order.id_os);
  const retryReport = retryableCloseReportRecord(order.id_os);
  if (retryReport && retryReport.close_code !== definition?.code) {
    const retryDefinition = closeDefinition(retryReport.close_code);
    if (retryDefinition) {
      definition = retryDefinition;
      state.closeCode = retryDefinition.code;
      elements.closeWorkspaceCode.value = retryDefinition.code;
    }
  }
  elements.closeDetailEyebrow.textContent = `OS ${order.num_os} - CONTRATO ${order.contract}`;
  elements.closeDetailTitle.textContent = order.service || "Baixa de OS";
  elements.closeDetailStatus.textContent = order.status || "EM CAMPO";
  elements.closeDetailClient.textContent = order.client || order.customer || `CLIENTE - ${order.contract}`;
  elements.closeDetailLocation.textContent = [order.city, order.district].filter(Boolean).join(" / ") || order.address || "-";
  const installerCheck = state.closeInstallerChecks[String(order.id_os)];
  elements.closeDetailTechnician.textContent = installerCheck?.status === "loading"
    ? "VALIDANDO NO IMPERIUM..."
    : installerCheck?.status === "error"
      ? "NAO CONFIRMADO"
      : order.technician || "-";
  elements.closeWorkspaceDescription.value = definition?.description || "";
  const requiresObservation = Boolean(definition?.requiresObservation);
  elements.closeObservationField.classList.toggle("hidden", !requiresObservation);
  elements.closeWorkspaceObservation.disabled = !requiresObservation;
  elements.closeWorkspaceContinue.disabled = !definition || !state.closeEnabled || state.running
    || Boolean(pendingReport && !retryReport)
    || installerCheck?.status !== "verified"
    || (requiresObservation && !elements.closeWorkspaceObservation.value.trim());
  const code = definition?.code || "";
  const allowsInstalled = code === "706" || (code !== "430" && Boolean(definition?.productive));
  const allowsRemoved = code === "430" || (code !== "706" && Boolean(definition?.productive));
  elements.closeInstalledSummary.classList.toggle("disabled", !allowsInstalled);
  elements.closeRemovedSummary.classList.toggle("disabled", !allowsRemoved);
  elements.closeMovementRule.textContent = code === "430"
    ? "Somente retirada"
    : code === "706"
      ? "Entrega de chip"
      : definition?.productive
        ? "Instalacao, troca ou materiais"
        : definition ? "Sem movimentacao de estoque" : "Aguardando codigo";
  elements.closeWorkspaceContinue.querySelector("span").textContent = retryReport
    ? "Revisar nova tentativa"
    : pendingReport
      ? reportState(pendingReport) === "uncertain" ? "Baixa nao confirmada" : "Aguardando confirmacao"
      : definition?.productive ? "Editar e confirmar" : "Confirmar baixa";
  elements.closeTransport.disabled = state.running || Boolean(pendingReport && !retryReport);
}

function renderHistory() {
  const automationHistory = Array.isArray(state.toaAutomation?.history)
    ? state.toaAutomation.history : [];
  const activities = [];
  state.failures.slice(0, 12).forEach((failure) => activities.push({
    kind: "error",
    title: `Baixa nao concluida - OS ${failure.num_os}`,
    detail: failure.error || failure.category_label || "Falha no Imperium",
    time: failure.last_attempt_at,
  }));
  if (state.importAuditLoaded) {
    state.importAuditHistory.slice(0, 20).forEach((item) => {
      const total = Number(item.count || 0);
      const imported = Number(item.imported || 0);
      const failed = Number(item.not_imported || 0);
      const duration = Number(item.duration_seconds || 0);
      const filename = String(item.filename || item.target || "lote TOA");
      activities.push({
        kind: item.ok === false ? "error" : "import",
        title: `${item.ok === false ? "Importacao com falha" : "Importacao concluida"} - ${filename}`,
        detail: `${imported}/${total} OS importadas${failed ? `; ${failed} nao importadas` : ""}${duration ? `; ${duration.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}s` : ""}`,
        time: item.at,
      });
    });
  } else {
    automationHistory.slice(0, 10).forEach((item) => {
      const routes = Array.isArray(item.routes) ? item.routes : [];
      const imported = routes.reduce((total, route) => total + Number(route.imported || 0), 0);
      const routeErrors = routes.filter((route) => route.status === "erro").length;
      activities.push({
        kind: item.ok === false ? "error" : "import",
        title: `Importacao TOA - ${routes.length} rota${routes.length === 1 ? "" : "s"}`,
        detail: `${imported} OS importadas${routeErrors ? `; ${routeErrors} rota${routeErrors === 1 ? "" : "s"} com erro` : ""}`,
        time: item.completed_at || item.started_at,
      });
    });
  }
  if (state.completed) activities.unshift({
    kind: "success",
    title: `${state.completed} baixas concluidas nesta sessao`,
    detail: "Resultados confirmados pelo servidor do Imperium",
    time: new Date().toISOString(),
  });
  activities.sort((a, b) => new Date(b.time || 0) - new Date(a.time || 0));
  elements.historyDateLabel.textContent = new Date().toLocaleDateString("pt-BR");
  elements.historyLoadedCount.textContent = state.orders.length;
  elements.historyCompletedCount.textContent = state.completed;
  elements.historyFailureCount.textContent = state.failures.length;
  elements.historyImportCount.textContent = state.importAuditLoaded ? state.importAuditHistory.length : automationHistory.length;
  elements.historyList.innerHTML = activities.length
    ? activities.slice(0, 24).map((activity) => `<article class="history-entry ${activity.kind}">
        <div class="history-entry-icon"><i data-lucide="${activity.kind === "error" ? "triangle-alert" : activity.kind === "import" ? "upload" : "circle-check-big"}"></i></div>
        <div><strong>${escapeHtml(activity.title)}</strong><span>${escapeHtml(activity.detail)}</span></div>
        <time>${escapeHtml(activity.time ? formatDateTime(activity.time) : "Hoje")}</time>
      </article>`).join("")
    : '<div class="history-empty"><i data-lucide="history"></i><strong>Nenhuma atividade registrada nesta sessao.</strong></div>';
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

function renderImportAuditHistory() {
  if (!elements.historyImportAuditList) return;
  if (!elements.historyImportAuditDate.value) elements.historyImportAuditDate.value = localDate();
  elements.historyImportAuditRefresh.disabled = state.importAuditLoading;
  elements.historyImportAuditRefresh.classList.toggle("is-spinning", state.importAuditLoading);
  elements.historyImportAuditStatus.textContent = state.importAuditLoading
    ? "Lendo auditoria..."
    : state.importAuditLoaded
      ? `${state.importAuditHistory.length} registro(s)${state.importAuditMalformed ? ` ? ${state.importAuditMalformed} linha(s) ignorada(s)` : ""}`
      : "Historico gravado em disco";
  if (state.importAuditLoading && !state.importAuditLoaded) {
    elements.historyImportAuditList.innerHTML = '<div class="history-audit-empty">Carregando importacoes...</div>';
    return;
  }
  elements.historyImportAuditList.innerHTML = state.importAuditHistory.length
    ? state.importAuditHistory.slice(0, 20).map((item) => {
        const total = Number(item.count || 0);
        const imported = Number(item.imported || 0);
        const failed = Number(item.not_imported || 0);
        const duration = Number(item.duration_seconds || 0);
        const filename = String(item.filename || item.target || "lote TOA");
        const tone = item.ok === false ? "error" : failed ? "warning" : "success";
        const status = item.ok === false ? "Falha" : failed ? "Parcial" : "Concluida";
        return `<article class="history-audit-row ${tone}">
          <div class="history-audit-row-top"><strong>${escapeHtml(filename)}</strong><span>${escapeHtml(status)}</span></div>
          <small>${escapeHtml(formatDateTime(item.at))} ? ${escapeHtml(item.company || state.profile.toUpperCase())}</small>
          <div class="history-audit-row-stats"><span><b>${imported}</b> importadas</span><span><b>${failed}</b> falhas</span><span><b>${total}</b> total</span>${duration ? `<span><b>${duration.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}s</b></span>` : ""}</div>
          ${item.error ? `<p>${escapeHtml(item.error)}</p>` : ""}
        </article>`;
      }).join("")
    : '<div class="history-audit-empty">Nenhuma importacao persistida nesta data.</div>';
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function loadImportAuditHistory({ quiet = false } = {}) {
  if (state.importAuditLoading || !elements.historyImportAuditDate) return;
  if (!elements.historyImportAuditDate.value) elements.historyImportAuditDate.value = localDate();
  state.importAuditLoading = true;
  renderImportAuditHistory();
  try {
    const query = new URLSearchParams({
      profile: state.profile,
      date: elements.historyImportAuditDate.value,
      limit: "120",
    });
    const payload = await request(`/api/import-history?${query.toString()}`, { timeoutMs: 15000 });
    state.importAuditHistory = Array.isArray(payload.items) ? payload.items : [];
    state.importAuditMalformed = Number(payload.malformed || 0);
    state.importAuditLoaded = true;
    renderHistory();
  } catch (error) {
    if (!quiet) showToast(`Nao foi possivel carregar a auditoria de importacoes: ${error.message}`, "error");
    console.error("Falha ao carregar auditoria de importacoes", error);
  } finally {
    state.importAuditLoading = false;
    renderImportAuditHistory();
  }
}

function renderServerLogs() {
  elements.refreshServerLog.disabled = state.serverLogLoading;
  elements.refreshServerLog.querySelector("span").textContent = state.serverLogLoading
    ? "Atualizando" : "Atualizar";
  elements.serverLogStatus.textContent = state.serverLogLoading
    ? "Lendo painel.log"
    : state.serverLogUpdatedAt
      ? `Atualizado ${formatAutomationTime(state.serverLogUpdatedAt)}`
      : "Aguardando leitura";
  elements.serverLogOutput.textContent = state.serverLogs.length
    ? state.serverLogs.join("\n")
    : state.serverLogLoading ? "Carregando log..." : "Nenhum evento registrado.";
}

async function loadServerLogs({ quiet = false } = {}) {
  if (state.serverLogLoading) return;
  state.serverLogLoading = true;
  renderServerLogs();
  try {
    const payload = await request("/api/logs?limit=180", { timeoutMs: 15000 });
    state.serverLogs = Array.isArray(payload.lines) ? payload.lines : [];
    state.serverLogUpdatedAt = payload.updated_at || new Date().toISOString();
  } catch (error) {
    if (!quiet) showToast(error.message, "error");
    console.error("Falha ao carregar log do servidor", error);
  } finally {
    state.serverLogLoading = false;
    renderServerLogs();
    elements.serverLogOutput.scrollTop = elements.serverLogOutput.scrollHeight;
  }
}

function filteredManualTechnicians() {
  const term = normalize(elements.manualTechnicianSearch.value.trim());
  if (!term) return state.stockTechnicians;
  return state.stockTechnicians.filter((technician) => normalize(
    `${technician.technician_name} ${technician.stock_name} ${technician.installer_id}`,
  ).includes(term));
}

function renderManualCreate() {
  const current = elements.manualTechnicianSelect.value;
  const options = [new Option(
    state.stockTechniciansLoading ? "Carregando tecnicos..." : "Selecione um tecnico",
    "",
  )];
  filteredManualTechnicians().forEach((technician) => options.push(new Option(
    stockTechnicianLabel(technician),
    String(technician.installer_id),
  )));
  elements.manualTechnicianSelect.replaceChildren(...options);
  if ([...elements.manualTechnicianSelect.options].some((option) => option.value === current)) {
    elements.manualTechnicianSelect.value = current;
  }
  const contractValid = /^\d{7}$/.test(elements.manualContract.value.trim());
  const serviceValid = state.nativeCreationServices.includes(elements.manualService.value.trim().toUpperCase());
  const closeCodeValid = Boolean(closeDefinition(elements.manualCloseCode.value));
  elements.manualCreateReview.disabled = state.bulkCreateLoading || !state.nativeCreationEnabled
    || !elements.manualTechnicianSelect.value || !contractValid || !serviceValid
    || !closeCodeValid;
  elements.manualTechnicianSearch.disabled = state.stockTechniciansLoading || state.bulkCreateLoading;
  elements.manualTechnicianSelect.disabled = state.stockTechniciansLoading || state.bulkCreateLoading;
  elements.manualCloseCode.disabled = state.bulkCreateLoading
    || !state.nativeCreationEnabled;
}

function openManualCreateDialog() {
  if (elements.manualCreateReview.disabled) return;
  elements.bulkTechnicianSelect.value = elements.manualTechnicianSelect.value;
  elements.bulkService.value = elements.manualService.value.trim().toUpperCase();
  elements.bulkContracts.value = elements.manualContract.value.trim();
  elements.bulkCloseCode.value = elements.manualCloseCode.value;
  renderBulkCreate();
  openBulkCreateDialog();
}

function assignImportFile(file) {
  if (!file) return;
  if (!/\.(csv|zip)$/i.test(file.name)) {
    showToast("Selecione um arquivo CSV ou ZIP do TOA.", "error");
    return;
  }
  state.importFile = file;
  selectImportTargetForFile(file);
  state.importPreview = null;
  state.importResult = null;
  state.selectedImportOs = null;
  previewImportFile();
}

function monitorCellClass(column, row) {
  if (column.key === "status") return `monitor-status monitor-status-${row.route_state || row.status_kind || "pending"}`;
  if (column.key === "tec1") return `monitor-status monitor-status-${row.tec1_kind || "unknown"}`;
  return "";
}

function monitorBucketMatches(value) {
  const selectedBucket = elements.monitorBucket.value;
  if (selectedBucket === "all") return true;
  return String(value || "").split(" / ").some(
    (bucket) => bucket.trim() === selectedBucket,
  );
}

// =============================================================================
// TOA | MONITOR DE O.S., BUCKETS, ROTAS E MODO TV
// =============================================================================
function renderMonitorBucketOptions(buckets) {
  const current = elements.monitorBucket.value || "all";
  const options = [new Option("Todos os buckets", "all")];
  (Array.isArray(buckets) ? buckets : []).forEach((bucket) => {
    options.push(new Option(`${bucket.name} (${bucket.count})`, bucket.name));
  });
  elements.monitorBucket.replaceChildren(...options);
  elements.monitorBucket.value = options.some((option) => option.value === current)
    ? current : "all";
  elements.monitorBucket.disabled = options.length === 1;
}

function monitorFilteredRows(view) {
  const query = String(elements.monitorSearch.value || "").trim().toLocaleLowerCase("pt-BR");
  const status = elements.monitorStatus.value;
  return view.rows.filter((row) => {
    const matchesQuery = !query || Object.values(row).some((value) => (
      String(value ?? "").toLocaleLowerCase("pt-BR").includes(query)
    ));
    const matchesBucket = monitorBucketMatches(row.bucket);
    if (!matchesQuery || !matchesBucket || status === "all") {
      return matchesQuery && matchesBucket;
    }
    return row.status_kind === status;
  });
}

function routeActivityMatches(activity) {
  const query = String(elements.monitorSearch.value || "").trim().toLocaleLowerCase("pt-BR");
  const status = elements.monitorStatus.value;
  const searchable = [
    activity.os,
    activity.contract,
    activity.service,
    activity.technician,
    activity.city,
    activity.district,
    activity.node,
    activity.status,
    activity.bucket,
  ].join(" ").toLocaleLowerCase("pt-BR");
  if (query && !searchable.includes(query)) return false;
  if (!monitorBucketMatches(activity.bucket)) return false;
  return status === "all" || activity.status_kind === status;
}

function routeDetailMarkup(activity) {
  if (!activity) {
    return `
      <div class="route-detail-empty">
        <i data-lucide="mouse-pointer-click" aria-hidden="true"></i>
        <strong>Selecione uma atividade</strong>
        <span>Clique em uma faixa da rota para abrir os detalhes.</span>
      </div>
    `;
  }
  const alert = activity.alert ? `
    <div class="route-detail-alert ${escapeHtml(activity.alert.severity)}">
      <i data-lucide="triangle-alert" aria-hidden="true"></i>
      <div><strong>${escapeHtml(activity.alert.label)}</strong><span>${escapeHtml(activity.alert.detail)}</span></div>
    </div>
  ` : "";
  const facts = activity.is_auxiliary ? [
    ["Tecnico", activity.technician],
    ["Bucket", activity.bucket],
    ["Inicio / fim", `${activity.actual_start} - ${activity.actual_end}`],
    ["Duracao", activity.duration],
    ["Tipo", "Pausa operacional do TOA"],
  ] : [
    ["Tecnico", activity.technician],
    ["Bucket", activity.bucket],
    ["Contrato", activity.contract],
    ["Janela de servico", `${activity.window_start} - ${activity.window_end}`],
    ["Inicio / fim", `${activity.actual_start} - ${activity.actual_end}`],
    ["Duracao", activity.duration],
    ["Deslocamento", activity.travel_time],
    ["Cidade / node", `${activity.city} / ${activity.node}`],
    ["Area", activity.work_area],
    ["Codigo de baixa", activity.close_code],
    ["ID da atividade", activity.activity_id],
  ];
  if (activity.route_state === "suspended") {
    facts.splice(2, 0,
      ["Login TOA", activity.technician_login || "-"],
      ["Destino atual", [activity.reallocated_to, activity.reallocated_to_login].filter(Boolean).join(" / ") || "Aguardando nova alocacao"],
      ["Status atual", activity.current_status || "-"],
    );
  }
  return `
    <header class="route-detail-head">
      <div>
        <span class="route-detail-eyebrow">ATIVIDADE SELECIONADA</span>
        <h4>${activity.is_auxiliary ? "REFEICAO" : `OS ${escapeHtml(activity.os)}`}</h4>
        <p>${escapeHtml(activity.service)}</p>
      </div>
      <span class="route-detail-status ${escapeHtml(activity.route_state)}">${escapeHtml(activity.route_state_label)}</span>
    </header>
    ${alert}
    <dl class="route-detail-facts">
      ${facts.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "-")}</dd></div>`).join("")}
    </dl>
    <p class="route-detail-note">${activity.is_auxiliary
      ? "Pausa trazida do CSV do TOA; nao entra nas contagens de OS."
      : activity.route_state === "suspended"
        ? "Historico preservado: a faixa suspensa nao conta como pendencia e nao gera alerta de janela."
        : "O alerta de janela e uma leitura operacional do DOMINIUM, nao o TEC1 oficial."}</p>
  `;
}

function renderRouteConsole(consoleModel) {
  const visibleTechnicians = (consoleModel?.technicians || []).map((technician) => ({
    ...technician,
    activities: technician.activities.filter(routeActivityMatches),
  })).filter((technician) => technician.activities.length);
  const activities = [];
  visibleTechnicians.forEach((technician) => technician.activities.forEach((activity) => activities.push(activity)));
  if (!activities.length) {
    elements.monitorRouteConsole.innerHTML = '<div class="route-console-empty">Nenhuma atividade corresponde aos filtros atuais.</div>';
    return { rows: [], columns: [] };
  }

  const startHour = Number(consoleModel.startHour || 6);
  const endHour = Number(consoleModel.endHour || 22);
  const totalMinutes = Math.max(60, (endHour - startHour) * 60);
  const hours = [];
  for (let hour = startHour; hour <= endHour; hour += 1) hours.push(hour);
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nowLeft = ((nowMinutes - startHour * 60) / totalMinutes) * 100;
  const visibleAlerts = activities.filter((activity) => activity.alert);
  let activityIndex = 0;
  const activityMap = [];
  const rows = visibleTechnicians.map((technician) => {
    const blocks = technician.activities.map((activity) => {
      const index = activityIndex;
      activityIndex += 1;
      activityMap.push(activity);
      const rawStart = activity.start_minutes;
      const rawEnd = activity.end_minutes;
      const left = rawStart === null || rawStart === undefined
        ? 1
        : Math.max(0, Math.min(98, ((rawStart - startHour * 60) / totalMinutes) * 100));
      const width = rawStart === null || rawStart === undefined || rawEnd === null || rawEnd === undefined
        ? 9
        : Math.max(2.8, Math.min(100 - left, ((rawEnd - rawStart) / totalMinutes) * 100));
      const alertMark = activity.alert
        ? '<span class="route-activity-alert" aria-hidden="true">!</span>' : "";
      return `
        <button class="route-activity ${escapeHtml(activity.route_state)}${activity.alert ? ` has-alert ${escapeHtml(activity.alert.severity)}` : ""}"
          type="button" data-route-activity="${index}" style="left:${left.toFixed(3)}%;width:${width.toFixed(3)}%"
          title="${escapeHtml(activity.is_auxiliary
        ? `${activity.route_state_label} | ${activity.technician} | ${activity.timeline_start} - ${activity.timeline_end}`
        : `${activity.route_state_label} | OS ${activity.os} | ${activity.service}`)}">
          ${alertMark}<strong>${escapeHtml(activity.timeline_start || "--:--")}</strong><span>${escapeHtml(activity.service)}</span>
        </button>
      `;
    }).join("");
    const activeCount = technician.activities.filter((item) => item.route_state === "started").length;
    const mealCount = technician.activities.filter((item) => item.is_auxiliary).length;
    const suspendedCount = technician.activities.filter((item) => item.route_state === "suspended").length;
    const serviceCount = technician.activities.length - mealCount - suspendedCount;
    return `
      <div class="route-technician-row">
        <div class="route-technician">
          <span class="route-technician-avatar">${escapeHtml(technician.technician.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join(""))}</span>
          <div><strong>${escapeHtml(technician.technician)}</strong><small>${serviceCount} atendimento${serviceCount === 1 ? "" : "s"}${suspendedCount ? ` | ${suspendedCount} suspensa` : ""}${mealCount ? ` | ${mealCount} refeicao` : ""}${activeCount ? " | em atendimento" : ""}</small></div>
        </div>
        <div class="route-lane">
          ${nowLeft >= 0 && nowLeft <= 100 ? `<span class="route-now-line" style="left:${nowLeft.toFixed(3)}%"><i></i></span>` : ""}
          ${blocks}
        </div>
      </div>
    `;
  }).join("");

  const alertCards = visibleAlerts.length ? `
    <div class="route-smart-alerts" role="status" aria-live="polite">
      ${visibleAlerts.slice(0, 5).map((activity) => {
    const index = activityMap.indexOf(activity);
    return `<button type="button" data-route-activity="${index}" class="route-smart-alert ${escapeHtml(activity.alert.severity)}">
          <i data-lucide="triangle-alert" aria-hidden="true"></i>
          <span><strong>${escapeHtml(activity.alert.label)}</strong><small>OS ${escapeHtml(activity.os)} | ${escapeHtml(activity.technician)} | ${escapeHtml(activity.alert.detail)}</small></span>
          <i data-lucide="chevron-right" aria-hidden="true"></i>
        </button>`;
  }).join("")}
      ${visibleAlerts.length > 5 ? `<span class="route-alert-overflow">+${visibleAlerts.length - 5} alertas na lista</span>` : ""}
    </div>
  ` : '<div class="route-smart-clear"><i data-lucide="circle-check" aria-hidden="true"></i><span>Nenhuma janela em risco na visao atual.</span></div>';

  elements.monitorRouteConsole.innerHTML = `
    <div class="route-console-topbar">
      <div class="route-legend" aria-label="Legenda de situacoes">
        <span><i class="completed"></i>Concluida</span>
        <span><i class="started"></i>Iniciada</span>
        <span><i class="pending"></i>Pendente / em rota</span>
        <span><i class="suspended"></i>Suspensa / realocada</span>
        <span><i class="auxiliary"></i>Refeicao</span>
      </div>
      <span class="route-live-chip"><i></i>${state.monitorCsvSnapshot
      ? "Alertas recalculados agora; troque o CSV para atualizar os status"
      : "Leitura automatica a cada 20 segundos"}</span>
    </div>
    ${alertCards}
    <div class="route-console-layout">
      <div class="route-timeline-card">
        <div class="route-timeline-scroll">
          <div class="route-timeline" style="--route-hours:${endHour - startHour}">
            <div class="route-hours-row">
              <div class="route-resource-title">RECURSOS</div>
              <div class="route-hours">
                ${hours.map((hour) => `<span style="left:${(((hour - startHour) / (endHour - startHour)) * 100).toFixed(3)}%">${String(hour).padStart(2, "0")}</span>`).join("")}
              </div>
            </div>
            ${rows}
          </div>
        </div>
      </div>
      <aside class="route-detail" id="monitorRouteDetail">${routeDetailMarkup(visibleAlerts[0] || activities.find((item) => item.route_state === "started") || activities[0])}</aside>
    </div>
  `;
  elements.monitorRouteConsole.querySelectorAll("[data-route-activity]").forEach((button) => {
    button.addEventListener("click", () => {
      const activity = activityMap[Number(button.dataset.routeActivity)];
      const detail = elements.monitorRouteConsole.querySelector("#monitorRouteDetail");
      if (detail && activity) detail.innerHTML = routeDetailMarkup(activity);
      elements.monitorRouteConsole.querySelectorAll(".route-activity.selected").forEach((item) => item.classList.remove("selected"));
      const matchingBlock = elements.monitorRouteConsole.querySelector(`.route-activity[data-route-activity="${button.dataset.routeActivity}"]`);
      matchingBlock?.classList.add("selected");
      window.lucide?.createIcons();
    });
  });
  return {
    rows: activities.map((activity) => ({ ...activity })),
    columns: [
      { key: "os", label: "OS" },
      { key: "contract", label: "Contrato" },
      { key: "technician", label: "Tecnico" },
      { key: "bucket", label: "Bucket" },
      { key: "service", label: "Servico" },
      { key: "route_state_label", label: "Situacao" },
      { key: "window_start", label: "Inicio janela" },
      { key: "window_end", label: "Fim janela" },
      { key: "actual_start", label: "Inicio real" },
      { key: "actual_end", label: "Fim real" },
    ],
  };
}

async function loadMonitorCsvSnapshot({ quiet = false } = {}) {
  try {
    const payload = await request(apiUrl("/api/monitor/snapshot"), { timeoutMs: 30000 });
    state.monitorCsvSnapshot = payload.active && payload.snapshot
      ? payload.snapshot : null;
    if (state.monitorCsvSnapshot?.uploaded_at) {
      state.monitorLastUpdatedAt = state.monitorCsvSnapshot.uploaded_at;
    }
    if (state.activeModule === "monitor") renderOperationsMonitor();
    return Boolean(state.monitorCsvSnapshot);
  } catch (error) {
    state.monitorCsvSnapshot = null;
    if (!quiet) showToast(`Nao foi possivel abrir o retrato CSV: ${error.message}`, "error");
    return false;
  }
}

async function importMonitorCsv(selectedFiles) {
  const files = Array.from(selectedFiles || []).filter((file) => file?.name);
  if (!files.length || state.monitorCsvLoading) return;
  state.monitorCsvLoading = true;
  elements.monitorCsvOpen.disabled = true;
  elements.monitorCsvReplace.disabled = true;
  elements.monitorCsvOpen.classList.add("loading");
  elements.monitorCsvOpen.querySelector("span").textContent = files.length > 1
    ? `Lendo ${files.length} CSVs` : "Lendo CSV";
  try {
    const payload = await request(apiUrl("/api/monitor/snapshot"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        files: await Promise.all(files.map(async (file) => ({
          filename: file.name,
          content_base64: await fileAsBase64(file),
        }))),
      }),
      timeoutMs: 120000,
    });
    state.monitorDemoMode = false;
    state.monitorView = "routes";
    state.monitorAlerted.clear();
    elements.monitorSearch.value = "";
    elements.monitorBucket.value = "all";
    elements.monitorStatus.value = "all";
    if (payload.snapshot.profile !== state.profile) {
      await switchProfile(payload.snapshot.profile);
    } else {
      state.monitorCsvSnapshot = payload.snapshot;
      state.monitorLastUpdatedAt = payload.snapshot.uploaded_at || new Date().toISOString();
      renderOperationsMonitor();
    }
    const profileSummaries = Object.values(payload.profiles || {});
    const totalOrders = profileSummaries.reduce(
      (total, item) => total + Number(item.order_count || 0), 0,
    );
    const totalMeals = profileSummaries.reduce(
      (total, item) => total + Number(item.timeline_activity_count || 0), 0,
    );
    const destinationCount = profileSummaries.length || 1;
    showToast(
      `${files.length} CSV${files.length === 1 ? "" : "s"} separado${files.length === 1 ? "" : "s"} em ${destinationCount} base${destinationCount === 1 ? "" : "s"} | ${totalOrders || payload.snapshot.order_count} OS unicas${totalMeals ? ` | ${totalMeals} refeicoes` : ""}.`,
      "success",
    );
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.monitorCsvLoading = false;
    elements.monitorCsvInput.value = "";
    elements.monitorCsvOpen.disabled = false;
    elements.monitorCsvReplace.disabled = false;
    elements.monitorCsvOpen.classList.remove("loading");
    elements.monitorCsvOpen.querySelector("span").textContent = "Carregar CSV do TOA";
  }
}

async function clearMonitorCsvSnapshot() {
  if (state.monitorCsvLoading) return;
  state.monitorCsvLoading = true;
  elements.monitorCsvClear.disabled = true;
  try {
    await request(apiUrl("/api/monitor/snapshot/clear"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    state.monitorCsvSnapshot = null;
    state.monitorLastUpdatedAt = new Date().toISOString();
    state.monitorAlerted.clear();
    renderOperationsMonitor();
    showToast("Monitor voltou a usar a lista consultada no Imperium.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.monitorCsvLoading = false;
    elements.monitorCsvClear.disabled = false;
  }
}

function notifyMonitorAlerts(model) {
  if (model.isDemo || !state.monitorNotifications || typeof Notification === "undefined"
    || Notification.permission !== "granted") return;
  const revisits = model.views.revisits.rows;
  revisits.forEach((row) => {
    const key = `${row.os}:revisita`;
    if (state.monitorAlerted.has(key)) return;
    state.monitorAlerted.add(key);
    new Notification("DOMINIUM - Revisita identificada", {
      body: `OS ${row.os} | ${row.technician} | contrato ${row.contract}`,
      tag: `dominium-revisita-${row.os}`,
    });
  });
  const routeAlerts = model.views.routes?.console?.alerts || [];
  routeAlerts.forEach((alert) => {
    const key = `${alert.os}:${alert.key}`;
    if (state.monitorAlerted.has(key)) return;
    state.monitorAlerted.add(key);
    new Notification(
      alert.severity === "late" ? "DOMINIUM - Janela possivelmente perdida" : "DOMINIUM - Janela em risco",
      {
        body: `OS ${alert.os} | ${alert.technician} | ${alert.detail}`,
        tag: `dominium-rota-${alert.os}-${alert.key}`,
      },
    );
  });
}

const TEC1_VOICE_STORAGE_KEY = "dominium-tec1-voice-alerts-v1";

function loadTec1VoiceAlertKeys() {
  try {
    const values = JSON.parse(sessionStorage.getItem("dominium-tec1-voice-alerts-v1") || "[]");
    return new Set(Array.isArray(values) ? values.slice(-600) : []);
  } catch (_error) {
    return new Set();
  }
}

function persistTec1VoiceAlertKeys() {
  const values = [...state.monitorVoiceAlerted].slice(-600);
  sessionStorage.setItem(TEC1_VOICE_STORAGE_KEY, JSON.stringify(values));
}

function preferredPortugueseVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  const portuguese = voices.filter((voice) => /^pt(?:-|_)/i.test(voice.lang || ""));
  const score = (voice) => {
    const name = normalize(voice.name || "");
    return (name.includes("NATURAL") ? 100 : 0)
      + (name.includes("GOOGLE") ? 80 : 0)
      + (name.includes("FRANCISCA") ? 70 : 0)
      + (name.includes("ANTONIO") ? 65 : 0)
      + (name.includes("MICROSOFT") ? 50 : 0)
      + (/^pt-BR$/i.test(voice.lang || "") ? 30 : 0);
  };
  return portuguese.sort((a, b) => score(b) - score(a))[0] || null;
}

function speakTec1WithBrowser(spokenText, finish) {
  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    finish();
    return;
  }
  const utterance = new SpeechSynthesisUtterance(spokenText);
  utterance.lang = "pt-BR";
  utterance.rate = 0.94;
  utterance.pitch = 1;
  utterance.volume = 1;
  const voice = preferredPortugueseVoice();
  if (voice) utterance.voice = voice;
  utterance.onend = finish;
  utterance.onerror = finish;
  window.speechSynthesis.speak(utterance);
}

async function processTec1VoiceQueue() {
  if (!state.monitorVoiceEnabled || state.monitorVoiceSpeaking || !state.monitorVoiceQueue.length) return;
  const item = state.monitorVoiceQueue.shift();
  const spokenText = item.message
    ? window.DominiumMonitor.speechPronunciationText(item.message)
    : window.DominiumMonitor.buildTec1VoiceMessage(item);
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    state.monitorVoiceAbort = null;
    state.monitorVoiceAudio = null;
    if (state.monitorVoiceAudioUrl) URL.revokeObjectURL(state.monitorVoiceAudioUrl);
    state.monitorVoiceAudioUrl = "";
    state.monitorVoiceSpeaking = false;
    window.setTimeout(processTec1VoiceQueue, 350);
  };
  state.monitorVoiceSpeaking = true;
  const controller = new AbortController();
  state.monitorVoiceAbort = controller;
  try {
    const response = await fetch("/api/voice/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: spokenText,
        voice: "pt-BR-FranciscaNeural",
        rate: "-5%",
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Voz neural indisponível (${response.status})`);
    const blob = await response.blob();
    if (!blob.size) throw new Error("Voz neural não retornou áudio");
    if (!state.monitorVoiceEnabled) {
      finish();
      return;
    }
    const audioUrl = URL.createObjectURL(blob);
    const audio = new Audio(audioUrl);
    state.monitorVoiceAudioUrl = audioUrl;
    state.monitorVoiceAudio = audio;
    audio.onended = finish;
    audio.onerror = () => {
      if (state.monitorVoiceAudioUrl) URL.revokeObjectURL(state.monitorVoiceAudioUrl);
      state.monitorVoiceAudioUrl = "";
      state.monitorVoiceAudio = null;
      speakTec1WithBrowser(spokenText, finish);
    };
    await audio.play();
  } catch (error) {
    if (error?.name === "AbortError" || !state.monitorVoiceEnabled) {
      finish();
      return;
    }
    console.warn("Voz neural indisponível; usando voz local.", error);
    speakTec1WithBrowser(spokenText, finish);
  }
}

function notifyMonitorTec1Voice(model) {
  if (!state.monitorVoiceEnabled || model?.isDemo || !window.DominiumMonitor) return;
  if (state.monitorTvActive && state.monitorTvDemo) return;
  if (!state.monitorTvActive && state.activeModule !== "monitor") return;
  const rows = model?.views?.monitor?.rows || [];
  const alerts = window.DominiumMonitor.buildTec1ContractAlerts(rows);
  alerts.forEach((alert) => {
    if (state.monitorVoiceAlerted.has(alert.key) || state.monitorVoiceQueue.length >= 12) return;
    state.monitorVoiceAlerted.add(alert.key);
    state.monitorVoiceQueue.push(alert);
  });
  persistTec1VoiceAlertKeys();
  processTec1VoiceQueue();
}

function toggleMonitorVoiceAlerts() {
  if (state.monitorVoiceEnabled) {
    state.monitorVoiceEnabled = false;
    state.monitorVoiceQueue = [];
    state.monitorVoiceSpeaking = false;
    state.monitorVoiceAbort?.abort?.();
    state.monitorVoiceAbort = null;
    if (state.monitorVoiceAudio) {
      state.monitorVoiceAudio.pause();
      state.monitorVoiceAudio.currentTime = 0;
    }
    state.monitorVoiceAudio = null;
    if (state.monitorVoiceAudioUrl) URL.revokeObjectURL(state.monitorVoiceAudioUrl);
    state.monitorVoiceAudioUrl = "";
    localStorage.removeItem("dominium-monitor-voice");
    window.speechSynthesis?.cancel?.();
    showToast("Avisos de voz do TEC1 desativados.");
  } else {
    state.monitorVoiceEnabled = true;
    localStorage.setItem("dominium-monitor-voice", "1");
    state.monitorVoiceQueue.unshift({ message: "Alertas de voz do téqui um ativados." });
    processTec1VoiceQueue();
    showToast("Voz neural gratuita ativada; voz local pronta como reserva.", "success");
  }
  renderOperationsMonitor();
  if (state.monitorTvActive) renderMonitorTv();
}

function buildMonitorAttentionPoints(model, { toaOnline, csvSnapshot } = {}) {
  const points = [];
  const routeAlerts = model.views.routes?.console?.alerts || [];
  routeAlerts.forEach((alert) => {
    const critical = alert.severity === "late";
    points.push({
      id: `route:${alert.os}:${alert.key}`,
      priority: critical ? 100 : 80,
      severity: critical ? "critical" : "risk",
      icon: critical ? "siren" : "timer",
      eyebrow: critical ? "AÇÃO IMEDIATA" : "JANELA EM RISCO",
      title: alert.label,
      description: `OS ${alert.os} com ${alert.technician}. ${alert.detail}.`,
      meta: [
        ["OS", alert.os],
        ["Técnico", alert.technician],
        ["Bucket", alert.bucket || "-"],
        ["Serviço", alert.service || "-"],
      ],
      actionLabel: "Abrir na Console de Rotas",
      view: "routes",
      search: alert.os,
    });
  });

  if (!model.isDemo && !csvSnapshot && !toaOnline) {
    points.push({
      id: "source:toa-offline",
      priority: 95,
      severity: "critical",
      icon: "cloud-off",
      eyebrow: "FONTE DE DADOS",
      title: "TOA desconectado — operação usando o último retrato",
      description: "Mudanças de rota, conclusão ou realocação podem ainda não ter chegado ao monitor.",
      meta: [["Situação", "Sem leitura ao vivo"], ["Ação", "Reconectar e atualizar"]],
      actionLabel: "Tentar atualizar agora",
      action: "refresh",
    });
  }

  const suspended = model.views.reallocations?.rows?.length || 0;
  if (suspended) {
    points.push({
      id: `suspended:${suspended}`,
      priority: 65,
      severity: "attention",
      icon: "shuffle",
      eyebrow: "REALOCAÇÃO",
      title: `${suspended} atividade${suspended === 1 ? " suspensa exige" : "s suspensas exigem"} acompanhamento`,
      description: "O histórico foi preservado; confira se todas já possuem técnico de destino.",
      meta: [["Suspensas", suspended], ["Leitura", "Destino atual e login TOA"]],
      actionLabel: "Ver suspensas e destinos",
      view: "reallocations",
    });
  }

  if (model.kpis.revisits) {
    points.push({
      id: `revisits:${model.kpis.revisits}`,
      priority: 58,
      severity: "attention",
      icon: "history",
      eyebrow: "QUALIDADE",
      title: `${model.kpis.revisits} revisita${model.kpis.revisits === 1 ? " identificada" : "s identificadas"}`,
      description: "Contratos com retorno dentro da regra de revisita precisam de análise do ofensor.",
      meta: [["Revisitas", model.kpis.revisits], ["Origem", "Histórico do contrato"]],
      actionLabel: "Analisar revisitas",
      view: "revisits",
    });
  }

  if (model.kpis.pending) {
    points.push({
      id: `pending:${model.kpis.pending}`,
      priority: 40,
      severity: "info",
      icon: "list-todo",
      eyebrow: "FILA OPERACIONAL",
      title: `${model.kpis.pending} OS aguardando ação ou desfecho`,
      description: "Priorize a fila pelas janelas mais próximas e pelos técnicos com maior carga.",
      meta: [["Pendentes", model.kpis.pending], ["Em campo", model.kpis.field]],
      actionLabel: "Abrir fila pendente",
      view: "pending",
    });
  }

  if (!points.length) {
    points.push({
      id: "operation:clear",
      priority: 0,
      severity: "safe",
      icon: "circle-check-big",
      eyebrow: "OPERAÇÃO MONITORADA",
      title: "Nenhum ponto crítico identificado agora",
      description: "O DOMINIUM continua acompanhando janelas, pendências e alterações da rota.",
      meta: [["Leitura", "Automática"], ["Alertas críticos", 0]],
      actionLabel: "Abrir Console de Rotas",
      view: "routes",
    });
  }
  return points.sort((a, b) => b.priority - a.priority).slice(0, 15);
}

function scheduleMonitorAttentionRotation() {
  if (state.monitorAttentionTimer) clearTimeout(state.monitorAttentionTimer);
  state.monitorAttentionTimer = null;
  if (
    state.activeModule !== "monitor" || state.monitorAttentionPaused
    || state.monitorAttentionPoints.length <= 1 || document.hidden
  ) return;
  state.monitorAttentionTimer = setTimeout(() => {
    state.monitorAttentionIndex = (state.monitorAttentionIndex + 1) % state.monitorAttentionPoints.length;
    renderMonitorAttentionStage();
  }, 6500);
}

function renderMonitorAttentionStage() {
  if (!elements.monitorAttentionStage) return;
  const points = state.monitorAttentionPoints || [];
  if (!points.length) {
    elements.monitorAttentionStage.className = "monitor-attention-stage hidden";
    scheduleMonitorAttentionRotation();
    return;
  }
  state.monitorAttentionIndex = Math.min(state.monitorAttentionIndex, points.length - 1);
  const point = points[state.monitorAttentionIndex];
  const total = points.length;
  elements.monitorAttentionStage.className = `monitor-attention-stage ${point.severity}${state.monitorAttentionPaused ? " paused" : ""}`;
  elements.monitorAttentionStage.innerHTML = `
    <div class="monitor-attention-glow" aria-hidden="true"></div>
    <div class="monitor-attention-icon"><i data-lucide="${escapeHtml(point.icon)}" aria-hidden="true"></i></div>
    <div class="monitor-attention-copy">
      <div class="monitor-attention-kicker"><span class="monitor-attention-pulse"></span>${escapeHtml(point.eyebrow)}</div>
      <h3>${escapeHtml(point.title)}</h3>
      <p>${escapeHtml(point.description)}</p>
      <div class="monitor-attention-meta">
        ${(point.meta || []).map(([label, value]) => `<span><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></span>`).join("")}
      </div>
    </div>
    <div class="monitor-attention-side">
      <span class="monitor-attention-count"><strong>${String(state.monitorAttentionIndex + 1).padStart(2, "0")}</strong> / ${String(total).padStart(2, "0")}</span>
      <button class="monitor-attention-action" type="button" data-attention-action>${escapeHtml(point.actionLabel)}</button>
      <div class="monitor-attention-controls" aria-label="Controles dos alertas">
        <button type="button" data-attention-prev title="Alerta anterior"><i data-lucide="chevron-left" aria-hidden="true"></i></button>
        <button type="button" data-attention-pause title="${state.monitorAttentionPaused ? "Retomar rotação" : "Pausar rotação"}"><i data-lucide="${state.monitorAttentionPaused ? "play" : "pause"}" aria-hidden="true"></i></button>
        <button type="button" data-attention-next title="Próximo alerta"><i data-lucide="chevron-right" aria-hidden="true"></i></button>
      </div>
    </div>
    <div class="monitor-attention-dots" aria-label="Pontos de atenção">
      ${points.map((item, index) => `<button type="button" data-attention-index="${index}" class="${index === state.monitorAttentionIndex ? "active" : ""}" aria-label="Mostrar alerta ${index + 1}: ${escapeHtml(item.title)}"></button>`).join("")}
    </div>
    <span class="monitor-attention-progress" aria-hidden="true"></span>
  `;
  const go = (offset) => {
    state.monitorAttentionIndex = (state.monitorAttentionIndex + offset + total) % total;
    renderMonitorAttentionStage();
  };
  elements.monitorAttentionStage.querySelector("[data-attention-prev]")?.addEventListener("click", () => go(-1));
  elements.monitorAttentionStage.querySelector("[data-attention-next]")?.addEventListener("click", () => go(1));
  elements.monitorAttentionStage.querySelector("[data-attention-pause]")?.addEventListener("click", () => {
    state.monitorAttentionPaused = !state.monitorAttentionPaused;
    renderMonitorAttentionStage();
  });
  elements.monitorAttentionStage.querySelectorAll("[data-attention-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.monitorAttentionIndex = Number(button.dataset.attentionIndex || 0);
      renderMonitorAttentionStage();
    });
  });
  elements.monitorAttentionStage.querySelector("[data-attention-action]")?.addEventListener("click", () => {
    if (point.action === "refresh") {
      elements.monitorRefresh.click();
      return;
    }
    if (point.view) state.monitorView = point.view;
    elements.monitorSearch.value = point.search || "";
    renderOperationsMonitor();
    elements.monitorTabs?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  });
  window.lucide?.createIcons();
  scheduleMonitorAttentionRotation();
}

function renderMonitorAttention(model, context) {
  const points = buildMonitorAttentionPoints(model, context);
  const signature = points.map((point) => point.id).join("|");
  if (signature !== state.monitorAttentionSignature) {
    state.monitorAttentionSignature = signature;
    state.monitorAttentionIndex = 0;
  }
  state.monitorAttentionPoints = points;
  renderMonitorAttentionStage();
}

function monitorTvProfileLabel() {
  const active = elements.profileTabs?.querySelector(".active");
  return String(active?.textContent || state.profile || "OPERAÇÃO").replace(/\s+/g, " ").trim().toUpperCase();
}

function monitorTvCountdown(deadline, now = new Date()) {
  if (!deadline) return { text: "SEM AGENDA", kind: "unknown" };
  const target = new Date(deadline);
  if (Number.isNaN(target.getTime())) return { text: "SEM AGENDA", kind: "unknown" };
  const seconds = Math.round((target.getTime() - now.getTime()) / 1000);
  const absolute = Math.abs(seconds);
  const hours = Math.floor(absolute / 3600);
  const minutes = Math.floor((absolute % 3600) / 60);
  const remainingSeconds = absolute % 60;
  const clock = [hours, minutes, remainingSeconds].map((value) => String(value).padStart(2, "0")).join(":");
  if (seconds < 0) return { text: `ESTOURADO +${clock}`, kind: "late" };
  if (seconds <= 3600) return { text: `FALTAM ${clock}`, kind: "risk" };
  return { text: `FALTAM ${clock}`, kind: "safe" };
}

function updateMonitorTvClock() {
  if (!state.monitorTvActive || !elements.monitorTv) return;
  const now = new Date();
  const clock = now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
  elements.monitorTv.querySelectorAll("[data-tv-clock]").forEach((item) => { item.textContent = clock; });
  elements.monitorTv.querySelectorAll("[data-tv-date]").forEach((item) => { item.textContent = date; });
  elements.monitorTv.querySelectorAll("[data-tv-deadline]").forEach((item) => {
    const countdown = monitorTvCountdown(item.dataset.tvDeadline, now);
    item.textContent = countdown.text;
    item.className = `monitor-tv-tec1-value ${countdown.kind}`;
  });
}

function monitorTvSourceOrders(now) {
  if (state.monitorTvDemo) {
    if (!Array.isArray(state.monitorTvDemoOrders)) {
      state.monitorTvDemoOrders = window.DominiumMonitor.buildMeetingExamples(now);
    }
    return state.monitorTvDemoOrders;
  }
  return Array.isArray(state.monitorCsvSnapshot?.orders) ? state.monitorCsvSnapshot.orders : state.orders;
}

function scheduleMonitorTvSlide(total) {
  if (state.monitorTvSlideTimer) clearTimeout(state.monitorTvSlideTimer);
  state.monitorTvSlideTimer = null;
  if (!state.monitorTvActive || state.monitorTvPaused || total <= 1 || document.hidden) return;
  state.monitorTvSlideTimer = setTimeout(() => {
    state.monitorTvSlideIndex = (state.monitorTvSlideIndex + 1) % total;
    renderMonitorTv();
  }, 8000);
}

function renderMonitorTv() {
  if (!state.monitorTvActive || !elements.monitorTv || !window.DominiumMonitor) return;
  const now = new Date();
  const sourceOrders = monitorTvSourceOrders(now);
  const model = window.DominiumMonitor.buildMonitorModel(sourceOrders, {
    now,
    selectedDate: elements.date.value || localDate(),
    timelineActivities: state.monitorTvDemo ? [] : state.monitorCsvSnapshot?.timeline_activities || [],
  });
  const tv = window.DominiumMonitor.buildTvDashboard(model);
  notifyMonitorTec1Voice(model);
  const slides = tv.tec1Rows.length ? tv.tec1Rows : [{
    os: "-", contract: "-", service: "Nenhuma atividade com agenda disponível",
    technician: "SEM INFORMAÇÃO", bucket: "-", status: "SEM AGENDA",
    schedule: "-", window_start: "-", window_end: "-", tec1_kind: "unknown",
    tec1_deadline: "", observation: "A API do TOA é necessária para atualização em tempo real.",
  }];
  state.monitorTvSlideIndex %= slides.length;
  const focus = slides[state.monitorTvSlideIndex];
  const countdown = monitorTvCountdown(focus.tec1_deadline, now);
  const sourceLabel = state.monitorTvDemo
    ? "DADOS DEMONSTRATIVOS"
    : state.monitorCsvSnapshot
      ? "RETRATO CSV DO TOA"
      : state.toaLiveStatus?.connected && state.toaLiveStatus?.authenticated
        ? "LEITURA CONECTADA" : "ÚLTIMO RETRATO DISPONÍVEL";
  const routeAlert = tv.routeAlerts[0];
  const updatedAt = state.monitorTvDemo
    ? "Cenário controlado para apresentação"
    : state.monitorLastUpdatedAt
      ? `Atualizado às ${new Date(state.monitorLastUpdatedAt).toLocaleTimeString("pt-BR")}`
      : "Aguardando atualização";
  elements.monitorTv.className = `monitor-tv ${state.monitorTvDemo ? "demo" : "live"}${state.monitorTvPaused ? " paused" : ""}`;
  elements.monitorTv.innerHTML = `
    <header class="monitor-tv-header">
      <div class="monitor-tv-brand">
        <span class="monitor-tv-logo"><img class="brand-asset" src="/assets/brands/technet-rings.svg" alt=""></span>
        <img class="monitor-tv-partner brand-asset" src="/assets/brands/claro-orb.png" alt="Claro">
        <div><strong>TECHNET · DOMINIUM</strong><small>Centro de Controle Operacional</small></div>
      </div>
      <div class="monitor-tv-context">
        <span>${escapeHtml(monitorTvProfileLabel())}</span>
        <strong class="${state.monitorTvDemo ? "demo" : "live"}"><i></i>${escapeHtml(sourceLabel)}</strong>
        <b class="api">API TOA · NECESSÁRIA</b>
      </div>
      <div class="monitor-tv-time"><strong data-tv-clock>${now.toLocaleTimeString("pt-BR")}</strong><span data-tv-date>${now.toLocaleDateString("pt-BR")}</span></div>
      <div class="monitor-tv-header-actions">
        <button type="button" data-theme-toggle title="Alternar tema"><i data-lucide="sun-moon" aria-hidden="true"></i><span data-theme-label>Tema</span></button>
        <button type="button" data-tv-voice class="${state.monitorVoiceEnabled ? "active" : ""}" title="${state.monitorVoiceEnabled ? "Desativar voz TEC1" : "Ativar voz TEC1"}"><i data-lucide="${state.monitorVoiceEnabled ? "volume-2" : "volume-x"}" aria-hidden="true"></i><span>${state.monitorVoiceEnabled ? "Voz ativa" : "Ativar voz"}</span></button>
        <button type="button" data-tv-source title="Alternar dados"><i data-lucide="database" aria-hidden="true"></i><span>${state.monitorTvDemo ? "Usar dados reais" : "Usar demonstração"}</span></button>
        <button type="button" data-tv-fullscreen title="Tela cheia"><i data-lucide="maximize" aria-hidden="true"></i></button>
        <button type="button" data-tv-exit title="Sair do modo TV"><i data-lucide="x" aria-hidden="true"></i></button>
      </div>
    </header>

    <section class="monitor-tv-kpis" aria-label="Indicadores operacionais">
      ${[
      ["Total de OS", tv.kpis.total || 0, "neutral"],
      ["Em campo", tv.kpis.field || 0, "green"],
      ["Concluídas", tv.kpis.completed || 0, "blue"],
      ["Pendentes", tv.kpis.pending || 0, "yellow"],
      ["TEC1 em atenção", tv.kpis.tec1Risk || 0, "red"],
      ["TEC1 estourado", tv.kpis.tec1Late || 0, "red"],
      ["Alertas de rota", tv.kpis.routeAlerts || 0, "orange"],
    ].map(([label, value, kind]) => `<article class="${kind}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join("")}
    </section>

    <main class="monitor-tv-main">
      <article class="monitor-tv-focus ${escapeHtml(countdown.kind)}">
        <div class="monitor-tv-focus-head">
          <div><span class="monitor-tv-focus-kicker"><i></i>TEC1 PRIORITÁRIO</span><small>Atividade ${state.monitorTvSlideIndex + 1} de ${slides.length}</small></div>
          <span class="monitor-tv-status ${escapeHtml(focus.tec1_kind || "unknown")}">${escapeHtml(focus.tec1 || focus.status || "Sem agenda")}</span>
        </div>
        <strong class="monitor-tv-tec1-value ${escapeHtml(countdown.kind)}" data-tv-deadline="${escapeHtml(focus.tec1_deadline || "")}">${escapeHtml(countdown.text)}</strong>
        <h1>${escapeHtml(focus.service || "Atividade sem tipo informado")}</h1>
        <div class="monitor-tv-focus-grid">
          ${[
      ["OS", focus.os], ["Contrato", focus.contract], ["Técnico", focus.technician], ["Login TOA", focus.technician_login],
      ["Bucket", focus.bucket], ["Status", focus.status], ["Agenda", focus.schedule],
      ["Janela", `${focus.window_start || "-"} — ${focus.window_end || "-"}`],
    ].map(([label, value]) => `<span><small>${escapeHtml(label)}</small><strong>${escapeHtml(value || "-")}</strong></span>`).join("")}
        </div>
        <div class="monitor-tv-observation"><i data-lucide="message-square-text" aria-hidden="true"></i><span><small>OBSERVAÇÃO DO TÉCNICO</small><strong>${escapeHtml(focus.observation || "Sem observação disponível")}</strong></span></div>
        <footer>
          <span><i data-lucide="info" aria-hidden="true"></i>Contagem operacional demonstrativa pelo fim da agenda.</span>
          <b>TEC1 oficial e eventos instantâneos dependem da API TOA.</b>
        </footer>
        <div class="monitor-tv-slide-controls">
          <button type="button" data-tv-prev aria-label="Anterior"><i data-lucide="chevron-left"></i></button>
          <button type="button" data-tv-pause aria-label="${state.monitorTvPaused ? "Retomar" : "Pausar"}"><i data-lucide="${state.monitorTvPaused ? "play" : "pause"}"></i></button>
          <div>${slides.map((_, index) => `<i class="${index === state.monitorTvSlideIndex ? "active" : ""}"></i>`).join("")}</div>
          <button type="button" data-tv-next aria-label="Próxima"><i data-lucide="chevron-right"></i></button>
        </div>
        <span class="monitor-tv-slide-progress"></span>
      </article>

      <aside class="monitor-tv-now">
        <header><span>OPERAÇÃO AGORA</span><strong>${tv.activeTechnicians.length} técnico${tv.activeTechnicians.length === 1 ? "" : "s"} em execução/rota</strong></header>
        <div class="monitor-tv-technicians">
          ${tv.activeTechnicians.length ? tv.activeTechnicians.slice(0, 3).map((item) => `
            <article><span class="avatar">${escapeHtml(item.technician.split(/\s+/).slice(0, 2).map((part) => part[0] || "").join(""))}</span><div><strong>${escapeHtml(item.technician)}</strong><small>OS ${escapeHtml(item.os)} · ${escapeHtml(item.service)}</small><b>${escapeHtml(item.state_label)} · ${escapeHtml(item.bucket)}</b></div></article>
          `).join("") : '<div class="monitor-tv-empty">Nenhum técnico iniciado na leitura atual.</div>'}
        </div>
        <article class="monitor-tv-next-tech">
          <div><span>PRÓXIMO TÉCNICO</span><b>DEPENDÊNCIA CRÍTICA</b></div>
          <strong>SEM INFORMAÇÃO</strong>
          <p>Precisamos da API do TOA para cruzar posição, deslocamento, rota e disponibilidade em tempo real.</p>
          <small><i data-lucide="lock-keyhole" aria-hidden="true"></i>Dado indisponível na exportação CSV</small>
        </article>
      </aside>
    </main>

    <section class="monitor-tv-api">
      <header><div><i data-lucide="plug-zap" aria-hidden="true"></i><span><strong>O QUE A API DO TOA DESBLOQUEIA</strong><small>Dados necessários para transformar o retrato em gestão ativa e preditiva</small></span></div><b>PRIORIDADE DE INTEGRAÇÃO</b></header>
      <div>${tv.missingApi.map((item) => `<article><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong><small><i data-lucide="circle-dashed" aria-hidden="true"></i>${escapeHtml(item.need)}</small></article>`).join("")}</div>
    </section>

    <footer class="monitor-tv-footer">
      <span class="monitor-tv-live"><i></i>Atualização visual automática</span>
      <div class="monitor-tv-ticker"><span>${routeAlert
      ? `ALERTA: OS ${escapeHtml(routeAlert.os)} · ${escapeHtml(routeAlert.technician)} · ${escapeHtml(routeAlert.detail)}`
      : "Nenhuma janela crítica identificada na leitura atual"} &nbsp; • &nbsp; API TOA necessária para técnico mais próximo, deslocamento real, TEC1 oficial e materiais.</span></div>
      <strong>${escapeHtml(updatedAt)}</strong>
    </footer>
  `;

  const move = (offset) => {
    state.monitorTvSlideIndex = (state.monitorTvSlideIndex + offset + slides.length) % slides.length;
    renderMonitorTv();
  };
  elements.monitorTv.querySelector("[data-tv-prev]")?.addEventListener("click", () => move(-1));
  elements.monitorTv.querySelector("[data-tv-next]")?.addEventListener("click", () => move(1));
  elements.monitorTv.querySelector("[data-tv-pause]")?.addEventListener("click", () => {
    state.monitorTvPaused = !state.monitorTvPaused;
    renderMonitorTv();
  });
  elements.monitorTv.querySelector("[data-tv-source]")?.addEventListener("click", () => {
    state.monitorTvDemo = !state.monitorTvDemo;
    state.monitorTvDemoOrders = state.monitorTvDemo ? window.DominiumMonitor.buildMeetingExamples(new Date()) : null;
    state.monitorTvSlideIndex = 0;
    renderMonitorTv();
  });
  elements.monitorTv.querySelector("[data-tv-voice]")?.addEventListener("click", toggleMonitorVoiceAlerts);
  elements.monitorTv.querySelector("[data-tv-fullscreen]")?.addEventListener("click", () => {
    elements.monitorTv.requestFullscreen?.().catch(() => { });
  });
  elements.monitorTv.querySelector("[data-tv-exit]")?.addEventListener("click", exitMonitorTv);
  syncThemeControls();
  window.lucide?.createIcons();
  updateMonitorTvClock();
  if (state.monitorTvClockTimer) clearInterval(state.monitorTvClockTimer);
  state.monitorTvClockTimer = setInterval(updateMonitorTvClock, 1000);
  scheduleMonitorTvSlide(slides.length);
}

function enterMonitorTv() {
  state.monitorTvActive = true;
  state.monitorTvDemo = true;
  state.monitorTvDemoOrders = window.DominiumMonitor.buildMeetingExamples(new Date());
  state.monitorTvSlideIndex = 0;
  state.monitorTvPaused = false;
  document.body.classList.add("monitor-tv-open");
  elements.monitorTv.classList.remove("hidden");
  renderMonitorTv();
  elements.monitorTv.requestFullscreen?.().catch(() => { });
}

function exitMonitorTv() {
  state.monitorTvActive = false;
  if (state.monitorTvSlideTimer) clearTimeout(state.monitorTvSlideTimer);
  if (state.monitorTvClockTimer) clearInterval(state.monitorTvClockTimer);
  state.monitorTvSlideTimer = null;
  state.monitorTvClockTimer = null;
  document.body.classList.remove("monitor-tv-open");
  elements.monitorTv.className = "monitor-tv hidden";
  elements.monitorTv.replaceChildren();
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => { });
}

function renderOperationsMonitor() {
  if (!elements.monitorWorkspace || !window.DominiumMonitor) return;
  const now = new Date();
  const csvSnapshot = state.monitorCsvSnapshot;
  const sourceOrders = state.monitorDemoMode
    ? window.DominiumMonitor.buildMeetingExamples(now)
    : Array.isArray(csvSnapshot?.orders)
      ? csvSnapshot.orders
      : state.orders;
  const model = window.DominiumMonitor.buildMonitorModel(sourceOrders, {
    now,
    selectedDate: elements.date.value || localDate(),
    timelineActivities: state.monitorDemoMode
      ? [] : csvSnapshot?.timeline_activities || [],
  });
  renderMonitorBucketOptions(model.buckets);
  elements.monitorTotal.textContent = model.kpis.total;
  elements.monitorField.textContent = model.kpis.field;
  elements.monitorCompleted.textContent = model.kpis.completed;
  elements.monitorPending.textContent = model.kpis.pending;
  elements.monitorRevisits.textContent = model.kpis.revisits;
  elements.monitorClosedWithCode.textContent = model.kpis.closedWithCode;
  elements.monitorRouteAlerts.textContent = model.kpis.routeAlerts;
  const toaOnline = Boolean(
    state.toaLiveStatus?.connected && state.toaLiveStatus?.authenticated,
  );
  const updatedAt = state.monitorLastUpdatedAt
    ? new Date(state.monitorLastUpdatedAt).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
    : "";
  elements.monitorFreshness.classList.toggle(
    "stale",
    !state.monitorDemoMode && !csvSnapshot && (state.monitorSnapshotStale || !toaOnline),
  );
  elements.monitorFreshness.classList.toggle(
    "csv",
    !state.monitorDemoMode && Boolean(csvSnapshot),
  );
  elements.monitorFreshness.textContent = state.monitorDemoMode
    ? "Cenarios de apresentacao ativos; dados reais permanecem preservados."
    : csvSnapshot
      ? `CSV do TOA ativo. Situacao importada${updatedAt ? ` as ${updatedAt}` : ""}; carregue um novo arquivo para atualizar.`
      : toaOnline && !state.monitorSnapshotStale
        ? `TOA conectado. Atualizacao automatica a cada 20s${updatedAt ? `; ultima as ${updatedAt}` : ""}.`
        : state.orders.length
          ? `TOA desconectado. Exibindo o ultimo retrato${updatedAt ? ` de ${updatedAt}` : ""}.`
          : "TOA desconectado. Aguardando um retrato da operacao.";
  renderMonitorAttention(model, { toaOnline, csvSnapshot });

  elements.monitorCsvSource.classList.toggle("hidden", !csvSnapshot);
  if (csvSnapshot) {
    elements.monitorCsvSourceTitle.textContent = csvSnapshot.filename || "Arquivo CSV do TOA";
    const excluded = Number(csvSnapshot.excluded_count || 0);
    elements.monitorCsvSourceDetail.textContent = [
      `${Number(csvSnapshot.order_count || sourceOrders.length)} OS unicas`,
      ...(Number(csvSnapshot.historical_assignment_count || 0)
        ? [`${Number(csvSnapshot.assignment_count || sourceOrders.length)} alocacoes`, `${Number(csvSnapshot.historical_assignment_count)} historicas`] : []),
      ...(Number(csvSnapshot.reallocation_count || 0)
        ? [`${Number(csvSnapshot.reallocation_count)} realocacao`] : []),
      `${Number(csvSnapshot.activity_count || 0)} atividades`,
      ...(Number(csvSnapshot.timeline_activity_count || 0)
        ? [`${Number(csvSnapshot.timeline_activity_count)} refeicoes`] : []),
      `${Number(csvSnapshot.source_rows || 0)} linhas do TOA`,
      excluded ? `${excluded} fora da base ignoradas` : "somente leitura; Baixar OS continua no Imperium",
    ].join(" | ");
  }

  const tabs = model.definitions.map((definition) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = definition.key === state.monitorView ? "active" : "";
    const tabCount = definition.key === "routes"
      ? model.views.routes?.console?.totalActivities || 0
      : model.views[definition.key]?.rows.length || 0;
    const count = document.createElement("span");
    count.className = "monitor-tab-count";
    count.textContent = tabCount;
    button.append(document.createTextNode(definition.label), count);
    button.setAttribute("aria-label", `${definition.label}: ${tabCount} registros`);
    button.addEventListener("click", () => {
      state.monitorView = definition.key;
      renderOperationsMonitor();
    });
    return button;
  });
  elements.monitorTabs.replaceChildren(...tabs);

  const view = model.views[state.monitorView] || model.views.monitor;
  const rows = monitorFilteredRows(view);
  elements.monitorViewTitle.textContent = view.title;
  elements.monitorViewSubtitle.textContent = view.subtitle;
  elements.monitorNotice.textContent = view.note || "";
  elements.monitorNotice.classList.toggle("hidden", !view.note);
  elements.monitorDemo.classList.toggle("active", state.monitorDemoMode);
  elements.monitorDemo.setAttribute("aria-pressed", state.monitorDemoMode ? "true" : "false");
  elements.monitorDemo.querySelector("span").textContent = state.monitorDemoMode
    ? "Voltar aos dados reais" : "Cenarios de exemplo";
  elements.monitorDemoBanner.classList.toggle("hidden", !state.monitorDemoMode);
  const routeConsoleActive = state.monitorView === "routes" && view.console;
  elements.monitorRouteConsole.classList.toggle("hidden", !routeConsoleActive);
  elements.monitorTableWrap.classList.toggle("hidden", Boolean(routeConsoleActive));
  let exportRows = rows;
  let exportColumns = view.columns;
  if (routeConsoleActive) {
    const routeExport = renderRouteConsole(view.console);
    exportRows = routeExport.rows;
    exportColumns = routeExport.columns;
  } else {
    elements.monitorTableHead.innerHTML = `<tr>${view.columns.map((column) => (
      `<th>${escapeHtml(column.label)}</th>`
    )).join("")}</tr>`;
    if (rows.length) {
      elements.monitorTableBody.innerHTML = rows.map((row) => `<tr class="${row.example ? "monitor-example-row" : ""}">${view.columns.map((column, index) => {
        const value = row[column.key] ?? "-";
        const className = monitorCellClass(column, row);
        const content = className
          ? `<span class="${className}">${escapeHtml(value)}</span>`
          : index === 0
            ? `<strong>${escapeHtml(value)}</strong>${row.example ? '<span class="monitor-example-badge">EXEMPLO</span>' : ""}`
            : escapeHtml(value);
        return `<td>${content}</td>`;
      }).join("")}</tr>`).join("");
    } else {
      elements.monitorTableBody.innerHTML = `<tr><td class="monitor-empty" colspan="${view.columns.length}">Nenhum registro corresponde aos filtros.</td></tr>`;
    }
  }
  state.monitorExportRows = state.monitorDemoMode ? [] : exportRows.map((row) => ({ ...row }));
  state.monitorExportColumns = exportColumns.map((column) => ({ ...column }));
  elements.monitorExport.disabled = state.monitorDemoMode || exportRows.length === 0;
  elements.monitorExport.title = state.monitorDemoMode
    ? "Exemplos nao sao exportados" : "Exportar a visao atual";
  elements.monitorNotify.classList.toggle("active", state.monitorNotifications);
  elements.monitorNotify.querySelector("span").textContent = state.monitorNotifications
    ? "Alertas ativos" : "Alertas";
  elements.monitorVoice.classList.toggle("active", state.monitorVoiceEnabled);
  elements.monitorVoice.setAttribute("aria-pressed", String(state.monitorVoiceEnabled));
  elements.monitorVoice.querySelector("span").textContent = state.monitorVoiceEnabled
    ? "Voz TEC1 ativa" : "Voz TEC1";
  notifyMonitorAlerts(model);
  notifyMonitorTec1Voice(model);
  window.lucide?.createIcons();
}

async function toggleMonitorNotifications() {
  if (state.monitorNotifications) {
    state.monitorNotifications = false;
    localStorage.removeItem("dominium-monitor-notifications");
    renderOperationsMonitor();
    showToast("Alertas locais desativados.");
    return;
  }
  if (typeof Notification === "undefined") {
    showToast("Este navegador nao oferece alertas locais.", "error");
    return;
  }
  const permission = Notification.permission === "granted"
    ? "granted" : await Notification.requestPermission();
  if (permission !== "granted") {
    showToast("Permissao de notificacao nao concedida.", "warning");
    return;
  }
  state.monitorNotifications = true;
  localStorage.setItem("dominium-monitor-notifications", "1");
  renderOperationsMonitor();
  showToast("Alertas operacionais ativados.", "success");
}

function exportOperationsMonitor() {
  if (!state.monitorExportRows.length) return;
  setDownloadMotion(elements.monitorExport, "running");
  const quote = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const lines = [
    state.monitorExportColumns.map((column) => quote(column.label)).join(";"),
    ...state.monitorExportRows.map((row) => state.monitorExportColumns
      .map((column) => quote(row[column.key])).join(";")),
  ];
  saveBlob(
    new Blob(["\uFEFF", lines.join("\r\n")], { type: "text/csv;charset=utf-8" }),
    `monitor-os-${state.monitorView}-${elements.date.value || localDate()}.csv`,
  );
  showToast("Relatorio do Monitor exportado.", "success");
  window.setTimeout(() => setDownloadMotion(elements.monitorExport, "complete"), 380);
}

function render() {
  const visible = visibleOrders();
  const actionable = visible.filter(
    (order) => !order.read_only && normalize(order.status) === "EM CAMPO",
  );
  const productive = productiveClose();
  renderProfileTabs();
  elements.body.replaceChildren(...visible.map(rowFor));
  elements.failuresBody.replaceChildren(...state.failures.map(failureRowFor));
  elements.pendingLabel.textContent = elements.status.value === "field"
    ? "Em campo"
    : "Resultados";
  elements.pendingCount.textContent = visible.length;
  elements.selectedCount.textContent = state.selected.size;
  elements.completedCount.textContent = state.completed;
  elements.failureCount.textContent = state.failures.length;
  elements.batch.disabled = state.running || state.loading || !state.closeEnabled
    || productive || state.selected.size === 0;
  elements.codeOptions.forEach((button) => {
    const supported = state.closeCodes.some((item) => item.code === button.dataset.closeCode);
    const active = button.dataset.closeCode === state.closeCode;
    button.classList.toggle("hidden", !supported);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    button.disabled = state.running || state.loading || !state.closeEnabled || !supported;
  });
  elements.refresh.disabled = state.running || state.loading;
  elements.date.disabled = state.running || state.loading;
  elements.selectAll.disabled = state.running || state.loading || !state.closeEnabled
    || productive || actionable.length === 0;
  elements.selectAll.checked = actionable.length > 0
    && actionable.every((order) => state.selected.has(order.id_os));
  elements.selectAll.indeterminate = !elements.selectAll.checked
    && actionable.some((order) => state.selected.has(order.id_os));
  elements.empty.classList.toggle("hidden", visible.length !== 0 || !elements.loading.classList.contains("hidden"));
  elements.failuresEmpty.classList.toggle("hidden", state.failures.length !== 0);
  elements.ordersSection.classList.toggle("hidden", state.activeView !== "orders");
  elements.failuresSection.classList.toggle("hidden", state.activeView !== "failures");
  elements.ordersTab.classList.toggle("active", state.activeView === "orders");
  elements.failuresTab.classList.toggle("active", state.activeView === "failures");
  elements.dashboardWorkspace.classList.toggle("hidden", state.activeModule !== "dashboard");
  elements.monitorWorkspace.classList.toggle("hidden", state.activeModule !== "monitor");
  elements.ordersWorkspace.classList.toggle("hidden", state.activeModule !== "orders");
  elements.stockWorkspace.classList.toggle("hidden", state.activeModule !== "stock");
  elements.techniciansWorkspace.classList.toggle("hidden", state.activeModule !== "technicians");
  elements.intelligenceWorkspace.classList.toggle("hidden", state.activeModule !== "intelligence");
  elements.bulkCreateWorkspace.classList.toggle("hidden", state.activeModule !== "bulk");
  elements.importWorkspace.classList.toggle("hidden", state.activeModule !== "imports");
  elements.automationTestWorkspace.classList.toggle(
    "hidden", state.activeModule !== "automation-test",
  );
  elements.closeWorkspace.classList.toggle("hidden", state.activeModule !== "close");
  elements.reportWorkspace.classList.toggle("hidden", state.activeModule !== "report");
  elements.databaseWorkspace.classList.toggle("hidden", state.activeModule !== "database");
  elements.historyWorkspace.classList.toggle("hidden", state.activeModule !== "history");
  elements.dashboardModule.classList.toggle("active", state.activeModule === "dashboard");
  elements.monitorModule?.classList.toggle("active", state.activeModule === "monitor");
  elements.ordersModule.classList.toggle("active", state.activeModule === "orders");
  elements.stockModule.classList.toggle("active", state.activeModule === "stock");
  elements.techniciansModule.classList.toggle("active", state.activeModule === "technicians");
  elements.intelligenceModule.classList.toggle("active", state.activeModule === "intelligence");
  elements.bulkCreateModule.classList.toggle("active", state.activeModule === "bulk");
  elements.importsModule.classList.toggle("active", state.activeModule === "imports");
  elements.automationTestModule.classList.toggle(
    "active", state.activeModule === "automation-test",
  );
  elements.closeModule.classList.toggle("active", state.activeModule === "close");
  elements.reportModule.classList.toggle("active", state.activeModule === "report");
  elements.databaseModule.classList.toggle("active", state.activeModule === "database");
  elements.historyModule.classList.toggle("active", state.activeModule === "history");
  renderDashboard();
  renderOperationsMonitor();
  renderImportPreview();
  renderToaAutomation();
  renderAutomationTest();
  renderStock();
  renderTechnicians();
  renderIntelligence();
  renderSerialAudit();
  renderBulkCreate();
  renderManualCreate();
  renderCloseWorkspace();
  renderDisconnectAutomation();
  renderSemiAutoQueue();
  renderCloseReport();
  renderHistory();
  renderServerLogs();
}

async function loadOrders({ preserveSelection = false, quiet = false } = {}) {
  if (state.loading) return false;
  const profileKey = state.profile;
  state.loading = true;
  if (!quiet) {
    elements.loading.classList.remove("hidden");
    elements.empty.classList.add("hidden");
    elements.body.replaceChildren();
  }
  elements.refresh.disabled = true;
  if (!quiet) setConnection("Consultando servidor");
  renderProfileTabs();
  try {
    const status = elements.status.value || "field";
    const serviceType = elements.service.value || "all";
    const payload = await request(apiUrl(
      `/api/orders?date=${encodeURIComponent(elements.date.value)}`
      + `&status=${encodeURIComponent(status)}`
      + `&service_type=${encodeURIComponent(serviceType)}`,
    ), { timeoutMs: status === "all" ? 300000 : 180000 });
    if (profileKey !== state.profile) return false;
    state.orders = payload.orders;
    state.monitorLastUpdatedAt = new Date().toISOString();
    state.monitorSnapshotStale = Boolean(payload.stale);
    state.closeInstallerChecks = {};
    if (preserveSelection) {
      const activeIds = new Set(state.orders.map((order) => order.id_os));
      state.selected = new Set(
        [...state.selected].filter((idOs) => activeIds.has(idOs)),
      );
    } else {
      state.selected.clear();
    }
    updateServiceOptions();
    await loadFailures(profileKey);
    await loadCloseReport({ quiet: true });
    setConnection(
      payload.stale
        ? "Operação em andamento; exibindo lista atual"
        : state.closeEnabled ? "Conectado ao servidor" : "Conectado; somente consulta",
      payload.stale ? "busy" : "online",
    );
    return true;
  } catch (error) {
    if (profileKey !== state.profile) return false;
    if (state.orders.length) state.monitorSnapshotStale = true;
    setConnection(
      state.orders.length ? "Conexão instável; lista mantida" : "Falha de conexão",
      "error",
    );
    if (!quiet) showToast(error.message, "error");
    return false;
  } finally {
    if (profileKey === state.profile) {
      state.loading = false;
      elements.loading.classList.add("hidden");
      elements.refresh.disabled = false;
      render();
    }
  }
}

function renderToaLiveStatus() {
  const status = state.toaLiveStatus;
  const searching = state.toaLiveLoading || state.toaLiveConnecting
    || Boolean(state.semiAutoCurrentContract);
  const online = Boolean(status?.connected && status?.authenticated);
  state.disconnectToaHealthy = online;
  const kind = searching || status?.busy ? "busy" : online ? "online" : "error";
  elements.toaLiveSession.className = `toa-live-session ${kind}`;
  elements.toaLiveSessionText.textContent = searching
      ? state.toaLiveConnecting ? "Abrindo TOA" : "Consultando contrato/O.S."
    : online
      ? status?.remote ? "Ponte TOA conectada" : "TOA conectado"
      : status?.last_error || "TOA fechado";
  const contract = elements.toaLiveContract.value.replace(/\D/g, "");
  elements.toaLiveLookup.disabled = searching || !online || contract.length < 5;
  elements.toaLiveContract.disabled = searching;
  elements.toaLiveOpen.disabled = searching || online;
  elements.toaLiveOpen.querySelector("span").textContent = online
    ? "TOA aberto"
    : state.toaLiveConnecting ? "Abrindo" : "Abrir TOA";
  elements.headerToaOpen.disabled = searching || online;
  elements.headerToaOpen.classList.toggle("online", online);
  elements.headerToaOpen.querySelector("span").textContent = online
    ? "TOA aberto"
    : state.toaLiveConnecting ? "Abrindo" : "Abrir TOA";
  elements.toaLiveLookup.classList.toggle("loading", searching);
  elements.toaLiveLookup.setAttribute("aria-busy", searching ? "true" : "false");
  elements.toaLiveLookup.querySelector("span").textContent = searching
    ? "Buscando atividade"
    : "Buscar no TOA";
  document.dispatchEvent(new CustomEvent("dominium:toa-status", {
    detail: { element: elements.toaLiveSession, kind },
  }));
  renderDisconnectAutomation();
  if (!online && state.disconnectAutomation?.status === "running") {
    void autoPauseDisconnectAutomation();
  }
  renderSemiAutoQueue();
}

async function loadToaLiveStatus({ quiet = false } = {}) {
  try {
    state.toaLiveStatus = await request("/api/toa-live/status", { timeoutMs: 15000 });
  } catch (error) {
    state.toaLiveStatus = {
      connected: false,
      authenticated: false,
      last_error: error.message,
    };
    if (!quiet) console.error("Falha ao verificar a sessao TOA", error);
  }
  const isOnline = Boolean(
    state.toaLiveStatus?.connected && state.toaLiveStatus?.authenticated,
  );
  if (!isOnline && state.orders.length) state.monitorSnapshotStale = true;
  renderToaLiveStatus();
  if (quiet && isOnline && state.activeModule === "monitor" && !state.loading) {
    await loadOrders({ preserveSelection: true, quiet: true });
  } else if (state.activeModule === "monitor") {
    renderOperationsMonitor();
  }
}

const disconnectStatusLabels = {
  idle: "Nao preparada",
  pending: "Na fila",
  checking_toa: "Consultando TOA",
  waiting_toa: "Aguardando conclusao",
  ready: "Validando baixa",
  submitting: "Enviando OS",
  awaiting_confirmation: "Aguardando Imperium",
  completed: "Concluida",
  manual_review: "Tratativa humana",
  failed: "Falha sem repeticao",
  expired: "Janela expirada",
  paused: "Pausada e salva",
  running: "Em execucao",
  stopped: "Parada e salva",
};

const disconnectTerminalStatuses = new Set([
  "awaiting_confirmation",
  "completed",
  "manual_review",
  "failed",
  "expired",
]);

function disconnectStatusLabel(value) {
  return disconnectStatusLabels[String(value || "")] || String(value || "Aguardando");
}

function disconnectIsRunning() {
  return state.disconnectAutomation?.status === "running" || state.disconnectAutomationWorker;
}

function disconnectDisplayList(values, emptyLabel = "Nenhum") {
  const items = (values || []).map((value) => {
    if (typeof value === "string") return value;
    const serial = String(value?.serial || value?.serialnumber || "").trim();
    const code = String(value?.code || value?.material_code || value?.codigoequipamento || "").trim();
    const quantity = value?.quantity ?? value?.qtd;
    if (serial) return `${serial}${value?.type ? ` (${String(value.type).toUpperCase()})` : ""}`;
    if (code) return `${code}${quantity ? ` x${quantity}` : ""}`;
    return "";
  }).filter(Boolean);
  return items.length ? items.join(", ") : emptyLabel;
}

function disconnectCurrentItem() {
  const automation = state.disconnectAutomation;
  const items = automation?.items || [];
  const current = items.find((item) => (
    String(item.contract) === String(automation?.current_contract || "")
  ));
  if (current) return current;
  const active = items.find((item) => ["checking_toa", "ready", "submitting"].includes(item.status));
  if (active) return active;
  return [...items].sort((left, right) => (
    String(right.updated_at || "").localeCompare(String(left.updated_at || ""))
  ))[0] || null;
}

// =============================================================================
// TOA -> IMPERIUM | FLUXOS AUTOMATICOS DE DESCONEXAO
// =============================================================================
function renderDisconnectAutomation() {
  if (!elements.disconnectAutomation) return;
  // O bot dedicado assumiu a baixa de desconexao. Mantemos o codigo legado
  // preservado, mas ele nao disputa espaco nem operacao com a nova esteira.
  elements.disconnectAutomation.classList.add("hidden");
  elements.disconnectAutomation.setAttribute("aria-hidden", "true");
  return;

  const automation = state.disconnectAutomation;
  const counts = automation?.counts || {};
  const queueStatus = automation?.status || "idle";
  const running = queueStatus === "running";
  const busy = state.disconnectAutomationLoading || state.disconnectAutomationWorker;
  const count = Number(automation?.count || 0);
  const waiting = ["pending", "checking_toa", "waiting_toa", "ready", "submitting"]
    .reduce((total, key) => total + Number(counts[key] || 0), 0);
  const completed = Number(counts.completed || 0) + Number(counts.awaiting_confirmation || 0);
  const review = Number(counts.manual_review || 0)
    + Number(counts.failed || 0) + Number(counts.expired || 0);

  elements.disconnectAutomationMessage.textContent = automation?.message
    || "Prepare a fila NTL/PWM-DMV_ADM importada de hoje para iniciar.";
  elements.disconnectQueueCount.textContent = String(count);
  elements.disconnectQueueStatus.textContent = disconnectStatusLabel(queueStatus);
  elements.disconnectWaitingCount.textContent = String(waiting);
  elements.disconnectCompletedCount.textContent = String(completed);
  elements.disconnectReviewCount.textContent = String(review);

  elements.disconnectPrepare.disabled = busy || running;
  elements.disconnectStart.disabled = busy || count === 0 || !["paused", "stopped"].includes(queueStatus);
  elements.disconnectPause.disabled = !running || state.disconnectAutomationLoading;
  elements.disconnectResume.disabled = busy || count === 0 || !["paused", "stopped"].includes(queueStatus);
  elements.disconnectStop.disabled = state.disconnectAutomationLoading
    || !["running", "paused"].includes(queueStatus);

  const online = Boolean(state.disconnectToaHealthy);
  elements.disconnectToaStatus.className = `toa-live-session ${online ? "online" : "error"}`;
  elements.disconnectToaStatusText.textContent = online
    ? "TOA online; verificacao a cada 20s"
    : "Sessao automatica TOA desconectada; fila sera pausada";

  const current = disconnectCurrentItem();
  const result = current?.result || {};
  const plans = Array.isArray(result.plans) ? result.plans : [];
  const activePlan = plans.find((plan) => (
    String(plan.num_os) === String(result.current_os || "")
  )) || plans[0] || {};
  elements.disconnectCurrentStage.textContent = result.stage
    || disconnectStatusLabel(current?.status || queueStatus);
  elements.disconnectCurrentWindow.textContent = current?.window_label || "Sem janela";
  elements.disconnectCurrentContract.textContent = current?.contract || "-";
  elements.disconnectCurrentOs.textContent = result.current_os
    || activePlan.num_os || (current?.os_numbers || []).join(", ") || "-";
  elements.disconnectCurrentTechnician.textContent = result.technician
    || activePlan.technician || (current?.technicians || []).join(", ") || "-";
  elements.disconnectCurrentAppointment.textContent = result.appointment
    || current?.window_label || "-";
  elements.disconnectCurrentCode.textContent = String(result.current_code || activePlan.code || "-");
  elements.disconnectCurrentService.textContent = result.current_service
    || activePlan.service || "-";
  elements.disconnectCurrentInstalled.textContent = disconnectDisplayList(
    activePlan.installed_equipment || result.installed_equipment,
  );
  elements.disconnectCurrentRemoved.textContent = disconnectDisplayList(
    activePlan.removed_equipment || result.removed_equipment,
  );
  elements.disconnectCurrentMaterials.textContent = disconnectDisplayList(
    activePlan.materials || result.materials,
    "Nao se aplica",
  );
  elements.disconnectCurrentResult.textContent = current?.last_error
    || result.message || (current
      ? `${disconnectStatusLabel(current.status)}. Tentativa de consulta ${current.attempts || 0}.`
      : "Nenhuma operacao em andamento.");

  const visible = (automation?.items || [])
    .filter((item) => !disconnectTerminalStatuses.has(item.status))
    .slice(0, 8);
  if (!visible.length) {
    elements.disconnectQueuePreview.replaceChildren(
      automationNode("p", "disconnect-queue-empty", count
        ? "Nao ha contratos ativos; revise os resultados da fila."
        : "Prepare a fila para visualizar os contratos por janela."),
    );
  } else {
    elements.disconnectQueuePreview.replaceChildren(...visible.map((item) => {
      const row = automationNode("article", "disconnect-queue-row");
      const identity = automationNode("div");
      identity.append(
        automationNode("strong", "", `Contrato ${item.contract}`),
        automationNode(
          "span",
          "",
          `${item.window_label || "Sem janela"} | ${(item.os_numbers || []).length} OS`,
        ),
      );
      const status = automationNode(
        "span",
        `disconnect-queue-status status-${item.status}`,
        disconnectStatusLabel(item.status),
      );
      row.append(identity, status);
      return row;
    }));
  }
}

async function loadDisconnectAutomation({ quiet = false } = {}) {
  try {
    state.disconnectAutomation = await request("/api/disconnect-automation", {
      timeoutMs: 15000,
    });
  } catch (error) {
    if (!quiet) {
      showToast(error.message, "error");
      console.error("Falha ao carregar a fila de desconexao", error);
    }
  }
  renderDisconnectAutomation();
}

async function disconnectAutomationRequest(path, body) {
  const payload = await request(`/api/disconnect-automation/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
    timeoutMs: 30000,
  });
  state.disconnectAutomation = payload.state || payload;
  renderDisconnectAutomation();
  return payload;
}

async function prepareDisconnectAutomation() {
  if (state.disconnectAutomationLoading || state.profile !== "natal") return;
  state.disconnectAutomationLoading = true;
  renderDisconnectAutomation();
  try {
    await disconnectAutomationRequest("prepare", {
      profile: "natal",
      target: "rn",
      date: localDate(),
    });
    showToast("Fila NTL/PWM-DMV_ADM preparada e salva.", "success");
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao preparar a fila de desconexao", error);
  } finally {
    state.disconnectAutomationLoading = false;
    renderDisconnectAutomation();
  }
}

async function autoPauseDisconnectAutomation() {
  if (
    state.disconnectAutoPausing
    || state.disconnectAutomation?.status !== "running"
  ) return;
  state.disconnectAutoPausing = true;
  state.disconnectAutomationStopRequested = true;
  try {
    await disconnectAutomationRequest("action", { action: "pause" });
    showToast("TOA desconectado. A fila foi pausada e salva.", "error");
  } catch (error) {
    console.error("Falha ao pausar a fila apos queda do TOA", error);
  } finally {
    state.disconnectAutoPausing = false;
    renderDisconnectAutomation();
  }
}

async function controlDisconnectAutomation(action) {
  if (state.disconnectAutomationLoading) return;
  if (
    action === "start"
    && !window.confirm(
      "Iniciar a baixa de desconexao? O DOMINIUM podera enviar OS reais pela integracao IMPERIUM.",
    )
  ) return;
  state.disconnectAutomationLoading = true;
  if (["pause", "stop"].includes(action)) state.disconnectAutomationStopRequested = true;
  renderDisconnectAutomation();
  try {
    const normalizedAction = action === "resume" ? "continue" : action;
    await disconnectAutomationRequest("action", { action: normalizedAction });
    if (["start", "continue"].includes(normalizedAction)) {
      state.disconnectAutomationStopRequested = false;
      if (!state.disconnectToaHealthy) {
        await autoPauseDisconnectAutomation();
        return;
      }
      void runDisconnectAutomation();
    }
  } catch (error) {
    showToast(error.message, "error");
    console.error(`Falha na acao ${action} da fila de desconexao`, error);
  } finally {
    state.disconnectAutomationLoading = false;
    renderDisconnectAutomation();
  }
}

function disconnectManualError(...reasons) {
  const clean = reasons.flat().map(String).map((value) => value.trim()).filter(Boolean);
  const error = new Error(clean.join(" | ") || "Tratativa humana necessaria");
  error.disconnectReasons = clean;
  return error;
}

function disconnectEquipmentDraft(items) {
  const unique = new Map();
  (items || []).forEach((item) => {
    const serial = String(item.serial || item.serialnumber || "").trim().toUpperCase();
    if (!serial) return;
    unique.set(serial, {
      serial,
      type: toaLiveEquipmentType(item),
      code: String(item.equipment_code || item.code || item.codigoequipamento || "").trim(),
    });
  });
  return [...unique.values()];
}

const CANONICAL_MATERIAL_MAP = {
  "22066907": { code: "22026219", name: "CABO COAXIAL RG6 TRISH SEM MENSAG BRANCO", unit: "M" },
  "22066906": { code: "22026223", name: "CABO COAXIAL RG6 TRISH COM MENSAG PRETO", unit: "M" },
  "22061796": { code: "22061736", name: "CABO DROP 1FO LOW F FIG8 LOW CINZA", unit: "M" },
  "22026267": { code: "22061736", name: "CABO DROP 1FO LOW F FIG8 LOW CINZA", unit: "M" },
  "22057620": { code: "22065513", name: "CONECTOR FO CAMPO CPO SC APC FRKW", unit: "UN" },
  "22069613": { code: "22065513", name: "CONECTOR FO CAMPO CPO SC APC FRKW", unit: "UN" },
  "22065512": { code: "22065513", name: "CONECTOR FO CAMPO CPO SC APC FRKW", unit: "UN" },
  "22057635": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22060738": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22026219": { code: "22026219", name: "CABO COAXIAL RG6 TRISH SEM MENSAG BRANCO", unit: "M" },
  "22026223": { code: "22026223", name: "CABO COAXIAL RG6 TRISH COM MENSAG PRETO", unit: "M" },
  "22061736": { code: "22061736", name: "CABO DROP 1FO LOW F FIG8 LOW CINZA", unit: "M" },
  "22065513": { code: "22065513", name: "CONECTOR FO CAMPO CPO SC APC FRKW", unit: "UN" },
  "22025139": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22024800": { code: "22024800", name: "ANEL DE VEDACAO WEATHER SEAL 1/2 CONEC F", unit: "UN" },
  "22025321": { code: "22024800", name: "ANEL DE VEDACAO WEATHER SEAL 1/2 CONEC F", unit: "UN" },
  "22025136": { code: "22025136", name: "BUCHA P/CABO RG6/59 BRANCA", unit: "UN" },
  "22026189": { code: "22026189", name: "CONEC_RI COMPRESSAO F-6", unit: "UN" },
  "22056364": { code: "22056364", name: "MINI ISOLADOR CPE P/CM DECODER", unit: "UN" },
  "22067384": { code: "22067384", name: "MINI ISOLADOR CPE CABLE MODEM E DECODER", unit: "UN" },
  "22056365": { code: "22056365", name: "PROTETOR P/MINI ISOLADOR CPE", unit: "UN" },
  "22056366": { code: "22056366", name: "ISOLADOR COAXIAL QUADRADO - CISP-HR", unit: "UN" },
  "22066517": { code: "22056366", name: "ISOLADOR COAXIAL QUADRADO - CISP-HR", unit: "UN" },
  "22056394": { code: "22056366", name: "ISOLADOR COAXIAL QUADRADO - CISP-HR", unit: "UN" },
  "22025091": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22025139": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22057635": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22060738": { code: "22025139", name: "FIXADOR FIO BR RG6 CIRCUL 7MM", unit: "UN" },
  "22025072": { code: "22064608", name: "FITA ISOLANTE 3M HIGHLAND 19MM X 20M", unit: "M" },
  "22064608": { code: "22064608", name: "FITA ISOLANTE 3M HIGHLAND 19MM X 20M", unit: "M" },
  "22056696": { code: "22064608", name: "FITA ISOLANTE 3M HIGHLAND 19MM X 20M", unit: "M" },
  "22055828": { code: "22055828", name: "ABRACADEIRA HELLERMANN T50R-PT", unit: "UN" },
  "22023400": { code: "22055828", name: "ABRACADEIRA HELLERMANN T50R-PT", unit: "UN" },
  "22025247": { code: "22055828", name: "ABRACADEIRA HELLERMANN T50R-PT", unit: "UN" },
  "22056346": { code: "22055828", name: "ABRACADEIRA HELLERMANN T50R-PT", unit: "UN" },
  "22026502": { code: "22026502", name: "PITAO S8 C/BUCHA", unit: "UN" },
  "22056395": { code: "22026502", name: "PITAO S8 C/BUCHA", unit: "UN" },
  "22061434": { code: "22061434", name: "PITAO C/FLANGE + BUCHA S10", unit: "UN" },
  "22026489": { code: "22061434", name: "PITAO C/FLANGE + BUCHA S10", unit: "UN" },
  "22061811": { code: "22061811", name: "CONECTOR UTP RJ45 M CAT 5 24AWG", unit: "UN" },
  "22026169": { code: "22061811", name: "CONECTOR UTP RJ45 M CAT 5 24AWG", unit: "UN" },
  "22059179": { code: "22061811", name: "CONECTOR UTP RJ45 M CAT 5 24AWG", unit: "UN" },
  "22026147": { code: "22026147", name: "CONEC_RI COMPRESSAO F-11", unit: "UN" },
  "22056764": { code: "22026147", name: "CONEC_RI COMPRESSAO F-11", unit: "UN" },
  "22057341": { code: "22057341", name: "CABO COAXIAL RG11 TRI C/M PT", unit: "M" },
  "22057156": { code: "22057341", name: "CABO COAXIAL RG11 TRI C/M PT", unit: "M" },
  "22056342": { code: "22065718", name: "MARCADOR CASA PRETO NR 0", unit: "UN" },
  "22065718": { code: "22065718", name: "MARCADOR CASA PRETO NR 0", unit: "UN" },
  "22055829": { code: "22065718", name: "MARCADOR CASA PRETO NR 0", unit: "UN" },
  "22066616": { code: "22065718", name: "MARCADOR CASA PRETO NR 0", unit: "UN" },
  "22056343": { code: "22065719", name: "MARCADOR CASA PRETO NR 1", unit: "UN" },
  "22065719": { code: "22065719", name: "MARCADOR CASA PRETO NR 1", unit: "UN" },
  "22055830": { code: "22065719", name: "MARCADOR CASA PRETO NR 1", unit: "UN" },
  "22066615": { code: "22065719", name: "MARCADOR CASA PRETO NR 1", unit: "UN" },
  "22056344": { code: "22065720", name: "MARCADOR CASA PRETO NR 2", unit: "UN" },
  "22065720": { code: "22065720", name: "MARCADOR CASA PRETO NR 2", unit: "UN" },
  "22055831": { code: "22065720", name: "MARCADOR CASA PRETO NR 2", unit: "UN" },
  "22066614": { code: "22065720", name: "MARCADOR CASA PRETO NR 2", unit: "UN" },
  "22056345": { code: "22065721", name: "MARCADOR CASA PRETO NR 3", unit: "UN" },
  "22065721": { code: "22065721", name: "MARCADOR CASA PRETO NR 3", unit: "UN" },
  "22055832": { code: "22065721", name: "MARCADOR CASA PRETO NR 3", unit: "UN" },
  "22066613": { code: "22065721", name: "MARCADOR CASA PRETO NR 3", unit: "UN" },
  "22056340": { code: "22065722", name: "MARCADOR CASA PRETO NR 4", unit: "UN" },
  "22065722": { code: "22065722", name: "MARCADOR CASA PRETO NR 4", unit: "UN" },
  "22055833": { code: "22065722", name: "MARCADOR CASA PRETO NR 4", unit: "UN" },
  "22066612": { code: "22065722", name: "MARCADOR CASA PRETO NR 4", unit: "UN" },
  "22056331": { code: "22065723", name: "MARCADOR CASA PRETO NR 5", unit: "UN" },
  "22065723": { code: "22065723", name: "MARCADOR CASA PRETO NR 5", unit: "UN" },
  "22055835": { code: "22065723", name: "MARCADOR CASA PRETO NR 5", unit: "UN" },
  "22066611": { code: "22065723", name: "MARCADOR CASA PRETO NR 5", unit: "UN" },
  "22056336": { code: "22065724", name: "MARCADOR CASA PRETO NR 6", unit: "UN" },
  "22065724": { code: "22065724", name: "MARCADOR CASA PRETO NR 6", unit: "UN" },
  "22066610": { code: "22065724", name: "MARCADOR CASA PRETO NR 6", unit: "UN" },
  "22056341": { code: "22065725", name: "MARCADOR CASA PRETO NR 7", unit: "UN" },
  "22065725": { code: "22065725", name: "MARCADOR CASA PRETO NR 7", unit: "UN" },
  "22055827": { code: "22065725", name: "MARCADOR CASA PRETO NR 7", unit: "UN" },
  "22066609": { code: "22065725", name: "MARCADOR CASA PRETO NR 7", unit: "UN" },
  "22056337": { code: "22065726", name: "MARCADOR CASA PRETO NR 8", unit: "UN" },
  "22065726": { code: "22065726", name: "MARCADOR CASA PRETO NR 8", unit: "UN" },
  "22055857": { code: "22065726", name: "MARCADOR CASA PRETO NR 8", unit: "UN" },
  "22066608": { code: "22065726", name: "MARCADOR CASA PRETO NR 8", unit: "UN" },
  "22056339": { code: "22065727", name: "MARCADOR CASA PRETO NR 9", unit: "UN" },
  "22065727": { code: "22065727", name: "MARCADOR CASA PRETO NR 9", unit: "UN" },
  "22066607": { code: "22065727", name: "MARCADOR CASA PRETO NR 9", unit: "UN" },
  "22025114": { code: "22065728", name: "MARCADOR CASA PRETO LETRA A", unit: "UN" },
  "22065728": { code: "22065728", name: "MARCADOR CASA PRETO LETRA A", unit: "UN" },
  "22025115": { code: "22065729", name: "MARCADOR CASA PRETO LETRA B", unit: "UN" },
  "22065729": { code: "22065729", name: "MARCADOR CASA PRETO LETRA B", unit: "UN" },
  "22025116": { code: "22025116", name: "MARCADOR CASA PTO LETRA C", unit: "UN" },
  "22065730": { code: "22025116", name: "MARCADOR CASA PTO LETRA C", unit: "UN" },
  "22025117": { code: "22025117", name: "MARCADOR CASA PTO LETRA D", unit: "UN" },
  "22065731": { code: "22025117", name: "MARCADOR CASA PTO LETRA D", unit: "UN" },
  "22025119": { code: "22025119", name: "MARCADOR CASA PTO LETRA E", unit: "UN" },
  "22065732": { code: "22025119", name: "MARCADOR CASA PTO LETRA E", unit: "UN" },
  "22025162": { code: "22025162", name: "MARCADOR APTO AMAR. NR.0", unit: "UN" },
  "22025250": { code: "22025250", name: "MARCADOR APTO AMAR. NR.1", unit: "UN" },
  "22025244": { code: "22025244", name: "MARCADOR APTO AMAR. NR.2", unit: "UN" },
  "22025241": { code: "22025241", name: "MARCADOR APTO AMAR. NR.3", unit: "UN" },
  "22025245": { code: "22025245", name: "MARCADOR APTO AMAR. NR.4", unit: "UN" },
  "22025237": { code: "22025237", name: "MARCADOR APTO AMAR. NR.5", unit: "UN" },
  "22025243": { code: "22025243", name: "MARCADOR APTO AMAR. NR.6", unit: "UN" },
  "22025238": { code: "22025238", name: "MARCADOR APTO AMAR. NR.7", unit: "UN" },
  "22025239": { code: "22025239", name: "MARCADOR APTO AMAR. NR.8", unit: "UN" },
  "22025240": { code: "22025240", name: "MARCADOR APTO AMAR. NR.9", unit: "UN" },
  "22025181": { code: "22025181", name: "MARCADOR APTO AMAR. LETRA A", unit: "UN" },
  "22025182": { code: "22025182", name: "MARCADOR APTO AMAR. LETRA B", unit: "UN" },
  "22025183": { code: "22025183", name: "MARCADOR APTO AMAR. LETRA C", unit: "UN" },
};

function toaLiveMaterialIdentity(item) {
  const rawCode = String(item?.material_code || item?.code || "").trim();
  const rawDescription = String(item?.description || "").trim();
  const code = /^\d{6,8}$/.test(rawCode)
    ? rawCode
    : /(?:^|\D)(\d{6,8})(?:\D|$)/.exec(
      `${rawCode} ${rawDescription}`,
    )?.[1] || "";
  const canonical = CANONICAL_MATERIAL_MAP[code];
  // Preserve the exact material code reported by TOA. Equivalence is resolved in the backend.
  const targetCode = code;
  let description = rawDescription.replace(
    code ? new RegExp(`^${code}[\\s_/-]+`, "i") : /^$/,
    "",
  ).trim();
  if (!description || description.toLowerCase() === "undefined") {
    description = canonical ? canonical.name : targetCode;
  }
  const normalized = normalize(`${rawCode} ${rawDescription} ${description}`);
  const words = new Set(normalized.split(/\s+/).filter(Boolean));
  const ignored = (
    targetCode === "22057705"
    || targetCode === "22026096"
    || targetCode === "22066009"
    || targetCode === "22062576"
    || targetCode === "22026272"
    || targetCode === "433135"
    || normalized.includes("FONTE")
    || normalized.includes("ALIMENTAC")
    || normalized.includes("TRAFO")
    || normalized.includes("CABO DE FORCA")
    || normalized.includes("CABO FORCA")
    || normalized.includes("CABO DE FORÇA")
    || normalized.includes("HDMI")
    || normalized.includes("PILHA")
    || normalized.includes("PILHAS")
    || normalized.includes("BATERIA")
    || normalized.includes("SAPATILHA")
    || normalized.includes("PROPE")
    || normalized.includes("DESCARTAVEL")
    || normalized.includes("EPI")
  );
  return {
    code: targetCode,
    description,
    ignored,
    source: rawCode || rawDescription || "(vazio)",
  };
}

function disconnectMaterialsDraft(items) {
  const materials = [];
  const ignored = [];
  const seen = new Set();
  (items || []).forEach((item) => {
    const identity = toaLiveMaterialIdentity(item);
    if (identity.ignored) {
      ignored.push({
        code: identity.code,
        description: identity.description || identity.source,
        reason: "acessorio_nao_baixado",
      });
      return;
    }
    if (!/^\d{6,8}$/.test(identity.code)) {
      throw disconnectManualError(
        `material_code_invalid:${identity.source}`,
      );
    }
    if (seen.has(identity.code)) {
      throw disconnectManualError(`duplicate_material_code:${identity.code}`);
    }
    const quantity = Number(item?.used_quantity ?? item?.quantity ?? 0);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      throw disconnectManualError(
        `material_quantity_invalid:${identity.code}`,
      );
    }
    seen.add(identity.code);
    materials.push({
      code: identity.code,
      description: identity.description,
      quantity,
    });
  });
  return { materials, ignored };
}

function disconnectAutomationMaterialDraft(items) {
  return {
    materials: [],
    ignored: (items || []).map((item) => {
      const identity = toaLiveMaterialIdentity(item);
      return {
        code: identity.code,
        description: String(
          item.description || item.name || item.equipment || "",
        ).trim(),
        quantity: String(item.quantity ?? item.qtd ?? "").trim(),
        reason: "disconnect_does_not_use_materials",
      };
    }),
  };
}

function disconnectTaskCapability(service) {
  const value = normalize(service);
  if (
    value.includes("INSTALACAO DE CABO GPON")
    || (value.includes("ASSINATURA") && !value.includes("STREAM"))
  ) return "close_only";
  if (
    value.includes("PONTO VIRT")
    || value.includes("MUDANCA DE PACOTE")
    || value.includes("TROCA")
    || value.includes("STREAM")
    || value.includes("RETIRAR EQUIP")
  ) return "material_capable";
  return "unknown";
}

function disconnectTaskExecuted(value) {
  const status = normalize(value);
  // The TOA uses N in slot 194 for completed activity tasks in DMV_ADM.
  // Activity completion is validated separately before this task-level check.
  if (status === "E" || status === "N") return true;
  return ["EXECUTAD", "CONCLUID", "COMPLETE", "FINALIZAD"]
    .some((candidate) => status.includes(candidate));
}

function disconnectTransientToaError(value) {
  const message = normalize(value?.message || value);
  return [
    "A SESSAO TOA NAO ESTA AUTENTICADA",
    "ABRA O TOA PELO BOTAO",
    "TOA DESCONECTADO",
    "FAILED TO FETCH",
    "TIMED OUT",
    "TIMEOUT",
  ].some((candidate) => message.includes(candidate));
}

function disconnectActivityComplete(value) {
  const status = normalize(value);
  return ["COMPLETE", "CONCLUID", "EXECUTAD", "FINALIZAD"]
    .some((candidate) => status.includes(candidate));
}

function disconnectCaptureBlockers(capture) {
  return [
    ...(capture.operation_blockers || []),
    ...(capture.validation_errors || []),
  ].map(String).filter((reason) => reason && reason !== "activity_not_complete");
}

function disconnectExactImperiumMatch(capture, task) {
  const matches = (capture.imperium_matches || []).filter((order) => (
    String(order.num_os || "") === String(task.os_number || "")
  ));
  if (matches.length !== 1) {
    throw disconnectManualError(`os_match_ambiguous:${task.os_number || "sem_numero"}`);
  }
  const order = matches[0];
  if (
    String(order.contract || "") !== String(capture.contract || "")
    || String(order.operation_identity?.activity_id || "") !== String(capture.aid || "")
  ) {
    throw disconnectManualError(`operation_identity_mismatch:${task.os_number}`);
  }
  return {
    ...order,
    operation_source: "toa_import",
  };
}

function disconnectChooseEquipmentPlan(plans, equipment, kind) {
  if (!equipment.length) return null;
  if (kind === "removed") {
    const removalPlans = plans.filter((plan) => plan.code === "430");
    if (removalPlans.length === 1) return removalPlans[0];
    if (removalPlans.length > 1) {
      throw disconnectManualError("multiple_430_inventory_targets");
    }
  }
  const allowed = plans.filter((plan) => plan.code === "409" && plan.capability !== "close_only");
  if (allowed.length === 1) return allowed[0];
  throw disconnectManualError(`${kind}_equipment_target_ambiguous`);
}

function disconnectRouteEquipment(plans, equipment, kind) {
  if (!equipment.length) return;
  if (kind === "removed" && plans.filter((plan) => plan.code === "430").length === 1) {
    disconnectChooseEquipmentPlan(plans, equipment, kind)[`${kind}_equipment`].push(...equipment);
    return;
  }
  equipment.forEach((item) => {
    const typed = plans.filter((plan) => (
      plan.code === "409"
      && plan.capability !== "close_only"
      && expectedEquipmentType(plan.service) === item.type
    ));
    const target = typed.length === 1
      ? typed[0]
      : disconnectChooseEquipmentPlan(plans, [item], kind);
    target[`${kind}_equipment`].push(item);
  });
}

function disconnectConsolidateStreamingPackage(plans, installed, removed) {
  const packagePlans = plans.filter((plan) => {
    const service = normalize(plan.service);
    return (
      (service.includes("MUD PACOTE") || service.includes("MUDANCA DE PACOTE"))
      && service.includes("STREAM")
    );
  });
  const removalPointPlans = plans.filter(
    (plan) => normalize(plan.service).includes("RETIRAR PONTO"),
  );
  if (!packagePlans.length && !removalPointPlans.length) return null;
  if (
    packagePlans.length !== 1
    || removalPointPlans.length < 1
    || packagePlans.length + removalPointPlans.length !== plans.length
  ) {
    throw disconnectManualError("streaming_package_target_ambiguous");
  }

  const target = packagePlans[0];
  if (target.code !== "409") {
    throw disconnectManualError(`streaming_package_requires_409:${target.num_os}`);
  }
  if (!installed.length) {
    throw disconnectManualError("close_409_without_incoming_equipment");
  }

  target.installed_equipment.push(...installed);
  target.removed_equipment.push(...removed);
  return {
    plans: [target],
    skipped: removalPointPlans.map((plan) => ({
      num_os: plan.num_os,
      service: plan.service,
      reason: "retirar_ponto_kept_open",
    })),
  };
}

function disconnectQueueItemHasAdmScope(queueItem) {
  const sources = Array.isArray(queueItem?.source_files) ? queueItem.source_files : [];
  if (!sources.length) return false;
  return sources.every((source) => {
    const filename = String(source || "").split(/[\\/]/).pop();
    return /(?:^|[-_])(NTL|PWM)[-_]DMV[-_]ADM(?:[-_.]|$)/i.test(filename);
  });
}

function disconnectBuildPlans(capture, queueItem) {
  if (!disconnectQueueItemHasAdmScope(queueItem)) {
    throw disconnectManualError("disconnect_scope_mismatch");
  }
  const captureBlockers = disconnectCaptureBlockers(capture);
  if (captureBlockers.length) throw disconnectManualError(captureBlockers);
  if (!capture.aid) throw disconnectManualError("missing_activity_id");
  if (String(capture.contract || "") !== String(queueItem.contract || "")) {
    throw disconnectManualError("contract_mismatch");
  }
  if (String(capture.scheduled_date || "") !== String(queueItem.date || "")) {
    throw disconnectManualError(
      `scheduled_date_mismatch:${capture.scheduled_date || "ausente"}:${queueItem.date}`,
    );
  }
  if (!disconnectActivityComplete(capture.activity_status)) {
    return {
      waiting: true,
      result: {
        stage: "Aguardando conclusao no TOA",
        appointment: queueItem.window_label,
        technician: capture.assigned_technician?.name || "",
        message: `Status atual no TOA: ${capture.activity_status || "nao informado"}.`,
      },
    };
  }

  const tasks = (capture.tasks || []).filter((task) => String(task.os_number || "").trim());
  if (!tasks.length) throw disconnectManualError("capture_without_tasks");
  const taskNumbers = tasks.map((task) => String(task.os_number));
  if (new Set(taskNumbers).size !== taskNumbers.length) {
    throw disconnectManualError("duplicate_task_os");
  }
  const expectedNumbers = [...new Set((queueItem.os_numbers || []).map(String))].sort();
  const capturedNumbers = [...new Set(taskNumbers)].sort();
  if (
    expectedNumbers.length !== capturedNumbers.length
    || expectedNumbers.some((value, index) => value !== capturedNumbers[index])
  ) {
    throw disconnectManualError(
      `task_os_set_mismatch:${expectedNumbers.join(",")}:${capturedNumbers.join(",")}`,
    );
  }

  const plans = tasks.map((task) => {
    if (!disconnectTaskExecuted(task.status)) {
      throw disconnectManualError(`task_not_executed:${task.os_number}:${task.status || "sem_status"}`);
    }
    const definition = state.closeCodes.find((item) => (
      String(item.code) === String(task.close_code || "")
    ));
    if (!definition) throw disconnectManualError(`unknown_close_code:${task.close_code || "ausente"}`);
    if (definition.requiresObservation) {
      throw disconnectManualError(`close_code_requires_observation:${definition.code}`);
    }
    const order = disconnectExactImperiumMatch(capture, task);
    const service = String(order.service || task.service || "").trim();
    return {
      task,
      order,
      definition,
      num_os: String(task.os_number),
      code: String(definition.code),
      service,
      technician: String(order.installer || capture.assigned_technician?.name || "").trim(),
      capability: disconnectTaskCapability(service),
      installed_equipment: [],
      removed_equipment: [],
      materials: [],
    };
  });

  const installed = disconnectEquipmentDraft(capture.installed_equipment);
  const removed = disconnectEquipmentDraft(capture.removed_equipment);
  const materialDraft = disconnectAutomationMaterialDraft(capture.materials);
  const materials = materialDraft.materials;

  const consolidation = disconnectConsolidateStreamingPackage(plans, installed, removed);
  const submissionPlans = consolidation?.plans || plans;
  if (!consolidation) {
    disconnectRouteEquipment(submissionPlans, installed, "installed");
    disconnectRouteEquipment(submissionPlans, removed, "removed");
  }
  if (materials.length) {
    const preferred = submissionPlans.filter((plan) => (
      plan.code === "409"
      && plan.capability === "material_capable"
      && !normalize(plan.service).includes("STREAM")
    ));
    const eligible = preferred.length === 1
      ? preferred
      : submissionPlans.filter(
        (plan) => plan.code === "409" && plan.capability === "material_capable",
      );
    if (eligible.length !== 1) throw disconnectManualError("material_target_ambiguous");
    eligible[0].materials.push(...materials);
  }
  submissionPlans.forEach((plan) => {
    if (plan.capability === "close_only" && (
      plan.installed_equipment.length || plan.removed_equipment.length || plan.materials.length
    )) {
      throw disconnectManualError(`inventory_in_close_only:${plan.num_os}`);
    }
    if (plan.code === "430" && plan.installed_equipment.length) {
      throw disconnectManualError(`installed_equipment_in_430:${plan.num_os}`);
    }
    if (!["409", "430"].includes(plan.code) && (
      plan.installed_equipment.length || plan.removed_equipment.length || plan.materials.length
    )) {
      throw disconnectManualError(`inventory_not_allowed_for_code:${plan.code}`);
    }
    if (plan.code === "430" && plan.removed_equipment.length === 0) {
      throw disconnectManualError(`430_without_removed_equipment:${plan.num_os}`);
    }
  });

  return {
    waiting: false,
    plans: submissionPlans,
    warnings: [
      ...(capture.validation_warnings || []).map(String),
      ...(consolidation?.skipped || []).map(
        (item) => `${item.reason}:${item.num_os}`,
      ),
      ...(materialDraft.ignored.length
        ? [`ignored_disconnect_materials:${materialDraft.ignored.length}`]
        : []),
    ],
    result: {
      stage: "Dados validados; pronto para enviar",
      appointment: queueItem.window_label,
      technician: capture.assigned_technician?.name || plans[0]?.technician || "",
      plans: submissionPlans.map((plan) => ({
        num_os: plan.num_os,
        code: plan.code,
        service: plan.service,
        technician: plan.technician,
        capability: plan.capability,
        installed_equipment: plan.installed_equipment,
        removed_equipment: plan.removed_equipment,
        materials: plan.materials,
      })),
      message: materialDraft.ignored.length
        ? `${submissionPlans.length} OS validadas; ${materialDraft.ignored.length} miscelaneas ignoradas pela regra de desconexao.`
        : `${submissionPlans.length} OS validadas antes do primeiro envio.`,
      ignored_materials: materialDraft.ignored,
      materials_not_applicable: true,
      skipped_open_orders: consolidation?.skipped || [],
    },
  };
}

async function updateDisconnectClaim(claim, status, options = {}) {
  const payload = await disconnectAutomationRequest("update", {
    contract: claim.item.contract,
    lease_token: claim.lease_token,
    status,
    result: options.result || {},
    error: options.error || "",
    reasons: options.reasons || [],
  });
  return payload;
}

async function processDisconnectClaim(claim) {
  const item = claim.item;
  let startedSubmitting = false;
  const submitted = [];
  try {
    const lookup = await request(apiUrl("/api/toa-live/lookup"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contract: item.contract,
        expected_profile_key: "natal",
      }),
      timeoutMs: 300000,
    });
    state.toaLiveStatus = lookup.session || state.toaLiveStatus;
    renderToaLiveStatus();
    if (lookup.profile !== "natal") throw disconnectManualError("shared_state_contamination");
    const captures = (lookup.results || []).filter((capture) => (
      String(capture.contract || "") === String(item.contract || "")
    ));
    if (captures.length !== 1) {
      throw disconnectManualError(`capture_count:${captures.length}`);
    }
    const built = disconnectBuildPlans(captures[0], item);
    if (built.waiting) {
      await updateDisconnectClaim(claim, "waiting_toa", { result: built.result });
      return;
    }

    const progress = {
      ...built.result,
      stage: "Iniciando envio validado",
      submitted_os: [],
    };
    if (state.disconnectAutomationStopRequested) {
      progress.stage = "Pausada antes do envio";
      progress.message = "Contrato validado e salvo; nenhuma OS foi enviada.";
      await updateDisconnectClaim(claim, "ready", {
        result: progress,
        reasons: built.warnings,
      });
      return;
    }
    await updateDisconnectClaim(claim, "submitting", {
      result: progress,
      reasons: built.warnings,
    });
    startedSubmitting = true;

    let pendingConfirmation = false;
    for (const plan of built.plans) {
      progress.current_os = plan.num_os;
      progress.current_code = plan.code;
      progress.current_service = plan.service;
      progress.stage = `Enviando OS ${plan.num_os}`;
      progress.message = `Codigo ${plan.code} | ${plan.service}`;
      await updateDisconnectClaim(claim, "submitting", { result: progress });
      const hasDataSnap = Boolean(state.authUser?.imperium_identities?.[state.profile]);
      const transport = (
        (state.activeModule === "close" && elements.closeTransport?.value)
        || (state.officialCloseEnabled ? "official_http" : (hasDataSnap ? "datasnap" : "official_http"))
      );
      const response = await submitClose(plan.order, plan.definition, {
        transport,
        installed_equipment: plan.installed_equipment,
        removed_equipment: plan.removed_equipment,
        materials: plan.materials,
        scheduled_date: item.date,
        live_capture_aid: captures[0].aid,
      });
      submitted.push(plan.num_os);
      progress.submitted_os = [...submitted];
      progress.message = response?.pending_confirmation
        ? `OS ${plan.num_os} recebida pela API; aguardando retorno do Imperium.`
        : `OS ${plan.num_os} concluida pelo canal selecionado.`;
      pendingConfirmation = pendingConfirmation || Boolean(response?.pending_confirmation);
      await updateDisconnectClaim(claim, "submitting", { result: progress });
    }

    progress.stage = pendingConfirmation ? "Aguardando confirmacao do Imperium" : "Concluida";
    progress.message = pendingConfirmation
      ? `${submitted.length} OS enviadas uma unica vez; sem repeticao automatica.`
      : `${submitted.length} OS concluidas.`;
    await updateDisconnectClaim(
      claim,
      pendingConfirmation ? "awaiting_confirmation" : "completed",
      { result: progress },
    );
  } catch (error) {
    const reasons = error.disconnectReasons || [];
    const result = {
      ...(claim.item.result || {}),
      stage: startedSubmitting ? "Falha depois do inicio do envio" : "Tratativa humana",
      submitted_os: submitted,
      message: error.message,
    };
    if (!startedSubmitting && disconnectTransientToaError(error)) {
      result.stage = "TOA temporariamente indisponivel";
      result.message = (
        "A sessao oscilou durante a consulta. A fila foi pausada e o "
        + "contrato continuara salvo para uma nova tentativa manual."
      );
      await updateDisconnectClaim(
        claim,
        "waiting_toa",
        { result, error: error.message, reasons },
      );
      await autoPauseDisconnectAutomation();
      console.warn(`Consulta TOA pausada para o contrato ${item.contract}`, error);
      return;
    }
    await updateDisconnectClaim(
      claim,
      startedSubmitting ? "failed" : "manual_review",
      { result, error: error.message, reasons },
    );
    console.error(`Falha no contrato automatico ${item.contract}`, error);
  }
}

async function runDisconnectAutomation() {
  if (state.disconnectAutomationWorker || state.profile !== "natal") return;
  state.disconnectAutomationWorker = true;
  renderDisconnectAutomation();
  try {
    while (
      !state.disconnectAutomationStopRequested
      && state.disconnectAutomation?.status === "running"
    ) {
      await loadToaLiveStatus({ quiet: true });
      if (!state.disconnectToaHealthy) {
        await autoPauseDisconnectAutomation();
        break;
      }
      const claim = await disconnectAutomationRequest("claim", {});
      if (claim.claimed) {
        await processDisconnectClaim(claim);
        continue;
      }
      if (claim.state?.status !== "running") break;
      await sleep(10000);
      await loadDisconnectAutomation({ quiet: true });
    }
  } catch (error) {
    showToast(error.message, "error");
    console.error("Worker da automacao de desconexao interrompido", error);
    await autoPauseDisconnectAutomation();
  } finally {
    state.disconnectAutomationWorker = false;
    renderDisconnectAutomation();
  }
}

// =============================================================================
// TOA | LOGIN, CONECTIVIDADE E RECUPERACAO DA SESSAO
// =============================================================================
function closeToaLoginDialog() {
  elements.toaLoginUsername.value = "";
  elements.toaLoginPassword.value = "";
  elements.toaLoginError.textContent = "";
  elements.toaLoginError.classList.add("hidden");
  if (elements.toaLoginDialog.open) elements.toaLoginDialog.close();
}

function openToaLoginDialog() {
  elements.toaLoginError.classList.add("hidden");
  elements.toaLoginDialog.showModal();
  elements.toaLoginUsername.focus();
}

async function connectToaLive(event) {
  event.preventDefault();
  if (state.toaLiveConnecting) return;
  const username = elements.toaLoginUsername.value.trim();
  const password = elements.toaLoginPassword.value;
  const accessMode = new FormData(elements.toaLoginForm).get("toa_access_mode") || "direct";
  if (!username || !password) {
    elements.toaLoginError.textContent = "Informe usuario e senha.";
    elements.toaLoginError.classList.remove("hidden");
    return;
  }
  state.toaLiveConnecting = true;
  elements.toaLoginSubmit.disabled = true;
  elements.toaLoginError.classList.add("hidden");
  renderToaLiveStatus();
  try {
    state.toaLiveStatus = await request("/api/toa-live/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, access_mode: accessMode }),
      timeoutMs: 180000,
    });
    closeToaLoginDialog();
    showToast(
      accessMode === "duo"
        ? "TOA aberto pelo acesso com DUO."
        : "TOA aberto pelo acesso direto/token.",
      "success",
    );
  } catch (error) {
    elements.toaLoginPassword.value = "";
    elements.toaLoginError.textContent = error.message;
    elements.toaLoginError.classList.remove("hidden");
  } finally {
    state.toaLiveConnecting = false;
    elements.toaLoginSubmit.disabled = false;
    renderToaLiveStatus();
  }
}

function toaLiveSerialLooksLikeChip(serial) {
  // ICCID de chip e um identificador exclusivamente numerico e muito maior
  // que os seriais comuns de decoder/EMTA. Mantenha-o sempre como string:
  // converter para Number perderia precisao nos ultimos digitos.
  return /^\d{18,25}$/.test(String(serial || "").trim());
}

function toaLiveEquipmentType(item) {
  const label = normalize(`${item.type || ""} ${item.description || ""}`);
  const serial = String(item.serial || "").trim().toUpperCase();
  if (label.includes("CHIP") || label.includes("SIMCARD") || label.includes("SIM CARD")) return "chip";
  if (toaLiveSerialLooksLikeChip(serial)) return "chip";
  if (label.includes("SMART")) return "smart";
  if (label.includes("EMTA") || label.includes("MODEM") || label.includes("DOCSIS")) return "emta";
  if (label.includes("DECODER") || label.includes("DECO")) return "decoder";
  if (/^[0-9A-F]{12}$/i.test(serial)) return "emta";
  if (/^\d+$/.test(serial)) return "decoder";
  return "auto";
}

function toaLiveEquipmentDraft(items, order, contractOrders = []) {
  const rawValues = (items || [])
    .filter((item) => String(item.serial || "").trim())
    .map((item) => ({
      serial: String(item.serial || "").trim().toUpperCase(),
      type: toaLiveEquipmentType(item),
    }));
  const seenSerials = new Set();
  const values = [];
  for (const item of rawValues) {
    if (!seenSerials.has(item.serial)) {
      seenSerials.add(item.serial);
      values.push(item);
    }
  }
  if (!values.length) return [];
  const expected = expectedEquipmentType(order?.service || "");
  const matching = expected
    ? values.filter((item) => {
        if (expected === "decoder") return item.type === "decoder" || item.type === "smart";
        return item.type === expected;
      })
    : values;
  if (!matching.length) return expected ? [] : values;

  const activeOrders = (contractOrders && contractOrders.length)
    ? contractOrders
    : (state.orders || []).filter((item) => String(item.contract) === String(order?.contract));

  const matchingContractOrders = activeOrders
    .filter((item) => (expected ? expectedEquipmentType(item.service) === expected : !isNoEquipmentService(item.service)))
    .sort((a, b) => Number(a.id_os || 0) - Number(b.id_os || 0));

  if (matchingContractOrders.length <= 1) {
    return matching;
  }

  const osIndex = matchingContractOrders.findIndex(
    (item) => String(item.num_os) === String(order?.num_os) || Number(item.id_os) === Number(order?.id_os),
  );
  if (osIndex < 0) return matching;

  const itemsPerOS = Math.ceil(matching.length / matchingContractOrders.length);
  const start = osIndex * itemsPerOS;
  const end = Math.min(matching.length, (osIndex + 1) * itemsPerOS);
  return matching.slice(start, end);
}

function toaLiveMaterialsDraft(items) {
  return (items || [])
    .map((item) => {
      const identity = toaLiveMaterialIdentity(item);
      return {
        code: identity.code,
        description: identity.description,
        quantity: Number(item.used_quantity ?? item.quantity ?? 0),
        ignored: identity.ignored,
      };
    })
    .filter((item) => !item.ignored)
    .filter((item) => item.code && item.quantity > 0);
}

function toaLiveImperiumMatch(capture, task) {
  const matches = capture?.imperium_matches || [];
  const exact = matches.find((order) => String(order.num_os) === String(task?.os_number));
  if (exact) return exact;
  return (state.orders || []).find((order) =>
    String(order.num_os) === String(task?.os_number)
    && String(order.contract) === String(capture?.contract)
  ) || null;
}

function operationDraftKey(order) {
  const identity = order?.operation_identity || {};
  if (
    identity.project_id && identity.profile_key && identity.city
    && identity.contract && identity.activity_id
  ) {
    return [
      identity.project_id,
      identity.profile_key,
      identity.city,
      identity.contract,
      identity.activity_id,
      order.num_os,
    ].join("|");
  }
  return `blocked:${state.profile}:${order?.id_os || ""}`;
}

function isNoEquipmentService(service) {
  const norm = normalize(service || "");
  return (
    norm.includes("ASSINATURA")
    || norm.includes("PORTABILIDADE")
    || norm.includes("CABO GPON")
    || norm.includes("INSTALACAO DE CABO")
    || norm.includes("INSTALACAO CABO")
    || norm.includes("PASSAGEM DE CABO")
    || norm.includes("LANCAMENTO DE CABO")
    || norm.includes("INSTALACAO CABO GPON")
  );
}

function toaLiveMaterialOwnerScore(order) {
  const service = normalize(order?.service || "");
  if (service.includes("ASSINATURA")) return 10;
  if (service.includes("PONTO VIRT") || service.includes("VIRTUA")) return 1000;
  if (service.includes("PONTO VOIP") || service.includes("VOIP")) return 950;
  if (service.includes("INTERNET") || service.includes("EMTA")) return 900;
  if (service.includes("PONTO PRINCIPAL") || service.includes("PRINCIPAL")) return 800;
  if (service.includes("RETORNO CREDENCIADA") || service.includes("RETORNO")) return 600;
  if (service.includes("MANUTENCAO") || service.includes("REPARO") || service.includes("VISITA TECNICA")) return 550;
  if (service.includes("STREAMING") || service.includes("DECODER") || service.includes("TV")) return 500;
  if (service.includes("MUDANCA DE PACOTE")) return 300;
  if (service.includes("MUDANCA DE ENDERECO") || service.includes("TROCA")) return 200;
  if (isNoEquipmentService(service)) return 10;
  return 50;
}

function isToaLiveMaterialOwner(order, contractOrders = []) {
  const currentService = normalize(order?.service || "");
  if (isNoEquipmentService(currentService)) return false;
  if (!contractOrders.length) return true;
  let best = null;
  let bestScore = -1;
  for (const item of contractOrders) {
    const itemService = normalize(item?.service || "");
    if (isNoEquipmentService(itemService)) continue;
    const score = toaLiveMaterialOwnerScore(item);
    if (score > bestScore) {
      bestScore = score;
      best = item;
    }
  }
  if (!best) return false;
  return String(best.num_os || best.id_os) === String(order?.num_os || order?.id_os);
}

function prepareToaLiveClose(
  capture,
  task,
  {
    openEditor = false,
    expectedProfile = state.toaLiveResult?.profile,
  } = {},
) {
  if (expectedProfile !== state.profile) {
    showToast("shared_state_contamination", "error");
    return false;
  }
  if ((capture.operation_blockers || []).length) {
    showToast(capture.operation_blockers.join(" | "), "error");
    return false;
  }
  const match = toaLiveImperiumMatch(capture, task);
  const displayedOrder = match && state.orders.find((item) =>
    Number(item.id_os) === Number(match.id_os)
    && String(item.num_os) === String(match.num_os)
    && String(item.contract) === String(match.contract)
  );
  const currentOrder = displayedOrder && !displayedOrder.read_only
    ? displayedOrder
    : match;
  const importedIdentityMatches = Boolean(
    match?.operation_source === "toa_import"
    && match?.operation_identity?.activity_id
    && String(match.operation_identity.activity_id) === String(capture.aid || "")
    && match?.import_scope?.source_hash
  );
  const order = currentOrder && {
    ...currentOrder,
    operation_source: importedIdentityMatches ? "toa_import" : (currentOrder.operation_source || "imperium_cache"),
    operation_identity: importedIdentityMatches ? match.operation_identity : currentOrder.operation_identity,
    approved_state_hash: currentOrder.approved_state_hash || match.approved_state_hash,
    import_scope: importedIdentityMatches ? match.import_scope : currentOrder.import_scope,
    manual_scope: importedIdentityMatches ? undefined : (currentOrder.manual_scope || match.manual_scope),
  };
  const code = String(task.close_code || "").trim();
  const technicianObservation = String(
    capture.technician_observation || capture.observation || "",
  ).trim();
  const definition = state.closeCodes.find((item) => item.code === code);
  if (!order) {
    showToast("A OS correspondente nao esta na lista atual do Imperium. Atualize as ordens.", "error");
    return false;
  }
  if (!definition) {
    showToast(`O codigo ${code || "vazio"} ainda nao esta cadastrado no painel`, "error");
    return false;
  }

  selectCloseWorkspaceOrder(order.id_os);
  elements.closeWorkspaceCode.value = code;
  elements.closeWorkspaceObservation.value = technicianObservation;
  if (definition.productive) {
    const contractOrders = (capture.imperium_matches && capture.imperium_matches.length)
      ? capture.imperium_matches
      : (state.orders || []).filter((item) => String(item.contract) === String(order.contract));
    const service = normalize(order.service);
    const noEquip = isNoEquipmentService(service);
    const installed = noEquip ? [] : toaLiveEquipmentDraft(capture.installed_equipment, order, contractOrders);
    const removed = noEquip ? [] : toaLiveEquipmentDraft(capture.removed_equipment, order, contractOrders);
    const materialOwner = !noEquip && isToaLiveMaterialOwner(order, contractOrders);
    const materials = (closeCodeAllowsMaterials(code) && materialOwner) ? toaLiveMaterialsDraft(capture.materials) : [];
    const movement = noEquip
      ? defaultMovement(order, code)
      : (code === "517" || (installed.length && removed.length)
        ? "swap"
        : (removed.length ? "remove" : defaultMovement(order, code)));
    state.productiveDrafts[operationDraftKey(order)] = {
      code,
      observation: technicianObservation,
      movement,
      installed_equipment: installed,
      removed_equipment: removed,
      materials,
      material_paste: "",
      material_notice: "Dados carregados da consulta ao vivo do TOA",
      // A captura do TOA e por atividade, enquanto a baixa e por OS. Uma chave
      // unica por atividade impede que o mesmo conjunto de materiais seja
      // movimentado novamente por outra tarefa/OS do mesmo atendimento.
      toa_paste_key: materials.length ? String(capture.material_paste_key || "") : "",
      live_capture_aid: capture.aid,
      // Keep the TOA date for audit. The backend uses the current Imperium list
      // date as dataagendamento because the official API locates OS by number + date.
      scheduled_date: String(capture.scheduled_date || "").trim(),
    };
  }
  renderCloseWorkspace();
  if (openEditor) openConfirmation([order], code, {
    observation: technicianObservation,
  });
  elements.closeDetailTitle.scrollIntoView({ block: "center", behavior: "smooth" });
  showToast(`OS ${order.num_os} preparada. Revise os dados antes de confirmar.`, "success");
  return true;
}

const SEMI_AUTO_ROUTE = "NTL-DMV";

function semiAutoCanonicalRoute(value) {
  return normalize(value).replaceAll("_", "-").replace(/\s+/g, "");
}

function semiAutoOrderRoute(order) {
  const direct = String(order.route || order.bucket || "").trim();
  if (direct && direct.includes("DMV")) return semiAutoCanonicalRoute(direct);
  const source = String(
    order.source_file || order.import_scope?.source_file || "",
  ).split(/[\\/]/).pop();
  const match = source.match(/^Atividades-(.+?)_\d{2}_\d{2}_\d{2}(?:\s*\(\d+\))?\.(?:csv|xlsx)$/i);
  return semiAutoCanonicalRoute(match?.[1] || "");
}

function semiAutoWindow(value) {
  const text = String(value || "").trim();
  const times = [...text.matchAll(/(?:^|\D)([0-2]?\d)(?::([0-5]\d))?(?=\D|$)/g)]
    .map((match) => {
      const hour = Number(match[1]);
      const minute = Number(match[2] || 0);
      return hour <= 24 && (hour < 24 || minute === 0)
        ? hour * 60 + minute
        : null;
    })
    .filter((value) => value !== null);
  if (times.length < 2) {
    return { start: 1440, end: 1440, label: text || "Sem janela" };
  }
  const [start, end] = times;
  return { start, end, label: text };
}

function semiAutoOrderWindow(order) {
  return semiAutoWindow(
    order.service_window || order.time_window || order.operational_window || "",
  );
}

function semiAutoOrderKey(order) {
  const osNumber = String(order?.num_os || order?.os_number || "").replace(/\D/g, "");
  const contract = String(order?.contract || "").replace(/\D/g, "");
  return osNumber && contract ? `${osNumber}:${contract}` : "";
}

function semiAutoEnrichOrders(orders, contextOrders) {
  const contexts = new Map();
  (contextOrders || []).forEach((context) => {
    const key = semiAutoOrderKey(context);
    if (!key) return;
    const current = contexts.get(key);
    const currentWindow = semiAutoOrderWindow(current || {}).end;
    const candidateWindow = semiAutoOrderWindow(context).end;
    if (!current || (currentWindow >= 1440 && candidateWindow < 1440)) {
      contexts.set(key, context);
    }
  });
  return (orders || []).map((order) => {
    const context = contexts.get(semiAutoOrderKey(order));
    if (!context) return order;
    return {
      ...order,
      route: order.route || context.route || context.bucket || "",
      bucket: order.bucket || context.bucket || context.route || "",
      toa_status: order.toa_status || context.toa_status || context.activity_status || "",
      activity_status: order.activity_status || context.activity_status || context.toa_status || "",
      activity_id: order.activity_id || context.activity_id || "",
      service_window: order.service_window || context.service_window || context.time_window || "",
      time_window: order.time_window || context.time_window || context.service_window || "",
      source_file: order.source_file || context.source_file || "",
      semi_auto_context_source: "toa_datalake",
    };
  });
}

function semiAutoAgendaRecords() {
  return (state.semiAutoAgenda?.records || []).filter((record) => (
    record?.agenda_only && String(record.contract || "").replace(/\D/g, "").length >= 5
  ));
}

function renderSemiAutoAgenda() {
  if (!elements.semiAutoAgendaChoose) return;
  const records = semiAutoAgendaRecords();
  const stats = state.semiAutoAgenda?.stats || {};
  const filename = state.semiAutoAgenda?.filename
    || records[0]?.source_files?.[0]
    || "";
  elements.semiAutoAgendaChoose.disabled = state.semiAutoAgendaLoading || state.semiAutoRunning;
  elements.semiAutoAgendaChoose.querySelector("span").textContent = state.semiAutoAgendaLoading
    ? "Lendo agenda..." : "Carregar agenda CSV/XLSX";
  elements.semiAutoAgendaName.textContent = filename || "Nenhuma agenda carregada";
  elements.semiAutoAgendaContracts.textContent = records.length;
  elements.semiAutoAgendaBlank.textContent = Number(stats.blank_or_invalid_contract || 0);
  elements.semiAutoAgendaNoWindow.textContent = Number(stats.missing_or_invalid_window || 0);
  elements.semiAutoAgendaDuplicates.textContent = Number(stats.duplicate_contract_rows || 0);
  elements.semiAutoAgendaMessage.classList.toggle("success", Boolean(records.length));
  elements.semiAutoAgendaMessage.classList.remove("error");
  elements.semiAutoAgendaMessage.textContent = records.length
    ? `${records.length} contrato(s) guardados por janela. A esteira consultará o Imperium antes do TOA.`
    : "Selecione a fotografia de atividades do dia para montar a ordem das pesquisas.";
}

async function loadSemiAutoAgenda({ quiet = true } = {}) {
  try {
    const date = elements.date.value;
    const payload = await request(apiUrl(
      `/api/toa-contracts?profile=${encodeURIComponent(state.profile)}&date=${encodeURIComponent(date)}`,
    ), { timeoutMs: 30000 });
    state.semiAutoAgenda = {
      records: (payload.records || []).filter((record) => record.agenda_only),
      filename: (payload.records || []).find((record) => record.agenda_only)?.source_files?.[0] || "",
      stats: {},
    };
  } catch (error) {
    state.semiAutoAgenda = null;
    if (!quiet) showToast(`Nao foi possivel carregar a agenda: ${error.message}`, "error");
  } finally {
    renderSemiAutoAgenda();
    renderSemiAutoQueue();
  }
}

async function importSemiAutoAgenda(file) {
  if (!file || state.semiAutoAgendaLoading) return;
  state.semiAutoAgendaLoading = true;
  renderSemiAutoAgenda();
  try {
    const payload = await request(apiUrl("/api/toa-agenda/import"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: state.profile,
        date: elements.date.value,
        filename: file.name,
        content_base64: await fileAsBase64(file),
      }),
      timeoutMs: 180000,
    });
    const records = (payload.contracts || []).map((record) => ({
      ...record,
      agenda_only: true,
      windows: record.window ? [record.window] : [],
      source_files: [payload.filename || file.name],
    }));
    state.semiAutoAgenda = {
      records,
      filename: payload.filename || file.name,
      stats: payload.stats || {},
    };
    state.semiAutoJobs = [];
    showToast(`${records.length} contrato(s) carregados e ordenados por janela.`, "success");
  } catch (error) {
    state.semiAutoAgenda = null;
    elements.semiAutoAgendaMessage.classList.add("error");
    elements.semiAutoAgendaMessage.textContent = error.message;
    showToast(`Agenda rejeitada: ${error.message}`, "error");
  } finally {
    state.semiAutoAgendaLoading = false;
    elements.semiAutoAgendaFile.value = "";
    renderSemiAutoAgenda();
    renderSemiAutoQueue();
  }
}

function semiAutoBuildJobs(agendaRecords, orders, profile) {
  const activeByContract = new Map();
  (orders || []).forEach((order) => {
    const contract = String(order.contract || "").replace(/\D/g, "");
    if (contract.length < 5) return;
    const list = activeByContract.get(contract) || [];
    list.push(order);
    activeByContract.set(contract, list);
  });
  const jobs = (agendaRecords || []).map((record) => {
    const contract = String(record.contract || "").replace(/\D/g, "");
    const activeOrders = activeByContract.get(contract) || [];
    const parsedWindow = semiAutoWindow(record.window || record.windows?.[0] || "");
    const windowStart = Number.isFinite(Number(record.window_start))
      ? Number(record.window_start) : parsedWindow.start;
    const windowEnd = Number.isFinite(Number(record.window_end))
      ? Number(record.window_end) : parsedWindow.end;
    const osNumbers = [...new Set(activeOrders.map((order) => (
      String(order.num_os || order.os_number || "").replace(/\D/g, "")
    )).filter(Boolean))];
    const activityIds = [...new Set(activeOrders.map((order) => (
      String(order.activity_id || "").trim()
    )).filter(Boolean))];
    let jobState = "pending";
    let message = "";
    let skipCategory = "";
    let skipTitle = "";
    let skipDetail = "";
    if (windowStart >= 1440 || windowEnd >= 1440) {
      jobState = "skipped";
      skipCategory = "agenda_invalid";
      skipTitle = "Janela Inválida";
      skipDetail = "Janela horária não reconhecida na agenda; TOA não consultado.";
      message = skipDetail;
    }
    return {
      contract,
      profile,
      route: SEMI_AUTO_ROUTE,
      windowStart,
      windowEnd,
      windowLabel: record.window || record.windows?.[0] || parsedWindow.label,
      originalWindowStart: windowStart,
      originalWindowEnd: windowEnd,
      originalWindowLabel: record.window || record.windows?.[0] || parsedWindow.label,
      windowOverrideMode: "",
      windowOverrideAt: 0,
      osNumbers,
      activityIds,
      agendaWindow: true,
      activeOrderCount: activeOrders.length,
      imperiumSeen: activeOrders.length > 0,
      sourceRows: record.source_rows || [],
      state: jobState,
      payload: null,
      candidates: [],
      message,
      skipCategory,
      skipTitle,
      skipDetail,
    };
  });
  return jobs.sort(semiAutoCompareJobs);
}

function semiAutoCompareJobs(left, right) {
  const leftForced = left?.windowOverrideMode === "now" ? 1 : 0;
  const rightForced = right?.windowOverrideMode === "now" ? 1 : 0;
  if (leftForced !== rightForced) return rightForced - leftForced;
  if (leftForced && Number(left?.windowOverrideAt || 0) !== Number(right?.windowOverrideAt || 0)) {
    return Number(right?.windowOverrideAt || 0) - Number(left?.windowOverrideAt || 0);
  }
  return (
    Number(left?.windowEnd ?? 1440) - Number(right?.windowEnd ?? 1440)
    || Number(left?.windowStart ?? 1440) - Number(right?.windowStart ?? 1440)
    || String(left?.contract || "").localeCompare(String(right?.contract || ""), "pt-BR", { numeric: true })
  );
}

function semiAutoOriginalWindowKey(job) {
  const start = Number(job?.originalWindowStart ?? job?.windowStart ?? 1440);
  const end = Number(job?.originalWindowEnd ?? job?.windowEnd ?? 1440);
  const label = String(job?.originalWindowLabel || job?.windowLabel || "").trim();
  return `${start}:${end}:${label}`;
}

function semiAutoJobDueNow(job, now = new Date()) {
  if (!job || job.windowStart >= 1440 || job.windowEnd >= 1440) return false;
  if (job.windowOverrideMode === "now") return true;
  return job.windowStart <= now.getHours() * 60 + now.getMinutes();
}

function semiAutoReconcileJobsWithOrders(orders) {
  const activeByContract = new Map();
  (orders || []).forEach((order) => {
    const contract = String(order.contract || "").replace(/\D/g, "");
    if (!contract) return;
    const list = activeByContract.get(contract) || [];
    list.push(order);
    activeByContract.set(contract, list);
  });
  state.semiAutoJobs.forEach((job) => {
    const activeOrders = activeByContract.get(String(job.contract || "")) || [];
    const activeNumbers = new Set(activeOrders.map((order) => (
      String(order.num_os || order.os_number || "").replace(/\D/g, "")
    )));
    job.osNumbers = [...activeNumbers];
    if (!activeOrders.length) {
      job.candidates = [];
      if (!job.imperiumSeen || job.skipCategory === "awaiting_imperium_import") return;
      job.state = "skipped";
      job.skipCategory = "imperium_closed";
      job.skipTitle = "OS Já Finalizada";
      job.skipDetail = "OS não está mais em campo no Imperium; contrato retirado da esteira.";
      job.message = job.skipDetail;
      return;
    }
    job.imperiumSeen = true;
    if (
      job.state === "skipped"
      && ["imperium_no_os", "awaiting_imperium_import"].includes(job.skipCategory)
    ) {
      job.state = "pending";
      job.skipCategory = "";
      job.skipTitle = "";
      job.skipDetail = "";
      job.message = "OS apareceu no Imperium; retomando baixa automática";
    }
    const windows = job.agendaWindow ? [] : activeOrders
      .map(semiAutoOrderWindow)
      .filter((window) => window.start < 1440 && window.end < 1440)
      .sort((left, right) => left.end - right.end || left.start - right.start);
    if (windows.length) {
      const [window] = windows;
      job.windowStart = window.start;
      job.windowEnd = window.end;
      job.windowLabel = window.label;
      if (
        job.state === "skipped"
        && String(job.message || "").startsWith("Janela nao informada")
      ) {
        job.state = "pending";
        job.message = "";
      }
    }
    if (job.candidates?.length) {
      job.candidates = job.candidates.filter((candidate) => activeNumbers.has(
        String(candidate.numOs || "").replace(/\D/g, ""),
      ));
      if (job.state === "ready" && !job.candidates.length) {
        job.state = "skipped";
        job.message = "As OS preparadas ja sairam de campo no Imperium";
      }
    }
  });
  state.semiAutoJobs.sort(semiAutoCompareJobs);
}

function semiAutoWindowGroups() {
  const groups = new Map();
  state.semiAutoJobs.forEach((job) => {
    const key = semiAutoOriginalWindowKey(job);
    const start = Number(job.originalWindowStart ?? job.windowStart ?? 1440);
    const end = Number(job.originalWindowEnd ?? job.windowEnd ?? 1440);
    const label = String(job.originalWindowLabel || job.windowLabel || "Janela não informada");
    const group = groups.get(key) || { key, start, end, label, jobs: [] };
    group.jobs.push(job);
    groups.set(key, group);
  });
  return [...groups.values()].sort((left, right) => (
    left.end - right.end || left.start - right.start || left.label.localeCompare(right.label, "pt-BR")
  ));
}

function semiAutoPrioritizeWindowNow(groupKey) {
  const timestamp = Date.now();
  let changed = 0;
  state.semiAutoJobs.forEach((job) => {
    if (semiAutoOriginalWindowKey(job) !== groupKey) return;
    const retryableSkip = ["awaiting_imperium_import", "toa_pending"].includes(job.skipCategory);
    if (!["pending", "searching"].includes(job.state) && !retryableSkip) return;
    job.windowOverrideMode = "now";
    job.windowOverrideAt = timestamp;
    changed += 1;
  });
  if (!changed) return false;
  state.semiAutoJobs.sort(semiAutoCompareJobs);
  state.semiAutoWaitingWindow = "";
  renderSemiAutoQueue();
  showToast(`${changed} contrato(s) da janela selecionada foram priorizados para agora.`, "success");
  return true;
}

function semiAutoRestoreWindow(groupKey) {
  let changed = 0;
  state.semiAutoJobs.forEach((job) => {
    if (semiAutoOriginalWindowKey(job) !== groupKey || job.windowOverrideMode !== "now") return;
    job.windowOverrideMode = "";
    job.windowOverrideAt = 0;
    changed += 1;
  });
  if (!changed) return false;
  state.semiAutoJobs.sort(semiAutoCompareJobs);
  renderSemiAutoQueue();
  showToast("Janela restaurada para o horário original da agenda.", "info");
  return true;
}

function renderSemiAutoWindowControl() {
  if (!elements.semiAutoWindowList || !elements.semiAutoWindowStatus) return;
  const groups = semiAutoWindowGroups();
  if (!groups.length) {
    elements.semiAutoWindowStatus.textContent = "Aguardando fila";
    elements.semiAutoWindowList.innerHTML = '<div class="semi-auto-window-empty">As janelas aparecerão aqui quando a agenda for iniciada.</div>';
    return;
  }

  const currentJob = state.semiAutoJobs.find((job) => String(job.contract) === String(state.semiAutoCurrentContract));
  const currentKey = currentJob ? semiAutoOriginalWindowKey(currentJob) : "";
  const currentGroup = groups.find((group) => group.key === currentKey);
  if (currentJob && currentGroup) {
    const position = currentGroup.jobs.indexOf(currentJob) + 1;
    elements.semiAutoWindowStatus.textContent = `Consultando ${currentGroup.label} · contrato ${position}/${currentGroup.jobs.length}`;
  } else {
    const forced = groups.find((group) => group.jobs.some((job) => job.windowOverrideMode === "now"));
    elements.semiAutoWindowStatus.textContent = forced
      ? `Prioridade manual: ${forced.label}`
      : "Ordem automática por horário da agenda";
  }

  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  elements.semiAutoWindowList.innerHTML = groups.map((group, index) => {
    const consulted = group.jobs.filter((job) => Boolean(job.payload)).length;
    const activeRemaining = group.jobs.filter((job) => ["pending", "searching"].includes(job.state)).length;
    const waitingToa = group.jobs.filter((job) => job.skipCategory === "toa_pending").length;
    const waitingImport = group.jobs.filter((job) => job.skipCategory === "awaiting_imperium_import").length;
    const remaining = activeRemaining + waitingToa + waitingImport;
    const forced = group.jobs.some((job) => job.windowOverrideMode === "now");
    const active = group.key === currentKey;
    const naturallyDue = group.start < 1440 && group.start <= nowMinutes;
    const actionable = activeRemaining > 0;
    const operationalLabel = forced ? "PRIORIZADA AGORA" : active ? "EM CONSULTA" : naturallyDue ? "LIBERADA" : "AGUARDANDO";
    return `
      <div class="semi-auto-window-row ${forced ? "is-forced" : ""} ${active ? "is-active" : ""}">
        <div class="semi-auto-window-main">
          <strong><i data-lucide="clock-3" aria-hidden="true"></i> ${escapeHtml(group.label)}</strong>
          <span>${group.jobs.length} contrato(s) · ${consulted} consultado(s) · ${remaining} restante(s)${waitingToa ? ` · ${waitingToa} pendente(s) TOA` : ""}${waitingImport ? ` · ${waitingImport} aguardando Imperium` : ""}</span>
        </div>
        <span class="semi-auto-window-state">${operationalLabel}</span>
        <div class="semi-auto-window-actions">
          ${forced
            ? `<button class="button secondary compact" type="button" data-window-restore="${index}">Restaurar horário</button>`
            : active
              ? '<button class="button secondary compact" type="button" disabled>Em consulta</button>'
              : `<button class="button secondary compact" type="button" data-window-now="${index}" ${!actionable ? "disabled" : ""}>${naturallyDue ? "Priorizar" : "Atuar agora"}</button>`}
        </div>
      </div>`;
  }).join("");

  elements.semiAutoWindowList.querySelectorAll("[data-window-now]").forEach((button) => {
    button.addEventListener("click", () => {
      const group = groups[Number(button.dataset.windowNow)];
      if (group) semiAutoPrioritizeWindowNow(group.key);
    });
  });
  elements.semiAutoWindowList.querySelectorAll("[data-window-restore]").forEach((button) => {
    button.addEventListener("click", () => {
      const group = groups[Number(button.dataset.windowRestore)];
      if (group) semiAutoRestoreWindow(group.key);
    });
  });
}

async function semiAutoRefreshActiveOrders({ announce = false } = {}) {
  if (state.semiAutoRefreshing) return false;
  const profile = state.profile;
  const epoch = state.profileEpoch;
  state.semiAutoRefreshing = true;
  renderSemiAutoQueue();
  try {
    const date = elements.date.value;
    const payload = await request(apiUrl(
      `/api/orders?date=${encodeURIComponent(date)}&status=field&service_type=all`,
    ), { timeoutMs: 180000 });
    if (profile !== state.profile || epoch !== state.profileEpoch) return false;
    if (payload.stale) {
      state.monitorSnapshotStale = true;
      if (announce) showToast(
        "O Imperium devolveu uma lista em cache. Aguarde a operacao atual terminar para iniciar a esteira.",
        "warning",
      );
      return false;
    }
    let contextOrders = [];
    try {
      const [context, registry] = await Promise.all([
        request(apiUrl(
          `/api/toa-datalake/feed?profile=${encodeURIComponent(profile)}&date=${encodeURIComponent(date)}`,
        ), { timeoutMs: 30000 }).catch((error) => {
          console.warn("Datalake TOA indisponivel para a esteira", error);
          return { orders: [] };
        }),
        request(apiUrl(
          `/api/toa-contracts?profile=${encodeURIComponent(profile)}&date=${encodeURIComponent(date)}`,
        ), { timeoutMs: 30000 }).catch((error) => {
          console.warn("Agenda CSV persistida indisponivel para a esteira", error);
          return { records: [] };
        }),
      ]);
      const registryOrders = (registry.records || []).flatMap((record) => {
        if (Array.isArray(record.orders) && record.orders.length) return record.orders;
        if ((record.windows || []).length !== 1) return [];
        return (record.os_numbers || []).map((osNumber) => ({
          contract: record.contract,
          os_number: osNumber,
          num_os: osNumber,
          time_window: record.windows[0],
          service_window: (record.service_windows || [])[0] || "",
          source_file: (record.source_files || [])[0] || "",
        }));
      });
      contextOrders = [...(context.orders || []), ...registryOrders];
    } catch (error) {
      console.warn("Contexto local de janelas do TOA indisponivel", error);
    }
    state.orders = semiAutoEnrichOrders(payload.orders || [], contextOrders);
    state.monitorSnapshotStale = false;
    state.monitorLastUpdatedAt = new Date().toISOString();
    state.semiAutoLastImperiumCheckAt = Date.now();
    state.semiAutoJobsSinceImperiumCheck = 0;
    if (state.semiAutoJobs.length) semiAutoReconcileJobsWithOrders(state.orders);
    render();
    return true;
  } catch (error) {
    state.monitorSnapshotStale = true;
    if (announce) showToast(`Nao foi possivel confirmar as OS em campo: ${error.message}`, "error");
    return false;
  } finally {
    state.semiAutoRefreshing = false;
    renderSemiAutoQueue();
  }
}

async function semiAutoWakeAwaitingImperiumImports() {
  const waitingContracts = new Set(
    state.semiAutoJobs
      .filter((job) => job.state === "skipped" && job.skipCategory === "awaiting_imperium_import")
      .map((job) => String(job.contract || "")),
  );
  if (!waitingContracts.size || state.semiAutoProfile !== state.profile) return 0;

  const refreshed = await semiAutoRefreshActiveOrders();
  if (!refreshed) return 0;

  const resumed = state.semiAutoJobs.filter((job) => (
    waitingContracts.has(String(job.contract || "")) && job.state === "pending"
  ));
  if (!resumed.length) return 0;

  showToast(
    `${resumed.length} contrato(s) aguardando importacao apareceram no Imperium e voltaram para a esteira.`,
    "success",
  );
  if (!state.semiAutoStopRequested && !state.semiAutoWorker) {
    state.semiAutoPaused = false;
    state.semiAutoRunning = true;
    void runSemiAutoQueue();
  }
  return resumed.length;
}

function semiAutoNeedsImperiumRefresh() {
  return (
    state.semiAutoJobsSinceImperiumCheck >= 20
    || Date.now() - state.semiAutoLastImperiumCheckAt >= 180000
  );
}

function semiAutoPendingConfirmationCandidates() {
  return state.semiAutoJobs.flatMap((job) => job.candidates || [])
    .filter((candidate) => candidate.pending);
}

const SEMI_AUTO_TOA_RETRY_MS = 5 * 60 * 1000;

function semiAutoScheduleToaRetry(job, now = Date.now()) {
  if (!job || job.skipCategory !== "toa_pending") return false;
  job.toaRetryCount = Number(job.toaRetryCount || 0) + 1;
  job.toaRetryAt = now + SEMI_AUTO_TOA_RETRY_MS;
  return true;
}

function semiAutoPromoteDueToaRetries(now = Date.now()) {
  let promoted = 0;
  state.semiAutoJobs.forEach((job) => {
    if (
      job.state !== "skipped"
      || job.skipCategory !== "toa_pending"
      || !Number(job.toaRetryAt)
      || Number(job.toaRetryAt) > now
    ) return;
    job.state = "pending";
    job.message = "Reconsultando atividade pendente no TOA";
    job.skipTitle = "";
    job.skipDetail = "";
    job.toaRetryAt = 0;
    promoted += 1;
  });
  return promoted;
}

function semiAutoNextToaRetryAt() {
  const retries = state.semiAutoJobs
    .filter((job) => job.state === "skipped" && job.skipCategory === "toa_pending" && Number(job.toaRetryAt) > 0)
    .map((job) => Number(job.toaRetryAt));
  return retries.length ? Math.min(...retries) : 0;
}

function semiAutoMarkCandidateConfirmed(candidate, record = null) {
  if (!candidate || candidate.closed) return false;
  candidate.pending = false;
  candidate.closed = true;
  candidate.reviewed = true;
  candidate.humanReview = false;
  candidate.humanReviewReason = "";
  candidate.confirmedByImperium = true;
  candidate.confirmationState = "confirmed";
  candidate.confirmationDetail = String(record?.detail || record?.message || "").trim();
  if (!candidate.autoCloseCounted) {
    candidate.autoCloseCounted = true;
    state.autoCloseCount = (state.autoCloseCount || 0) + 1;
  }
  return true;
}

function semiAutoMarkCandidateUncertain(candidate, record = null) {
  if (!candidate || !candidate.pending) return false;
  candidate.pending = false;
  candidate.closed = false;
  candidate.reviewed = true;
  candidate.confirmedByImperium = false;
  candidate.confirmationState = String(record?.state || "uncertain").trim().toLowerCase() || "uncertain";
  candidate.confirmationDetail = String(record?.detail || "").trim();
  candidate.humanReview = true;
  candidate.humanReviewReason = String(
    record?.message
    || record?.detail
    || "A baixa foi enviada, mas o Imperium não confirmou o encerramento da OS. Não repetir automaticamente.",
  ).trim();
  if (!candidate.humanReviewCounted) {
    candidate.humanReviewCounted = true;
    state.humanReviewCount = (state.humanReviewCount || 0) + 1;
  }
  return true;
}

async function semiAutoRefreshPendingConfirmations() {
  if (state.semiAutoPendingConfirmationWorker) return;
  state.semiAutoPendingConfirmationWorker = true;
  const profile = state.profile;
  const epoch = state.profileEpoch;
  let delay = 1500;
  try {
    while (profile === state.profile && epoch === state.profileEpoch) {
      const pendingCandidates = semiAutoPendingConfirmationCandidates();
      if (!pendingCandidates.length) return;
      await sleep(delay);
      delay = delay < 3000 ? 3000 : delay < 6000 ? 6000 : delay < 12000 ? 12000 : 15000;
      if (profile !== state.profile || epoch !== state.profileEpoch) return;
      try {
        const date = elements.date.value || localDate();
        const reportPayload = await request(
          apiUrl(`/api/close-report?date=${encodeURIComponent(date)}`),
          { timeoutMs: 60000 },
        );
        const records = Array.isArray(reportPayload.records) ? reportPayload.records : [];
        const byRequestId = new Map(records.map((record) => [
          String(record.request_id || "").trim(),
          record,
        ]).filter(([requestId]) => requestId));
        const fallbackCandidates = [];
        let changed = 0;
        semiAutoPendingConfirmationCandidates().forEach((candidate) => {
          const requestId = String(candidate.closeRequestId || "").trim();
          const record = requestId ? byRequestId.get(requestId) : null;
          if (!record) {
            fallbackCandidates.push(candidate);
            return;
          }
          const reportState = String(record.state || "pending").trim().toLowerCase();
          candidate.confirmationState = reportState || "pending";
          candidate.confirmationDetail = String(record.detail || record.message || "").trim();
          if (reportState === "confirmed") {
            if (semiAutoMarkCandidateConfirmed(candidate, record)) changed += 1;
          } else if (["uncertain", "failed"].includes(reportState)) {
            if (semiAutoMarkCandidateUncertain(candidate, record)) changed += 1;
          }
        });

        // Compatibilidade com solicitações antigas que não guardavam request_id.
        // Nunca reenvia a baixa: apenas confirma pela ausência da OS em campo.
        if (fallbackCandidates.length) {
          const ordersPayload = await request(apiUrl(
            `/api/orders?date=${encodeURIComponent(date)}&status=field&service_type=all`,
          ), { timeoutMs: 60000 });
          if (!ordersPayload.stale) {
            const activeNumbers = new Set((ordersPayload.orders || []).map((order) => (
              String(order.num_os || order.os_number || "").replace(/\D/g, "")
            )).filter(Boolean));
            fallbackCandidates.forEach((candidate) => {
              const numOs = String(candidate.numOs || candidate.order?.num_os || "").replace(/\D/g, "");
              if (numOs && !activeNumbers.has(numOs)) {
                if (semiAutoMarkCandidateConfirmed(candidate, {
                  message: "OS não aparece mais em campo no Imperium.",
                })) changed += 1;
              }
            });
          }
        }
        if (changed) renderSemiAutoQueue();
      } catch (error) {
        console.warn("Confirmacao da baixa no Imperium indisponivel", error);
      }
    }
  } finally {
    state.semiAutoPendingConfirmationWorker = false;
    renderSemiAutoQueue();
  }
}

function semiAutoCandidates(payload, job) {
  const candidates = [];
  const eligibleOs = new Set((job?.osNumbers || []).map(String));
  (payload.results || []).forEach((capture) => {
    const route = semiAutoCanonicalRoute(automationProviderLabel(capture.route_provider));
    if (route !== SEMI_AUTO_ROUTE) return;
    if (!disconnectActivityComplete(capture.activity_status)) return;

    const matchedOsSet = new Set();
    (capture.tasks || []).forEach((task) => {
      const match = toaLiveImperiumMatch(capture, task);
      let code = String(task.close_code || "").trim();
      const numOs = String(match?.num_os || task.os_number || "");
      if (
        !match
        || !eligibleOs.has(numOs)
        || !disconnectTaskExecuted(task.status)
      ) return;

      if (!code || !state.closeCodes.some((item) => item.code === code)) return;

      matchedOsSet.add(numOs);
      candidates.push({
        capture,
        task: { ...task, close_code: code },
        order: match,
        numOs,
        code,
        reviewed: false,
      });
    });

  });
  semiAutoAssignMaterialOwners(candidates);
  return candidates;
}

function semiAutoMaterialGroupKey(candidate) {
  const capture = candidate?.capture || {};
  const aid = String(capture.aid || "").trim();
  if (aid) return `aid:${aid}`;
  return [
    "activity",
    String(capture.contract || "").trim(),
    String(capture.scheduled_date || "").trim(),
    normalize(capture.work_type || ""),
    String(capture.technician?.id || capture.technician_id || "").trim(),
  ].join("|");
}

function semiAutoCandidateAcceptsMaterials(candidate) {
  if (!closeCodeAllowsMaterials(candidate?.code)) return false;
  if (!toaLiveMaterialsDraft(candidate?.capture?.materials).length) return false;
  const service = normalize(candidate?.order?.service || candidate?.capture?.work_type || "");
  if (isNoEquipmentService(service)) return false;
  return true;
}

function semiAutoMaterialOwnerScore(candidate) {
  const service = normalize(candidate?.order?.service || candidate?.capture?.work_type || "");
  if (service.includes("ASSINATURA")) return 10;
  if (service.includes("PONTO VIRT") || service.includes("VIRTUA")) return 600;
  if (service.includes("PONTO VOIP") || service.includes("VOIP")) return 550;
  if (service.includes("INTERNET") || service.includes("EMTA")) return 500;
  if (service.includes("PONTO PRINCIPAL") || service.includes("PRINCIPAL")) return 450;
  if (service.includes("RETORNO CREDENCIADA") || service.includes("RETORNO")) return 400;
  if (service.includes("MANUTENCAO") || service.includes("REPARO") || service.includes("VISITA TECNICA")) return 350;
  if (service.includes("MUDANCA DE PACOTE")) return 300;
  if (service.includes("MUDANCA DE ENDERECO")) return 200;
  if (service.includes("INSTALACAO") || service.includes("ADESAO") || service.includes("INSTALAR")) return 100;
  if (isNoEquipmentService(service)) return 10;
  return 50;
}

function semiAutoAssignMaterialOwners(candidates) {
  const groups = new Map();
  (candidates || []).forEach((candidate, index) => {
    candidate.materialGroupKey = semiAutoMaterialGroupKey(candidate);
    candidate.materialOwner = false;
    candidate.materialOwnerOs = "";
    candidate.materialGroupSize = 0;
    candidate.materialEligible = semiAutoCandidateAcceptsMaterials(candidate);
    candidate.materialOrderIndex = index;
    const group = groups.get(candidate.materialGroupKey) || [];
    group.push(candidate);
    groups.set(candidate.materialGroupKey, group);
  });
  groups.forEach((group) => {
    const eligible = group.filter((candidate) => candidate.materialEligible);
    if (!eligible.length) return;
    const owner = eligible.reduce((selected, candidate) => {
      const scoreCandidate = semiAutoMaterialOwnerScore(candidate);
      const scoreSelected = semiAutoMaterialOwnerScore(selected);
      if (scoreCandidate > scoreSelected) return candidate;
      if (scoreCandidate === scoreSelected) {
        return candidate.materialOrderIndex < selected.materialOrderIndex ? candidate : selected;
      }
      return selected;
    });
    group.forEach((candidate) => {
      candidate.materialGroupSize = group.length;
      candidate.materialOwner = candidate === owner;
      candidate.materialOwnerOs = owner.numOs;
    });
  });
  return candidates;
}

function semiAutoCandidateMaterials(candidate) {
  if (!candidate?.materialOwner) return [];
  return toaLiveMaterialsDraft(candidate.capture?.materials);
}

function semiAutoCandidateCapture(candidate, profile) {
  const materials = semiAutoCandidateMaterials(candidate);
  const capture = candidate.capture || {};
  const pasteSource = [
    "TOA-LIVE",
    profile || "",
    capture.contract || "",
    capture.aid || candidate.materialGroupKey || "",
  ].join("|");
  return {
    ...capture,
    materials,
    material_paste_key: materials.length ? materialPasteKey(pasteSource) : "",
  };
}

function semiAutoUpdateExistingDraft(candidate, profile) {
  const match = candidate?.order || toaLiveImperiumMatch(candidate?.capture || {}, candidate?.task || {});
  if (!match) return;
  const displayed = state.orders.find((order) => (
    Number(order.id_os) === Number(match.id_os)
    && String(order.num_os) === String(match.num_os)
  ));
  [match, displayed].filter(Boolean).forEach((order) => {
    const draft = state.productiveDrafts[operationDraftKey(order)];
    if (!draft || !closeCodeAllowsMaterials(draft.code)) return;
    const candidateCapture = semiAutoCandidateCapture(candidate, profile);
    draft.materials = candidateCapture.materials;
    draft.toa_paste_key = candidateCapture.material_paste_key;
    draft.material_notice = candidate.materialOwner
      ? `Miscelaneas vinculadas somente a OS ${candidate.numOs}`
      : `Miscelaneas vinculadas a OS ${candidate.materialOwnerOs}`;
  });
}

function semiAutoSetMaterialOwner(job, candidateIndex) {
  const selected = job?.candidates?.[candidateIndex];
  if (!selected?.materialEligible) return;
  const group = job.candidates.filter((candidate) => (
    candidate.materialGroupKey === selected.materialGroupKey
  ));
  group.forEach((candidate) => {
    candidate.materialOwner = candidate === selected;
    candidate.materialOwnerOs = selected.numOs;
    candidate.reviewed = false;
  });
  group.forEach((candidate) => semiAutoUpdateExistingDraft(candidate, job.profile));
}

function semiAutoEquipmentSerial(item) {
  return String(item?.serial || "").trim().toUpperCase();
}

function semiAutoObservationReplacement(capture, sourceSerial, allowedTargets) {
  const text = String(capture?.technician_observation || capture?.observation || "");
  const regex = /Troca do equipamento de serial:\s*([A-Za-z0-9]+)\s+pelo de serial:\s*([A-Za-z0-9]+)/gi;
  const source = String(sourceSerial || "").trim().toUpperCase();
  const targets = new Set(allowedTargets || []);
  const matches = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    const from = String(match[1] || "").trim().toUpperCase();
    const to = String(match[2] || "").trim().toUpperCase();
    if (from === source && targets.has(to)) matches.push(to);
  }
  return [...new Set(matches)].length === 1 ? [...new Set(matches)][0] : "";
}

function semiAutoStructuredEquipmentPlan(installed, removed, capture = {}) {
  const installedList = Array.isArray(installed) ? installed : [];
  const removedList = Array.isArray(removed) ? removed : [];
  const installedBySerial = new Map(installedList.map((item) => [semiAutoEquipmentSerial(item), item]).filter(([serial]) => serial));
  const removedBySerial = new Map(removedList.map((item) => [semiAutoEquipmentSerial(item), item]).filter(([serial]) => serial));
  const overlap = [...installedBySerial.keys()].filter((serial) => removedBySerial.has(serial));

  if (!overlap.length) {
    return { installed: installedList, removed: removedList, correction: null, error: "" };
  }
  if (overlap.length !== 1) {
    return {
      installed: installedList,
      removed: removedList,
      correction: null,
      error: `Mais de um serial aparece simultaneamente como instalado e retirado (${overlap.join(", ")}); revisar substituicoes antes da baixa`,
    };
  }

  const sourceSerial = overlap[0];
  const sourceInstalled = installedBySerial.get(sourceSerial);
  const sourceType = String(sourceInstalled?.type || "").trim().toLowerCase();
  let replacements = installedList.filter((item) => {
    const serial = semiAutoEquipmentSerial(item);
    return serial && serial !== sourceSerial && !removedBySerial.has(serial);
  });
  if (sourceType && sourceType !== "auto") {
    const sameType = replacements.filter((item) => String(item?.type || "").trim().toLowerCase() === sourceType);
    if (sameType.length) replacements = sameType;
  }

  let replacement = replacements.length === 1 ? replacements[0] : null;
  if (!replacement && replacements.length) {
    const allowedTargets = replacements.map(semiAutoEquipmentSerial).filter(Boolean);
    const observedTarget = semiAutoObservationReplacement(capture, sourceSerial, allowedTargets);
    replacement = replacements.find((item) => semiAutoEquipmentSerial(item) === observedTarget) || null;
  }
  if (!replacement) {
    return {
      installed: installedList,
      removed: removedList,
      correction: null,
      error: `O serial ${sourceSerial} aparece como instalado e retirado, mas o equipamento substituto nao foi identificado de forma unica`,
    };
  }

  const replacementSerial = semiAutoEquipmentSerial(replacement);
  return {
    installed: installedList.filter((item) => semiAutoEquipmentSerial(item) !== replacementSerial),
    removed: removedList.filter((item) => semiAutoEquipmentSerial(item) !== sourceSerial),
    correction: {
      installed: [replacement],
      removed: [removedBySerial.get(sourceSerial)],
      materials: [],
      source_serial: sourceSerial,
      replacement_serial: replacementSerial,
    },
    error: "",
  };
}

function semiAutoCandidateEquipmentPlan(candidate) {
  const match = candidate?.order || toaLiveImperiumMatch(candidate?.capture, candidate?.task);
  if (!match) return { installed: [], removed: [], correction: null, error: "OS nao encontrada no Imperium" };
  const capture = candidate?.capture || {};
  const service = normalize(match.service);
  if (service.includes("ASSINATURA")) return { installed: [], removed: [], correction: null, error: "" };
  if (candidate.materialGroupSize > 1 && !candidate.materialOwner) return { installed: [], removed: [], correction: null, error: "" };

  const contractOrders = (capture.imperium_matches && capture.imperium_matches.length)
    ? capture.imperium_matches
    : (state.orders || []).filter((item) => String(item.contract) === String(match.contract));
  const rawInstalled = toaLiveEquipmentDraft(capture.installed_equipment, match, contractOrders);
  const untypedRemoved = toaLiveEquipmentDraft(capture.removed_equipment, match, contractOrders);
  const installedType = rawInstalled.find((item) => item.type && item.type !== "auto")?.type || "";
  const expectedType = expectedEquipmentType(match.service);
  const rawRemoved = untypedRemoved.map((item) => {
    if (item.type && item.type !== "auto") return item;
    const resolvedType = installedType
      || expectedType
      || (/^[0-9A-F]{12}$/i.test(item.serial) ? "emta" : (/^\d+$/.test(item.serial) ? "decoder" : "emta"));
    return { ...item, type: resolvedType };
  });
  const plan = semiAutoStructuredEquipmentPlan(rawInstalled, rawRemoved, capture);
  candidate.equipmentCorrectionPlan = plan.correction;
  candidate.equipmentPlanError = plan.error;
  return plan;
}

function semiAutoCandidateInstalledEquipment(candidate) {
  return semiAutoCandidateEquipmentPlan(candidate).installed;
}

function semiAutoCandidateRemovedEquipment(candidate) {
  return semiAutoCandidateEquipmentPlan(candidate).removed;
}

function semiAutoInventoryLabel(candidate) {
  const installed = semiAutoCandidateInstalledEquipment(candidate).length;
  const removed = semiAutoCandidateRemovedEquipment(candidate).length;
  const materials = semiAutoCandidateMaterials(candidate).length;
  return `${installed} instalado(s) · ${removed} retirado(s) · ${materials} miscelanea(s)`;
}

function semiAutoCandidateService(candidate) {
  return String(
    candidate?.order?.service
    || candidate?.task?.service
    || candidate?.capture?.work_type
    || "Servico nao informado",
  ).trim();
}

function semiAutoCandidateKind(candidate) {
  const service = normalize(semiAutoCandidateService(candidate));
  if (service.includes("MUDANCA DE ENDERECO")) return "Mudanca de Endereco";
  if (service.includes("PONTO VIRT") || service.includes("VIRTUA")) return "Ponto Virtua";
  if (service.includes("ASSINATURA")) return "Assinatura";
  if (service.includes("RETORNO CREDENCIADA")) return "Retorno de credenciada";
  if (service.includes("INSTAL")) return "Instalacao";
  return semiAutoCandidateService(candidate);
}

function semiAutoActivityGroups(job) {
  const groups = new Map();
  (job?.candidates || []).forEach((candidate, candidateIndex) => {
    const key = candidate.materialGroupKey || semiAutoMaterialGroupKey(candidate);
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        aid: String(candidate.capture?.aid || "").trim(),
        workType: String(candidate.capture?.work_type || "Atividade TOA").trim(),
        candidates: [],
      });
    }
    groups.get(key).candidates.push({ candidate, candidateIndex });
  });
  return [...groups.values()];
}

function semiAutoContractServiceSummary(job) {
  const counts = new Map();
  (job?.candidates || []).forEach((candidate) => {
    const kind = semiAutoCandidateKind(candidate);
    counts.set(kind, (counts.get(kind) || 0) + 1);
  });
  return [...counts.entries()].map(([kind, count]) => (
    count > 1 ? `${kind} (${count})` : kind
  )).join(" · ");
}

function renderSemiAutoContractReview() {
  const dialog = elements.semiAutoContractDialog;
  const job = state.semiAutoJobs[state.semiAutoReviewJobIndex];
  if (!dialog || !job) return;
  const candidates = job.candidates || [];
  const groups = semiAutoActivityGroups(job);
  const reviewed = candidates.filter((candidate) => candidate.reviewed).length;
  elements.semiAutoContractTitle.textContent = `Contrato ${job.contract}`;
  elements.semiAutoContractMeta.textContent = [
    job.route,
    job.windowLabel,
    `${candidates.length} O.S.`,
    `${groups.length} atividade(s) TOA`,
    reviewed ? `${reviewed} revisada(s)` : "nenhuma revisada",
  ].join(" · ");
  elements.semiAutoContractActivities.innerHTML = groups.map((group, groupIndex) => {
    const sourceMaterials = toaLiveMaterialsDraft(group.candidates[0]?.candidate?.capture?.materials).length;
    const owner = group.candidates.find(({ candidate }) => candidate.materialOwner)?.candidate;
    return `
      <section class="semi-auto-contract-activity">
        <header>
          <div>
            <span>ATIVIDADE ${groupIndex + 1}${group.aid ? ` · AID ${escapeHtml(group.aid)}` : ""}</span>
            <strong>${escapeHtml(group.workType)}</strong>
          </div>
          <small>${sourceMaterials
            ? `${sourceMaterials} miscelanea(s) capturada(s) · destino: OS ${escapeHtml(owner?.numOs || "a definir")}`
            : "Sem miscelaneas nesta atividade"}</small>
        </header>
        <div class="semi-auto-contract-orders">
          ${group.candidates.map(({ candidate, candidateIndex }) => `
            <article class="semi-auto-contract-order ${candidate.reviewed ? "reviewed" : ""} ${candidate.materialOwner ? "material-owner" : ""}">
              <div class="semi-auto-contract-order-main">
                <div class="semi-auto-contract-order-title">
                  <span>OS ${escapeHtml(candidate.numOs)}</span>
                  <em>${escapeHtml(semiAutoCandidateKind(candidate))}</em>
                </div>
                <strong>${escapeHtml(semiAutoCandidateService(candidate))}</strong>
                <small>Codigo ${escapeHtml(candidate.code)} · ${escapeHtml(semiAutoInventoryLabel(candidate))}</small>
                ${candidate.materialOwnerOs ? `<small class="semi-auto-material-note">
                  ${candidate.materialOwner
                    ? "Esta O.S. recebe as miscelaneas desta atividade."
                    : `As miscelaneas ficam somente na OS ${escapeHtml(candidate.materialOwnerOs)}.`}
                </small>` : ""}
              </div>
              <div class="semi-auto-item-actions">
                ${candidate.materialEligible && candidate.materialGroupSize > 1 ? `
                  <button class="button ghost compact" type="button"
                    data-contract-material-owner="${candidateIndex}"
                    ${candidate.materialOwner ? "disabled" : ""}>
                    ${candidate.materialOwner ? "Recebe miscelaneas" : "Colocar miscelaneas nesta OS"}
                  </button>` : ""}
                <button class="button primary compact" type="button" data-contract-close="${candidateIndex}">
                  <i data-lucide="send" aria-hidden="true"></i><span>Baixar esta OS</span>
                </button>
                <button class="button secondary compact" type="button" data-contract-review="${candidateIndex}">
                  ${candidate.reviewed ? "Reabrir esta OS" : "Revisar esta OS"}
                </button>
              </div>
            </article>`).join("")}
        </div>
      </section>`;
  }).join("");

  elements.semiAutoContractActivities.querySelectorAll("[data-contract-material-owner]").forEach((button) => {
    button.addEventListener("click", () => {
      const candidateIndex = Number(button.dataset.contractMaterialOwner);
      semiAutoSetMaterialOwner(job, candidateIndex);
      renderSemiAutoContractReview();
      renderSemiAutoQueue();
      showToast(
        `As miscelaneas da atividade serao usadas somente na OS ${job.candidates[candidateIndex].numOs}.`,
        "success",
      );
    });
  });
  elements.semiAutoContractActivities.querySelectorAll("[data-contract-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const candidateIndex = Number(button.dataset.contractClose);
      const candidate = job.candidates[candidateIndex];
      if (!candidate) return;
      const prepared = prepareToaLiveClose(
        semiAutoCandidateCapture(candidate, job.profile),
        candidate.task,
        { expectedProfile: job.profile, openEditor: true },
      );
      if (prepared) {
        candidate.reviewed = true;
        dialog.close();
      }
      renderSemiAutoQueue();
    });
  });
  elements.semiAutoContractActivities.querySelectorAll("[data-contract-review]").forEach((button) => {
    button.addEventListener("click", () => {
      const candidateIndex = Number(button.dataset.contractReview);
      const candidate = job.candidates[candidateIndex];
      if (!candidate) return;
      const prepared = prepareToaLiveClose(
        semiAutoCandidateCapture(candidate, job.profile),
        candidate.task,
        { expectedProfile: job.profile },
      );
      if (prepared) {
        candidate.reviewed = true;
        dialog.close();
      }
      renderSemiAutoQueue();
    });
  });
}

function openSemiAutoContractReview(jobIndex) {
  const job = state.semiAutoJobs[jobIndex];
  if (!job?.candidates?.length || !elements.semiAutoContractDialog) return;
  state.semiAutoReviewJobIndex = jobIndex;
  renderSemiAutoContractReview();
  if (!elements.semiAutoContractDialog.open) elements.semiAutoContractDialog.showModal();
}

function openSemiAutoSkippedDialog() {
  if (!elements.semiAutoSkippedDialog) return;
  state.semiAutoSkippedFilter = "all";
  if (elements.semiAutoSkippedSearch) elements.semiAutoSkippedSearch.value = "";
  renderSemiAutoSkippedDialog();
  if (!elements.semiAutoSkippedDialog.open) elements.semiAutoSkippedDialog.showModal();
}

function renderSemiAutoSkippedDialog() {
  if (!elements.semiAutoSkippedDialog || !elements.semiAutoSkippedList) return;
  const allSkipped = (state.semiAutoJobs || []).filter((job) => (
    ["skipped", "error"].includes(job.state)
    && !["toa_pending", "awaiting_imperium_import"].includes(job.skipCategory)
  ));

  const filterCategory = state.semiAutoSkippedFilter || "all";
  const query = (elements.semiAutoSkippedSearch?.value || "").trim().toLowerCase();

  // Counts for filters
  const countImperium = allSkipped.filter((j) =>
    ["imperium_no_os", "imperium_closed"].includes(j.skipCategory)
  ).length;
  const countToaNotFound = allSkipped.filter((j) => j.skipCategory === "toa_not_found").length;
  const countOther = allSkipped.length - countImperium - countToaNotFound;

  const countAllEl = document.querySelector("#countSkippedAll");
  const countImpEl = document.querySelector("#countSkippedImperium");
  const countNotFoundEl = document.querySelector("#countSkippedToaNotFound");
  const countOtherEl = document.querySelector("#countSkippedOther");

  if (countAllEl) countAllEl.textContent = allSkipped.length;
  if (countImpEl) countImpEl.textContent = countImperium;
  if (countNotFoundEl) countNotFoundEl.textContent = countToaNotFound;
  if (countOtherEl) countOtherEl.textContent = Math.max(0, countOther);

  // Update active chip styling
  if (elements.semiAutoSkippedFilters) {
    elements.semiAutoSkippedFilters.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("active", chip.dataset.filter === filterCategory);
    });
  }

  // Filter items
  let filtered = allSkipped.filter((job) => {
    if (filterCategory === "imperium_no_os") {
      return ["imperium_no_os", "imperium_closed"].includes(job.skipCategory);
    }
    if (filterCategory === "toa_not_found") {
      return job.skipCategory === "toa_not_found";
    }
    if (filterCategory === "other") {
      return !["imperium_no_os", "imperium_closed", "toa_not_found"].includes(job.skipCategory);
    }
    return true;
  });

  if (query) {
    filtered = filtered.filter((job) => {
      const matchContract = String(job.contract || "").toLowerCase().includes(query);
      const matchWindow = String(job.windowLabel || "").toLowerCase().includes(query);
      const matchOs = (job.osNumbers || []).some((os) => String(os).toLowerCase().includes(query));
      const matchDetail = String(job.skipDetail || job.message || "").toLowerCase().includes(query);
      const matchTitle = String(job.skipTitle || "").toLowerCase().includes(query);
      return matchContract || matchWindow || matchOs || matchDetail || matchTitle;
    });
  }

  if (elements.semiAutoSkippedCount) {
    elements.semiAutoSkippedCount.textContent = `${filtered.length} de ${allSkipped.length} contrato(s) exibido(s)`;
  }

  if (!filtered.length) {
    elements.semiAutoSkippedList.innerHTML = `<div class="semi-auto-empty">${
      allSkipped.length ? "Nenhum contrato corresponde ao filtro ou busca selecionada." : "Nenhum contrato ignorado ou não localizado na esteira até o momento."
    }</div>`;
    return;
  }

  elements.semiAutoSkippedList.innerHTML = filtered.map((job) => {
    let badgeClass = "other";
    if (["imperium_no_os", "imperium_closed"].includes(job.skipCategory)) badgeClass = "imperium-no-os";
    else if (job.skipCategory === "toa_pending") badgeClass = "toa-pending";
    else if (job.skipCategory === "toa_not_found") badgeClass = "toa-not-found";
    else if (job.skipCategory === "error") badgeClass = "error";

    const badgeTitle = escapeHtml(job.skipTitle || (job.state === "error" ? "Erro" : "Ignorado"));
    const reasonText = escapeHtml(job.skipDetail || job.message || "Não foi possível processar");
    const osNumbersStr = (job.osNumbers || []).length
      ? `OS no Imperium: ${job.osNumbers.map(escapeHtml).join(", ")}`
      : "Sem OS aberta no Imperium";

    let techStr = "";
    if (job.payload?.results?.length) {
      const techs = [...new Set(job.payload.results.map((c) => c.technician_name).filter(Boolean))];
      if (techs.length) techStr = `Técnico no TOA: ${techs.map(escapeHtml).join(", ")}`;
    }

    return `
      <article class="semi-auto-skipped-card">
        <div class="semi-auto-skipped-card-main">
          <div class="semi-auto-skipped-card-header">
            <span class="semi-auto-skipped-contract">CONTRATO ${escapeHtml(job.contract)}</span>
            <span class="semi-auto-skipped-window">Janela ${escapeHtml(job.windowLabel || "livre")}</span>
            <span class="skip-badge ${badgeClass}">${badgeTitle}</span>
          </div>
          <p class="semi-auto-skipped-reason">${reasonText}</p>
          <div class="semi-auto-skipped-meta">
            <span>${osNumbersStr}</span>
            ${techStr ? `<span>${techStr}</span>` : ""}
          </div>
        </div>
        <div class="semi-auto-skipped-card-actions">
          <button class="button secondary compact" type="button" data-copy-skipped-contract="${escapeHtml(job.contract)}" title="Copiar contrato">
            Copiar
          </button>
          <button class="button secondary compact" type="button" data-lookup-skipped-contract="${escapeHtml(job.contract)}" title="Consultar contrato no TOA Live">
            Consultar TOA
          </button>
        </div>
      </article>
    `;
  }).join("");

  elements.semiAutoSkippedList.querySelectorAll("[data-copy-skipped-contract]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const contract = btn.dataset.copySkippedContract;
      if (navigator.clipboard && contract) {
        navigator.clipboard.writeText(contract).then(() => {
          showToast(`Contrato ${contract} copiado!`, "success");
        }).catch(() => {
          showToast(`Contrato: ${contract}`);
        });
      }
    });
  });

  elements.semiAutoSkippedList.querySelectorAll("[data-lookup-skipped-contract]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const contract = btn.dataset.lookupSkippedContract;
      if (!contract) return;
      if (elements.semiAutoSkippedDialog.open) elements.semiAutoSkippedDialog.close();
      if (elements.toaLiveContract) {
        elements.toaLiveContract.value = contract;
        elements.toaLiveContract.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      lookupToaLiveContract();
    });
  });
}

function humanReviewReasonText(reason) {
  const raw = String(reason || "").trim();
  if (!raw) return "Revisao necessaria";
  const labels = {
    installer_mismatch_unresolved: "Tecnico do TOA nao localizado de forma unica no Imperium",
    installer_reassignment_failed: "Imperium nao conseguiu reatribuir a OS ao tecnico do TOA",
    installer_reassignment_unconfirmed: "Imperium nao confirmou a troca de tecnico da OS",
    imperium_not_open: "OS nao esta mais aberta no Imperium",
    toa_not_found: "Contrato ou atividade nao localizado no TOA",
    material_transfer_uncertain: "Transferencia de material sem confirmacao; nao repetir automaticamente",
    stock_owner_mismatch: "Equipamento esta em outro estoque",
    unknown_close_code: "Codigo de baixa nao reconhecido",
    shared_state_contamination: "Contexto de base mudou durante a operacao",
  };
  const lower = raw.toLowerCase();
  for (const [code, label] of Object.entries(labels)) {
    if (lower === code || lower.includes(code)) return label;
  }
  if (/^[a-z0-9_]+$/i.test(raw)) {
    return raw.replaceAll("_", " ").replace(/^./, (char) => char.toUpperCase());
  }
  return raw;
}

function renderSemiAutoQueue() {
  if (!elements.semiAutoPanel) return;
  const jobs = state.semiAutoJobs;
  const readyJobs = jobs
    .map((job, jobIndex) => ({ job, jobIndex }))
    .filter(({ job }) => job.candidates?.length);
  const temporaryWaitCategories = new Set(["toa_pending", "awaiting_imperium_import"]);
  const toaPending = jobs.filter((job) => job.skipCategory === "toa_pending").length;
  const awaitingImperium = jobs.filter((job) => job.skipCategory === "awaiting_imperium_import").length;
  const activePending = jobs.filter((job) => ["pending", "searching"].includes(job.state)).length;
  const temporaryWaiting = toaPending + awaitingImperium;
  const processed = jobs.filter((job) => (
    ["ready", "skipped", "error"].includes(job.state)
    && !temporaryWaitCategories.has(job.skipCategory)
  )).length;
  const skipped = jobs.filter((job) => (
    ["skipped", "error"].includes(job.state)
    && !temporaryWaitCategories.has(job.skipCategory)
  )).length;
  const pending = activePending + temporaryWaiting;
  const imperiumClosed = jobs.filter((job) => ["imperium_no_os", "imperium_closed"].includes(job.skipCategory)).length;
  const imperiumOpen = jobs.filter((job) => Array.isArray(job.osNumbers) && job.osNumbers.length > 0).length;
  const toaConsulted = jobs.filter((job) => Boolean(job.payload)).length;
  elements.semiAutoPanel.classList.toggle("hidden", jobs.length === 0 && !state.semiAutoRunning);
  elements.semiAutoProcessed.textContent = jobs.length;
  if (elements.semiAutoImperiumOpenCount) elements.semiAutoImperiumOpenCount.textContent = imperiumOpen;
  if (elements.semiAutoImperiumClosedCount) elements.semiAutoImperiumClosedCount.textContent = imperiumClosed;
  if (elements.semiAutoToaConsultedCount) elements.semiAutoToaConsultedCount.textContent = toaConsulted;
  if (elements.semiAutoClosedCount) elements.semiAutoClosedCount.textContent = state.autoCloseCount || 0;
  if (elements.semiAutoHumanCount) elements.semiAutoHumanCount.textContent = state.humanReviewCount || 0;
  if (elements.semiAutoToaPendingCount) elements.semiAutoToaPendingCount.textContent = toaPending;
  if (elements.semiAutoAwaitingImperiumCount) elements.semiAutoAwaitingImperiumCount.textContent = awaitingImperium;
  elements.semiAutoReady.textContent = readyJobs.length;
  elements.semiAutoSkipped.textContent = skipped;
  elements.semiAutoPending.textContent = pending;
  elements.semiAutoHeadline.textContent = state.semiAutoPaused
    ? "Fila pausada; as revisoes prontas continuam disponiveis"
    : state.semiAutoRunning
      ? (state.autoCloseMode ? `Executando Baixa Automatica (100%): ${processed}/${jobs.length} contratos` : `${processed}/${jobs.length} contratos pesquisados`)
      : activePending
        ? `Fila interrompida com ${activePending} contrato(s) ainda não pesquisado(s)`
        : temporaryWaiting
          ? `Aguardando dependências externas: ${temporaryWaiting} contrato(s)`
          : jobs.length
            ? (state.autoCloseMode ? "Baixa automatica concluida!" : "Pesquisa concluida; aguardando revisao humana")
            : "Aguardando inicio";
  const toaRetryMinutes = state.semiAutoToaRetryWaitingUntil > Date.now()
    ? Math.max(1, Math.ceil((state.semiAutoToaRetryWaitingUntil - Date.now()) / 60000))
    : 0;
  const currentWindowJob = jobs.find((job) => String(job.contract) === String(state.semiAutoCurrentContract));
  const currentWindowJobs = currentWindowJob
    ? jobs.filter((job) => semiAutoOriginalWindowKey(job) === semiAutoOriginalWindowKey(currentWindowJob))
    : [];
  const currentWindowPosition = currentWindowJob ? currentWindowJobs.indexOf(currentWindowJob) + 1 : 0;
  const currentWindowLabel = currentWindowJob
    ? String(currentWindowJob.originalWindowLabel || currentWindowJob.windowLabel || "janela sem horário")
    : "";
  elements.semiAutoCurrent.innerHTML = state.semiAutoCurrentContract
    ? `<span class="pulse-indicator" aria-hidden="true"></span><span>Consultando janela <strong>${escapeHtml(currentWindowLabel)}</strong> · contrato <strong>${escapeHtml(state.semiAutoCurrentContract)}</strong>${currentWindowJobs.length ? ` · <strong>${currentWindowPosition}/${currentWindowJobs.length}</strong>` : ""}${currentWindowJob?.windowOverrideMode === "now" ? " · prioridade manual" : ""}</span>`
    : toaRetryMinutes
      ? `<i data-lucide="rotate-cw" aria-hidden="true"></i><span>Contratos pendentes no TOA serão pesquisados novamente em até <strong>${toaRetryMinutes} min</strong>.</span>`
      : state.semiAutoWaitingWindow
        ? `<i data-lucide="clock" aria-hidden="true"></i><span>Aguardando o início da janela <strong>${escapeHtml(state.semiAutoWaitingWindow)}</strong>.</span>`
        : state.semiAutoRefreshing
          ? `<span class="pulse-indicator" aria-hidden="true"></span><span>Confirmando no Imperium quais OS continuam em campo...</span>`
          : `<span>Nenhum contrato em consulta.</span>`;
  elements.semiAutoPause.disabled = !state.semiAutoRunning;
  elements.semiAutoPause.textContent = state.semiAutoPaused ? "Continuar" : "Pausar";
  elements.semiAutoStop.disabled = !state.semiAutoRunning;
  elements.semiAutoReadyList.innerHTML = readyJobs.length
    ? readyJobs.map(({ job, jobIndex }) => {
      const candidates = job.candidates || [];
      const groups = semiAutoActivityGroups(job);
      const reviewed = candidates.filter((candidate) => candidate.reviewed).length;
      const closed = candidates.filter((candidate) => candidate.closed).length;
      const pending = candidates.filter((candidate) => candidate.pending).length;
      const human = candidates.filter((candidate) => candidate.humanReview);
      const materialOwners = candidates.filter((candidate) => candidate.materialOwner);
      const isAllClosed = candidates.length > 0 && closed === candidates.length;
      const hasHuman = human.length > 0;
      const hasPending = pending > 0;
      const statusClass = isAllClosed ? "status-closed" : hasHuman ? "status-human" : hasPending ? "status-pending" : "status-ready";
      const omittedList = candidates.flatMap((c) => c.omittedMaterials || []);

      return `
      <article class="semi-auto-ready-card ${statusClass}">
        <div class="semi-auto-card-header">
          <div class="semi-auto-card-badges">
            ${job.route ? `<span class="badge-route">${escapeHtml(job.route)}</span>` : ""}
            ${job.windowLabel ? `<span class="badge-window"><i data-lucide="clock" aria-hidden="true"></i> ${escapeHtml(job.windowLabel)}</span>` : ""}
            <span class="badge-contract">CONTRATO <strong>${escapeHtml(job.contract)}</strong></span>
          </div>
          <div class="semi-auto-card-status">
            ${isAllClosed
              ? '<span class="status-pill success"><i data-lucide="check-circle-2" aria-hidden="true"></i> Baixada Auto (100%)</span>'
              : hasHuman
                ? '<span class="status-pill warning"><i data-lucide="alert-triangle" aria-hidden="true"></i> Tratativa Humana</span>'
                : hasPending
                  ? '<span class="status-pill info"><i data-lucide="clock" aria-hidden="true"></i> Aguardando confirmação</span>'
                  : closed > 0
                    ? `<span class="status-pill info"><i data-lucide="zap" aria-hidden="true"></i> ${closed}/${candidates.length} Auto</span>`
                    : '<span class="status-pill neutral"><i data-lucide="list-checks" aria-hidden="true"></i> Pronto p/ revisar</span>'
            }
          </div>
        </div>

        <div class="semi-auto-card-body">
          <h4 class="semi-auto-card-title">${escapeHtml(semiAutoContractServiceSummary(job) || "Atividades TOA")}</h4>

          <div class="semi-auto-card-metrics">
            <span class="metric-chip"><i data-lucide="file-text" aria-hidden="true"></i> ${candidates.length} O.S.</span>
            <span class="metric-chip"><i data-lucide="layers" aria-hidden="true"></i> ${groups.length} atividade(s) TOA</span>
            ${closed ? `<span class="metric-chip success"><i data-lucide="check" aria-hidden="true"></i> ${closed} baixada(s) auto</span>` : ""}
            ${pending ? `<span class="metric-chip warning"><i data-lucide="clock" aria-hidden="true"></i> ${pending} aguardando conf.</span>` : ""}
            <span class="metric-chip ${reviewed === candidates.length ? "success" : ""}">${reviewed}/${candidates.length} processada(s)</span>
          </div>

          ${hasHuman ? `
            <div class="semi-auto-card-alert alert-warning">
              <i data-lucide="alert-triangle" aria-hidden="true"></i>
              <div>
                <strong>Retida para tratativa humana:</strong>
                <span>${escapeHtml(human.map((c) => `OS ${c.numOs} (${c.humanReviewReason || "verificar"})`).join(" · "))}</span>
              </div>
            </div>
          ` : ""}

          ${omittedList.length ? `
            <div class="semi-auto-card-alert alert-danger">
              <i data-lucide="package-x" aria-hidden="true"></i>
              <div>
                <strong>Material omitido por saldo zerado:</strong>
                <span>${escapeHtml(omittedList.map((m) => `${m.description || m.code} (${m.code})`).join(" · "))}</span>
              </div>
            </div>
          ` : ""}

          ${materialOwners.length ? `
            <div class="semi-auto-card-note">
              <i data-lucide="boxes" aria-hidden="true"></i>
              <span>Miscelâneas vinculadas a ${materialOwners.map((candidate) => `OS <strong>${escapeHtml(candidate.numOs)}</strong>`).join(" · ")}</span>
            </div>
          ` : ""}
        </div>

        <div class="semi-auto-card-footer">
          <button class="button ${reviewed ? "secondary" : "primary"} compact" type="button" data-semi-contract-review="${jobIndex}">
            <i data-lucide="${reviewed ? "eye" : "check-square"}" aria-hidden="true"></i>
            <span>${reviewed ? "Ver detalhes do contrato" : "Revisar contrato"}</span>
          </button>
        </div>
      </article>`;
    }).join("")
    : '<div class="semi-auto-empty"><i data-lucide="inbox" aria-hidden="true"></i><span>As atividades encontradas aparecerão aqui sem interromper a próxima pesquisa.</span></div>';
  elements.semiAutoReadyList.querySelectorAll("[data-semi-contract-review]").forEach((button) => {
    button.addEventListener("click", () => {
      openSemiAutoContractReview(Number(button.dataset.semiContractReview));
    });
  });
  renderSemiAutoWindowControl();
  if (globalThis.lucide) globalThis.lucide.createIcons();

  const online = Boolean(state.toaLiveStatus?.connected && state.toaLiveStatus?.authenticated);
  const resumable = jobs.some((job) => job.state === "pending");
  const agendaCount = semiAutoAgendaRecords().length;
  const isBusy = state.semiAutoRefreshing || !online || !agendaCount || (state.semiAutoRunning && !state.semiAutoPaused);
  elements.semiAutoStart.disabled = isBusy;
  elements.semiAutoStart.querySelector("span").textContent = state.semiAutoRefreshing
    ? "Conferindo Imperium"
    : state.semiAutoPaused || resumable
    ? "Continuar semiautomatico"
    : state.semiAutoRunning && !state.autoCloseMode
      ? "Pesquisando contratos"
      : "Baixa semiautomatica";
  if (elements.autoCloseStart) {
    elements.autoCloseStart.disabled = isBusy;
    elements.autoCloseStart.querySelector("span").textContent = state.autoCloseMode && state.semiAutoRunning
      ? "Baixando 100%..."
      : "Baixa Automatica (100%)";
  }
  renderSemiAutoAgenda();
}

function semiAutoExpectedSkip(error) {
  const message = normalize(error?.message || "");
  return [
    "OUTSIDE DMV ROUTE TREE",
    "TOA SEM RESULTADOS",
    "SEM RESULTADOS",
    "NAO LOCALIZAD",
    "NENHUMA ATIVIDADE",
  ].some((marker) => message.includes(marker));
}

function semiAutoClassifySkip(job, payload) {
  if (!payload || !Array.isArray(payload.results) || payload.results.length === 0) {
    return {
      category: "toa_not_found",
      title: "Não Localizado no TOA",
      detail: "A busca no TOA não retornou nenhuma atividade para este contrato.",
    };
  }

  const results = payload.results;
  const dmvResults = results.filter((capture) => {
    const route = semiAutoCanonicalRoute(automationProviderLabel(capture.route_provider));
    return route === SEMI_AUTO_ROUTE;
  });

  if (!dmvResults.length) {
    const otherRoutes = [...new Set(results.map((c) => c.route_provider).filter(Boolean))].join(", ") || "outra base/rota";
    return {
      category: "toa_other_route",
      title: "Fora da Rota DMV",
      detail: `Atividade encontrada no TOA pertence a outra rota (${otherRoutes}), fora da árvore NTL-DMV.`,
    };
  }

  const incomplete = dmvResults.filter((c) => !disconnectActivityComplete(c.activity_status));
  if (incomplete.length === dmvResults.length) {
    const statuses = dmvResults.map((c) => {
      const st = String(c.activity_status || "").toLowerCase();
      const tech = c.technician_name ? ` (${c.technician_name})` : "";
      const label = st === "started" ? "iniciada / em atendimento"
        : st === "pending" ? "pendente"
        : st === "suspended" ? "suspensa"
        : st === "cancelled" ? "cancelada"
        : st || "não finalizada";
      return `${label}${tech}`;
    }).join(", ");
    return {
      category: "toa_pending",
      title: "Pendente no TOA",
      detail: `Atividade no TOA ainda não foi concluída pelo técnico: ${statuses}.`,
    };
  }

  const eligibleOs = new Set((job?.osNumbers || []).map(String));
  if (!eligibleOs.size) {
    return {
      category: "awaiting_imperium_import",
      title: "Aguardando Importação no Imperium",
      detail: "Atividade localizada no TOA, mas a OS ainda não apareceu no Imperium. O contrato ficará guardado e será retomado após a próxima importação/atualização.",
    };
  }
  const tasks = dmvResults.flatMap((c) => c.tasks || []);
  const taskOsNumbers = tasks.map((t) => String(t.os_number || "")).filter(Boolean);
  if (taskOsNumbers.length && !taskOsNumbers.some((os) => eligibleOs.has(os))) {
    return {
      category: "os_mismatch",
      title: "OS Divergente no TOA",
      detail: `Atividade concluída no TOA com OS ${taskOsNumbers.join(", ")}, divergente da OS em campo no Imperium (${[...eligibleOs].join(", ") || "nenhuma"}).`,
    };
  }

  const unexecuted = tasks.filter((t) => !disconnectTaskExecuted(t.status));
  if (unexecuted.length && unexecuted.length === tasks.length) {
    return {
      category: "toa_unexecuted",
      title: "Tarefa Não Executada",
      detail: "Atividade finalizada no TOA, mas as tarefas foram marcadas como canceladas ou não executadas.",
    };
  }

  return {
    category: "toa_other",
    title: "Sem OS Compatível",
    detail: "Atividade encontrada no TOA, mas nenhuma OS aberta no Imperium atende aos critérios de baixa automática.",
  };
}

function semiAutoClassifyErrorSkip(job, error) {
  const msg = String(error?.message || "");
  if (msg.includes("OUTSIDE DMV ROUTE TREE") || msg.includes("FORA DA ROTA")) {
    return {
      category: "toa_other_route",
      title: "Fora da Rota DMV",
      detail: `Contrato pertence a outra rota/árvore: ${msg}`,
    };
  }
  if (semiAutoExpectedSkip(error) || msg.includes("toa_contrato_nao_encontrado") || msg.includes("toa_resposta_busca_invalida")) {
    return {
      category: "toa_not_found",
      title: "Não Localizado no TOA",
      detail: "Contrato não encontrado no TOA desta base.",
    };
  }
  return {
    category: "error",
    title: "Erro na Consulta",
    detail: `Erro ao consultar TOA: ${msg}`,
  };
}

async function executeDirectAutoClose(candidate, materials = []) {
  const match = candidate.order || toaLiveImperiumMatch(candidate.capture, candidate.task);
  if (!match) return false;
  const capture = candidate.capture || {};
  const task = candidate.task || {};
  const code = String(task.close_code || candidate.code || "409").trim();

  const contractOrders = (capture.imperium_matches && capture.imperium_matches.length)
    ? capture.imperium_matches
    : (state.orders || []).filter((item) => String(item.contract) === String(match.contract));
  const installed = semiAutoCandidateInstalledEquipment(candidate);
  const removed = semiAutoCandidateRemovedEquipment(candidate);

  const displayedOrder = state.orders.find((item) =>
    Number(item.id_os) === Number(match.id_os)
    && String(item.num_os) === String(match.num_os)
  );
  const currentOrder = displayedOrder && !displayedOrder.read_only ? displayedOrder : match;

  const movement = (code === "517" || (installed.length && removed.length))
    ? "swap"
    : (removed.length ? "remove" : defaultMovement(match, code));

  const service = normalize(currentOrder.service || match.service || "");
  const operationSource = currentOrder.operation_source || match.operation_source || "imperium_cache";
  const identity = currentOrder.operation_identity || match.operation_identity;
  const importScope = currentOrder.import_scope || match.import_scope;
  const manualScope = currentOrder.manual_scope || match.manual_scope;
  const approvedStateHash = currentOrder.approved_state_hash || match.approved_state_hash;
  const approvedSourceHash = importScope?.source_hash || manualScope?.source_hash;
  const hasMaterials = Array.isArray(materials) && materials.length > 0;

  const hasDataSnap = Boolean(state.authUser?.imperium_identities?.[state.profile]);
  const transport = (
    (state.activeModule === "close" && elements.closeTransport?.value)
    || (state.officialCloseEnabled ? "official_http" : (hasDataSnap ? "datasnap" : "official_http"))
  );

  const toaTechName = String(
    capture.assigned_technician?.name
    || capture.technician_name
    || capture.technician
    || ""
  ).trim();
  const toaTechLogin = String(
    capture.assigned_technician?.external_id
    || capture.assigned_technician?.login
    || capture.technician_login
    || ""
  ).trim().toUpperCase();
  const toaTechId = String(capture.assigned_technician?.id || "").trim();

  const body = {
    profile: state.profile,
    code,
    num_os: String(match.num_os || currentOrder.num_os || "").trim(),
    transport,
    toa_technician: {
      name: toaTechName,
      login: toaTechLogin,
      id: toaTechId,
    },
    observation: String(capture.technician_observation || capture.observation || "").trim(),
    operation_source: operationSource,
    operation_identity: identity,
    import_scope: importScope,
    approved_source_hash: approvedSourceHash,
    approved_state_hash: approvedStateHash,
    manual_scope: manualScope,
    movement,
    installed_equipment: installed,
    removed_equipment: removed,
    materials: isNoEquipmentService(service) ? [] : materials.map((m) => ({
      ...m,
      equivalence_confirmed: true,
    })),
  };

  try {
    const res = await request(apiUrl(`/api/orders/${currentOrder.id_os || match.id_os}/close`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: hasMaterials ? 480000 : 300000,
    });
    if (res?.pending_confirmation) {
      return {
        closed: false,
        pending: true,
        requestId: String(res.request_id || "").trim(),
        reportState: String(res.state || "pending").trim().toLowerCase(),
        materialPreparation: res.material_preparation || null,
        message: res.message || "Aguardando confirmacao do Imperium",
      };
    }
    return Boolean(res && (res.ok || res.status === "confirmed" || res.confirmed));
  } catch (err) {
    console.error(`Falha na baixa automatica da OS ${match.num_os}:`, err);
    return {
      closed: false,
      humanReview: true,
      reason: err?.data?.reason || err?.reason || err.message || "Falha na confirmacao da baixa",
      error: err.message,
    };
  }
}

async function processAutoCloseCandidate(candidate, profile) {
  const match = candidate.order || toaLiveImperiumMatch(candidate.capture, candidate.task);
  if (!match) return { closed: false, humanReview: true, reason: "OS nao encontrada no Imperium" };
  const capture = candidate.capture || {};
  const task = candidate.task || {};
  const code = String(task.close_code || candidate.code || "409").trim();
  const service = normalize(match.service);
  const noEquipment = isNoEquipmentService(service);
  const definition = state.closeCodes.find((item) => item.code === code);
  const isImproductive = (!definition || !definition.productive || code === "106" || code === "555" || code === "510");

  if (noEquipment || isImproductive) {
    const res = await executeDirectAutoClose(candidate, []);
    if (res && typeof res === "object") {
      if (res.pending) {
        return {
          closed: false,
          pending: true,
          humanReview: false,
          requestId: res.requestId || "",
          reportState: res.reportState || "pending",
          materialPreparation: res.materialPreparation || null,
          reason: res.message || "Aguardando confirmacao do Imperium",
        };
      }
      if (res.closed) {
        return {
          closed: true,
          humanReview: false,
          reason: "",
        };
      }
      return {
        closed: false,
        humanReview: true,
        reason: res.reason || res.error || `Falha ao enviar baixa do codigo ${code}`,
      };
    }
    const success = Boolean(res);
    return {
      closed: success,
      humanReview: !success,
      reason: success ? "" : `Falha ao enviar baixa do codigo ${code}`,
    };
  }

  const equipmentPlan = semiAutoCandidateEquipmentPlan(candidate);
  if (equipmentPlan.error) {
    return { closed: false, humanReview: true, reason: equipmentPlan.error };
  }
  if (equipmentPlan.correction) {
    return {
      closed: false,
      humanReview: true,
      reason: `Substituicao serial ${equipmentPlan.correction.source_serial} -> ${equipmentPlan.correction.replacement_serial} requer baixa principal + correcao de estoque; aguardando protocolo de correcao serial validado`,
    };
  }

  const rawMaterials = semiAutoCandidateMaterials(candidate);
  const materials = consolidateAutoCloseMaterials(
    rawMaterials.filter((item) => !toaLiveMaterialIdentity(item).ignored),
  );

  // Do not remove a TOA material in the browser because one concrete code has
  // zero balance. The backend resolves the official DspLoc/Atlas group by code,
  // consumes sibling codes from technician stock and RETORNO, and blocks safely
  // if the whole official group is unavailable.
  const validMaterials = closeCodeAllowsMaterials(code) ? materials : [];
  candidate.omittedMaterials = [];
  candidate.validatedMaterials = validMaterials;

  const res = await executeDirectAutoClose(candidate, validMaterials);
  if (res && typeof res === "object") {
    if (res.pending) {
      return {
        closed: false,
        pending: true,
        humanReview: false,
        requestId: res.requestId || "",
        reportState: res.reportState || "pending",
        materialPreparation: res.materialPreparation || null,
        reason: res.message || "Aguardando confirmacao do Imperium",
      };
    }
    if (res.closed) {
      return {
        closed: true,
        pending: false,
        humanReview: false,
        reason: "",
      };
    }
    return {
      closed: false,
      humanReview: true,
      reason: res.reason || res.error || "Falha na confirmacao da baixa",
    };
  }
  const success = Boolean(res);
  return {
    closed: success,
    humanReview: !success,
    reason: success ? "" : "Falha na confirmacao da baixa",
  };
}

async function runSemiAutoQueue() {
  if (state.semiAutoWorker) return;
  state.semiAutoWorker = true;
  const profile = state.semiAutoProfile;
  const epoch = state.profileEpoch;
  try {
    while (
      state.semiAutoRunning
      && !state.semiAutoStopRequested
      && state.profile === profile
      && state.profileEpoch === epoch
    ) {
      if (state.semiAutoPaused) {
        await sleep(300);
        continue;
      }
      state.semiAutoToaRetryWaitingUntil = 0;
      semiAutoPromoteDueToaRetries();
      if (semiAutoNeedsImperiumRefresh()) {
        const refreshed = await semiAutoRefreshActiveOrders();
        if (!refreshed) {
          state.semiAutoWaitingWindow = "confirmacao da lista do Imperium";
          renderSemiAutoQueue();
          await sleep(10000);
          continue;
        }
      }
      const now = new Date();
      const job = state.semiAutoJobs.find((item) => (
        item.state === "pending" && semiAutoJobDueNow(item, now)
      ));
      if (!job) {
        const nextWindow = state.semiAutoJobs.find((item) => (
          item.state === "pending" && item.windowStart < 1440
        ));
        const nextToaRetryAt = semiAutoNextToaRetryAt();
        if (!nextWindow && nextToaRetryAt) {
          state.semiAutoWaitingWindow = "";
          state.semiAutoToaRetryWaitingUntil = nextToaRetryAt;
          renderSemiAutoQueue();
          const retryWaitMs = Math.max(1000, nextToaRetryAt - Date.now());
          await sleep(Math.min(retryWaitMs, 30000));
          continue;
        }
        if (!nextWindow) break;
        state.semiAutoWaitingWindow = nextWindow.windowLabel;
        renderSemiAutoQueue();
        const nowMinutes = now.getHours() * 60 + now.getMinutes();
        const waitMs = Math.max(1000, (nextWindow.windowStart - nowMinutes) * 60000);
        // Reavalia em poucos segundos para que uma prioridade manual de janela
        // passe a valer rapidamente, sem interromper o contrato que já está em execução.
        await sleep(Math.min(waitMs, 3000));
        continue;
      }
      state.semiAutoWaitingWindow = "";
      job.state = "searching";
      state.semiAutoCurrentContract = job.contract;
      renderSemiAutoQueue();
      renderToaLiveStatus();
      try {
        const payload = await request(apiUrl("/api/toa-live/lookup"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: job.contract,
            expected_profile_key: profile,
          }),
          timeoutMs: 300000,
        });
        if (
          state.profile !== profile
          || state.profileEpoch !== epoch
          || payload.profile !== profile
        ) {
          throw new Error("shared_state_contamination");
        }
        job.profile = payload.profile;
        job.payload = payload;
        job.candidates = semiAutoCandidates(payload, job);

        if (state.autoCloseMode && job.candidates.length) {
          for (const candidate of job.candidates) {
            if (candidate.reviewed || candidate.closed) continue;
            const res = await processAutoCloseCandidate(candidate, job.profile);
            if (res.pending) {
              candidate.closed = false;
              candidate.pending = true;
              candidate.reviewed = true;
              candidate.closeRequestId = res.requestId || candidate.closeRequestId || "";
              candidate.confirmationState = res.reportState || "pending";
              candidate.materialPreparation = res.materialPreparation || candidate.materialPreparation || null;
              candidate.pendingSince = candidate.pendingSince || Date.now();
              candidate.humanReview = false;
              candidate.humanReviewReason = "";
              void semiAutoRefreshPendingConfirmations();
              showToast(`OS ${candidate.numOs} enviada; aguardando confirmacao do Imperium...`, "info");
            } else if (res.closed) {
              candidate.closed = true;
              candidate.pending = false;
              candidate.reviewed = true;
              candidate.confirmationState = "confirmed";
              if (!candidate.autoCloseCounted) {
                candidate.autoCloseCounted = true;
                state.autoCloseCount = (state.autoCloseCount || 0) + 1;
              }
              showToast(`OS ${candidate.numOs} baixada automaticamente com sucesso!`, "success");
            } else if (res.humanReview) {
              candidate.humanReview = true;
              candidate.humanReviewReason = res.reason;
              state.humanReviewCount = (state.humanReviewCount || 0) + 1;
              showToast(`OS ${candidate.numOs} retida para tratativa humana: ${humanReviewReasonText(res.reason)}`, "warning");
            }
          }
        }

        job.state = job.candidates.length ? "ready" : "skipped";
        if (job.candidates.length) {
          job.skipCategory = "";
          job.skipTitle = "";
          job.skipDetail = "";
          job.toaRetryAt = 0;
          job.toaRetryCount = 0;
          job.message = `${job.candidates.length} OS processada(s)`;
        } else {
          const skipInfo = semiAutoClassifySkip(job, payload);
          job.skipCategory = skipInfo.category;
          job.skipTitle = skipInfo.title;
          job.skipDetail = skipInfo.detail;
          if (semiAutoScheduleToaRetry(job)) {
            job.message = `${skipInfo.detail} Nova consulta automática em 5 min.`;
          } else {
            job.toaRetryAt = 0;
            job.message = skipInfo.detail;
          }
        }
      } catch (error) {
        job.state = semiAutoExpectedSkip(error) ? "skipped" : "error";
        const skipInfo = semiAutoClassifyErrorSkip(job, error);
        job.skipCategory = skipInfo.category;
        job.skipTitle = skipInfo.title;
        job.skipDetail = skipInfo.detail;
        job.message = skipInfo.detail;
      } finally {
        state.semiAutoJobsSinceImperiumCheck += 1;
        state.semiAutoCurrentContract = "";
        renderSemiAutoQueue();
        renderToaLiveStatus();
      }
      await sleep(1000);
    }
  } finally {
    state.semiAutoWorker = false;
    state.semiAutoCurrentContract = "";
    state.semiAutoWaitingWindow = "";
    state.semiAutoToaRetryWaitingUntil = 0;
    if (!state.semiAutoPaused) state.semiAutoRunning = false;
    renderSemiAutoQueue();
    renderToaLiveStatus();
  }
}

async function startAutoCloseQueue() {
  state.autoCloseMode = true;
  state.autoCloseCount = 0;
  state.humanReviewCount = 0;
  await startSemiAutoQueue();
}

async function startSemiAutoQueue() {
  if (state.semiAutoRunning && state.semiAutoPaused) {
    const refreshed = await semiAutoRefreshActiveOrders({ announce: true });
    if (!refreshed) return;
    state.semiAutoPaused = false;
    renderSemiAutoQueue();
    return;
  }
  const refreshed = await semiAutoRefreshActiveOrders({ announce: true });
  if (!refreshed) return;
  const agendaRecords = semiAutoAgendaRecords();
  if (!agendaRecords.length) {
    showToast("Carregue primeiro o CSV ou XLSX com contratos e janelas do TOA.", "warning");
    renderSemiAutoQueue();
    return;
  }
  state.semiAutoJobs = semiAutoBuildJobs(agendaRecords, state.orders, state.profile);
  if (!state.semiAutoJobs.some((job) => job.state === "pending")) {
    showToast(
      "Todos os contratos da agenda ja estao fora de campo no Imperium. A ponte TOA nao foi consultada.",
      "success",
    );
    renderSemiAutoQueue();
    return;
  }
  state.semiAutoProfile = state.profile;
  state.semiAutoStopRequested = false;
  state.semiAutoPaused = false;
  state.semiAutoWaitingWindow = "";
  state.semiAutoToaRetryWaitingUntil = 0;
  state.semiAutoRunning = true;
  renderSemiAutoQueue();
  void runSemiAutoQueue();
}

function toggleSemiAutoPause() {
  if (!state.semiAutoRunning) return;
  state.semiAutoPaused = !state.semiAutoPaused;
  renderSemiAutoQueue();
}

function stopSemiAutoQueue() {
  state.semiAutoStopRequested = true;
  state.semiAutoPaused = false;
  state.semiAutoRunning = false;
  state.semiAutoWaitingWindow = "";
  state.semiAutoToaRetryWaitingUntil = 0;
  renderSemiAutoQueue();
}

function toaLiveInventorySummary(capture) {
  const section = automationNode("div", "toa-live-inventory");
  const groups = [
    ["Instalados", capture.installed_equipment || []],
    ["Retirados", capture.removed_equipment || []],
    ["Miscelaneas", capture.materials || []],
  ];
  groups.forEach(([label, items]) => {
    const group = automationNode("div");
    group.append(automationNode("span", "", label));
    const value = items.length
      ? items.map(automationInventoryLabel).join(" | ")
      : "Nenhum";
    group.append(automationNode("strong", "", value));
    section.append(group);
  });
  return section;
}

function toaLiveWindowSort(capture) {
  const values = Array.isArray(capture.window_sort) ? capture.window_sort : [];
  return [Number(values[0] ?? 1440), Number(values[1] ?? 1440)];
}

function toaLiveWindowLabel(capture) {
  return String(capture.operational_window || "Sem janela").trim() || "Sem janela";
}

function toaLiveWindowHeading(label, captures, currentWindow) {
  const heading = automationNode("div", "toa-live-window-heading");
  const identity = automationNode("div");
  const isCurrent = label === currentWindow;
  identity.append(
    automationNode("span", "", isCurrent ? "JANELA OPERACIONAL ATUAL" : "JANELA OPERACIONAL"),
    automationNode("strong", "", label),
  );
  heading.append(
    identity,
    automationNode("span", "toa-live-window-count", `${captures.length} atividade${captures.length === 1 ? "" : "s"}`),
  );
  if (isCurrent) heading.classList.add("current");
  return heading;
}

function toaLiveCaptureCard(capture, requestedOs) {
  const article = automationNode("article", "toa-live-capture");
  const heading = automationNode("header");
  const identity = automationNode("div");
  identity.append(
    automationNode("span", "", `AID ${capture.aid || "-"}`),
    automationNode("h4", "", `${capture.work_type || "Atividade"} | Contrato ${capture.contract}`),
  );
  heading.append(
    identity,
    automationNode("strong", `automation-decision ${capture.decision}`, automationDecisionLabel(capture.decision)),
  );
  article.append(heading);

  const officialWindow = capture.official_service_window || capture.service_window || "Nao informada";
  const operationalWindow = toaLiveWindowLabel(capture);
  const facts = automationNode("div", "toa-live-facts");
  [
    ["Cidade", capture.city || "Nao informada"],
    ["Tecnico", automationProviderLabel(capture.assigned_technician)],
    ["Status", capture.activity_status || "Nao informado"],
    ["Janela operacional", operationalWindow],
    ["Janela oficial TOA", officialWindow],
    ["Rota", automationProviderLabel(capture.route_provider)],
  ].forEach(([label, value]) => {
    const item = automationNode("div");
    item.append(automationNode("span", "", label), automationNode("strong", "", value));
    facts.append(item);
  });
  article.append(facts);
  if (capture.operational_window_source === "current_disconnection") {
    article.append(automationNode(
      "p",
      "toa-live-operational-note",
      `Desconexao com janela oficial ${officialWindow}: priorizada na faixa atual ${operationalWindow}.`,
    ));
  }
  article.append(toaLiveInventorySummary(capture));

  const tasks = automationNode("div", "toa-live-tasks");
  (capture.tasks || []).forEach((task) => {
    const row = automationNode("div", "toa-live-task");
    const isRequested = Boolean(task.requested || (
      requestedOs && String(task.os_number || "") === String(requestedOs)
    ));
    if (isRequested) row.classList.add("requested");
    const details = automationNode("div");
    const match = toaLiveImperiumMatch(capture, task);
    const service = String(
      task.service || task.os_type || match?.service || capture.work_type || "Servico nao informado",
    ).replace(/^\s*\d+\s*-\s*/, "").trim();
    details.append(
      automationNode("strong", "", `OS ${task.os_number || "-"}${isRequested ? " | PESQUISADA" : ""}`),
      automationNode("span", "", service),
      automationNode(
        "span",
        "",
        `Codigo ${task.close_code || "-"} | TOA ${task.status || "-"} | Imperium ${task.imperium_status || (match ? "EM CAMPO" : "FORA DA LISTA EM CAMPO")}`,
      ),
    );
    const actions = automationNode("div", "semi-auto-item-actions");
    const closeBtn = automationNode("button", "button primary compact", "Baixar esta OS");
    closeBtn.type = "button";
    closeBtn.disabled = !match || !task.close_code || !state.closeEnabled;
    closeBtn.title = match
      ? "Abrir editor e enviar a baixa desta OS imediatamente"
      : "OS nao localizada na lista atual do Imperium";
    closeBtn.addEventListener("click", () => {
      prepareToaLiveClose(capture, task, { openEditor: true });
    });

    const prepareBtn = automationNode("button", "button secondary compact", "Preparar no editor");
    prepareBtn.type = "button";
    prepareBtn.disabled = !match || !task.close_code;
    prepareBtn.title = match
      ? "Carregar estes dados no editor sem abrir o modal de baixa imediatamente"
      : "OS nao localizada na lista atual do Imperium";
    prepareBtn.addEventListener("click", () => {
      prepareToaLiveClose(capture, task, { openEditor: false });
    });

    actions.append(closeBtn, prepareBtn);
    row.append(details, actions);
    tasks.append(row);
  });
  article.append(tasks);

  const warnings = [...(capture.validation_errors || []), ...(capture.validation_warnings || [])];
  if (warnings.length) {
    article.append(automationNode("p", "toa-live-warning", warnings.join(" | ")));
  }
  return article;
}

function renderToaLiveResult() {
  const payload = state.toaLiveResult;
  elements.toaLiveResult.classList.toggle("hidden", !payload);
  if (!payload) {
    elements.toaLiveResult.replaceChildren();
    return;
  }
  const nodes = [];
  const captures = [...(payload.results || [])].sort((left, right) => {
    const [leftStart, leftEnd] = toaLiveWindowSort(left);
    const [rightStart, rightEnd] = toaLiveWindowSort(right);
    return leftStart - rightStart || leftEnd - rightEnd
      || String(left.contract || "").localeCompare(String(right.contract || ""))
      || String(left.aid || "").localeCompare(String(right.aid || ""));
  });
  const groups = new Map();
  captures.forEach((capture) => {
    const label = toaLiveWindowLabel(capture);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(capture);
  });
  groups.forEach((groupCaptures, label) => {
    nodes.push(toaLiveWindowHeading(label, groupCaptures, payload.current_operational_window));
    groupCaptures.forEach((capture) => {
      nodes.push(toaLiveCaptureCard(capture, payload.requested_os));
    });
  });
  elements.toaLiveResult.replaceChildren(...nodes);
  document.dispatchEvent(new CustomEvent("dominium:toa-results", {
    detail: { cards: nodes },
  }));
}

async function lookupToaLiveContract() {
  const query = elements.toaLiveContract.value.replace(/\D/g, "");
  if (query.length < 5 || state.toaLiveLoading) return;
  state.toaLiveLoading = true;
  const requestedProfile = state.profile;
  const requestedEpoch = state.profileEpoch;
  state.toaLiveResult = null;
  const lookupStartedAt = Date.now();
  const updateLookupProgress = () => {
    const elapsed = Math.max(0, Math.floor((Date.now() - lookupStartedAt) / 1000));
    const phase = elapsed < 3
      ? "Enviando a consulta para a ponte segura"
      : elapsed < 10
        ? "Coletor consultando o TOA em segundo plano"
        : "Aguardando os equipamentos, materiais e tarefas do TOA";
    elements.toaLiveLookupMessage.textContent = `${phase} · ${query} · ${elapsed}s`;
  };
  updateLookupProgress();
  const lookupProgressTimer = window.setInterval(updateLookupProgress, 1000);
  renderToaLiveStatus();
  renderToaLiveResult();
  try {
    const payload = await request(apiUrl("/api/toa-live/lookup"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        expected_profile_key: requestedProfile,
      }),
      timeoutMs: 300000,
    });
    if (
      state.profile !== requestedProfile
      || state.profileEpoch !== requestedEpoch
      || payload.profile !== requestedProfile
    ) {
      throw new Error("shared_state_contamination");
    }
    state.toaLiveResult = payload;
    state.toaLiveStatus = payload.session || state.toaLiveStatus;
    const count = (payload.results || []).length;
    const target = payload.query_type === "os"
      ? `OS ${payload.requested_os} no contrato ${payload.resolved_contract}`
      : `contrato ${payload.resolved_contract}`;
    const foundNote = payload.query_type === "os" && !payload.requested_os_found
      ? " A OS nao apareceu nas tarefas capturadas; confira a atividade retornada."
      : "";
    elements.toaLiveLookupMessage.textContent = `${target}: ${count} atividade${count === 1 ? "" : "s"} em ${payload.elapsed_seconds}s, separada${count === 1 ? "" : "s"} por janela.${foundNote}`;
    renderToaLiveResult();
    showToast("Consulta TOA concluida. Selecione a OS para preparar a baixa.", "success");
  } catch (error) {
    let msg = error.message;
    if (msg.includes("toa_resposta_busca_invalida")) {
      msg = "Contrato nao localizado no TOA desta base. Verifique se o contrato pertence a base/cidade selecionada.";
    } else if (msg.includes("toa_contrato_nao_encontrado")) {
      msg = "Contrato nao encontrado no TOA.";
    }
    elements.toaLiveLookupMessage.textContent = msg;
    showToast(msg, "error");
    console.error("Falha na consulta ao vivo do TOA", error);
  } finally {
    window.clearInterval(lookupProgressTimer);
    if (
      state.profile === requestedProfile
      && state.profileEpoch === requestedEpoch
    ) {
      state.toaLiveLoading = false;
      renderToaLiveStatus();
    }
  }
}

// =============================================================================
// IMPERIUM | EDITOR DE MOVIMENTACAO, SERIAIS E MISCELANEAS
// =============================================================================
function defaultMovement(order, code) {
  if (code === "430") return "remove";
  if (code === "706") return "install";
  if (code === "517" || code === "518" || code === "519" || code === "520" || code === "521") return "swap";
  const service = normalize(order.service);
  return (service.includes("TROCA") || service.includes("MUDANCA DE PACOTE") || service.includes("RETORNO")) ? "swap" : "install";
}

function movementIsFixed(order, code) {
  const service = normalize(order.service);
  return code === "430" || code === "706" || code === "517"
    || service.includes("TROCA") || service.includes("MUDANCA DE PACOTE");
}

function equipmentContainer(kind) {
  return kind === "installed" ? elements.installedRows : elements.removedRows;
}

function refreshEquipmentRemoveButtons(kind) {
  const rows = [...equipmentContainer(kind).querySelectorAll(".equipment-row")];
  rows.forEach((row) => {
    row.querySelector(".remove-equipment").disabled = false;
  });
  const addButton = kind === "installed" ? elements.addInstalled : elements.addRemoved;
  const limit = kind === "installed" && state.pendingProductive?.code === "706" ? 1 : 300;
  addButton.disabled = rows.length >= limit;
  addButton.title = rows.length >= limit
    ? `Limite de ${limit} equipamento${limit === 1 ? "" : "s"}`
    : `Adicionar equipamento ${kind === "installed" ? "instalado" : "removido"}`;
}

function addEquipmentRow(kind, initial = {}) {
  const container = equipmentContainer(kind);
  const row = document.createElement("div");
  row.className = "equipment-row";

  const serial = document.createElement("input");
  serial.type = "text";
  serial.inputMode = "text";
  serial.autocomplete = "off";
  serial.className = "equipment-serial";
  serial.placeholder = kind === "installed" ? "Serial instalado" : "Serial removido";
  serial.setAttribute("aria-label", serial.placeholder);
  serial.minLength = kind === "installed" ? 4 : 8;
  serial.maxLength = 25;
  serial.pattern = kind === "installed" ? "[A-Za-z0-9]{4,25}" : "[A-Za-z0-9]{8,25}";
  serial.required = true;
  serial.value = initial.serial || "";

  const type = document.createElement("select");
  type.className = "equipment-type";
  type.setAttribute("aria-label", "Tipo do equipamento");
  if (kind === "installed") type.add(new Option("Automatico", "auto"));
  type.add(new Option("Decoder", "decoder"));
  type.add(new Option("EMTA", "emta"));
  type.add(new Option("Smart", "smart"));
  if (kind === "installed") type.add(new Option("Chip", "chip"));
  const chipClose = kind === "installed" && state.pendingProductive?.code === "706";
  type.value = initial.type || (chipClose ? "chip" : kind === "installed" ? "auto" : "decoder");
  serial.addEventListener("input", () => {
    const value = serial.value.trim();
    if (chipClose) {
      type.value = "chip";
    } else if (/[A-Za-z]/.test(value)) {
      type.value = "emta";
    } else if (/^\d+$/.test(value) && (type.value === "auto" || type.value === "emta")) {
      type.value = "decoder";
    }
  });

  const remove = document.createElement("button");
  remove.className = "icon-button remove-equipment";
  remove.type = "button";
  remove.textContent = "x";
  remove.title = "Remover equipamento";
  remove.setAttribute("aria-label", "Remover equipamento");
  remove.addEventListener("click", () => {
    row.remove();
    refreshEquipmentRemoveButtons(kind);
  });

  row.append(serial, type, remove);
  container.append(row);
  refreshEquipmentRemoveButtons(kind);
  return row;
}

function setEquipmentSection(kind, enabled) {
  const section = kind === "installed" ? elements.installedSection : elements.removedSection;
  section.classList.toggle("hidden", !enabled);
  section.querySelectorAll("input, select, button").forEach((control) => {
    control.disabled = !enabled;
  });
  refreshEquipmentRemoveButtons(kind);
}

function equipmentValues(kind) {
  return [...equipmentContainer(kind).querySelectorAll(".equipment-row")].map((row) => ({
    serial: row.querySelector(".equipment-serial").value.trim().toUpperCase(),
    type: row.querySelector(".equipment-type").value,
  }));
}

function refreshMaterialControls() {
  const rows = [...elements.materialRows.querySelectorAll(".material-row")];
  elements.addMaterial.disabled = state.materialLoading
    || state.materialPasteLoading
    || Boolean(state.materialError)
    || state.materialInventory.length === 0
    || rows.length >= 300;
  if (state.materialLoading) {
    elements.materialStatus.textContent = "Consultando estoque";
  } else if (state.materialPasteLoading) {
    elements.materialStatus.textContent = "Correlacionando colagem TOA";
  } else if (state.materialError) {
    elements.materialStatus.textContent = state.materialError;
  } else if (state.materialNotice) {
    elements.materialStatus.textContent = state.materialNotice;
  } else {
    elements.materialStatus.textContent = `${state.materialInventory.length} itens no estoque`;
  }
  elements.processMaterialPaste.disabled = state.materialLoading || state.materialPasteLoading;
  const selectedEquivalences = rows.map((row) => {
    const code = row.querySelector(".material-code").value;
    const quantity = Number(row.querySelector(".material-quantity").value || 0);
    const material = state.materialInventory.find((item) => item.code === code);
    return material?.requires_confirmation ? { material, quantity } : null;
  }).filter(Boolean);
  elements.materialEquivalenceReview.classList.toggle(
    "hidden",
    selectedEquivalences.length === 0,
  );
  elements.materialEquivalenceSummary.replaceChildren(
    ...selectedEquivalences.map(({ material, quantity }) => {
      const line = document.createElement("span");
      const sources = (material.source_codes || []).join(" + ") || "Codigo TOA";
      line.textContent = `${sources} -> ${material.code} (${quantity} ${material.unit || ""})`;
      return line;
    }),
  );
  if (selectedEquivalences.length === 0) {
    state.materialEquivalenceConfirmed = false;
    elements.materialEquivalenceConfirm.checked = false;
  }
  const hasUnconfirmedEquivalence = selectedEquivalences.length > 0
    && !state.materialEquivalenceConfirmed;
  const materialsVisible = !elements.materialSection.classList.contains("hidden");
  elements.equipmentConfirm.disabled = materialsVisible
    && (state.materialPasteLoading || hasUnconfirmedEquivalence);
}

function updateMaterialStock(row) {
  const code = row.querySelector(".material-code").value;
  const material = state.materialInventory.find((item) => item.code === code);
  const stock = row.querySelector(".material-stock");
  const quantity = Number(row.querySelector(".material-quantity").value || 0);
  const sourceCodes = (material?.source_codes || []).filter((value) => value !== code);
  const technicianStock = Number(material?.stock_quantity || 0);
  const hasReturnStock = material?.return_stock_quantity !== undefined
    && material?.return_stock_quantity !== null;
  const returnStock = Number(material?.return_stock_quantity || 0);
  const shortage = Math.max(0, quantity - technicianStock);
  const totalAvailable = technicianStock + (hasReturnStock ? returnStock : 0);
  const insufficient = Boolean(material && quantity > technicianStock && (
    state.profile !== "natal"
    || !hasReturnStock
    || quantity > totalAvailable
  ));
  stock.replaceChildren();
  if (material?.status === "unresolved") {
    stock.textContent = "Nao localizado (sera ignorado)";
  } else if (!material) {
    stock.textContent = "Selecione o material";
  } else {
    const technicianChip = document.createElement("span");
    technicianChip.className = "material-stock-chip technician";
    technicianChip.textContent = `Tecnico ${technicianStock} ${material.unit || ""}`;
    stock.append(technicianChip);
    if (hasReturnStock) {
      const returnChip = document.createElement("span");
      returnChip.className = "material-stock-chip return";
      returnChip.textContent = `RETORNO ${returnStock} ${material.unit || ""}`;
      stock.append(returnChip);
    }
    if (material.requires_confirmation) {
      const equivalence = document.createElement("span");
      equivalence.className = "material-stock-detail";
      equivalence.textContent = `Equiv. ${sourceCodes.join(" + ")}`;
      stock.append(equivalence);
    }
    if (shortage) {
      const detail = document.createElement("span");
      detail.className = `material-stock-detail ${insufficient ? "blocked" : "covered"}`;
      detail.textContent = insufficient
        ? (totalAvailable <= 0
            ? "Sem saldo (sera descartado da baixa)"
            : `RETORNO complementa ${returnStock} (faltam ${Math.max(0, quantity - totalAvailable)})`)
        : `RETORNO complementa ${shortage}`;
      stock.append(detail);
    }
  }
  stock.classList.toggle(
    "warning",
    Boolean(material && (
      material.status === "unresolved"
      || material.requires_confirmation
      || quantity > technicianStock
    )),
  );
  stock.classList.toggle("shortfall", insufficient);
  refreshMaterialControls();
}

function addMaterialRow(initial = {}) {
  const row = document.createElement("div");
  row.className = "material-row";

  const code = document.createElement("select");
  code.className = "material-code";
  code.required = true;
  code.setAttribute("aria-label", "Miscelanea");
  code.add(new Option("Selecione a miscelanea", ""));
  state.materialInventory
    .filter((material) => !toaLiveMaterialIdentity({ code: material.code, description: material.name }).ignored)
    .forEach((material) => {
      code.add(new Option(
        `${material.code} - ${material.name}`,
        material.code,
      ));
    });
  const initialResolvedCode = resolveMaterialCodeWithEquivalence(initial.code, state.materialInventory);
  code.value = initialResolvedCode || initial.code || "";

  const quantity = document.createElement("input");
  quantity.className = "material-quantity";
  quantity.type = "number";
  quantity.inputMode = "numeric";
  quantity.min = "1";
  quantity.max = "65535";
  quantity.step = "1";
  quantity.required = true;
  quantity.value = initial.quantity || 1;
  quantity.setAttribute("aria-label", "Quantidade da miscelanea");

  const stock = document.createElement("span");
  stock.className = "material-stock";

  const remove = document.createElement("button");
  remove.className = "icon-button remove-equipment";
  remove.type = "button";
  remove.textContent = "x";
  remove.title = "Remover miscelanea";
  remove.setAttribute("aria-label", "Remover miscelanea");
  remove.addEventListener("click", () => {
    row.remove();
    refreshMaterialControls();
  });
  code.addEventListener("change", () => updateMaterialStock(row));
  quantity.addEventListener("input", () => updateMaterialStock(row));

  row.append(code, quantity, stock, remove);
  elements.materialRows.append(row);
  updateMaterialStock(row);
  refreshMaterialControls();
  return row;
}

function materialValues() {
  return [...elements.materialRows.querySelectorAll(".material-row")].map((row) => {
    const code = row.querySelector(".material-code").value;
    const material = state.materialInventory.find((item) => item.code === code);
    if (!material || !code) return null;
    const quantity = Number(row.querySelector(".material-quantity").value || 0);
    if (quantity <= 0) return null;
    const techStock = Number(material.stock_quantity || 0);
    const retStock = Number(material.return_stock_quantity || 0);
    const totalAvail = techStock + retStock;
    // Se o item nao tem saldo nem no tecnico nem no retorno, descarta automaticamente da baixa
    if (totalAvail <= 0) return null;
    const finalQty = Math.min(quantity, totalAvail);
    return {
      code,
      description: material.lookup_description || material.name || "",
      quantity: finalQty,
      source_codes: material.source_codes || [code],
      match_type: material.match_type || "exact",
      requires_confirmation: Boolean(material.requires_confirmation),
      equivalence_confirmed: Boolean(
        !material.requires_confirmation || state.materialEquivalenceConfirmed
      ),
    };
  }).filter(Boolean);
}

function expectedEquipmentType(service) {
  const value = normalize(service);
  if (value.includes("CHIP") || value.includes("SIM CARD") || value.includes("SIMCARD") || value.includes("LINHA MOVEL")) return "chip";
  if (value.includes("STREAM") || value.includes("DECODER") || value.includes("CLARO TV") || value.includes("TV")) return "decoder";
  if (value.includes("PONTO VIRT") || value.includes("VIRTUA") || value.includes("EMTA") || value.includes("INTERNET") || value.includes("BANDA LARGA") || value.includes("WIFI") || value.includes("MODEM")) return "emta";
  return "";
}

const APPROVED_MATERIAL_EQUIVALENCE_GROUPS = [
  { key: "fiber_connector", codes: ["22057620", "22065513", "22069613", "22065512"] },
  { key: "fixador_rg6", codes: ["22025091", "22025139", "22057635", "22060738"] },
  { key: "cabo_rg6_preto", codes: ["22026223", "22066906"] },
  { key: "cabo_rg6_branco", codes: ["22026219", "22066907"] },
  { key: "cabo_drop_1fo", codes: ["22061736", "22061796", "22026267"] },
  { key: "fita_isolante", codes: ["22025072", "22064608", "22056696"] },
  { key: "anel_vedacao", codes: ["22024800", "22025321"] },
  { key: "mini_isolador", codes: ["22056364", "22067384"] },
  { key: "isolador", codes: ["22056366", "22066517", "22056394"] },
  { key: "abracadeira", codes: ["22055828", "22023400", "22025247", "22056346"] },
  { key: "pitao_bucha", codes: ["22026502", "22056395", "22061434", "22026489"] },
  { key: "conector_utp_rj45", codes: ["22061811", "22026169", "22059179"] },
  { key: "conector_rg11", codes: ["22026147", "22056764"] },
  { key: "cabo_rg11", codes: ["22057341", "22057156"] },
  { key: "marcador_casa_0", codes: ["22056342", "22065718", "22066616", "22055829"] },
  { key: "marcador_casa_1", codes: ["22056343", "22065719", "22066615", "22055830"] },
  { key: "marcador_casa_2", codes: ["22056344", "22065720", "22066614", "22055831"] },
  { key: "marcador_casa_3", codes: ["22056345", "22065721", "22066613", "22055832"] },
  { key: "marcador_casa_4", codes: ["22056340", "22065722", "22066612", "22055833"] },
  { key: "marcador_casa_5", codes: ["22056331", "22065723", "22066611", "22055835"] },
  { key: "marcador_casa_6", codes: ["22056336", "22065724", "22066610"] },
  { key: "marcador_casa_7", codes: ["22056341", "22065725", "22066609", "22055827"] },
  { key: "marcador_casa_8", codes: ["22056337", "22065726", "22066608", "22055857"] },
  { key: "marcador_casa_9", codes: ["22056339", "22065727", "22066607"] },
  { key: "marcador_casa_a", codes: ["22025114", "22065728"] },
  { key: "marcador_casa_b", codes: ["22025115", "22065729"] },
  { key: "marcador_casa_c", codes: ["22025116", "22065730"] },
  { key: "marcador_casa_d", codes: ["22025117", "22065731"] },
  { key: "marcador_casa_e", codes: ["22025119", "22065732"] },
];

function autoCloseMaterialFamily(code) {
  const codeStr = String(code || "").trim();
  const group = APPROVED_MATERIAL_EQUIVALENCE_GROUPS.find((item) => item.codes.includes(codeStr));
  return group || { key: `code_${codeStr}`, codes: [codeStr] };
}

function consolidateAutoCloseMaterials(materials = []) {
  const grouped = new Map();
  (materials || []).forEach((material) => {
    const quantity = Number(material?.quantity || 0);
    const code = String(material?.code || "").trim();
    if (!code || !Number.isFinite(quantity) || quantity <= 0) return;
    const family = autoCloseMaterialFamily(code);
    // Preserve the concrete TOA code. Equivalence is resolved authoritatively
    // by the Imperium backend/DspLoc, never by frontend text or family guesses.
    const key = `code_${code}`;
    const current = grouped.get(key) || {
      ...material,
      code,
      quantity: 0,
      sourceCodes: [code],
      materialFamily: family.key,
    };
    current.quantity += quantity;
    grouped.set(key, current);
  });
  return [...grouped.values()];
}

function allocateAutoCloseMaterial(material, inventory = []) {
  const requested = Number(material?.quantity || 0);
  const originalCode = String(material?.code || "").trim();
  const family = autoCloseMaterialFamily(originalCode);
  const allowedCodes = new Set(family.codes.map(String));
  const candidates = (inventory || [])
    .filter((item) => allowedCodes.has(String(item.code || "")))
    .map((item) => ({
      item,
      code: String(item.code || ""),
      technician: Number(item.stock_quantity || 0),
      retorno: Number(item.return_stock_quantity || 0),
    }))
    .filter((entry) => entry.technician + entry.retorno > 0)
    .sort((left, right) => {
      const priority = (entry) => {
        const exact = entry.code === originalCode;
        if (entry.technician > 0) return exact ? 0 : 1;
        if (entry.retorno > 0) return exact ? 2 : 3;
        return 4;
      };
      return priority(left) - priority(right)
        || (right.technician + right.retorno) - (left.technician + left.retorno);
    });
  let remaining = requested;
  const allocated = [];
  candidates.forEach((entry) => {
    if (remaining <= 0) return;
    const available = entry.technician + entry.retorno;
    const quantity = Math.min(remaining, available);
    if (quantity <= 0) return;
    allocated.push({
      ...material,
      code: entry.code,
      quantity,
      allocation: {
        technician_stock: entry.technician,
        return_stock: entry.retorno,
      },
    });
    remaining -= quantity;
  });
  return { allocated, missingQuantity: Math.max(0, remaining), candidates };
}

function resolveMaterialCodeWithEquivalence(code, inventory = []) {
  const codeStr = String(code || "").trim();
  const group = APPROVED_MATERIAL_EQUIVALENCE_GROUPS.find((g) => g.codes.includes(codeStr));
  const exact = inventory.find((m) => String(m.code) === codeStr);

  // 1. If exact code has positive technician stock (> 0), keep exact
  if (exact && Number(exact.stock_quantity || 0) > 0) {
    return exact.code;
  }

  // 2. If equivalence group has an item with positive technician stock (> 0), switch to it!
  if (group) {
    const matchedWithStock = inventory.find(
      (m) => group.codes.includes(String(m.code)) && Number(m.stock_quantity || 0) > 0
    );
    if (matchedWithStock) return matchedWithStock.code;
  }

  // 3. If exact code has return stock (> 0), keep exact
  if (exact && Number(exact.return_stock_quantity || 0) > 0) {
    return exact.code;
  }

  // 4. If equivalence group has return stock (> 0), use it
  if (group) {
    const matchedWithRetStock = inventory.find(
      (m) => group.codes.includes(String(m.code)) && Number(m.return_stock_quantity || 0) > 0
    );
    if (matchedWithRetStock) return matchedWithRetStock.code;
  }

  // 5. Fallback: exact if found in inventory, or any group member found in inventory
  if (exact) return exact.code;
  if (group) {
    const matched = inventory.find((m) => group.codes.includes(String(m.code)));
    if (matched) return matched.code;
  }
  const canonical = CANONICAL_MATERIAL_MAP[codeStr];
  return canonical ? canonical.code : codeStr;
}

function mergeMaterialInventory(materials) {
  const merged = new Map(state.materialInventory.map((item) => [item.code, item]));
  materials.forEach((item) => {
    merged.set(item.code, { ...merged.get(item.code), ...item });
  });
  state.materialInventory = [...merged.values()].sort((a, b) => (
    `${a.code} ${a.name}`.localeCompare(`${b.code} ${b.name}`)
  ));
}

function materialPasteKey(text) {
  let hash = 2166136261;
  const normalized = text.replace(/\s+/g, " ").trim().toUpperCase();
  for (let index = 0; index < normalized.length; index += 1) {
    hash ^= normalized.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function materialPasteAssignments() {
  const key = `imperium-toa-misc-${localDate()}-${state.profile}`;
  try {
    return { key, values: JSON.parse(sessionStorage.getItem(key) || "{}") };
  } catch {
    return { key, values: {} };
  }
}

async function processMaterialPaste() {
  const pending = state.pendingProductive;
  const text = elements.materialPaste.value.trim();
  if (!pending || !text || state.materialPasteLoading) return;
  const pasteKey = materialPasteKey(text);
  state.materialPasteLoading = true;
  state.materialNotice = "";
  state.materialEquivalenceConfirmed = false;
  elements.materialEquivalenceConfirm.checked = false;
  refreshMaterialControls();
  try {
    const payload = await request(
      apiUrl(`/api/orders/${pending.order.id_os}/material-paste`),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        timeoutMs: 60000,
      },
    );
    if (state.pendingProductive?.order.id_os !== pending.order.id_os) return;
    state.materialError = "";
    const resolvedPasteKey = payload.paste_key || pasteKey;
    const resolvedAssignments = materialPasteAssignments();
    const assignedOs = payload.material_assignment?.os_number
      || resolvedAssignments.values[resolvedPasteKey];

    const expectedType = expectedEquipmentType(pending.order.service);
    let equipment = payload.equipment.filter((item) => item.equipment_type === expectedType);
    if (!expectedType && payload.equipment.length === 1) equipment = payload.equipment;
    const selectedEquipment = equipment.length === 1 ? equipment[0] : null;
    if (selectedEquipment) {
      elements.installedRows.replaceChildren();
      addEquipmentRow("installed", {
        serial: selectedEquipment.serial,
        type: selectedEquipment.equipment_type,
      });
    }
    const materialsAlreadyUsed = assignedOs && assignedOs !== pending.order.num_os;
    const selectedMaterials = materialsAlreadyUsed ? [] : payload.materials;
    mergeMaterialInventory(selectedMaterials);
    elements.materialRows.replaceChildren();
    selectedMaterials
      .forEach((item) => addMaterialRow({ code: item.code, quantity: item.quantity }));

    const validation = payload.validation || {};
    const unresolved = Number(validation.unresolved_count
      ?? selectedMaterials.filter((item) => item.status === "unresolved").length);
    const shortage = Number(validation.shortage_count
      ?? selectedMaterials.filter((item) => item.status === "shortage").length);
    const equivalent = Number(validation.equivalent_count
      ?? selectedMaterials.filter((item) => item.requires_confirmation).length);
    const ignored = Number(validation.ignored_count || 0);
    const parts = [`${selectedMaterials.length} miscelaneas coladas`];
    if (ignored) {
      parts.push(
        `${ignored} acessorio${ignored === 1 ? "" : "s"} ignorado${ignored === 1 ? "" : "s"} `
        + "(fonte, cabo de forca, HDMI ou pilha)",
      );
    }
    if (materialsAlreadyUsed) {
      parts.push(`miscelaneas ja usadas na OS ${assignedOs}`);
    }
    if (shortage) {
      parts.push(
        state.profile === "natal"
          ? `${shortage} com complemento do estoque virtual RETORNO`
          : `${shortage} com saldo insuficiente`,
      );
    }
    if (unresolved) parts.push(`${unresolved} nao correlacionadas`);
    if (equivalent) parts.push(`${equivalent} equivalencias aguardando confirmacao`);
    if (!selectedEquipment && payload.equipment.length > 1) {
      parts.push("equipamento nao definido pelo servico");
    }
    state.currentMaterialPasteKey = resolvedPasteKey;
    state.materialNotice = parts.join("; ");
    const blockingShortage = shortage > 0 && state.profile !== "natal";
    showToast(
      state.materialNotice,
      unresolved || blockingShortage ? "error" : "success",
    );
  } catch (error) {
    state.materialNotice = error.message;
    showToast(error.message, "error");
    console.error("Falha ao processar colagem TOA", error);
  } finally {
    state.materialPasteLoading = false;
    refreshMaterialControls();
  }
}

async function loadMaterialInventory(order) {
  state.materialInventory = [];
  state.materialError = "";
  state.materialNotice = "";
  state.materialEquivalenceConfirmed = false;
  elements.materialEquivalenceConfirm.checked = false;
  state.materialLoading = true;
  refreshMaterialControls();
  try {
    let payload = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        payload = await request(
          apiUrl(`/api/orders/${order.id_os}/material-inventory`),
          { timeoutMs: 50000 },
        );
        break;
      } catch (err) {
        if (err.status === 409 && attempt < 4) {
          await sleep(1500);
          continue;
        }
        throw err;
      }
    }
    if (state.pendingProductive?.order.id_os !== order.id_os) return;
    state.materialInventory = [...(payload?.materials || [])].sort((a, b) => (
      `${a.code} ${a.name}`.localeCompare(`${b.code} ${b.name}`)
    ));
    state.materialNotice = payload?.return_stock_error
      ? "Estoque RETORNO indisponivel; faltas serao bloqueadas por seguranca"
      : payload?.return_stock_name
        ? "Saldos do tecnico e do RETORNO conferidos"
        : "Saldo do tecnico conferido";
  } catch (error) {
    if (state.pendingProductive?.order.id_os !== order.id_os) return;
    state.materialError = error.message;
    console.error("Falha ao consultar estoque de miscelaneas", error);
  } finally {
    if (state.pendingProductive?.order.id_os === order.id_os) {
      state.materialLoading = false;
      refreshMaterialControls();
    }
  }
}

function updateEquipmentFields() {
  const movement = elements.movement.value;
  setEquipmentSection("installed", movement === "install" || movement === "swap");
  setEquipmentSection("removed", movement === "remove" || movement === "swap");
  const materialsEnabled = closeCodeAllowsMaterials(state.pendingProductive?.code) && (movement === "install" || movement === "swap");
  elements.materialSection.classList.toggle("hidden", !materialsEnabled);
  elements.materialSection.querySelectorAll("input, select, button").forEach((control) => {
    control.disabled = !materialsEnabled;
  });
  if (materialsEnabled) refreshMaterialControls();
}

function openEquipmentDialog(order, definition, extra = {}) {
  const draft = state.productiveDrafts[operationDraftKey(order)];
  state.pendingProductive = {
    order,
    code: definition.code,
    extra: {
      observation: draft?.observation || "",
      ...extra,
    },
  };
  elements.equipmentOrder.textContent = extra.retry_of_request_id
    ? `Nova tentativa controlada - OS ${order.num_os} - ${order.service}`
    : `OS ${order.num_os} - ${order.service}`;
  elements.equipmentCode.textContent = definition.code;
  elements.equipmentDescription.textContent = definition.description;
  elements.installedRows.replaceChildren();
  elements.removedRows.replaceChildren();
  elements.materialRows.replaceChildren();
  elements.materialPaste.value = draft?.material_paste || "";
  state.materialInventory = [];
  state.materialError = "";
  state.materialNotice = "";
  state.materialPasteLoading = false;
  state.currentMaterialPasteKey = "";
  state.materialEquivalenceConfirmed = false;
  elements.materialEquivalenceConfirm.checked = false;
  const service = normalize(order.service);
  const isAssinatura = service.includes("ASSINATURA");
  state.materialLoading = closeCodeAllowsMaterials(definition.code) && !isAssinatura;
  elements.movement.value = draft?.code === definition.code
    ? draft.movement
    : defaultMovement(order, definition.code);
  elements.movement.disabled = movementIsFixed(order, definition.code);
  updateEquipmentFields();
  if (draft?.code === definition.code) {
    elements.installedRows.replaceChildren();
    elements.removedRows.replaceChildren();
    (draft.installed_equipment || []).forEach((item) => addEquipmentRow("installed", item));
    (draft.removed_equipment || []).forEach((item) => addEquipmentRow("removed", item));
    updateEquipmentFields();
    state.currentMaterialPasteKey = draft.toa_paste_key || "";
  }
  elements.equipmentDialog.showModal();
  if (closeCodeAllowsMaterials(definition.code) && !isAssinatura) {
    loadMaterialInventory(order).then(() => {
      if (state.pendingProductive?.order.id_os !== order.id_os) return;
      if (draft?.code !== definition.code) return;
      (draft.materials || []).forEach((item) => {
        const resolvedCode = resolveMaterialCodeWithEquivalence(item.code, state.materialInventory);
        const canonical = CANONICAL_MATERIAL_MAP[resolvedCode] || CANONICAL_MATERIAL_MAP[item.code];
        const resolvedName = (item.description && item.description !== "undefined") ? item.description : (canonical ? canonical.name : resolvedCode);
        if (!state.materialInventory.some((material) => material.code === resolvedCode)) {
          state.materialInventory.push({
            code: resolvedCode,
            name: resolvedName,
            lookup_description: resolvedName,
            stock_quantity: 0,
            unit: canonical?.unit || "",
            status: "shortage",
          });
        }
      });
      mergeMaterialInventory(draft.materials || []);
      state.materialInventory.sort((a, b) => (
        `${a.code} ${a.name}`.localeCompare(`${b.code} ${b.name}`)
      ));
      elements.materialRows.replaceChildren();
      (draft.materials || []).forEach((item) => {
        const resolvedCode = resolveMaterialCodeWithEquivalence(item.code, state.materialInventory);
        const canonical = CANONICAL_MATERIAL_MAP[resolvedCode] || CANONICAL_MATERIAL_MAP[item.code];
        const resolvedName = (item.description && item.description !== "undefined") ? item.description : (canonical ? canonical.name : resolvedCode);
        addMaterialRow({ ...item, code: resolvedCode, description: resolvedName });
      });
      state.materialNotice = draft.material_notice || "Preenchimento anterior restaurado";
      refreshMaterialControls();
    });
  }
  const firstInput = elements.equipmentDialog.querySelector(".equipment-row:not(.hidden) input:not(:disabled)");
  if (firstInput) setTimeout(() => firstInput.focus(), 0);
}

function openClosePicker(order) {
  if (state.running || !state.closeEnabled) return;
  state.pendingConfirmation = [order];
  elements.closePickerOrder.textContent = `OS ${order.num_os} - ${order.service}`;
  const quickCodes = state.closeCodes.filter(
    (definition) => !definition.productive && !definition.requiresObservation,
  );
  elements.rowCloseCode.replaceChildren(
    ...quickCodes.map((definition) => new Option(
      `${definition.code} - ${definition.description}`,
      definition.code,
    )),
  );
  elements.rowCloseCode.value = quickCodes.some((item) => item.code === state.closeCode)
    ? state.closeCode : "106";
  elements.closePickerDialog.showModal();
}

function openConfirmation(orders, code = state.closeCode, extra = {}) {
  if (state.running || !state.closeEnabled || orders.length === 0) return;
  const definition = closeDefinition(code);
  if (!definition) return;
  if (definition.requiresObservation && !String(extra.observation || "").trim()) {
    showToast(`O codigo ${definition.code} requer uma observacao`, "error");
    return;
  }
  if (definition.productive) {
    if (orders.length !== 1) {
      showToast("A baixa produtiva deve ser feita uma OS por vez", "error");
      return;
    }
    const service = normalize(orders[0].service);
    const draft = state.productiveDrafts[operationDraftKey(orders[0])];
    const isZeroInventory = (
      isNoEquipmentService(service)
      || (
        expectedEquipmentType(orders[0].service) === ""
        && (!draft || (
          (draft.installed_equipment || []).length === 0
          && (draft.removed_equipment || []).length === 0
          && (draft.materials || []).length === 0
        ))
      )
    );
    if (isZeroInventory && (!draft || (
      (draft.installed_equipment || []).length === 0
      && (draft.removed_equipment || []).length === 0
      && (draft.materials || []).length === 0
    ))) {
      state.pendingConfirmation = orders;
      state.pendingCode = definition.code;
      state.pendingCloseExtra = { ...extra };
      elements.confirmMessage.textContent = extra.retry_of_request_id
        ? `Repetir de forma controlada a OS ${orders[0].num_os}, sem movimentacao de estoque?`
        : `Baixar a OS ${orders[0].num_os} sem movimentacao de estoque?`;
      elements.confirmCode.textContent = definition.code;
      elements.confirmDescription.textContent = definition.description;
      elements.dialog.showModal();
      return;
    }
    openEquipmentDialog(orders[0], definition, extra);
    return;
  }
  state.pendingConfirmation = orders;
  state.pendingCode = definition.code;
  state.pendingCloseExtra = extra;
  elements.confirmMessage.textContent = orders.length === 1
    ? `Baixar a OS ${orders[0].num_os}?`
    : `Baixar ${orders.length} ordens de serviço selecionadas?`;
  elements.confirmCode.textContent = definition.code;
  elements.confirmDescription.textContent = definition.description;
  elements.dialog.showModal();
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function submitClose(order, definition, extra = {}) {
  const operationSource = order.operation_source || (
    order.operation_identity?.activity_id ? "toa_import" : ""
  );
  const identity = order.operation_identity;
  const importScope = order.import_scope;
  const manualScope = order.manual_scope;
  if (operationSource === "toa_import" && !identity?.activity_id) {
    throw new Error("missing_activity_id");
  }
  if (
    operationSource === "toa_import"
    && (!importScope?.source_hash || !order.approved_state_hash)
  ) {
    throw new Error("stale_snapshot");
  }
  if (
    operationSource === "imperium_cache"
    && (!manualScope?.state_hash || !order.approved_state_hash)
  ) {
    throw new Error("stale_snapshot");
  }
  if (!["toa_import", "imperium_cache"].includes(operationSource)) {
    throw new Error("payload_scope_violation");
  }
  const hasMaterials = Array.isArray(extra.materials) && extra.materials.length > 0;
  const hasDataSnap = Boolean(state.authUser?.imperium_identities?.[state.profile]);
  const transport = extra.transport || (
    (state.activeModule === "close" && elements.closeTransport?.value)
    || (state.officialCloseEnabled ? "official_http" : (hasDataSnap ? "datasnap" : "official_http"))
  );
  const maxAttempts = transport === "official_http" ? 1 : 60;
  const toaTechName = String(
    extra.toa_technician?.name
    || order.assigned_technician?.name
    || order.technician_name
    || ""
  ).trim();
  const toaTechLogin = String(
    extra.toa_technician?.login
    || order.assigned_technician?.external_id
    || order.assigned_technician?.login
    || order.technician_login
    || ""
  ).trim().toUpperCase();
  const toaTechId = String(
    extra.toa_technician?.id
    || order.assigned_technician?.id
    || ""
  ).trim();
  const toaTech = (toaTechName || toaTechLogin) ? {
    name: toaTechName,
    login: toaTechLogin,
    id: toaTechId,
  } : undefined;

  for (let busyAttempt = 1; busyAttempt <= maxAttempts; busyAttempt += 1) {
    try {
      return await request(apiUrl(`/api/orders/${order.id_os}/close`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...extra,
          ...(toaTech && !extra.toa_technician ? { toa_technician: toaTech } : {}),
          num_os: order.num_os,
          code: definition.code,
          transport,
          operation_source: operationSource,
          operation_identity: identity,
          approved_state_hash: order.approved_state_hash,
          import_scope: importScope,
          approved_source_hash: importScope?.source_hash,
          manual_scope: manualScope,
        }),
        timeoutMs: hasMaterials ? 480000 : 300000,
      });
    } catch (error) {
      if (error.status !== 409 || busyAttempt === maxAttempts || state.stopped) throw error;
      elements.runDetail.textContent = "Aguardando a operação anterior terminar";
      await sleep(2000);
    }
  }
  return null;
}

function serialFailureContext(message) {
  const text = String(message || "");
  const serial = /O serial\s+([A-Z0-9._/\-]+)/i.exec(text)?.[1]?.toUpperCase() || "";
  const expected = /estoque de\s+(.+?);/i.exec(text)?.[1]?.trim() || "";
  return { serial, expected };
}

function renderSerialOwnerLookup() {
  const lookup = state.serialOwnerLookup;
  if (!lookup) return;
  const payload = lookup.payload;
  elements.serialOwnerSerial.textContent = lookup.serial;
  elements.serialOwnerLoading.classList.toggle("hidden", !lookup.loading);
  elements.serialOwnerResult.classList.toggle("hidden", !payload?.found);
  elements.serialOwnerError.classList.toggle("hidden", !lookup.error && payload?.found !== false);
  elements.serialOwnerViewStock.classList.toggle("hidden", !payload?.owner);
  elements.serialOwnerViewStock.disabled = lookup.loading;
  elements.serialOwnerTransfer.disabled = lookup.loading || !payload?.found
    || !lookup.order || !state.serializedTransferEnabled;
  elements.serialOwnerTransfer.title = state.serializedTransferEnabled
    ? "Preparar a transferencia deste serial para o instalador atual da OS"
    : "Transferencia de equipamento validada somente em Natal";
  elements.serialOwnerMoveOrder.disabled = lookup.loading || !payload?.found
    || !state.installerChangeEnabled;
  if (payload?.found) {
    const owner = payload.owner;
    elements.serialOwnerCurrent.textContent = stockTechnicianLabel(owner);
    elements.serialOwnerExpected.textContent = lookup.expected || "Tecnico responsavel pela OS";
    elements.serialOwnerEquipment.textContent = payload.equipment?.name || "Equipamento serializado";
    elements.serialOwnerCode.textContent = payload.equipment?.code || String(payload.stock_serial?.equipment_id || "-");
    elements.serialOwnerScan.textContent = `${payload.scanned} de ${payload.total_stocks} estoques em ${payload.elapsed_seconds}s${payload.cached ? " (cache)" : ""}`;
    elements.serialOwnerWarning.textContent = lookup.expected
      ? `Divergencia de rota: o estoque esta em ${owner.technician_name}, mas a OS aponta ${lookup.expected}. Se a desconexao foi importada antes das movimentacoes de 07:40-08:40, atualize ou reimporte a OS apos 09:00; nao transfira o equipamento por causa desse erro.`
      : "Confira se a OS foi importada antes da movimentacao de rota. Se o tecnico atual for o executor correto, atualize a OS em vez de transferir o estoque.";
    elements.serialOwnerViewStock.querySelector("span").textContent = `Ver estoque de ${owner.technician_name}`;
    elements.serialOwnerTransfer.querySelector("span").textContent = lookup.expected
      ? `Transferir equipamento para ${lookup.expected}`
      : "Transferir equipamento para o tecnico da OS";
    elements.serialOwnerMoveOrder.querySelector("span").textContent =
      `Mover OS para ${owner.technician_name}`;
    elements.serialOwnerMoveOrder.title = state.installerChangeEnabled
      ? `Alterar somente as OS do contrato ${lookup.order?.contract || "selecionado"}`
      : "Alteracao de instalador validada somente em Natal";
  }
  if (lookup.error) {
    elements.serialOwnerError.textContent = lookup.error;
  } else if (payload?.found === false) {
    elements.serialOwnerError.textContent = `O serial nao apareceu em nenhum dos ${payload.total_stocks} estoques consultados.`;
  }
}

async function openSerialOwnerLookup(error, order) {
  const context = serialFailureContext(error?.message);
  if (!context.serial) return;
  state.serialOwnerLookup = {
    ...context,
    order,
    loading: true,
    payload: null,
    error: "",
  };
  renderSerialOwnerLookup();
  if (!elements.serialOwnerDialog.open) elements.serialOwnerDialog.showModal();
  try {
    const payload = await request(
      apiUrl(`/api/stock/serial-owner?serial=${encodeURIComponent(context.serial)}`),
      { timeoutMs: 180000 },
    );
    state.serialOwnerLookup = {
      ...state.serialOwnerLookup,
      loading: false,
      payload,
    };
  } catch (lookupError) {
    state.serialOwnerLookup = {
      ...state.serialOwnerLookup,
      loading: false,
      error: lookupError.message,
    };
    console.error("Falha ao localizar proprietario do serial", lookupError);
  }
  renderSerialOwnerLookup();
}

function renderInstallerMovePreview() {
  const preview = state.installerMovePreview;
  if (!preview) return;
  elements.installerMoveMessage.textContent =
    `Mover as OS do contrato ${preview.contract} para ${preview.installer_name}?`;
  elements.installerMoveContract.textContent = preview.contract;
  elements.installerMoveTarget.textContent = preview.installer_name;
  elements.installerMoveCount.textContent = preview.count;
  elements.installerMoveOrders.innerHTML = preview.orders.map((order) => `
    <div class="installer-move-order">
      <strong>OS ${escapeHtml(order.num_os)}</strong>
      <span>${escapeHtml(order.service)}</span>
      <code>IdOS ${escapeHtml(order.id_os)}</code>
    </div>
  `).join("");
  elements.installerMoveError.classList.toggle("hidden", !state.installerMoveError);
  elements.installerMoveError.textContent = state.installerMoveError;
  elements.installerMoveConfirm.disabled = state.installerMoveLoading;
  elements.installerMoveCancel.disabled = state.installerMoveLoading;
  elements.installerMoveConfirm.querySelector("span").textContent = state.installerMoveLoading
    ? "Movendo..." : `Sim, mover ${preview.count} OS`;
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function openInstallerMovePreview() {
  const lookup = state.serialOwnerLookup;
  if (!lookup?.payload?.found || !lookup.order || !state.installerChangeEnabled) return;
  elements.serialOwnerMoveOrder.disabled = true;
  elements.serialOwnerMoveOrder.querySelector("span").textContent = "Preparando previa...";
  try {
    const preview = await request(apiUrl(
      `/api/orders/${lookup.order.id_os}/installer-change-preview?serial=${encodeURIComponent(lookup.serial)}`,
    ), { timeoutMs: 180000 });
    state.installerMovePreview = preview;
    state.installerMoveLoading = false;
    state.installerMoveError = "";
    elements.serialOwnerDialog.close();
    renderInstallerMovePreview();
    elements.installerMoveDialog.showModal();
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao preparar alteracao de instalador", error);
    renderSerialOwnerLookup();
  }
}

async function confirmInstallerMove() {
  const preview = state.installerMovePreview;
  if (!preview || state.installerMoveLoading) return;
  state.installerMoveLoading = true;
  renderInstallerMovePreview();
  try {
    const result = await request(apiUrl(
      `/api/orders/${preview.orders[0].id_os}/move-installer`,
    ), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirmed: true,
        serial: preview.serial,
        preview_token: preview.preview_token,
      }),
      timeoutMs: Math.max(90000, preview.count * 60000),
    });
    const changedIds = new Set(result.orders.map((order) => Number(order.id_os)));
    state.orders = state.orders.map((order) => changedIds.has(Number(order.id_os))
      ? { ...order, technician: result.installer_name }
      : order);
    showToast(
      `${result.count} OS do contrato ${result.contract} movidas para ${result.installer_name}.`,
      "success",
    );
    elements.installerMoveDialog.close();
    render();
  } catch (error) {
    state.installerMoveError = error.message;
    showToast(error.message, "error");
    console.error("Falha ao alterar instalador", error);
  } finally {
    state.installerMoveLoading = false;
    renderInstallerMovePreview();
  }
}

function renderSerializedTransferPreview() {
  const preview = state.serializedTransferPreview;
  if (!preview) return;
  elements.serializedTransferMessage.textContent =
    `Transferir somente o serial ${preview.serial} para o instalador atual da OS ${preview.order.num_os}?`;
  elements.serializedTransferSerial.textContent = preview.serial;
  elements.serializedTransferSource.textContent = stockTechnicianLabel(preview.source);
  elements.serializedTransferTarget.textContent = stockTechnicianLabel(preview.target);
  elements.serializedTransferEquipment.textContent = preview.equipment.name;
  elements.serializedTransferCode.textContent = preview.equipment.code;
  elements.serializedTransferError.classList.toggle("hidden", !state.serializedTransferError);
  elements.serializedTransferError.textContent = state.serializedTransferError;
  elements.serializedTransferConfirm.disabled = state.serializedTransferLoading;
  elements.serializedTransferCancel.disabled = state.serializedTransferLoading;
  elements.serializedTransferConfirm.querySelector("span").textContent =
    state.serializedTransferLoading ? "Transferindo e confirmando..." : "Sim, transferir equipamento";
  if (globalThis.lucide) globalThis.lucide.createIcons();
}

async function openSerializedTransferPreview() {
  const lookup = state.serialOwnerLookup;
  if (!lookup?.payload?.found || !lookup.order || !state.serializedTransferEnabled) return;
  elements.serialOwnerTransfer.disabled = true;
  elements.serialOwnerTransfer.querySelector("span").textContent = "Preparando previa...";
  try {
    const preview = await request(apiUrl(
      `/api/orders/${lookup.order.id_os}/serialized-transfer-preview?serial=${encodeURIComponent(lookup.serial)}`,
    ), { timeoutMs: 240000 });
    state.serializedTransferPreview = preview;
    state.serializedTransferLoading = false;
    state.serializedTransferError = "";
    elements.serialOwnerDialog.close();
    renderSerializedTransferPreview();
    elements.serializedTransferDialog.showModal();
  } catch (error) {
    showToast(error.message, "error");
    console.error("Falha ao preparar transferencia do equipamento", error);
    renderSerialOwnerLookup();
  }
}

async function confirmSerializedTransfer() {
  const preview = state.serializedTransferPreview;
  if (!preview || state.serializedTransferLoading) return;
  state.serializedTransferLoading = true;
  state.serializedTransferError = "";
  renderSerializedTransferPreview();
  try {
    const result = await request(apiUrl(
      `/api/orders/${preview.id_os}/transfer-serial`,
    ), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirmed: true,
        preview_token: preview.preview_token,
      }),
      timeoutMs: 300000,
    });
    showToast(
      `Serial ${result.serial} transferido para ${result.target.technician_name}. A OS pode ser baixada novamente.`,
      "success",
    );
    elements.serializedTransferDialog.close();
  } catch (error) {
    state.serializedTransferError = error.message;
    showToast(error.message, "error");
    console.error("Falha ao transferir equipamento", error);
  } finally {
    state.serializedTransferLoading = false;
    renderSerializedTransferPreview();
  }
}

async function processOrders(orders, closeCode, equipment = null) {
  const definition = closeDefinition(closeCode);
  state.running = true;
  state.paused = false;
  state.stopped = false;
  elements.runbar.classList.remove("hidden");
  elements.pause.textContent = "Pausar";
  let processed = 0;
  let failed = 0;
  let pending = 0;
  let consecutiveFailures = 0;
  render();

  for (const order of orders) {
    while (state.paused && !state.stopped) await sleep(120);
    if (state.stopped) break;
    elements.runTitle.textContent = `Baixando OS ${order.num_os}`;
    elements.runDetail.textContent = `${processed + 1} de ${orders.length}`;
    elements.progress.style.width = `${Math.round((processed / orders.length) * 100)}%`;
    try {
      const result = await submitClose(order, definition, equipment || {});
      if (result?.pending_confirmation) {
        pending += 1;
        state.selected.delete(order.id_os);
        consecutiveFailures = 0;
        showToast(`OS ${order.num_os}: ${result.message}`, "warning");
        await loadCloseReport({ quiet: true });
      } else {
        if (equipment?.toa_paste_key && equipment.materials?.length) {
          const assignments = materialPasteAssignments();
          assignments.values[equipment.toa_paste_key] = order.num_os;
          sessionStorage.setItem(assignments.key, JSON.stringify(assignments.values));
        }
        state.orders = state.orders.filter((item) => item.id_os !== order.id_os);
        delete state.productiveDrafts[operationDraftKey(order)];
        state.selected.delete(order.id_os);
        state.failures = state.failures.filter((failure) => failure.id_os !== order.id_os);
        state.completed += 1;
        consecutiveFailures = 0;
      }
    } catch (error) {
      failed += 1;
      consecutiveFailures += 1;
      upsertFailure(order, error, definition.code);
      showToast(`OS ${order.num_os}: ${error.message}`, "error");
      if (equipment && definition.productive) {
        const draft = state.productiveDrafts[operationDraftKey(order)];
        if (draft) draft.last_error = error.message;
      }
      if (serialFailureContext(error.message).serial) {
        openSerialOwnerLookup(error, order);
      }
      const normalizedError = normalize(error.message);
      const connectionFailure = normalizedError.includes("NAO FOI POSSIVEL CONECTAR")
        || normalizedError.includes("WINERROR 10060")
        || normalizedError.includes("GETADDRINFO");
      if (error.uncertain || connectionFailure || consecutiveFailures >= 5) {
        state.stopped = true;
      }
    }
    processed += 1;
    elements.progress.style.width = `${Math.round((processed / orders.length) * 100)}%`;
    render();
    await sleep(1000);
  }

  state.running = false;
  state.paused = false;
  elements.pause.textContent = "Pausar";
  await loadOrders({ preserveSelection: true });
  render();
  const successful = processed - failed - pending;
  if (state.stopped && failed) {
    elements.runTitle.textContent = "Lote interrompido";
    elements.runDetail.textContent = `${successful} concluídas; ${failed} falharam`;
  } else if (state.stopped) {
    elements.runTitle.textContent = "Lote interrompido";
    elements.runDetail.textContent = `${processed} de ${orders.length} processadas`;
  } else if (failed) {
    elements.runTitle.textContent = "Lote concluído com falhas";
    elements.runDetail.textContent = `${successful} concluídas; ${pending} aguardando; ${failed} continuam selecionadas`;
    showToast(`${failed} OS falharam e continuam selecionadas.`, "error");
  } else if (pending) {
    elements.runTitle.textContent = "Aguardando confirmacao";
    elements.runDetail.textContent = `${pending} OS recebidas; acompanhe o resultado no Relatorio`;
    showToast(`${pending} OS aguardando confirmacao do Imperium.`, "warning");
  } else {
    elements.runTitle.textContent = "Lote concluído";
    elements.runDetail.textContent = `${processed} ordens baixadas com código ${definition.code}`;
    showToast(`${processed} ordens baixadas com sucesso.`, "success");
  }
}

elements.date.value = localDate();
elements.date.min = elements.date.value;
elements.date.max = elements.date.value;
elements.reportDate.value = localDate();
elements.databaseDate.value = "";
elements.intelligenceDate.value = localDate();
elements.intelligenceDate.max = localDate();
elements.bulkCreateDate.value = localDate();
elements.refresh.addEventListener("click", () => loadOrders());
elements.sidebarToggle.addEventListener("click", toggleSidebar);
elements.dashboardModule.addEventListener("click", () => setModule("dashboard"));
elements.monitorModule?.addEventListener("click", () => setModule("monitor"));
elements.ordersModule.addEventListener("click", () => setModule("orders"));
elements.stockModule.addEventListener("click", () => setModule("stock"));
elements.techniciansModule.addEventListener("click", () => setModule("technicians"));
elements.intelligenceModule.addEventListener("click", () => setModule("intelligence"));
elements.bulkCreateModule.addEventListener("click", () => setModule("bulk"));
elements.importsModule.addEventListener("click", () => setModule("imports"));
elements.automationTestModule.addEventListener("click", () => setModule("automation-test"));
elements.closeModule.addEventListener("click", () => setModule("close"));
elements.reportModule.addEventListener("click", () => setModule("report"));
elements.databaseModule.addEventListener("click", () => setModule("database"));
elements.historyModule.addEventListener("click", () => setModule("history"));
let databaseSearchTimer;
elements.databaseSearch.addEventListener("input", () => {
  clearTimeout(databaseSearchTimer);
  databaseSearchTimer = setTimeout(() => loadOperationalDatabase({ quiet: true }), 250);
});
elements.databaseDate.addEventListener("change", () => loadOperationalDatabase());
elements.databaseRefresh.addEventListener("click", () => loadOperationalDatabase());
elements.intelligenceRefresh.addEventListener("click", () => loadIntelligence());
elements.intelligenceDays.addEventListener("change", () => loadIntelligence());
elements.intelligenceDate.addEventListener("change", () => {
  state.serialAudit = null;
  renderSerialAudit();
  loadIntelligence();
});
elements.intelligenceTechnicianSearch.addEventListener("input", renderIntelligence);
elements.healthRefresh.addEventListener("click", () => loadHealthCheck({ fresh: true }));
elements.serialAuditRun.addEventListener("click", runSerialAudit);
elements.intelligencePdf.addEventListener("click", () => {
  const url = new URL("/api/intelligence/report.pdf", window.location.origin);
  url.searchParams.set("date", elements.intelligenceDate.value || localDate());
  window.location.assign(`${url.pathname}${url.search}`);
  showToast("Gerando relatorio diario consolidado...", "success");
});
elements.monitorSearch.addEventListener("input", renderOperationsMonitor);
elements.monitorBucket.addEventListener("change", renderOperationsMonitor);
elements.monitorStatus.addEventListener("change", renderOperationsMonitor);
elements.monitorDemo.addEventListener("click", () => {
  state.monitorDemoMode = !state.monitorDemoMode;
  state.monitorView = "monitor";
  elements.monitorSearch.value = "";
  elements.monitorBucket.value = "all";
  elements.monitorStatus.value = "all";
  renderOperationsMonitor();
  showToast(state.monitorDemoMode
    ? "Cenarios de exemplo ativados. Nenhuma OS real sera alterada."
    : "Dados reais restaurados.");
});
elements.monitorTvOpen.addEventListener("click", enterMonitorTv);
elements.monitorNotify.addEventListener("click", toggleMonitorNotifications);
elements.monitorVoice.addEventListener("click", toggleMonitorVoiceAlerts);
elements.monitorExport.addEventListener("click", exportOperationsMonitor);
elements.monitorCsvOpen.addEventListener("click", () => elements.monitorCsvInput.click());
elements.monitorCsvReplace.addEventListener("click", () => elements.monitorCsvInput.click());
elements.monitorCsvInput.addEventListener("change", () => {
  const files = elements.monitorCsvInput.files || [];
  if (files.length) void importMonitorCsv(files);
});
elements.monitorCsvClear.addEventListener("click", clearMonitorCsvSnapshot);
elements.monitorRefresh.addEventListener("click", async () => {
  if (state.monitorCsvSnapshot) {
    elements.monitorCsvInput.click();
    return;
  }
  elements.monitorRefresh.disabled = true;
  try {
    const refreshed = await loadOrders({ preserveSelection: true, quiet: true });
    if (refreshed) showToast("Monitor atualizado.", "success");
  } finally {
    elements.monitorRefresh.disabled = false;
  }
});
elements.termsOpen.addEventListener("click", openTermsDialog);
elements.termsClose.addEventListener("click", closeTermsDialog);
elements.termsDismiss.addEventListener("click", closeTermsDialog);
elements.termsAccept.addEventListener("click", acceptTerms);
elements.reportRefresh.addEventListener("click", () => loadCloseReport());
if (elements.reportExportXlsx) elements.reportExportXlsx.addEventListener("click", exportCloseReportXlsx);
elements.reportDate.addEventListener("change", () => loadCloseReport());
elements.reportSearch.addEventListener("input", renderCloseReport);
elements.reportState.addEventListener("change", renderCloseReport);
elements.refreshServerLog.addEventListener("click", () => loadServerLogs());
if (elements.historyImportAuditRefresh) elements.historyImportAuditRefresh.addEventListener("click", () => loadImportAuditHistory());
if (elements.historyImportAuditDate) elements.historyImportAuditDate.addEventListener("change", () => {
  state.importAuditLoaded = false;
  state.importAuditHistory = [];
  loadImportAuditHistory();
});
elements.dashboardOpenOrders.addEventListener("click", () => setModule("orders"));
elements.stockTechnicianSearch.addEventListener("input", renderStock);
elements.stockSource.addEventListener("change", () => {
  const requested = elements.stockSource.value === "official" ? "official" : "datasnap";
  if (requested === "official" && !["natal", "fortaleza"].includes(state.profile)) {
    elements.stockSource.value = "datasnap";
    showToast("A API oficial ainda nao esta configurada para esta base.", "error");
    return;
  }
  state.stockSource = requested;
  state.stockTechnicians = [];
  state.stockSelectedId = "";
  state.stockData = null;
  state.stockWriteoffBasket.clear();
  state.pendingStockWriteoff = null;
  state.stockWriteoffRequestId = null;
  state.stockBatchSelected.clear();
  elements.stockTechnicianSearch.value = "";
  elements.stockItemSearch.value = "";
  elements.stockGroupFilter.replaceChildren(new Option("Todos", ""));
  renderStock();
  loadStockTechnicians();
});
elements.stockTechnicianSelect.addEventListener("change", () => {
  state.stockSelectedId = elements.stockTechnicianSelect.value;
  state.stockData = null;
  state.stockWriteoffBasket.clear();
  state.pendingStockWriteoff = null;
  state.stockWriteoffRequestId = null;
  elements.stockItemSearch.value = "";
  elements.stockGroupFilter.replaceChildren(new Option("Todos", ""));
  renderStock();
});
elements.stockConsult.addEventListener("click", loadTechnicianStock);
elements.stockWriteoffOpen.addEventListener("click", openStockWriteoffDialog);
elements.stockWriteoffForm.addEventListener("submit", submitStockWriteoff);
elements.stockWriteoffCancel.addEventListener("click", () => {
  if (!state.stockWriteoffLoading) elements.stockWriteoffDialog.close();
});
elements.stockWriteoffDialog.addEventListener("cancel", (event) => {
  if (state.stockWriteoffLoading) event.preventDefault();
});
elements.stockWriteoffDialog.addEventListener("close", () => {
  if (!state.stockWriteoffLoading) {
    state.pendingStockWriteoff = null;
    state.stockWriteoffRequestId = null;
  }
});
elements.stockPdf.addEventListener("click", () => {
  const stockId = Number(state.stockSelectedId);
  if (stockId) generateStockPdf([stockId], { individual: true });
});
elements.stockBatch.addEventListener("click", openStockBatchDialog);
elements.stockBatchSearch.addEventListener("input", renderStockBatchDialog);
elements.stockBatchSelectVisible.addEventListener("click", () => {
  const visible = filteredStockBatchTechnicians();
  const combined = new Set(state.stockBatchSelected);
  visible.forEach((technician) => combined.add(String(technician.stock_id)));
  if (combined.size > 150) {
    showToast("O lote permite no maximo 150 tecnicos.", "error");
    return;
  }
  state.stockBatchSelected = combined;
  renderStockBatchDialog();
});
elements.stockBatchClear.addEventListener("click", () => {
  state.stockBatchSelected.clear();
  renderStockBatchDialog();
});
elements.stockBatchPdf.addEventListener(
  "click",
  () => generateStockPdf(selectedStockIds()),
);
elements.stockBatchPrint.addEventListener("click", printSelectedStocks);
elements.stockShowZero.addEventListener("change", renderStock);
elements.stockItemSearch.addEventListener("input", renderStock);
elements.stockGroupFilter.addEventListener("change", renderStock);
elements.technicianSearch.addEventListener("input", renderTechnicians);
elements.technicianTeamFilter.addEventListener("change", renderTechnicians);
elements.bulkTechnicianSearch.addEventListener("input", renderBulkCreate);
elements.bulkTechnicianSelect.addEventListener("change", () => {
  if (!state.bulkCreateResult?.uncertain) {
    state.bulkCreateResult = null;
    state.bulkCreateRequestId = null;
  }
  renderBulkCreate();
});
elements.bulkService.addEventListener("change", () => {
  if (!state.bulkCreateResult?.uncertain) {
    state.bulkCreateResult = null;
    state.bulkCreateRequestId = null;
  }
  renderBulkCreate();
});
elements.bulkContracts.addEventListener("input", () => {
  if (!state.bulkCreateResult?.uncertain) {
    state.bulkCreateResult = null;
    state.bulkCreateRequestId = null;
  }
  renderBulkCreate();
});
elements.bulkCloseCode.addEventListener("change", () => {
  if (!state.bulkCreateResult?.uncertain) {
    state.bulkCreateResult = null;
    state.bulkCreateRequestId = null;
  }
  renderBulkCreate();
});
elements.bulkCreateReview.addEventListener("click", openBulkCreateDialog);
elements.bulkCreateDialog.addEventListener("close", () => {
  if (elements.bulkCreateDialog.returnValue === "confirm") createBulkOrders();
});
elements.manualTechnicianSearch.addEventListener("input", renderManualCreate);
elements.manualTechnicianSelect.addEventListener("change", renderManualCreate);
elements.manualService.addEventListener("change", renderManualCreate);
elements.manualCloseCode.addEventListener("change", renderManualCreate);
elements.manualContract.addEventListener("input", () => {
  elements.manualContract.value = elements.manualContract.value.replace(/\D/g, "").slice(0, 7);
  renderManualCreate();
});
elements.manualCreateReview.addEventListener("click", openManualCreateDialog);
elements.chooseImportFile.addEventListener("click", () => elements.importFile.click());
elements.importFile.addEventListener("change", () => {
  const file = elements.importFile.files?.[0] || null;
  if (file) assignImportFile(file);
  else renderImportPreview();
});
elements.importDropzone.addEventListener("click", (event) => {
  if (!event.target.closest("button")) elements.importFile.click();
});
elements.importDropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    elements.importFile.click();
  }
});
["dragenter", "dragover"].forEach((name) => elements.importDropzone.addEventListener(name, (event) => {
  event.preventDefault();
  elements.importDropzone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => elements.importDropzone.addEventListener(name, (event) => {
  event.preventDefault();
  elements.importDropzone.classList.remove("dragging");
}));
elements.importDropzone.addEventListener("drop", (event) => assignImportFile(event.dataTransfer?.files?.[0]));
elements.importSelectAll?.addEventListener("change", () => {
  const checked = elements.importSelectAll.checked;
  if (checked) {
    state.selectedImportOs = new Set((state.importPreview?.orders || []).map((o) => String(o.os_number)));
  } else {
    state.selectedImportOs = new Set();
  }
  renderImportPreview();
});
elements.commitImport.addEventListener("click", commitImportFile);
elements.toaAutomationRun.addEventListener("click", runToaAutomation);
elements.automationTestLot.addEventListener("change", () => {
  state.automationTestLotKey = elements.automationTestLot.value;
  state.automationTestResult = null;
  renderAutomationTest();
});
elements.automationTestContracts.addEventListener("input", renderAutomationTest);
elements.automationTestAnalyze.addEventListener("click", analyzeAutomationTest);
elements.automationWindowButtons.forEach((button) => button.addEventListener("click", () => {
  const slot = button.dataset.automationSlot;
  const records = state.automationTestRegistry?.records || [];
  const contracts = [...new Set(
    records
      .filter((record) => (record.review_slots || []).includes(slot))
      .map((record) => String(record.contract || "").trim())
      .filter(Boolean),
  )];
  elements.automationTestContracts.value = contracts.join("\n");
  state.automationTestResult = null;
  state.automationTestMessage = `${contracts.length} contratos carregados da janela ${slot}.`;
  renderAutomationTest();
}));
elements.closeQueueSearch.addEventListener("input", renderCloseWorkspace);
elements.closeWorkspaceCode.addEventListener("input", () => {
  elements.closeWorkspaceCode.value = elements.closeWorkspaceCode.value.replace(/\D/g, "").slice(0, 4);
  renderCloseWorkspace();
});
elements.closeWorkspaceObservation.addEventListener("input", renderCloseWorkspace);
elements.toaLiveContract.addEventListener("input", () => {
  elements.toaLiveContract.value = elements.toaLiveContract.value.replace(/\D/g, "").slice(0, 18);
  renderToaLiveStatus();
});
elements.toaLiveContract.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !elements.toaLiveLookup.disabled) {
    event.preventDefault();
    lookupToaLiveContract();
  }
});
elements.toaLiveLookup.addEventListener("click", lookupToaLiveContract);
elements.semiAutoAgendaChoose.addEventListener("click", () => {
  if (!state.semiAutoAgendaLoading) elements.semiAutoAgendaFile.click();
});
elements.semiAutoAgendaFile.addEventListener("change", () => {
  void importSemiAutoAgenda(elements.semiAutoAgendaFile.files?.[0]);
});
elements.semiAutoStart.addEventListener("click", () => {
  state.autoCloseMode = false;
  startSemiAutoQueue();
});
if (elements.autoCloseStart) {
  elements.autoCloseStart.addEventListener("click", startAutoCloseQueue);
}
elements.semiAutoPause.addEventListener("click", toggleSemiAutoPause);
elements.semiAutoStop.addEventListener("click", stopSemiAutoQueue);
elements.semiAutoContractDialog.addEventListener("close", () => {
  state.semiAutoReviewJobIndex = -1;
});
if (elements.semiAutoSkippedCard) {
  elements.semiAutoSkippedCard.addEventListener("click", openSemiAutoSkippedDialog);
  elements.semiAutoSkippedCard.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSemiAutoSkippedDialog();
    }
  });
}
if (elements.semiAutoSkipped) {
  elements.semiAutoSkipped.addEventListener("click", (event) => {
    event.stopPropagation();
    openSemiAutoSkippedDialog();
  });
}
if (elements.semiAutoSkippedClose) {
  elements.semiAutoSkippedClose.addEventListener("click", () => {
    if (elements.semiAutoSkippedDialog?.open) elements.semiAutoSkippedDialog.close();
  });
}
if (elements.semiAutoSkippedBottomClose) {
  elements.semiAutoSkippedBottomClose.addEventListener("click", () => {
    if (elements.semiAutoSkippedDialog?.open) elements.semiAutoSkippedDialog.close();
  });
}
if (elements.semiAutoSkippedSearch) {
  elements.semiAutoSkippedSearch.addEventListener("input", () => renderSemiAutoSkippedDialog());
}
if (elements.semiAutoSkippedFilters) {
  elements.semiAutoSkippedFilters.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.semiAutoSkippedFilter = chip.dataset.filter || "all";
      renderSemiAutoSkippedDialog();
    });
  });
}
if (elements.semiAutoSkippedCopyBtn) {
  elements.semiAutoSkippedCopyBtn.addEventListener("click", () => {
    const allSkipped = (state.semiAutoJobs || []).filter((job) =>
      ["skipped", "error"].includes(job.state)
    );
    const filterCategory = state.semiAutoSkippedFilter || "all";
    const query = (elements.semiAutoSkippedSearch?.value || "").trim().toLowerCase();
    let filtered = allSkipped.filter((job) => {
      if (filterCategory === "imperium_no_os") {
        return ["imperium_no_os", "imperium_closed"].includes(job.skipCategory);
      }
      if (filterCategory === "toa_pending") {
        return job.skipCategory === "toa_pending";
      }
      if (filterCategory === "toa_not_found") {
        return job.skipCategory === "toa_not_found";
      }
      if (filterCategory === "other") {
        return !["imperium_no_os", "imperium_closed", "toa_pending", "toa_not_found"].includes(job.skipCategory);
      }
      return true;
    });
    if (query) {
      filtered = filtered.filter((job) => {
        const matchContract = String(job.contract || "").toLowerCase().includes(query);
        const matchWindow = String(job.windowLabel || "").toLowerCase().includes(query);
        const matchOs = (job.osNumbers || []).some((os) => String(os).toLowerCase().includes(query));
        const matchDetail = String(job.skipDetail || job.message || "").toLowerCase().includes(query);
        const matchTitle = String(job.skipTitle || "").toLowerCase().includes(query);
        return matchContract || matchWindow || matchOs || matchDetail || matchTitle;
      });
    }
    const contracts = filtered.map((j) => j.contract).filter(Boolean);
    if (!contracts.length) {
      showToast("Nenhum contrato para copiar.", "info");
      return;
    }
    const text = contracts.join("\n");
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(`${contracts.length} contratos copiados para a área de transferência!`, "success");
      }).catch(() => {
        showToast(`${contracts.length} contratos: ${contracts.join(", ")}`);
      });
    }
  });
}
elements.toaLiveOpen.addEventListener("click", openToaLoginDialog);
elements.headerToaOpen.addEventListener("click", openToaLoginDialog);
elements.toaLoginForm.addEventListener("submit", connectToaLive);
elements.toaLoginClose.addEventListener("click", closeToaLoginDialog);
elements.toaLoginCancel.addEventListener("click", closeToaLoginDialog);
elements.toaLoginDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeToaLoginDialog();
});
elements.disconnectPrepare.addEventListener("click", prepareDisconnectAutomation);
elements.disconnectStart.addEventListener(
  "click",
  () => controlDisconnectAutomation("start"),
);
elements.disconnectPause.addEventListener(
  "click",
  () => controlDisconnectAutomation("pause"),
);
elements.disconnectResume.addEventListener(
  "click",
  () => controlDisconnectAutomation("resume"),
);
elements.disconnectStop.addEventListener(
  "click",
  () => controlDisconnectAutomation("stop"),
);
elements.closeWorkspaceCode.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !elements.closeWorkspaceContinue.disabled) {
    event.preventDefault();
    elements.closeWorkspaceContinue.click();
  }
});
elements.closeWorkspaceContinue.addEventListener("click", () => {
  const order = selectedCloseWorkspaceOrder();
  const definition = closeWorkspaceDefinition();
  const retryReport = order ? retryableCloseReportRecord(order.id_os) : null;
  if (order && definition) openConfirmation([order], definition.code, {
    ...closeRetryExtra(retryReport),
    observation: elements.closeWorkspaceObservation.value.trim(),
  });
});
elements.closeOpenOrders.addEventListener("click", () => setModule("orders"));
elements.ordersTab.addEventListener("click", () => {
  state.activeView = "orders";
  updateAddress();
  render();
});
elements.failuresTab.addEventListener("click", () => {
  state.activeView = "failures";
  updateAddress();
  render();
});
elements.date.addEventListener("change", async () => {
  await loadOrders();
  await loadSemiAutoAgenda({ quiet: true });
});
elements.search.addEventListener("input", render);
elements.status.addEventListener("change", () => loadOrders());
elements.service.addEventListener("change", () => loadOrders());
elements.codeOptions.forEach((button) => {
  button.addEventListener("click", () => {
    if (state.running || state.loading || !state.closeEnabled) return;
    const code = button.dataset.closeCode;
    if (state.closeCodes.some((item) => item.code === code)) {
      state.closeCode = code;
      if (productiveClose(code)) state.selected.clear();
      render();
    }
  });
});
elements.selectAll.addEventListener("change", () => {
  if (!state.closeEnabled || productiveClose()) return;
  visibleOrders().filter(
    (order) => !order.read_only && normalize(order.status) === "EM CAMPO",
  ).forEach((order) => {
    if (elements.selectAll.checked) state.selected.add(order.id_os);
    else state.selected.delete(order.id_os);
  });
  render();
});
elements.batch.addEventListener("click", () => {
  if (productiveClose()) return;
  const orders = state.orders.filter((order) => state.selected.has(order.id_os));
  openConfirmation(orders);
});
elements.closePickerDialog.addEventListener("close", () => {
  const order = state.pendingConfirmation[0];
  state.pendingConfirmation = [];
  if (elements.closePickerDialog.returnValue === "confirm" && order) {
    openConfirmation([order], elements.rowCloseCode.value);
  }
});
elements.dialog.addEventListener("close", () => {
  if (elements.dialog.returnValue === "confirm") {
    const orders = state.pendingConfirmation;
    const closeCode = state.pendingCode;
    const extra = state.pendingCloseExtra;
    state.pendingConfirmation = [];
    state.pendingCloseExtra = {};
    processOrders(orders, closeCode, extra);
  } else {
    state.pendingConfirmation = [];
    state.pendingCloseExtra = {};
  }
});
elements.serialOwnerViewStock.addEventListener("click", async () => {
  const owner = state.serialOwnerLookup?.payload?.owner;
  if (!owner) return;
  elements.serialOwnerDialog.close();
  setModule("stock");
  if (!state.stockTechnicians.length) await loadStockTechnicians();
  state.stockSelectedId = String(owner.stock_id);
  state.stockData = null;
  elements.stockTechnicianSearch.value = "";
  renderStock();
  await loadTechnicianStock();
});
elements.serialOwnerMoveOrder.addEventListener("click", openInstallerMovePreview);
elements.serialOwnerTransfer.addEventListener("click", openSerializedTransferPreview);
elements.serialOwnerDialog.addEventListener("close", () => {
  state.serialOwnerLookup = null;
});
elements.installerMoveConfirm.addEventListener("click", confirmInstallerMove);
elements.installerMoveDialog.addEventListener("close", () => {
  if (!state.installerMoveLoading) {
    state.installerMovePreview = null;
    state.installerMoveError = "";
  }
});
elements.serializedTransferConfirm.addEventListener("click", confirmSerializedTransfer);
elements.serializedTransferDialog.addEventListener("close", () => {
  if (!state.serializedTransferLoading) {
    state.serializedTransferPreview = null;
    state.serializedTransferError = "";
  }
});
elements.movement.addEventListener("change", updateEquipmentFields);
elements.addInstalled.addEventListener("click", () => {
  addEquipmentRow("installed").querySelector("input").focus();
});
elements.addRemoved.addEventListener("click", () => {
  addEquipmentRow("removed").querySelector("input").focus();
});
elements.addMaterial.addEventListener("click", () => {
  addMaterialRow().querySelector("select").focus();
});
elements.processMaterialPaste.addEventListener("click", processMaterialPaste);
elements.materialEquivalenceConfirm.addEventListener("change", () => {
  state.materialEquivalenceConfirmed = elements.materialEquivalenceConfirm.checked;
  refreshMaterialControls();
});
elements.equipmentDialog.addEventListener("close", () => {
  const pending = state.pendingProductive;
  state.pendingProductive = null;
  if (elements.equipmentDialog.returnValue !== "confirm" || !pending) return;
  const movement = elements.movement.value;
  const draftKey = operationDraftKey(pending.order);
  const previousDraft = state.productiveDrafts[draftKey];
  const equipment = {
    ...(pending.extra || {}),
    installed_equipment: movement === "install" || movement === "swap"
      ? equipmentValues("installed")
      : [],
    removed_equipment: movement === "remove" || movement === "swap"
      ? equipmentValues("removed")
      : [],
    materials: closeCodeAllowsMaterials(pending.code) && (movement === "install" || movement === "swap")
      ? materialValues()
      : [],
    toa_paste_key: state.currentMaterialPasteKey,
    // Preserve TOA live capture metadata so the backend receives the original
    // scheduled_date (dataagendamento) even after the user edits the equipment list.
    scheduled_date: previousDraft?.scheduled_date || "",
    live_capture_aid: previousDraft?.live_capture_aid || "",
  };
  state.productiveDrafts[draftKey] = {
    code: pending.code,
    movement,
    ...equipment,
    material_paste: elements.materialPaste.value,
    material_notice: state.materialNotice,
  };
  processOrders([pending.order], pending.code, equipment);
});
elements.pause.addEventListener("click", () => {
  state.paused = !state.paused;
  elements.pause.textContent = state.paused ? "Continuar" : "Pausar";
  elements.runTitle.textContent = state.paused ? "Lote pausado" : "Processando";
});
elements.stop.addEventListener("click", () => { state.stopped = true; });

async function refreshForNewDay() {
  if (!state.authReady) return;
  const today = localDate();
  if (state.running || elements.date.value === today) return;
  elements.date.value = today;
  elements.date.min = today;
  elements.date.max = today;
  state.completed = 0;
  await loadOrders();
}

window.addEventListener("focus", refreshForNewDay);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.authReady) {
    refreshForNewDay();
    loadToaAutomation({ quiet: true });
    loadToaLiveStatus({ quiet: true });
  }
});

setInterval(() => {
  if (state.authReady) loadToaAutomation({ quiet: true });
}, 15000);
setInterval(() => {
  if (state.authReady) loadToaLiveStatus({ quiet: true });
}, 20000);
setInterval(() => {
  if (state.activeModule === "history") loadServerLogs({ quiet: true });
}, 7500);
setInterval(() => {
  if (state.activeModule === "intelligence") loadHealthCheck({ fresh: true, quiet: true });
}, 60000);
setInterval(() => {
  const hasPending = (state.closeReport.records || []).some((record) => (
    ["sending", "pending", "uncertain"].includes(String(record.state))
  ));
  if (state.activeModule === "report" || hasPending) loadCloseReport({ quiet: true });
}, 10000);

renderSidebarState();
syncThemeControls();

if (globalThis.lucide) {
  globalThis.lucide.createIcons({
    attrs: {
      "stroke-width": 2,
      width: 18,
      height: 18,
    },
  });
}

async function initialize() {
  try {
    state.profileSwitching = true;
    await loadImportTargets();
    await loadToaAutomation({ quiet: true });
    await loadProfiles();
    await loadProfile();
    await loadMonitorCsvSnapshot({ quiet: true });
    await loadToaLiveStatus({ quiet: true });
    await loadOrders();
    await loadSemiAutoAgenda({ quiet: true });
    await loadCloseReport({ quiet: true });
    if (["stock", "bulk"].includes(state.activeModule)) {
      await loadStockTechnicians();
    }
    if (state.activeModule === "technicians") await loadTechnicians();
    if (state.activeModule === "automation-test") await loadAutomationTestData();
    if (state.activeModule === "intelligence") {
      await Promise.all([loadIntelligence({ quiet: true }), loadHealthCheck({ quiet: true })]);
    }
  } catch (error) {
    setConnection("Falha ao iniciar o painel", "error");
    showToast(error.message, "error");
    console.error("Falha ao iniciar o painel", error);
  } finally {
    state.loading = false;
    state.profileSwitching = false;
    renderProfileTabs();
    render();
  }
}

bootstrapAuthentication();
window.setTimeout(() => {
  if (state.authReady) showTermsOnFirstVisit();
}, 250);
