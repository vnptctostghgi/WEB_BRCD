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

document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", async () => {
  document.querySelectorAll(".nav-item, .app-view").forEach((element) => element.classList.remove("active"));
  item.classList.add("active");
  $(`#view-${item.dataset.view}`)?.classList.add("active");
  $("#module-title").textContent = item.dataset.title || item.textContent.trim();
  $("#sidebar").classList.remove("menu-open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  if (item.dataset.view === "users") await loadUsers();
  if (item.dataset.view === "vault") await loadCredentials();
  if (item.dataset.view === "websites") await loadAdminWebsites();
  if (item.dataset.view === "system") await loadSystem();
  if (item.dataset.view === "roles") await loadRoles();
  if (item.dataset.view === "permissions") await loadPermissionManager();
  if (item.dataset.view === "data-permissions") await loadDataPermissionManager();
  if (item.dataset.view === "catalogs") await loadRegions();
  if (item.dataset.view === "audit") await loadAudit();
}));

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => {
  if (button.dataset.openDialog === "region-dialog") {
    openRegion("");
    return;
  }
  if (button.dataset.openDialog === "role-dialog") {
    openRole("");
    return;
  }
  $(`#${button.dataset.openDialog}`).showModal();
}));
document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

$("#menu-search")?.addEventListener("input", (event) => filterNavigation(event.currentTarget.value));

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

$("#test-button")?.addEventListener("click", async () => {
  const button = $("#test-button");
  setButtonLoading(button, true);
  try {
    const data = await api("/api/health/database");
    $("#database-summary").textContent = data.ok ? "Đã kết nối" : "Kết nối lỗi";
    const detail = data.ok && data.details?.database_version ? ` Oracle ${data.details.database_version}.` : "";
    showMessage($("#result"), data.ok ? `${data.message}${detail}` : data.message, data.ok ? "success" : "error");
  } catch (error) {
    showMessage($("#result"), error.message, "error");
  } finally {
    setButtonLoading(button, false);
  }
});

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
  $("#permission-tree").innerHTML = features.map((feature) => `
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
  $("#connection-form")?.addEventListener("submit", saveConnection);
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

async function loadPermissionManager() {
  if (!users.length) users = (await api("/api/admin/users")).users;
  if (!features.length) features = (await api("/api/admin/features")).features;
  renderUserSelection("#permission-users");
  $("#permission-features").innerHTML = features.map((feature) => `
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

async function loadSystem() {
  $("#system-cards").innerHTML = loadingRow(1, "Đang tải thông tin hệ thống...");
  const data = await api("/api/admin/system");
  await loadConnections();
  $("#system-cards").innerHTML = [
    ["APP", "Môi trường", data.environment],
    ["STO", "Database chính", data.storage_backend],
    ["DB", "Oracle Service", data.oracle_service || "Chưa cấu hình"],
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

async function loadAdminWebsites() {
  setTableLoading("#websites-table", 5, "Đang tải danh mục website...");
  websites = (await api("/api/admin/websites")).websites;
  $("#websites-table").innerHTML = websites.length ? websites.map((website) => `<tr>
    <td><strong>${escapeHtml(website.name)}</strong></td>
    <td><a class="font-bold text-vnpt-600 hover:underline dark:text-sky-300" href="${escapeHtml(website.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(website.url)}</a></td>
    <td><span class="status ${website.requires_otp ? "pending" : "viewer"}">${website.requires_otp ? "Có OTP" : "Không OTP"}</span></td>
    <td><span class="status ${website.is_active ? "active" : "inactive"}">${website.is_active ? "Đang dùng" : "Ngừng dùng"}</span></td>
    <td><button class="table-action" data-edit-website="${website.id}">Chỉnh sửa</button></td></tr>`).join("") : emptyRow(5, "Chưa có website", "Thêm danh mục website để người dùng lưu tài khoản.");
  document.querySelectorAll("[data-edit-website]").forEach((button) => button.addEventListener("click", () => openWebsite(Number(button.dataset.editWebsite))));
}

function openWebsite(id) {
  const website = websites.find((item) => item.id === id);
  const form = $("#website-form");
  form.elements.namedItem("id").value = website.id;
  form.elements.namedItem("name").value = website.name;
  form.elements.namedItem("url").value = website.url;
  form.elements.namedItem("requires_otp").checked = Boolean(website.requires_otp);
  form.elements.namedItem("is_active").checked = Boolean(website.is_active);
  $("#website-dialog").showModal();
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
    form.reset();
    form.is_active.checked = true;
    $("#website-dialog").close();
    await loadAdminWebsites();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
}

async function loadCredentialWebsites() {
  websites = (await api("/api/websites")).websites;
  const select = $("#credential-website");
  if (!select) return;
  select.innerHTML = `<option value="">Chọn website</option>` + websites.map((website) => `<option value="${website.id}">${escapeHtml(website.name)}</option>`).join("");
  updateCredentialWebsite();
}

function updateCredentialWebsite() {
  const select = $("#credential-website");
  if (!select) return;
  const website = websites.find((item) => item.id === Number(select.value));
  $("#credential-url").value = website?.url || "";
  $("#credential-otp").textContent = website ? (website.requires_otp ? "Website này yêu cầu OTP khi đăng nhập." : "Website này không yêu cầu OTP.") : "";
}

async function loadCredentials() {
  setTableLoading("#credentials-table", 5, "Đang tải tài khoản website...");
  await loadCredentialWebsites();
  const credentials = (await api("/api/credentials")).credentials;
  $("#credentials-table").innerHTML = credentials.length ? credentials.map((credential) => `<tr>
    <td><strong>${escapeHtml(credential.website_name)}</strong></td>
    <td><a class="font-bold text-vnpt-600 hover:underline dark:text-sky-300" href="${escapeHtml(credential.url)}" target="_blank" rel="noopener noreferrer">Mở website</a></td>
    <td>${escapeHtml(credential.login_username)}</td>
    <td><span class="status ${credential.requires_otp ? "pending" : "viewer"}">${credential.requires_otp ? "Có OTP" : "Không OTP"}</span></td>
    <td class="action-group">${canRevealVault ? `<button class="table-action" data-reveal="${credential.id}">Xem mật khẩu</button>` : ""}${canManageVault ? `<button class="table-action danger" data-delete-credential="${credential.id}">Xóa</button>` : ""}</td></tr>`).join("") : emptyRow(5, "Chưa có tài khoản web", "Bấm thêm tài khoản để lưu thông tin đăng nhập của bạn.");
  document.querySelectorAll("[data-reveal]").forEach((button) => button.addEventListener("click", () => revealCredential(button)));
  document.querySelectorAll("[data-delete-credential]").forEach((button) => button.addEventListener("click", () => deleteCredential(Number(button.dataset.deleteCredential))));
}

async function revealCredential(button) {
  try {
    const data = await api(`/api/credentials/${button.dataset.reveal}/reveal`, { method: "POST" });
    button.textContent = data.password;
    setTimeout(() => { button.textContent = "Xem mật khẩu"; }, 10000);
  } catch (error) {
    alert(error.message);
  }
}

async function deleteCredential(id) {
  if (!confirm("Xóa tài khoản web này?")) return;
  await api(`/api/credentials/${id}`, { method: "DELETE" });
  await loadCredentials();
}

$("#credential-website")?.addEventListener("change", updateCredentialWebsite);
$("#credential-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/credentials", { method: "POST", body: JSON.stringify({ ...data, id: data.id ? Number(data.id) : null, website_id: Number(data.website_id) }) });
    form.reset();
    $("#credential-dialog").close();
    await loadCredentials();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
});
