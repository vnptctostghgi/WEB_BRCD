const $ = (selector) => document.querySelector(selector);
const role = document.body.dataset.role;
let mustChangePassword = ["1", "True", "true"].includes(document.body.dataset.mustChange);
const canManageVault = document.body.dataset.canManageVault === "True";
const canRevealVault = document.body.dataset.canRevealVault === "True";
let users = [];
let websites = [];
let credentialWebsites = [];
let credentials = [];
let features = [];
let regions = [];
let connections = [];
let systemRoles = [];
let workTasks = [];
let zaloAutoMessages = [];
let dataMiningSchedules = [];
let dataMiningRuns = [];
let oneBssReports = [];
let oneBssReportDrafts = [];
let oneBssReportRuns = [];
let oneBssPendingSessionId = "";
let oneBssPendingOtpRequestId = "";
let oneBssOtpPollTimer = null;
let oneBssOtpPollToken = 0;
let oneBssOtpManualSubmitStarted = false;
let oneBssManualOtpTimer = null;
let oneBssRunInProgress = false;
let oneBssRunParameterEditing = false;
let mobileGatewayLoaded = false;
let mobileGatewayDevices = [];
let mobileGatewayOverview = {};
let mobileGatewaySmsPage = 1;
let mobileGatewaySmsHasMore = false;
let mobileGatewayNotificationPage = 1;
let mobileGatewayNotificationHasMore = false;
let mobileGatewayOtpFilters = [];
let mobileGatewayOtpLatest = [];
let mobileGatewayMediaItems = [];
let mobileGatewayPairingPollTimer = null;
let mobileGatewayPairingCountdownTimer = null;
let mobileGatewayActivePairingId = null;
let mobileGatewayActivePairingExpiresAt = "";
let sqlReports = [];
let sqlReportDrafts = [];
let dynamicReportPage = 1;
let dynamicReportTotal = 0;
let dynamicReportLoaded = false;
let dynamicReportColumns = [];
let dynamicReportLoadedRows = [];
let dynamicReportFilteredRows = [];
let dynamicReportSearchActive = false;
let dynamicReportExportJobs = [];
const dynamicReportHistoryPollingJobs = new Set();
let menuLayoutState = [];
let auditLogs = [];
let dashboardFiberLoaded = false;
let dashboardViewerLayouts = [];
let dashboardViewerLayoutsLoaded = false;
let dashboardViewerLayout = null;
let dashboardViewerActiveTabId = "";
let dashboardViewerLoadedTabs = {};
let dashboardFeatureCodes = new Set();
let dashboardLayouts = [];
let dashboardBuilderLayout = null;
let dashboardBuilderActiveTabId = "";
let dashboardBuilderLoadedTabs = {};
let dashboardPageIdByFeatureCode = new Map();
let draggedDashboardTabId = "";
let draggedDashboardRowId = "";
const dashboardChartInstances = new Map();
let pendingDashboardCharts = [];
let pendingDashboardSheets = [];
const dashboardLayoutDefinitions = {
  "1_column": { total: 1, spans: [1], label: "1 cột" },
  "2_columns": { total: 2, spans: [1, 1], label: "2 cột" },
  "3_columns": { total: 3, spans: [1, 1, 1], label: "3 cột" },
  "4_columns": { total: 4, spans: [1, 1, 1, 1], label: "4 cột" },
  "5_columns": { total: 5, spans: [1, 1, 1, 1, 1], label: "5 cột" },
  "6_columns": { total: 6, spans: [1, 1, 1, 1, 1, 1], label: "6 cột" },
  "4_columns_1_3": { total: 4, spans: [1, 3], label: "4 cột: 1 + 3" },
  "4_columns_3_1": { total: 4, spans: [3, 1], label: "4 cột: 3 + 1" },
  "5_columns_1_4": { total: 5, spans: [1, 4], label: "5 cột: 1 + 4" },
  "5_columns_4_1": { total: 5, spans: [4, 1], label: "5 cột: 4 + 1" },
  "5_columns_2_3": { total: 5, spans: [2, 3], label: "5 cột: 2 + 3" },
  "5_columns_3_2": { total: 5, spans: [3, 2], label: "5 cột: 3 + 2" },
  "6_columns_1_5": { total: 6, spans: [1, 5], label: "6 cột: 1 + 5" },
  "6_columns_5_1": { total: 6, spans: [5, 1], label: "6 cột: 5 + 1" },
  "6_columns_2_4": { total: 6, spans: [2, 4], label: "6 cột: 2 + 4" },
  "6_columns_4_2": { total: 6, spans: [4, 2], label: "6 cột: 4 + 2" },
};
const dashboardLayoutColumns = Object.fromEntries(Object.entries(dashboardLayoutDefinitions).map(([key, definition]) => [key, definition.spans.length]));
const dashboardDataWidgetTypes = new Set(["bar_chart", "pie_chart", "line_chart", "combo_chart", "multi_bar_chart", "horizontal_multi_bar_chart", "multi_line_chart", "data_table", "metric", "data_card"]);
const dashboardNonSqlWidgetTypes = new Set(["text_title", "google_sheet_embed"]);
const dashboardColorScaleStops = [
  { ratio: 0, rgb: [239, 68, 68] },
  { ratio: .5, rgb: [245, 158, 11] },
  { ratio: 1, rgb: [59, 130, 246] },
];
const dashboardPiePalette = [
  "#2563eb",
  "#f59e0b",
  "#22c55e",
  "#a855f7",
  "#ef4444",
  "#14b8a6",
  "#eab308",
  "#ec4899",
  "#06b6d4",
  "#f97316",
  "#84cc16",
  "#8b5cf6",
];
const dashboardRuntimeThemes = {
  dark: {
    cardBackground: "#041931",
    cardBorder: "rgba(125, 211, 252, .72)",
    textColor: "#ffffff",
    axisColor: "#f8fafc",
    secondaryAxisColor: "#fef3c7",
    gridColor: "rgba(186, 230, 253, .24)",
    valueShadow: "transparent",
    labelStroke: "rgba(2, 6, 23, .85)",
    lineColor: "#2563eb",
    lineFill: "rgba(37, 99, 235, .22)",
    pieBorder: "#082f49",
    seriesPalette: ["#38bdf8", "#f59e0b", "#22c55e", "#ef4444", "#a78bfa", "#14b8a6", "#f97316", "#60a5fa"],
    piePalette: dashboardPiePalette,
  },
  light: {
    cardBackground: "#ffffff",
    cardBorder: "rgba(14, 116, 144, .34)",
    textColor: "#0f172a",
    axisColor: "#111827",
    secondaryAxisColor: "#92400e",
    gridColor: "rgba(15, 23, 42, .14)",
    valueShadow: "transparent",
    labelStroke: "rgba(255, 255, 255, .92)",
    lineColor: "#1d4ed8",
    lineFill: "rgba(29, 78, 216, .14)",
    pieBorder: "#ffffff",
    seriesPalette: ["#2563eb", "#f97316", "#16a34a", "#dc2626", "#7c3aed", "#0891b2", "#ca8a04", "#db2777"],
    piePalette: ["#2563eb", "#f97316", "#16a34a", "#7c3aed", "#dc2626", "#0891b2", "#ca8a04", "#db2777", "#0284c7", "#ea580c", "#65a30d", "#9333ea"],
  },
};
const chartJsSource = "https://cdn.jsdelivr.net/npm/chart.js";
const html2CanvasSource = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
let chartJsLoadPromise = null;
let html2CanvasLoadPromise = null;
let dashboardChartRenderToken = 0;
let dashboardSheetRenderToken = 0;
let dashboardRuntimeTheme = localStorage.getItem("dashboardRuntimeTheme") === "light" ? "light" : "dark";
let activeViewLoadToken = 0;
const VIEW_TRANSITION_MS = 320;
const VIEW_SETTLE_MS = 140;
let viewTransitionTimer = 0;
let viewTransitionHoldTimer = 0;
const dataCacheTimestamps = new Map();
const dashboardViewerLayoutCache = new Map();
const dashboardBuilderLayoutCache = new Map();
const DATA_CACHE_TTL_MS = 2 * 60 * 1000;

function markDataFresh(key) {
  dataCacheTimestamps.set(key, Date.now());
}

function markDataStale(...keys) {
  keys.forEach((key) => dataCacheTimestamps.delete(key));
}

function isDataFresh(key) {
  const timestamp = dataCacheTimestamps.get(key);
  return Boolean(timestamp && Date.now() - timestamp < DATA_CACHE_TTL_MS);
}

function cloneDashboardLayout(layout) {
  return JSON.parse(JSON.stringify(layout || {}));
}

function nextPaint() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
  });
}

function getViewTransitionHeight(...views) {
  const measuredHeights = views
    .map((view) => Math.ceil(view?.getBoundingClientRect?.().height || 0))
    .filter(Boolean);
  const viewportFloor = Math.min(Math.max(window.innerHeight * 0.66, 360), 720);
  return Math.max(360, viewportFloor, ...measuredHeights);
}

function holdAppViewHeight(...views) {
  const main = $(".app-main");
  if (!main) return;
  window.clearTimeout(viewTransitionHoldTimer);
  main.style.setProperty("--view-transition-min-height", `${getViewTransitionHeight(...views)}px`);
  main.classList.add("view-transitioning");
}

function releaseAppViewHeight(delay = VIEW_SETTLE_MS) {
  const main = $(".app-main");
  window.clearTimeout(viewTransitionHoldTimer);
  viewTransitionHoldTimer = window.setTimeout(() => {
    if (document.body.classList.contains("view-loading")) {
      releaseAppViewHeight(VIEW_SETTLE_MS);
      return;
    }
    main?.classList.remove("view-transitioning");
    main?.style.removeProperty("--view-transition-min-height");
  }, delay);
}

function markViewSettled(view) {
  if (!view?.classList.contains("active")) return;
  view.classList.add("view-settled");
  window.setTimeout(() => view.classList.remove("view-settled"), 320);
}

async function runActiveViewLoader(token, loader, activeView) {
  await nextPaint();
  if (token !== activeViewLoadToken) return;
  const loadingView = activeView || document.querySelector(".app-view.active");
  loadingView?.classList.add("view-preparing");
  holdAppViewHeight(document.querySelector(".app-view.view-exiting"), loadingView);
  const loadingTimer = window.setTimeout(() => {
    if (token === activeViewLoadToken) document.body.classList.add("view-loading");
  }, 90);
  try {
    await loader();
  } catch (error) {
    if (token === activeViewLoadToken) showToast(error.message || "Không tải được dữ liệu.", "error");
  } finally {
    window.clearTimeout(loadingTimer);
    if (token === activeViewLoadToken) {
      document.body.classList.remove("view-loading");
      loadingView?.classList.remove("view-preparing");
      markViewSettled(loadingView);
      await nextPaint();
      releaseAppViewHeight();
    }
  }
}

function setActiveAppView(viewName) {
  const nextView = $(`#view-${viewName}`);
  if (!nextView) return null;
  const currentView = document.querySelector(".app-view.active");
  window.clearTimeout(viewTransitionTimer);
  document.querySelectorAll(".app-view.view-exiting, .app-view.view-entering").forEach((view) => {
    view.classList.remove("view-exiting", "view-entering");
  });
  document.querySelectorAll(".app-view.active").forEach((view) => {
    if (view !== currentView && view !== nextView) view.classList.remove("active");
  });
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (!currentView || currentView === nextView || reduceMotion) {
    document.querySelectorAll(".app-view").forEach((view) => view.classList.remove("active", "view-exiting", "view-entering"));
    nextView.classList.add("active");
    releaseAppViewHeight(0);
    return nextView;
  }
  holdAppViewHeight(currentView, nextView);
  currentView.classList.remove("active");
  currentView.classList.add("view-exiting");
  nextView.classList.add("active", "view-entering");
  viewTransitionTimer = window.setTimeout(() => {
    currentView.classList.remove("view-exiting");
    nextView.classList.remove("view-entering");
    releaseAppViewHeight();
  }, VIEW_TRANSITION_MS);
  return nextView;
}

const navFeatureConfig = {
  quanlycongviec: { view: "work-tasks", icon: "list", keywords: "quan ly cong viec task lich telegram nhac viec" },
  taikhoanweb: { view: "vault", icon: "vault", keywords: "tai khoan web mat khau" },
  quantringuoidung: { view: "users", icon: "users", keywords: "quan tri nguoi dung user" },
  quantrimenu: { view: "menu-admin", icon: "list", keywords: "quan tri menu sap xep di chuyen module" },
  quantridanhmuc: { view: "catalogs", icon: "list", keywords: "quan tri danh muc phan vung vai tro bien" },
  quantriketnoi: { view: "system", icon: "plug", keywords: "quan tri ket noi api db ftp drive telegram zalo" },
  mobilegateway: { view: "mobile-gateway", icon: "database", keywords: "mobile gateway sms otp android onebss" },
  phanquyennguoidung: { view: "permissions", icon: "shield", keywords: "phan quyen nguoi dung chuc nang" },
  phanquyendulieunguoidung: { view: "data-permissions", icon: "database", keywords: "phan quyen du lieu phan vung" },
  nhatkyhoatdong: { view: "audit", icon: "audit", keywords: "nhat ky audit log" },
  truyvansql: { view: "reports", icon: "chart", keywords: "truy van sql bao cao thong ke bieu do" },
  thietkelayoutbaocao: { view: "dashboard-builder", icon: "chart", keywords: "dashboard builder thiet ke layout bao cao tab bieu do" },
  daodulieuonebss: { view: "onebss-mining", icon: "database", keywords: "dao du lieu onebss bao cao excel" },
};

const navGroupOnlyFeatureCodes = new Set(["dashboard", "baocaomoi"]);

const navGroupIcons = {
  quantriweb: "shield",
  quantridanhmuc: "list",
  quantriketnoi: "plug",
  taikhoanweb: "vault",
  dashboard: "dashboard",
  truyvansql: "chart",
  baocaomoi: "chart",
};

const mojibakePattern = new RegExp("(?:\\u00c3|\\u00c4|\\u00c2|\\u00c6|\\u00e1\\u00ba|\\u00e1\\u00bb|\\u00e2\\u20ac)");
const windows1252ByteMap = new Map([
  ["€", 0x80], ["‚", 0x82], ["ƒ", 0x83], ["„", 0x84], ["…", 0x85], ["†", 0x86], ["‡", 0x87],
  ["ˆ", 0x88], ["‰", 0x89], ["Š", 0x8a], ["‹", 0x8b], ["Œ", 0x8c], ["Ž", 0x8e],
  ["‘", 0x91], ["’", 0x92], ["“", 0x93], ["”", 0x94], ["•", 0x95], ["–", 0x96], ["—", 0x97],
  ["˜", 0x98], ["™", 0x99], ["š", 0x9a], ["›", 0x9b], ["œ", 0x9c], ["ž", 0x9e], ["Ÿ", 0x9f],
]);

function repairTextEncoding(value) {
  const text = String(value ?? "");
  if (!mojibakePattern.test(text) || !window.TextDecoder) return text;
  try {
    const bytes = Uint8Array.from([...text].map((character) => {
      const mapped = windows1252ByteMap.get(character);
      return mapped ?? (character.charCodeAt(0) & 0xff);
    }));
    const decoded = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    return decoded.includes(String.fromCharCode(0xfffd)) ? text : decoded;
  } catch {
    return text;
  }
}

function repairDataEncoding(value) {
  if (typeof value === "string") return repairTextEncoding(value);
  if (Array.isArray(value)) return value.map((item) => repairDataEncoding(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [repairTextEncoding(key), repairDataEncoding(item)]));
  }
  return value;
}

function escapeHtml(value) {
  return repairTextEncoding(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: options.body instanceof FormData ? (options.headers || {}) : { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Phiên đăng nhập đã hết hạn.");
  }
  const text = await response.text();
  let body = {};
  if (text.trim()) {
    try {
      body = JSON.parse(text);
    } catch {
      const preview = text.replace(/\s+/g, " ").trim().slice(0, 240);
      throw new Error(`May chu tra ve phan hoi khong phai JSON (HTTP ${response.status}). ${preview}`);
    }
  } else if (!response.ok) {
    throw new Error(`May chu tra ve phan hoi rong (HTTP ${response.status}). Hay thu lai hoac rut ngan dieu kien bao cao.`);
  }
  if (response.status === 403) {
    const message = body.detail || "Bạn không có quyền truy cập chức năng này";
    showToast(message, "error");
    throw new Error(message);
  }
  if (!response.ok) throw new Error(body.detail || "Có lỗi xảy ra.");
  return body;
}

function showMessage(element, text, type = "success") {
  if (element) {
    element.textContent = "";
    element.classList?.add("hidden");
    element.setAttribute?.("aria-hidden", "true");
  }
  showToast(text, type);
}

let toastTimer;
async function copyTextToClipboard(text) {
  const value = String(text || "");
  if (!value) throw new Error("Khong co noi dung de sao chep.");
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  const ok = document.execCommand("copy");
  textarea.remove();
  if (!ok) throw new Error("Trinh duyet chan sao chep clipboard.");
}

async function copyMobileOtpFromButton(button) {
  const code = button?.dataset.mobileCopyOtp || "";
  if (!code || code === "null") return;
  try {
    await copyTextToClipboard(code);
    showToast(`Da sao chep OTP ${code}.`);
  } catch (error) {
    showToast(error.message || "Khong sao chep duoc OTP.", "error");
  }
}

function selectElementText(element) {
  if (!element) return;
  const selection = window.getSelection?.();
  if (!selection) return;
  const range = document.createRange();
  range.selectNodeContents(element);
  selection.removeAllRanges();
  selection.addRange(range);
}

function renderMobileOtpCopyCell(code) {
  const value = String(code || "").trim();
  const canCopy = value && value !== "null" && !/^\*+$/.test(value);
  return `
    <div class="mobile-otp-copy-cell">
      <code class="mobile-otp-code" data-mobile-otp-code tabindex="0">${escapeHtml(value || "null")}</code>
      <button class="table-action mobile-otp-copy-button" data-mobile-copy-otp="${escapeHtml(value)}" type="button" ${canCopy ? "" : "disabled"}>Copy</button>
    </div>`;
}
function showToast(text, type = "success") {
  const toast = $("#toast");
  if (!toast) return;
  window.clearTimeout(toastTimer);
  toast.textContent = repairTextEncoding(text);
  toast.className = `toast ${type === "error" ? "error" : ""}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3500);
}

function loadingRow(colspan, text = "Đang tải dữ liệu...") {
  return `<tr><td colspan="${colspan}" class="loading-row">${escapeHtml(text)}</td></tr>`;
}

function emptyRow(colspan, title, description = "Chưa có dữ liệu để hiển thị.") {
  return `<tr><td colspan="${colspan}"><div class="empty-state"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div></div></td></tr>`;
}

function renderCompactCode(value) {
  const text = typeof value === "string" ? value.trim() : (JSON.stringify(value ?? {}, null, 2) || "");
  return `<code class="compact-code" title="${escapeHtml(text)}">${escapeHtml(text)}</code>`;
}

function setTableLoading(selector, colspan, text) {
  const element = $(selector);
  if (element) element.innerHTML = loadingRow(colspan, text);
}

function setButtonLoading(button, isLoading) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
}

$("#menu-button")?.addEventListener("click", () => {
  const open = $("#sidebar").classList.toggle("menu-open");
  $("#menu-button").setAttribute("aria-expanded", String(open));
});

document.querySelectorAll(".nav-group").forEach((group) => {
  group.open = false;
});

function featurePathFromCode(code) {
  const normalized = String(code || "").trim().replace(/^\/+|\/+$/g, "");
  return normalized ? `/${encodeURIComponent(normalized)}` : "/";
}

function featureCodeFromCurrentPath() {
  const path = window.location.pathname.replace(/^\/+|\/+$/g, "");
  if (!path || path === "login") return "";
  return decodeURIComponent(path).toLowerCase();
}

function updateFeatureUrl(code, { replace = false } = {}) {
  const nextPath = featurePathFromCode(code);
  if (!nextPath || nextPath === window.location.pathname) return;
  const nextUrl = `${nextPath}${window.location.hash || ""}`;
  if (replace) {
    window.history.replaceState({ featureCode: code }, "", nextUrl);
  } else {
    window.history.pushState({ featureCode: code }, "", nextUrl);
  }
}

function viewLoaderForNav(nextView, dashboardPageId) {
  if (nextView === "dashboard") return () => (dashboardPageId ? openDashboardViewerLayout(dashboardPageId) : loadDashboardViewer());
  if (nextView === "users") return () => loadUsers();
  if (nextView === "vault") return () => loadCredentials();
  if (nextView === "websites") return () => loadAdminWebsites();
  if (nextView === "system") return () => loadSystem();
  if (nextView === "reports") return () => loadDynamicReports();
  if (nextView === "onebss-mining") return () => loadOneBssMining();
  if (nextView === "mobile-gateway") return () => loadMobileGateway();
  if (nextView === "dashboard-builder") return () => loadDashboardBuilder();
  if (nextView === "menu-admin") return () => loadMenuLayout();
  if (nextView === "work-tasks") return () => loadWorkTasks();
  if (nextView === "permissions") return () => loadPermissionManager();
  if (nextView === "data-permissions") return () => loadDataPermissionManager();
  if (nextView === "catalogs") return () => loadCatalogs();
  if (nextView === "audit") return () => loadAudit();
  return null;
}

async function activateNavItem(item, options = {}) {
  const { updateUrl = true, replaceUrl = false } = options;
  const loadToken = ++activeViewLoadToken;
  const nextView = item.dataset.view || "";
  const dashboardPageId = item.dataset.dashboardPageId || "";
  $("#view-dashboard")?.classList.toggle("dashboard-dynamic-mode", Boolean(dashboardPageId));
  document.querySelectorAll(".nav-item").forEach((element) => element.classList.remove("active"));
  item.classList.add("active");
  openNavParents(item);
  const activeView = setActiveAppView(nextView);
  const moduleTitle = $("#module-title");
  if (moduleTitle) moduleTitle.textContent = item.dataset.title || item.textContent.trim();
  $("#sidebar").classList.remove("menu-open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  if (updateUrl) updateFeatureUrl(item.dataset.featureCode, { replace: replaceUrl });
  const loader = viewLoaderForNav(nextView, dashboardPageId);
  if (loader) runActiveViewLoader(loadToken, loader, activeView);
  else document.body.classList.remove("view-loading");
}

$("#nav-tree")?.addEventListener("click", async (event) => {
  const item = event.target.closest(".nav-item[data-view]");
  if (!item || !$("#nav-tree")?.contains(item)) return;
  await activateNavItem(item);
});

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.openDialog === "credential-dialog") {
    openCredential("").catch((error) => showToast(error.message, "error"));
    return;
  }
  if (button.dataset.openDialog === "website-dialog") {
    openWebsite("");
    return;
  }
  if (button.dataset.openDialog === "region-dialog") {
    openRegion("");
    return;
  }
  if (button.dataset.openDialog === "role-dialog") {
    openRole("");
    return;
  }
  if (button.dataset.openDialog === "work-task-dialog") {
    openWorkTask("");
    return;
  }
  if (button.dataset.openDialog === "sql-report-dialog") {
    openSqlReport("");
    return;
  }
  $(`#${button.dataset.openDialog}`).showModal();
}));
document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

$("#menu-search")?.addEventListener("input", (event) => filterNavigation(event.currentTarget.value));

$("#menu-layout-table")?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-menu-move]");
  if (!button || !$("#menu-layout-table")?.contains(button)) return;
  moveMenuItem(button.dataset.menuCode, button.dataset.menuMove);
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("#save-menu-layout");
  if (!button) return;
  event.preventDefault();
  await saveMenuLayout(button);
});

function filterNavigation(keyword) {
  const query = keyword.trim().toLowerCase();
  let visibleItems = 0;
  document.querySelectorAll(".nav-group").forEach((group) => {
    let groupHasVisibleChild = false;
    group.querySelectorAll(".nav-item").forEach((item) => {
      const text = `${item.textContent} ${item.dataset.keywords || ""}`.toLowerCase();
      const visible = !query || text.includes(query);
      item.classList.toggle("hidden-by-search", !visible);
      if (visible) {
        groupHasVisibleChild = true;
        visibleItems += 1;
      }
    });
    group.classList.toggle("hidden-by-search", !groupHasVisibleChild);
    if (query && groupHasVisibleChild) group.open = true;
  });
  document.querySelectorAll("#nav-tree > .nav-item").forEach((item) => {
    const text = `${item.textContent} ${item.dataset.keywords || ""}`.toLowerCase();
    const visible = !query || text.includes(query);
    item.classList.toggle("hidden-by-search", !visible);
    if (visible) visibleItems += 1;
  });
  $("#nav-empty")?.classList.toggle("hidden", visibleItems > 0);
}

if (mustChangePassword) {
  const dialog = $("#password-dialog");
  if (dialog && !dialog.open) {
    dialog.showModal();
  }
}

syncNavigationFromFeatures();

window.addEventListener("popstate", () => {
  activateNavForCurrentPath();
});

function closeTopDropdowns(except = null) {
  ["notification-menu", "user-menu"].forEach((id) => {
    const menu = $(`#${id}`);
    if (menu && menu !== except) menu.classList.add("hidden");
  });
  ["notification-toggle", "user-menu-toggle"].forEach((id) => {
    const button = $(`#${id}`);
    if (button && (except === null || button.getAttribute("aria-controls") !== except?.id)) {
      button.setAttribute("aria-expanded", "false");
    }
  });
}

function toggleTopDropdown(buttonSelector, menuSelector) {
  const button = $(buttonSelector);
  const menu = $(menuSelector);
  if (!button || !menu) return;
  button.setAttribute("aria-controls", menu.id);
  button.addEventListener("click", async (event) => {
    event.stopPropagation();
    const willOpen = menu.classList.contains("hidden");
    closeTopDropdowns(menu);
    menu.classList.toggle("hidden", !willOpen);
    button.setAttribute("aria-expanded", String(willOpen));
    if (willOpen && menu.id === "notification-menu") await loadNotifications();
  });
}

toggleTopDropdown("#notification-toggle", "#notification-menu");
toggleTopDropdown("#user-menu-toggle", "#user-menu");

document.addEventListener("click", (event) => {
  if (!event.target.closest(".dropdown-wrap")) closeTopDropdowns();
});

$("#credential-form")?.addEventListener("submit", saveCredential);
$("#credential-website")?.addEventListener("change", updateCredentialWebsiteInfo);

document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
}));

async function loadNotifications() {
  const list = $("#notification-list");
  if (!list) return;
  list.innerHTML = `<div class="dropdown-empty">Đang tải thông báo...</div>`;
  try {
    const data = await api("/api/notifications");
    list.innerHTML = data.notifications.length ? data.notifications.map((item) => `
      <article class="notification-item">
        <strong>${escapeHtml(item.title)}</strong>
        <p>${escapeHtml(item.message)}</p>
        <small>${new Date(item.created_at).toLocaleString("vi-VN")}</small>
      </article>
    `).join("") : `<div class="dropdown-empty">Chưa có thông báo mới.</div>`;
  } catch (error) {
    list.innerHTML = `<div class="dropdown-empty error">${escapeHtml(error.message)}</div>`;
  }
}

async function ensureDashboardViewerLoaded() {
  if (dashboardViewerLayout) {
    renderDashboardViewer();
    await loadDashboardViewerTab(dashboardViewerActiveTabId);
    return;
  }
  await loadDashboardViewer();
}

async function loadDashboardFiber({ force = false } = {}) {
  if (dashboardFiberLoaded && !force) return;
  const button = $("#refresh-dashboard-fiber");
  const message = $("#dashboard-fiber-message");
  setDashboardFiberLoading();
  if (button) setButtonLoading(button, true);
  try {
    const response = await api("/api/dashboard/fiber");
    dashboardFiberLoaded = true;
    renderDashboardFiber(response);
    if (message) showMessage(message, response.message || "Đã tải dữ liệu Fiber.", response.ok ? "success" : "error");
  } catch (error) {
    renderDashboardFiberError(error.message);
    if (message) showMessage(message, error.message, "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

function setDashboardFiberLoading() {
  ["vnpt", "ttvt"].forEach((group) => {
    const body = $(`#dashboard-fiber-${group}-body`);
    const chart = $(`#dashboard-fiber-${group}-chart`);
    if (body) body.innerHTML = loadingRow(3, "Đang tải sản lượng Fiber...");
    if (chart) chart.innerHTML = `<div class="dashboard-chart-empty">Đang tải dữ liệu...</div>`;
  });
}

function renderDashboardFiber(response) {
  const vnptRows = response.groups?.vnpt?.rows || [];
  const ttvtRows = response.groups?.ttvt?.rows || [];
  const period = response.period_label ? `Tháng ${response.period_label}` : "Tháng hiện tại";
  const fiberTotal = response.summary?.production?.fiber ?? response.groups?.vnpt?.total ?? 0;

  const summaryPeriod = $("#dashboard-summary-period");
  const fiberPeriod = $("#dashboard-fiber-period");
  const productionFiber = $("#dashboard-production-fiber");
  if (summaryPeriod) summaryPeriod.textContent = period;
  if (fiberPeriod) fiberPeriod.textContent = `${period}, lọc loại hình 58 và thuê bao chưa cắt.`;
  if (productionFiber) productionFiber.textContent = formatDashboardNumber(fiberTotal);

  renderDashboardFiberTable("vnpt", vnptRows);
  renderDashboardFiberTable("ttvt", ttvtRows);
  renderDashboardFiberChart("#dashboard-fiber-vnpt-chart", vnptRows);
  renderDashboardFiberChart("#dashboard-fiber-ttvt-chart", ttvtRows);
}

function renderDashboardFiberError(message) {
  const productionFiber = $("#dashboard-production-fiber");
  if (productionFiber) productionFiber.textContent = "--";
  ["vnpt", "ttvt"].forEach((group) => {
    const body = $(`#dashboard-fiber-${group}-body`);
    const chart = $(`#dashboard-fiber-${group}-chart`);
    if (body) body.innerHTML = emptyRow(3, "Không tải được dữ liệu Fiber", message);
    if (chart) chart.innerHTML = `<div class="dashboard-chart-empty error">${escapeHtml(message)}</div>`;
  });
}

function renderDashboardFiberTable(group, rows) {
  const body = $(`#dashboard-fiber-${group}-body`);
  if (!body) return;
  body.innerHTML = rows.length ? rows.map((row) => `
    <tr>
      <td><span class="rank-cell">${escapeHtml(row.rank)}</span></td>
      <td><strong>${escapeHtml(row.unit_name)}</strong></td>
      <td>${formatDashboardNumber(row.fiber_quantity)}</td>
    </tr>
  `).join("") : emptyRow(3, "Chưa có dữ liệu", "API nội bộ chưa trả dữ liệu cho nhóm này.");
}

function renderDashboardFiberChart(selector, rows) {
  const chart = $(selector);
  if (!chart) return;
  if (!rows.length) {
    chart.innerHTML = `<div class="dashboard-chart-empty">Chưa có dữ liệu để vẽ biểu đồ.</div>`;
    return;
  }
  const maxValue = Math.max(...rows.map((row) => Number(row.fiber_quantity) || 0), 1);
  chart.innerHTML = rows.map((row) => {
    const value = Number(row.fiber_quantity) || 0;
    const width = value > 0 ? Math.max(4, Math.round((value / maxValue) * 100)) : 0;
    return `
      <div class="bar-row">
        <div class="bar-label"><strong>#${escapeHtml(row.rank)}</strong><span>${escapeHtml(row.unit_name)}</span></div>
        <div class="bar-track"><span style="width: ${width}%"></span></div>
        <div class="bar-value">${formatDashboardNumber(value)}</div>
      </div>
    `;
  }).join("");
}

function applyDashboardLayoutList(layouts = []) {
  dashboardViewerLayouts = Array.isArray(layouts) ? layouts : [];
  dashboardViewerLayoutsLoaded = true;
  markDataFresh("dashboardViewerLayouts");
  const pageEntries = [];
  dashboardViewerLayouts.forEach((layout) => {
    const pageId = layout.page_id || "";
    const compactCode = dashboardFeatureCodeForPageId(pageId);
    const underscoreCode = String(pageId).trim().toLowerCase();
    if (compactCode && pageId) pageEntries.push([compactCode, pageId]);
    if (underscoreCode && pageId) pageEntries.push([underscoreCode, pageId]);
  });
  dashboardPageIdByFeatureCode = new Map(pageEntries);
  dashboardFeatureCodes = new Set(dashboardPageIdByFeatureCode.keys());
}

async function loadDashboardViewer() {
  if (!$("#dashboard-designed-section")) return;
  try {
    if (!dashboardViewerLayoutsLoaded) {
      const data = await api("/api/dashboard-layouts");
      applyDashboardLayoutList(data.layouts || []);
    }
    if (!dashboardViewerLayouts.length) {
      dashboardViewerLayout = null;
      renderDashboardViewerEmpty("Chưa có trang Dashboard", "Hãy tạo Layout trong chức năng Thiết kế Layout báo cáo.");
      return;
    }
    const pageId = dashboardViewerLayout?.page_id || dashboardViewerLayouts[0].page_id;
    await openDashboardViewerLayout(pageId);
  } catch (error) {
    showMessage($("#dashboard-viewer-message"), error.message, "error");
    renderDashboardViewerEmpty("Không tải được Dashboard đã thiết kế", error.message);
  }
}

async function openDashboardViewerLayout(pageId) {
  const normalizedPageId = String(pageId || "").trim();
  if (!normalizedPageId) return;
  const preferredTabId = dashboardViewerLayout?.page_id === normalizedPageId ? dashboardViewerActiveTabId : "";
  const cachedLayout = dashboardViewerLayoutCache.get(normalizedPageId);
  if (cachedLayout) {
    dashboardViewerActiveTabId = preferredTabId;
    dashboardViewerLayout = normalizeDashboardViewerLayout(cloneDashboardLayout(cachedLayout), cachedLayout.page_name || "");
    dashboardViewerLayout.page_name = cachedLayout.page_name || dashboardViewerLayout.page_name;
    if (!dashboardViewerLayout.tabs.some((tab) => tab.tab_id === dashboardViewerActiveTabId)) {
      dashboardViewerActiveTabId = dashboardViewerLayout.tabs[0]?.tab_id || "";
    }
    renderDashboardViewer();
    await loadDashboardViewerTab(dashboardViewerActiveTabId);
    return;
  }
  const data = await api(`/api/dashboard-layouts/${encodeURIComponent(normalizedPageId)}`);
  dashboardViewerActiveTabId = preferredTabId;
  dashboardViewerLayout = normalizeDashboardViewerLayout(data.layout || {}, data.page_name || "");
  dashboardViewerLayout.page_name = data.page_name || dashboardViewerLayout.page_name;
  if (!dashboardViewerLayout.tabs.some((tab) => tab.tab_id === dashboardViewerActiveTabId)) {
    dashboardViewerActiveTabId = dashboardViewerLayout.tabs[0]?.tab_id || "";
  }
  dashboardViewerLayoutCache.set(normalizedPageId, cloneDashboardLayout(dashboardViewerLayout));
  renderDashboardViewer();
  await loadDashboardViewerTab(dashboardViewerActiveTabId);
}

function renderDashboardViewerPageOptions() {
  const select = $("#dashboard-viewer-page");
  if (!select) return;
  select.innerHTML = dashboardViewerLayouts.length
    ? dashboardViewerLayouts.map((page) => `<option value="${escapeHtml(page.page_id)}">${escapeHtml(page.page_name || page.page_id)}</option>`).join("")
    : `<option value="">Chưa có Dashboard</option>`;
  if (dashboardViewerLayout?.page_id) select.value = dashboardViewerLayout.page_id;
}

function renderDashboardViewerEmpty(title, description) {
  applyDashboardRuntimeTheme();
  renderDashboardViewerPageOptions();
  const tabs = $("#dashboard-viewer-tabs");
  const workspace = $("#dashboard-viewer-workspace");
  if (tabs) tabs.innerHTML = "";
  if (workspace) {
    workspace.innerHTML = `
      <div class="dashboard-empty">
        <p class="eyebrow">Dashboard Builder</p>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(description)}</p>
      </div>
    `;
  }
}

function dashboardChartTheme() {
  return dashboardRuntimeThemes[dashboardRuntimeTheme] || dashboardRuntimeThemes.dark;
}

function applyDashboardRuntimeTheme() {
  const section = $("#dashboard-designed-section");
  if (!section) return;
  const isLight = dashboardRuntimeTheme === "light";
  section.classList.toggle("dashboard-theme-light", isLight);
  section.classList.toggle("dashboard-theme-dark", !isLight);
  const button = $("#dashboard-theme-toggle");
  if (!button) return;
  button.setAttribute("aria-pressed", String(isLight));
  button.title = isLight ? "Chuyển nền tối" : "Chuyển nền sáng";
  const label = button.querySelector("span");
  if (label) label.textContent = isLight ? "Tối" : "Sáng";
  const icon = button.querySelector("use");
  if (icon) icon.setAttribute("href", isLight ? "#icon-moon" : "#icon-sun");
  const visibleIcon = button.querySelector(".theme-toggle-icon");
  if (visibleIcon) visibleIcon.textContent = isLight ? "☾" : "☀";
  const visibleLabel = button.querySelector(".theme-toggle-text");
  if (visibleLabel) visibleLabel.textContent = isLight ? "Tối" : "Sáng";
}

function toggleDashboardRuntimeTheme() {
  dashboardRuntimeTheme = dashboardRuntimeTheme === "light" ? "dark" : "light";
  localStorage.setItem("dashboardRuntimeTheme", dashboardRuntimeTheme);
  applyDashboardRuntimeTheme();
  if (dashboardViewerLayout) renderDashboardViewer();
}

function switchDashboardViewerTab(tabId) {
  dashboardViewerActiveTabId = tabId;
  renderDashboardViewer();
  loadDashboardViewerTab(tabId);
}

function dashboardViewerTabCacheKey(tabId) {
  return `${dashboardViewerLayout?.page_id || ""}:${tabId}`;
}

async function loadDashboardViewerTab(tabId, { force = false } = {}) {
  if (!dashboardViewerLayout || !tabId) return;
  const pageId = dashboardViewerLayout.page_id;
  const key = dashboardViewerTabCacheKey(tabId);
  if (dashboardViewerLoadedTabs[key] && !force) {
    renderDashboardViewer();
    return;
  }
  const button = $("#refresh-dashboard-viewer-tab");
  if (button) setButtonLoading(button, true);
  try {
    const response = await api(`/api/dashboard-layouts/${encodeURIComponent(pageId)}/tabs/${encodeURIComponent(tabId)}/data`);
    dashboardViewerLoadedTabs[key] = { ...response, loaded_at: new Date().toISOString() };
    if (dashboardViewerLayout?.page_id === pageId && dashboardViewerActiveTabId === tabId) {
      renderDashboardViewer();
      $("#dashboard-viewer-message")?.classList.add("hidden");
    }
  } catch (error) {
    if (dashboardViewerLayout?.page_id === pageId && dashboardViewerActiveTabId === tabId) {
      showMessage($("#dashboard-viewer-message"), error.message, "error");
    }
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

function renderDashboardViewer() {
  if (!dashboardViewerLayout) return;
  applyDashboardRuntimeTheme();
  renderDashboardViewerPageOptions();
  const title = $("#dashboard-viewer-title");
  const loadedAt = $("#dashboard-viewer-loaded-at");
  const tabs = $("#dashboard-viewer-tabs");
  const workspace = $("#dashboard-viewer-workspace");
  const tab = dashboardViewerLayout.tabs.find((item) => item.tab_id === dashboardViewerActiveTabId) || dashboardViewerLayout.tabs[0];
  if (!tabs || !workspace || !tab) return;
  destroyDashboardCharts();
  if (title) title.textContent = dashboardViewerLayout.page_name || "Dashboard";
  const loadedPayload = dashboardViewerLoadedTabs[dashboardViewerTabCacheKey(tab.tab_id)];
  if (loadedAt) {
    loadedAt.textContent = loadedPayload?.loaded_at
      ? `Dữ liệu được lấy vào lúc: ${new Date(loadedPayload.loaded_at).toLocaleString("vi-VN")}`
      : "Dữ liệu được lấy vào lúc: Chưa tải";
  }
  tabs.innerHTML = dashboardViewerLayout.tabs.map((item) => `
    <button class="runtime-tab ${item.tab_id === tab.tab_id ? "active" : ""}" data-viewer-tab="${escapeHtml(item.tab_id)}" type="button" role="tab" aria-selected="${item.tab_id === tab.tab_id}">
      ${escapeHtml(item.tab_name)}
    </button>
  `).join("");
  const dataByWidget = new Map(((dashboardViewerLoadedTabs[dashboardViewerTabCacheKey(tab.tab_id)] || {}).widgets || []).map((item) => [`${item.row_id}:${item.position}`, item]));
  workspace.innerHTML = (tab.grid_layout || []).length ? tab.grid_layout.map((row, rowIndex) => {
    const columns = dashboardLayoutColumnCount(row.layout_type);
    const widgetsByPosition = new Map((row.widgets || []).map((widget) => [Number(widget.position), widget]));
    const rowChartHeight = dashboardRowChartHeight(row, dataByWidget);
    const cells = Array.from({ length: columns }, (_, cellIndex) => {
      const position = cellIndex + 1;
      const widget = widgetsByPosition.get(position);
      const data = dataByWidget.get(`${row.row_id}:${position}`);
      return `<div class="dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}">${renderRuntimeWidget(widget, data, `dashboard-viewer-${rowIndex}-${position}`, { chartHeight: rowChartHeight })}</div>`;
    }).join("");
    return `<section class="${dashboardGridClass(row.layout_type)}" style="${dashboardGridStyle(row.layout_type)}">${cells}</section>`;
  }).join("") : `
    <div class="dashboard-empty">
      <p class="eyebrow">Dashboard Builder</p>
      <h2>Tab chưa có Layout</h2>
      <p>Mở chức năng Thiết kế Layout báo cáo để thêm biểu đồ cho Tab này.</p>
    </div>
  `;
  schedulePendingDashboardCharts();
  schedulePendingDashboardSheets();
}

function formatDashboardNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return new Intl.NumberFormat("vi-VN").format(number);
}

$("#password-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    const response = await api("/api/auth/change-password", { method: "POST", body: JSON.stringify(data) });
    showMessage(form.querySelector(".result"), response.message);
    mustChangePassword = false;
    document.body.dataset.mustChange = "False";
    form.reset();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
});

async function loadUsers({ force = false } = {}) {
  if (!force && isDataFresh("users")) {
    renderUsersTable();
    return;
  }
  if (users.length && !force) {
    renderUsersTable();
  }
  if (!users.length || force) setTableLoading("#users-table", 5, "Đang tải danh sách người dùng...");
  users = (await api("/api/admin/users")).users;
  markDataFresh("users");
  renderUsersTable();
}

function renderUsersTable() {
  const keyword = ($("#user-search")?.value || "").trim().toLowerCase();
  const filteredUsers = keyword ? users.filter((user) => [
    user.username,
    user.full_name,
    user.employee_code,
    user.email,
    user.department,
    user.job_title,
    user.phone,
  ].some((value) => String(value || "").toLowerCase().includes(keyword))) : users;
  const count = $("#user-count");
  if (count) count.textContent = `${filteredUsers.length}/${users.length} người dùng`;
  $("#users-table").innerHTML = filteredUsers.length ? filteredUsers.map((user) => `
    <tr>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-user="${user.id}">Chỉnh sửa</button> <button class="table-action danger" data-delete-user="${user.id}">Xóa</button></div></td>
      <td><strong>${escapeHtml(user.username)}</strong><small class='cell-note'>${escapeHtml(user.email || user.employee_code || "")}</small>${user.must_change_password ? "<small class='cell-note'>Cần đổi mật khẩu</small>" : ""}</td>
      <td>${escapeHtml(user.full_name)}<small class='cell-note'>${escapeHtml(user.department || "")}</small></td>
      <td><span class="status ${user.role === "admin" ? "admin" : "viewer"}">${user.role === "admin" ? "Quản trị viên" : "Người xem"}</span></td>
      <td><span class="status ${user.is_active ? "active" : "inactive"}">${user.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
    </tr>`).join("") : emptyRow(5, keyword ? "Không tìm thấy người dùng" : "Chưa có người dùng", keyword ? "Hãy thử nhập từ khóa khác." : "Hãy tạo hoặc import người dùng từ Excel.");
  document.querySelectorAll("[data-edit-user]").forEach((button) => button.addEventListener("click", () => openEditUser(Number(button.dataset.editUser))));
  document.querySelectorAll("[data-delete-user]").forEach((button) => button.addEventListener("click", () => deleteUser(Number(button.dataset.deleteUser))));
}

async function deleteUser(id) {
  if (!confirm("Xóa người dùng này?")) return;
  await api(`/api/admin/users/${id}`, { method: "DELETE" });
  await loadUsers({ force: true });
}

async function openEditUser(id) {
  const user = users.find((item) => item.id === id);
  const form = $("#edit-user-form");
  form.elements.namedItem("id").value = user.id;
  form.elements.namedItem("full_name").value = user.full_name;
  form.elements.namedItem("role").value = user.role;
  form.elements.namedItem("is_active").checked = Boolean(user.is_active);
  form.elements.namedItem("password").value = "";
  form.querySelector(".result").className = "result hidden";
  if (!features.length) features = (await api("/api/admin/features")).features;
  const granted = new Set((await api(`/api/admin/users/${id}/permissions`)).feature_codes);
  const orderedFeatures = flattenFeatureTree(buildFeatureTree(features)).map((row) => row.feature);
  $("#permission-tree").innerHTML = orderedFeatures.map((feature) => `
    <label class="permission-item ${feature.parent_code ? "child" : "parent"}">
      <input type="checkbox" value="${escapeHtml(feature.code)}" ${granted.has(feature.code) ? "checked" : ""} />
      <span>${escapeHtml(feature.name)}</span>
    </label>`).join("");
  bindPermissionCascade("#permission-tree");
  $("#edit-user-dialog").showModal();
}

if (role === "admin") {
  normalizeMobileGatewayUi();
  $("#create-user-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/admin/users", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      form.reset();
      $("#create-user-dialog").close();
      await loadUsers({ force: true });
    } catch (error) {
      showMessage(form.querySelector(".result"), error.message, "error");
    }
  });

  $("#edit-user-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await api(`/api/admin/users/${data.id}`, { method: "PUT", body: JSON.stringify({ full_name: data.full_name, role: data.role, is_active: form.is_active.checked }) });
      if (data.password) await api(`/api/admin/users/${data.id}/reset-password`, { method: "POST", body: JSON.stringify({ password: data.password }) });
      const feature_codes = [...$("#permission-tree").querySelectorAll("input:checked")].map((input) => input.value);
      await api(`/api/admin/users/${data.id}/permissions`, { method: "PUT", body: JSON.stringify({ feature_codes }) });
      $("#edit-user-dialog").close();
      await loadUsers({ force: true });
    } catch (error) {
      showMessage(form.querySelector(".result"), error.message, "error");
    }
  });

  $("#refresh-audit")?.addEventListener("click", () => loadAudit({ force: true }));
  $("#mobile-refresh")?.addEventListener("click", () => loadMobileGateway({ force: true }));
  $("#mobile-create-pairing-code")?.addEventListener("click", createMobilePairingCode);
  document.querySelectorAll("[data-mobile-tab]").forEach((button) => button.addEventListener("click", () => activateMobileGatewayTab(button.dataset.mobileTab)));
  ["#mobile-sms-device-filter", "#mobile-sms-sender-filter", "#mobile-sms-query-filter", "#mobile-sms-date-from", "#mobile-sms-date-to", "#mobile-sms-sim-filter"].forEach((selector) => {
    $(selector)?.addEventListener("input", () => {
      mobileGatewaySmsPage = 1;
      loadMobileGatewaySms({ force: true });
    });
    $(selector)?.addEventListener("change", () => {
      mobileGatewaySmsPage = 1;
      loadMobileGatewaySms({ force: true });
    });
  });
  $("#mobile-sms-prev")?.addEventListener("click", () => {
    mobileGatewaySmsPage = Math.max(1, mobileGatewaySmsPage - 1);
    loadMobileGatewaySms({ force: true });
  });
  $("#mobile-sms-next")?.addEventListener("click", () => {
    if (!mobileGatewaySmsHasMore) return;
    mobileGatewaySmsPage += 1;
    loadMobileGatewaySms({ force: true });
  });
  $("#mobile-save-otp-filter")?.addEventListener("click", saveMobileOtpFilter);
  $("#mobile-refresh-otp")?.addEventListener("click", loadMobileOtpData);
  $("#mobile-otp-latest-table")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mobile-copy-otp]");
    if (button) copyMobileOtpFromButton(button);
  });
  $("#mobile-otp-latest-table")?.addEventListener("dblclick", (event) => {
    const code = event.target.closest("[data-mobile-otp-code]");
    if (code) selectElementText(code);
  });
  ["#mobile-notification-device-filter", "#mobile-notification-app-filter", "#mobile-notification-query-filter"].forEach((selector) => {
    $(selector)?.addEventListener("input", () => {
      mobileGatewayNotificationPage = 1;
      loadMobileNotifications({ force: true });
    });
    $(selector)?.addEventListener("change", () => {
      mobileGatewayNotificationPage = 1;
      loadMobileNotifications({ force: true });
    });
  });
  $("#mobile-notification-prev")?.addEventListener("click", () => {
    mobileGatewayNotificationPage = Math.max(1, mobileGatewayNotificationPage - 1);
    loadMobileNotifications({ force: true });
  });
  $("#mobile-notification-next")?.addEventListener("click", () => {
    if (!mobileGatewayNotificationHasMore) return;
    mobileGatewayNotificationPage += 1;
    loadMobileNotifications({ force: true });
  });
  ["#mobile-media-device-filter", "#mobile-media-type-filter"].forEach((selector) => {
    $(selector)?.addEventListener("change", () => loadMobileMedia());
  });
  $("#mobile-policy-device")?.addEventListener("change", loadMobilePolicy);
  $("#mobile-save-policy")?.addEventListener("click", saveMobilePolicy);
  $("#refresh-zalo-message-logs")?.addEventListener("click", loadZaloMessageLogs);
  $("#zalo-send-test-message")?.addEventListener("click", (event) => sendZaloTestMessage(event.currentTarget));
  $("#refresh-zalo-auto-messages")?.addEventListener("click", () => loadZaloAutoMessages({ force: true }));
  $("#add-zalo-auto-message")?.addEventListener("click", () => openZaloAutoMessage(""));
  $("#zalo-auto-message-form")?.addEventListener("submit", saveZaloAutoMessage);
  $("#save-zalo-auto-message-button")?.addEventListener("click", () => $("#zalo-auto-message-form")?.requestSubmit());
  $("#refresh-data-mining")?.addEventListener("click", () => loadDataMining({ force: true }));
  $("#add-data-mining-schedule")?.addEventListener("click", () => openDataMiningSchedule(""));
  $("#data-mining-form")?.addEventListener("submit", saveDataMiningSchedule);
  $("#save-data-mining-button")?.addEventListener("click", () => $("#data-mining-form")?.requestSubmit());
  $("#website-form")?.addEventListener("submit", saveWebsite);
  $("#region-form")?.addEventListener("submit", saveRegion);
  $("#role-form")?.addEventListener("submit", saveRole);
  $("#work-task-form")?.addEventListener("submit", saveWorkTask);
  $("#save-work-task-button")?.addEventListener("click", () => $("#work-task-form")?.requestSubmit());
  $("#connection-form")?.addEventListener("submit", saveConnection);
  $("#sql-report-form")?.addEventListener("submit", saveSqlReport);
  $("#add-inline-sql-report")?.addEventListener("click", addInlineSqlReport);
  $("#sql-report-search")?.addEventListener("input", renderSqlReports);
  $("#sql-report-picker")?.addEventListener("change", renderSqlReports);
  $("#add-inline-onebss-report")?.addEventListener("click", addInlineOneBssReport);
  $("#onebss-report-search")?.addEventListener("input", renderOneBssReports);
  $("#onebss-report-picker")?.addEventListener("change", renderOneBssReports);
  $("#onebss-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    oneBssPendingSessionId = "";
    resetOneBssOtpState();
    await runOneBssReport();
  });
  $("#toggle-onebss-param-edit")?.addEventListener("click", toggleOneBssRunParameterEditing);
  $("#clear-onebss-run-history")?.addEventListener("click", clearOneBssRunHistory);
  $("#onebss-run-report-select")?.addEventListener("change", () => {
    oneBssPendingSessionId = "";
    resetOneBssOtpState();
    oneBssRunParameterEditing = false;
    renderOneBssRunParameters();
  });
  $("#onebss-otp-input")?.addEventListener("input", async (event) => {
    const value = event.currentTarget.value.replace(/\D/g, "").slice(0, 8);
    event.currentTarget.value = value;
    clearOneBssManualOtpTimer();
    if (value.length >= 4 && oneBssPendingSessionId && !oneBssRunInProgress) {
      const delay = value.length >= 6 ? 250 : 900;
      oneBssManualOtpTimer = setTimeout(async () => {
        const currentValue = $("#onebss-otp-input")?.value || "";
        if (currentValue !== value || !oneBssPendingSessionId || oneBssRunInProgress) return;
        oneBssOtpManualSubmitStarted = true;
        stopOneBssOtpPolling();
        setOneBssOtpStatus("Dang dung OTP nhap tay de dang nhap...", "info");
        await runOneBssReport(value, { otpRequestId: oneBssPendingOtpRequestId, otpSource: "manual" });
      }, delay);
    }
  });
  $("#connection-search")?.addEventListener("input", renderConnectionsTable);
  $("#connection-picker")?.addEventListener("change", renderConnectionsTable);
  $("#create-menu")?.addEventListener("click", createMenu);
  $("#new-menu-name")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") createMenu();
  });
  $("#new-dashboard-page")?.addEventListener("click", createDashboardPage);
  $("#save-dashboard-layout")?.addEventListener("click", (event) => saveDashboardLayout(event.currentTarget));
  $("#refresh-dashboard-sql-reports")?.addEventListener("click", (event) => refreshDashboardSqlReports(event.currentTarget));
  $("#add-dashboard-tab")?.addEventListener("click", addDashboardTab);
  $("#dashboard-row-type") && ($("#dashboard-row-type").innerHTML = dashboardLayoutTypeOptions("2_columns"));
  $("#add-dashboard-row")?.addEventListener("click", () => addDashboardRow($("#dashboard-row-type")?.value || "2_columns"));
  $("#refresh-dashboard-preview")?.addEventListener("click", () => loadDashboardPreviewTab(dashboardBuilderActiveTabId, { force: true }));
  $("#dashboard-parent-code")?.addEventListener("change", () => {
    collectDashboardBuilderStateFromDom();
    renderDashboardPages();
  });
  $("#dashboard-layout-pages")?.addEventListener("click", handleDashboardPageAction);
  $("#dashboard-builder-tabs")?.addEventListener("click", handleDashboardBuilderTabClick);
  $("#dashboard-builder-tabs")?.addEventListener("dblclick", handleDashboardBuilderTabRename);
  $("#dashboard-builder-tabs")?.addEventListener("dragstart", handleDashboardTabDragStart);
  $("#dashboard-builder-tabs")?.addEventListener("dragover", handleDashboardTabDragOver);
  $("#dashboard-builder-tabs")?.addEventListener("drop", handleDashboardTabDrop);
  $("#dashboard-builder-tabs")?.addEventListener("dragend", handleDashboardTabDragEnd);
  $("#dashboard-preview-tabs")?.addEventListener("click", handleDashboardPreviewTabClick);
  $("#dashboard-preview-workspace")?.addEventListener("click", handleDashboardRuntimeAction);
  $("#dashboard-builder-workspace")?.addEventListener("click", handleDashboardWorkspaceClick);
  $("#dashboard-builder-workspace")?.addEventListener("change", handleDashboardWorkspaceChange);
  $("#dashboard-builder-workspace")?.addEventListener("input", handleDashboardWorkspaceInput);
  $("#dashboard-builder-workspace")?.addEventListener("dragstart", handleDashboardRowDragStart);
  $("#dashboard-builder-workspace")?.addEventListener("dragover", handleDashboardRowDragOver);
  $("#dashboard-builder-workspace")?.addEventListener("drop", handleDashboardRowDrop);
  $("#dashboard-builder-workspace")?.addEventListener("dragend", handleDashboardRowDragEnd);
  $("#dynamic-report-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    dynamicReportPage = 1;
    dynamicReportSearchActive = false;
    await loadDynamicReportData({ includeSearch: false });
  });
  $("#dynamic-report-search")?.addEventListener("input", () => {
    dynamicReportPage = 1;
  });
  $("#dynamic-report-search")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyDynamicReportSearch();
    }
  });
  $("#search-dynamic-report")?.addEventListener("click", applyDynamicReportSearch);
  $("#dynamic-report-page-size")?.addEventListener("change", async () => {
    dynamicReportPage = 1;
    if (dynamicReportLoaded) await loadDynamicReportData();
  });
  $("#export-dynamic-report")?.addEventListener("click", exportDynamicReport);
  $("#dynamic-report-export-results")?.addEventListener("click", handleDynamicReportExportAction);
  renderDynamicReportExportJobs();
  loadDynamicReportHistory({ silent: true }).catch(() => {});
  $("#dynamic-report-select")?.addEventListener("change", () => {
    clearDynamicReportCache();
    renderDynamicReportFilters();
  });
  $("#dynamic-report-prev")?.addEventListener("click", async () => {
    if (dynamicReportPage <= 1) return;
    dynamicReportPage -= 1;
    await loadDynamicReportData();
  });
  $("#dynamic-report-next")?.addEventListener("click", async () => {
    const pageSize = Number($("#dynamic-report-page-size")?.value || 20);
    if (dynamicReportPage * pageSize >= dynamicReportTotal) return;
    dynamicReportPage += 1;
    await loadDynamicReportData();
  });
  $("#user-search")?.addEventListener("input", renderUsersTable);
  $("#user-import-file")?.addEventListener("change", importUserFile);
  $("#save-bulk-permissions")?.addEventListener("click", saveBulkPermissions);
  $("#save-data-permissions")?.addEventListener("click", saveDataPermissions);
}

$("#dashboard-viewer-page")?.addEventListener("change", (event) => {
  if (event.currentTarget.value) openDashboardViewerLayout(event.currentTarget.value);
});
$("#dashboard-viewer-tabs")?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-viewer-tab]");
  if (button) switchDashboardViewerTab(button.dataset.viewerTab);
});
$("#dashboard-viewer-workspace")?.addEventListener("click", handleDashboardRuntimeAction);
$("#refresh-dashboard-viewer-tab")?.addEventListener("click", () => loadDashboardViewerTab(dashboardViewerActiveTabId, { force: true }));
$("#dashboard-theme-toggle")?.addEventListener("click", toggleDashboardRuntimeTheme);
$("#capture-dashboard-viewer")?.addEventListener("click", captureDashboardViewerPageImage);
$("#save-dashboard-capture-to-zalo")?.addEventListener("click", (event) => saveDashboardCaptureToZalo(event.currentTarget));
applyDashboardRuntimeTheme();

async function importUserFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const data = new FormData();
  data.append("file", file);
  try {
    const result = await api("/api/admin/users/import", { method: "POST", body: data });
    showMessage($("#users-message"), `Đã thêm ${result.created_count} người dùng, bỏ qua ${result.skipped_count} dòng.`);
    await loadUsers({ force: true });
  } catch (error) {
    showMessage($("#users-message"), error.message, "error");
  } finally {
    event.target.value = "";
  }
}

function selectedValues(containerSelector) {
  return [...document.querySelectorAll(`${containerSelector} input:checked`)].map((input) => input.value);
}

function selectedNumbers(containerSelector) {
  return selectedValues(containerSelector).map((value) => Number(value));
}

function renderUserSelection(selector) {
  const box = $(selector);
  box.innerHTML = users.map((user) => `
    <label class="selection-item">
      <input type="checkbox" value="${user.id}" />
      <span><strong>${escapeHtml(user.employee_code || user.username)}</strong><small>${escapeHtml(user.full_name)}</small></span>
    </label>
  `).join("");
}

async function loadCredentialWebsites({ force = false } = {}) {
  if (!force && isDataFresh("credentialWebsites")) {
    fillCredentialWebsiteOptions();
    return;
  }
  const data = await api("/api/websites");
  credentialWebsites = data.websites || [];
  markDataFresh("credentialWebsites");
  fillCredentialWebsiteOptions();
}

async function loadCredentials({ force = false } = {}) {
  if (!force && isDataFresh("credentials")) {
    renderCredentialsTable();
    return;
  }
  if (credentials.length && !force) {
    renderCredentialsTable();
  }
  if (!credentials.length || force) setTableLoading("#credentials-table", 5, "Đang tải tài khoản website...");
  const [credentialData] = await Promise.all([
    api("/api/credentials"),
    canManageVault ? loadCredentialWebsites({ force: false }) : Promise.resolve(),
  ]);
  credentials = credentialData.credentials || [];
  markDataFresh("credentials");
  renderCredentialsTable();
}

function renderCredentialsTable() {
  const table = $("#credentials-table");
  if (!table) return;
  table.innerHTML = credentials.length ? credentials.map((credential) => {
    const actions = [];
    if (canManageVault) actions.push(`<button class="table-action" data-edit-credential="${escapeHtml(credential.id)}" type="button">Sửa</button>`);
    if (canRevealVault) actions.push(`<button class="table-action" data-reveal-credential="${escapeHtml(credential.id)}" type="button">Xem mật khẩu</button>`);
    if (canManageVault) actions.push(`<button class="table-action danger" data-delete-credential="${escapeHtml(credential.id)}" type="button">Xóa</button>`);
    return `
      <tr>
        <td class="table-action-cell"><div class="action-group">${actions.join("") || "<span class=\"status viewer\">Xem</span>"}</div></td>
        <td><strong>${escapeHtml(credential.website_name || "")}</strong></td>
        <td><a class="text-sky-200 hover:underline" href="${escapeHtml(credential.url || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(credential.url || "-")}</a></td>
        <td>${escapeHtml(credential.login_username || "")}${credential.notes ? `<small class="cell-note">${escapeHtml(credential.notes)}</small>` : ""}</td>
        <td><span class="status ${Number(credential.requires_otp) ? "pending" : "viewer"}">${Number(credential.requires_otp) ? "Có OTP" : "Không"}</span></td>
      </tr>
    `;
  }).join("") : emptyRow(5, "Chưa có tài khoản website", "Bấm Thêm tài khoản để lưu tài khoản dùng cho công việc.");
  document.querySelectorAll("[data-edit-credential]").forEach((button) => {
    button.addEventListener("click", () => openCredential(Number(button.dataset.editCredential)).catch((error) => showToast(error.message, "error")));
  });
  document.querySelectorAll("[data-reveal-credential]").forEach((button) => {
    button.addEventListener("click", () => revealCredential(Number(button.dataset.revealCredential)));
  });
  document.querySelectorAll("[data-delete-credential]").forEach((button) => {
    button.addEventListener("click", () => deleteCredential(Number(button.dataset.deleteCredential)));
  });
}

function fillCredentialWebsiteOptions() {
  const select = $("#credential-website");
  if (!select) return;
  const current = select.value;
  select.innerHTML = credentialWebsites.length
    ? credentialWebsites.map((website) => `<option value="${escapeHtml(website.id)}">${escapeHtml(website.name)} (${escapeHtml(website.url)})</option>`).join("")
    : `<option value="">Chưa có website</option>`;
  if (current && credentialWebsites.some((website) => String(website.id) === String(current))) select.value = current;
  updateCredentialWebsiteInfo();
}

function updateCredentialWebsiteInfo() {
  const select = $("#credential-website");
  const url = $("#credential-url");
  const otp = $("#credential-otp");
  const website = credentialWebsites.find((item) => String(item.id) === String(select?.value || ""));
  if (url) url.value = website?.url || "";
  if (otp) otp.textContent = website ? (Number(website.requires_otp) ? "Website này có OTP." : "Website này không yêu cầu OTP.") : "Chọn website để xem thông tin OTP.";
}

async function openCredential(id = "") {
  if (canManageVault) await loadCredentialWebsites();
  const credential = credentials.find((item) => Number(item.id) === Number(id));
  const form = $("#credential-form");
  if (!form) return;
  form.reset();
  form.elements.namedItem("id").value = credential?.id || "";
  form.elements.namedItem("website_id").value = credential?.website_id || credentialWebsites[0]?.id || "";
  form.elements.namedItem("login_username").value = credential?.login_username || "";
  form.elements.namedItem("password").value = "";
  form.elements.namedItem("notes").value = credential?.notes || "";
  form.querySelector(".result").className = "result hidden";
  updateCredentialWebsiteInfo();
  $("#credential-dialog")?.showModal();
}

async function saveCredential(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/credentials", { method: "POST", body: JSON.stringify({
      id: data.id ? Number(data.id) : null,
      website_id: Number(data.website_id),
      login_username: data.login_username,
      password: data.password,
      notes: data.notes || "",
    })});
    $("#credential-dialog")?.close();
    showToast("Đã lưu tài khoản website.");
    await loadCredentials({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function revealCredential(id) {
  try {
    const response = await api(`/api/credentials/${id}/reveal`, { method: "POST" });
    window.prompt("Mật khẩu", response.password || "");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function deleteCredential(id) {
  if (!confirm("Xóa tài khoản website này?")) return;
  try {
    await api(`/api/credentials/${id}`, { method: "DELETE" });
    showToast("Đã xóa tài khoản website.");
    await loadCredentials({ force: true });
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function loadAdminWebsites({ force = false } = {}) {
  if (!force && isDataFresh("websites")) {
    renderWebsitesTable();
    return;
  }
  if (websites.length && !force) {
    renderWebsitesTable();
  }
  if (!websites.length || force) setTableLoading("#websites-table", 5, "Đang tải danh mục website...");
  websites = (await api("/api/admin/websites")).websites;
  markDataFresh("websites");
  renderWebsitesTable();
}

function renderWebsitesTable() {
  const table = $("#websites-table");
  if (!table) return;
  table.innerHTML = websites.length ? websites.map((website) => `
    <tr>
      <td class="table-action-cell"><button class="table-action" data-edit-website="${website.id}" type="button">Sửa</button></td>
      <td><strong>${escapeHtml(website.name)}</strong></td>
      <td><a class="text-sky-200 hover:underline" href="${escapeHtml(website.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(website.url)}</a></td>
      <td><span class="status ${website.requires_otp ? "pending" : "viewer"}">${website.requires_otp ? "Có OTP" : "Không"}</span></td>
      <td><span class="status ${website.is_active ? "active" : "inactive"}">${website.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
    </tr>
  `).join("") : emptyRow(5, "Chưa có website", "Bấm Thêm website để tạo danh mục dùng chung.");
  document.querySelectorAll("[data-edit-website]").forEach((button) => {
    button.addEventListener("click", () => openWebsite(Number(button.dataset.editWebsite)));
  });
}

function openWebsite(id = "") {
  const website = websites.find((item) => Number(item.id) === Number(id));
  const form = $("#website-form");
  if (!form) return;
  form.reset();
  form.elements.namedItem("id").value = website?.id || "";
  form.elements.namedItem("name").value = website?.name || "";
  form.elements.namedItem("url").value = website?.url || "";
  form.elements.namedItem("requires_otp").checked = website ? Boolean(website.requires_otp) : false;
  form.elements.namedItem("is_active").checked = website ? Boolean(website.is_active) : true;
  form.querySelector(".result").className = "result hidden";
  $("#website-dialog")?.showModal();
}

async function saveWebsite(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/admin/websites", { method: "POST", body: JSON.stringify({
      id: data.id ? Number(data.id) : null,
      name: data.name,
      url: data.url,
      requires_otp: form.requires_otp.checked,
      is_active: form.is_active.checked,
    })});
    $("#website-dialog")?.close();
    showToast("Đã lưu danh mục website.");
    markDataStale("credentialWebsites");
    await loadAdminWebsites({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function loadPermissionManager() {
  if (!isDataFresh("users")) {
    users = (await api("/api/admin/users")).users;
    markDataFresh("users");
  }
  if (!isDataFresh("features")) {
    features = (await api("/api/admin/features")).features;
    markDataFresh("features");
  }
  renderUserSelection("#permission-users");
  const orderedFeatures = flattenFeatureTree(buildFeatureTree(features)).map((row) => row.feature);
  $("#permission-features").innerHTML = orderedFeatures.map((feature) => `
    <label class="permission-item ${feature.parent_code ? "child" : "parent"}">
      <input type="checkbox" value="${escapeHtml(feature.code)}" />
      <span>${escapeHtml(feature.name)}</span>
    </label>`).join("");
  bindPermissionCascade("#permission-features");
}

async function saveBulkPermissions() {
  const user_ids = selectedNumbers("#permission-users");
  const feature_codes = selectedValues("#permission-features");
  await api("/api/admin/permissions/bulk", { method: "PUT", body: JSON.stringify({ user_ids, feature_codes }) });
  alert("Đã lưu phân quyền người dùng.");
}

async function loadDataPermissionManager() {
  if (!isDataFresh("users")) {
    users = (await api("/api/admin/users")).users;
    markDataFresh("users");
  }
  renderUserSelection("#data-permission-users");
  if (!regions.length || !isDataFresh("regions")) {
    regions = (await api("/api/admin/regions")).regions;
    markDataFresh("regions");
  }
  $("#data-region-options").innerHTML = regions.map((region) => `
    <label class="selection-item">
      <input type="checkbox" value="${escapeHtml(region.code)}" />
      <span><strong>${escapeHtml(region.code)}</strong><small>${escapeHtml(region.name)}</small></span>
    </label>`).join("");
}

async function saveDataPermissions() {
  const user_ids = selectedNumbers("#data-permission-users");
  const region_codes = selectedValues("#data-region-options");
  await api("/api/admin/data-permissions/bulk", { method: "PUT", body: JSON.stringify({ user_ids, region_codes }) });
  alert("Đã lưu phân quyền dữ liệu.");
}

async function loadRoles({ force = false } = {}) {
  if (!force && isDataFresh("roles")) {
    renderRolesTable();
    return;
  }
  if (systemRoles.length && !force) {
    renderRolesTable();
  }
  if (!systemRoles.length || force) setTableLoading("#roles-table", 6, "Đang tải vai trò người dùng...");
  systemRoles = (await api("/api/admin/roles")).roles;
  markDataFresh("roles");
  renderRolesTable();
}

function renderRolesTable() {
  $("#roles-table").innerHTML = systemRoles.length ? systemRoles.map((roleItem) => `
    <tr>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-role="${escapeHtml(roleItem.code)}">Sửa</button> <button class="table-action danger" data-delete-role="${escapeHtml(roleItem.code)}">Xóa</button></div></td>
      <td><strong>${escapeHtml(roleItem.code)}</strong></td>
      <td>${escapeHtml(roleItem.name)}</td>
      <td>${escapeHtml(roleItem.description || "")}</td>
      <td><span class="status ${roleItem.is_active ? "active" : "inactive"}">${roleItem.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
      <td>${escapeHtml(roleItem.sort_order)}</td>
    </tr>
  `).join("") : emptyRow(6, "Chưa có vai trò", "Thêm vai trò để chuẩn hóa nhóm người dùng.");
  document.querySelectorAll("[data-edit-role]").forEach((button) => button.addEventListener("click", () => openRole(button.dataset.editRole)));
  document.querySelectorAll("[data-delete-role]").forEach((button) => button.addEventListener("click", () => deleteRole(button.dataset.deleteRole)));
}

async function loadCatalogs({ force = false } = {}) {
  await Promise.all([loadRegions({ force }), loadRoles({ force })]);
}

function openRole(code = "") {
  const roleItem = systemRoles.find((item) => item.code === code);
  const form = $("#role-form");
  form.elements.namedItem("code").value = roleItem?.code || "";
  form.elements.namedItem("code").readOnly = Boolean(roleItem);
  form.elements.namedItem("name").value = roleItem?.name || "";
  form.elements.namedItem("description").value = roleItem?.description || "";
  form.elements.namedItem("sort_order").value = roleItem?.sort_order ?? 0;
  form.elements.namedItem("is_active").checked = roleItem ? Boolean(roleItem.is_active) : true;
  form.querySelector(".result").className = "result hidden";
  $("#role-dialog").showModal();
}

async function saveRole(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/admin/roles", { method: "POST", body: JSON.stringify({
      code: data.code,
      name: data.name,
      description: data.description || "",
      sort_order: Number(data.sort_order || 0),
      is_active: form.is_active.checked,
    })});
    form.reset();
    form.elements.namedItem("code").readOnly = false;
    form.is_active.checked = true;
    $("#role-dialog").close();
    showMessage($("#roles-message"), "Đã lưu vai trò.");
    await loadRoles({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteRole(code) {
  if (!confirm(`Xóa vai trò ${code}?`)) return;
  try {
    await api(`/api/admin/roles/${encodeURIComponent(code)}`, { method: "DELETE" });
    showMessage($("#roles-message"), `Đã xóa vai trò ${code}.`);
    await loadRoles({ force: true });
  } catch (error) {
    showMessage($("#roles-message"), error.message, "error");
  }
}

function featureSortValue(feature) {
  return Number(feature.sort_order ?? 0);
}

function sortFeaturesForTree(items) {
  return [...items].sort((left, right) => (
    featureSortValue(left) - featureSortValue(right)
    || String(left.name || "").localeCompare(String(right.name || ""), "vi")
    || String(left.code).localeCompare(String(right.code))
  ));
}

function buildFeatureTree(sourceFeatures) {
  const nodes = new Map(sourceFeatures.map((feature) => [feature.code, { feature, children: [] }]));
  const roots = [];
  nodes.forEach((node) => {
    const parent = node.feature.parent_code ? nodes.get(node.feature.parent_code) : null;
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  });
  const sortNodes = (items) => {
    items.sort((left, right) => (
      featureSortValue(left.feature) - featureSortValue(right.feature)
      || String(left.feature.name || "").localeCompare(String(right.feature.name || ""), "vi")
      || String(left.feature.code).localeCompare(String(right.feature.code))
    ));
    items.forEach((item) => sortNodes(item.children));
    return items;
  };
  return sortNodes(roots);
}

function flattenFeatureTree(nodes, level = 0, rows = []) {
  nodes.forEach((node) => {
    rows.push({ feature: node.feature, level });
    flattenFeatureTree(node.children, level + 1, rows);
  });
  return rows;
}

function descendantFeatureCodes(sourceFeatures, parentCode) {
  const childrenByParent = new Map();
  (sourceFeatures || []).forEach((feature) => {
    const parent = feature.parent_code || "";
    if (!parent) return;
    if (!childrenByParent.has(parent)) childrenByParent.set(parent, []);
    childrenByParent.get(parent).push(feature.code);
  });
  const result = [];
  const visit = (code) => {
    (childrenByParent.get(code) || []).forEach((childCode) => {
      result.push(childCode);
      visit(childCode);
    });
  };
  visit(parentCode);
  return result;
}

function bindPermissionCascade(containerSelector) {
  const container = $(containerSelector);
  if (!container) return;
  container.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      descendantFeatureCodes(features, checkbox.value).forEach((code) => {
        const child = [...container.querySelectorAll("input[type='checkbox']")].find((input) => input.value === code);
        if (child) child.checked = checkbox.checked;
      });
    });
  });
}

const dashboardParentExcludedFeatureCodes = new Set(["dashboard", "quanlycongviec", "truyvansql", "reports", "new_reports"]);

function dashboardParentMenuCandidates(sourceFeatures = features) {
  return sortFeaturesForTree((sourceFeatures || []).filter((feature) => {
    const code = String(feature?.code || "");
    if (!code || feature.parent_code || dashboardParentExcludedFeatureCodes.has(code)) return false;
    if (navFeatureConfig[code]?.view) return false;
    return true;
  }));
}

function dashboardDefaultParentCode() {
  const candidates = dashboardParentMenuCandidates();
  return candidates.find((feature) => feature.code === "baocaomoi")?.code || candidates[0]?.code || "baocaomoi";
}

function dashboardParentMenuLabel(code) {
  const feature = (features || []).find((item) => item.code === code);
  if (feature?.name) return feature.name;
  if (code === "baocaomoi") return "B\u00e1o c\u00e1o m\u1edbi";
  if (code === "quantriweb") return "Qu\u1ea3n tr\u1ecb web";
  return code || "B\u00e1o c\u00e1o m\u1edbi";
}

function dashboardParentMenuOptions(selectedCode = "") {
  const selected = selectedCode || dashboardDefaultParentCode();
  const candidates = dashboardParentMenuCandidates();
  const options = candidates.length ? candidates : [{ code: "baocaomoi", name: "B\u00e1o c\u00e1o m\u1edbi" }];
  if (selected && !options.some((feature) => feature.code === selected)) {
    options.push({ code: selected, name: dashboardParentMenuLabel(selected) });
  }
  return options.map((feature) => {
    const selectedAttr = feature.code === selected ? " selected" : "";
    return `<option value="${escapeHtml(feature.code)}"${selectedAttr}>${escapeHtml(feature.name || feature.code)}</option>`;
  }).join("");
}

function featureIcon(feature) {
  return featureNavigationConfig(feature)?.icon || navGroupIcons[feature.code] || "list";
}

function dashboardRuntimeErrorSummary(response) {
  const failedWidgets = Array.isArray(response?.failed_widgets) ? response.failed_widgets : [];
  if (!failedWidgets.length) return response?.message || "Một số biểu đồ chưa tải được dữ liệu.";
  const details = failedWidgets.slice(0, 3).map((item) => {
    const label = item.title || item.sql_code || `Ô ${item.row_id || "?"}.${item.position || "?"}`;
    const error = item.message || item.details?.error || "Không rõ lỗi.";
    return `${label}: ${error}`;
  }).join(" | ");
  return `${response?.message || "Một số biểu đồ chưa tải được dữ liệu."} ${details}`;
}

function iconMarkup(icon) {
  return `<svg class="nav-svg"><use href="#icon-${escapeHtml(icon)}"></use></svg>`;
}

function dashboardPageIdFromFeatureCode(code) {
  if (code === "dashboard") return "DASHBOARD_KINH_DOANH";
  const mappedPageId = dashboardPageIdByFeatureCode.get(code);
  if (mappedPageId) return mappedPageId;
  return String(code || "")
    .replace(/[^A-Za-z0-9]+/g, "")
    .toUpperCase() || "DASHBOARD_KINH_DOANH";
}

function dashboardFeatureCodeForPageId(pageId) {
  const compact = String(pageId || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
  if (compact === "dashboardkinhdoanh") return "dashboard";
  if (compact === "reports") return "truyvansql";
  return compact || "dashboard";
}

function featureNavigationConfig(feature) {
  if (navGroupOnlyFeatureCodes.has(feature.code)) return null;
  const staticConfig = navFeatureConfig[feature.code];
  if (staticConfig) return staticConfig;
  const dashboardPageId = dashboardPageIdFromFeatureCode(feature.code);
  if (feature.parent_code === "truyvansql" || feature.parent_code === "reports" || dashboardFeatureCodes.has(feature.code)) {
    return {
      view: "dashboard",
      icon: "chart",
      keywords: `dashboard bao cao thong ke ${feature.name || ""} ${feature.code || ""}`,
      dashboardPageId,
    };
  }
  return null;
}

function navNodeHasVisibleItem(node) {
  if (navGroupOnlyFeatureCodes.has(node.feature.code)) return true;
  if (featureNavigationConfig(node.feature)?.view) return true;
  return node.children.some((child) => navNodeHasVisibleItem(child));
}

function renderNavigationButton(feature, level) {
  const config = featureNavigationConfig(feature);
  if (!config?.view) return "";
  const classes = ["nav-item"];
  if (level > 0) classes.push("child");
  if (level > 1) classes.push("subchild");
  const title = feature.name || feature.code;
  const keywords = `${config.keywords || ""} ${feature.name || ""} ${feature.code}`;
  const dashboardPageAttr = config.dashboardPageId ? ` data-dashboard-page-id="${escapeHtml(config.dashboardPageId)}"` : "";
  return `
    <button class="${classes.join(" ")}" data-feature-code="${escapeHtml(feature.code)}" data-view="${escapeHtml(config.view)}" data-title="${escapeHtml(title)}" data-keywords="${escapeHtml(keywords)}"${dashboardPageAttr}>
      ${iconMarkup(config.icon || "list")}<span>${escapeHtml(title)}</span>
    </button>
  `;
}

function renderNavigationNode(node, level = 0) {
  const visibleChildren = node.children.filter((child) => navNodeHasVisibleItem(child));
  if (!visibleChildren.length && navGroupOnlyFeatureCodes.has(node.feature.code)) {
    const groupClass = `nav-group${level > 0 ? " nav-subgroup" : ""}`;
    return `
      <details class="${groupClass}">
        <summary data-feature-code="${escapeHtml(node.feature.code)}">
          <span class="chevron">›</span>${iconMarkup(featureIcon(node.feature))}<strong>${escapeHtml(node.feature.name || node.feature.code)}</strong>
        </summary>
      </details>
    `;
  }
  if (!visibleChildren.length) return renderNavigationButton(node.feature, level);
  const groupClass = `nav-group${level > 0 ? " nav-subgroup" : ""}`;
  const children = visibleChildren.map((child) => renderNavigationNode(child, level + 1)).join("");
  return `
    <details class="${groupClass}">
      <summary data-feature-code="${escapeHtml(node.feature.code)}">
        <span class="chevron">›</span>${iconMarkup(featureIcon(node.feature))}<strong>${escapeHtml(node.feature.name || node.feature.code)}</strong>
      </summary>
      ${children}
    </details>
  `;
}

function findNavItemByFeatureCode(code) {
  return [...document.querySelectorAll("#nav-tree .nav-item[data-feature-code]")].find((item) => item.dataset.featureCode === code);
}

function findFirstNavItemUnderFeatureCode(code) {
  const summary = [...document.querySelectorAll("#nav-tree summary[data-feature-code]")].find((item) => item.dataset.featureCode === code);
  return summary?.closest(".nav-group")?.querySelector(".nav-item[data-view]") || null;
}

function preferredNavItem(activeCode) {
  const routeCode = featureCodeFromCurrentPath();
  const preferredCode = routeCode || activeCode;
  if (!preferredCode || preferredCode === "dashboard") {
    return findFirstNavItemUnderFeatureCode("dashboard") || document.querySelector("#nav-tree .nav-item[data-view]");
  }
  return (
    findNavItemByFeatureCode(preferredCode)
    || findFirstNavItemUnderFeatureCode(preferredCode)
    || findFirstNavItemUnderFeatureCode("dashboard")
    || document.querySelector("#nav-tree .nav-item[data-view]")
  );
}

function openNavParents(item) {
  let parent = item.parentElement;
  while (parent) {
    if (parent.matches?.(".nav-group")) parent.open = true;
    parent = parent.parentElement;
  }
}

async function syncNavigationFromFeatures() {
  try {
    try {
      const navigationData = await api("/api/navigation");
      features = navigationData.features || [];
      markDataFresh("features");
      applyDashboardLayoutList(navigationData.dashboard_layouts || []);
    } catch {
      features = (await api("/api/admin/features")).features;
      markDataFresh("features");
      try {
        const layoutsData = await api("/api/admin/dashboard-layouts");
        applyDashboardLayoutList(layoutsData.layouts || []);
      } catch {
        applyDashboardLayoutList([]);
      }
    }
    const tree = $("#nav-tree");
    if (!tree) return;
    const activeCode = tree.querySelector(".nav-item.active")?.dataset.featureCode || "dashboard";
    const html = buildFeatureTree(features)
      .filter((node) => navNodeHasVisibleItem(node))
      .map((node) => renderNavigationNode(node))
      .join("");
    if (html.trim()) tree.innerHTML = html;
    const activeItem = preferredNavItem(activeCode);
    if (activeItem) {
      await activateNavItem(activeItem, { updateUrl: !featureCodeFromCurrentPath(), replaceUrl: true });
    }
    filterNavigation($("#menu-search")?.value || "");
  } catch {
    // Nếu API layout chưa sẵn sàng, sidebar vẫn dùng cấu trúc tĩnh đã render từ server.
  }
}

async function activateNavForCurrentPath() {
  const routeCode = featureCodeFromCurrentPath();
  if (!routeCode && window.location.pathname !== "/") return false;
  const item = preferredNavItem(routeCode || "dashboard");
  if (!item) return false;
  openNavParents(item);
  await activateNavItem(item, { updateUrl: false });
  return true;
}

function collectMenuLayoutStateFromDom() {
  const rows = [...document.querySelectorAll("#menu-layout-table tr[data-feature-row]")];
  if (!rows.length) return;
  const currentByCode = new Map(menuLayoutState.map((feature) => [feature.code, feature]));
  menuLayoutState = rows.map((row) => {
    const code = row.dataset.featureRow;
    const existing = currentByCode.get(code) || {};
    return {
      ...existing,
      code,
      name: row.querySelector("[name='name']")?.value.trim() || code,
      parent_code: row.querySelector("[name='parent_code']")?.value || null,
      sort_order: Number(existing.sort_order || 0),
    };
  });
}

function normalizeMenuSiblingOrders(parentCode = null) {
  sortFeaturesForTree(menuLayoutState.filter((feature) => (feature.parent_code || null) === (parentCode || null)))
    .forEach((feature, index) => {
      feature.sort_order = (index + 1) * 10;
    });
}

function normalizeAllMenuOrders() {
  const parents = new Set(menuLayoutState.map((feature) => feature.parent_code || null));
  parents.add(null);
  parents.forEach((parentCode) => normalizeMenuSiblingOrders(parentCode));
}

function descendantCodesForFeature(code) {
  const childrenByParent = new Map();
  menuLayoutState.forEach((feature) => {
    if (!feature.parent_code) return;
    if (!childrenByParent.has(feature.parent_code)) childrenByParent.set(feature.parent_code, []);
    childrenByParent.get(feature.parent_code).push(feature.code);
  });
  const descendants = new Set();
  const stack = [...(childrenByParent.get(code) || [])];
  while (stack.length) {
    const childCode = stack.pop();
    if (descendants.has(childCode)) continue;
    descendants.add(childCode);
    stack.push(...(childrenByParent.get(childCode) || []));
  }
  return descendants;
}

function renderParentOptions(feature) {
  const descendants = descendantCodesForFeature(feature.code);
  return [`<option value="">Không thuộc nhóm</option>`]
    .concat(sortFeaturesForTree(menuLayoutState).filter((item) => item.code !== feature.code).map((item) => {
      const selected = (feature.parent_code || "") === item.code ? " selected" : "";
      const disabled = descendants.has(item.code) ? " disabled" : "";
      return `<option value="${escapeHtml(item.code)}"${selected}${disabled}>${escapeHtml(item.name)} (${escapeHtml(item.code)})</option>`;
    }))
    .join("");
}

function renderMenuLayout() {
  const table = $("#menu-layout-table");
  if (!table) return;
  const rows = flattenFeatureTree(buildFeatureTree(menuLayoutState));
  table.innerHTML = rows.length ? rows.map(({ feature, level }) => {
    const siblings = sortFeaturesForTree(menuLayoutState.filter((item) => (item.parent_code || null) === (feature.parent_code || null)));
    const siblingIndex = siblings.findIndex((item) => item.code === feature.code);
    return `
      <tr data-feature-row="${escapeHtml(feature.code)}">
        <td class="table-action-cell">
          <div class="action-group menu-move-actions">
            <button class="table-action" data-menu-move="up" data-menu-code="${escapeHtml(feature.code)}" type="button" ${siblingIndex <= 0 ? "disabled" : ""}>Lên</button>
            <button class="table-action" data-menu-move="down" data-menu-code="${escapeHtml(feature.code)}" type="button" ${siblingIndex >= siblings.length - 1 ? "disabled" : ""}>Xuống</button>
          </div>
        </td>
        <td><div class="menu-feature-cell" style="--menu-level:${level}"><strong>${escapeHtml(feature.code)}</strong><small>Cấp ${level + 1}</small></div></td>
        <td><input class="form-control" name="name" value="${escapeHtml(feature.name)}" /></td>
        <td><select class="form-control" name="parent_code">${renderParentOptions(feature)}</select></td>
      </tr>
    `;
  }).join("") : emptyRow(4, "Chưa có chức năng", "Danh mục chức năng chưa có dữ liệu.");

  document.querySelectorAll("#menu-layout-table select[name='parent_code']").forEach((select) => {
    select.addEventListener("change", () => changeMenuParent(select.closest("tr").dataset.featureRow, select.value));
  });
}

function changeMenuParent(code, parentCode) {
  collectMenuLayoutStateFromDom();
  const item = menuLayoutState.find((feature) => feature.code === code);
  if (!item) return;
  item.parent_code = parentCode || null;
  const siblingOrders = menuLayoutState
    .filter((feature) => feature.code !== code && (feature.parent_code || null) === (item.parent_code || null))
    .map((feature) => featureSortValue(feature));
  item.sort_order = (Math.max(0, ...siblingOrders) || 0) + 10;
  normalizeMenuSiblingOrders(item.parent_code);
  renderMenuLayout();
}

function moveMenuItem(code, direction) {
  collectMenuLayoutStateFromDom();
  const item = menuLayoutState.find((feature) => feature.code === code);
  if (!item) return;
  const siblings = sortFeaturesForTree(menuLayoutState.filter((feature) => (feature.parent_code || null) === (item.parent_code || null)));
  const index = siblings.findIndex((feature) => feature.code === code);
  const targetIndex = direction === "up" ? index - 1 : index + 1;
  if (index < 0 || targetIndex < 0 || targetIndex >= siblings.length) return;
  const [moved] = siblings.splice(index, 1);
  siblings.splice(targetIndex, 0, moved);
  siblings.forEach((feature, siblingIndex) => {
    feature.sort_order = (siblingIndex + 1) * 10;
  });
  renderMenuLayout();
}

async function createMenu() {
  const menuNameInput = $("#new-menu-name");
  const cleanedName = menuNameInput?.value.trim() || "";
  if (!cleanedName) {
    showMessage($("#menu-layout-message"), "Nh\u1eadp t\u00ean menu tr\u01b0\u1edbc khi t\u1ea1o.", "error");
    menuNameInput?.focus();
    return;
  }
  const button = $("#create-menu");
  if (button) button.disabled = true;
  try {
    await api("/api/admin/features/menu", { method: "POST", body: JSON.stringify({ name: cleanedName }) });
    if (menuNameInput) menuNameInput.value = "";
    await loadMenuLayout();
    showMessage($("#menu-layout-message"), "\u0110\u00e3 t\u1ea1o menu. B\u1ea5m L\u01b0u c\u1ea5u tr\u00fac menu \u0111\u1ec3 ch\u1ed1t c\u00e2y menu.");
  } catch (error) {
    showMessage($("#menu-layout-message"), error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

async function loadMenuLayout() {
  features = (await api("/api/admin/features")).features;
  markDataFresh("features");
  menuLayoutState = features.map((feature) => ({ ...feature }));
  renderMenuLayout();
}

async function saveMenuLayout(button = null) {
  const saveButton = button || $("#save-menu-layout");
  const originalLabel = saveButton?.textContent;
  if (saveButton) {
    saveButton.disabled = true;
    saveButton.textContent = "Đang lưu...";
  }
  try {
    collectMenuLayoutStateFromDom();
    if (!menuLayoutState.length) {
      await loadMenuLayout();
      collectMenuLayoutStateFromDom();
    }
    normalizeAllMenuOrders();
    const payload = menuLayoutState.map((feature) => ({
      code: feature.code,
      name: feature.name,
      parent_code: feature.parent_code || null,
      sort_order: Number(feature.sort_order || 0),
    }));
    await api("/api/admin/features/layout", { method: "PUT", body: JSON.stringify({ features: payload }) });
    showMessage($("#menu-layout-message"), "Đã lưu cấu trúc menu. Trang sẽ tải lại để hiển thị cây menu mới.");
    window.setTimeout(() => window.location.reload(), 600);
  } catch (error) {
    showMessage($("#menu-layout-message"), error.message, "error");
    if (saveButton) {
      saveButton.disabled = false;
      saveButton.textContent = originalLabel || "Lưu cấu trúc menu";
    }
  }
}

function dashboardLayoutTemplate(pageName = "Dashboard Kinh doanh", pageId = "DASHBOARD_KINH_DOANH", options = {}) {
  return {
    page_id: pageId,
    page_name: repairTextEncoding(pageName),
    parent_code: options.parentCode || dashboardDefaultParentCode(),
    tabs: [
      {
        tab_id: `tab_${Date.now()}`,
        tab_name: "Tab mới",
        order: 1,
        grid_layout: options.empty ? [] : [
          { row_id: 1, layout_type: "2_columns", widgets: [] },
        ],
      },
    ],
  };
}

function normalizeDashboardLayoutData(layout, pageName = "") {
  return {
    page_id: String(layout?.page_id || "DASHBOARD_KINH_DOANH").trim().toUpperCase(),
    page_name: repairTextEncoding(pageName || layout?.page_name || String(layout?.page_id || "Dashboard Kinh doanh")),
    parent_code: String(layout?.parent_code || layout?.parentCode || "").trim() || dashboardDefaultParentCode(),
    tabs: Array.isArray(layout?.tabs) ? layout.tabs.map((tab, index) => ({
      tab_id: String(tab.tab_id || `tab_${Date.now()}_${index}`).trim(),
      tab_name: repairTextEncoding(String(tab.tab_name || `Tab ${index + 1}`).trim()),
      order: index + 1,
      grid_layout: Array.isArray(tab.grid_layout) ? tab.grid_layout.map((row, rowIndex) => ({
        row_id: Number(row.row_id || rowIndex + 1),
        layout_type: dashboardLayoutColumns[row.layout_type] ? row.layout_type : "2_columns",
        widgets: Array.isArray(row.widgets) ? row.widgets.map((widget) => ({
          position: Number(widget.position || 1),
          type: String(widget.type || "bar_chart"),
          title: repairTextEncoding(String(widget.title || "")),
          sql_code: String(widget.sql_code || "").trim().toUpperCase(),
          report_id: widget.report_id ?? null,
          filters: widget.filters && typeof widget.filters === "object" && !Array.isArray(widget.filters) ? widget.filters : {},
          chart_config: widget.chart_config && typeof widget.chart_config === "object" && !Array.isArray(widget.chart_config) ? widget.chart_config : {},
          text_content: repairTextEncoding(String(widget.text_content || "")),
          icon_url: String(widget.icon_url || ""),
        })).filter((widget) => widget.sql_code || dashboardNonSqlWidgetTypes.has(widget.type)) : [],
      })) : [],
    })) : [],
  };
}

function normalizeDashboardBuilderLayout(layout, pageName = "") {
  const normalized = normalizeDashboardLayoutData(layout, pageName);
  if (!normalized.tabs.length) normalized.tabs = dashboardLayoutTemplate(normalized.page_name, normalized.page_id).tabs;
  if (!normalized.tabs.some((tab) => tab.tab_id === dashboardBuilderActiveTabId)) {
    dashboardBuilderActiveTabId = normalized.tabs[0]?.tab_id || "";
  }
  return normalized;
}

function dashboardPageIdFromName(pageName) {
  const generatedId = String(pageName || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || `DASHBOARD_${Date.now()}`;
  return generatedId.startsWith("DASHBOARD_") ? generatedId : `DASHBOARD_${generatedId}`;
}

function normalizeDashboardViewerLayout(layout, pageName = "") {
  const normalized = normalizeDashboardLayoutData(layout, pageName);
  if (!normalized.tabs.length) normalized.tabs = dashboardLayoutTemplate(normalized.page_name, normalized.page_id).tabs;
  if (!normalized.tabs.some((tab) => tab.tab_id === dashboardViewerActiveTabId)) {
    dashboardViewerActiveTabId = normalized.tabs[0]?.tab_id || "";
  }
  return normalized;
}

function currentDashboardTab() {
  return dashboardBuilderLayout?.tabs?.find((tab) => tab.tab_id === dashboardBuilderActiveTabId) || dashboardBuilderLayout?.tabs?.[0] || null;
}

function dashboardGridClass(layoutType) {
  return "dashboard-layout-grid";
}

function dashboardGridStyle(layoutType) {
  const definition = dashboardLayoutDefinitions[layoutType] || dashboardLayoutDefinitions["2_columns"];
  return `--dashboard-layout-columns:${definition.total}`;
}

function dashboardLayoutSpans(layoutType) {
  return (dashboardLayoutDefinitions[layoutType] || dashboardLayoutDefinitions["2_columns"]).spans;
}

function dashboardCellStyle(layoutType, index) {
  const span = dashboardLayoutSpans(layoutType)[index] || 1;
  return `--dashboard-cell-span:${span}`;
}

function dashboardLayoutColumnCount(layoutType) {
  return dashboardLayoutSpans(layoutType).length;
}

function dashboardWidgetTypeLabel(type) {
  if (type === "google_sheet_embed") return "Nhúng Google Sheet";
  const extraLabels = {
    multi_bar_chart: "Biểu đồ cột nhiều đơn vị",
    horizontal_multi_bar_chart: "Bi\u1ec3u \u0111\u1ed3 c\u1ed9t ngang nhi\u1ec1u \u0111\u01a1n v\u1ecb",
    multi_line_chart: "Biểu đồ đường nhiều đơn vị",
  };
  if (extraLabels[type]) return extraLabels[type];
  return {
    bar_chart: "Biểu đồ cột",
    pie_chart: "Biểu đồ tròn",
    line_chart: "Biểu đồ đường",
    combo_chart: "Biểu đồ kết hợp",
    data_table: "Bảng số liệu",
    metric: "Thẻ số liệu",
    data_card: "Thẻ dữ liệu",
    text_title: "Tiêu đề text",
  }[type] || type;
}

function dashboardWidgetTypeOptions(selectedType) {
  return ["bar_chart", "multi_bar_chart", "horizontal_multi_bar_chart", "pie_chart", "line_chart", "multi_line_chart", "combo_chart", "data_table", "metric", "data_card", "google_sheet_embed", "text_title"].map((type) => (
    `<option value="${type}" ${selectedType === type ? "selected" : ""}>${dashboardWidgetTypeLabel(type)}</option>`
  )).join("");
}

function normalizeDashboardSqlCode(value) {
  const text = String(value || "").trim();
  const prefix = text.includes("(") ? text.split("(")[0].trim() : text;
  if (/^[A-Za-z0-9_-]+$/.test(prefix)) return prefix.toUpperCase();
  const match = text.match(/[A-Za-z0-9_-]+/);
  return match ? match[0].toUpperCase() : "";
}

function dashboardReportCode(report) {
  return normalizeDashboardSqlCode(report?.ma_bao_cao) || normalizeDashboardSqlCode(report?.ten_bao_cao);
}

function dashboardReportName(report) {
  const code = dashboardReportCode(report);
  const name = String(report?.ten_bao_cao || "").trim();
  const rawCode = String(report?.ma_bao_cao || "").trim();
  if (name && normalizeDashboardSqlCode(name) !== code) return name;
  if (rawCode && normalizeDashboardSqlCode(rawCode) !== code) return rawCode;
  return name || rawCode || code;
}

function dashboardReportByCode(code) {
  const normalizedCode = normalizeDashboardSqlCode(code);
  return sqlReports.find((report) => dashboardReportCode(report) === normalizedCode);
}

function dashboardReportParams(report) {
  return (report?.cac_tham_so || []).map((param) => String(param || "").trim()).filter(Boolean);
}

function dashboardFilterValueForParam(filters, param) {
  if (!filters || typeof filters !== "object" || Array.isArray(filters)) return "";
  if (Object.prototype.hasOwnProperty.call(filters, param)) return filters[param];
  const normalizedParam = param.toUpperCase();
  const matchingKey = Object.keys(filters).find((key) => String(key).trim().toUpperCase() === normalizedParam);
  return matchingKey ? filters[matchingKey] : "";
}

function dashboardParamFiltersToText(params, existingFilters = {}) {
  if (!params.length) return "";
  const filters = {};
  params.forEach((param) => {
    filters[param] = dashboardFilterValueForParam(existingFilters, param);
  });
  return JSON.stringify(filters, null, 2);
}

function dashboardSqlOptions(selectedCode, selectedReportId = null) {
  const normalizedSelectedCode = normalizeDashboardSqlCode(selectedCode);
  const normalizedReportId = selectedReportId === null || selectedReportId === undefined || selectedReportId === "" ? "" : String(selectedReportId);
  const options = [`<option value="">Chọn mã SQL</option>`].concat(sqlReports.map((report) => {
    const code = dashboardReportCode(report);
    const name = dashboardReportName(report);
    const reportId = String(report.id || "");
    const selected = (normalizedReportId && reportId === normalizedReportId) || (!normalizedReportId && code === normalizedSelectedCode) ? " selected" : "";
    if (!code) return "";
    return `<option value="${escapeHtml(code)}" data-report-id="${escapeHtml(reportId)}"${selected}>${escapeHtml(code)} (${escapeHtml(name)})</option>`;
  }).filter(Boolean));
  if (selectedCode && !dashboardReportByCode(selectedCode)) {
    options.push(`<option value="${escapeHtml(selectedCode)}" selected>${escapeHtml(selectedCode)} (chưa có trong cấu hình SQL)</option>`);
  }
  return options.join("");
}

function dashboardWidgetParamHint(sqlCode) {
  if (!sqlCode) return "Chọn mã SQL từ danh mục Cấu hình báo cáo động.";
  const report = dashboardReportByCode(sqlCode);
  if (!report) return "Mã này chưa có trong Cấu hình báo cáo động. Hãy thêm SQL hoặc đổi sang mã khác.";
  const params = dashboardReportParams(report);
  return params.length ? `Tham số hỗ trợ: ${params.join(", ")}` : "Báo cáo này không có tham số lọc.";
}

function dashboardFiltersToText(filters) {
  if (!filters || typeof filters !== "object" || Array.isArray(filters) || !Object.keys(filters).length) return "";
  return JSON.stringify(filters, null, 2);
}

function parseDashboardFilters(value, strict = false) {
  const text = String(value || "").trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
  } catch {
    // Try the admin-friendly format where each line is its own JSON object.
  }
  const merged = {};
  let parsedLineCount = 0;
  for (const line of text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)) {
    try {
      const parsedLine = JSON.parse(line);
      if (parsedLine && typeof parsedLine === "object" && !Array.isArray(parsedLine)) {
        Object.assign(merged, parsedLine);
        parsedLineCount += 1;
        continue;
      }
    } catch {
      // Report a single clear validation error below.
    }
    if (strict) {
      throw new Error("Bộ lọc mặc định phải là một JSON object hoặc nhiều dòng JSON object, ví dụ: {\"LOAIHINH\":\"58\"}");
    }
    return {};
  }
  if (parsedLineCount > 0) return merged;
  if (strict) throw new Error("Bộ lọc mặc định phải là JSON object hợp lệ, ví dụ: {\"status\":\"1\"}.");
  return {};
}

function dashboardBuilderPageById(pageId) {
  return dashboardLayouts.find((page) => page.page_id === pageId);
}

function dashboardBuilderPageIsSaved(page) {
  return Boolean(page && page.saved !== false && !page.unsaved);
}

async function loadDashboardLayoutPages() {
  const pagesData = await api("/api/admin/dashboard-layout-pages");
  dashboardLayouts = pagesData.pages || [];
  markDataFresh("dashboardLayoutPages");
  return dashboardLayouts;
}

async function loadDashboardBuilder({ force = false } = {}) {
  const message = $("#dashboard-builder-message");
  const pageList = $("#dashboard-layout-pages");
  if (!force && dashboardBuilderLayout) {
    renderDashboardBuilder();
    if (message) message.className = "result hidden";
    return;
  }
  if (pageList) pageList.innerHTML = `<div class="dashboard-empty"><p>Đang tải danh sách trang báo cáo...</p></div>`;
  try {
    const preferredPageId = dashboardBuilderLayout?.page_id || "";
    const [pagesData, reportsData, featuresData] = await Promise.all([
      api("/api/admin/dashboard-layout-pages"),
      api("/api/admin/sql-reports"),
      api("/api/admin/features"),
    ]);
    dashboardLayouts = pagesData.pages || [];
    sqlReports = reportsData.reports || [];
    features = featuresData.features || features;
    markDataFresh("dashboardBuilder");
    markDataFresh("dashboardLayoutPages");
    markDataFresh("sqlReports");
    markDataFresh("features");
    if (dashboardLayouts.length) {
      const preferredPage = dashboardLayouts.find((page) => page.page_id === preferredPageId) || dashboardLayouts[0];
      await openDashboardPage(preferredPage.page_id);
    } else {
      dashboardBuilderLayout = dashboardLayoutTemplate();
      dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
      renderDashboardBuilder();
    }
    if (message) message.className = "result hidden";
  } catch (error) {
    if (message) showMessage(message, error.message, "error");
    $("#dashboard-layout-pages").innerHTML = emptyRow(3, "Không tải được Dashboard Builder", error.message);
  }
}

async function refreshDashboardSqlReports(button = null) {
  if (button) setButtonLoading(button, true);
  const message = $("#dashboard-builder-message");
  try {
    const reportsData = await api("/api/admin/sql-reports");
    sqlReports = reportsData.reports || [];
    markDataFresh("sqlReports");
    fillDynamicReportSelect();
    if (dashboardBuilderLayout) {
      collectDashboardBuilderStateFromDom();
      renderDashboardBuilder();
    }
    if (dashboardViewerLayout) renderDashboardViewer();
    if (message) showMessage(message, "Đã làm mới danh mục báo cáo SQL.");
  } catch (error) {
    if (message) showMessage(message, error.message, "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

async function openDashboardPage(pageId) {
  const page = dashboardBuilderPageById(pageId);
  if (page && !dashboardBuilderPageIsSaved(page)) {
    dashboardBuilderLayout = dashboardLayoutTemplate(page.page_name || page.feature_name || page.page_id, page.page_id, { parentCode: page.parent_code || dashboardDefaultParentCode() });
    dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
    renderDashboardBuilder();
    renderDashboardPreview();
    return;
  }
  await openDashboardLayout(pageId);
}

async function openDashboardLayout(pageId) {
  const normalizedPageId = String(pageId || "").trim();
  if (!normalizedPageId) return;
  const preferredTabId = dashboardBuilderLayout?.page_id === normalizedPageId ? dashboardBuilderActiveTabId : "";
  const page = dashboardBuilderPageById(pageId);
  const cachedLayout = dashboardBuilderLayoutCache.get(normalizedPageId);
  if (cachedLayout) {
    dashboardBuilderActiveTabId = preferredTabId;
    dashboardBuilderLayout = normalizeDashboardBuilderLayout(cloneDashboardLayout(cachedLayout), cachedLayout.page_name || "");
    dashboardBuilderLayout.page_name = repairTextEncoding(page?.page_name || cachedLayout.page_name || dashboardBuilderLayout.page_name);
    dashboardBuilderLayout.parent_code = page?.parent_code || cachedLayout.parent_code || dashboardBuilderLayout.parent_code || dashboardDefaultParentCode();
    if (!dashboardBuilderLayout.tabs.some((tab) => tab.tab_id === dashboardBuilderActiveTabId)) {
      dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
    }
    renderDashboardBuilder();
    await loadDashboardPreviewTab(dashboardBuilderActiveTabId);
    return;
  }
  const data = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(normalizedPageId)}`);
  dashboardBuilderActiveTabId = preferredTabId;
  dashboardBuilderLayout = normalizeDashboardBuilderLayout(data.layout || {}, data.page_name || "");
  dashboardBuilderLayout.page_name = repairTextEncoding(page?.page_name || data.page_name || dashboardBuilderLayout.page_name);
  dashboardBuilderLayout.parent_code = page?.parent_code || data.parent_code || data.layout?.parent_code || dashboardBuilderLayout.parent_code || dashboardDefaultParentCode();
  if (!dashboardBuilderLayout.tabs.some((tab) => tab.tab_id === dashboardBuilderActiveTabId)) {
    dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
  }
  dashboardBuilderLayoutCache.set(normalizedPageId, cloneDashboardLayout(dashboardBuilderLayout));
  renderDashboardBuilder();
  await loadDashboardPreviewTab(dashboardBuilderActiveTabId);
}

function createDashboardPage() {
  const pageName = prompt("Nhập tên trang báo cáo mới:", "Dashboard mới");
  if (pageName === null) return;
  const cleanedName = pageName.trim() || "Dashboard mới";
  dashboardBuilderLayout = dashboardLayoutTemplate(cleanedName, dashboardPageIdFromName(cleanedName), { parentCode: $("#dashboard-parent-code")?.value || dashboardDefaultParentCode() });
  dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
  renderDashboardBuilder();
}

function renderDashboardBuilder() {
  if (!dashboardBuilderLayout) return;
  if (!dashboardBuilderLayout.parent_code) dashboardBuilderLayout.parent_code = dashboardDefaultParentCode();
  $("#dashboard-page-id").value = dashboardBuilderLayout.page_id || "";
  $("#dashboard-page-name").value = dashboardBuilderLayout.page_name || "";
  const parentSelect = $("#dashboard-parent-code");
  if (parentSelect) {
    parentSelect.innerHTML = dashboardParentMenuOptions(dashboardBuilderLayout.parent_code);
    dashboardBuilderLayout.parent_code = parentSelect.value || dashboardBuilderLayout.parent_code;
  }
  renderDashboardPages();
  renderDashboardBuilderTabs();
  renderDashboardWorkspace();
  renderDashboardPreview();
}

function renderDashboardPages() {
  const container = $("#dashboard-layout-pages");
  if (!container) return;
  const currentPageId = dashboardBuilderLayout?.page_id || "";
  const hasCurrent = dashboardLayouts.some((page) => page.page_id === currentPageId);
  const rows = [...dashboardLayouts];
  if (currentPageId && !hasCurrent) {
    rows.unshift({ page_id: currentPageId, page_name: dashboardBuilderLayout.page_name, parent_code: dashboardBuilderLayout.parent_code, unsaved: true });
  }
  container.innerHTML = rows.length ? rows.map((page) => `
    <article class="dashboard-page-card ${page.page_id === currentPageId ? "active" : ""}">
      <div class="dashboard-page-card-body">
        <span class="status ${page.unsaved ? "inactive" : "active"}">${page.unsaved ? "Ch\u01b0a l\u01b0u" : "\u0110\u00e3 l\u01b0u"}</span>
        <strong>${escapeHtml(page.page_name || page.page_id)}</strong>
        <code>${escapeHtml(page.page_id)}</code>
        <small>Menu: ${escapeHtml(dashboardParentMenuLabel(page.parent_code || dashboardDefaultParentCode()))}</small>
      </div>
      <div class="action-group dashboard-page-card-actions">
        <button class="table-action" data-dashboard-open="${escapeHtml(page.page_id)}" type="button">M\u1edf</button>
        ${page.unsaved
          ? `<button class="table-action danger" data-dashboard-purge="${escapeHtml(page.feature_code || "")}" type="button" ${page.feature_code ? "" : "disabled"}>X\u00f3a h\u1eb3n</button>`
          : `<button class="table-action danger" data-dashboard-delete="${escapeHtml(page.page_id)}" type="button">X\u00f3a layout</button>`}
      </div>
    </article>
  `).join("") : `<div class="dashboard-empty"><h2>Ch\u01b0a c\u00f3 trang b\u00e1o c\u00e1o</h2><p>B\u1ea5m T\u1ea1o trang b\u00e1o c\u00e1o \u0111\u1ec3 b\u1eaft \u0111\u1ea7u thi\u1ebft k\u1ebf.</p></div>`;
}

function renderDashboardBuilderTabs() {
  const container = $("#dashboard-builder-tabs");
  if (!container || !dashboardBuilderLayout) return;
  container.innerHTML = dashboardBuilderLayout.tabs.map((tab) => `
    <button class="builder-tab ${tab.tab_id === dashboardBuilderActiveTabId ? "active" : ""}" draggable="true" data-tab-id="${escapeHtml(tab.tab_id)}" type="button" role="tab" aria-selected="${tab.tab_id === dashboardBuilderActiveTabId}">
      <span>${escapeHtml(tab.tab_name)}</span>
      <span class="builder-tab-edit" data-rename-tab="${escapeHtml(tab.tab_id)}" title="Đổi tên Tab">✎</span>
      <span class="builder-tab-delete" data-delete-tab="${escapeHtml(tab.tab_id)}" title="Xóa Tab">×</span>
    </button>
  `).join("");
}

function handleDashboardPageAction(event) {
  const openButton = event.target.closest("[data-dashboard-open]");
  const deleteButton = event.target.closest("[data-dashboard-delete]");
  const purgeButton = event.target.closest("[data-dashboard-purge]");
  if (openButton) {
    openDashboardPage(openButton.dataset.dashboardOpen).catch((error) => showMessage($("#dashboard-builder-message"), error.message, "error"));
    return;
  }
  if (deleteButton) {
    deleteDashboardPage(deleteButton.dataset.dashboardDelete);
    return;
  }
  if (purgeButton) {
    purgeUnsavedDashboardPage(purgeButton.dataset.dashboardPurge);
  }
}

async function deleteDashboardPage(pageId) {
  if (!confirm(`Xóa trang báo cáo ${pageId}?`)) return;
  try {
    const deletedName = dashboardBuilderLayout?.page_id === pageId
      ? dashboardBuilderLayout.page_name
      : (dashboardLayouts.find((page) => page.page_id === pageId)?.page_name || pageId);
    await api(`/api/admin/dashboard-layouts/${encodeURIComponent(pageId)}`, { method: "DELETE" });
    dashboardBuilderLayoutCache.delete(pageId);
    dashboardViewerLayoutCache.delete(pageId);
    Object.keys(dashboardBuilderLoadedTabs).forEach((key) => {
      if (key.startsWith(`${pageId}:`)) delete dashboardBuilderLoadedTabs[key];
    });
    Object.keys(dashboardViewerLoadedTabs).forEach((key) => {
      if (key.startsWith(`${pageId}:`)) delete dashboardViewerLoadedTabs[key];
    });
    markDataStale("dashboardBuilder", "dashboardLayoutPages", "dashboardViewerLayouts");
    showMessage($("#dashboard-builder-message"), "Đã xóa trang báo cáo.");
    await loadDashboardLayoutPages();
    let deletedPage = dashboardLayouts.find((page) => page.page_id === pageId);
    if (!deletedPage) {
      deletedPage = { page_id: pageId, page_name: deletedName, unsaved: true, saved: false };
      dashboardLayouts.unshift(deletedPage);
    }
    if (deletedPage) {
      await openDashboardPage(deletedPage.page_id);
    } else if (dashboardLayouts.length) {
      await openDashboardPage(dashboardLayouts[0].page_id);
    } else {
      dashboardBuilderLayout = dashboardLayoutTemplate();
      dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
      renderDashboardBuilder();
    }
  } catch (error) {
    showMessage($("#dashboard-builder-message"), error.message, "error");
  }
}

function handleDashboardBuilderTabClick(event) {
  const deleteButton = event.target.closest("[data-delete-tab]");
  if (deleteButton) {
    event.stopPropagation();
    deleteDashboardTab(deleteButton.dataset.deleteTab);
    return;
  }
  const renameButton = event.target.closest("[data-rename-tab]");
  if (renameButton) {
    event.stopPropagation();
    renameDashboardTab(renameButton.dataset.renameTab);
    return;
  }
  const tabButton = event.target.closest("[data-tab-id]");
  if (tabButton) switchDashboardBuilderTab(tabButton.dataset.tabId);
}

async function purgeUnsavedDashboardPage(featureCode) {
  if (!featureCode || !confirm("Xóa hẳn mục Dashboard chưa lưu này khỏi cây chức năng?")) return;
  try {
    await api(`/api/admin/dashboard-layout-pages/${encodeURIComponent(featureCode)}`, { method: "DELETE" });
    markDataStale("dashboardBuilder", "dashboardLayoutPages", "dashboardViewerLayouts");
    showMessage($("#dashboard-builder-message"), "Đã xóa hẳn mục Dashboard chưa lưu.");
    await loadDashboardLayoutPages();
    if (dashboardLayouts.length) {
      await openDashboardPage(dashboardLayouts[0].page_id);
    } else {
      dashboardBuilderLayout = dashboardLayoutTemplate();
      dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
      renderDashboardBuilder();
    }
  } catch (error) {
    showMessage($("#dashboard-builder-message"), error.message, "error");
  }
}

function handleDashboardBuilderTabRename(event) {
  const tabButton = event.target.closest("[data-tab-id]");
  if (!tabButton || event.target.closest("[data-delete-tab]") || event.target.closest("[data-rename-tab]")) return;
  renameDashboardTab(tabButton.dataset.tabId);
}

function renameDashboardTab(tabId) {
  const tab = dashboardBuilderLayout.tabs.find((item) => item.tab_id === tabId);
  if (!tab) return;
  const newName = prompt("Đổi tên Tab:", tab.tab_name);
  if (newName === null) return;
  tab.tab_name = repairTextEncoding(newName.trim() || tab.tab_name);
  renderDashboardBuilder();
}

function handleDashboardTabDragStart(event) {
  const tabButton = event.target.closest("[data-tab-id]");
  if (!tabButton) return;
  draggedDashboardTabId = tabButton.dataset.tabId;
  tabButton.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
}

function handleDashboardTabDragOver(event) {
  if (!draggedDashboardTabId || !event.target.closest("[data-tab-id]")) return;
  event.preventDefault();
}

function handleDashboardTabDrop(event) {
  const target = event.target.closest("[data-tab-id]");
  if (!target || !draggedDashboardTabId || target.dataset.tabId === draggedDashboardTabId) return;
  event.preventDefault();
  moveDashboardTab(draggedDashboardTabId, target.dataset.tabId);
}

function handleDashboardTabDragEnd() {
  draggedDashboardTabId = "";
  document.querySelectorAll(".builder-tab.dragging").forEach((tab) => tab.classList.remove("dragging"));
}

function moveDashboardTab(sourceTabId, targetTabId) {
  const tabs = dashboardBuilderLayout.tabs;
  const sourceIndex = tabs.findIndex((tab) => tab.tab_id === sourceTabId);
  const targetIndex = tabs.findIndex((tab) => tab.tab_id === targetTabId);
  if (sourceIndex < 0 || targetIndex < 0) return;
  const [moved] = tabs.splice(sourceIndex, 1);
  tabs.splice(targetIndex, 0, moved);
  tabs.forEach((tab, index) => { tab.order = index + 1; });
  renderDashboardBuilder();
}

function switchDashboardBuilderTab(tabId) {
  collectDashboardBuilderStateFromDom();
  dashboardBuilderActiveTabId = tabId;
  renderDashboardBuilder();
  loadDashboardPreviewTab(tabId);
}

function addDashboardTab() {
  collectDashboardBuilderStateFromDom();
  const index = (dashboardBuilderLayout.tabs?.length || 0) + 1;
  const tab = {
    tab_id: `tab_${Date.now()}`,
    tab_name: `Tab ${index}`,
    order: index,
    grid_layout: [],
  };
  dashboardBuilderLayout.tabs.push(tab);
  dashboardBuilderActiveTabId = tab.tab_id;
  renderDashboardBuilder();
}

function deleteDashboardTab(tabId) {
  if (!dashboardBuilderLayout || dashboardBuilderLayout.tabs.length <= 1) {
    showToast("Dashboard cần có ít nhất một Tab.", "error");
    return;
  }
  if (!confirm("Xóa Tab này?")) return;
  dashboardBuilderLayout.tabs = dashboardBuilderLayout.tabs.filter((tab) => tab.tab_id !== tabId);
  dashboardBuilderLayout.tabs.forEach((tab, index) => { tab.order = index + 1; });
  dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
  renderDashboardBuilder();
}

function collectDashboardBuilderStateFromDom({ strictFilters = false } = {}) {
  if (!dashboardBuilderLayout) return;
  const pageId = $("#dashboard-page-id")?.value.trim().toUpperCase();
  const pageName = $("#dashboard-page-name")?.value.trim();
  const parentCode = $("#dashboard-parent-code")?.value.trim();
  if (pageId) dashboardBuilderLayout.page_id = pageId;
  if (pageName) dashboardBuilderLayout.page_name = repairTextEncoding(pageName);
  if (parentCode) dashboardBuilderLayout.parent_code = parentCode;
  const tab = currentDashboardTab();
  if (!tab) return;
  const rows = [...document.querySelectorAll("#dashboard-builder-workspace .builder-row")];
  tab.grid_layout = rows.map((row, index) => {
    const layoutValue = row.querySelector("[name='layout_type']")?.value || "2_columns";
    const layoutType = dashboardLayoutColumns[layoutValue] ? layoutValue : "2_columns";
    const widgets = [...row.querySelectorAll(".builder-widget-card")].map((card) => {
      const position = Number(card.dataset.position || 1);
      if (position > dashboardLayoutColumnCount(layoutType)) return null;
      const type = card.querySelector("[name='type']")?.value || "bar_chart";
      const sqlSelect = card.querySelector("[name='sql_code']");
      const sqlCode = sqlSelect?.value.trim().toUpperCase() || "";
      const selectedReportId = sqlSelect?.selectedOptions?.[0]?.dataset.reportId || "";
      const title = card.querySelector("[name='title']")?.value.trim() || "";
      const textContent = card.querySelector("[name='text_content']")?.value.trim() || "";
      const iconUrl = card.querySelector("[name='icon_url']")?.value.trim() || "";
      const filters = parseDashboardFilters(card.querySelector("[name='filters']")?.value || "", strictFilters);
      const activeConfig = card.querySelector(".dashboard-widget-config.active");
      const chartConfig = {
        orientation: type === "horizontal_multi_bar_chart" ? "horizontal" : activeConfig?.querySelector("[name='chart_orientation']")?.value || "vertical",
        label_column: activeConfig?.querySelector("[name='label_column']")?.value.trim() || "",
        value_column: activeConfig?.querySelector("[name='value_column']")?.value.trim() || "",
        bar_column: activeConfig?.querySelector("[name='bar_column']")?.value.trim() || "",
        line_column: activeConfig?.querySelector("[name='line_column']")?.value.trim() || "",
        bar_label: activeConfig?.querySelector("[name='bar_label']")?.value.trim() || "",
        line_label: activeConfig?.querySelector("[name='line_label']")?.value.trim() || "",
        series_columns: activeConfig?.querySelector("[name='series_columns']")?.value.trim() || "",
        series_labels: activeConfig?.querySelector("[name='series_labels']")?.value.trim() || "",
        embed_url: activeConfig?.querySelector("[name='embed_url']")?.value.trim() || "",
        embed_height: activeConfig?.querySelector("[name='embed_height']")?.value.trim() || "",
        embed_width: activeConfig?.querySelector("[name='embed_width']")?.value.trim() || "",
        color_scale: Boolean(activeConfig?.querySelector("[name='color_scale']")?.checked),
      };
      const hasDisplayConfig = title || textContent || iconUrl || sqlCode || chartConfig.embed_url;
      if (!hasDisplayConfig) return null;
      return {
        position,
        type,
        title,
        sql_code: sqlCode,
        report_id: selectedReportId ? Number(selectedReportId) : null,
        filters,
        chart_config: chartConfig,
        text_content: textContent,
        icon_url: iconUrl,
      };
    }).filter(Boolean);
    return {
      row_id: Number(row.dataset.rowId || index + 1),
      layout_type: layoutType,
      widgets,
    };
  });
}

function renderDashboardWorkspace() {
  const workspace = $("#dashboard-builder-workspace");
  const tab = currentDashboardTab();
  if (!workspace || !tab) return;
  workspace.innerHTML = tab.grid_layout?.length ? tab.grid_layout.map((row, index) => renderDashboardBuilderRow(row, index)).join("") : `
    <div class="dashboard-empty">
      <p class="eyebrow">Workspace Grid</p>
      <h2>Tab này chưa có Layout</h2>
      <p>Bấm Thêm Layout 1, 2, 3 hoặc 4 cột để bắt đầu bố trí tiêu đề, thẻ dữ liệu và biểu đồ.</p>
    </div>
  `;
}

function dashboardLayoutTypeOptions(selectedType) {
  return Object.entries(dashboardLayoutDefinitions).map(([type, definition]) => (
    `<option value="${type}" ${selectedType === type ? "selected" : ""}>${escapeHtml(definition.label)}</option>`
  )).join("");
}

function dashboardConfigValue(widget, key, fallback = "") {
  return escapeHtml(widget?.chart_config?.[key] ?? fallback);
}

function dashboardConfigChecked(widget, key) {
  return widget?.chart_config?.[key] ? "checked" : "";
}

function dashboardColorScaleOption(widget) {
  return `
    <label class="checkbox-label dashboard-color-scale-option">
      <input type="checkbox" name="color_scale" ${dashboardConfigChecked(widget, "color_scale")} />
      <span>Bật thang màu Đỏ - Xanh dương</span>
    </label>
  `;
}

function renderDashboardWidgetAdvancedConfig(widget) {
  const type = widget.type || "bar_chart";
  const orientation = widget.chart_config?.orientation || "vertical";
  return `
    <div class="dashboard-widget-config ${type === "bar_chart" ? "active" : ""}" data-config-for="bar_chart">
      <label>Hướng biểu đồ cột<select class="form-control" name="chart_orientation"><option value="vertical" ${orientation !== "horizontal" ? "selected" : ""}>Cột đứng</option><option value="horizontal" ${orientation === "horizontal" ? "selected" : ""}>Cột ngang</option></select></label>
      <div class="grid gap-2 md:grid-cols-2">
        <label>Cột nhãn<input class="form-control" name="label_column" value="${dashboardConfigValue(widget, "label_column")}" placeholder="Tự nhận diện nếu để trống" /></label>
        <label>Cột giá trị<input class="form-control" name="value_column" value="${dashboardConfigValue(widget, "value_column")}" placeholder="Tự nhận diện nếu để trống" /></label>
      </div>
      ${dashboardColorScaleOption(widget)}
    </div>
    <div class="dashboard-widget-config ${type === "line_chart" ? "active" : ""}" data-config-for="line_chart">
      <div class="grid gap-2 md:grid-cols-2">
        <label>Cột nhãn<input class="form-control" name="label_column" value="${dashboardConfigValue(widget, "label_column")}" placeholder="Tự nhận diện nếu để trống" /></label>
        <label>Cột giá trị<input class="form-control" name="value_column" value="${dashboardConfigValue(widget, "value_column")}" placeholder="Tự nhận diện nếu để trống" /></label>
      </div>
      ${dashboardColorScaleOption(widget)}
    </div>
    <div class="dashboard-widget-config ${type === "multi_bar_chart" || type === "horizontal_multi_bar_chart" ? "active" : ""}" data-config-for="multi_bar_chart,horizontal_multi_bar_chart">
      <div class="grid gap-2 md:grid-cols-2">
        <label>Cột nhãn<input class="form-control" name="label_column" value="${dashboardConfigValue(widget, "label_column")}" placeholder="Ví dụ: ten_don_vi" /></label>
        <label>Các cột dữ liệu<input class="form-control" name="series_columns" value="${dashboardConfigValue(widget, "series_columns")}" placeholder="fiber,mytv,cam,mesh" /></label>
        <label>Nhãn hiển thị<input class="form-control" name="series_labels" value="${dashboardConfigValue(widget, "series_labels")}" placeholder="Fiber, MyTV, CAM, Mesh" /></label>
      </div>
      ${dashboardColorScaleOption(widget)}
    </div>
    <div class="dashboard-widget-config ${type === "multi_line_chart" ? "active" : ""}" data-config-for="multi_line_chart">
      <div class="grid gap-2 md:grid-cols-2">
        <label>Cột nhãn<input class="form-control" name="label_column" value="${dashboardConfigValue(widget, "label_column")}" placeholder="Ví dụ: ten_don_vi" /></label>
        <label>Các cột dữ liệu<input class="form-control" name="series_columns" value="${dashboardConfigValue(widget, "series_columns")}" placeholder="fiber,mytv,cam,mesh" /></label>
        <label>Nhãn hiển thị<input class="form-control" name="series_labels" value="${dashboardConfigValue(widget, "series_labels")}" placeholder="Fiber, MyTV, CAM, Mesh" /></label>
      </div>
      ${dashboardColorScaleOption(widget)}
    </div>
    <div class="dashboard-widget-config ${type === "combo_chart" ? "active" : ""}" data-config-for="combo_chart">
      <div class="grid gap-2 md:grid-cols-2">
        <label>Cột nhãn<input class="form-control" name="label_column" value="${dashboardConfigValue(widget, "label_column")}" placeholder="Ví dụ: ten_don_vi" /></label>
        <label>Nhãn cột<input class="form-control" name="bar_label" value="${dashboardConfigValue(widget, "bar_label", "Cột")}" /></label>
        <label>Cột dữ liệu dạng cột<input class="form-control" name="bar_column" value="${dashboardConfigValue(widget, "bar_column")}" placeholder="Ví dụ: san_luong" /></label>
        <label>Nhãn đường<input class="form-control" name="line_label" value="${dashboardConfigValue(widget, "line_label", "Đường")}" /></label>
        <label>Cột dữ liệu dạng đường<input class="form-control" name="line_column" value="${dashboardConfigValue(widget, "line_column")}" placeholder="Ví dụ: ty_le" /></label>
      </div>
      ${dashboardColorScaleOption(widget)}
    </div>
    <div class="dashboard-widget-config ${type === "data_card" ? "active" : ""}" data-config-for="data_card">
      <label>Ảnh biểu tượng<input class="form-control" name="icon_url" value="${escapeHtml(widget.icon_url || "")}" placeholder="https://.../icon.png" /></label>
      <label>Ghi chú thẻ<textarea class="form-control" name="text_content" rows="2" placeholder="Dòng ghi chú dưới số liệu">${escapeHtml(widget.text_content || "")}</textarea></label>
    </div>
    <div class="dashboard-widget-config ${type === "google_sheet_embed" ? "active" : ""}" data-config-for="google_sheet_embed">
      <label>Link Google Sheet xuất bản lên web<input class="form-control" name="embed_url" value="${dashboardConfigValue(widget, "embed_url")}" placeholder="https://docs.google.com/spreadsheets/d/e/.../pubhtml" /></label>
      <small>Chỉ dùng link Google Sheet public hoặc Xuất bản lên web. Hệ thống sẽ tự lấy đúng bảng và co chiều cao theo nội dung.</small>
    </div>
    <div class="dashboard-widget-config ${type === "text_title" ? "active" : ""}" data-config-for="text_title">
      <label>Nội dung text<textarea class="form-control" name="text_content" rows="3" placeholder="Nhập mô tả hoặc tiêu đề phụ">${escapeHtml(widget.text_content || "")}</textarea></label>
    </div>
  `;
}

function renderDashboardBuilderRow(row, index) {
  const columns = dashboardLayoutColumnCount(row.layout_type);
  const widgetsByPosition = new Map((row.widgets || []).map((widget) => [Number(widget.position), widget]));
  const cells = Array.from({ length: columns }, (_, cellIndex) => {
    const position = cellIndex + 1;
    const widget = widgetsByPosition.get(position) || { position, type: "bar_chart", title: "", sql_code: "", report_id: null, chart_config: {}, filters: {} };
    const requiresSql = !dashboardNonSqlWidgetTypes.has(widget.type);
    const report = dashboardReportByCode(widget.sql_code || "");
    const params = dashboardReportParams(report);
    const existingFilters = widget.filters && typeof widget.filters === "object" && !Array.isArray(widget.filters) ? widget.filters : {};
    const filterText = Object.keys(existingFilters).length ? dashboardFiltersToText(existingFilters) : dashboardParamFiltersToText(params);
    const showFilterField = requiresSql && (params.length || Object.keys(existingFilters).length);
    return `
      <div class="builder-widget-card dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}" data-position="${position}">
        <small>Ô ${position}</small>
        <label>Tiêu đề<input class="form-control" name="title" value="${escapeHtml(widget.title || "")}" placeholder="Tên biểu đồ, thẻ hoặc tiêu đề" /></label>
        <label>Loại hiển thị<select class="form-control" name="type">${dashboardWidgetTypeOptions(widget.type)}</select></label>
        <label class="dashboard-sql-field ${requiresSql ? "" : "hidden"}">Mã SQL<select class="form-control" name="sql_code" data-previous-code="${escapeHtml(widget.sql_code || "")}">${dashboardSqlOptions(widget.sql_code || "", widget.report_id)}</select><small data-sql-param-hint>${escapeHtml(dashboardWidgetParamHint(widget.sql_code || ""))}</small></label>
        <label class="dashboard-filter-field ${showFilterField ? "" : "hidden"}">Bộ lọc mặc định<textarea class="form-control dashboard-filter-json" name="filters" rows="3" placeholder='{"LOAIHINH":""}'>${escapeHtml(filterText)}</textarea></label>
        ${renderDashboardWidgetAdvancedConfig(widget)}
      </div>
    `;
  }).join("");
  return `
    <section class="builder-row" draggable="true" data-row-id="${escapeHtml(row.row_id || index + 1)}">
      <div class="builder-row-header">
        <div><p class="eyebrow">Dòng Layout ${index + 1}</p><div class="builder-row-title">Kéo dòng này để đổi thứ tự trong Tab</div></div>
        <label>Loại Layout<select class="form-control" name="layout_type">${dashboardLayoutTypeOptions(row.layout_type)}</select></label>
        <div class="action-group">
          <button class="table-action" data-move-dashboard-row="up" data-row-id="${escapeHtml(row.row_id || index + 1)}" type="button" ${index <= 0 ? "disabled" : ""}>Lên</button>
          <button class="table-action" data-move-dashboard-row="down" data-row-id="${escapeHtml(row.row_id || index + 1)}" type="button" ${index >= ((currentDashboardTab()?.grid_layout || []).length - 1) ? "disabled" : ""}>Xuống</button>
          <button class="table-action danger" data-delete-dashboard-row="${escapeHtml(row.row_id || index + 1)}" type="button">Xóa dòng</button>
        </div>
      </div>
      <div class="${dashboardGridClass(row.layout_type)}" style="${dashboardGridStyle(row.layout_type)}">${cells}</div>
    </section>
  `;
}

function addDashboardRow(layoutType) {
  collectDashboardBuilderStateFromDom();
  const tab = currentDashboardTab();
  if (!tab) return;
  const nextRowId = Math.max(0, ...((tab.grid_layout || []).map((row) => Number(row.row_id) || 0))) + 1;
  tab.grid_layout.push({ row_id: nextRowId, layout_type: layoutType, widgets: [] });
  renderDashboardBuilder();
}

function handleDashboardWorkspaceClick(event) {
  const moveButton = event.target.closest("[data-move-dashboard-row]");
  if (moveButton) {
    moveDashboardRow(moveButton.dataset.rowId, moveButton.dataset.moveDashboardRow);
    return;
  }
  const deleteButton = event.target.closest("[data-delete-dashboard-row]");
  if (!deleteButton) return;
  deleteDashboardRow(deleteButton.dataset.deleteDashboardRow);
}

function moveDashboardRow(rowId, direction) {
  collectDashboardBuilderStateFromDom();
  const tab = currentDashboardTab();
  if (!tab?.grid_layout?.length) return;
  const index = tab.grid_layout.findIndex((row) => String(row.row_id) === String(rowId));
  if (index < 0) return;
  const targetIndex = direction === "up" ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= tab.grid_layout.length) return;
  [tab.grid_layout[index], tab.grid_layout[targetIndex]] = [tab.grid_layout[targetIndex], tab.grid_layout[index]];
  renderDashboardBuilder();
}

function applyDashboardSqlSelection(select) {
  const card = select.closest(".builder-widget-card");
  if (!card) return;
  const report = dashboardReportByCode(select.value);
  const previousReport = dashboardReportByCode(select.dataset.previousCode || "");
  const titleInput = card.querySelector("[name='title']");
  const currentTitle = titleInput?.value.trim() || "";
  if (report && titleInput && (!currentTitle || currentTitle === previousReport?.ten_bao_cao)) {
    titleInput.value = report.ten_bao_cao;
  }
  const hint = card.querySelector("[data-sql-param-hint]");
  if (hint) hint.textContent = dashboardWidgetParamHint(select.value);
  const filterField = card.querySelector(".dashboard-filter-field");
  const filterInput = card.querySelector("[name='filters']");
  if (filterField && filterInput) {
    const params = dashboardReportParams(report);
    if (params.length) {
      const existingFilters = parseDashboardFilters(filterInput.value || "", false);
      filterInput.value = dashboardParamFiltersToText(params, existingFilters);
      filterField.classList.remove("hidden");
    } else {
      filterInput.value = "";
      filterField.classList.add("hidden");
    }
  }
  select.dataset.previousCode = select.value;
}

function handleDashboardWorkspaceChange(event) {
  const rowType = event.target.closest("[name='layout_type']");
  const sqlSelect = event.target.closest("[name='sql_code']");
  const widgetType = event.target.closest("[name='type']");
  if (sqlSelect) applyDashboardSqlSelection(sqlSelect);
  collectDashboardBuilderStateFromDom();
  delete dashboardBuilderLoadedTabs[dashboardTabCacheKey(dashboardBuilderActiveTabId)];
  if (rowType || widgetType) renderDashboardBuilder();
  else renderDashboardPreview();
}

function handleDashboardWorkspaceInput() {
  collectDashboardBuilderStateFromDom();
  delete dashboardBuilderLoadedTabs[dashboardTabCacheKey(dashboardBuilderActiveTabId)];
  renderDashboardPreview();
}

function deleteDashboardRow(rowId) {
  const tab = currentDashboardTab();
  if (!tab || !confirm("Xóa dòng Layout này?")) return;
  tab.grid_layout = (tab.grid_layout || []).filter((row) => String(row.row_id) !== String(rowId));
  renderDashboardBuilder();
}

function handleDashboardRowDragStart(event) {
  const row = event.target.closest(".builder-row");
  if (!row) return;
  draggedDashboardRowId = row.dataset.rowId;
  row.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
}

function handleDashboardRowDragOver(event) {
  if (!draggedDashboardRowId || !event.target.closest(".builder-row")) return;
  event.preventDefault();
}

function handleDashboardRowDrop(event) {
  const target = event.target.closest(".builder-row");
  if (!target || !draggedDashboardRowId || target.dataset.rowId === draggedDashboardRowId) return;
  event.preventDefault();
  collectDashboardBuilderStateFromDom();
  const tab = currentDashboardTab();
  const sourceIndex = tab.grid_layout.findIndex((row) => String(row.row_id) === String(draggedDashboardRowId));
  const targetIndex = tab.grid_layout.findIndex((row) => String(row.row_id) === String(target.dataset.rowId));
  if (sourceIndex < 0 || targetIndex < 0) return;
  const [moved] = tab.grid_layout.splice(sourceIndex, 1);
  tab.grid_layout.splice(targetIndex, 0, moved);
  renderDashboardBuilder();
}

function handleDashboardRowDragEnd() {
  draggedDashboardRowId = "";
  document.querySelectorAll(".builder-row.dragging").forEach((row) => row.classList.remove("dragging"));
}

async function saveDashboardLayout(button = null) {
  if (!dashboardBuilderLayout) return;
  const saveButton = button || $("#save-dashboard-layout");
  if (saveButton) setButtonLoading(saveButton, true);
  try {
    collectDashboardBuilderStateFromDom({ strictFilters: true });
    const parentCode = dashboardBuilderLayout.parent_code || dashboardDefaultParentCode();
    const payload = {
      page_id: dashboardBuilderLayout.page_id,
      page_name: dashboardBuilderLayout.page_name,
      parent_code: parentCode,
      layout: {
        page_id: dashboardBuilderLayout.page_id,
        parent_code: parentCode,
        tabs: dashboardBuilderLayout.tabs,
      },
    };
    const response = await api("/api/admin/dashboard-layouts", { method: "POST", body: JSON.stringify(payload) });
    dashboardBuilderLayout = normalizeDashboardBuilderLayout({ ...(response.layout || payload.layout), parent_code: response.parent_code || parentCode }, payload.page_name);
    dashboardBuilderLayout.parent_code = response.parent_code || parentCode;
    dashboardBuilderLayoutCache.set(dashboardBuilderLayout.page_id, cloneDashboardLayout(dashboardBuilderLayout));
    dashboardViewerLayoutCache.delete(dashboardBuilderLayout.page_id);
    Object.keys(dashboardViewerLoadedTabs).forEach((key) => {
      if (key.startsWith(`${dashboardBuilderLayout.page_id}:`)) delete dashboardViewerLoadedTabs[key];
    });
    markDataStale("dashboardViewerLayouts");
    await loadDashboardLayoutPages();
    features = [];
    await syncNavigationFromFeatures();
    dashboardBuilderLoadedTabs = {};
    renderDashboardBuilder();
    showMessage($("#dashboard-builder-message"), "Đã lưu Layout báo cáo.");
    showToast("Đã lưu Layout báo cáo.");
    renderDashboardPreview();
  } catch (error) {
    showMessage($("#dashboard-builder-message"), error.message, "error");
  } finally {
    if (saveButton) setButtonLoading(saveButton, false);
  }
}

function handleDashboardPreviewTabClick(event) {
  const button = event.target.closest("[data-preview-tab]");
  if (!button) return;
  switchDashboardBuilderTab(button.dataset.previewTab);
}

function dashboardTabCacheKey(tabId) {
  return `${dashboardBuilderLayout?.page_id || ""}:${tabId}`;
}

function dashboardPageIsSaved() {
  return dashboardBuilderPageIsSaved(dashboardBuilderPageById(dashboardBuilderLayout?.page_id));
}

async function loadDashboardPreviewTab(tabId, { force = false } = {}) {
  if (!dashboardBuilderLayout || !tabId) return;
  const pageId = dashboardBuilderLayout.page_id;
  const key = `${pageId}:${tabId}`;
  if (dashboardBuilderLoadedTabs[key] && !force) {
    renderDashboardPreview();
    return;
  }
  if (!dashboardPageIsSaved()) {
    showMessage($("#dashboard-preview-message"), "Hãy lưu Layout trước khi tải dữ liệu preview.", "error");
    return;
  }
  const button = $("#refresh-dashboard-preview");
  if (button) setButtonLoading(button, true);
  try {
    const response = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(pageId)}/tabs/${encodeURIComponent(tabId)}/data`);
    dashboardBuilderLoadedTabs[key] = response;
    if (dashboardBuilderLayout?.page_id === pageId && dashboardBuilderActiveTabId === tabId) {
      renderDashboardPreview();
      if (response.ok) showMessage($("#dashboard-preview-message"), response.message || "Đã tải dữ liệu Tab dashboard.", "success");
      else $("#dashboard-preview-message")?.classList.add("hidden");
    }
  } catch (error) {
    if (dashboardBuilderLayout?.page_id === pageId && dashboardBuilderActiveTabId === tabId) {
      showMessage($("#dashboard-preview-message"), error.message, "error");
    }
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

function renderDashboardPreview() {
  const tabs = $("#dashboard-preview-tabs");
  const workspace = $("#dashboard-preview-workspace");
  const tab = currentDashboardTab();
  if (!tabs || !workspace || !dashboardBuilderLayout || !tab) return;
  destroyDashboardCharts();
  tabs.innerHTML = dashboardBuilderLayout.tabs.map((item) => `
    <button class="runtime-tab ${item.tab_id === dashboardBuilderActiveTabId ? "active" : ""}" data-preview-tab="${escapeHtml(item.tab_id)}" type="button" role="tab" aria-selected="${item.tab_id === dashboardBuilderActiveTabId}">
      ${escapeHtml(item.tab_name)}
    </button>
  `).join("");
  const dataByWidget = new Map(((dashboardBuilderLoadedTabs[dashboardTabCacheKey(tab.tab_id)] || {}).widgets || []).map((item) => [`${item.row_id}:${item.position}`, item]));
  workspace.innerHTML = (tab.grid_layout || []).length ? tab.grid_layout.map((row, rowIndex) => {
    const columns = dashboardLayoutColumnCount(row.layout_type);
    const widgetsByPosition = new Map((row.widgets || []).map((widget) => [Number(widget.position), widget]));
    const rowChartHeight = dashboardRowChartHeight(row, dataByWidget);
    const cells = Array.from({ length: columns }, (_, cellIndex) => {
      const position = cellIndex + 1;
      const widget = widgetsByPosition.get(position);
      const data = dataByWidget.get(`${row.row_id}:${position}`);
      return `<div class="dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}">${renderRuntimeWidget(widget, data, `dashboard-preview-${rowIndex}-${position}`, { chartHeight: rowChartHeight })}</div>`;
    }).join("");
    return `<section class="${dashboardGridClass(row.layout_type)}" style="${dashboardGridStyle(row.layout_type)}">${cells}</section>`;
  }).join("") : `
    <div class="dashboard-empty">
      <p class="eyebrow">Preview</p>
      <h2>Tab chưa có Layout</h2>
      <p>Thêm Layout và chọn mã SQL để xem dữ liệu dashboard tại đây.</p>
    </div>
  `;
  schedulePendingDashboardCharts();
  schedulePendingDashboardSheets();
}

function renderRuntimeWidget(widget, widgetData, elementId, options = {}) {
  if (!widget) {
    return `<article class="runtime-widget-card"><div class="runtime-widget-empty">Ô trống</div></article>`;
  }
  const title = widget.title || widget.sql_code || "Tiêu đề";
  if (widget.type === "text_title") return renderRuntimeTextTitleWidget(widget);
  if (widget.type === "google_sheet_embed") return renderRuntimeGoogleSheetWidget(widget);
  if (!widget.sql_code) {
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-empty">Chưa chọn mã SQL cho ô này.</div></article>`;
  }
  const result = widgetData?.data;
  if (!result) {
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-empty">Chưa tải dữ liệu. Mở Tab này để hệ thống gọi API.</div></article>`;
  }
  if (!result.ok) {
    const details = result.details ? `<small>${escapeHtml(JSON.stringify(result.details))}</small>` : "";
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-error">${escapeHtml(result.message || "Không tải được dữ liệu.")}${details}</div></article>`;
  }
  if (widget.type === "data_table") return renderRuntimeTableWidget(title, result);
  if (widget.type === "metric") return renderRuntimeMetricWidget(title, result, widget.sql_code);
  if (widget.type === "data_card") return renderRuntimeDataCardWidget(widget, result);
  return renderRuntimeChartWidget(title, result, widget, elementId, options);
}

function dashboardTrustedGoogleSheetUrl(rawUrl) {
  try {
    const url = new URL(String(rawUrl || "").trim());
  if (url.protocol !== "https:") return "";
  if (url.hostname !== "docs.google.com") return "";
  if (!url.pathname.startsWith("/spreadsheets/")) return "";
  return url.href;
  } catch {
    return "";
  }
}

function dashboardEmbedHeight(value) {
  const height = Number.parseInt(value, 10);
  return Math.min(1400, Math.max(260, Number.isFinite(height) ? height : 520));
}

function dashboardEmbedWidth(value) {
  const width = Number.parseInt(value, 10);
  return Math.min(2600, Math.max(640, Number.isFinite(width) ? width : 1280));
}

function renderRuntimeGoogleSheetWidget(widget) {
  const title = widget.title || "Google Sheet";
  const embedUrl = dashboardTrustedGoogleSheetUrl(widget.chart_config?.embed_url || "");
  if (!embedUrl) {
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-empty">Nhập link Google Sheet đã xuất bản lên web.</div></article>`;
  }
  const elementId = `google-sheet-${Math.random().toString(36).slice(2, 10)}`;
  pendingDashboardSheets.push({ elementId, url: embedUrl });
  return `
    <article class="runtime-widget-card runtime-embed-card">
      <div class="runtime-sheet-table" id="${escapeHtml(elementId)}" data-dashboard-sheet-state="loading">
        <div class="runtime-widget-empty">Đang tải bảng Google Sheet...</div>
      </div>
    </article>
  `;
}

function renderRuntimeTextTitleWidget(widget) {
  return `
    <article class="runtime-widget-card runtime-text-widget">
      ${widget.title ? `<h2>${escapeHtml(widget.title)}</h2>` : ""}
      ${widget.text_content ? `<p>${escapeHtml(widget.text_content)}</p>` : ""}
    </article>
  `;
}

function renderRuntimeTableWidget(title, result) {
  const columns = result.columns || [];
  const rows = result.rows || [];
  return `
    <article class="runtime-widget-card">
      <h3>${escapeHtml(title)}</h3>
      <div class="table-scroll">
        <table>
          <thead>${columns.length ? `<tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>` : ""}</thead>
          <tbody>${rows.length ? rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>`).join("") : emptyRow(Math.max(columns.length, 1), "Không có dữ liệu", "API chưa trả dòng dữ liệu nào.")}</tbody>
        </table>
      </div>
    </article>
  `;
}

function pickDashboardNumericColumn(rows, columns, preferred = "", excluded = new Set()) {
  if (preferred && columns.includes(preferred) && rows.some((row) => Number.isFinite(parseDashboardNumber(row[preferred])))) return preferred;
  return columns.find((column) => !excluded.has(column) && rows.some((row) => Number.isFinite(parseDashboardNumber(row[column])))) || "";
}

function pickDashboardLabelColumn(rows, columns, preferred = "", excluded = new Set()) {
  if (preferred && columns.includes(preferred)) return preferred;
  return columns.find((column) => !excluded.has(column) && rows.some((row) => String(row[column] ?? "").trim())) || columns[0] || "";
}

function renderRuntimeMetricWidget(title, result, sqlCode) {
  const rows = result.rows || [];
  const columns = result.columns || [];
  const firstRow = rows[0] || {};
  const numericColumn = pickDashboardNumericColumn(rows, columns);
  const value = numericColumn ? parseDashboardNumber(firstRow[numericColumn]) : rows.length;
  return `
    <article class="runtime-widget-card">
      <div class="metric-preview">
        <span>${escapeHtml(title)}</span>
        <strong>${formatDashboardNumber(value)}</strong>
        <small>${escapeHtml(numericColumn || sqlCode)}</small>
      </div>
    </article>
  `;
}

function renderRuntimeDataCardWidget(widget, result) {
  const rows = result.rows || [];
  const columns = result.columns || [];
  const firstRow = rows[0] || {};
  const valueColumn = pickDashboardNumericColumn(rows, columns, widget.chart_config?.value_column || "");
  const value = valueColumn ? parseDashboardNumber(firstRow[valueColumn]) : rows.length;
  const icon = widget.icon_url
    ? `<img class="runtime-data-card-icon" src="${escapeHtml(widget.icon_url)}" alt="" loading="lazy" />`
    : `<div class="metric-icon">${escapeHtml((widget.title || widget.sql_code || "D").slice(0, 3).toUpperCase())}</div>`;
  return `
    <article class="runtime-widget-card runtime-data-card">
      ${icon}
      <div>
        <span>${escapeHtml(widget.title || widget.sql_code)}</span>
        <strong>${formatDashboardNumber(value)}</strong>
        <small>${escapeHtml(widget.text_content || valueColumn || widget.sql_code)}</small>
      </div>
    </article>
  `;
}

function dashboardRuntimeChartData(widget, result) {
  if (widget.type === "combo_chart") return extractDashboardComboChartData(result, widget.chart_config || {});
  if (widget.type === "multi_bar_chart" || widget.type === "horizontal_multi_bar_chart" || widget.type === "multi_line_chart") {
    return extractDashboardMultiSeriesChartData(result, widget.chart_config || {});
  }
  return extractDashboardChartData(result, widget.chart_config || {});
}

function dashboardRuntimeChartHeight(widget, widgetData) {
  if (!widget || !dashboardDataWidgetTypes.has(widget.type) || ["data_table", "metric", "data_card"].includes(widget.type)) return 0;
  const result = widgetData?.data;
  if (!result?.ok) return 0;
  const chartData = dashboardRuntimeChartData(widget, result);
  if (!chartData.labels.length || (Array.isArray(chartData.series) && !chartData.series.length)) return 0;
  return dashboardChartHeight(widget.type, chartData);
}

function dashboardRowChartHeight(row, dataByWidget) {
  return Math.max(0, ...(row.widgets || []).map((widget) => dashboardRuntimeChartHeight(widget, dataByWidget.get(`${row.row_id}:${widget.position}`))));
}

function renderRuntimeChartWidget(title, result, widget, elementId, options = {}) {
  const chartData = dashboardRuntimeChartData(widget, result);
  if (!chartData.labels.length || (Array.isArray(chartData.series) && !chartData.series.length)) {
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-empty">Không có dữ liệu để vẽ biểu đồ.</div></article>`;
  }
  const chartHeight = Math.max(dashboardChartHeight(widget.type, chartData), Number(options.chartHeight) || 0);
  pendingDashboardCharts.push({ elementId, widgetType: widget.type, chartData, chartConfig: widget.chart_config || {} });
  return `
    <article class="runtime-widget-card runtime-chart-card">
      <div class="runtime-widget-heading">
        <h3>${escapeHtml(title)}</h3>
        <button class="runtime-copy-chart" data-copy-chart="${escapeHtml(elementId)}" type="button" title="Chụp đúng giao diện biểu đồ">Chụp ảnh</button>
      </div>
      <div class="runtime-chart-box" style="--chart-height:${chartHeight}px"><canvas id="${escapeHtml(elementId)}"></canvas></div>
    </article>
  `;
}

function roundedRectPath(context, x, y, width, height, radius) {
  const safeRadius = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.moveTo(x + safeRadius, y);
  context.lineTo(x + width - safeRadius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  context.lineTo(x + width, y + height - safeRadius);
  context.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
  context.lineTo(x + safeRadius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  context.lineTo(x, y + safeRadius);
  context.quadraticCurveTo(x, y, x + safeRadius, y);
  context.closePath();
}

function cloneChartConfigValue(value) {
  if (Array.isArray(value)) return value.map((item) => cloneChartConfigValue(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneChartConfigValue(item)]));
  }
  return value;
}

function renderHighResolutionChart(canvasId, width, height, scale) {
  const sourceChart = dashboardChartInstances.get(canvasId);
  if (!sourceChart || !window.Chart) return null;
  const output = document.createElement("canvas");
  output.style.width = `${width}px`;
  output.style.height = `${height}px`;
  output.width = Math.round(width * scale);
  output.height = Math.round(height * scale);
  const config = sourceChart.config?._config || sourceChart.config || {};
  const options = cloneChartConfigValue(config.options || {});
  options.responsive = false;
  options.maintainAspectRatio = false;
  options.animation = false;
  options.devicePixelRatio = scale;
  options.plugins = {
    ...(options.plugins || {}),
    tooltip: { enabled: false },
  };
  const highChart = new Chart(output, {
    type: config.type || sourceChart.config.type,
    data: cloneChartConfigValue(config.data || sourceChart.data),
    options,
    plugins: config.plugins || [],
  });
  highChart.update();
  return { canvas: output, chart: highChart };
}

async function copyDashboardChartImage(canvasId) {
  const chartCanvas = document.getElementById(canvasId);
  const card = chartCanvas?.closest(".runtime-widget-card");
  const title = card?.querySelector("h3")?.textContent?.trim() || "Biểu đồ";
  if (!chartCanvas || !card) throw new Error("Không tìm thấy biểu đồ để sao chép.");

  let blob = null;
  try {
    blob = await renderDashboardChartCardBlob(chartCanvas, card, title, canvasId);
  } catch {
    blob = await captureDashboardCardBlob(card);
  }
  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      return "clipboard";
    } catch {
      // Some browsers render the PNG correctly but block image clipboard writes.
    }
  }
  downloadDashboardChartImage(blob, title);
  return "download";
}

async function captureDashboardCardBlob(card) {
  const html2canvas = await ensureHtml2CanvasLoaded();
  const actionButton = card.querySelector(".runtime-copy-chart");
  const previousVisibility = actionButton?.style.visibility || "";
  if (actionButton) actionButton.style.visibility = "hidden";
  try {
    const canvas = await html2canvas(card, {
      backgroundColor: null,
      scale: Math.max(3, Math.min(4, (window.devicePixelRatio || 1.5) * 1.5)),
      useCORS: true,
      logging: false,
    });
    return canvasToPngBlob(canvas);
  } finally {
    if (actionButton) actionButton.style.visibility = previousVisibility;
  }
}

async function renderDashboardChartCardBlob(chartCanvas, card, title, canvasId) {
  const theme = dashboardChartTheme();
  const scale = Math.max(4, Math.min(5, (window.devicePixelRatio || 1) * 2.5));
  const cardRect = card.getBoundingClientRect();
  const chartRect = chartCanvas.getBoundingClientRect();
  const highResolutionChart = renderHighResolutionChart(canvasId, chartRect.width, chartRect.height, scale);
  const chartSource = highResolutionChart?.canvas || chartCanvas;
  const output = document.createElement("canvas");
  output.width = Math.round(cardRect.width * scale);
  output.height = Math.round(cardRect.height * scale);
  const context = output.getContext("2d");
  context.scale(scale, scale);

  roundedRectPath(context, 0, 0, cardRect.width, cardRect.height, 18);
  context.fillStyle = theme.cardBackground;
  context.fill();
  context.lineWidth = 1;
  context.strokeStyle = theme.cardBorder;
  context.stroke();

  context.fillStyle = theme.textColor;
  context.font = "950 14px Arial, system-ui, sans-serif";
  context.textBaseline = "top";
  context.fillText(title, 12, 12);

  context.drawImage(
    chartSource,
    chartRect.left - cardRect.left,
    chartRect.top - cardRect.top,
    chartRect.width,
    chartRect.height,
  );
  highResolutionChart?.chart.destroy();

  return canvasToPngBlob(output);
}

function canvasToPngBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((item) => item ? resolve(item) : reject(new Error("Không tạo được ảnh biểu đồ.")), "image/png");
  });
}

function base64ToBlob(base64, mimeType = "image/png") {
  const binary = atob(String(base64 || ""));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: mimeType });
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Khong doc duoc anh chup."));
    reader.readAsDataURL(blob);
  });
}

function downloadDashboardChartImage(blob, title) {
  const safeName = String(title || "bieu-do")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "bieu-do";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeName}.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function waitAnimationFrames(count = 2) {
  return new Promise((resolve) => {
    const step = () => {
      count -= 1;
      if (count <= 0) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function resizeDashboardCharts() {
  dashboardChartInstances.forEach((chart) => chart?.resize?.());
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function dashboardCaptureFileName() {
  const title = dashboardViewerLayout?.page_name || $("#dashboard-viewer-title")?.textContent || "dashboard";
  const activeTab = dashboardViewerLayout?.tabs?.find((tab) => tab.tab_id === dashboardViewerActiveTabId)?.tab_name || "tab";
  return `${title}-${activeTab}`;
}

async function waitDashboardEmbedsReady(area, timeoutMs = 10000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const loadingSheets = Array.from(area.querySelectorAll("[data-dashboard-sheet-state='loading']"));
    const pendingImages = Array.from(area.querySelectorAll("img")).filter((image) => !image.complete);
    if (!loadingSheets.length && !pendingImages.length) return true;
    await sleep(180);
  }
  return false;
}

function dashboardHasExternalIframes(area) {
  return Boolean(area.querySelector("iframe"));
}

function dashboardHasEmbeddedContent(area) {
  return Boolean(area.querySelector(".runtime-embed-card, .runtime-sheet-table, iframe"));
}

async function captureDashboardViewerAreaBlob(area) {
  const html2canvas = await ensureHtml2CanvasLoaded();
  const section = $("#dashboard-designed-section");
  const previousAreaStyle = area.getAttribute("style") || "";
  const previousScrollLeft = area.scrollLeft;
  const backgroundColor = getComputedStyle(section || area).backgroundColor || null;
  area.classList.add("dashboard-capture-rendering");
  area.style.width = "1920px";
  area.style.minWidth = "1920px";
  area.style.maxWidth = "none";
  area.scrollLeft = 0;
  resizeDashboardCharts();
  const embedsReady = await waitDashboardEmbedsReady(area);
  if (!embedsReady) {
    throw new Error("Trang nhúng chưa tải xong, vui lòng đợi vài giây rồi chụp lại.");
  }
  if (dashboardHasExternalIframes(area)) {
    throw new Error("IFRAME_CAPTURE_REQUIRED");
  }
  if (document.fonts?.ready) await document.fonts.ready;
  await waitAnimationFrames(3);
  try {
    const captureHeight = Math.max(Math.ceil(area.scrollHeight), Math.ceil(area.getBoundingClientRect().height), 1);
    const maxPixels = 70000000;
    const scale = Math.max(2, Math.min(3, Math.sqrt(maxPixels / (1920 * captureHeight))));
    const canvas = await html2canvas(area, {
      backgroundColor,
      width: 1920,
      height: captureHeight,
      windowWidth: 1920,
      windowHeight: 1080,
      scale,
      useCORS: true,
      logging: false,
      scrollX: 0,
      scrollY: 0,
    });
    return canvasToPngBlob(canvas);
  } finally {
    if (previousAreaStyle) area.setAttribute("style", previousAreaStyle);
    else area.removeAttribute("style");
    area.scrollLeft = previousScrollLeft;
    area.classList.remove("dashboard-capture-rendering");
    resizeDashboardCharts();
  }
}

async function captureDashboardViewerServerBlob() {
  const pageUrl = `${window.location.pathname}${window.location.search || ""}`;
  const response = await api("/api/admin/dashboard/capture", {
    method: "POST",
    body: JSON.stringify({ page_url: pageUrl || "/" }),
  });
  return base64ToBlob(response.image_base64, response.mime_type || "image/png");
}

async function captureDashboardViewerPageImage() {
  const button = $("#capture-dashboard-viewer");
  const area = $("#dashboard-viewer-capture-area");
  if (!area || !area.querySelector("#dashboard-viewer-workspace")) {
    showToast("Không tìm thấy vùng Dashboard để chụp.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    let blob = null;
    try {
      blob = await captureDashboardViewerServerBlob();
    } catch (error) {
      if (dashboardHasEmbeddedContent(area)) throw error;
      blob = await captureDashboardViewerAreaBlob(area);
    }
    if (navigator.clipboard?.write && window.ClipboardItem) {
      try {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        showToast("Đã sao chép ảnh toàn bộ Dashboard.");
        return;
      } catch {
        // Some browsers block image clipboard writes, so fall back to download.
      }
    }
    downloadDashboardChartImage(blob, dashboardCaptureFileName());
    showToast("Trình duyệt chặn clipboard, đã tải ảnh Dashboard PNG.");
  } catch (error) {
    showToast(error.message || "Không chụp được Dashboard.", "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function saveDashboardCaptureToZalo(button) {
  const picker = $("#dashboard-zalo-schedule-picker");
  if (!picker?.value) {
    if (!zaloAutoMessages.length) await loadZaloAutoMessages({ force: true });
    showToast("Chọn lịch Zalo nhận ảnh trước.", "error");
    return;
  }
  const area = $("#dashboard-viewer-capture-area");
  if (!area || !area.querySelector("#dashboard-viewer-workspace")) {
    showToast("Không tìm thấy vùng Dashboard để chụp.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    let blob = null;
    try {
      blob = await captureDashboardViewerServerBlob();
    } catch (error) {
      if (dashboardHasEmbeddedContent(area)) throw error;
      blob = await captureDashboardViewerAreaBlob(area);
    }
    const response = await uploadZaloAutoMessageCapture(picker.value, blob, window.location.pathname);
    showToast(response.capture_url ? "Đã lưu ảnh chụp cho lịch Zalo." : "Đã lưu ảnh chụp.");
    await loadZaloAutoMessages({ force: true });
  } catch (error) {
    showToast(error.message || "Không lưu được ảnh chụp Zalo.", "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function handleDashboardRuntimeAction(event) {
  const copyButton = event.target.closest("[data-copy-chart]");
  if (!copyButton) return;
  try {
    copyButton.disabled = true;
    const mode = await copyDashboardChartImage(copyButton.dataset.copyChart);
    showToast(mode === "clipboard" ? "Đã sao chép ảnh biểu đồ." : "Trình duyệt chặn clipboard, đã tải ảnh PNG.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    copyButton.disabled = false;
  }
}

function extractDashboardChartData(result, chartConfig = {}) {
  const rows = result.rows || [];
  const columns = result.columns || [];
  if (!rows.length || !columns.length) return { labels: [], values: [], orientation: chartConfig.orientation || "vertical" };
  const valueColumn = pickDashboardNumericColumn(rows, columns, chartConfig.value_column || "");
  const labelColumn = pickDashboardLabelColumn(rows, columns, chartConfig.label_column || "", new Set([valueColumn]));
  return {
    labels: rows.map((row, index) => String(row[labelColumn] ?? `Dòng ${index + 1}`)),
    values: rows.map((row) => parseDashboardNumber(row[valueColumn]) || 0),
    orientation: chartConfig.orientation || "vertical",
    colorScale: Boolean(chartConfig.color_scale),
  };
}

function extractDashboardComboChartData(result, chartConfig = {}) {
  const rows = result.rows || [];
  const columns = result.columns || [];
  if (!rows.length || !columns.length) return { labels: [], barValues: [], lineValues: [] };
  const barColumn = pickDashboardNumericColumn(rows, columns, chartConfig.bar_column || "");
  const lineColumn = pickDashboardNumericColumn(rows, columns, chartConfig.line_column || "", new Set([barColumn]));
  const labelColumn = pickDashboardLabelColumn(rows, columns, chartConfig.label_column || "", new Set([barColumn, lineColumn]));
  return {
    labels: rows.map((row, index) => String(row[labelColumn] ?? `Dòng ${index + 1}`)),
    barValues: rows.map((row) => parseDashboardNumber(row[barColumn]) || 0),
    lineValues: rows.map((row) => parseDashboardNumber(row[lineColumn]) || 0),
    barLabel: chartConfig.bar_label || barColumn || "Cột",
    lineLabel: chartConfig.line_label || lineColumn || "Đường",
    colorScale: Boolean(chartConfig.color_scale),
  };
}

function dashboardConfigList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function extractDashboardMultiSeriesChartData(result, chartConfig = {}) {
  const rows = result.rows || [];
  const columns = result.columns || [];
  if (!rows.length || !columns.length) return { labels: [], datasets: [] };
  const configuredColumns = dashboardConfigList(chartConfig.series_columns);
  const seriesColumns = configuredColumns.length
    ? configuredColumns.filter((column) => columns.includes(column))
    : columns.filter((column) => rows.some((row) => Number.isFinite(parseDashboardNumber(row[column])))).slice(0, 6);
  const labelColumn = pickDashboardLabelColumn(rows, columns, chartConfig.label_column || "", new Set(seriesColumns));
  const configuredLabels = dashboardConfigList(chartConfig.series_labels);
  return {
    labels: rows.map((row, index) => String(row[labelColumn] ?? `Dòng ${index + 1}`)),
    series: seriesColumns.map((column, index) => ({
      label: configuredLabels[index] || column,
      values: rows.map((row) => parseDashboardNumber(row[column]) || 0),
    })),
    orientation: chartConfig.orientation || "vertical",
    colorScale: Boolean(chartConfig.color_scale),
  };
}

function dashboardChartHeight(widgetType, chartData) {
  const count = Math.max(1, chartData.labels?.length || 1);
  const horizontal = widgetType === "horizontal_multi_bar_chart" || widgetType === "bar_chart" && chartData.orientation === "horizontal";
  if (horizontal) return Math.min(760, Math.max(220, count * 28 + 56));
  if (widgetType === "combo_chart") return Math.min(620, Math.max(260, count * 18 + 112));
  if (widgetType === "multi_bar_chart" || widgetType === "multi_line_chart") return Math.min(700, Math.max(270, count * 20 + 118));
  if (widgetType === "line_chart") return Math.min(560, Math.max(250, count * 14 + 96));
  if (widgetType === "bar_chart") return Math.min(640, Math.max(260, count * 18 + 104));
  return 260;
}

function dashboardChartPrimaryValues(chartData) {
  if (Array.isArray(chartData.series)) return chartData.series.flatMap((series) => series.values || []);
  return chartData.values || chartData.barValues || chartData.lineValues || [];
}

function dashboardAxisMax(values) {
  const finiteValues = (values || []).map(Number).filter(Number.isFinite);
  if (!finiteValues.length) return 1;
  const maxValue = Math.max(...finiteValues);
  return Math.max(3, Math.ceil(maxValue) + 3);
}

function dashboardInterpolateRgb(start, end, ratio) {
  return start.map((channel, index) => Math.round(channel + (end[index] - channel) * ratio));
}

function dashboardColorFromScaleRatio(ratio, alpha = .86) {
  const safeRatio = Math.min(1, Math.max(0, Number.isFinite(ratio) ? ratio : .5));
  const lowerStop = safeRatio <= .5 ? dashboardColorScaleStops[0] : dashboardColorScaleStops[1];
  const upperStop = safeRatio <= .5 ? dashboardColorScaleStops[1] : dashboardColorScaleStops[2];
  const localRatio = (safeRatio - lowerStop.ratio) / (upperStop.ratio - lowerStop.ratio || 1);
  const [red, green, blue] = dashboardInterpolateRgb(lowerStop.rgb, upperStop.rgb, localRatio);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function dashboardValueColors(values, alpha = .96) {
  const numericValues = values.map((value) => Number(value));
  const finiteValues = numericValues.filter(Number.isFinite);
  if (!finiteValues.length) return values.map(() => "rgba(148, 163, 184, .92)");
  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  const range = max - min;
  return numericValues.map((value) => {
    if (!Number.isFinite(value)) return "rgba(148, 163, 184, .92)";
    const ratio = range === 0 ? .5 : (value - min) / range;
    return dashboardColorFromScaleRatio(ratio, alpha);
  });
}

function dashboardCategoryColors(count) {
  return Array.from({ length: Math.max(0, count) }, (_, index) => dashboardPiePalette[index % dashboardPiePalette.length]);
}

function dashboardLineGradient(context, alpha = 1) {
  const chart = context.chart;
  const area = chart.chartArea;
  if (!area) return `rgba(59, 130, 246, ${alpha})`;
  const gradient = chart.ctx.createLinearGradient(0, area.bottom, 0, area.top);
  dashboardColorScaleStops.forEach((stop) => {
    const [red, green, blue] = stop.rgb;
    gradient.addColorStop(stop.ratio, `rgba(${red}, ${green}, ${blue}, ${alpha})`);
  });
  return gradient;
}

function parseDashboardNumber(value) {
  if (value === null || value === undefined || value === "") return NaN;
  if (typeof value === "number") return value;
  const normalized = String(value).replace(/\./g, "").replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : NaN;
}

function ensureChartJsLoaded() {
  if (window.Chart) return Promise.resolve();
  if (chartJsLoadPromise) return chartJsLoadPromise;
  chartJsLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = chartJsSource;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      chartJsLoadPromise = null;
      reject(new Error("Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c th\u01b0 vi\u1ec7n bi\u1ec3u \u0111\u1ed3."));
    };
    document.head.appendChild(script);
  });
  return chartJsLoadPromise;
}

function ensureHtml2CanvasLoaded() {
  if (window.html2canvas) return Promise.resolve(window.html2canvas);
  if (html2CanvasLoadPromise) return html2CanvasLoadPromise;
  html2CanvasLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = html2CanvasSource;
    script.async = true;
    script.onload = () => resolve(window.html2canvas);
    script.onerror = () => {
      html2CanvasLoadPromise = null;
      reject(new Error("Không tải được công cụ chụp ảnh biểu đồ."));
    };
    document.head.appendChild(script);
  });
  return html2CanvasLoadPromise;
}

function schedulePendingDashboardCharts() {
  if (!pendingDashboardCharts.length) return;
  const token = dashboardChartRenderToken;
  window.requestAnimationFrame(() => renderPendingDashboardCharts(token));
}

function schedulePendingDashboardSheets() {
  const jobs = pendingDashboardSheets;
  const token = dashboardSheetRenderToken;
  pendingDashboardSheets = [];
  if (!jobs.length) return;
  jobs.forEach(async ({ elementId, url }) => {
    if (token !== dashboardSheetRenderToken) return;
    const target = document.getElementById(elementId);
    if (!target) return;
    try {
      const response = await api(`/api/google-sheet-table?url=${encodeURIComponent(url)}`);
      if (token !== dashboardSheetRenderToken) return;
      target.innerHTML = response.html || `<div class="runtime-widget-empty">Không tìm thấy bảng trong Google Sheet.</div>`;
      target.dataset.dashboardSheetState = response.html ? "loaded" : "empty";
    } catch (error) {
      if (token !== dashboardSheetRenderToken) return;
      target.innerHTML = `<div class="runtime-widget-error">${escapeHtml(error.message || "Không tải được bảng Google Sheet.")}</div>`;
      target.dataset.dashboardSheetState = "error";
    }
  });
}

function renderChartLoadError(jobs, message) {
  jobs.forEach(({ elementId }) => {
    const canvas = document.getElementById(elementId);
    const box = canvas?.closest(".runtime-chart-box");
    if (box) box.innerHTML = `<div class="runtime-widget-empty">${escapeHtml(message)}</div>`;
  });
}

async function renderPendingDashboardCharts(token = dashboardChartRenderToken) {
  // A stale render pass must not clear jobs queued by the newly active tab.
  if (token !== dashboardChartRenderToken) return;
  const jobs = pendingDashboardCharts;
  pendingDashboardCharts = [];
  if (!jobs.length) return;
  try {
    await ensureChartJsLoaded();
  } catch (error) {
    renderChartLoadError(jobs, error.message);
    return;
  }
  if (token !== dashboardChartRenderToken) return;
  jobs.forEach(({ elementId, widgetType, chartData }) => {
    const canvas = document.getElementById(elementId);
    if (!canvas || !window.Chart) return;
    const theme = dashboardChartTheme();
    const useColorScale = Boolean(chartData.colorScale);
    const isPie = widgetType === "pie_chart";
    const palette = isPie
      ? Array.from({ length: chartData.labels.length }, (_, index) => theme.piePalette[index % theme.piePalette.length])
      : useColorScale
        ? dashboardValueColors(dashboardChartPrimaryValues(chartData))
        : theme.seriesPalette;
    const isLine = widgetType === "line_chart";
    const isCombo = widgetType === "combo_chart";
    const isMulti = widgetType === "multi_bar_chart" || widgetType === "horizontal_multi_bar_chart" || widgetType === "multi_line_chart";
    const isMultiLine = widgetType === "multi_line_chart";
    const chartType = isCombo || isMulti && !isMultiLine ? "bar" : isPie ? "pie" : (isLine || isMultiLine) ? "line" : "bar";
    const seriesPalette = theme.seriesPalette;
    const datasets = isMulti ? chartData.series.map((series, seriesIndex) => ({
      label: series.label,
      data: series.values,
      backgroundColor: isMultiLine ? (useColorScale ? (context) => dashboardLineGradient(context, .24) : `${seriesPalette[seriesIndex % seriesPalette.length]}4d`) : (useColorScale ? dashboardValueColors(series.values, .96) : seriesPalette[seriesIndex % seriesPalette.length]),
      borderColor: isMultiLine && useColorScale ? (context) => dashboardLineGradient(context, 1) : seriesPalette[seriesIndex % seriesPalette.length],
      pointBackgroundColor: isMultiLine ? seriesPalette[seriesIndex % seriesPalette.length] : undefined,
      borderWidth: isMultiLine ? 4 : 1.5,
      tension: .35,
      fill: isMultiLine,
    })) : isCombo ? [
      {
        type: "bar",
        label: chartData.barLabel,
        data: chartData.barValues,
        backgroundColor: useColorScale ? dashboardValueColors(chartData.barValues, .96) : theme.seriesPalette[0],
        borderColor: theme.textColor,
        borderWidth: 1.5,
        yAxisID: "y",
      },
      {
        type: "line",
        label: chartData.lineLabel,
        data: chartData.lineValues,
        borderColor: useColorScale ? (context) => dashboardLineGradient(context, 1) : theme.lineColor,
        backgroundColor: useColorScale ? (context) => dashboardLineGradient(context, .24) : theme.lineFill,
        pointBackgroundColor: useColorScale ? dashboardValueColors(chartData.lineValues) : theme.lineColor,
        pointBorderColor: theme.textColor,
        pointRadius: 4,
        borderWidth: 4,
        tension: .35,
        yAxisID: "y1",
      },
    ] : [{
      label: "Giá trị",
      data: chartData.values,
      backgroundColor: isPie ? palette : isLine ? (useColorScale ? (context) => dashboardLineGradient(context, .24) : theme.lineFill) : (useColorScale ? palette : theme.seriesPalette[0]),
      borderColor: isPie ? theme.pieBorder : isLine && useColorScale ? (context) => dashboardLineGradient(context, 1) : theme.lineColor,
      pointBackgroundColor: isLine ? (useColorScale ? palette : theme.lineColor) : undefined,
      pointBorderColor: isLine ? theme.textColor : undefined,
      pointRadius: isLine ? 4.5 : undefined,
      borderWidth: isPie ? 2 : isLine ? 4 : 1.5,
      tension: .35,
      fill: isLine,
    }];
    const isHorizontalAxis = widgetType === "horizontal_multi_bar_chart" || widgetType === "bar_chart" && chartData.orientation === "horizontal";
    const primaryAxisMax = dashboardAxisMax(dashboardChartPrimaryValues(chartData));
    const chartFontFamily = "Arial, system-ui, sans-serif";
    const axisTickStyle = { color: theme.axisColor, font: { size: 15, weight: "700", family: chartFontFamily }, textStrokeColor: theme.labelStroke, textStrokeWidth: 1 };
    const axisGridStyle = { color: theme.gridColor };
    const scales = isPie ? {} : isCombo ? {
      x: { ticks: { ...axisTickStyle, autoSkip: false, maxRotation: 55, minRotation: 0 }, grid: axisGridStyle },
      y: { beginAtZero: true, max: dashboardAxisMax(chartData.barValues), ticks: axisTickStyle, grid: axisGridStyle },
      y1: { beginAtZero: true, max: dashboardAxisMax(chartData.lineValues), position: "right", ticks: { color: theme.secondaryAxisColor, font: { size: 15, weight: "700", family: chartFontFamily }, textStrokeColor: theme.labelStroke, textStrokeWidth: 1 }, grid: { drawOnChartArea: false } },
    } : {
      x: { beginAtZero: isHorizontalAxis, max: isHorizontalAxis ? primaryAxisMax : undefined, ticks: { ...axisTickStyle, autoSkip: false, maxRotation: 55, minRotation: 0 }, grid: axisGridStyle },
      y: { beginAtZero: true, max: isHorizontalAxis ? undefined : primaryAxisMax, ticks: { ...axisTickStyle, autoSkip: false }, grid: axisGridStyle },
    };
    const valueLabelPlugin = {
      id: `dashboardValueLabels-${elementId}`,
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        ctx.font = `800 15px ${chartFontFamily}`;
        ctx.fillStyle = theme.textColor;
        ctx.shadowColor = theme.valueShadow;
        ctx.shadowBlur = 0;
        ctx.lineWidth = 2;
        ctx.strokeStyle = theme.labelStroke;
        chart.data.datasets.forEach((dataset, datasetIndex) => {
          const meta = chart.getDatasetMeta(datasetIndex);
          if (meta.hidden) return;
          meta.data.forEach((point, index) => {
            const value = dataset.data[index];
            if (value === null || value === undefined || Number.isNaN(Number(value))) return;
            const position = point.tooltipPosition();
            const horizontal = chart.options.indexAxis === "y" && dataset.type !== "line";
            ctx.textAlign = horizontal ? "left" : "center";
            const label = formatDashboardNumber(value);
            const x = position.x + (horizontal ? 8 : 0);
            const y = position.y - (horizontal ? 0 : 8);
            ctx.strokeText(label, x, y);
            ctx.fillText(label, x, y);
          });
        });
        ctx.restore();
      },
    };
    dashboardChartInstances.set(elementId, new Chart(canvas, {
      type: chartType,
      data: { labels: chartData.labels, datasets },
      options: {
        indexAxis: isHorizontalAxis ? "y" : "x",
        responsive: true,
        maintainAspectRatio: false,
        devicePixelRatio: Math.max(2, window.devicePixelRatio || 1),
        plugins: {
          legend: { display: isPie || isCombo || isMulti, labels: { color: theme.textColor, font: { size: 14, weight: "700", family: chartFontFamily } } },
        },
        scales,
      },
      plugins: [valueLabelPlugin],
    }));
  });
}

function destroyDashboardCharts() {
  dashboardChartRenderToken += 1;
  dashboardSheetRenderToken += 1;
  dashboardChartInstances.forEach((chart) => chart.destroy());
  dashboardChartInstances.clear();
  pendingDashboardCharts = [];
  pendingDashboardSheets = [];
}

async function loadRegions({ force = false } = {}) {
  if (!force && isDataFresh("regions")) {
    renderRegionsTable();
    return;
  }
  if (regions.length && !force) {
    renderRegionsTable();
  }
  regions = (await api("/api/admin/regions")).regions;
  markDataFresh("regions");
  renderRegionsTable();
}

function renderRegionsTable() {
  $("#regions-table").innerHTML = regions.length ? regions.map((region) => `
    <tr>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-region="${escapeHtml(region.code)}">Sửa</button> <button class="table-action danger" data-delete-region="${escapeHtml(region.code)}">Xóa</button></div></td>
      <td><strong>${escapeHtml(region.code)}</strong></td>
      <td>${escapeHtml(region.name)}</td>
      <td><span class="status ${region.is_active ? "active" : "inactive"}">${region.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
      <td>${escapeHtml(region.sort_order)}</td>
    </tr>
  `).join("") : emptyRow(5, "Chưa có phân vùng", "Thêm phân vùng để phân quyền dữ liệu.");
  document.querySelectorAll("[data-edit-region]").forEach((button) => button.addEventListener("click", () => openRegion(button.dataset.editRegion)));
  document.querySelectorAll("[data-delete-region]").forEach((button) => button.addEventListener("click", () => deleteRegion(button.dataset.deleteRegion)));
}

function openRegion(code = "") {
  const region = regions.find((item) => item.code === code);
  const form = $("#region-form");
  form.elements.namedItem("code").value = region?.code || "";
  form.elements.namedItem("code").readOnly = Boolean(region);
  form.elements.namedItem("name").value = region?.name || "";
  form.elements.namedItem("sort_order").value = region?.sort_order ?? 0;
  form.elements.namedItem("is_active").checked = region ? Boolean(region.is_active) : true;
  form.querySelector(".result").className = "result hidden";
  $("#region-dialog").showModal();
}

async function saveRegion(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/admin/regions", { method: "POST", body: JSON.stringify({
      code: data.code,
      name: data.name,
      sort_order: Number(data.sort_order || 0),
      is_active: form.is_active.checked,
    })});
    form.reset();
    form.elements.namedItem("code").readOnly = false;
    form.is_active.checked = true;
    $("#region-dialog").close();
    showMessage($("#regions-message"), "Đã lưu phân vùng.");
    await loadRegions({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteRegion(code) {
  if (!confirm(`Xóa phân vùng ${code}? Các phân quyền dữ liệu liên quan cũng sẽ được xóa.`)) return;
  try {
    await api(`/api/admin/regions/${encodeURIComponent(code)}`, { method: "DELETE" });
    showMessage($("#regions-message"), `Đã xóa phân vùng ${code}.`);
    await loadRegions({ force: true });
  } catch (error) {
    showMessage($("#regions-message"), error.message, "error");
  }
}

async function loadWorkTasks({ force = false } = {}) {
  if (!force && isDataFresh("workTasks")) {
    renderWorkTasks();
    return;
  }
  if (workTasks.length && !force) {
    renderWorkTasks();
  }
  if (!workTasks.length || force) setTableLoading("#work-tasks-table", 9, "Đang tải lịch công việc...");
  workTasks = (await api("/api/admin/work-tasks")).tasks;
  markDataFresh("workTasks");
  renderWorkTasks();
}

function renderWorkTasks() {
  const table = $("#work-tasks-table");
  if (!table) return;
  table.innerHTML = workTasks.length ? workTasks.map((task) => `
    <tr>
      <td class="table-action-cell">
        <div class="action-group">
          <button class="table-action" data-edit-work-task="${escapeHtml(task.task_id)}">Sửa</button>
          <button class="table-action" data-complete-work-task="${escapeHtml(task.task_id)}">Hoàn thành</button>
          <button class="table-action danger" data-delete-work-task="${escapeHtml(task.task_id)}">Xóa</button>
        </div>
      </td>
      <td><strong>${escapeHtml(task.task_id)}</strong></td>
      <td>${escapeHtml(task.ten_cong_viec)}${task.last_notified_at ? `<small class="cell-note">Đã nhắc: ${escapeHtml(new Date(task.last_notified_at).toLocaleString("vi-VN"))}</small>` : ""}</td>
      <td><span class="status viewer">${escapeHtml(task.type)}</span></td>
      <td><strong>${escapeHtml(task.time)}</strong></td>
      <td>${escapeHtml(task.weekday || "-")}</td>
      <td>${escapeHtml(task.once_date || "-")}</td>
      <td>${escapeHtml(task.group || "-")}</td>
      <td><span class="status ${task.check ? "active" : "inactive"}">${task.check ? "Đã xong" : "Đang chờ"}</span></td>
    </tr>
  `).join("") : emptyRow(9, "Chưa có lịch công việc", "Hãy thêm công việc để hệ thống nhắc qua Telegram đúng giờ.");
  document.querySelectorAll("[data-edit-work-task]").forEach((button) => button.addEventListener("click", () => openWorkTask(button.dataset.editWorkTask)));
  document.querySelectorAll("[data-complete-work-task]").forEach((button) => button.addEventListener("click", () => completeWorkTask(button.dataset.completeWorkTask)));
  document.querySelectorAll("[data-delete-work-task]").forEach((button) => button.addEventListener("click", () => deleteWorkTask(button.dataset.deleteWorkTask)));
}

function openWorkTask(taskId = "") {
  const task = workTasks.find((item) => item.task_id === taskId);
  const form = $("#work-task-form");
  form.elements.namedItem("task_id").value = task?.task_id || "";
  form.elements.namedItem("task_id").readOnly = true;
  form.elements.namedItem("ten_cong_viec").value = task?.ten_cong_viec || "";
  form.elements.namedItem("type").value = task?.type || "Daily";
  form.elements.namedItem("time").value = task?.time || "07:00";
  form.elements.namedItem("weekday").value = task?.weekday || "";
  form.elements.namedItem("once_date").value = task?.once_date || "";
  form.elements.namedItem("group").value = task?.group || "ME";
  form.elements.namedItem("check").checked = task ? Boolean(task.check) : false;
  form.querySelector(".result").className = "result hidden";
  $("#work-task-dialog").showModal();
}

async function saveWorkTask(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/admin/work-tasks", { method: "POST", body: JSON.stringify({
      task_id: data.task_id,
      ten_cong_viec: data.ten_cong_viec,
      type: data.type,
      time: data.time,
      weekday: data.weekday || "",
      once_date: data.once_date || "",
      group: data.group || "",
      check: form.check.checked,
    })});
    form.reset();
    form.elements.namedItem("task_id").readOnly = true;
    form.elements.namedItem("type").value = "Daily";
    form.elements.namedItem("time").value = "07:00";
    form.elements.namedItem("group").value = "ME";
    $("#work-task-dialog").close();
    showMessage($("#work-tasks-message"), "Đã lưu công việc.");
    showToast("Đã lưu lịch công việc.");
    await loadWorkTasks({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
    showToast(error.message, "error");
  }
}

async function completeWorkTask(taskId) {
  if (!confirm(`Xác nhận đã hoàn thành ${taskId}? Lịch này sẽ được tắt và ẩn khỏi danh sách.`)) return;
  try {
    const result = await api(`/api/admin/work-tasks/${encodeURIComponent(taskId)}/complete`, { method: "POST" });
    showMessage($("#work-tasks-message"), result.message || "Đã hoàn thành công việc.");
    await loadWorkTasks({ force: true });
  } catch (error) {
    showMessage($("#work-tasks-message"), error.message, "error");
  }
}

async function deleteWorkTask(taskId) {
  if (!confirm(`Xóa lịch công việc ${taskId}?`)) return;
  try {
    await api(`/api/admin/work-tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
    showMessage($("#work-tasks-message"), `Đã xóa lịch ${taskId}.`);
    await loadWorkTasks({ force: true });
  } catch (error) {
    showMessage($("#work-tasks-message"), error.message, "error");
  }
}

async function loadSystem({ force = false } = {}) {
  if (!force && isDataFresh("system") && isDataFresh("connections") && isDataFresh("sqlReports") && isDataFresh("oneBssReports") && isDataFresh("dataMining")) return;
  $("#system-cards").innerHTML = loadingRow(1, "Đang tải thông tin hệ thống...");
  const [data] = await Promise.all([
    api("/api/admin/system"),
    loadConnections({ force }),
    loadZaloAutoMessages({ force }),
    loadZaloMessageLogs({ force }),
    loadDataMining({ force }),
    loadSqlReports({ force }),
    loadOneBssReports({ force }),
  ]);
  markDataFresh("system");
  $("#system-cards").innerHTML = [
    ["APP", "Môi trường", data.environment],
    ["STO", "Database chính", data.storage_backend],
    ["API", "API dữ liệu", data.internal_api_mock_mode ? "Mock nội bộ" : data.internal_api_url],
    ["USR", "Người dùng hoạt động", `${data.active_user_count}/${data.user_count}`],
  ].map(([icon, label, value]) => `<article class="metric-card"><div class="metric-icon">${icon}</div><div><span>${label}</span><strong>${escapeHtml(value)}</strong></div></article>`).join("");
}

async function loadConnections({ force = false } = {}) {
  if (!force && isDataFresh("connections")) {
    renderConnectionsTable();
    return;
  }
  if (connections.length && !force) {
    renderConnectionsTable();
  }
  if (!connections.length || force) renderConnectionEditorLoading("Đang tải kết nối hệ thống...");
  const data = await api("/api/admin/connections");
  connections = data.connections;
  markDataFresh("connections");
  renderConnectionsTable();
}

function renderConnectionsTable() {
  const editor = $("#connection-editor");
  if (!editor) return;
  refreshConnectionPicker();
  const selectedCode = $("#connection-picker")?.value || "";
  const selectedConnection = selectedCode ? connections.find((connection) => connection.code === selectedCode) : null;
  if (!selectedConnection) {
    editor.innerHTML = `<div class="empty-state"><div><strong>Chưa chọn kết nối</strong><p>Hãy tìm hoặc chọn một kết nối hệ thống để chỉnh cấu hình.</p></div></div>`;
    return;
  }
  editor.innerHTML = renderConnectionEditor(selectedConnection);
  document.querySelectorAll("[data-inline-connection-field]").forEach((field) => {
    field.addEventListener("input", () => markConnectionDirty(field.closest("[data-connection-row]")));
    field.addEventListener("change", () => markConnectionDirty(field.closest("[data-connection-row]")));
  });
  document.querySelectorAll("[data-inline-connection-active]").forEach((field) => {
    field.addEventListener("change", () => markConnectionDirty(field.closest("[data-connection-row]")));
  });
  document.querySelectorAll("[data-save-connection-inline]").forEach((button) => {
    button.addEventListener("click", () => saveInlineConnection(button.dataset.saveConnectionInline, button));
  });
  document.querySelectorAll("[data-test-connection]").forEach((button) => {
    button.addEventListener("click", () => testConnection(button.dataset.testConnection, button));
  });
  document.querySelectorAll("[data-connect-google-drive]").forEach((button) => {
    button.addEventListener("click", () => connectGoogleDrive(button));
  });
  document.querySelectorAll("[data-disconnect-google-drive]").forEach((button) => {
    button.addEventListener("click", () => disconnectGoogleDrive(button));
  });
}

function renderConnectionEditorLoading(text) {
  const editor = $("#connection-editor");
  if (editor) editor.innerHTML = `<div class="loading-row">${escapeHtml(text)}</div>`;
}

function refreshConnectionPicker() {
  const picker = $("#connection-picker");
  if (!picker) return;
  const search = ($("#connection-search")?.value || "").trim().toLowerCase();
  const current = picker.value;
  const filteredConnections = connections.filter((connection) => {
    if (!search) return true;
    const configKeys = Object.keys(connection.config || {});
    const text = [connection.name, connection.code, connection.connection_type, connection.description, connection.secret_ref, ...configKeys].join(" ").toLowerCase();
    return text.includes(search);
  });
  picker.innerHTML = `<option value="">Chọn kết nối cần cấu hình</option>${filteredConnections.map((connection) => `<option value="${escapeHtml(connection.code)}">${escapeHtml(connection.name || connection.code)} (${escapeHtml(connection.code)})</option>`).join("")}`;
  if (current && filteredConnections.some((connection) => connection.code === current)) picker.value = current;
}

function renderConnectionEditor(connection) {
  const configText = JSON.stringify(connection.config || {}, null, 2);
  const configKeys = Object.keys(connection.config || {});
  const protectedKeys = connection.protected_config_keys || [];
  const variables = [connection.secret_ref, ...configKeys, ...protectedKeys.map((key) => `protected:${key}`)].filter(Boolean);
  return `
    <div class="connection-editor-card" data-connection-row="${escapeHtml(connection.code)}">
      <div class="section-heading">
        <div><p class="eyebrow">Chỉnh kết nối</p><h3>${escapeHtml(connection.name || connection.code)}</h3><p>${escapeHtml(connection.code)}</p></div>
        <div class="action-group"><button class="table-action hidden" data-save-connection-inline="${escapeHtml(connection.code)}">Lưu</button><button class="table-action" data-test-connection="${escapeHtml(connection.code)}"><span class="button-label">Kiểm tra</span><span class="spinner"></span></button></div>
      </div>
      <label>Tên<input class="form-control inline-admin-input" data-inline-connection-field="name" value="${escapeHtml(connection.name || "")}" /></label>
      <label>Mã<code class="compact-code">${escapeHtml(connection.code)}</code></label>
      <label>Loại
        <select class="form-control inline-admin-input" data-inline-connection-field="connection_type">
          ${["internal_api", "supabase", "ftp", "drive", "telegram", "zalo"].map((type) => `<option value="${type}" ${connection.connection_type === type ? "selected" : ""}>${type}</option>`).join("")}
        </select>
      </label>
      <label class="checkbox-label inline-checkbox"><input type="checkbox" data-inline-connection-active ${connection.is_active ? "checked" : ""} /> Đang dùng</label>
      <label>Danh sách biến<div class="connection-variable-list">${variables.length ? variables.map((item) => `<span class="status viewer">${escapeHtml(item)}</span>`).join(" ") : "Không có"}</div></label>
      ${renderDriveOauthPanel(connection)}
      <label>Mô tả<textarea class="form-control inline-admin-note connection-description" data-inline-connection-field="description" rows="3" placeholder="Mô tả">${escapeHtml(connection.description || "")}</textarea></label>
      <label>Bảng lệnh / Cấu hình<textarea class="form-control inline-admin-code connection-editor-code" data-inline-connection-field="config_json" rows="14">${escapeHtml(configText)}</textarea></label>
      <div class="cell-note" id="connection-result-${escapeHtml(connection.code)}"></div>
    </div>`;
}

function renderDriveOauthPanel(connection) {
  if (connection.connection_type !== "drive" && connection.code !== "drive_storage") return "";
  const config = connection.config || {};
  const protectedKeys = connection.protected_config_keys || [];
  const email = config.oauth_email || "";
  const connectedAt = config.oauth_connected_at || "";
  const folder = config.folder || config.folder_id || "";
  const connected = Boolean(email || connectedAt || protectedKeys.includes("oauth_refresh_token_enc"));
  return `
    <div class="drive-oauth-panel">
      <div>
        <strong>Google Drive OAuth</strong>
        <p>${connected ? `Đã kết nối${email ? `: ${escapeHtml(email)}` : ""}${connectedAt ? ` (${escapeHtml(connectedAt)})` : ""}` : "Chưa kết nối tài khoản Google Drive của anh."}</p>
        <p>${folder ? `Thư mục mặc định: ${escapeHtml(folder)}` : "OneBSS sẽ ưu tiên thư mục trong link lưu báo cáo."}</p>
      </div>
      <div class="action-group">
        <button class="btn-secondary" type="button" data-connect-google-drive><span class="button-label">${connected ? "Kết nối lại Drive" : "Kết nối Google Drive"}</span><span class="spinner"></span></button>
        <button class="table-action danger ${connected ? "" : "hidden"}" type="button" data-disconnect-google-drive><span class="button-label">Ngắt kết nối</span><span class="spinner"></span></button>
      </div>
    </div>`;
}

function markConnectionDirty(row) {
  row?.querySelector("[data-save-connection-inline]")?.classList.remove("hidden");
}

async function saveInlineConnection(code, button) {
  const row = document.querySelector(`[data-connection-row="${CSS.escape(code)}"]`);
  if (!row) return;
  let config = {};
  try {
    config = JSON.parse(row.querySelector('[data-inline-connection-field="config_json"]')?.value || "{}");
  } catch {
    showToast("Cấu hình JSON chưa đúng định dạng.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    await api(`/api/admin/connections/${encodeURIComponent(code)}`, { method: "PUT", body: JSON.stringify({
      name: row.querySelector('[data-inline-connection-field="name"]')?.value.trim() || code,
      connection_type: row.querySelector('[data-inline-connection-field="connection_type"]')?.value || "internal_api",
      description: row.querySelector('[data-inline-connection-field="description"]')?.value || "",
      config,
      is_active: Boolean(row.querySelector("[data-inline-connection-active]")?.checked),
    })});
    button.classList.add("hidden");
    showToast("Đã lưu kết nối hệ thống.");
    await loadConnections({ force: true });
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function openConnection(code) {
  const connection = connections.find((item) => item.code === code);
  const form = $("#connection-form");
  form.elements.namedItem("code").value = connection.code;
  form.elements.namedItem("name").value = connection.name;
  form.elements.namedItem("connection_type").value = connection.connection_type;
  form.elements.namedItem("description").value = connection.description || "";
  form.elements.namedItem("config_json").value = JSON.stringify(connection.config || {}, null, 2);
  form.elements.namedItem("is_active").checked = Boolean(connection.is_active);
  form.querySelector(".result").className = "result hidden";
  $("#connection-dialog").showModal();
}

async function saveConnection(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  let config = {};
  try {
    config = data.config_json ? JSON.parse(data.config_json) : {};
  } catch {
    showMessage(form.querySelector(".result"), "Cấu hình JSON chưa đúng định dạng.", "error");
    return;
  }
  try {
    await api(`/api/admin/connections/${encodeURIComponent(data.code)}`, { method: "PUT", body: JSON.stringify({
      name: data.name,
      connection_type: data.connection_type,
      description: data.description || "",
      config,
      is_active: form.is_active.checked,
    })});
    $("#connection-dialog").close();
    await loadConnections({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function connectGoogleDrive(button) {
  const popup = window.open("", "google-drive-oauth", "width=560,height=760");
  setButtonLoading(button, true);
  try {
    const result = await api("/api/google-drive/oauth/start", { method: "POST" });
    if (popup) {
      popup.location.href = result.authorization_url;
      popup.focus();
    } else {
      window.location.href = result.authorization_url;
    }
    showToast("Đang mở trang cấp quyền Google Drive...");
  } catch (error) {
    if (popup) popup.close();
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function disconnectGoogleDrive(button) {
  if (!confirm("Ngắt kết nối Google Drive OAuth? File OneBSS sẽ không upload được vào Drive cá nhân cho tới khi kết nối lại.")) return;
  setButtonLoading(button, true);
  try {
    await api("/api/google-drive/oauth/disconnect", { method: "POST" });
    showToast("Đã ngắt kết nối Google Drive.");
    await loadConnections({ force: true });
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

window.addEventListener("message", async (event) => {
  if (event.origin !== window.location.origin || event.data?.type !== "google-drive-oauth") return;
  showToast(event.data.message || (event.data.ok ? "Đã kết nối Google Drive." : "Kết nối Google Drive lỗi."), event.data.ok ? "success" : "error");
  await loadConnections({ force: true });
});

async function testConnection(code, button) {
  const resultBox = $(`#connection-result-${CSS.escape(code)}`);
  if (resultBox) resultBox.textContent = "";
  showToast("Đang kiểm tra kết nối...");
  setButtonLoading(button, true);
  try {
    const result = await api(`/api/admin/connections/${code}/test`, { method: "POST" });
    const details = result.details ? ` Chi tiết: ${JSON.stringify(result.details)}` : "";
    showToast(`${result.message}${details}`.slice(0, 360), result.ok ? "success" : "error");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadDataMining({ force = false } = {}) {
  const scheduleTable = $("#data-mining-schedules-table");
  const runsTable = $("#data-mining-runs-table");
  if (!scheduleTable || !runsTable) return;
  if (!force && isDataFresh("dataMining")) {
    renderDataMiningSchedules();
    renderDataMiningRuns();
    return;
  }
  setTableLoading("#data-mining-schedules-table", 7, "Đang tải lịch đào dữ liệu...");
  setTableLoading("#data-mining-runs-table", 5, "Đang tải nhật ký đào dữ liệu...");
  try {
    const [scheduleData, runData] = await Promise.all([
      api("/api/admin/data-mining/schedules"),
      api("/api/admin/data-mining/runs?limit=30"),
    ]);
    dataMiningSchedules = scheduleData.schedules || [];
    dataMiningRuns = runData.runs || [];
    markDataFresh("dataMining");
    renderDataMiningSchedules();
    renderDataMiningRuns();
  } catch (error) {
    scheduleTable.innerHTML = emptyRow(7, "Không tải được lịch đào dữ liệu", error.message);
    runsTable.innerHTML = emptyRow(5, "Không tải được nhật ký đào dữ liệu", error.message);
  }
}

function dataMiningScheduleText(schedule) {
  if (schedule.schedule_type === "Weekly") return `Hàng tuần ${schedule.weekday || "-"} lúc ${schedule.run_time || "-"}`;
  if (schedule.schedule_type === "Monthly") return `Ngày ${schedule.month_day || 1} hàng tháng lúc ${schedule.run_time || "-"}`;
  return `Hàng ngày lúc ${schedule.run_time || "-"}`;
}

function renderDataMiningSchedules() {
  const table = $("#data-mining-schedules-table");
  if (!table) return;
  table.innerHTML = dataMiningSchedules.length
    ? dataMiningSchedules.map((schedule) => renderDataMiningScheduleRow(schedule)).join("")
    : emptyRow(7, "Chưa có lịch đào dữ liệu", "Bấm Thêm lịch để cấu hình tự động lấy báo cáo OneBSS.");
  document.querySelectorAll("[data-edit-data-mining]").forEach((button) => button.addEventListener("click", () => openDataMiningSchedule(button.dataset.editDataMining)));
  document.querySelectorAll("[data-run-data-mining]").forEach((button) => button.addEventListener("click", () => runDataMiningScheduleNow(button.dataset.runDataMining, button)));
  document.querySelectorAll("[data-delete-data-mining]").forEach((button) => button.addEventListener("click", () => deleteDataMiningSchedule(button.dataset.deleteDataMining)));
}

function renderDataMiningScheduleRow(schedule) {
  const paramsText = JSON.stringify(schedule.parameters || {});
  const lastRun = schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString("vi-VN") : "";
  const fileText = schedule.file_name_template || "Theo tên báo cáo";
  const storageText = schedule.storage_link || "Lưu nội bộ";
  return `
    <tr>
      <td><strong>${escapeHtml(schedule.name || schedule.schedule_id)}</strong><small class="cell-note">${escapeHtml(schedule.report_url || "")}</small></td>
      <td>${escapeHtml(dataMiningScheduleText(schedule))}</td>
      <td><code>${escapeHtml(fileText)}</code><small class="cell-note">${escapeHtml(storageText)}</small></td>
      <td class="compact-code-cell">${renderCompactCode(paramsText)}</td>
      <td><span class="status ${schedule.is_active ? "viewer" : "inactive"}">${schedule.is_active ? "Đang bật" : "Tạm tắt"}</span>${schedule.last_status ? `<small class="cell-note">${escapeHtml(schedule.last_status)}</small>` : ""}${schedule.last_error ? `<small class="cell-note text-red-700">${escapeHtml(schedule.last_error)}</small>` : ""}</td>
      <td>${lastRun ? escapeHtml(lastRun) : "-"}${schedule.last_file_name ? `<small class="cell-note">${escapeHtml(schedule.last_file_name)}</small>` : ""}</td>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-data-mining="${escapeHtml(schedule.schedule_id)}">Sửa</button><button class="table-action" data-run-data-mining="${escapeHtml(schedule.schedule_id)}"><span class="button-label">Chạy thử</span><span class="spinner"></span></button><button class="table-action danger" data-delete-data-mining="${escapeHtml(schedule.schedule_id)}">Xóa</button></div></td>
    </tr>`;
}

function renderDataMiningRuns() {
  const table = $("#data-mining-runs-table");
  if (!table) return;
  table.innerHTML = dataMiningRuns.length
    ? dataMiningRuns.map((run) => renderDataMiningRunRow(run)).join("")
    : emptyRow(5, "Chưa có lượt chạy", "Khi lịch chạy hoặc bấm Chạy thử, kết quả sẽ xuất hiện ở đây.");
}

function renderDataMiningRunRow(run) {
  const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
  const ok = run.status === "success";
  const storageLink = run.storage_link && /^https?:\/\//.test(run.storage_link)
    ? `<small class="cell-note"><a href="${escapeHtml(run.storage_link)}" target="_blank" rel="noopener">Mở file lưu trữ</a></small>`
    : "";
  const file = run.file_path ? `<code>${escapeHtml(run.file_name || run.file_path)}</code><small class="cell-note">${escapeHtml(run.file_path)}</small>${storageLink}` : (storageLink || "-");
  return `
    <tr>
      <td>${escapeHtml(startedAt)}</td>
      <td><code>${escapeHtml(run.schedule_id || "")}</code><small class="cell-note">${escapeHtml(run.run_id || "")}</small></td>
      <td><span class="status ${ok ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
      <td>${file}${run.storage_status ? `<small class="cell-note">${escapeHtml(run.storage_status)}</small>` : ""}</td>
      <td>${escapeHtml(run.message || "")}</td>
    </tr>`;
}

function openDataMiningSchedule(scheduleId = "") {
  const schedule = dataMiningSchedules.find((item) => item.schedule_id === scheduleId);
  const form = $("#data-mining-form");
  if (!form) return;
  form.elements.namedItem("schedule_id").value = schedule?.schedule_id || "";
  form.elements.namedItem("name").value = schedule?.name || "";
  form.elements.namedItem("report_url").value = schedule?.report_url || "";
  form.elements.namedItem("schedule_type").value = schedule?.schedule_type || "Daily";
  form.elements.namedItem("run_time").value = schedule?.run_time || "07:00";
  form.elements.namedItem("weekday").value = schedule?.weekday || "";
  form.elements.namedItem("month_day").value = schedule?.month_day || 1;
  form.elements.namedItem("storage_link").value = schedule?.storage_link || "";
  form.elements.namedItem("file_name_template").value = schedule?.file_name_template || "";
  form.elements.namedItem("parameters_json").value = JSON.stringify(schedule?.parameters || {}, null, 2);
  form.elements.namedItem("is_active").checked = schedule ? Boolean(schedule.is_active) : true;
  form.querySelector(".result").className = "result hidden";
  $("#data-mining-dialog")?.showModal();
}

async function saveDataMiningSchedule(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  let parameters = {};
  try {
    parameters = data.parameters_json ? JSON.parse(data.parameters_json) : {};
  } catch {
    showMessage(form.querySelector(".result"), "Tham số JSON chưa đúng định dạng.", "error");
    return;
  }
  try {
    await api("/api/admin/data-mining/schedules", { method: "POST", body: JSON.stringify({
      schedule_id: data.schedule_id || "",
      name: data.name || "",
      report_url: data.report_url || "",
      schedule_type: data.schedule_type || "Daily",
      run_time: data.run_time || "07:00",
      weekday: data.weekday || "",
      month_day: Number(data.month_day || 1),
      storage_link: data.storage_link || "",
      file_name_template: data.file_name_template || "",
      parameters,
      is_active: Boolean(form.elements.namedItem("is_active")?.checked),
    })});
    $("#data-mining-dialog")?.close();
    showMessage($("#data-mining-result"), "Đã lưu lịch đào dữ liệu.");
    showToast("Đã lưu lịch đào dữ liệu.");
    await loadDataMining({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
    showToast(error.message, "error");
  }
}

async function runDataMiningScheduleNow(scheduleId, button) {
  const schedule = dataMiningSchedules.find((item) => item.schedule_id === scheduleId);
  const otp = prompt("Nhập OTP OneBSS nếu đang có mã. Có thể để trống nếu phiên OneBSS còn hiệu lực.");
  if (otp === null) return;
  const defaultParameters = JSON.stringify(schedule?.parameters || {}, null, 2);
  const parametersText = prompt("Nhập JSON tham số cho lần chạy này. Để trống nếu muốn dùng tham số trong lịch.", defaultParameters);
  if (parametersText === null) return;
  let parameters = {};
  try {
    parameters = parametersText.trim() ? JSON.parse(parametersText) : {};
  } catch {
    showMessage($("#data-mining-result"), "Tham số JSON chạy thử chưa đúng định dạng.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    const response = await api(`/api/admin/data-mining/schedules/${encodeURIComponent(scheduleId)}/run-now`, {
      method: "POST",
      body: JSON.stringify({ otp, allow_device_registration: true, parameters }),
    });
    const message = response.result?.message || (response.ok ? "Đã chạy lịch đào dữ liệu." : "Chưa chạy xong lịch đào dữ liệu.");
    showMessage($("#data-mining-result"), message, response.ok ? "success" : "error");
    await loadDataMining({ force: true });
  } catch (error) {
    showMessage($("#data-mining-result"), error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteDataMiningSchedule(scheduleId) {
  if (!confirm(`Xóa lịch đào dữ liệu ${scheduleId}?`)) return;
  try {
    await api(`/api/admin/data-mining/schedules/${encodeURIComponent(scheduleId)}`, { method: "DELETE" });
    showMessage($("#data-mining-result"), `Đã xóa lịch ${scheduleId}.`);
    await loadDataMining({ force: true });
  } catch (error) {
    showMessage($("#data-mining-result"), error.message, "error");
  }
}

async function loadZaloAutoMessages({ force = false } = {}) {
  const table = $("#zalo-auto-messages-table");
  if (!table) return;
  if (!force && isDataFresh("zaloAutoMessages")) {
    renderZaloAutoMessages();
    fillZaloAutoMessagePickers();
    return;
  }
  if (zaloAutoMessages.length && !force) renderZaloAutoMessages();
  if (!zaloAutoMessages.length || force) setTableLoading("#zalo-auto-messages-table", 6, "Đang tải lịch gửi Zalo...");
  try {
    const data = await api("/api/admin/zalo/auto-messages");
    zaloAutoMessages = data.schedules || [];
    markDataFresh("zaloAutoMessages");
    renderZaloAutoMessages();
    fillZaloAutoMessagePickers();
  } catch (error) {
    table.innerHTML = emptyRow(6, "Không tải được lịch gửi Zalo", error.message);
  }
}

function fillZaloAutoMessagePickers() {
  const picker = $("#dashboard-zalo-schedule-picker");
  if (!picker) return;
  const current = picker.value;
  const options = zaloAutoMessages
    .filter((schedule) => schedule.is_active)
    .map((schedule) => `<option value="${escapeHtml(schedule.schedule_id)}">${escapeHtml(schedule.name || schedule.schedule_id)}</option>`)
    .join("");
  picker.innerHTML = `<option value="">Lịch Zalo</option>${options}`;
  if (current && zaloAutoMessages.some((schedule) => schedule.schedule_id === current)) picker.value = current;
}

function zaloScheduleText(schedule) {
  if (schedule.schedule_type === "TimeWindow") return `Khung giờ: ${(schedule.time_slots || []).join(", ") || "-"}`;
  if (schedule.schedule_type === "Weekly") return `Hàng tuần ${schedule.weekday || "-"} lúc ${schedule.run_time || "-"}`;
  if (schedule.schedule_type === "Monthly") return `Ngày ${schedule.month_day || 1} hằng tháng lúc ${schedule.run_time || "-"}`;
  return `Hằng ngày lúc ${schedule.run_time || "-"}`;
}

function renderZaloAutoMessages() {
  const table = $("#zalo-auto-messages-table");
  if (!table) return;
  table.innerHTML = zaloAutoMessages.length
    ? zaloAutoMessages.map((schedule) => renderZaloAutoMessageRow(schedule)).join("")
    : emptyRow(6, "Chưa có lịch gửi Zalo", "Bấm Thêm lịch để cấu hình lịch gửi ảnh chụp tự động.");
  document.querySelectorAll("[data-edit-zalo-auto-message]").forEach((button) => button.addEventListener("click", () => openZaloAutoMessage(button.dataset.editZaloAutoMessage)));
  document.querySelectorAll("[data-send-zalo-auto-message]").forEach((button) => button.addEventListener("click", () => sendZaloAutoMessageNow(button.dataset.sendZaloAutoMessage, button)));
  document.querySelectorAll("[data-delete-zalo-auto-message]").forEach((button) => button.addEventListener("click", () => deleteZaloAutoMessage(button.dataset.deleteZaloAutoMessage)));
}

function renderZaloAutoMessageRow(schedule) {
  const targetText = [schedule.target_type === "person" ? "Cá nhân" : "Nhóm", schedule.chat_name, schedule.chat_id].filter(Boolean).join(" · ") || "Dùng chat mới nhất";
  const imageText = schedule.latest_capture_url ? "Lần chụp gần nhất" : "Tự chụp mới khi gửi";
  const lastSent = schedule.last_sent_at ? new Date(schedule.last_sent_at).toLocaleString("vi-VN") : "";
  return `
    <tr>
      <td><strong>${escapeHtml(schedule.name || schedule.schedule_id)}</strong><small class="cell-note">${escapeHtml(schedule.page_label || schedule.page_url || "/")}</small></td>
      <td>${escapeHtml(zaloScheduleText(schedule))}</td>
      <td><code>${escapeHtml(targetText)}</code></td>
      <td>${escapeHtml(imageText)}${schedule.latest_capture?.created_at ? `<small class="cell-note">${escapeHtml(new Date(schedule.latest_capture.created_at).toLocaleString("vi-VN"))}</small>` : ""}</td>
      <td><span class="status ${schedule.is_active ? "viewer" : "inactive"}">${schedule.is_active ? "Đang chạy" : "Tạm tắt"}</span>${lastSent ? `<small class="cell-note">Đã gửi: ${escapeHtml(lastSent)}</small>` : ""}${schedule.last_error ? `<small class="cell-note text-red-700">${escapeHtml(schedule.last_error)}</small>` : ""}</td>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-zalo-auto-message="${escapeHtml(schedule.schedule_id)}">Sửa</button><button class="table-action" data-send-zalo-auto-message="${escapeHtml(schedule.schedule_id)}"><span class="button-label">Gửi thử</span><span class="spinner"></span></button><button class="table-action danger" data-delete-zalo-auto-message="${escapeHtml(schedule.schedule_id)}">Xóa</button></div></td>
    </tr>`;
}

function openZaloAutoMessage(scheduleId = "") {
  const schedule = zaloAutoMessages.find((item) => item.schedule_id === scheduleId);
  const form = $("#zalo-auto-message-form");
  form.elements.namedItem("schedule_id").value = schedule?.schedule_id || "";
  form.elements.namedItem("name").value = schedule?.name || "";
  form.elements.namedItem("page_url").value = schedule?.page_url || window.location.pathname || "/";
  form.elements.namedItem("page_label").value = schedule?.page_label || "";
  form.elements.namedItem("schedule_type").value = schedule?.schedule_type || "Daily";
  form.elements.namedItem("time_slots").value = (schedule?.time_slots || []).join(", ");
  form.elements.namedItem("run_time").value = schedule?.run_time || "07:00";
  form.elements.namedItem("weekday").value = schedule?.weekday || "";
  form.elements.namedItem("month_day").value = schedule?.month_day || 1;
  form.elements.namedItem("target_type").value = schedule?.target_type || "group";
  form.elements.namedItem("chat_id").value = schedule?.chat_id || "";
  form.elements.namedItem("chat_name").value = schedule?.chat_name || "";
  form.elements.namedItem("caption").value = schedule?.caption || "";
  form.elements.namedItem("photo_url").value = schedule?.photo_url || "";
  form.elements.namedItem("capture_file").value = "";
  form.elements.namedItem("is_active").checked = schedule ? Boolean(schedule.is_active) : true;
  form.querySelector(".result").className = "result hidden";
  $("#zalo-auto-message-dialog").showModal();
}

function zaloTimeSlotsToArray(value) {
  return String(value || "").split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean);
}

async function saveZaloAutoMessage(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const file = form.elements.namedItem("capture_file")?.files?.[0];
  try {
    const response = await api("/api/admin/zalo/auto-messages", { method: "POST", body: JSON.stringify({
      schedule_id: data.schedule_id || "",
      name: data.name || "",
      page_url: data.page_url || "/",
      page_label: data.page_label || "",
      schedule_type: data.schedule_type || "Daily",
      time_slots: zaloTimeSlotsToArray(data.time_slots),
      run_time: data.run_time || "07:00",
      weekday: data.weekday || "",
      month_day: Number(data.month_day || 1),
      target_type: data.target_type || "group",
      chat_id: data.chat_id || "",
      chat_name: data.chat_name || "",
      caption: data.caption || "",
      photo_url: data.photo_url || "",
      is_active: Boolean(form.elements.namedItem("is_active")?.checked),
    })});
    if (file) await uploadZaloAutoMessageCapture(response.schedule.schedule_id, file, data.page_url || "/");
    $("#zalo-auto-message-dialog").close();
    showMessage($("#zalo-auto-message-result"), "Đã lưu lịch gửi Zalo.");
    showToast("Đã lưu lịch gửi Zalo.");
    await loadZaloAutoMessages({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
    showToast(error.message, "error");
  }
}

async function uploadZaloAutoMessageCapture(scheduleId, blob, pageUrl = "") {
  const dataUrl = await blobToDataUrl(blob);
  return api(`/api/admin/zalo/auto-messages/${encodeURIComponent(scheduleId)}/captures`, {
    method: "POST",
    body: JSON.stringify({
      image_base64: dataUrl,
      mime_type: blob.type || "image/png",
      page_url: pageUrl || window.location.pathname || "/",
    }),
  });
}

async function sendZaloAutoMessageNow(scheduleId, button) {
  setButtonLoading(button, true);
  try {
    const result = await api(`/api/admin/zalo/auto-messages/${encodeURIComponent(scheduleId)}/send-now`, { method: "POST" });
    showMessage($("#zalo-auto-message-result"), `${result.message} Chat ID: ${result.chat_id}`);
    await Promise.all([loadZaloAutoMessages({ force: true }), loadZaloMessageLogs()]);
  } catch (error) {
    showMessage($("#zalo-auto-message-result"), error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteZaloAutoMessage(scheduleId) {
  if (!confirm(`Xóa lịch gửi Zalo ${scheduleId}?`)) return;
  try {
    await api(`/api/admin/zalo/auto-messages/${encodeURIComponent(scheduleId)}`, { method: "DELETE" });
    showMessage($("#zalo-auto-message-result"), `Đã xóa lịch ${scheduleId}.`);
    await loadZaloAutoMessages({ force: true });
  } catch (error) {
    showMessage($("#zalo-auto-message-result"), error.message, "error");
  }
}

async function loadZaloMessageLogs() {
  const table = $("#zalo-message-logs-table");
  if (!table) return;
  setTableLoading("#zalo-message-logs-table", 5, "Đang tải nhật ký Zalo Bot...");
  try {
    const data = await api("/api/admin/zalo/message-logs?limit=100");
    const logs = data.logs || [];
    table.innerHTML = logs.length
      ? logs.map((log) => renderZaloMessageLog(log)).join("")
      : emptyRow(5, "Chưa có tin nhắn Zalo", "Khi người dùng mention hoặc trả lời bot trong nhóm, log sẽ xuất hiện ở đây.");
  } catch (error) {
    table.innerHTML = emptyRow(5, "Không tải được nhật ký Zalo", error.message);
  }
}

function renderZaloMessageLog(log) {
  const directionLabel = log.direction === "out" ? "Bot gửi" : "Bot nhận";
  const directionClass = log.direction === "out" ? "admin" : "viewer";
  const chatParts = [log.chat_type, log.chat_id].filter(Boolean);
  const sender = log.sender_name || log.sender_id || "";
  const chatText = chatParts.length ? chatParts.join(" · ") : "-";
  const bodyText = log.text || log.raw_preview || "-";
  const keyNote = [log.raw_keys?.length ? `root: ${log.raw_keys.join(", ")}` : "", log.result_keys?.length ? `result: ${log.result_keys.join(", ")}` : "", log.message_keys?.length ? `message: ${log.message_keys.join(", ")}` : ""].filter(Boolean).join(" | ");
  return `
    <tr>
      <td>${log.created_at ? new Date(log.created_at).toLocaleString("vi-VN") : "-"}</td>
      <td><span class="status ${directionClass}">${directionLabel}</span></td>
      <td><code>${escapeHtml(chatText)}</code>${sender ? `<small class="cell-note">${escapeHtml(sender)}</small>` : ""}</td>
      <td class="compact-code-cell"><pre class="compact-code">${escapeHtml(bodyText)}</pre>${keyNote ? `<small class="cell-note">${escapeHtml(keyNote)}</small>` : ""}</td>
      <td><span class="status ${log.ok ? "viewer" : "inactive"}">${log.ok ? "OK" : "Lỗi"}</span></td>
    </tr>`;
}

async function sendZaloTestMessage(button) {
  const resultBox = $("#zalo-send-test-result");
  setButtonLoading(button, true);
  try {
    const response = await api("/api/admin/zalo/send-test-message", {
      method: "POST",
      body: JSON.stringify({ text: "Tin nhan test tu Bot VNPT Can Tho." }),
    });
    showMessage(resultBox, `${response.message} Chat ID: ${response.chat_id}`);
    await loadZaloMessageLogs();
  } catch (error) {
    showMessage(resultBox, error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadSqlReports({ force = false } = {}) {
  if (!force && isDataFresh("sqlReports")) {
    renderSqlReports();
    fillDynamicReportSelect();
    return;
  }
  if (sqlReports.length && !force) {
    renderSqlReports();
    fillDynamicReportSelect();
  }
  if (!sqlReports.length || force) renderSqlReportEditorLoading("Đang tải cấu hình SQL...");
  try {
    const data = await api("/api/admin/sql-reports");
    sqlReports = data.reports || [];
    markDataFresh("sqlReports");
    renderSqlReports();
    fillDynamicReportSelect();
    if (dashboardBuilderLayout) {
      collectDashboardBuilderStateFromDom();
      renderDashboardBuilder();
    }
    if (dashboardViewerLayout) renderDashboardViewer();
  } catch (error) {
    showMessage($("#sql-reports-message"), error.message, "error");
    const editor = $("#sql-report-editor");
    if (editor) editor.innerHTML = `<div class="empty-state"><div><strong>Không tải được cấu hình SQL</strong><p>${escapeHtml(error.message)}</p></div></div>`;
  }
}

function renderSqlReports() {
  const editor = $("#sql-report-editor");
  if (!editor) return;
  refreshSqlReportPicker();
  const pickedCode = $("#sql-report-picker")?.value || "";
  const selectedReport = pickedCode ? sqlReports.find((report) => report.ma_bao_cao === pickedCode) : null;
  const draft = sqlReportDrafts[0] || createSqlReportDraft();
  editor.innerHTML = renderSqlReportEditor(selectedReport || draft, !selectedReport);
  document.querySelectorAll("[data-inline-sql-field]").forEach((field) => {
    field.addEventListener("input", () => markSqlReportDirty(field.closest("[data-sql-row]")));
  });
  document.querySelectorAll("[data-save-sql-report-inline]").forEach((button) => {
    button.addEventListener("click", () => saveInlineSqlReport(button.dataset.saveSqlReportInline, button));
  });
  document.querySelectorAll("[data-delete-sql-report]").forEach((button) => {
    button.addEventListener("click", () => deleteInlineSqlReport(button.dataset.deleteSqlReport));
  });
}

function renderSqlReportEditorLoading(text) {
  const editor = $("#sql-report-editor");
  if (editor) editor.innerHTML = `<div class="loading-row">${escapeHtml(text)}</div>`;
}

function refreshSqlReportPicker() {
  const picker = $("#sql-report-picker");
  if (!picker) return;
  const search = ($("#sql-report-search")?.value || "").trim().toLowerCase();
  const current = picker.value;
  const filteredReports = sqlReports.filter((report) => {
    if (!search) return true;
    const text = [report.ten_bao_cao, report.ma_bao_cao, ...(report.cac_tham_so || [])].join(" ").toLowerCase();
    return text.includes(search);
  });
  picker.innerHTML = `<option value="">Thêm SQL mới / chưa chọn SQL</option>${filteredReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")}`;
  if (current && filteredReports.some((report) => report.ma_bao_cao === current)) picker.value = current;
}

function createSqlReportDraft() {
  const draft = {
    _draft: true,
    _rowKey: "draft-new-sql-report",
    id: "",
    ten_bao_cao: "",
    ma_bao_cao: "",
    cau_lenh_sql: "SELECT 1 AS GIA_TRI;",
    cac_tham_so: [],
  };
  sqlReportDrafts = [draft];
  return draft;
}

function renderSqlReportEditor(report, isDraft = false) {
  const rowKey = report._rowKey || `sql-${report.id}`;
  const params = (report.cac_tham_so || []).join(", ");
  return `
    <div class="sql-report-editor-card" data-sql-row="${escapeHtml(rowKey)}" data-sql-report-id="${escapeHtml(report.id || "")}">
      <div class="section-heading">
        <div><p class="eyebrow">${isDraft ? "Thêm SQL" : "Chỉnh SQL"}</p><h3>${isDraft ? "Tạo lệnh SQL mới" : escapeHtml(report.ten_bao_cao || report.ma_bao_cao)}</h3></div>
        <div class="action-group"><button class="table-action ${isDraft ? "" : "hidden"}" data-save-sql-report-inline="${escapeHtml(rowKey)}">Lưu</button>${isDraft ? "" : `<button class="table-action danger" data-delete-sql-report="${escapeHtml(rowKey)}">Xóa</button>`}</div>
      </div>
      <label>Tên<input class="form-control inline-admin-input" data-inline-sql-field="ten_bao_cao" value="${escapeHtml(report.ten_bao_cao || "")}" placeholder="Tên báo cáo" /></label>
      <label>Mã<input class="form-control inline-admin-input" data-inline-sql-field="ma_bao_cao" value="${escapeHtml(report.ma_bao_cao || "")}" placeholder="VD: BC_THUE_BAO" /></label>
      <label>Danh sách biến<input class="form-control inline-admin-input inline-admin-params" data-inline-sql-field="cac_tham_so" value="${escapeHtml(params)}" placeholder="LOAIHINH, MONTH, DONVI" /><small class="cell-note">Mỗi biến cách nhau bằng dấu phẩy.</small></label>
      <label>Bảng lệnh<textarea class="form-control inline-admin-code sql-report-editor-code" data-inline-sql-field="cau_lenh_sql" rows="16" placeholder="SELECT ...;">${escapeHtml(report.cau_lenh_sql || "")}</textarea></label>
    </div>`;
}

function markSqlReportDirty(row) {
  row?.querySelector("[data-save-sql-report-inline]")?.classList.remove("hidden");
}

function addInlineSqlReport() {
  sqlReportDrafts = [createSqlReportDraft()];
  if ($("#sql-report-picker")) $("#sql-report-picker").value = "";
  if ($("#sql-report-search")) $("#sql-report-search").value = "";
  renderSqlReports();
  document.querySelector('[data-sql-row="draft-new-sql-report"]')?.querySelector("input")?.focus();
}

async function saveInlineSqlReport(rowKey, button) {
  const row = document.querySelector(`[data-sql-row="${CSS.escape(rowKey)}"]`);
  if (!row) return;
  const params = (row.querySelector('[data-inline-sql-field="cac_tham_so"]')?.value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const payload = {
    id: row.dataset.sqlReportId ? Number(row.dataset.sqlReportId) : null,
    ten_bao_cao: row.querySelector('[data-inline-sql-field="ten_bao_cao"]')?.value.trim() || "",
    ma_bao_cao: row.querySelector('[data-inline-sql-field="ma_bao_cao"]')?.value.trim() || "",
    cau_lenh_sql: row.querySelector('[data-inline-sql-field="cau_lenh_sql"]')?.value || "",
    cac_tham_so: params,
  };
  if (!payload.ten_bao_cao || !payload.ma_bao_cao || !payload.cau_lenh_sql.trim()) {
    showToast("Vui lòng nhập đủ tên, mã và bảng lệnh SQL.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    await api("/api/admin/sql-reports", { method: "POST", body: JSON.stringify(payload) });
    sqlReportDrafts = sqlReportDrafts.filter((item) => item._rowKey !== rowKey);
    showMessage($("#sql-reports-message"), "Đã lưu cấu hình SQL.");
    showToast("Đã lưu cấu hình SQL.");
    await loadSqlReports({ force: true });
    const picker = $("#sql-report-picker");
    if (picker && sqlReports.some((report) => report.ma_bao_cao === payload.ma_bao_cao)) {
      picker.value = payload.ma_bao_cao;
      renderSqlReports();
    }
  } catch (error) {
    showMessage($("#sql-reports-message"), error.message, "error");
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteInlineSqlReport(rowKey) {
  if (rowKey.startsWith("draft-")) {
    sqlReportDrafts = sqlReportDrafts.filter((item) => item._rowKey !== rowKey);
    renderSqlReports();
    return;
  }
  const row = document.querySelector(`[data-sql-row="${CSS.escape(rowKey)}"]`);
  const reportId = row?.dataset.sqlReportId;
  if (reportId) await deleteSqlReport(reportId);
}

function openSqlReport(reportId) {
  const report = sqlReports.find((item) => String(item.id) === String(reportId));
  const form = $("#sql-report-form");
  if (!form) return;
  form.reset();
  form.elements.namedItem("id").value = report?.id || "";
  form.elements.namedItem("ten_bao_cao").value = report?.ten_bao_cao || "";
  form.elements.namedItem("ma_bao_cao").value = report?.ma_bao_cao || "";
  form.elements.namedItem("cau_lenh_sql").value = report?.cau_lenh_sql || "";
  form.elements.namedItem("cac_tham_so").value = (report?.cac_tham_so || []).join(", ");
  form.querySelector(".result").className = "result hidden";
  $("#sql-report-dialog")?.showModal();
}

async function saveSqlReport(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const params = String(data.cac_tham_so || "").split(",").map((item) => item.trim()).filter(Boolean);
  try {
    await api("/api/admin/sql-reports", { method: "POST", body: JSON.stringify({
      id: data.id ? Number(data.id) : null,
      ten_bao_cao: data.ten_bao_cao,
      ma_bao_cao: data.ma_bao_cao,
      cau_lenh_sql: data.cau_lenh_sql,
      cac_tham_so: params,
    })});
    $("#sql-report-dialog")?.close();
    showMessage($("#sql-reports-message"), "Đã lưu cấu hình SQL.");
    showToast("Đã lưu cấu hình SQL.");
    await loadSqlReports({ force: true });
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteSqlReport(reportId) {
  if (!confirm("Xóa cấu hình SQL này?")) return;
  try {
    await api(`/api/admin/sql-reports/${reportId}`, { method: "DELETE" });
    showMessage($("#sql-reports-message"), "Đã xóa cấu hình SQL.");
    await loadSqlReports({ force: true });
  } catch (error) {
    showMessage($("#sql-reports-message"), error.message, "error");
  }
}

async function loadOneBssReports({ force = false } = {}) {
  if (!force && isDataFresh("oneBssReports")) {
    renderOneBssReports();
    fillOneBssRunSelect();
    return;
  }
  if (oneBssReports.length && !force) {
    renderOneBssReports();
    fillOneBssRunSelect();
  }
  if (!oneBssReports.length || force) renderOneBssReportEditorLoading("Đang tải cấu hình OneBSS...");
  try {
    const data = await api("/api/admin/onebss-reports");
    oneBssReports = data.reports || [];
    markDataFresh("oneBssReports");
    renderOneBssReports();
    fillOneBssRunSelect();
  } catch (error) {
    showMessage($("#onebss-reports-message"), error.message, "error");
    const editor = $("#onebss-report-editor");
    if (editor) editor.innerHTML = `<div class="empty-state"><div><strong>Không tải được cấu hình OneBSS</strong><p>${escapeHtml(error.message)}</p></div></div>`;
  }
}

function renderOneBssReports() {
  const editor = $("#onebss-report-editor");
  if (!editor) return;
  refreshOneBssReportPicker();
  const pickedCode = $("#onebss-report-picker")?.value || "";
  const selectedReport = pickedCode ? oneBssReports.find((report) => report.ma_bao_cao === pickedCode) : null;
  const draft = oneBssReportDrafts[0] || createOneBssReportDraft();
  editor.innerHTML = renderOneBssReportEditor(selectedReport || draft, !selectedReport);
  ensureOneBssOtpServiceCodeField(editor, selectedReport || draft);
  document.querySelectorAll("[data-inline-onebss-field]").forEach((field) => {
    field.addEventListener("input", () => markOneBssReportDirty(field.closest("[data-onebss-row]")));
  });
  document.querySelectorAll("[data-save-onebss-report-inline]").forEach((button) => {
    button.addEventListener("click", () => saveInlineOneBssReport(button.dataset.saveOnebssReportInline, button));
  });
  document.querySelectorAll("[data-delete-onebss-report]").forEach((button) => {
    button.addEventListener("click", () => deleteInlineOneBssReport(button.dataset.deleteOnebssReport));
  });
}

function ensureOneBssOtpServiceCodeField(editor, report) {
  const row = editor?.querySelector("[data-onebss-row]");
  if (!row || row.querySelector('[data-inline-onebss-field="otp_service_code"]')) return;
  const before = row.querySelector('[data-inline-onebss-field="danh_sach_bien"]')?.closest("label");
  const label = document.createElement("label");
  label.innerHTML = `Ma OTP tu dong<input class="form-control inline-admin-input" data-inline-onebss-field="otp_service_code" value="${escapeHtml(report?.otp_service_code || "onebss")}" placeholder="onebss" /><small class="cell-note">Nhap dung Ma OTP trong Mobile Gateway. OneBSS chi goi ma nay; nguoi gui, so ky tu va vi tri cat lay theo cau hinh OTP Mobile Gateway.</small>`;
  row.insertBefore(label, before || null);
}

function renderOneBssReportEditorLoading(text) {
  const editor = $("#onebss-report-editor");
  if (editor) editor.innerHTML = `<div class="loading-row">${escapeHtml(text)}</div>`;
}

function refreshOneBssReportPicker() {
  const picker = $("#onebss-report-picker");
  if (!picker) return;
  const search = ($("#onebss-report-search")?.value || "").trim().toLowerCase();
  const current = picker.value;
  const filteredReports = oneBssReports.filter((report) => {
    if (!search) return true;
    const text = [report.ten_bao_cao, report.ma_bao_cao, report.report_url, report.storage_link, JSON.stringify(report.parameters || {}), ...(report.danh_sach_bien || [])].join(" ").toLowerCase();
    return text.includes(search);
  });
  picker.innerHTML = `<option value="">Thêm báo cáo mới / chưa chọn báo cáo</option>${filteredReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")}`;
  if (current && filteredReports.some((report) => report.ma_bao_cao === current)) picker.value = current;
}

function createOneBssReportDraft() {
  const draft = {
    _draft: true,
    _rowKey: "draft-new-onebss-report",
    id: "",
    ma_bao_cao: "",
    ten_bao_cao: "",
    danh_sach_bien: ["P_PHANVUNG_ID", "P_LOAI_NGAY", "P_TUNGAY", "P_DENNGAY", "P_LOAI_BAOCAO", "P_LOAI_BIENDONG"],
    parameters: {
      P_PHANVUNG_ID: { $each: ["13", "14", "15"] },
      P_LOAI_NGAY: "1",
      P_TUNGAY: "{{month_start}}",
      P_DENNGAY: "{{today}}",
      P_LOAI_BAOCAO: "2",
      P_LOAI_BIENDONG: "1",
      $merge_excel: { sheet: "DATA", source_column: "P_PHANVUNG_ID" },
    },
    otp_service_code: "onebss",
    report_url: "",
    storage_link: "",
  };
  oneBssReportDrafts = [draft];
  return draft;
}

function renderOneBssReportEditor(report, isDraft = false) {
  const rowKey = report._rowKey || `onebss-${report.id}`;
  const params = (report.danh_sach_bien || []).join(", ");
  const parameterJson = JSON.stringify(report.parameters || {}, null, 2);
  return `
    <div class="sql-report-editor-card" data-onebss-row="${escapeHtml(rowKey)}" data-onebss-report-id="${escapeHtml(report.id || "")}">
      <div class="section-heading">
        <div><p class="eyebrow">${isDraft ? "Thêm báo cáo OneBSS" : "Chỉnh báo cáo OneBSS"}</p><h3>${isDraft ? "Tạo cấu hình báo cáo mới" : escapeHtml(report.ten_bao_cao || report.ma_bao_cao)}</h3></div>
        <div class="action-group"><button class="table-action ${isDraft ? "" : "hidden"}" data-save-onebss-report-inline="${escapeHtml(rowKey)}">Lưu</button>${isDraft ? "" : `<button class="table-action danger" data-delete-onebss-report="${escapeHtml(rowKey)}">Xóa</button>`}</div>
      </div>
      <label>Mã báo cáo<input class="form-control inline-admin-input" data-inline-onebss-field="ma_bao_cao" value="${escapeHtml(report.ma_bao_cao || "")}" placeholder="Tự sinh nếu để trống" /></label>
      <label>Tên báo cáo<input class="form-control inline-admin-input" data-inline-onebss-field="ten_bao_cao" value="${escapeHtml(report.ten_bao_cao || "")}" placeholder="Tên báo cáo OneBSS" /></label>
      <label>Danh sách biến<input class="form-control inline-admin-input inline-admin-params" data-inline-onebss-field="danh_sach_bien" value="${escapeHtml(params)}" placeholder="P_PHANVUNG_ID, P_LOAI_NGAY, P_TUNGAY, P_DENNGAY, P_LOAI_BAOCAO, P_LOAI_BIENDONG" /><small class="cell-note">Mỗi biến cách nhau bằng dấu phẩy.</small></label>
      <label>Tham số xuất trực tiếp JSON<textarea class="form-control inline-admin-input font-mono text-xs" data-inline-onebss-field="parameters" rows="9" placeholder='{"P_PHANVUNG_ID":{"$each":["13","14","15"]},"P_TUNGAY":"{{month_start}}","P_DENNGAY":"{{today}}"}'>${escapeHtml(parameterJson === "{}" ? "" : parameterJson)}</textarea><small class="cell-note">Lưu điều kiện xuất ở đây để khi chạy chỉ cần bấm Lấy báo cáo.</small></label>
      <label>Link lấy báo cáo<input class="form-control inline-admin-input" data-inline-onebss-field="report_url" value="${escapeHtml(report.report_url || "")}" placeholder="https://onebss.vnpt.vn/#/report/bi?..." /></label>
      <label>Link lưu báo cáo<input class="form-control inline-admin-input" data-inline-onebss-field="storage_link" value="${escapeHtml(report.storage_link || "")}" placeholder="Link thư mục Google Drive hoặc thư mục nội bộ" /></label>
    </div>`;
}

function markOneBssReportDirty(row) {
  row?.querySelector("[data-save-onebss-report-inline]")?.classList.remove("hidden");
}

function addInlineOneBssReport() {
  oneBssReportDrafts = [createOneBssReportDraft()];
  if ($("#onebss-report-picker")) $("#onebss-report-picker").value = "";
  if ($("#onebss-report-search")) $("#onebss-report-search").value = "";
  renderOneBssReports();
  document.querySelector('[data-onebss-row="draft-new-onebss-report"]')?.querySelector("input")?.focus();
}

async function saveInlineOneBssReport(rowKey, button) {
  const row = document.querySelector(`[data-onebss-row="${CSS.escape(rowKey)}"]`);
  if (!row) return;
  const variables = (row.querySelector('[data-inline-onebss-field="danh_sach_bien"]')?.value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  let parameters = {};
  const parameterText = row.querySelector('[data-inline-onebss-field="parameters"]')?.value.trim() || "";
  if (parameterText) {
    try {
      parameters = JSON.parse(parameterText);
    } catch {
      showToast("Tham số xuất trực tiếp JSON chưa đúng định dạng.", "error");
      return;
    }
  }
  const payload = {
    id: row.dataset.onebssReportId ? Number(row.dataset.onebssReportId) : null,
    ma_bao_cao: row.querySelector('[data-inline-onebss-field="ma_bao_cao"]')?.value.trim() || "",
    ten_bao_cao: row.querySelector('[data-inline-onebss-field="ten_bao_cao"]')?.value.trim() || "",
    danh_sach_bien: variables,
    parameters,
    otp_service_code: row.querySelector('[data-inline-onebss-field="otp_service_code"]')?.value.trim().toLowerCase() || "onebss",
    report_url: row.querySelector('[data-inline-onebss-field="report_url"]')?.value.trim() || "",
    storage_link: row.querySelector('[data-inline-onebss-field="storage_link"]')?.value.trim() || "",
  };
  if (!payload.ten_bao_cao || !payload.report_url) {
    showToast("Vui lòng nhập tên báo cáo và link lấy báo cáo OneBSS.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    const response = await api("/api/admin/onebss-reports", { method: "POST", body: JSON.stringify(payload) });
    oneBssReportDrafts = oneBssReportDrafts.filter((item) => item._rowKey !== rowKey);
    markDataStale("oneBssReports", "oneBssMining");
    showMessage($("#onebss-reports-message"), "Đã lưu cấu hình OneBSS.");
    showToast("Đã lưu cấu hình OneBSS.");
    await loadOneBssReports({ force: true });
    const picker = $("#onebss-report-picker");
    if (picker && response.ma_bao_cao) {
      picker.value = response.ma_bao_cao;
      renderOneBssReports();
    }
  } catch (error) {
    showMessage($("#onebss-reports-message"), error.message, "error");
    showToast(error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteInlineOneBssReport(rowKey) {
  if (rowKey.startsWith("draft-")) {
    oneBssReportDrafts = oneBssReportDrafts.filter((item) => item._rowKey !== rowKey);
    renderOneBssReports();
    return;
  }
  const row = document.querySelector(`[data-onebss-row="${CSS.escape(rowKey)}"]`);
  const reportId = row?.dataset.onebssReportId;
  if (!reportId || !confirm("Xóa cấu hình báo cáo OneBSS này?")) return;
  try {
    await api(`/api/admin/onebss-reports/${reportId}`, { method: "DELETE" });
    markDataStale("oneBssReports", "oneBssMining");
    showMessage($("#onebss-reports-message"), "Đã xóa cấu hình OneBSS.");
    await loadOneBssReports({ force: true });
  } catch (error) {
    showMessage($("#onebss-reports-message"), error.message, "error");
  }
}

async function loadDynamicReports() {
  if (!sqlReports.length) {
    try {
      const data = await api("/api/reports/configs");
      sqlReports = data.reports || [];
      markDataFresh("reportConfigs");
    } catch (error) {
      showMessage($("#dynamic-report-message"), error.message, "error");
      return;
    }
  }
  fillDynamicReportSelect();
  renderDynamicReportFilters();
  if (!dynamicReportLoaded) clearDynamicReportCache();
}

function fillDynamicReportSelect() {
  const select = $("#dynamic-report-select");
  if (!select) return;
  const current = select.value;
  select.innerHTML = sqlReports.length
    ? sqlReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")
    : `<option value="">Chưa có báo cáo</option>`;
  if (current && sqlReports.some((report) => report.ma_bao_cao === current)) select.value = current;
}

function renderDynamicReportFilters() {
  const container = $("#dynamic-report-filters");
  const select = $("#dynamic-report-select");
  if (!container || !select) return;
  const report = sqlReports.find((item) => item.ma_bao_cao === select.value);
  if (!report) {
    container.innerHTML = "";
    container.classList.add("hidden");
    return;
  }
  const params = dashboardReportParams(report);
  if (!params.length) {
    container.innerHTML = "";
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");
  container.innerHTML = params.map((param) => {
    const lower = param.toLowerCase();
    if (lower.includes("ngay") || lower.includes("date")) {
      return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" type="date" /></label>`;
    }
    if (lower.includes("status") || lower.includes("trang_thai")) {
      return `<label>${escapeHtml(param)}<select class="form-control dynamic-filter" name="${escapeHtml(param)}"><option value="">Tất cả</option><option value="1">Đang hoạt động</option><option value="0">Không hoạt động</option></select></label>`;
    }
    return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" placeholder="Nhập ${escapeHtml(param)}" /></label>`;
  }).join("");
}

function dynamicReportFilters() {
  const filters = {};
  document.querySelectorAll(".dynamic-filter").forEach((input) => {
    if (input.value) filters[input.name] = input.value;
  });
  return filters;
}

function dynamicReportPayload({ page = dynamicReportPage, includeSearch = dynamicReportSearchActive } = {}) {
  const search = includeSearch ? ($("#dynamic-report-search")?.value || "").trim() : "";
  return {
    ma_bao_cao: $("#dynamic-report-select")?.value || "",
    filters: dynamicReportFilters(),
    search,
    search_columns: search ? dynamicReportColumns : [],
    page,
    page_size: Number($("#dynamic-report-page-size")?.value || 20),
  };
}

function clearDynamicReportCache() {
  dynamicReportPage = 1;
  dynamicReportTotal = 0;
  dynamicReportLoaded = false;
  dynamicReportColumns = [];
  dynamicReportLoadedRows = [];
  dynamicReportFilteredRows = [];
  dynamicReportSearchActive = false;
  $("#dynamic-report-head") && ($("#dynamic-report-head").innerHTML = "");
  $("#dynamic-report-body") && ($("#dynamic-report-body").innerHTML = emptyRow(1, "Chưa có dữ liệu", "Bấm Lấy dữ liệu để tải báo cáo."));
  $("#dynamic-report-page-info") && ($("#dynamic-report-page-info").textContent = "Chưa có dữ liệu");
  $("#dynamic-report-prev") && ($("#dynamic-report-prev").disabled = true);
  $("#dynamic-report-next") && ($("#dynamic-report-next").disabled = true);
}

function normalizeDynamicSearchText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

async function applyDynamicReportSearch() {
  const message = $("#dynamic-report-message");
  if (!dynamicReportColumns.length) {
    showMessage(message, "Bấm Lấy dữ liệu trước để hệ thống nhận danh sách cột, sau đó mới Tìm.", "error");
    return;
  }
  const search = ($("#dynamic-report-search")?.value || "").trim();
  dynamicReportPage = 1;
  dynamicReportSearchActive = Boolean(search);
  await loadDynamicReportData({ includeSearch: dynamicReportSearchActive });
}

async function loadDynamicReportData({ includeSearch = dynamicReportSearchActive } = {}) {
  const select = $("#dynamic-report-select");
  const message = $("#dynamic-report-message");
  const button = $("#run-dynamic-report");
  if (!select || !select.value) {
    $("#dynamic-report-head").innerHTML = "";
    $("#dynamic-report-body").innerHTML = emptyRow(1, "Chưa có báo cáo", "Hãy thêm cấu hình SQL trong Quản trị kết nối.");
    return;
  }
  setButtonLoading(button, true);
  try {
    const response = await api("/api/reports/run", {
      method: "POST",
      body: JSON.stringify(dynamicReportPayload({ includeSearch })),
    });
    if (response.ok === false) throw new Error(response.message || "Không tải được dữ liệu báo cáo.");
    const rows = Array.isArray(response.rows) ? response.rows : [];
    dynamicReportColumns = response.columns || dynamicReportColumns;
    if (!dynamicReportColumns.length && rows[0]) dynamicReportColumns = Object.keys(rows[0]);
    dynamicReportLoadedRows = rows;
    dynamicReportFilteredRows = [];
    dynamicReportLoaded = true;
    renderDynamicReportTable(response);
    loadDynamicReportHistory({ silent: true }).catch(() => {});
    showMessage(message, response.message || (includeSearch ? "Đã tải kết quả tìm kiếm." : "Đã tải dữ liệu báo cáo."));
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function downloadFileNameFromDisposition(headerValue) {
  const value = String(headerValue || "");
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].replace(/"/g, ""));
    } catch {
      return encoded[1].replace(/"/g, "");
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain?.[1] || "";
}

function dynamicReportFallbackFileName() {
  const code = ($("#dynamic-report-select")?.value || "truy_van_sql").toLowerCase().replace(/[^a-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") || "truy_van_sql";
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  return `${code}_${stamp}.xlsx`;
}

function downloadDynamicReportBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || dynamicReportFallbackFileName();
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function dynamicReportHistoryItemKey(job) {
  const current = job || {};
  return current.history_id || current.job_id || current.local_id || `local-${Date.now()}`;
}

function dynamicReportHistoryTypeLabel(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "export") return "Xuất file";
  return "Lấy dữ liệu";
}

function dynamicReportExportStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "cancel_requested") return "Đang ngừng";
  if (normalized === "cancelled") return "Đã ngừng";
  if (normalized === "success") return "Đã lấy";
  if (normalized === "complete") return "Hoàn tất";
  if (normalized === "failed") return "Lỗi";
  if (normalized === "running") return "Đang chạy";
  if (normalized === "queued") return "Đang chờ";
  return status || "-";
}

function dynamicReportExportStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "cancel_requested") return "pending";
  if (normalized === "cancelled") return "inactive";
  if (normalized === "success") return "active";
  if (normalized === "complete") return "active";
  if (normalized === "failed") return "inactive";
  if (normalized === "running") return "admin";
  return "pending";
}

function dynamicReportExportRowsText(job) {
  const progressRows = Number(job.progress?.rows || 0);
  const progressTotal = Number(job.progress?.total || 0);
  const rows = Number(job.rows || progressRows || 0);
  const total = Number(job.total || progressTotal || 0);
  if (!rows && !total) return "-";
  return total && total !== rows ? `${rows.toLocaleString("vi-VN")}/${total.toLocaleString("vi-VN")}` : rows.toLocaleString("vi-VN");
}

function upsertDynamicReportExportJob(job) {
  const current = repairDataEncoding(job || {});
  const jobId = dynamicReportHistoryItemKey(current);
  const existing = dynamicReportExportJobs.find((item) => dynamicReportHistoryItemKey(item) === jobId) || {};
  const selected = $("#dynamic-report-select");
  const merged = {
    ...existing,
    ...current,
    job_id: jobId,
    history_id: current.history_id || existing.history_id || jobId,
    event_type: current.event_type || existing.event_type || "export",
    queue_position: current.queue_position || existing.queue_position || 0,
    can_cancel: current.can_cancel ?? existing.can_cancel ?? dynamicReportExportIsActive(current),
    created_at: current.created_at || existing.created_at || new Date().toISOString(),
    report_code: current.report_code || existing.report_code || selected?.value || "",
    report_name: current.report_name || existing.report_name || selected?.selectedOptions?.[0]?.textContent || "",
  };
  dynamicReportExportJobs = [
    merged,
    ...dynamicReportExportJobs.filter((item) => dynamicReportHistoryItemKey(item) !== jobId),
  ].slice(0, 30);
  renderDynamicReportExportJobs();
  return merged;
}

function dynamicReportExportIsActive(job) {
  const status = String(job?.status || "").toLowerCase();
  return ["queued", "running", "cancel_requested"].includes(status);
}

function dynamicReportQueueText(job) {
  const position = Number(job?.queue_position || 0);
  return position > 0 ? `#${position}` : "-";
}

function dynamicReportExportResultHtml(job, status) {
  const link = job.drive_url || job.download_url || "";
  const action = [];
  if (link) {
    action.push(`<a class="table-action" href="${escapeHtml(link)}" target="_blank" rel="noopener">Mở file</a>`);
  } else {
    action.push(`<span>${escapeHtml(job.message || (status === "failed" ? "Xuất file lỗi" : "Đang xử lý"))}</span>`);
  }
  if (job.can_cancel || dynamicReportExportIsActive(job)) {
    const isStopping = status === "cancel_requested";
    const label = status === "queued" ? "Xóa lệnh" : isStopping ? "Đang ngừng" : "Ngừng lệnh";
    action.push(`<button class="table-action danger" data-dynamic-report-job-action="cancel" data-job-id="${escapeHtml(job.job_id || "")}" type="button" ${isStopping ? "disabled" : ""}>${label}</button>`);
  }
  return `<div class="action-group">${action.join("")}</div>`;
}

function renderDynamicReportExportJobs() {
  const body = $("#dynamic-report-export-results");
  if (!body) return;
  const heading = document.querySelector(".dynamic-report-export-heading h2");
  if (heading) heading.textContent = "Hàng đợi và lịch sử kết quả";
  const head = body.closest("table")?.querySelector("thead");
  if (head) head.innerHTML = "<tr><th>Thời gian</th><th>Thứ tự</th><th>Loại</th><th>Báo cáo</th><th>Trạng thái</th><th>Số dòng</th><th>Kết quả / thao tác</th></tr>";
  if (!dynamicReportExportJobs.length) {
    body.innerHTML = emptyRow(7, "Chưa có hàng đợi", "Kết quả lấy dữ liệu và xuất file sẽ xuất hiện ở đây.");
    return;
  }
  body.innerHTML = dynamicReportExportJobs.map((job) => {
    const createdAt = job.created_at ? new Date(job.created_at).toLocaleString("vi-VN") : "-";
    const status = String(job.status || "queued").toLowerCase();
    return `
      <tr>
        <td>${escapeHtml(createdAt)}</td>
        <td>${escapeHtml(dynamicReportQueueText(job))}</td>
        <td>${escapeHtml(dynamicReportHistoryTypeLabel(job.event_type))}</td>
        <td><strong>${escapeHtml(job.report_code || job.ma_bao_cao || "-")}</strong><small class="cell-note">${escapeHtml(job.report_name || job.ten_bao_cao || "")}</small></td>
        <td><span class="status ${dynamicReportExportStatusClass(status)}">${escapeHtml(dynamicReportExportStatusLabel(status))}</span></td>
        <td>${escapeHtml(dynamicReportExportRowsText(job))}</td>
        <td class="table-action-cell">${dynamicReportExportResultHtml(job, status)}</td>
      </tr>
    `;
  }).join("");
}

function setDynamicReportExportStatus(text, type = "success", job = null) {
  const box = $("#dynamic-report-message");
  if (box) {
    box.textContent = "";
    box.classList.add("hidden");
    box.setAttribute("aria-hidden", "true");
  }
  showToast(text || job?.message || "", type);
}

function dynamicReportExportJobTime(job) {
  const value = job?.created_at || job?.updated_at || 0;
  if (typeof value === "number") return value * 1000;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function mergeDynamicReportExportJobs(items) {
  const merged = new Map();
  [...dynamicReportExportJobs, ...(items || [])].forEach((raw) => {
    const job = repairDataEncoding(raw || {});
    const key = dynamicReportHistoryItemKey(job);
    const existing = merged.get(key) || {};
    merged.set(key, {
      ...existing,
      ...job,
      job_id: job.job_id || existing.job_id || key,
      history_id: job.history_id || existing.history_id || key,
    });
  });
  dynamicReportExportJobs = Array.from(merged.values())
    .sort((left, right) => {
      const leftActive = dynamicReportExportIsActive(left) ? 1 : 0;
      const rightActive = dynamicReportExportIsActive(right) ? 1 : 0;
      if (leftActive !== rightActive) return rightActive - leftActive;
      return dynamicReportExportJobTime(right) - dynamicReportExportJobTime(left);
    })
    .slice(0, 30);
  renderDynamicReportExportJobs();
  dynamicReportExportJobs.forEach((job) => {
    if (dynamicReportExportIsActive(job) && job.job_id) monitorDynamicReportExportJob(job.job_id);
  });
}

async function loadDynamicReportHistory({ silent = false } = {}) {
  try {
    const [historyData, queueData] = await Promise.all([
      api("/api/reports/history?limit=30"),
      api("/api/reports/export-jobs?limit=100"),
    ]);
    mergeDynamicReportExportJobs([...(queueData.jobs || []), ...(historyData.items || [])]);
  } catch (error) {
    if (!silent) showToast(error.message, "error");
  }
}

async function monitorDynamicReportExportJob(jobId) {
  if (!jobId || dynamicReportHistoryPollingJobs.has(jobId)) return;
  dynamicReportHistoryPollingJobs.add(jobId);
  try {
    for (let attempt = 0; attempt < 900; attempt += 1) {
      await sleep(attempt === 0 ? 1500 : 2500);
      const job = repairDataEncoding(await api(`/api/reports/export-jobs/${encodeURIComponent(jobId)}`));
      upsertDynamicReportExportJob(job);
      if (!dynamicReportExportIsActive(job)) {
        if (job.status === "complete") showToast(job.message || "Đã xuất file xong. Bấm Mở file trong bảng lịch sử.");
        if (job.status === "cancelled") showToast(job.message || "Đã ngừng lệnh xuất file.");
        break;
      }
    }
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    dynamicReportHistoryPollingJobs.delete(jobId);
    loadDynamicReportHistory({ silent: true }).catch(() => {});
  }
}

async function handleDynamicReportExportAction(event) {
  const button = event.target.closest("[data-dynamic-report-job-action]");
  if (!button) return;
  const action = button.dataset.dynamicReportJobAction;
  const jobId = button.dataset.jobId || "";
  if (action !== "cancel" || !jobId) return;
  button.disabled = true;
  try {
    const job = repairDataEncoding(await api(`/api/reports/export-jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" }));
    upsertDynamicReportExportJob(job);
    showToast(job.message || "Đã gửi lệnh ngừng/xóa job.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    loadDynamicReportHistory({ silent: true }).catch(() => {});
  }
}

async function waitDynamicReportExportJob(jobId, button) {
  let lastMessage = "";
  for (let attempt = 0; attempt < 900; attempt += 1) {
    await sleep(attempt === 0 ? 1000 : 2000);
    const job = repairDataEncoding(await api(`/api/reports/export-jobs/${encodeURIComponent(jobId)}`));
    upsertDynamicReportExportJob(job);
    if (job.message && job.message !== lastMessage) {
      lastMessage = job.message;
      button?.setAttribute("title", repairTextEncoding(job.message));
      if (job.status === "queued") setDynamicReportExportStatus(job.message);
    }
    if (job.status === "complete") return job;
    if (job.status === "failed") throw new Error(job.message || "Không xuất được file Excel.");
  }
  throw new Error("Tạo file Excel quá lâu. Hãy kiểm tra lại job xuất hoặc thu hẹp điều kiện báo cáo.");
}

function downloadDynamicReportExportJob(job) {
  if (!job.download_url) throw new Error("Job xuất Excel chưa có link tải file.");
  if (job.drive_url) {
    setDynamicReportExportStatus(job.message || "Đã xuất file Excel lên Google Drive.", "success", job);
    const opened = window.open(job.drive_url, "_blank", "noopener");
    if (!opened) window.location.href = job.drive_url;
    return;
  }
  setDynamicReportExportStatus(
    `${job.message || "Đã tạo file Excel."} Nếu trình duyệt chưa tự tải, bấm link này:`,
    "success",
    job,
  );
  window.location.href = job.download_url;
}

async function exportDynamicReport() {
  const select = $("#dynamic-report-select");
  const message = $("#dynamic-report-message");
  const button = $("#export-dynamic-report");
  let activeExportJob = null;
  if (!select || !select.value) {
    showMessage(message, "Chọn loại báo cáo trước khi xuất file.", "error");
    return;
  }
  if (!dynamicReportColumns.length) {
    showMessage(message, "Bấm Lấy dữ liệu trước, sau đó mới xuất file Excel.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    const started = repairDataEncoding(await api("/api/reports/export-jobs", {
      method: "POST",
      body: JSON.stringify(dynamicReportPayload({ page: 1, includeSearch: dynamicReportSearchActive })),
    }));
    activeExportJob = upsertDynamicReportExportJob({
      ...started,
      report_code: select.value,
      report_name: select.selectedOptions?.[0]?.textContent || "",
      created_at: new Date().toISOString(),
    });
    if (!started.job_id) throw new Error("Không thấy job xuất file.");
    showMessage(message, started.message || "Đang xuất file Excel ở chế độ nền.");
    setDynamicReportExportStatus(started.message || "Đang xuất file Excel ở chế độ nền.");
    monitorDynamicReportExportJob(started.job_id);
    loadDynamicReportHistory({ silent: true }).catch(() => {});
    showMessage(message, "Đã đưa lệnh xuất file vào hàng đợi. Khi xong, link sẽ hiện ở bảng bên dưới.");
    return;
  } catch (error) {
    upsertDynamicReportExportJob({
      ...(activeExportJob || {
        local_id: `local-${Date.now()}`,
        report_code: select?.value || "",
        report_name: select?.selectedOptions?.[0]?.textContent || "",
        created_at: new Date().toISOString(),
      }),
      status: "failed",
      message: error.message,
    });
    setDynamicReportExportStatus(error.message, "error");
    showMessage(message, error.message, "error");
  } finally {
    button?.removeAttribute("title");
    setButtonLoading(button, false);
  }
}

function renderDynamicReportTable(response) {
  const columns = response.columns || [];
  const rows = response.rows || [];
  dynamicReportLoaded = true;
  dynamicReportTotal = response.pagination?.total || rows.length;
  $("#dynamic-report-head").innerHTML = columns.length ? `<tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>` : "";
  $("#dynamic-report-body").innerHTML = rows.length
    ? rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>`).join("")
    : emptyRow(Math.max(columns.length, 1), "Không có dữ liệu", "Thử thay đổi điều kiện lọc hoặc kiểm tra câu SQL.");
  const page = response.pagination?.page || dynamicReportPage;
  const pageSize = response.pagination?.page_size || Number($("#dynamic-report-page-size")?.value || 20);
  dynamicReportPage = page;
  $("#dynamic-report-page-info").textContent = `Trang ${page} · ${rows.length}/${dynamicReportTotal} dòng`;
  $("#dynamic-report-prev").disabled = page <= 1;
  $("#dynamic-report-next").disabled = page * pageSize >= dynamicReportTotal;
}

async function loadOneBssMining({ force = false } = {}) {
  if (!force && isDataFresh("oneBssMining")) {
    fillOneBssRunSelect();
    renderOneBssRunParameters();
    renderOneBssRunHistory();
    return;
  }
  try {
    const [configData, runData] = await Promise.all([
      api("/api/onebss-reports/configs"),
      api("/api/onebss-reports/runs?limit=30"),
    ]);
    oneBssReports = (configData.reports || []).map((report) => repairDataEncoding(report));
    oneBssReportRuns = (runData.runs || []).map((run) => repairDataEncoding(run));
    markDataFresh("oneBssReports");
    markDataFresh("oneBssMining");
    fillOneBssRunSelect();
    renderOneBssRunParameters();
    renderOneBssRunHistory();
  } catch (error) {
    showMessage($("#onebss-run-message"), error.message, "error");
    const history = $("#onebss-run-history");
    if (history) history.innerHTML = emptyRow(6, "Không tải được dữ liệu OneBSS", error.message);
  }
}

function fillOneBssRunSelect() {
  const select = $("#onebss-run-report-select");
  if (!select) return;
  const current = select.value;
  select.innerHTML = oneBssReports.length
    ? oneBssReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")
    : `<option value="">Chưa có báo cáo OneBSS</option>`;
  if (current && oneBssReports.some((report) => report.ma_bao_cao === current)) select.value = current;
}

function selectedOneBssReport() {
  const code = $("#onebss-run-report-select")?.value || "";
  return oneBssReports.find((report) => report.ma_bao_cao === code) || null;
}

function renderOneBssRunParameters() {
  const container = $("#onebss-run-parameters");
  if (!container) return;
  const report = selectedOneBssReport();
  const variables = report?.danh_sach_bien || [];
  if (!report) {
    container.innerHTML = "";
    return;
  }
  const jsonTemplate = JSON.stringify(report?.parameters || {}, null, 2);
  container.innerHTML = `
    ${variables.length ? `<div class="compact-code-cell">${renderCompactCode(variables.join(", "))}</div>` : ""}
    <label>Tham số đã cấu hình<textarea class="form-control onebss-param-json font-mono text-xs" rows="9" readonly placeholder="Chưa cấu hình tham số trong Quản trị dữ liệu OneBSS">${escapeHtml(jsonTemplate === "{}" ? "" : jsonTemplate)}</textarea></label>
  `;
}

function collectOneBssRunParameters() {
  const parameters = {};
  document.querySelectorAll(".onebss-param-input").forEach((input) => {
    parameters[input.name] = input.value || "";
  });
  const jsonBox = $(".onebss-param-json");
  if (jsonBox && jsonBox.value.trim()) {
    try {
      return JSON.parse(jsonBox.value);
    } catch {
      throw new Error("Tham số lọc JSON chưa đúng định dạng.");
    }
  }
  const report = selectedOneBssReport();
  if (report?.parameters && Object.keys(report.parameters).length) return report.parameters;
  return parameters;
}

function stopOneBssOtpPolling() {
  oneBssOtpPollToken += 1;
  if (oneBssOtpPollTimer) clearTimeout(oneBssOtpPollTimer);
  oneBssOtpPollTimer = null;
}

function clearOneBssManualOtpTimer() {
  if (oneBssManualOtpTimer) clearTimeout(oneBssManualOtpTimer);
  oneBssManualOtpTimer = null;
}

function setOneBssOtpStatus(message = "", tone = "info") {
  const status = $("#onebss-otp-status");
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
  status.classList.toggle("hidden", !message);
}

function resetOneBssOtpState({ hidePanel = true } = {}) {
  stopOneBssOtpPolling();
  clearOneBssManualOtpTimer();
  oneBssPendingOtpRequestId = "";
  oneBssOtpManualSubmitStarted = false;
  const input = $("#onebss-otp-input");
  if (input) {
    input.value = "";
    input.placeholder = "Nhap OTP";
  }
  setOneBssOtpStatus("");
  if (hidePanel) $("#onebss-otp-panel")?.classList.add("hidden");
}

function showOneBssOtpPanel(message = "") {
  $("#onebss-otp-panel")?.classList.remove("hidden");
  if (message) setOneBssOtpStatus(message);
  $("#onebss-otp-input")?.focus();
}

function startOneBssOtpPolling(otpRequestId) {
  const requestId = String(otpRequestId || "").trim();
  if (!requestId) return;
  stopOneBssOtpPolling();
  oneBssPendingOtpRequestId = requestId;
  oneBssOtpManualSubmitStarted = false;
  const token = oneBssOtpPollToken;
  setOneBssOtpStatus("Dang doi OTP tu tin nhan. Anh co the nhap tay neu nhan duoc truoc.");

  const poll = async () => {
    if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
    try {
      const response = await api(`/api/onebss-reports/otp-requests/${encodeURIComponent(requestId)}`);
      if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
      if (response.status === "matched") {
        clearOneBssManualOtpTimer();
        const input = $("#onebss-otp-input");
        if (input) {
          input.value = response.otp ? String(response.otp).replace(/\D/g, "").slice(0, 8) : "";
          input.placeholder = response.code_masked ? `OTP ${response.code_masked}` : "OTP tu dong da san sang";
        }
        setOneBssOtpStatus("Da boc tach OTP tu tin nhan. Dang dang nhap...", "success");
        stopOneBssOtpPolling();
        await runOneBssReport(response.otp || "", { otpRequestId: requestId, otpSource: "auto" });
        return;
      }
      if (["waiting", "created"].includes(response.status || "")) {
        oneBssOtpPollTimer = setTimeout(poll, 2000);
        return;
      }
      setOneBssOtpStatus(response.message || "Chua nhan duoc OTP tu tin nhan.", "warning");
    } catch (error) {
      if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
      setOneBssOtpStatus(error.message || "Khong kiem tra duoc tin nhan OTP.", "warning");
      oneBssOtpPollTimer = setTimeout(poll, 4000);
    }
  };

  oneBssOtpPollTimer = setTimeout(poll, 900);
}

async function runOneBssReport(otp = "", options = {}) {
  const select = $("#onebss-run-report-select");
  const button = $("#run-onebss-report");
  const message = $("#onebss-run-message");
  const report = selectedOneBssReport();
  if (!select || !select.value || !report) {
    showMessage(message, "Chưa có cấu hình báo cáo OneBSS.", "error");
    return;
  }
  let parameters = {};
  try {
    parameters = collectOneBssRunParameters();
  } catch (error) {
    showMessage(message, error.message, "error");
    return;
  }
  oneBssRunInProgress = true;
  setButtonLoading(button, true);
  try {
    const response = await api("/api/onebss-reports/run", {
      method: "POST",
      body: JSON.stringify({
        ma_bao_cao: select.value,
        parameters,
        otp,
        session_id: oneBssPendingSessionId,
        otp_request_id: options.otpRequestId || oneBssPendingOtpRequestId,
        otp_source: options.otpSource || "",
      }),
    });
    if (response.status === "otp_required" || response.status === "otp_invalid" || response.status === "manual_otp_required") {
      oneBssPendingSessionId = response.session_id || oneBssPendingSessionId;
      oneBssPendingOtpRequestId = response.otp_request_id || oneBssPendingOtpRequestId;
      if (response.status === "otp_invalid") oneBssOtpManualSubmitStarted = false;
      showOneBssOtpPanel(oneBssPendingOtpRequestId ? "Dang doi OTP tu tin nhan. Anh co the nhap tay neu nhan duoc truoc." : "");
      if (oneBssPendingOtpRequestId && !oneBssOtpManualSubmitStarted) startOneBssOtpPolling(oneBssPendingOtpRequestId);
      showMessage(message, response.message || "OneBSS yêu cầu OTP.", response.status === "otp_invalid" ? "error" : "info");
      return;
    }
    oneBssPendingSessionId = "";
    resetOneBssOtpState();
    showMessage(message, response.message || (response.ok ? "Đã lấy báo cáo OneBSS." : "Lấy báo cáo OneBSS lỗi."), response.ok ? "success" : "error");
    await refreshOneBssRunHistory(select.value);
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    oneBssRunInProgress = false;
    setButtonLoading(button, false);
  }
}

async function refreshOneBssRunHistory(maBaoCao = "") {
  const query = maBaoCao ? `?ma_bao_cao=${encodeURIComponent(maBaoCao)}&limit=30` : "?limit=30";
  const data = await api(`/api/onebss-reports/runs${query}`);
  oneBssReportRuns = (data.runs || []).map((run) => repairDataEncoding(run));
  renderOneBssRunHistory();
}

function renderOneBssRunHistory() {
  const table = $("#onebss-run-history");
  if (!table) return;
  table.innerHTML = oneBssReportRuns.length
    ? oneBssReportRuns.map((run) => renderOneBssRunRow(run)).join("")
    : emptyRow(6, "Chưa có lượt lấy báo cáo", "Kết quả lấy OneBSS sẽ xuất hiện ở đây sau khi bấm Lấy báo cáo.");
}

function renderOneBssRunRow(run) {
  run = repairDataEncoding(run);
  const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
  const ok = run.status === "success";
  const storageStatus = run.storage_status || "";
  const isUploadedDriveFile = /^uploaded_google_drive:/i.test(storageStatus);
  const isDirectFileLink = run.storage_link
    && /^https?:\/\//.test(run.storage_link)
    && (isUploadedDriveFile || /\/file\/d\/|[?&]id=/.test(run.storage_link));
  const fileLink = isDirectFileLink
    ? `<a href="${escapeHtml(run.storage_link)}" target="_blank" rel="noopener">Mở file</a>`
    : (run.file_path ? `<code>${escapeHtml(run.file_name || run.file_path)}</code><small class="cell-note">${escapeHtml(run.file_path)}</small>` : "-");
  return `
    <tr>
      <td>${escapeHtml(startedAt)}</td>
      <td><strong>${escapeHtml(run.ten_bao_cao || run.ma_bao_cao)}</strong><small class="cell-note">${escapeHtml(run.ma_bao_cao || "")}</small></td>
      <td><span class="status ${ok ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
      <td class="compact-code-cell">${renderCompactCode(JSON.stringify(run.parameters || {}))}</td>
      <td>${fileLink}${storageStatus ? `<small class="cell-note">${escapeHtml(storageStatus)}</small>` : ""}</td>
      <td>${escapeHtml(run.message || "")}</td>
    </tr>`;
}

function normalizeOneBssRunShellText() {
  const summary = $("#onebss-run-history-summary");
  if (summary && !summary.dataset.normalized) {
    summary.textContent = "Ch\u01b0a c\u00f3 d\u1eef li\u1ec7u";
    summary.dataset.normalized = "1";
  }
  const historyTitle = $(".onebss-history-header h2");
  if (historyTitle && !historyTitle.dataset.normalized) {
    historyTitle.textContent = "L\u1ecbch s\u1eed l\u1ea5y d\u1eef li\u1ec7u";
    historyTitle.dataset.normalized = "1";
  }
  const clearButton = $("#clear-onebss-run-history");
  if (clearButton && !clearButton.dataset.normalized) {
    clearButton.textContent = "D\u1ecdn l\u1ecbch s\u1eed";
    clearButton.dataset.normalized = "1";
  }
  const tableHeader = $(".onebss-run-table thead tr");
  if (tableHeader && !tableHeader.dataset.normalized) {
    tableHeader.innerHTML = "<th>Th\u1eddi gian</th><th>B\u00e1o c\u00e1o</th><th>K\u1ebft qu\u1ea3</th><th>File</th><th>Th\u00f4ng b\u00e1o</th>";
    tableHeader.dataset.normalized = "1";
  }
}

function renderOneBssRunParameters() {
  const container = $("#onebss-run-parameters");
  if (!container) return;
  normalizeOneBssRunShellText();
  const report = selectedOneBssReport();
  const variables = report?.danh_sach_bien || [];
  if (!report) {
    container.innerHTML = "";
    updateOneBssParameterEditButton();
    return;
  }
  const jsonTemplate = JSON.stringify(report?.parameters || {}, null, 2);
  const chips = variables.length
    ? variables.map((variable) => `<span>${escapeHtml(variable)}</span>`).join("")
    : "<span>Kh\u00f4ng c\u00f3 bi\u1ebfn c\u1ea5u h\u00ecnh</span>";
  container.innerHTML = `
    <div class="onebss-variable-panel"><span class="onebss-field-title">Danh s\u00e1ch bi\u1ebfn</span><div class="onebss-variable-list">${chips}</div></div>
    <label class="onebss-json-panel">
      <span class="onebss-field-title">Tham s\u1ed1 l\u1ea7n ch\u1ea1y n\u00e0y</span>
      <textarea class="form-control onebss-param-json font-mono text-xs" rows="${oneBssRunParameterEditing ? 10 : 5}" ${oneBssRunParameterEditing ? "" : "readonly"} placeholder="{}">${escapeHtml(jsonTemplate === "{}" ? "" : jsonTemplate)}</textarea>
    </label>
  `;
  updateOneBssParameterEditButton();
}

function updateOneBssParameterEditButton() {
  const button = $("#toggle-onebss-param-edit");
  if (!button) return;
  button.textContent = oneBssRunParameterEditing ? "D\u1eebng s\u1eeda" : "Ch\u1ec9nh tham s\u1ed1";
  button.classList.toggle("active", oneBssRunParameterEditing);
}

function toggleOneBssRunParameterEditing() {
  oneBssRunParameterEditing = !oneBssRunParameterEditing;
  renderOneBssRunParameters();
  if (oneBssRunParameterEditing) $(".onebss-param-json")?.focus();
}

function renderOneBssRunHistory() {
  normalizeOneBssRunShellText();
  const table = $("#onebss-run-history");
  const summary = $("#onebss-run-history-summary");
  if (summary) {
    const successCount = oneBssReportRuns.filter((run) => run.status === "success").length;
    summary.textContent = oneBssReportRuns.length ? `${oneBssReportRuns.length} l\u01b0\u1ee3t g\u1ea7n nh\u1ea5t, ${successCount} th\u00e0nh c\u00f4ng` : "Ch\u01b0a c\u00f3 d\u1eef li\u1ec7u";
  }
  if (!table) return;
  const visibleRuns = oneBssReportRuns.slice(0, 12);
  table.innerHTML = visibleRuns.length
    ? visibleRuns.map((run) => renderOneBssRunRow(run)).join("")
    : emptyRow(5, "Ch\u01b0a c\u00f3 l\u01b0\u1ee3t l\u1ea5y b\u00e1o c\u00e1o", "K\u1ebft qu\u1ea3 l\u1ea5y OneBSS s\u1ebd xu\u1ea5t hi\u1ec7n \u1edf \u0111\u00e2y sau khi b\u1ea5m L\u1ea5y b\u00e1o c\u00e1o.");
}

function renderOneBssRunRow(run) {
  run = repairDataEncoding(run);
  const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
  const ok = run.status === "success";
  const storageStatus = run.storage_status || "";
  const isUploadedDriveFile = /^uploaded_google_drive:/i.test(storageStatus);
  const isDirectFileLink = run.storage_link
    && /^https?:\/\//.test(run.storage_link)
    && (isUploadedDriveFile || /\/file\/d\/|\/spreadsheets\/d\/|[?&]id=/.test(run.storage_link));
  const fileLink = isDirectFileLink
    ? `<a class="onebss-file-link" href="${escapeHtml(run.storage_link)}" target="_blank" rel="noopener">M\u1edf file</a>`
    : (run.file_path ? `<span class="onebss-file-name">${escapeHtml(run.file_name || run.file_path)}</span>` : "-");
  const message = truncateText(run.message || "", 180);
  return `
    <tr>
      <td class="onebss-time-cell">${escapeHtml(startedAt)}</td>
      <td><strong>${escapeHtml(run.ten_bao_cao || run.ma_bao_cao)}</strong><small class="cell-note">${escapeHtml(run.ma_bao_cao || "")}</small></td>
      <td><span class="status ${ok ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
      <td>${fileLink}${storageStatus ? `<small class="cell-note">${escapeHtml(truncateText(storageStatus, 60))}</small>` : ""}</td>
      <td><span title="${escapeHtml(run.message || "")}">${escapeHtml(message)}</span></td>
    </tr>`;
}

function truncateText(value, maxLength = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

async function clearOneBssRunHistory() {
  const select = $("#onebss-run-report-select");
  const code = select?.value || "";
  const message = $("#onebss-run-message");
  const button = $("#clear-onebss-run-history");
  if (!confirm("X\u00f3a l\u1ecbch s\u1eed l\u1ea5y d\u1eef li\u1ec7u OneBSS \u0111ang hi\u1ec3n th\u1ecb?")) return;
  const query = code ? `?ma_bao_cao=${encodeURIComponent(code)}` : "";
  try {
    if (button) setButtonLoading(button, true);
    let response;
    try {
      response = await api(`/api/onebss-reports/runs${query}`, { method: "DELETE" });
    } catch (deleteError) {
      response = await api(`/api/onebss-reports/runs/clear${query}`, { method: "POST" });
    }
    showMessage(message, `\u0110\u00e3 d\u1ecdn ${response.deleted || 0} d\u00f2ng l\u1ecbch s\u1eed.`);
    oneBssReportRuns = [];
    renderOneBssRunHistory();
    await refreshOneBssRunHistory(code);
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

function mobileFormatTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return "-";
  }
}

function normalizeMobileGatewayUi() {
  const root = $("#view-mobile-gateway");
  if (!root || root.dataset.mobileUiV13 === "true") return;
  root.dataset.mobileUiV13 = "true";
  const actionGroup = root.querySelector(".page-header .action-group");
  if (actionGroup) actionGroup.innerHTML = "";
  const tabs = root.querySelector(".mobile-gateway-tabs");
  if (tabs) {
    tabs.innerHTML = `
      <button class="mobile-gateway-tab active" data-mobile-tab="overview" type="button">Tổng quan</button>
      <button class="mobile-gateway-tab" data-mobile-tab="devices-config" type="button">Thiết bị</button>
      <button class="mobile-gateway-tab" data-mobile-tab="sms" type="button">SMS</button>
      <button class="mobile-gateway-tab" data-mobile-tab="otp" type="button">OTP</button>`;
  }
  const devicesPanel = root.querySelector('[data-mobile-panel="devices"]');
  if (devicesPanel) {
    devicesPanel.dataset.mobilePanel = "devices-config";
    devicesPanel.innerHTML = `
      <section class="data-card">
        <div class="section-heading">
          <div><p class="eyebrow">Pairing</p><h2>Kết nối điện thoại đọc SMS</h2></div>
          <div class="action-group"><button class="btn-primary" id="mobile-create-pairing-code" type="button">Tạo mã ghép nối</button><button class="btn-secondary" id="mobile-refresh-inline" type="button">Làm mới</button></div>
        </div>
        <div id="mobile-pairing-result" class="mobile-pairing-result hidden"></div>
        <div class="table-scroll mt-4"><table><thead><tr><th>Trạng thái</th><th>Tạo bởi</th><th>Tạo lúc</th><th>Hết hạn</th><th>Thiết bị sử dụng</th></tr></thead><tbody id="mobile-pairing-table"></tbody></table></div>
      </section>
      <section class="data-card mt-4">
        <div class="section-heading"><div><p class="eyebrow">Thiết bị</p><h2>Danh sách thiết bị</h2></div></div>
        <div class="table-scroll"><table><thead><tr><th class="table-action-column">Thao tác</th><th>Thiết bị</th><th>Trạng thái</th><th>Heartbeat</th><th>Pin/Mạng</th><th>Phiên bản</th><th>SMS chờ</th></tr></thead><tbody id="mobile-devices-table"></tbody></table></div>
      </section>`;
  }
  const smsPanel = root.querySelector('[data-mobile-panel="sms"]');
  if (smsPanel) {
    smsPanel.innerHTML = `
      <section class="data-card">
        <div class="admin-inline-toolbar">
          <label>Thiết bị<select class="form-control" id="mobile-sms-device-filter"><option value="">Tất cả</option></select></label>
          <label>Người gửi<input class="form-control" id="mobile-sms-sender-filter" /></label>
          <label>Nội dung<input class="form-control" id="mobile-sms-query-filter" /></label>
          <label>Từ ngày<input class="form-control" id="mobile-sms-date-from" type="date" /></label>
          <label>Đến ngày<input class="form-control" id="mobile-sms-date-to" type="date" /></label>
          <label>SIM<input class="form-control" id="mobile-sms-sim-filter" type="number" /></label>
        </div>
        <div class="table-scroll"><table><thead><tr><th>Người gửi</th><th>Thời gian nhận</th><th>Nội dung</th><th>Thiết bị</th><th>SIM</th></tr></thead><tbody id="mobile-sms-table"></tbody></table></div>
        <div class="mt-4 flex items-center justify-between gap-3"><span id="mobile-sms-page-info">Trang 1</span><div class="action-group"><button class="btn-secondary" id="mobile-sms-prev" type="button">Trang trước</button><button class="btn-secondary" id="mobile-sms-next" type="button">Trang sau</button></div></div>
      </section>`;
  }
  const otpPanel = root.querySelector('[data-mobile-panel="otp"]');
  if (otpPanel) {
    otpPanel.innerHTML = `
      <section class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div class="data-card">
          <div class="section-heading"><div><p class="eyebrow">OTP filter</p><h2>Quy tắc lọc OTP</h2></div><button class="btn-primary" id="mobile-save-otp-filter" type="button">Lưu quy tắc</button></div>
          <form id="mobile-otp-filter-form" class="mobile-form-grid">
            <input type="hidden" name="id" />
            <label>ID<input class="form-control" name="filter_id" value="onebss" /></label>
            <label>Tên quy tắc<input class="form-control" name="rule_name" value="OneBSS mặc định" required /></label>
            <label>Service code<input class="form-control" name="service_code" value="onebss" required /></label>
            <label>Người gửi<input class="form-control" name="sender_pattern" value="293" required /></label>
            <label>So khớp<select class="form-control" name="sender_match_type"><option value="contains">contains</option><option value="exact">exact</option><option value="regex">regex</option></select></label>
            <label>Độ dài OTP<input class="form-control" name="otp_length" type="number" value="6" min="1" max="12" /></label>
            <label>Start prefix<input class="form-control" name="start_prefix" value="1364" /></label>
            <label>Hiệu lực giây<input class="form-control" name="validity_seconds" type="number" value="60" /></label>
            <label>Thiết bị<select class="form-control" name="device_id" id="mobile-otp-device"><option value="">Tất cả</option></select></label>
            <label>SIM<input class="form-control" name="sim_slot" type="number" /></label>
            <label>Ưu tiên<input class="form-control" name="priority" type="number" value="10" /></label>
            <label class="checkbox-label"><input type="checkbox" name="enabled" checked /> Bật</label>
          </form>
          <div class="table-scroll mt-4"><table><thead><tr><th>ID</th><th>Quy tắc</th><th>Sender</th><th>Prefix</th><th>Hiệu lực</th><th>Trạng thái</th></tr></thead><tbody id="mobile-otp-filters-table"></tbody></table></div>
        </div>
        <div class="data-card">
          <div class="section-heading"><div><p class="eyebrow">OTP</p><h2>OTP mới nhất</h2></div><button class="btn-secondary" id="mobile-refresh-otp" type="button">Làm mới</button></div>
          <div class="table-scroll"><table><thead><tr><th>Người gửi</th><th>Quy tắc</th><th>OTP mới nhất</th><th>Thời gian</th><th>Hiệu lực</th><th>Trạng thái</th></tr></thead><tbody id="mobile-otp-latest-table"></tbody></table></div>
        </div>
      </section>`;
  }
  const notificationsPanel = root.querySelector('[data-mobile-panel="notifications"]');
  if (notificationsPanel) {
    notificationsPanel.innerHTML = `
      <section class="data-card">
        <div class="admin-inline-toolbar">
          <label>Thiết bị<select class="form-control" id="mobile-notification-device-filter"><option value="">Tất cả</option></select></label>
          <label>App/Package<input class="form-control" id="mobile-notification-app-filter" /></label>
          <label>Nội dung<input class="form-control" id="mobile-notification-query-filter" /></label>
        </div>
        <div class="table-scroll"><table><thead><tr><th>App</th><th>Tiêu đề</th><th>Nội dung</th><th>Thời gian</th><th>Thiết bị</th></tr></thead><tbody id="mobile-notifications-table"></tbody></table></div>
        <div class="mt-4 flex items-center justify-between gap-3"><span id="mobile-notification-page-info">Trang 1</span><div class="action-group"><button class="btn-secondary" id="mobile-notification-prev" type="button">Trang trước</button><button class="btn-secondary" id="mobile-notification-next" type="button">Trang sau</button></div></div>
      </section>`;
  }
  normalizeMobileOtpFormDefaults(root);
  root.querySelector('[data-mobile-panel="commands"]')?.remove();
  root.querySelector('[data-mobile-panel="logs"]')?.remove();
  root.querySelector('[data-mobile-panel="settings"]')?.remove();
  root.querySelector('[data-mobile-panel="notifications"]')?.remove();
  root.querySelector('[data-mobile-panel="media"]')?.remove();
  $("#mobile-refresh-inline")?.addEventListener("click", () => loadMobileGateway({ force: true }));
}

function normalizeMobileOtpFormDefaults(root) {
  const form = root?.querySelector("#mobile-otp-filter-form");
  if (!form || form.dataset.defaultNormalized === "true") return;
  form.dataset.defaultNormalized = "true";
  const sender = form.elements.namedItem("sender_pattern");
  const startPrefix = form.elements.namedItem("start_prefix");
  if (sender && String(sender.value || "").trim() === "293") sender.value = "VNPT";
  if (startPrefix && String(startPrefix.value || "").trim() === "1364") startPrefix.value = "0";
}

function mobileDeviceLabel(deviceId) {
  const device = mobileGatewayDevices.find((item) => item.device_id === deviceId);
  return device ? `${device.name || device.device_id}` : (deviceId || "-");
}

function activateMobileGatewayTab(tabName) {
  document.querySelectorAll("[data-mobile-tab]").forEach((button) => button.classList.toggle("active", button.dataset.mobileTab === tabName));
  document.querySelectorAll("[data-mobile-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.mobilePanel === tabName));
}

async function loadMobileGateway({ force = false } = {}) {
  normalizeMobileGatewayUi();
  const message = $("#mobile-gateway-message");
  try {
    await Promise.all([
      loadMobileGatewayOverview(),
      loadMobileGatewayDevices(),
      loadMobilePairingCodes(),
      loadMobileGatewaySms({ force: true }),
      loadMobileOtpData(),
    ]);
    mobileGatewayLoaded = true;
    startMobileOtpTicker();
    if (message) message.className = "result hidden mb-4";
  } catch (error) {
    showMessage(message, error.message, "error");
  }
}

async function loadMobileGatewayOverview() {
  const data = await api("/api/admin/mobile-gateway/overview");
  mobileGatewayOverview = data.overview || {};
  renderMobileGatewayOverview();
}

function renderMobileGatewayOverview() {
  const cards = [
    ["Online", mobileGatewayOverview.devices_online || 0],
    ["Offline", mobileGatewayOverview.devices_offline || 0],
    ["SMS hôm nay", mobileGatewayOverview.sms_today || 0],
    ["OTP hôm nay", mobileGatewayOverview.otp_today || 0],
    ["OTP thành công", mobileGatewayOverview.otp_success || 0],
    ["OTP timeout", mobileGatewayOverview.otp_timeout || 0],
    ["Lệnh chờ", mobileGatewayOverview.pending_commands || 0],
    ["Cảnh báo", mobileGatewayOverview.device_alerts || 0],
  ];
  const target = $("#mobile-overview-cards");
  if (target) {
    target.innerHTML = cards.map(([label, value]) => `
      <article class="status-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>
    `).join("");
  }
  renderMobileRecentSms(mobileGatewayOverview.recent_sms || []);
  const settings = mobileGatewayOverview.settings || {};
  const ttl = $("#mobile-pairing-ttl");
  const threshold = $("#mobile-online-threshold");
  if (ttl) ttl.value = settings.pairing_ttl_seconds || 600;
  if (threshold) threshold.value = settings.online_threshold_seconds || 180;
}

function renderMobileRecentSms(items) {
  const table = $("#mobile-recent-sms-table");
  if (!table) return;
  table.replaceChildren();
  if (!items.length) {
    table.innerHTML = emptyRow(4, "Chưa có SMS");
    return;
  }
  items.forEach((sms) => {
    const row = document.createElement("tr");
    [mobileFormatTime(sms.received_at), mobileDeviceLabel(sms.device_id), sms.sender || "", sms.body || sms.body_masked || ""].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    table.appendChild(row);
  });
}

async function loadMobileGatewayDevices() {
  const data = await api("/api/admin/mobile-gateway/devices");
  mobileGatewayDevices = data.devices || [];
  renderMobileGatewayDevices();
  renderMobileGatewayDeviceOptions();
}

function renderMobileGatewayDeviceOptions() {
  const options = mobileGatewayDevices.map((device) => `<option value="${escapeHtml(device.device_id)}">${escapeHtml(device.name || device.device_id)}</option>`).join("");
  ["#mobile-policy-device"].forEach((selector) => {
    const select = $(selector);
    if (select) select.innerHTML = options || `<option value="">Chưa có thiết bị</option>`;
  });
  ["#mobile-sms-device-filter", "#mobile-otp-device", "#mobile-notification-device-filter", "#mobile-media-device-filter"].forEach((selector) => {
    const select = $(selector);
    if (select) select.innerHTML = `<option value="">Tất cả</option>${options}`;
  });
  renderMobileMediaDevices();
}

function renderMobileGatewayDevices() {
  const table = $("#mobile-devices-table");
  if (!table) return;
  table.innerHTML = mobileGatewayDevices.length ? mobileGatewayDevices.map((device) => {
    const heartbeat = device.heartbeat || {};
    const active = device.is_active;
    const online = device.online;
    const statusClass = !active ? "inactive" : (online ? "viewer" : "pending");
    const statusText = !active ? "Đã thu hồi" : (online ? "Online" : "Offline");
    return `<tr>
      <td class="table-action-cell"><div class="action-group">
        <button class="table-action" data-mobile-policy="${escapeHtml(device.device_id)}" type="button">Policy</button>
        <button class="table-action" data-mobile-command="${escapeHtml(device.device_id)}" type="button">Lệnh</button>
        <button class="table-action danger" data-mobile-revoke="${escapeHtml(device.device_id)}" type="button">${active ? "Thu hồi" : "Kích hoạt"}</button>
      </div></td>
      <td><strong>${escapeHtml(device.name || device.device_id)}</strong><small class="cell-note">${escapeHtml(device.manufacturer || "")} ${escapeHtml(device.model || "")}</small></td>
      <td><span class="status ${statusClass}">${statusText}</span></td>
      <td>${escapeHtml(String(heartbeat.battery_percent ?? "-"))}%<small class="cell-note">${escapeHtml(heartbeat.charging ? "Đang sạc" : "")} ${escapeHtml(heartbeat.network_type || "")}</small></td>
      <td>${escapeHtml(device.app_version || "-")}<small class="cell-note">Android ${escapeHtml(device.android_version || "-")}</small></td>
      <td>SMS: ${heartbeat.sms_permission ? "OK" : "-"}<small class="cell-note">Notification: ${heartbeat.notification_access ? "OK" : "-"}</small></td>
      <td>${escapeHtml(mobileFormatTime(device.last_seen_at))}<small class="cell-note">SMS chờ: ${escapeHtml(String(heartbeat.pending_sms || 0))}, TB chờ: ${escapeHtml(String(heartbeat.pending_notifications || 0))}</small></td>
    </tr>`;
  }).join("") : emptyRow(7, "Chưa có thiết bị");
  document.querySelectorAll("[data-mobile-revoke]").forEach((button) => button.addEventListener("click", () => toggleMobileDeviceActive(button.dataset.mobileRevoke)));
  document.querySelectorAll("[data-mobile-policy]").forEach((button) => button.addEventListener("click", () => {
    activateMobileGatewayTab("settings");
    const select = $("#mobile-policy-device");
    if (select) select.value = button.dataset.mobilePolicy;
    loadMobilePolicy();
  }));
  document.querySelectorAll("[data-mobile-command]").forEach((button) => button.addEventListener("click", () => {
    activateMobileGatewayTab("commands");
    const select = $("#mobile-command-device");
    if (select) select.value = button.dataset.mobileCommand;
  }));
}

async function toggleMobileDeviceActive(deviceId) {
  const device = mobileGatewayDevices.find((item) => item.device_id === deviceId);
  if (!device) return;
  const action = device.is_active ? "revoke" : "reactivate";
  await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/${action}`, { method: "POST" });
  await loadMobileGatewayDevices();
}

async function createMobilePairingCode() {
  const result = await api("/api/admin/mobile-gateway/pairing-codes", { method: "POST" });
  const box = $("#mobile-pairing-result");
  if (box) {
    box.className = "mobile-pairing-result";
    box.textContent = `${result.pairing_code} - hết hạn: ${mobileFormatTime(result.expires_at)}`;
  }
  await loadMobilePairingCodes();
}

async function loadMobilePairingCodes() {
  const data = await api("/api/admin/mobile-gateway/pairing-codes");
  const table = $("#mobile-pairing-table");
  if (!table) return;
  table.innerHTML = (data.codes || []).length ? data.codes.map((code) => `<tr><td><span class="status ${code.status === "used" ? "viewer" : "pending"}">${escapeHtml(code.status)}</span></td><td>${escapeHtml(code.created_by || "")}</td><td>${escapeHtml(mobileFormatTime(code.expires_at))}</td><td>${escapeHtml(code.used_by_device_id || "-")}</td></tr>`).join("") : emptyRow(4, "Chưa có mã ghép nối");
}

async function loadMobileGatewaySms({ force = false } = {}) {
  const deviceId = $("#mobile-sms-device-filter")?.value || "";
  const sender = $("#mobile-sms-sender-filter")?.value || "";
  const query = $("#mobile-sms-query-filter")?.value || "";
  const otpOnly = $("#mobile-sms-otp-filter")?.checked ? "true" : "false";
  if (force) setTableLoading("#mobile-sms-table", 7, "Đang tải SMS...");
  const data = await api(`/api/admin/mobile-gateway/sms?page=${mobileGatewaySmsPage}&page_size=50&device_id=${encodeURIComponent(deviceId)}&sender=${encodeURIComponent(sender)}&query=${encodeURIComponent(query)}&otp_only=${otpOnly}`);
  mobileGatewaySmsHasMore = Boolean(data.has_more);
  renderMobileSmsTable(data.items || []);
  const pageInfo = $("#mobile-sms-page-info");
  if (pageInfo) pageInfo.textContent = `Trang ${mobileGatewaySmsPage}`;
}

function renderMobileSmsTable(items) {
  const table = $("#mobile-sms-table");
  if (!table) return;
  table.replaceChildren();
  if (!items.length) {
    table.innerHTML = emptyRow(7, "Chưa có SMS");
    return;
  }
  items.forEach((sms) => {
    const row = document.createElement("tr");
    const values = [
      mobileFormatTime(sms.received_at),
      mobileDeviceLabel(sms.device_id),
      sms.sim_slot ?? "-",
      sms.sender || "",
      sms.body || sms.body_masked || "",
      sms.is_otp_candidate ? "Có" : "-",
      sms.used_for_otp ? "Đã dùng" : "-",
    ];
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    table.appendChild(row);
  });
}

async function loadMobileOtpData() {
  const [configs, requests] = await Promise.all([
    api("/api/admin/mobile-gateway/otp/configurations"),
    api("/api/admin/mobile-gateway/otp/requests?limit=100"),
  ]);
  mobileGatewayOtpConfigurations = configs.configurations || [];
  mobileGatewayOtpRequests = requests.requests || [];
  renderMobileOtpConfiguration();
  renderMobileOtpRequests();
}

function renderMobileOtpConfiguration() {
  const form = $("#mobile-otp-config-form");
  const config = mobileGatewayOtpConfigurations.find((item) => item.service_code === "onebss") || mobileGatewayOtpConfigurations[0];
  if (!form || !config) return;
  Object.entries(config).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value ?? "";
  });
}

async function saveMobileOtpConfiguration() {
  const form = $("#mobile-otp-config-form");
  const data = Object.fromEntries(new FormData(form));
  const checkbox = (name) => Boolean(form.elements.namedItem(name)?.checked);
  const payload = {
    ...data,
    id: data.id ? Number(data.id) : null,
    enabled: checkbox("enabled"),
    auto_fill_enabled: checkbox("auto_fill_enabled"),
    manual_fallback_enabled: checkbox("manual_fallback_enabled"),
    wait_timeout_seconds: Number(data.wait_timeout_seconds || 120),
    validity_seconds: Number(data.validity_seconds || 180),
    otp_length_min: 4,
    otp_length_max: 8,
    priority: Number(data.priority || 100),
    sim_slot: data.sim_slot === "" ? null : Number(data.sim_slot),
  };
  await api("/api/admin/mobile-gateway/otp/configurations", { method: "POST", body: JSON.stringify(payload) });
  showToast("Đã lưu cấu hình OTP.");
  await loadMobileOtpData();
}

async function testMobileOtpRegex() {
  const form = $("#mobile-otp-config-form");
  const response = await api("/api/admin/mobile-gateway/otp/test-regex", {
    method: "POST",
    body: JSON.stringify({ otp_regex: form.elements.namedItem("otp_regex").value, sample_text: $("#mobile-otp-sample")?.value || "" }),
  });
  showToast(response.matched ? `Match: ${response.code_masked}` : "Không match OTP", response.matched ? "success" : "error");
}

async function createMobileOtpRequest() {
  const form = $("#mobile-otp-config-form");
  await api("/api/admin/mobile-gateway/otp/requests", {
    method: "POST",
    body: JSON.stringify({ service_code: form.elements.namedItem("service_code").value || "onebss", job_id: `manual-${Date.now()}` }),
  });
  await loadMobileOtpData();
}

function renderMobileOtpRequests() {
  const table = $("#mobile-otp-requests-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpRequests.length ? mobileGatewayOtpRequests.map((request) => `<tr>
    <td><strong>${escapeHtml(request.request_id)}</strong><small class="cell-note">${escapeHtml(request.job_id || "")}</small></td>
    <td>${escapeHtml(request.service_code || "")}</td>
    <td><span class="status ${request.status === "consumed" ? "viewer" : request.status === "waiting" ? "pending" : "inactive"}">${escapeHtml(request.status || "")}</span></td>
    <td>${escapeHtml(request.matched_source_type || "-")} ${escapeHtml(request.code_masked || "")}</td>
    <td>${escapeHtml(mobileFormatTime(request.requested_at))}<small class="cell-note">Hết hạn ${escapeHtml(mobileFormatTime(request.expires_at))}</small></td>
    <td class="table-action-cell">${request.status === "waiting" ? `<button class="table-action danger" data-mobile-cancel-otp="${escapeHtml(request.request_id)}" type="button">Hủy</button>` : ""}</td>
  </tr>`).join("") : emptyRow(6, "Chưa có OTP request");
  document.querySelectorAll("[data-mobile-cancel-otp]").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/admin/mobile-gateway/otp/requests/${encodeURIComponent(button.dataset.mobileCancelOtp)}/cancel`, { method: "POST" });
    await loadMobileOtpData();
  }));
}

async function loadMobileNotifications() {
  const data = await api("/api/admin/mobile-gateway/notifications?limit=100");
  const table = $("#mobile-notifications-table");
  if (!table) return;
  table.innerHTML = (data.items || []).length ? data.items.map((item) => `<tr><td>${escapeHtml(mobileFormatTime(item.posted_at))}</td><td>${escapeHtml(mobileDeviceLabel(item.device_id))}</td><td>${escapeHtml(item.package_name || "")}</td><td>${escapeHtml(item.title || "")}</td><td>${escapeHtml(item.text || item.text_masked || "")}</td><td>${escapeHtml(item.used_for_otp ? "Đã dùng" : "-")}</td></tr>`).join("") : emptyRow(6, "Chưa có thông báo");
}

async function loadMobileCommands() {
  const data = await api("/api/admin/mobile-gateway/commands?limit=100");
  const table = $("#mobile-commands-table");
  if (!table) return;
  table.innerHTML = (data.commands || []).length ? data.commands.map((command) => `<tr><td>${escapeHtml(mobileFormatTime(command.created_at))}</td><td>${escapeHtml(mobileDeviceLabel(command.device_id))}</td><td>${escapeHtml(command.command_type || "")}</td><td><span class="status ${command.status === "completed" ? "viewer" : command.status === "failed" ? "inactive" : "pending"}">${escapeHtml(command.status || "")}</span></td><td>${escapeHtml(mobileFormatTime(command.expires_at))}</td><td>${escapeHtml(command.sanitized_error || "")}</td></tr>`).join("") : emptyRow(6, "Chưa có lệnh");
}

async function sendMobileCommand() {
  const deviceId = $("#mobile-command-device")?.value || "";
  const commandType = $("#mobile-command-type")?.value || "";
  if (!deviceId || !commandType) return showToast("Chọn thiết bị và lệnh.", "error");
  await api("/api/admin/mobile-gateway/commands", { method: "POST", body: JSON.stringify({ device_id: deviceId, command_type: commandType, payload: {} }) });
  showToast("Đã gửi lệnh.");
  await loadMobileCommands();
}

async function loadMobileLogs() {
  const [diagnostics, events] = await Promise.all([
    api("/api/admin/mobile-gateway/diagnostics?limit=100"),
    api("/api/admin/mobile-gateway/otp/events?limit=100"),
  ]);
  const diagTable = $("#mobile-diagnostics-table");
  if (diagTable) {
    diagTable.innerHTML = (diagnostics.items || []).length ? diagnostics.items.map((item) => `<tr><td>${escapeHtml(mobileFormatTime(item.created_at))}</td><td>${escapeHtml(mobileDeviceLabel(item.device_id))}</td><td>${escapeHtml(item.app_version || "")}</td><td>${escapeHtml(item.sanitized_error || "")}</td><td class="compact-code-cell">${renderCompactCode(JSON.stringify(item.payload || {}))}</td></tr>`).join("") : emptyRow(5, "Chưa có diagnostics");
  }
  const eventTable = $("#mobile-otp-events-table");
  if (eventTable) {
    eventTable.innerHTML = (events.events || []).length ? events.events.map((event) => `<tr><td>${escapeHtml(mobileFormatTime(event.created_at))}</td><td>${escapeHtml(event.request_id || "")}</td><td>${escapeHtml(event.event_type || "")}</td><td>${escapeHtml(event.source_type || "")} ${escapeHtml(event.source_id || "")}</td></tr>`).join("") : emptyRow(4, "Chưa có sự kiện OTP");
  }
}

async function loadMobilePolicy() {
  const deviceId = $("#mobile-policy-device")?.value || "";
  if (!deviceId) return;
  const data = await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/policy`);
  const form = $("#mobile-policy-form");
  const policy = data.policy || {};
  Object.entries(policy).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else if (key === "notification_allowlist") field.value = (value || []).join("\n");
    else field.value = value ?? "";
  });
}

async function saveMobilePolicy() {
  const form = $("#mobile-policy-form");
  const deviceId = form.elements.namedItem("device_id")?.value || "";
  if (!deviceId) return showToast("Chọn thiết bị.", "error");
  const checkbox = (name) => Boolean(form.elements.namedItem(name)?.checked);
  const payload = {
    sms_enabled: checkbox("sms_enabled"),
    notifications_enabled: checkbox("notifications_enabled"),
    clipboard_enabled: checkbox("clipboard_enabled"),
    diagnostics_enabled: checkbox("diagnostics_enabled"),
    force_update: checkbox("force_update"),
    notification_allowlist: (form.elements.namedItem("notification_allowlist").value || "").split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean),
    heartbeat_interval_minutes: Number(form.elements.namedItem("heartbeat_interval_minutes").value || 15),
    sync_interval_minutes: Number(form.elements.namedItem("sync_interval_minutes").value || 15),
    batch_size: Number(form.elements.namedItem("batch_size").value || 50),
    local_retention_days: Number(form.elements.namedItem("local_retention_days").value || 14),
    minimum_app_version: form.elements.namedItem("minimum_app_version").value || "1.1.0",
  };
  await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/policy`, { method: "PUT", body: JSON.stringify(payload) });
  showToast("Đã lưu policy.");
}

function mobileGatewayDateStart(value) {
  return value ? `${value}T00:00:00+00:00` : "";
}

function mobileGatewayDateEnd(value) {
  return value ? `${value}T23:59:59+00:00` : "";
}

function mobileGatewayStatusText(code) {
  if (code.used_at || code.status === "used") return { text: "Đã sử dụng", className: "viewer" };
  const expiresAt = Date.parse(code.expires_at || "");
  if (expiresAt && expiresAt < Date.now()) return { text: "Hết hạn", className: "inactive" };
  return { text: "Chưa sử dụng", className: "pending" };
}

function startMobilePairingTimers() {
  clearInterval(mobileGatewayPairingCountdownTimer);
  clearInterval(mobileGatewayPairingPollTimer);
  mobileGatewayPairingCountdownTimer = setInterval(renderMobilePairingCountdown, 1000);
  mobileGatewayPairingPollTimer = setInterval(loadMobilePairingCodes, 3000);
  renderMobilePairingCountdown();
}

function stopMobilePairingTimers() {
  clearInterval(mobileGatewayPairingCountdownTimer);
  clearInterval(mobileGatewayPairingPollTimer);
  mobileGatewayPairingCountdownTimer = null;
  mobileGatewayPairingPollTimer = null;
}

function renderMobilePairingCountdown(statusText = "") {
  const box = $("#mobile-pairing-result");
  if (!box || !mobileGatewayActivePairingId) return;
  const expiresAt = Date.parse(mobileGatewayActivePairingExpiresAt || "");
  const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
  const status = statusText || (remaining > 0 ? `Còn ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}` : "Hết hạn");
  const code = box.dataset.pairingCode || "";
  box.className = "mobile-pairing-result";
  box.innerHTML = `<strong>${escapeHtml(code)}</strong><span>${escapeHtml(status)}</span>`;
  if (remaining <= 0 && !statusText) stopMobilePairingTimers();
}

async function createMobilePairingCode() {
  const payload = {
    sms_enabled: true,
    notifications_enabled: false,
    heartbeat_enabled: true,
    clipboard_enabled: false,
    camera_enabled: false,
  };
  const result = await api("/api/admin/mobile-gateway/pairing-codes", { method: "POST", body: JSON.stringify(payload) });
  mobileGatewayActivePairingId = result.id;
  mobileGatewayActivePairingExpiresAt = result.expires_at || "";
  const box = $("#mobile-pairing-result");
  if (box) {
    box.dataset.pairingCode = result.pairing_code || "";
    box.className = "mobile-pairing-result";
    box.innerHTML = `<strong>${escapeHtml(result.pairing_code || "")}</strong><span>Đang chờ Poco F3 ghép nối...</span>`;
  }
  startMobilePairingTimers();
  await loadMobilePairingCodes();
}

async function loadMobilePairingCodes() {
  const data = await api("/api/admin/mobile-gateway/pairing-codes");
  const codes = data.codes || [];
  const table = $("#mobile-pairing-table");
  if (table) {
    table.innerHTML = codes.length ? codes.map((code) => {
      const statusInfo = mobileGatewayStatusText(code);
      const deviceName = code.used_by_device_id ? mobileDeviceLabel(code.used_by_device_id) : "-";
      return `<tr>
        <td><span class="status ${statusInfo.className}">${escapeHtml(statusInfo.text)}</span></td>
        <td>${escapeHtml(code.created_by || "")}</td>
        <td>${escapeHtml(mobileFormatTime(code.created_at))}</td>
        <td>${escapeHtml(mobileFormatTime(code.expires_at))}</td>
        <td>${escapeHtml(deviceName)}</td>
      </tr>`;
    }).join("") : emptyRow(5, "Chưa có mã ghép nối");
  }
  const active = codes.find((code) => String(code.id) === String(mobileGatewayActivePairingId));
  if (active && (active.used_at || active.status === "used")) {
    await loadMobileGatewayDevices();
    renderMobilePairingCountdown(`Đã kết nối: ${mobileDeviceLabel(active.used_by_device_id)} lúc ${mobileFormatTime(active.used_at)}`);
    stopMobilePairingTimers();
    mobileGatewayActivePairingId = null;
  }
}

function renderMobileGatewayDevices() {
  const table = $("#mobile-devices-table");
  if (!table) return;
  table.innerHTML = mobileGatewayDevices.length ? mobileGatewayDevices.map((device) => {
    const heartbeat = device.heartbeat || {};
    const active = device.is_active;
    const online = device.online;
    const statusClass = !active ? "inactive" : (online ? "viewer" : "pending");
    const statusText = !active ? "Đã thu hồi" : (online ? "Online" : "Offline");
    return `<tr>
      <td class="table-action-cell"><div class="action-group">
        <button class="table-action danger" data-mobile-revoke="${escapeHtml(device.device_id)}" type="button">${active ? "Thu hồi" : "Kích hoạt"}</button>
        <button class="table-action danger" data-mobile-delete="${escapeHtml(device.device_id)}" type="button" ${online ? "disabled" : ""}>Xóa</button>
      </div></td>
      <td><strong>${escapeHtml(device.name || device.device_id)}</strong><small class="cell-note">${escapeHtml(device.manufacturer || "")} ${escapeHtml(device.model || "")}</small></td>
      <td><span class="status ${statusClass}">${statusText}</span></td>
      <td>${escapeHtml(mobileFormatTime(device.last_seen_at))}<small class="cell-note">SMS permission: ${heartbeat.sms_permission ? "OK" : "-"} · Notification: ${heartbeat.notification_access ? "OK" : "-"}</small></td>
      <td>${escapeHtml(String(heartbeat.battery_percent ?? "-"))}%<small class="cell-note">${escapeHtml(heartbeat.charging ? "Đang sạc" : "")} ${escapeHtml(heartbeat.network_type || "")}</small></td>
      <td>${escapeHtml(device.app_version || "-")}<small class="cell-note">Android ${escapeHtml(device.android_version || "-")}</small></td>
      <td>${escapeHtml(String(heartbeat.pending_sms || 0))}</td>
    </tr>`;
  }).join("") : emptyRow(7, "Chưa có thiết bị");
  document.querySelectorAll("[data-mobile-revoke]").forEach((button) => button.addEventListener("click", () => toggleMobileDeviceActive(button.dataset.mobileRevoke)));
  document.querySelectorAll("[data-mobile-delete]").forEach((button) => button.addEventListener("click", () => deleteMobileDevice(button.dataset.mobileDelete)));
}

async function sendMobileMediaCommand(deviceId, commandType) {
  if (!deviceId) return;
  await api("/api/admin/mobile-gateway/commands", {
    method: "POST",
    body: JSON.stringify({
      device_id: deviceId,
      command_type: commandType,
      payload: { user_visible: true, message: commandType === "capture_photo" ? "Yêu cầu chụp ảnh từ quản trị viên" : "Yêu cầu quay video từ quản trị viên" },
    }),
  });
  showToast(commandType === "capture_photo" ? "Đã gửi yêu cầu chụp ảnh." : "Đã gửi yêu cầu quay video.");
  await loadMobileMedia();
}

async function deleteMobileDevice(deviceId) {
  if (!deviceId) return;
  const device = mobileGatewayDevices.find((item) => item.device_id === deviceId);
  const label = device?.name || deviceId;
  if (!confirm(`Xóa thiết bị đã ngừng kết nối: ${label}? SMS đã đồng bộ vẫn được giữ lại.`)) return;
  await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/delete`, { method: "POST" });
  showToast("Đã xóa thiết bị khỏi danh sách.");
  await loadMobileGateway({ force: true });
}

async function loadMobileGatewaySms({ force = false } = {}) {
  const deviceId = $("#mobile-sms-device-filter")?.value || "";
  const sender = $("#mobile-sms-sender-filter")?.value || "";
  const query = $("#mobile-sms-query-filter")?.value || "";
  const dateFrom = mobileGatewayDateStart($("#mobile-sms-date-from")?.value || "");
  const dateTo = mobileGatewayDateEnd($("#mobile-sms-date-to")?.value || "");
  const simSlot = $("#mobile-sms-sim-filter")?.value || "";
  if (force) setTableLoading("#mobile-sms-table", 5, "Đang tải SMS...");
  const data = await api(`/api/admin/mobile-gateway/sms?page=${mobileGatewaySmsPage}&page_size=50&device_id=${encodeURIComponent(deviceId)}&sender=${encodeURIComponent(sender)}&query=${encodeURIComponent(query)}&date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}&sim_slot=${encodeURIComponent(simSlot)}`);
  mobileGatewaySmsHasMore = Boolean(data.has_more);
  renderMobileSmsTable(data.items || []);
  const pageInfo = $("#mobile-sms-page-info");
  if (pageInfo) pageInfo.textContent = `Trang ${mobileGatewaySmsPage}`;
}

function renderMobileSmsTable(items) {
  const table = $("#mobile-sms-table");
  if (!table) return;
  table.replaceChildren();
  if (!items.length) {
    table.innerHTML = emptyRow(5, "Chưa có SMS");
    return;
  }
  items.forEach((sms) => {
    const row = document.createElement("tr");
    [sms.sender || "", mobileFormatTime(sms.received_at), sms.body || sms.body_masked || "", mobileDeviceLabel(sms.device_id), sms.sim_slot ?? "-"].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    table.appendChild(row);
  });
}

async function loadMobileOtpData() {
  const [filters, latest] = await Promise.all([
    api("/api/admin/mobile-gateway/otp/filters"),
    api("/api/admin/mobile-gateway/otp/latest?limit=100"),
  ]);
  mobileGatewayOtpFilters = filters.filters || [];
  mobileGatewayOtpLatest = latest.items || [];
  renderMobileOtpFilterForm();
  renderMobileOtpFilters();
  renderMobileOtpLatest();
}

function renderMobileOtpFilterForm() {
  const form = $("#mobile-otp-filter-form");
  if (!form || form.dataset.loaded === "true") return;
  const otpFilter = mobileGatewayOtpFilters.find((item) => item.filter_id === "onebss") || mobileGatewayOtpFilters[0];
  if (!otpFilter) return;
  form.dataset.loaded = "true";
  Object.entries(otpFilter).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value ?? "";
  });
}

function renderMobileOtpFilters() {
  const table = $("#mobile-otp-filters-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpFilters.length ? mobileGatewayOtpFilters.map((item) => `<tr>
    <td>${escapeHtml(item.filter_id || item.id || "")}</td>
    <td>${escapeHtml(item.rule_name || "")}<small class="cell-note">${escapeHtml(item.service_code || "")}</small></td>
    <td>${escapeHtml(item.sender_pattern || "")}<small class="cell-note">${escapeHtml(item.sender_match_type || "")}</small></td>
    <td>${escapeHtml(item.start_prefix || "-")}<small class="cell-note">${escapeHtml(String(item.otp_length || 6))} ký tự</small></td>
    <td>${escapeHtml(String(item.validity_seconds || 60))} giây</td>
    <td><span class="status ${item.enabled ? "viewer" : "inactive"}">${item.enabled ? "Bật" : "Tắt"}</span></td>
  </tr>`).join("") : emptyRow(6, "Chưa có quy tắc OTP");
}

async function saveMobileOtpFilter() {
  const form = $("#mobile-otp-filter-form");
  const data = Object.fromEntries(new FormData(form));
  const payload = {
    ...data,
    id: data.id ? Number(data.id) : null,
    enabled: Boolean(form.elements.namedItem("enabled")?.checked),
    otp_length: Number(data.otp_length || 6),
    validity_seconds: Number(data.validity_seconds || 60),
    priority: Number(data.priority || 100),
    sim_slot: data.sim_slot === "" ? null : Number(data.sim_slot),
  };
  await api("/api/admin/mobile-gateway/otp/filters", { method: "POST", body: JSON.stringify(payload) });
  form.dataset.loaded = "";
  showToast("Đã lưu quy tắc OTP.");
  await loadMobileOtpData();
}

function mobileOtpLatestStatus(item) {
  if (item.status === "used") return { text: "Đã sử dụng", className: "viewer", ttl: "-" };
  const expiresAt = Date.parse(item.expires_at || "");
  const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
  if (!expiresAt || remaining <= 0 || item.status === "expired") return { text: "Đã hết hiệu lực", className: "inactive", ttl: "0 giây" };
  return { text: "Còn hiệu lực", className: "pending", ttl: `${remaining} giây` };
}

function renderMobileOtpLatest() {
  const table = $("#mobile-otp-latest-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpLatest.length ? mobileGatewayOtpLatest.map((item) => {
    const statusInfo = mobileOtpLatestStatus(item);
    const code = item.code || item.code_masked || "null";
    return `<tr>
      <td>${escapeHtml(item.sender || "")}</td>
      <td>${escapeHtml(item.rule_name || item.filter_id || "")}</td>
      <td>${renderMobileOtpCopyCell(code)}</td>
      <td>${escapeHtml(mobileFormatTime(item.received_at))}</td>
      <td>${escapeHtml(statusInfo.ttl)}</td>
      <td><span class="status ${statusInfo.className}">${escapeHtml(statusInfo.text)}</span></td>
    </tr>`;
  }).join("") : emptyRow(6, "Chưa có OTP mới");
}

function startMobileOtpTicker() {
  if (window.mobileGatewayOtpTicker) return;
  window.mobileGatewayOtpTicker = setInterval(renderMobileOtpLatest, 1000);
  window.mobileGatewayOtpRefresh = setInterval(() => {
    if ($("#view-mobile-gateway")?.classList.contains("active")) loadMobileOtpData();
  }, 15000);
}

async function loadMobileNotifications({ force = false } = {}) {
  const deviceId = $("#mobile-notification-device-filter")?.value || "";
  const packageName = $("#mobile-notification-app-filter")?.value || "";
  const query = $("#mobile-notification-query-filter")?.value || "";
  if (force) setTableLoading("#mobile-notifications-table", 5, "Đang tải thông báo...");
  const data = await api(`/api/admin/mobile-gateway/notifications?page=${mobileGatewayNotificationPage}&page_size=50&device_id=${encodeURIComponent(deviceId)}&package_name=${encodeURIComponent(packageName)}&query=${encodeURIComponent(query)}`);
  mobileGatewayNotificationHasMore = Boolean(data.has_more);
  const table = $("#mobile-notifications-table");
  if (table) {
    table.innerHTML = (data.items || []).length ? data.items.map((item) => `<tr>
      <td>${escapeHtml(item.app_name || item.package_name || "")}<small class="cell-note">${escapeHtml(item.package_name || "")}</small></td>
      <td>${escapeHtml(item.title || "")}</td>
      <td>${escapeHtml(item.text || item.text_masked || "")}</td>
      <td>${escapeHtml(mobileFormatTime(item.posted_at))}</td>
      <td>${escapeHtml(mobileDeviceLabel(item.device_id))}</td>
    </tr>`).join("") : emptyRow(5, "Chưa có thông báo");
  }
  const pageInfo = $("#mobile-notification-page-info");
  if (pageInfo) pageInfo.textContent = `Trang ${mobileGatewayNotificationPage}`;
}

async function loadMobileMedia() {
  const deviceId = $("#mobile-media-device-filter")?.value || "";
  const mediaType = $("#mobile-media-type-filter")?.value || "";
  const data = await api(`/api/admin/mobile-gateway/media?page=1&page_size=50&device_id=${encodeURIComponent(deviceId)}&media_type=${encodeURIComponent(mediaType)}`);
  mobileGatewayMediaItems = data.items || [];
  renderMobileMediaDevices();
  renderMobileMediaTable();
}

function renderMobileMediaDevices() {
  const table = $("#mobile-media-devices-table");
  if (!table) return;
  table.innerHTML = mobileGatewayDevices.length ? mobileGatewayDevices.map((device) => {
    const heartbeat = device.heartbeat || {};
    const cameraEnabled = Boolean(device.policy?.camera_enabled);
    return `<tr>
      <td><strong>${escapeHtml(device.name || device.device_id)}</strong><small class="cell-note">${escapeHtml(device.model || "")}</small></td>
      <td><span class="status ${device.online ? "viewer" : "pending"}">${device.online ? "Online" : "Offline"}</span></td>
      <td><span class="status ${cameraEnabled ? "viewer" : "inactive"}">${cameraEnabled ? "Đã bật" : "Đang tắt"}</span></td>
      <td>${escapeHtml(mobileFormatTime(device.last_seen_at))}<small class="cell-note">${escapeHtml(heartbeat.network_type || "")}</small></td>
      <td class="table-action-cell"><div class="action-group">
        <button class="table-action" data-mobile-photo="${escapeHtml(device.device_id)}" type="button" ${cameraEnabled ? "" : "disabled"}>Chụp ảnh</button>
        <button class="table-action" data-mobile-video="${escapeHtml(device.device_id)}" type="button" ${cameraEnabled ? "" : "disabled"}>Quay video</button>
      </div></td>
    </tr>`;
  }).join("") : emptyRow(5, "Chưa có thiết bị");
  document.querySelectorAll("#mobile-media-devices-table [data-mobile-photo]").forEach((button) => button.addEventListener("click", () => sendMobileMediaCommand(button.dataset.mobilePhoto, "capture_photo")));
  document.querySelectorAll("#mobile-media-devices-table [data-mobile-video]").forEach((button) => button.addEventListener("click", () => sendMobileMediaCommand(button.dataset.mobileVideo, "record_video")));
}

function renderMobileMediaTable() {
  const table = $("#mobile-media-table");
  if (!table) return;
  table.innerHTML = mobileGatewayMediaItems.length ? mobileGatewayMediaItems.map((item) => {
    const preview = item.drive_url ? `<a href="${escapeHtml(item.drive_url)}" target="_blank" rel="noopener">${item.media_type === "video" ? "Video" : "Ảnh"}</a>` : "-";
    return `<tr>
      <td>${preview}</td>
      <td>${escapeHtml(mobileDeviceLabel(item.device_id))}</td>
      <td>${escapeHtml(item.media_type || "")}<small class="cell-note">${escapeHtml(item.mime_type || "")}</small></td>
      <td>${escapeHtml(mobileFormatTime(item.captured_at || item.uploaded_at || item.created_at))}</td>
      <td>${item.drive_url ? `<a href="${escapeHtml(item.drive_url)}" target="_blank" rel="noopener">${escapeHtml(item.file_name || "Google Drive")}</a>` : escapeHtml(item.file_name || "")}</td>
      <td><span class="status ${item.status === "uploaded" ? "viewer" : "inactive"}">${escapeHtml(item.status || "")}</span><small class="cell-note">${escapeHtml(item.error_message || "")}</small></td>
    </tr>`;
  }).join("") : emptyRow(6, "Chưa có media");
}

async function loadMobilePolicy() {
  const deviceId = $("#mobile-policy-device")?.value || "";
  if (!deviceId) return;
  const data = await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/policy`);
  const form = $("#mobile-policy-form");
  const policy = data.policy || {};
  Object.entries(policy).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else if (key === "notification_allowlist") field.value = (value || []).join("\n");
    else field.value = value ?? "";
  });
}

async function saveMobilePolicy() {
  const form = $("#mobile-policy-form");
  const deviceId = form.elements.namedItem("device_id")?.value || "";
  if (!deviceId) return showToast("Chọn thiết bị.", "error");
  const checkbox = (name) => Boolean(form.elements.namedItem(name)?.checked);
  const payload = {
    sms_enabled: checkbox("sms_enabled"),
    notifications_enabled: checkbox("notifications_enabled"),
    clipboard_enabled: checkbox("clipboard_enabled"),
    camera_enabled: checkbox("camera_enabled"),
    diagnostics_enabled: checkbox("diagnostics_enabled"),
    force_update: checkbox("force_update"),
    notification_allowlist: (form.elements.namedItem("notification_allowlist").value || "").split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean),
    heartbeat_interval_minutes: Number(form.elements.namedItem("heartbeat_interval_minutes").value || 15),
    sync_interval_minutes: Number(form.elements.namedItem("sync_interval_minutes").value || 15),
    batch_size: Number(form.elements.namedItem("batch_size").value || 50),
    local_retention_days: Number(form.elements.namedItem("local_retention_days").value || 14),
    minimum_app_version: form.elements.namedItem("minimum_app_version").value || "1.3.0",
  };
  await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/policy`, { method: "PUT", body: JSON.stringify(payload) });
  showToast("Đã lưu policy.");
  await loadMobileGatewayDevices();
}

$("#telegram-test-message")?.addEventListener("click", async () => {
  const button = $("#telegram-test-message");
  const resultBox = $("#telegram-test-result");
  setButtonLoading(button, true);
  try {
    const response = await api("/api/admin/telegram/test-message", { method: "POST" });
    showMessage(resultBox, response.message);
  } catch (error) {
    showMessage(resultBox, error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
});

$("#zalo-set-webhook")?.addEventListener("click", async () => {
  const button = $("#zalo-set-webhook");
  const resultBox = $("#zalo-webhook-result");
  setButtonLoading(button, true);
  try {
    const response = await api("/api/admin/zalo/webhook/setup", { method: "POST" });
    const webhookUrl = response.details?.webhook_url ? ` ${response.details.webhook_url}` : "";
    showMessage(resultBox, `${response.message}${webhookUrl}`);
    await loadConnections({ force: true });
  } catch (error) {
    showMessage(resultBox, error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
});

async function loadAudit({ force = false } = {}) {
  if (!force && isDataFresh("auditLogs")) {
    renderAuditLogs();
    return;
  }
  if (auditLogs.length && !force) {
    renderAuditLogs();
  }
  if (!auditLogs.length || force) setTableLoading("#audit-table", 4, "Đang tải nhật ký hoạt động...");
  auditLogs = (await api("/api/admin/audit-logs")).logs;
  markDataFresh("auditLogs");
  renderAuditLogs();
}

function renderAuditLogs() {
  $("#audit-table").innerHTML = auditLogs.length ? auditLogs.map((log) => `<tr><td>${new Date(log.created_at).toLocaleString("vi-VN")}</td><td><strong>${escapeHtml(log.actor)}</strong></td><td>${escapeHtml(log.action)}</td><td>${escapeHtml(log.details)}</td></tr>`).join("") : emptyRow(4, "Chưa có nhật ký", "Các thao tác quan trọng sẽ xuất hiện tại đây.");
}
