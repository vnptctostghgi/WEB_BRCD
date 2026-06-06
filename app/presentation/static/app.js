const $ = (selector) => document.querySelector(selector);
const role = document.body.dataset.role;
const canManageVault = document.body.dataset.canManageVault === "True";
const canRevealVault = document.body.dataset.canRevealVault === "True";
let users = [];
let websites = [];
let features = [];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
  $(`#view-${item.dataset.view}`).classList.add("active");
  $("#sidebar").classList.remove("menu-open");
  $("#menu-button")?.setAttribute("aria-expanded", "false");
  if (item.dataset.view === "users") await loadUsers();
  if (item.dataset.view === "vault") await loadCredentials();
  if (item.dataset.view === "websites") await loadAdminWebsites();
  if (item.dataset.view === "system") await loadSystem();
  if (item.dataset.view === "audit") await loadAudit();
}));

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.openDialog}`).showModal()));
document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

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
    form.reset();
  } catch (error) {
    showMessage(form.querySelector(".result"), error.message, "error");
  }
});

async function loadUsers() {
  setTableLoading("#users-table", 5, "Đang tải danh sách người dùng...");
  users = (await api("/api/admin/users")).users;
  $("#users-table").innerHTML = users.length ? users.map((user) => `
    <tr>
      <td><strong>${escapeHtml(user.username)}</strong>${user.must_change_password ? "<small class='cell-note'>Cần đổi mật khẩu</small>" : ""}</td>
      <td>${escapeHtml(user.full_name)}</td>
      <td><span class="status ${user.role === "admin" ? "admin" : "viewer"}">${user.role === "admin" ? "Quản trị viên" : "Người xem"}</span></td>
      <td><span class="status ${user.is_active ? "active" : "inactive"}">${user.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
      <td><button class="table-action" data-edit-user="${user.id}">Chỉnh sửa</button></td>
    </tr>`).join("") : emptyRow(5, "Chưa có người dùng", "Hãy tạo tài khoản đầu tiên để cấp quyền sử dụng hệ thống.");
  document.querySelectorAll("[data-edit-user]").forEach((button) => button.addEventListener("click", () => openEditUser(Number(button.dataset.editUser))));
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
  $("#connections-table").innerHTML = data.connections.length ? data.connections.map((connection) => `
    <tr>
      <td><strong>${escapeHtml(connection.name)}</strong><small class="cell-note">${escapeHtml(connection.description)}</small></td>
      <td><span class="status viewer">${escapeHtml(connection.connection_type)}</span></td>
      <td><span class="status ${connection.is_active ? "active" : "inactive"}">${connection.is_active ? "Đang dùng" : "Chưa cấu hình"}</span></td>
      <td><code>${escapeHtml(JSON.stringify(connection.config))}</code></td>
      <td>${escapeHtml(connection.secret_ref || "Không có")}</td>
      <td><button class="table-action" data-test-connection="${escapeHtml(connection.code)}"><span class="button-label">Kiểm tra</span><span class="spinner"></span></button><div class="cell-note" id="connection-result-${escapeHtml(connection.code)}"></div></td>
    </tr>`).join("") : emptyRow(6, "Chưa có kết nối", "Hãy cấu hình kết nối trong phần quản trị hệ thống.");
  document.querySelectorAll("[data-test-connection]").forEach((button) => {
    button.addEventListener("click", () => testConnection(button.dataset.testConnection, button));
  });
}

async function testConnection(code, button) {
  const resultBox = $(`#connection-result-${CSS.escape(code)}`);
  resultBox.textContent = "Đang kiểm tra...";
  setButtonLoading(button, true);
  try {
    const result = await api(`/api/admin/connections/${code}/test`, { method: "POST" });
    resultBox.textContent = result.message;
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
