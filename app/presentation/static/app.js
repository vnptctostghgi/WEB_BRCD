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

const navFeatureConfig = {
  dashboard: { view: "dashboard", icon: "dashboard", keywords: "tong quan dashboard" },
  "admin.work_tasks": { view: "work-tasks", icon: "list", keywords: "quan ly cong viec task lich telegram nhac viec" },
  vault: { view: "vault", icon: "vault", keywords: "tai khoan web mat khau" },
  "admin.users": { view: "users", icon: "users", keywords: "quan tri nguoi dung user" },
  "admin.menu": { view: "menu-admin", icon: "list", keywords: "quan tri menu sap xep di chuyen module" },
  "admin.catalogs": { view: "catalogs", icon: "list", keywords: "quan tri danh muc phan vung vai tro bien" },
  "admin.connections": { view: "system", icon: "plug", keywords: "quan tri ket noi api db ftp drive telegram" },
  "admin.permissions": { view: "permissions", icon: "shield", keywords: "phan quyen nguoi dung chuc nang" },
  "admin.data_permissions": { view: "data-permissions", icon: "database", keywords: "phan quyen du lieu phan vung" },
  "admin.audit": { view: "audit", icon: "audit", keywords: "nhat ky audit log" },
  reports: { view: "reports", icon: "chart", keywords: "bao cao thong ke bieu do" },
};

const navGroupIcons = {
  "admin.web": "shield",
  "admin.catalogs": "list",
  "admin.connections": "plug",
  vault: "vault",
  reports: "chart",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
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
  if (!response.ok) throw new Error(body.detail || "Có lỗi xảy ra.");
  return body;
}

function showMessage(element, text, type = "success") {
  element.className = `result ${type}`;
  element.textContent = text;
}

let toastTimer;
function showToast(text, type = "success") {
  const toast = $("#toast");
  if (!toast) return;
  window.clearTimeout(toastTimer);
  toast.textContent = text;
  toast.className = `toast ${type === "error" ? "error" : ""}`.trim();
  toastTimer = window.setTimeout(() => toast.classList.add("hidden"), 3200);
}

function loadingRow(colspan, text = "Đang tải dữ liệu...") {
  return `<tr><td colspan="${colspan}" class="loading-row">${escapeHtml(text)}</td></tr>`;
}

function emptyRow(colspan, title, description = "Chưa có dữ liệu để hiển thị.") {
  return `<tr><td colspan="${colspan}"><div class="empty-state"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div></div></td></tr>`;
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

async function activateNavItem(item) {
  document.querySelectorAll(".nav-item, .app-view").forEach((element) => element.classList.remove("active"));
  item.classList.add("active");
  $(`#view-${item.dataset.view}`)?.classList.add("active");
  $("#module-title").textContent = item.dataset.title || item.textContent.trim();
  $("#sidebar").classList.remove("menu-open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  if (item.dataset.view === "dashboard") await initDashboard();
  if (item.dataset.view === "users") await loadUsers();
  if (item.dataset.view === "vault") await loadCredentials();
  if (item.dataset.view === "websites") await loadAdminWebsites();
  if (item.dataset.view === "system") await loadSystem();
  if (item.dataset.view === "reports") await loadDynamicReports();
  if (item.dataset.view === "menu-admin") await loadMenuLayout();
  if (item.dataset.view === "work-tasks") await loadWorkTasks();
  if (item.dataset.view === "permissions") await loadPermissionManager();
  if (item.dataset.view === "data-permissions") await loadDataPermissionManager();
  if (item.dataset.view === "catalogs") await loadCatalogs();
  if (item.dataset.view === "audit") await loadAudit();
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
}

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

document.querySelectorAll("[data-dashboard-tab]").forEach((button) => {
  button.addEventListener("click", async () => {
    await switchDashboardTab(button.dataset.dashboardTab);
  });
});

$("#refresh-dashboard-fiber")?.addEventListener("click", () => loadDashboardFiber({ force: true }));

initDashboard();

async function initDashboard() {
  if (!$("#view-dashboard")) return;
  await loadDashboardFiber();
}

async function switchDashboardTab(tabName) {
  document.querySelectorAll("[data-dashboard-tab]").forEach((button) => {
    const active = button.dataset.dashboardTab === tabName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".dashboard-tab-panel").forEach((panel) => {
    const active = panel.id === `dashboard-tab-${tabName}`;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  if (tabName === "fiber") await loadDashboardFiber();
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

  $("#dashboard-summary-period").textContent = period;
  $("#dashboard-fiber-period").textContent = `${period}, lọc loại hình 58 và thuê bao chưa cắt.`;
  $("#dashboard-production-fiber").textContent = formatDashboardNumber(fiberTotal);

  renderDashboardFiberTable("vnpt", vnptRows);
  renderDashboardFiberTable("ttvt", ttvtRows);
  renderDashboardFiberChart("#dashboard-fiber-vnpt-chart", vnptRows);
  renderDashboardFiberChart("#dashboard-fiber-ttvt-chart", ttvtRows);
}

function renderDashboardFiberError(message) {
  $("#dashboard-production-fiber").textContent = "--";
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
      <td><strong>${escapeHtml(user.username)}</strong><small class='cell-note'>${escapeHtml(user.email || user.employee_code || "")}</small>${user.must_change_password ? "<small class='cell-note'>Cần đổi mật khẩu</small>" : ""}</td>
      <td>${escapeHtml(user.full_name)}<small class='cell-note'>${escapeHtml(user.department || "")}</small></td>
      <td><span class="status ${user.role === "admin" ? "admin" : "viewer"}">${user.role === "admin" ? "Quản trị viên" : "Người xem"}</span></td>
      <td><span class="status ${user.is_active ? "active" : "inactive"}">${user.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
      <td><button class="table-action" data-edit-user="${user.id}">Chỉnh sửa</button> <button class="table-action danger" data-delete-user="${user.id}">Xóa</button></td>
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
      <td><strong>${escapeHtml(website.name)}</strong></td>
      <td><a class="text-sky-200 hover:underline" href="${escapeHtml(website.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(website.url)}</a></td>
      <td><span class="status ${website.requires_otp ? "pending" : "viewer"}">${website.requires_otp ? "Có OTP" : "Không"}</span></td>
      <td><span class="status ${website.is_active ? "active" : "inactive"}">${website.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
      <td><button class="table-action" data-edit-website="${website.id}" type="button">Sửa</button></td>
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
      <td><strong>${escapeHtml(roleItem.code)}</strong></td>
      <td>${escapeHtml(roleItem.name)}</td>
      <td>${escapeHtml(roleItem.description || "")}</td>
      <td><span class="status ${roleItem.is_active ? "active" : "inactive"}">${roleItem.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
      <td>${escapeHtml(roleItem.sort_order)}</td>
      <td><button class="table-action" data-edit-role="${escapeHtml(roleItem.code)}">Sửa</button> <button class="table-action danger" data-delete-role="${escapeHtml(roleItem.code)}">Xóa</button></td>
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
  return navFeatureConfig[feature.code]?.icon || navGroupIcons[feature.code] || "list";
}

function iconMarkup(icon) {
  return `<svg class="nav-svg"><use href="#icon-${escapeHtml(icon)}"></use></svg>`;
}

function navNodeHasVisibleItem(node) {
  if (navFeatureConfig[node.feature.code]?.view) return true;
  return node.children.some((child) => navNodeHasVisibleItem(child));
}

function renderNavigationButton(feature, level) {
  const config = navFeatureConfig[feature.code];
  if (!config?.view) return "";
  const classes = ["nav-item"];
  if (level > 0) classes.push("child");
  if (level > 1) classes.push("subchild");
  const title = feature.name || feature.code;
  const keywords = `${config.keywords || ""} ${feature.name || ""} ${feature.code}`;
  return `
    <button class="${classes.join(" ")}" data-feature-code="${escapeHtml(feature.code)}" data-view="${escapeHtml(config.view)}" data-title="${escapeHtml(title)}" data-keywords="${escapeHtml(keywords)}">
      ${iconMarkup(config.icon || "list")}<span>${escapeHtml(title)}</span>
    </button>
  `;
}

function renderNavigationNode(node, level = 0) {
  const visibleChildren = node.children.filter((child) => navNodeHasVisibleItem(child));
  const canOpenView = Boolean(navFeatureConfig[node.feature.code]?.view);
  if (!visibleChildren.length) return renderNavigationButton(node.feature, level);
  const groupClass = `nav-group${level > 0 ? " nav-subgroup" : ""}`;
  const children = [
    canOpenView ? renderNavigationButton(node.feature, level + 1) : "",
    ...visibleChildren.map((child) => renderNavigationNode(child, level + 1)),
  ].join("");
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

function openNavParents(item) {
  let parent = item.parentElement;
  while (parent) {
    if (parent.matches?.(".nav-group")) parent.open = true;
    parent = parent.parentElement;
  }
}

async function syncNavigationFromFeatures() {
  try {
    features = (await api("/api/admin/features")).features;
    const tree = $("#nav-tree");
    if (!tree) return;
    const activeCode = tree.querySelector(".nav-item.active")?.dataset.featureCode || "dashboard";
    const html = buildFeatureTree(features)
      .filter((node) => navNodeHasVisibleItem(node))
      .map((node) => renderNavigationNode(node))
      .join("");
    if (html.trim()) tree.innerHTML = html;
    const activeItem = findNavItemByFeatureCode(activeCode) || findNavItemByFeatureCode("dashboard") || tree.querySelector(".nav-item[data-view]");
    if (activeItem) {
      activeItem.classList.add("active");
      openNavParents(activeItem);
    }
    filterNavigation($("#menu-search")?.value || "");
  } catch {
    // Nếu API layout chưa sẵn sàng, sidebar vẫn dùng cấu trúc tĩnh đã render từ server.
  }
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
        <td><div class="menu-feature-cell" style="--menu-level:${level}"><strong>${escapeHtml(feature.code)}</strong><small>Cấp ${level + 1}</small></div></td>
        <td><input class="form-control" name="name" value="${escapeHtml(feature.name)}" /></td>
        <td><select class="form-control" name="parent_code">${renderParentOptions(feature)}</select></td>
        <td>
          <div class="action-group menu-move-actions">
            <button class="table-action" data-menu-move="up" data-menu-code="${escapeHtml(feature.code)}" type="button" ${siblingIndex <= 0 ? "disabled" : ""}>Lên</button>
            <button class="table-action" data-menu-move="down" data-menu-code="${escapeHtml(feature.code)}" type="button" ${siblingIndex >= siblings.length - 1 ? "disabled" : ""}>Xuống</button>
          </div>
        </td>
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

async function loadRegions() {
  regions = (await api("/api/admin/regions")).regions;
  $("#regions-table").innerHTML = regions.length ? regions.map((region) => `
    <tr>
      <td><strong>${escapeHtml(region.code)}</strong></td>
      <td>${escapeHtml(region.name)}</td>
      <td><span class="status ${region.is_active ? "active" : "inactive"}">${region.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
      <td>${escapeHtml(region.sort_order)}</td>
      <td><button class="table-action" data-edit-region="${escapeHtml(region.code)}">Sửa</button> <button class="table-action danger" data-delete-region="${escapeHtml(region.code)}">Xóa</button></td>
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
      <td><strong>${escapeHtml(task.task_id)}</strong></td>
      <td>${escapeHtml(task.ten_cong_viec)}${task.last_notified_at ? `<small class="cell-note">Đã nhắc: ${escapeHtml(new Date(task.last_notified_at).toLocaleString("vi-VN"))}</small>` : ""}</td>
      <td><span class="status viewer">${escapeHtml(task.type)}</span></td>
      <td><strong>${escapeHtml(task.time)}</strong></td>
      <td>${escapeHtml(task.weekday || "-")}</td>
      <td>${escapeHtml(task.once_date || "-")}</td>
      <td>${escapeHtml(task.group || "-")}</td>
      <td><span class="status ${task.check ? "active" : "inactive"}">${task.check ? "Đã xong" : "Đang chờ"}</span></td>
      <td>
        <div class="action-group">
          <button class="table-action" data-edit-work-task="${escapeHtml(task.task_id)}">Sửa</button>
          <button class="table-action" data-complete-work-task="${escapeHtml(task.task_id)}">Hoàn thành</button>
          <button class="table-action danger" data-delete-work-task="${escapeHtml(task.task_id)}">Xóa</button>
        </div>
      </td>
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
      <td><strong>${escapeHtml(connection.name)}</strong><small class="cell-note">${escapeHtml(connection.description)}</small></td>
      <td><span class="status viewer">${escapeHtml(connection.connection_type)}</span></td>
      <td><span class="status ${connection.is_active ? "active" : "inactive"}">${connection.is_active ? "Đang dùng" : "Chưa cấu hình"}</span></td>
      <td><code>${escapeHtml(JSON.stringify(connection.config))}</code></td>
      <td>${escapeHtml(connection.secret_ref || "Không có")}</td>
      <td><div class="action-group"><button class="table-action" data-edit-connection="${escapeHtml(connection.code)}">Cấu hình</button><button class="table-action" data-test-connection="${escapeHtml(connection.code)}"><span class="button-label">Kiểm tra</span><span class="spinner"></span></button></div><div class="cell-note" id="connection-result-${escapeHtml(connection.code)}"></div></td>
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
      <td><strong>${escapeHtml(report.ten_bao_cao)}</strong></td>
      <td><code>${escapeHtml(report.ma_bao_cao)}</code></td>
      <td>${(report.cac_tham_so || []).map((item) => `<span class="status viewer">${escapeHtml(item)}</span>`).join(" ") || "Không có"}</td>
      <td><code>${escapeHtml(report.cau_lenh_sql)}</code></td>
      <td><div class="action-group"><button class="table-action" data-edit-sql-report="${report.id}">Sửa</button><button class="table-action danger" data-delete-sql-report="${report.id}">Xóa</button></div></td>
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
    container.innerHTML = `<div class="empty-state"><strong>Chưa có tham số</strong><p>Hãy tạo cấu hình SQL trước.</p></div>`;
    return;
  }
  const params = report.cac_tham_so || [];
  container.innerHTML = params.length ? params.map((param) => {
    const lower = param.toLowerCase();
    if (lower.includes("ngay") || lower.includes("date")) {
      return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" type="date" /></label>`;
    }
    if (lower.includes("status") || lower.includes("trang_thai")) {
      return `<label>${escapeHtml(param)}<select class="form-control dynamic-filter" name="${escapeHtml(param)}"><option value="">Tất cả</option><option value="1">Đang hoạt động</option><option value="0">Không hoạt động</option></select></label>`;
    }
    return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" placeholder="Nhập ${escapeHtml(param)}" /></label>`;
  }).join("") : `<div class="empty-state"><strong>Không có tham số lọc</strong><p>Báo cáo này sẽ chạy trực tiếp theo SQL đã cấu hình.</p></div>`;
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
