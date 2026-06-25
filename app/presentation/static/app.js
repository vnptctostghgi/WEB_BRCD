const $ = (selector) => document.querySelector(selector);
const role = document.body.dataset.role;
let mustChangePassword = ["1", "True", "true"].includes(document.body.dataset.mustChange);
const canManageVault = document.body.dataset.canManageVault === "True";
const canRevealVault = document.body.dataset.canRevealVault === "True";
let users = [];
let websites = [];
let features = [];
let regions = [];
let connections = [];
let systemRoles = [];
let workTasks = [];
let sqlReports = [];
let dynamicReportPage = 1;
let dynamicReportTotal = 0;
let menuLayoutState = [];
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
const dashboardDataWidgetTypes = new Set(["bar_chart", "pie_chart", "line_chart", "combo_chart", "multi_bar_chart", "multi_line_chart", "data_table", "metric", "data_card"]);
const dashboardColorScaleStops = [
  { ratio: 0, rgb: [239, 68, 68] },
  { ratio: .5, rgb: [245, 158, 11] },
  { ratio: 1, rgb: [59, 130, 246] },
];
const chartJsSource = "https://cdn.jsdelivr.net/npm/chart.js";
let chartJsLoadPromise = null;
let dashboardChartRenderToken = 0;

const navFeatureConfig = {
  quanlycongviec: { view: "work-tasks", icon: "list", keywords: "quan ly cong viec task lich telegram nhac viec" },
  taikhoanweb: { view: "vault", icon: "vault", keywords: "tai khoan web mat khau" },
  quantringuoidung: { view: "users", icon: "users", keywords: "quan tri nguoi dung user" },
  quantrimenu: { view: "menu-admin", icon: "list", keywords: "quan tri menu sap xep di chuyen module" },
  quantridanhmuc: { view: "catalogs", icon: "list", keywords: "quan tri danh muc phan vung vai tro bien" },
  quantriketnoi: { view: "system", icon: "plug", keywords: "quan tri ket noi api db ftp drive telegram" },
  phanquyennguoidung: { view: "permissions", icon: "shield", keywords: "phan quyen nguoi dung chuc nang" },
  phanquyendulieunguoidung: { view: "data-permissions", icon: "database", keywords: "phan quyen du lieu phan vung" },
  nhatkyhoatdong: { view: "audit", icon: "audit", keywords: "nhat ky audit log" },
  truyvansql: { view: "reports", icon: "chart", keywords: "truy van sql bao cao thong ke bieu do" },
  thietkelayoutbaocao: { view: "dashboard-builder", icon: "chart", keywords: "dashboard builder thiet ke layout bao cao tab bieu do" },
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
  const body = await response.json();
  if (response.status === 403) {
    const message = body.detail || "Bạn không có quyền truy cập chức năng này";
    showToast(message, "error");
    throw new Error(message);
  }
  if (!response.ok) throw new Error(body.detail || "Có lỗi xảy ra.");
  return body;
}

function showMessage(element, text, type = "success") {
  element.className = `result ${type}`;
  element.textContent = repairTextEncoding(text);
}

let toastTimer;
function showToast(text, type = "success") {
  const toast = $("#toast");
  if (!toast) return;
  window.clearTimeout(toastTimer);
  toast.textContent = repairTextEncoding(text);
  toast.className = `toast ${type === "error" ? "error" : ""}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3200);
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

async function activateNavItem(item, options = {}) {
  const { updateUrl = true, replaceUrl = false } = options;
  const nextView = item.dataset.view || "";
  const dashboardPageId = item.dataset.dashboardPageId || "";
  $("#view-dashboard")?.classList.toggle("dashboard-dynamic-mode", Boolean(dashboardPageId));
  if (nextView !== "dashboard") dashboardViewerLoadedTabs = {};
  if (nextView !== "dashboard-builder") {
    dashboardBuilderLoadedTabs = {};
  }
  document.querySelectorAll(".nav-item, .app-view").forEach((element) => element.classList.remove("active"));
  item.classList.add("active");
  openNavParents(item);
  $(`#view-${item.dataset.view}`)?.classList.add("active");
  const moduleTitle = $("#module-title");
  if (moduleTitle) moduleTitle.textContent = item.dataset.title || item.textContent.trim();
  $("#sidebar").classList.remove("menu-open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  if (updateUrl) updateFeatureUrl(item.dataset.featureCode, { replace: replaceUrl });
  if (nextView === "dashboard" && dashboardPageId) {
    await openDashboardViewerLayout(dashboardPageId);
  }
  if (nextView === "users") await loadUsers();
  if (nextView === "vault") await loadCredentials();
  if (nextView === "websites") await loadAdminWebsites();
  if (nextView === "system") await loadSystem();
  if (nextView === "reports") await loadDynamicReports();
  if (nextView === "dashboard-builder") await loadDashboardBuilder();
  if (nextView === "menu-admin") await loadMenuLayout();
  if (nextView === "work-tasks") await loadWorkTasks();
  if (nextView === "permissions") await loadPermissionManager();
  if (nextView === "data-permissions") await loadDataPermissionManager();
  if (nextView === "catalogs") await loadCatalogs();
  if (nextView === "audit") await loadAudit();
}

$("#nav-tree")?.addEventListener("click", async (event) => {
  const item = event.target.closest(".nav-item[data-view]");
  if (!item || !$("#nav-tree")?.contains(item)) return;
  await activateNavItem(item);
});

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => {
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

if (role === "admin") {
  syncNavigationFromFeatures();
} else {
  activateNavForCurrentPath();
}

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
  dashboardPageIdByFeatureCode = new Map(dashboardViewerLayouts.map((layout) => [
    dashboardFeatureCodeForPageId(layout.page_id),
    layout.page_id,
  ]).filter(([code, pageId]) => code && pageId));
  dashboardFeatureCodes = new Set(dashboardPageIdByFeatureCode.keys());
}

async function loadDashboardViewer() {
  if (!$("#dashboard-designed-section")) return;
  try {
    if (!dashboardViewerLayoutsLoaded) {
      const data = await api("/api/admin/dashboard-layouts");
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
  const data = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(pageId)}`);
  dashboardViewerLayout = normalizeDashboardViewerLayout(data.layout || {}, data.page_name || "");
  dashboardViewerLayout.page_name = data.page_name || dashboardViewerLayout.page_name;
  dashboardViewerActiveTabId = dashboardViewerLayout.tabs[0]?.tab_id || "";
  dashboardViewerLoadedTabs = {};
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
  const key = dashboardViewerTabCacheKey(tabId);
  if (dashboardViewerLoadedTabs[key] && !force) {
    renderDashboardViewer();
    return;
  }
  const button = $("#refresh-dashboard-viewer-tab");
  if (button) setButtonLoading(button, true);
  try {
    const response = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(dashboardViewerLayout.page_id)}/tabs/${encodeURIComponent(tabId)}/data`);
    dashboardViewerLoadedTabs[key] = { ...response, loaded_at: new Date().toISOString() };
    renderDashboardViewer();
    $("#dashboard-viewer-message")?.classList.add("hidden");
  } catch (error) {
    showMessage($("#dashboard-viewer-message"), error.message, "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

function renderDashboardViewer() {
  if (!dashboardViewerLayout) return;
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
    const cells = Array.from({ length: columns }, (_, cellIndex) => {
      const position = cellIndex + 1;
      const widget = widgetsByPosition.get(position);
      const data = dataByWidget.get(`${row.row_id}:${position}`);
      return `<div class="dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}">${renderRuntimeWidget(widget, data, `dashboard-viewer-${rowIndex}-${position}`)}</div>`;
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

async function loadUsers() {
  setTableLoading("#users-table", 5, "Đang tải danh sách người dùng...");
  users = (await api("/api/admin/users")).users;
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
  await loadUsers();
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
  $("#permission-tree").querySelectorAll(".permission-item.parent input").forEach((parent) => {
    parent.addEventListener("change", () => {
      features.filter((feature) => feature.parent_code === parent.value).forEach((feature) => {
        const child = $("#permission-tree").querySelector(`input[value="${feature.code}"]`);
        if (child) child.checked = parent.checked;
      });
    });
  });
  $("#edit-user-dialog").showModal();
}

if (role === "admin") {
  $("#create-user-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api("/api/admin/users", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      form.reset();
      $("#create-user-dialog").close();
      await loadUsers();
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
      await loadUsers();
    } catch (error) {
      showMessage(form.querySelector(".result"), error.message, "error");
    }
  });

  $("#refresh-audit")?.addEventListener("click", loadAudit);
  $("#website-form")?.addEventListener("submit", saveWebsite);
  $("#region-form")?.addEventListener("submit", saveRegion);
  $("#role-form")?.addEventListener("submit", saveRole);
  $("#work-task-form")?.addEventListener("submit", saveWorkTask);
  $("#save-work-task-button")?.addEventListener("click", () => $("#work-task-form")?.requestSubmit());
  $("#connection-form")?.addEventListener("submit", saveConnection);
  $("#sql-report-form")?.addEventListener("submit", saveSqlReport);
  $("#new-dashboard-page")?.addEventListener("click", createDashboardPage);
  $("#new-dashboard-group")?.addEventListener("click", createDashboardGroup);
  $("#save-dashboard-layout")?.addEventListener("click", (event) => saveDashboardLayout(event.currentTarget));
  $("#refresh-dashboard-sql-reports")?.addEventListener("click", (event) => refreshDashboardSqlReports(event.currentTarget));
  $("#add-dashboard-tab")?.addEventListener("click", addDashboardTab);
  $("#dashboard-row-type") && ($("#dashboard-row-type").innerHTML = dashboardLayoutTypeOptions("2_columns"));
  $("#add-dashboard-row")?.addEventListener("click", () => addDashboardRow($("#dashboard-row-type")?.value || "2_columns"));
  $("#refresh-dashboard-preview")?.addEventListener("click", () => loadDashboardPreviewTab(dashboardBuilderActiveTabId, { force: true }));
  $("#dashboard-viewer-page")?.addEventListener("change", (event) => {
    if (event.currentTarget.value) openDashboardViewerLayout(event.currentTarget.value);
  });
  $("#dashboard-viewer-tabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-viewer-tab]");
    if (button) switchDashboardViewerTab(button.dataset.viewerTab);
  });
  $("#refresh-dashboard-viewer-tab")?.addEventListener("click", () => loadDashboardViewerTab(dashboardViewerActiveTabId, { force: true }));
  $("#dashboard-layout-pages")?.addEventListener("click", handleDashboardPageAction);
  $("#dashboard-builder-tabs")?.addEventListener("click", handleDashboardBuilderTabClick);
  $("#dashboard-builder-tabs")?.addEventListener("dblclick", handleDashboardBuilderTabRename);
  $("#dashboard-builder-tabs")?.addEventListener("dragstart", handleDashboardTabDragStart);
  $("#dashboard-builder-tabs")?.addEventListener("dragover", handleDashboardTabDragOver);
  $("#dashboard-builder-tabs")?.addEventListener("drop", handleDashboardTabDrop);
  $("#dashboard-builder-tabs")?.addEventListener("dragend", handleDashboardTabDragEnd);
  $("#dashboard-preview-tabs")?.addEventListener("click", handleDashboardPreviewTabClick);
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
    await runDynamicReport();
  });
  $("#dynamic-report-select")?.addEventListener("change", async () => {
    dynamicReportPage = 1;
    renderDynamicReportFilters();
    await runDynamicReport();
  });
  $("#dynamic-report-prev")?.addEventListener("click", async () => {
    if (dynamicReportPage <= 1) return;
    dynamicReportPage -= 1;
    await runDynamicReport();
  });
  $("#dynamic-report-next")?.addEventListener("click", async () => {
    const pageSize = Number($("#dynamic-report-page-size")?.value || 20);
    if (dynamicReportPage * pageSize >= dynamicReportTotal) return;
    dynamicReportPage += 1;
    await runDynamicReport();
  });
  $("#user-search")?.addEventListener("input", renderUsersTable);
  $("#user-import-file")?.addEventListener("change", importUserFile);
  $("#save-bulk-permissions")?.addEventListener("click", saveBulkPermissions);
  $("#save-data-permissions")?.addEventListener("click", saveDataPermissions);
}

async function importUserFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const data = new FormData();
  data.append("file", file);
  try {
    const result = await api("/api/admin/users/import", { method: "POST", body: data });
    showMessage($("#users-message"), `Đã thêm ${result.created_count} người dùng, bỏ qua ${result.skipped_count} dòng.`);
    await loadUsers();
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

async function loadAdminWebsites() {
  setTableLoading("#websites-table", 5, "Đang tải danh mục website...");
  websites = (await api("/api/admin/websites")).websites;
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
    await loadAdminWebsites();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function loadPermissionManager() {
  if (!users.length) users = (await api("/api/admin/users")).users;
  if (!features.length) features = (await api("/api/admin/features")).features;
  renderUserSelection("#permission-users");
  const orderedFeatures = flattenFeatureTree(buildFeatureTree(features)).map((row) => row.feature);
  $("#permission-features").innerHTML = orderedFeatures.map((feature) => `
    <label class="permission-item ${feature.parent_code ? "child" : "parent"}">
      <input type="checkbox" value="${escapeHtml(feature.code)}" />
      <span>${escapeHtml(feature.name)}</span>
    </label>`).join("");
}

async function saveBulkPermissions() {
  const user_ids = selectedNumbers("#permission-users");
  const feature_codes = selectedValues("#permission-features");
  await api("/api/admin/permissions/bulk", { method: "PUT", body: JSON.stringify({ user_ids, feature_codes }) });
  alert("Đã lưu phân quyền người dùng.");
}

async function loadDataPermissionManager() {
  if (!users.length) users = (await api("/api/admin/users")).users;
  renderUserSelection("#data-permission-users");
  regions = (await api("/api/admin/regions")).regions;
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

async function loadRoles() {
  setTableLoading("#roles-table", 6, "Đang tải vai trò người dùng...");
  systemRoles = (await api("/api/admin/roles")).roles;
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

async function loadCatalogs() {
  await Promise.all([loadRegions(), loadRoles()]);
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
    await loadRoles();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteRole(code) {
  if (!confirm(`Xóa vai trò ${code}?`)) return;
  try {
    await api(`/api/admin/roles/${encodeURIComponent(code)}`, { method: "DELETE" });
    showMessage($("#roles-message"), `Đã xóa vai trò ${code}.`);
    await loadRoles();
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
      applyDashboardLayoutList(navigationData.dashboard_layouts || []);
    } catch {
      features = (await api("/api/admin/features")).features;
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

async function loadMenuLayout() {
  features = (await api("/api/admin/features")).features;
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
        })).filter((widget) => widget.sql_code || widget.type === "text_title") : [],
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
  const extraLabels = {
    multi_bar_chart: "Biểu đồ cột nhiều đơn vị",
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
  return ["bar_chart", "multi_bar_chart", "pie_chart", "line_chart", "multi_line_chart", "combo_chart", "data_table", "metric", "data_card", "text_title"].map((type) => (
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
  return dashboardLayouts;
}

async function loadDashboardBuilder() {
  const message = $("#dashboard-builder-message");
  setTableLoading("#dashboard-layout-pages", 3, "Đang tải danh sách trang báo cáo...");
  try {
    const [pagesData, reportsData] = await Promise.all([
      api("/api/admin/dashboard-layout-pages"),
      api("/api/admin/sql-reports"),
    ]);
    dashboardLayouts = pagesData.pages || [];
    sqlReports = reportsData.reports || [];
    if (dashboardLayouts.length) {
      await openDashboardPage(dashboardLayouts[0].page_id);
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
    dashboardBuilderLayout = dashboardLayoutTemplate(page.page_name || page.feature_name || page.page_id, page.page_id);
    dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
    dashboardBuilderLoadedTabs = {};
    renderDashboardBuilder();
    renderDashboardPreview();
    return;
  }
  await openDashboardLayout(pageId);
}

async function openDashboardLayout(pageId) {
  const data = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(pageId)}`);
  const page = dashboardBuilderPageById(pageId);
  dashboardBuilderLayout = normalizeDashboardBuilderLayout(data.layout || {}, data.page_name || "");
  dashboardBuilderLayout.page_name = repairTextEncoding(page?.page_name || data.page_name || dashboardBuilderLayout.page_name);
  dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0]?.tab_id || "";
  dashboardBuilderLoadedTabs = {};
  renderDashboardBuilder();
  await loadDashboardPreviewTab(dashboardBuilderActiveTabId);
}

function createDashboardPage() {
  const pageName = prompt("Nhập tên trang báo cáo mới:", "Dashboard mới");
  if (pageName === null) return;
  const cleanedName = pageName.trim() || "Dashboard mới";
  dashboardBuilderLayout = dashboardLayoutTemplate(cleanedName, dashboardPageIdFromName(cleanedName));
  dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
  dashboardBuilderLoadedTabs = {};
  renderDashboardBuilder();
}

function createDashboardGroup() {
  const pageName = prompt("Nhập tên mục cha:", "Nhóm Dashboard mới");
  if (pageName === null) return;
  const cleanedName = pageName.trim() || "Nhóm Dashboard mới";
  dashboardBuilderLayout = dashboardLayoutTemplate(cleanedName, dashboardPageIdFromName(cleanedName), { empty: true });
  dashboardBuilderActiveTabId = dashboardBuilderLayout.tabs[0].tab_id;
  dashboardBuilderLoadedTabs = {};
  renderDashboardBuilder();
}

function renderDashboardBuilder() {
  if (!dashboardBuilderLayout) return;
  $("#dashboard-page-id").value = dashboardBuilderLayout.page_id || "";
  $("#dashboard-page-name").value = dashboardBuilderLayout.page_name || "";
  renderDashboardPages();
  renderDashboardBuilderTabs();
  renderDashboardWorkspace();
  renderDashboardPreview();
}

function renderDashboardPages() {
  const table = $("#dashboard-layout-pages");
  if (!table) return;
  const currentPageId = dashboardBuilderLayout?.page_id || "";
  const hasCurrent = dashboardLayouts.some((page) => page.page_id === currentPageId);
  const rows = [...dashboardLayouts];
  if (currentPageId && !hasCurrent) {
    rows.unshift({ page_id: currentPageId, page_name: dashboardBuilderLayout.page_name, unsaved: true });
  }
  table.innerHTML = rows.length ? rows.map((page) => `
    <tr class="${page.page_id === currentPageId ? "active-row" : ""}">
      <td class="table-action-cell">
        <div class="action-group">
          <button class="table-action" data-dashboard-open="${escapeHtml(page.page_id)}" type="button">Mở</button>
          <button class="table-action danger" data-dashboard-delete="${escapeHtml(page.page_id)}" type="button" ${page.unsaved ? "disabled" : ""}>Xóa</button>
        </div>
      </td>
      <td><strong>${escapeHtml(page.page_id)}</strong>${page.unsaved ? "<small class='cell-note'>Chưa lưu</small>" : ""}</td>
      <td>${escapeHtml(page.page_name || page.page_id)}</td>
    </tr>
  `).join("") : emptyRow(3, "Chưa có trang báo cáo", "Bấm Tạo trang báo cáo để bắt đầu thiết kế.");
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
  if (openButton) {
    openDashboardPage(openButton.dataset.dashboardOpen).catch((error) => showMessage($("#dashboard-builder-message"), error.message, "error"));
    return;
  }
  if (deleteButton) {
    deleteDashboardPage(deleteButton.dataset.dashboardDelete);
  }
}

async function deleteDashboardPage(pageId) {
  if (!confirm(`Xóa trang báo cáo ${pageId}?`)) return;
  try {
    await api(`/api/admin/dashboard-layouts/${encodeURIComponent(pageId)}`, { method: "DELETE" });
    showMessage($("#dashboard-builder-message"), "Đã xóa trang báo cáo.");
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
  if (pageId) dashboardBuilderLayout.page_id = pageId;
  if (pageName) dashboardBuilderLayout.page_name = repairTextEncoding(pageName);
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
        orientation: activeConfig?.querySelector("[name='chart_orientation']")?.value || "vertical",
        label_column: activeConfig?.querySelector("[name='label_column']")?.value.trim() || "",
        value_column: activeConfig?.querySelector("[name='value_column']")?.value.trim() || "",
        bar_column: activeConfig?.querySelector("[name='bar_column']")?.value.trim() || "",
        line_column: activeConfig?.querySelector("[name='line_column']")?.value.trim() || "",
        bar_label: activeConfig?.querySelector("[name='bar_label']")?.value.trim() || "",
        line_label: activeConfig?.querySelector("[name='line_label']")?.value.trim() || "",
        series_columns: activeConfig?.querySelector("[name='series_columns']")?.value.trim() || "",
        series_labels: activeConfig?.querySelector("[name='series_labels']")?.value.trim() || "",
        color_scale: Boolean(activeConfig?.querySelector("[name='color_scale']")?.checked),
      };
      const hasDisplayConfig = title || textContent || iconUrl || sqlCode;
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
    <div class="dashboard-widget-config ${type === "multi_bar_chart" ? "active" : ""}" data-config-for="multi_bar_chart">
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
    const isTextWidget = widget.type === "text_title";
    const report = dashboardReportByCode(widget.sql_code || "");
    const params = dashboardReportParams(report);
    const existingFilters = widget.filters && typeof widget.filters === "object" && !Array.isArray(widget.filters) ? widget.filters : {};
    const filterText = Object.keys(existingFilters).length ? dashboardFiltersToText(existingFilters) : dashboardParamFiltersToText(params);
    const showFilterField = !isTextWidget && (params.length || Object.keys(existingFilters).length);
    return `
      <div class="builder-widget-card dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}" data-position="${position}">
        <small>Ô ${position}</small>
        <label>Tiêu đề<input class="form-control" name="title" value="${escapeHtml(widget.title || "")}" placeholder="Tên biểu đồ, thẻ hoặc tiêu đề" /></label>
        <label>Loại hiển thị<select class="form-control" name="type">${dashboardWidgetTypeOptions(widget.type)}</select></label>
        <label class="dashboard-sql-field ${isTextWidget ? "hidden" : ""}">Mã SQL<select class="form-control" name="sql_code" data-previous-code="${escapeHtml(widget.sql_code || "")}">${dashboardSqlOptions(widget.sql_code || "", widget.report_id)}</select><small data-sql-param-hint>${escapeHtml(dashboardWidgetParamHint(widget.sql_code || ""))}</small></label>
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
    const payload = {
      page_id: dashboardBuilderLayout.page_id,
      page_name: dashboardBuilderLayout.page_name,
      layout: {
        page_id: dashboardBuilderLayout.page_id,
        tabs: dashboardBuilderLayout.tabs,
      },
    };
    const response = await api("/api/admin/dashboard-layouts", { method: "POST", body: JSON.stringify(payload) });
    dashboardBuilderLayout = normalizeDashboardBuilderLayout(response.layout || payload.layout, payload.page_name);
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
  const key = dashboardTabCacheKey(tabId);
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
    const response = await api(`/api/admin/dashboard-layouts/${encodeURIComponent(dashboardBuilderLayout.page_id)}/tabs/${encodeURIComponent(tabId)}/data`);
    dashboardBuilderLoadedTabs[key] = response;
    renderDashboardPreview();
    if (response.ok) showMessage($("#dashboard-preview-message"), response.message || "Đã tải dữ liệu Tab dashboard.", "success");
    else $("#dashboard-preview-message")?.classList.add("hidden");
  } catch (error) {
    showMessage($("#dashboard-preview-message"), error.message, "error");
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
    const cells = Array.from({ length: columns }, (_, cellIndex) => {
      const position = cellIndex + 1;
      const widget = widgetsByPosition.get(position);
      const data = dataByWidget.get(`${row.row_id}:${position}`);
      return `<div class="dashboard-layout-cell" style="${dashboardCellStyle(row.layout_type, cellIndex)}">${renderRuntimeWidget(widget, data, `dashboard-preview-${rowIndex}-${position}`)}</div>`;
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
}

function renderRuntimeWidget(widget, widgetData, elementId) {
  if (!widget) {
    return `<article class="runtime-widget-card"><div class="runtime-widget-empty">Ô trống</div></article>`;
  }
  const title = widget.title || widget.sql_code || "Tiêu đề";
  if (widget.type === "text_title") return renderRuntimeTextTitleWidget(widget);
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
  return renderRuntimeChartWidget(title, result, widget, elementId);
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

function renderRuntimeChartWidget(title, result, widget, elementId) {
  const chartData = widget.type === "combo_chart"
    ? extractDashboardComboChartData(result, widget.chart_config || {})
    : (widget.type === "multi_bar_chart" || widget.type === "multi_line_chart")
      ? extractDashboardMultiSeriesChartData(result, widget.chart_config || {})
      : extractDashboardChartData(result, widget.chart_config || {});
  if (!chartData.labels.length || (Array.isArray(chartData.series) && !chartData.series.length)) {
    return `<article class="runtime-widget-card"><h3>${escapeHtml(title)}</h3><div class="runtime-widget-empty">Không có dữ liệu để vẽ biểu đồ.</div></article>`;
  }
  const chartHeight = dashboardChartHeight(widget.type, chartData);
  pendingDashboardCharts.push({ elementId, widgetType: widget.type, chartData, chartConfig: widget.chart_config || {} });
  return `
    <article class="runtime-widget-card">
      <h3>${escapeHtml(title)}</h3>
      <div class="runtime-chart-box" style="--chart-height:${chartHeight}px"><canvas id="${escapeHtml(elementId)}"></canvas></div>
    </article>
  `;
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
    colorScale: Boolean(chartConfig.color_scale),
  };
}

function dashboardChartHeight(widgetType, chartData) {
  const count = Math.max(1, chartData.labels?.length || 1);
  const horizontal = widgetType === "bar_chart" && chartData.orientation === "horizontal";
  if (horizontal) return Math.min(1200, Math.max(280, count * 42 + 90));
  if (widgetType === "combo_chart") return Math.min(860, Math.max(320, count * 24 + 140));
  if (widgetType === "multi_bar_chart" || widgetType === "multi_line_chart") return Math.min(980, Math.max(340, count * 26 + 150));
  if (widgetType === "line_chart") return Math.min(780, Math.max(320, count * 18 + 120));
  if (widgetType === "bar_chart") return Math.min(900, Math.max(320, count * 24 + 130));
  return 320;
}

function dashboardChartPrimaryValues(chartData) {
  if (Array.isArray(chartData.series)) return chartData.series.flatMap((series) => series.values || []);
  return chartData.values || chartData.barValues || chartData.lineValues || [];
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

function dashboardValueColors(values, alpha = .86) {
  const numericValues = values.map((value) => Number(value));
  const finiteValues = numericValues.filter(Number.isFinite);
  if (!finiteValues.length) return values.map(() => "rgba(148, 163, 184, .72)");
  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  const range = max - min;
  return numericValues.map((value) => {
    if (!Number.isFinite(value)) return "rgba(148, 163, 184, .72)";
    const ratio = range === 0 ? .5 : (value - min) / range;
    return dashboardColorFromScaleRatio(ratio, alpha);
  });
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
      reject(new Error("KhÃ´ng táº£i Ä‘Æ°á»£c thÆ° viá»‡n biá»ƒu Ä‘á»“."));
    };
    document.head.appendChild(script);
  });
  return chartJsLoadPromise;
}

function schedulePendingDashboardCharts() {
  if (!pendingDashboardCharts.length) return;
  const token = dashboardChartRenderToken;
  window.requestAnimationFrame(() => renderPendingDashboardCharts(token));
}

function renderChartLoadError(jobs, message) {
  jobs.forEach(({ elementId }) => {
    const canvas = document.getElementById(elementId);
    const box = canvas?.closest(".runtime-chart-box");
    if (box) box.innerHTML = `<div class="runtime-widget-empty">${escapeHtml(message)}</div>`;
  });
}

async function renderPendingDashboardCharts(token = dashboardChartRenderToken) {
  const jobs = pendingDashboardCharts;
  pendingDashboardCharts = [];
  if (!jobs.length) return;
  if (token !== dashboardChartRenderToken) return;
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
    const useColorScale = Boolean(chartData.colorScale);
    const palette = useColorScale ? dashboardValueColors(dashboardChartPrimaryValues(chartData)) : ["#38bdf8", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa", "#14b8a6", "#f97316"];
    const isPie = widgetType === "pie_chart";
    const isLine = widgetType === "line_chart";
    const isCombo = widgetType === "combo_chart";
    const isMulti = widgetType === "multi_bar_chart" || widgetType === "multi_line_chart";
    const isMultiLine = widgetType === "multi_line_chart";
    const chartType = isCombo || isMulti && !isMultiLine ? "bar" : isPie ? "pie" : (isLine || isMultiLine) ? "line" : "bar";
    const seriesPalette = ["#38bdf8", "#f59e0b", "#22c55e", "#ef4444", "#a78bfa", "#14b8a6", "#f97316", "#60a5fa"];
    const datasets = isMulti ? chartData.series.map((series, seriesIndex) => ({
      label: series.label,
      data: series.values,
      backgroundColor: isMultiLine ? (useColorScale ? (context) => dashboardLineGradient(context, .16) : `${seriesPalette[seriesIndex % seriesPalette.length]}33`) : (useColorScale ? dashboardValueColors(series.values, .82) : `${seriesPalette[seriesIndex % seriesPalette.length]}cc`),
      borderColor: isMultiLine && useColorScale ? (context) => dashboardLineGradient(context, 1) : seriesPalette[seriesIndex % seriesPalette.length],
      pointBackgroundColor: isMultiLine ? seriesPalette[seriesIndex % seriesPalette.length] : undefined,
      borderWidth: isMultiLine ? 3 : 1,
      tension: .35,
      fill: isMultiLine,
    })) : isCombo ? [
      {
        type: "bar",
        label: chartData.barLabel,
        data: chartData.barValues,
        backgroundColor: useColorScale ? dashboardValueColors(chartData.barValues) : "rgba(56, 189, 248, .72)",
        borderColor: "#e0f2fe",
        borderWidth: 1,
        yAxisID: "y",
      },
      {
        type: "line",
        label: chartData.lineLabel,
        data: chartData.lineValues,
        borderColor: useColorScale ? (context) => dashboardLineGradient(context, 1) : "#2563eb",
        backgroundColor: useColorScale ? (context) => dashboardLineGradient(context, .18) : "rgba(37, 99, 235, .14)",
        pointBackgroundColor: useColorScale ? dashboardValueColors(chartData.lineValues) : "#2563eb",
        pointBorderColor: "#e0f2fe",
        pointRadius: 4,
        borderWidth: 3,
        tension: .35,
        yAxisID: "y1",
      },
    ] : [{
      label: "Giá trị",
      data: chartData.values,
      backgroundColor: isPie ? palette : isLine ? (useColorScale ? (context) => dashboardLineGradient(context, .18) : "rgba(37, 99, 235, .14)") : (useColorScale ? palette : "rgba(56, 189, 248, .72)"),
      borderColor: isPie ? "#061d38" : isLine && useColorScale ? (context) => dashboardLineGradient(context, 1) : "#2563eb",
      pointBackgroundColor: isLine ? (useColorScale ? palette : "#2563eb") : undefined,
      pointBorderColor: isLine ? "#e0f2fe" : undefined,
      pointRadius: isLine ? 4 : undefined,
      borderWidth: isLine ? 3 : 1,
      tension: .35,
      fill: isLine,
    }];
    const scales = isPie ? {} : isCombo ? {
      x: { ticks: { color: "#bae6fd", autoSkip: false, maxRotation: 55, minRotation: 0 }, grid: { color: "rgba(125, 211, 252, .1)" } },
      y: { beginAtZero: true, ticks: { color: "#bae6fd" }, grid: { color: "rgba(125, 211, 252, .12)" } },
      y1: { beginAtZero: true, position: "right", ticks: { color: "#fde68a" }, grid: { drawOnChartArea: false } },
    } : {
      x: { ticks: { color: "#bae6fd", autoSkip: false, maxRotation: 55, minRotation: 0 }, grid: { color: "rgba(125, 211, 252, .1)" } },
      y: { beginAtZero: true, ticks: { color: "#bae6fd", autoSkip: false }, grid: { color: "rgba(125, 211, 252, .12)" } },
    };
    const valueLabelPlugin = {
      id: `dashboardValueLabels-${elementId}`,
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        ctx.font = "700 11px Inter, system-ui, sans-serif";
        ctx.fillStyle = "#e0f2fe";
        chart.data.datasets.forEach((dataset, datasetIndex) => {
          const meta = chart.getDatasetMeta(datasetIndex);
          if (meta.hidden) return;
          meta.data.forEach((point, index) => {
            const value = dataset.data[index];
            if (value === null || value === undefined || Number.isNaN(Number(value))) return;
            const position = point.tooltipPosition();
            const horizontal = chart.options.indexAxis === "y" && dataset.type !== "line";
            ctx.textAlign = horizontal ? "left" : "center";
            ctx.fillText(formatDashboardNumber(value), position.x + (horizontal ? 8 : 0), position.y - (horizontal ? 0 : 8));
          });
        });
        ctx.restore();
      },
    };
    dashboardChartInstances.set(elementId, new Chart(canvas, {
      type: chartType,
      data: { labels: chartData.labels, datasets },
      options: {
        indexAxis: widgetType === "bar_chart" && chartData.orientation === "horizontal" ? "y" : "x",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: isPie || isCombo || isMulti, labels: { color: "#e0f2fe" } },
        },
        scales,
      },
      plugins: [valueLabelPlugin],
    }));
  });
}

function destroyDashboardCharts() {
  dashboardChartRenderToken += 1;
  dashboardChartInstances.forEach((chart) => chart.destroy());
  dashboardChartInstances.clear();
  pendingDashboardCharts = [];
}

async function loadRegions() {
  regions = (await api("/api/admin/regions")).regions;
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
    await loadRegions();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteRegion(code) {
  if (!confirm(`Xóa phân vùng ${code}? Các phân quyền dữ liệu liên quan cũng sẽ được xóa.`)) return;
  try {
    await api(`/api/admin/regions/${encodeURIComponent(code)}`, { method: "DELETE" });
    showMessage($("#regions-message"), `Đã xóa phân vùng ${code}.`);
    await loadRegions();
  } catch (error) {
    showMessage($("#regions-message"), error.message, "error");
  }
}

async function loadWorkTasks() {
  setTableLoading("#work-tasks-table", 9, "Đang tải lịch công việc...");
  workTasks = (await api("/api/admin/work-tasks")).tasks;
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
    await loadWorkTasks();
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
    await loadWorkTasks();
  } catch (error) {
    showMessage($("#work-tasks-message"), error.message, "error");
  }
}

async function deleteWorkTask(taskId) {
  if (!confirm(`Xóa lịch công việc ${taskId}?`)) return;
  try {
    await api(`/api/admin/work-tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
    showMessage($("#work-tasks-message"), `Đã xóa lịch ${taskId}.`);
    await loadWorkTasks();
  } catch (error) {
    showMessage($("#work-tasks-message"), error.message, "error");
  }
}

async function loadSystem() {
  $("#system-cards").innerHTML = loadingRow(1, "Đang tải thông tin hệ thống...");
  const data = await api("/api/admin/system");
  await loadConnections();
  await loadSqlReports();
  $("#system-cards").innerHTML = [
    ["APP", "Môi trường", data.environment],
    ["STO", "Database chính", data.storage_backend],
    ["API", "API dữ liệu", data.internal_api_mock_mode ? "Mock nội bộ" : data.internal_api_url],
    ["USR", "Người dùng hoạt động", `${data.active_user_count}/${data.user_count}`],
  ].map(([icon, label, value]) => `<article class="metric-card"><div class="metric-icon">${icon}</div><div><span>${label}</span><strong>${escapeHtml(value)}</strong></div></article>`).join("");
}

async function loadConnections() {
  setTableLoading("#connections-table", 6, "Đang tải kết nối hệ thống...");
  const data = await api("/api/admin/connections");
  connections = data.connections;
  $("#connections-table").innerHTML = connections.length ? connections.map((connection) => `
    <tr>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-connection="${escapeHtml(connection.code)}">Cấu hình</button><button class="table-action" data-test-connection="${escapeHtml(connection.code)}"><span class="button-label">Kiểm tra</span><span class="spinner"></span></button></div><div class="cell-note" id="connection-result-${escapeHtml(connection.code)}"></div></td>
      <td><strong>${escapeHtml(connection.name)}</strong><small class="cell-note">${escapeHtml(connection.description)}</small></td>
      <td><span class="status viewer">${escapeHtml(connection.connection_type)}</span></td>
      <td><span class="status ${connection.is_active ? "active" : "inactive"}">${connection.is_active ? "Đang dùng" : "Chưa cấu hình"}</span></td>
      <td class="compact-code-cell">${renderCompactCode(connection.config || {})}</td>
      <td>${escapeHtml(connection.secret_ref || "Không có")}</td>
    </tr>`).join("") : emptyRow(6, "Chưa có kết nối", "Hãy cấu hình kết nối trong phần quản trị hệ thống.");
  document.querySelectorAll("[data-edit-connection]").forEach((button) => {
    button.addEventListener("click", () => openConnection(button.dataset.editConnection));
  });
  document.querySelectorAll("[data-test-connection]").forEach((button) => {
    button.addEventListener("click", () => testConnection(button.dataset.testConnection, button));
  });
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
    await loadConnections();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function testConnection(code, button) {
  const resultBox = $(`#connection-result-${CSS.escape(code)}`);
  resultBox.textContent = "Đang kiểm tra...";
  setButtonLoading(button, true);
  try {
    const result = await api(`/api/admin/connections/${code}/test`, { method: "POST" });
    const details = result.details ? ` Chi tiết: ${JSON.stringify(result.details)}` : "";
    resultBox.textContent = `${result.message}${details}`;
    resultBox.style.color = result.ok ? "#166534" : "#991b1b";
  } catch (error) {
    resultBox.textContent = error.message;
    resultBox.style.color = "#991b1b";
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadSqlReports() {
  setTableLoading("#sql-reports-table", 5, "Đang tải cấu hình SQL...");
  try {
    const data = await api("/api/admin/sql-reports");
    sqlReports = data.reports || [];
    renderSqlReports();
    fillDynamicReportSelect();
    if (dashboardBuilderLayout) {
      collectDashboardBuilderStateFromDom();
      renderDashboardBuilder();
    }
    if (dashboardViewerLayout) renderDashboardViewer();
  } catch (error) {
    showMessage($("#sql-reports-message"), error.message, "error");
    $("#sql-reports-table").innerHTML = emptyRow(5, "Không tải được cấu hình SQL", error.message);
  }
}

function renderSqlReports() {
  const table = $("#sql-reports-table");
  if (!table) return;
  table.innerHTML = sqlReports.length ? sqlReports.map((report) => `
    <tr>
      <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-sql-report="${escapeHtml(report.id)}">Sửa</button><button class="table-action danger" data-delete-sql-report="${escapeHtml(report.id)}">Xóa</button></div></td>
      <td><strong>${escapeHtml(report.ten_bao_cao)}</strong></td>
      <td><code>${escapeHtml(report.ma_bao_cao)}</code></td>
      <td>${(report.cac_tham_so || []).map((item) => `<span class="status viewer">${escapeHtml(item)}</span>`).join(" ") || "Không có"}</td>
      <td class="compact-code-cell">${renderCompactCode(report.cau_lenh_sql || "")}</td>
    </tr>
  `).join("") : emptyRow(5, "Chưa có cấu hình SQL", "Bấm Thêm SQL để tạo báo cáo động đầu tiên.");
  document.querySelectorAll("[data-edit-sql-report]").forEach((button) => button.addEventListener("click", () => openSqlReport(button.dataset.editSqlReport)));
  document.querySelectorAll("[data-delete-sql-report]").forEach((button) => button.addEventListener("click", () => deleteSqlReport(button.dataset.deleteSqlReport)));
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
    await loadSqlReports();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function deleteSqlReport(reportId) {
  if (!confirm("Xóa cấu hình SQL này?")) return;
  try {
    await api(`/api/admin/sql-reports/${reportId}`, { method: "DELETE" });
    showMessage($("#sql-reports-message"), "Đã xóa cấu hình SQL.");
    await loadSqlReports();
  } catch (error) {
    showMessage($("#sql-reports-message"), error.message, "error");
  }
}

async function loadDynamicReports() {
  if (!sqlReports.length) {
    try {
      const data = await api("/api/reports/configs");
      sqlReports = data.reports || [];
    } catch (error) {
      showMessage($("#dynamic-report-message"), error.message, "error");
      return;
    }
  }
  fillDynamicReportSelect();
  renderDynamicReportFilters();
  if (sqlReports.length) await runDynamicReport();
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

async function runDynamicReport() {
  const select = $("#dynamic-report-select");
  const message = $("#dynamic-report-message");
  const button = $("#run-dynamic-report");
  if (!select || !select.value) {
    $("#dynamic-report-head").innerHTML = "";
    $("#dynamic-report-body").innerHTML = emptyRow(1, "Chưa có báo cáo", "Hãy thêm cấu hình SQL trong Quản trị kết nối.");
    return;
  }
  const filters = {};
  document.querySelectorAll(".dynamic-filter").forEach((input) => {
    if (input.value) filters[input.name] = input.value;
  });
  setButtonLoading(button, true);
  try {
    const response = await api("/api/reports/run", { method: "POST", body: JSON.stringify({
      ma_bao_cao: select.value,
      filters,
      page: dynamicReportPage,
      page_size: Number($("#dynamic-report-page-size")?.value || 20),
    })});
    renderDynamicReportTable(response);
    showMessage(message, response.message || "Đã tải dữ liệu báo cáo.");
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function renderDynamicReportTable(response) {
  const columns = response.columns || [];
  const rows = response.rows || [];
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

async function loadAudit() {
  setTableLoading("#audit-table", 4, "Đang tải nhật ký hoạt động...");
  const logs = (await api("/api/admin/audit-logs")).logs;
  $("#audit-table").innerHTML = logs.length ? logs.map((log) => `<tr><td>${new Date(log.created_at).toLocaleString("vi-VN")}</td><td><strong>${escapeHtml(log.actor)}</strong></td><td>${escapeHtml(log.action)}</td><td>${escapeHtml(log.details)}</td></tr>`).join("") : emptyRow(4, "Chưa có nhật ký", "Các thao tác quan trọng sẽ xuất hiện tại đây.");
}
