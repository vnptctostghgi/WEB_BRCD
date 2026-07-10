// Focused Mobile Gateway UI for SMS + OTP. Loaded after app.js on purpose.

function normalizeMobileGatewayUi() {
  const root = $("#view-mobile-gateway");
  if (!root) return;
  const activeTab = root.querySelector("[data-mobile-tab].active")?.dataset.mobileTab || "overview";
  const safeTab = ["overview", "devices-config", "sms", "otp"].includes(activeTab) ? activeTab : "overview";
  const actionGroup = root.querySelector(".page-header .action-group");
  if (actionGroup) actionGroup.innerHTML = "";
  const tabs = root.querySelector(".mobile-gateway-tabs");
  if (tabs) {
    tabs.innerHTML = `
      <button class="mobile-gateway-tab ${safeTab === "overview" ? "active" : ""}" data-mobile-tab="overview" type="button">Tổng quan</button>
      <button class="mobile-gateway-tab ${safeTab === "devices-config" ? "active" : ""}" data-mobile-tab="devices-config" type="button">Thiết bị</button>
      <button class="mobile-gateway-tab ${safeTab === "sms" ? "active" : ""}" data-mobile-tab="sms" type="button">SMS</button>
      <button class="mobile-gateway-tab ${safeTab === "otp" ? "active" : ""}" data-mobile-tab="otp" type="button">OTP</button>
      <button class="btn-secondary mobile-refresh-tab" id="mobile-refresh" type="button">Làm mới</button>`;
  }
  const overviewPanel = root.querySelector('[data-mobile-panel="overview"]');
  if (overviewPanel) overviewPanel.classList.toggle("active", safeTab === "overview");
  const devicesPanel = root.querySelector('[data-mobile-panel="devices"], [data-mobile-panel="devices-config"]');
  if (devicesPanel) {
    devicesPanel.dataset.mobilePanel = "devices-config";
    devicesPanel.classList.toggle("active", safeTab === "devices-config");
    devicesPanel.innerHTML = `
      <section class="data-card">
        <div class="section-heading">
          <div><p class="eyebrow">Kết nối</p><h2>Điện thoại đọc SMS</h2></div>
          <button class="btn-primary" id="mobile-create-pairing-code" type="button">Tạo mã ghép nối</button>
        </div>
        <div id="mobile-pairing-result" class="mobile-pairing-result hidden"></div>
      </section>
      <section class="data-card mt-4">
        <div class="section-heading"><div><p class="eyebrow">Thiết bị</p><h2>Danh sách điện thoại</h2></div></div>
        <div class="table-scroll"><table><thead><tr><th class="table-action-column">Thao tác</th><th>Thiết bị</th><th>Trạng thái</th><th>Lần đồng bộ</th><th>Phiên bản</th><th>SMS chờ</th></tr></thead><tbody id="mobile-devices-table"></tbody></table></div>
      </section>`;
  }
  const smsPanel = root.querySelector('[data-mobile-panel="sms"]');
  if (smsPanel) {
    smsPanel.classList.toggle("active", safeTab === "sms");
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
        <div class="table-scroll"><table><thead><tr><th>Người gửi</th><th>Thời gian nhận</th><th>Nội dung tin nhắn</th><th>Thiết bị</th><th>SIM</th></tr></thead><tbody id="mobile-sms-table"></tbody></table></div>
        <div class="mt-4 flex items-center justify-between gap-3"><span id="mobile-sms-page-info">Trang 1</span><div class="action-group"><button class="btn-secondary" id="mobile-sms-prev" type="button">Trang trước</button><button class="btn-secondary" id="mobile-sms-next" type="button">Trang sau</button></div></div>
      </section>`;
  }
  const otpPanel = root.querySelector('[data-mobile-panel="otp"]');
  if (otpPanel) {
    otpPanel.classList.toggle("active", safeTab === "otp");
    otpPanel.innerHTML = `
      <section class="grid gap-4 xl:grid-cols-[.85fr_1.15fr]">
        <div class="data-card">
          <div class="section-heading"><div><p class="eyebrow">Quy tắc</p><h2>Lọc OTP theo SMS</h2></div><button class="btn-primary" id="mobile-save-otp-filter" type="button">Lưu quy tắc</button></div>
          <form id="mobile-otp-filter-form" class="mobile-form-grid">
            <input type="hidden" name="id" />
            <label>Mã OTP<input class="form-control" name="filter_id" value="onebss" required /></label>
            <label>Người gửi<input class="form-control" name="sender_pattern" value="293" required /></label>
            <label>Số lượng ký tự OTP<input class="form-control" name="otp_length" type="number" value="6" min="1" max="12" /></label>
            <label>Ký tự bắt đầu<input class="form-control" name="start_prefix" placeholder="Ví dụ: 1364" /></label>
            <label class="checkbox-label"><input type="checkbox" name="enabled" checked /> Cho phép sử dụng tự động</label>
          </form>
          <div class="table-scroll mt-4"><table><thead><tr><th>Mã OTP</th><th>Người gửi</th><th>Số ký tự</th><th>Bắt đầu</th><th>Tự động</th></tr></thead><tbody id="mobile-otp-filters-table"></tbody></table></div>
        </div>
        <div class="data-card">
          <div class="section-heading"><div><p class="eyebrow">OTP</p><h2>OTP mới nhất theo mã</h2></div><button class="btn-secondary" id="mobile-refresh-otp" type="button">Làm mới</button></div>
          <div class="table-scroll"><table><thead><tr><th>Mã OTP</th><th>Người gửi</th><th>OTP</th><th>Thời gian nhận SMS</th><th>Trạng thái 60s</th></tr></thead><tbody id="mobile-otp-latest-table"></tbody></table></div>
        </div>
      </section>`;
  }
  ["commands", "logs", "settings", "notifications", "media"].forEach((name) => root.querySelector(`[data-mobile-panel="${name}"]`)?.remove());
  bindMobileGatewayFocusedEvents();
}

function bindMobileGatewayFocusedEvents() {
  document.querySelectorAll("#view-mobile-gateway [data-mobile-tab]").forEach((button) => {
    if (button.dataset.boundFocusedClick) return;
    button.dataset.boundFocusedClick = "true";
    button.addEventListener("click", () => activateMobileGatewayTab(button.dataset.mobileTab));
  });
  const bind = (selector, eventName, handler) => {
    const element = $(selector);
    if (!element) return;
    const key = `boundFocused${eventName}`;
    if (element.dataset[key]) return;
    element.dataset[key] = "true";
    element.addEventListener(eventName, handler);
  };
  bind("#mobile-refresh", "click", () => loadMobileGateway({ force: true }));
  bind("#mobile-create-pairing-code", "click", createMobilePairingCode);
  ["#mobile-sms-device-filter", "#mobile-sms-sender-filter", "#mobile-sms-query-filter", "#mobile-sms-date-from", "#mobile-sms-date-to", "#mobile-sms-sim-filter"].forEach((selector) => {
    ["input", "change"].forEach((eventName) => bind(selector, eventName, () => {
      mobileGatewaySmsPage = 1;
      window.mobileGatewayKnownSmsReady = false;
      loadMobileGatewaySms({ force: true });
    }));
  });
  bind("#mobile-sms-prev", "click", () => {
    mobileGatewaySmsPage = Math.max(1, mobileGatewaySmsPage - 1);
    window.mobileGatewayKnownSmsReady = false;
    loadMobileGatewaySms({ force: true });
  });
  bind("#mobile-sms-next", "click", () => {
    if (!mobileGatewaySmsHasMore) return;
    mobileGatewaySmsPage += 1;
    window.mobileGatewayKnownSmsReady = false;
    loadMobileGatewaySms({ force: true });
  });
  bind("#mobile-save-otp-filter", "click", saveMobileOtpFilter);
  bind("#mobile-refresh-otp", "click", loadMobileOtpData);
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

function renderMobileGatewayOverview() {
  const cards = [
    ["Online", mobileGatewayOverview.devices_online || 0],
    ["Offline", mobileGatewayOverview.devices_offline || 0],
    ["SMS hôm nay", mobileGatewayOverview.sms_today || 0],
    ["OTP hôm nay", mobileGatewayOverview.otp_today || 0],
    ["OTP thành công", mobileGatewayOverview.otp_success || 0],
    ["OTP timeout", mobileGatewayOverview.otp_timeout || 0],
    ["Cảnh báo", mobileGatewayOverview.device_alerts || 0],
  ];
  const target = $("#mobile-overview-cards");
  if (target) {
    target.innerHTML = cards.map(([label, value]) => `<article class="status-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>`).join("");
  }
  renderMobileRecentSms(mobileGatewayOverview.recent_sms || []);
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
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    table.appendChild(row);
  });
}

function renderMobileGatewayDeviceOptions() {
  const options = mobileGatewayDevices.map((device) => `<option value="${escapeHtml(device.device_id)}">${escapeHtml(device.name || device.device_id)}</option>`).join("");
  const select = $("#mobile-sms-device-filter");
  if (select) select.innerHTML = `<option value="">Tất cả</option>${options}`;
}

function renderMobileGatewayDevices() {
  const table = $("#mobile-devices-table");
  if (!table) return;
  table.innerHTML = mobileGatewayDevices.length ? mobileGatewayDevices.map((device) => {
    const heartbeat = device.heartbeat || {};
    const active = device.is_active;
    const online = device.online;
    const statusClass = !active ? "inactive" : (online ? "viewer" : "pending");
    const statusText = !active ? "Đã hủy ghép nối" : (online ? "Online" : "Offline");
    return `<tr>
      <td class="table-action-cell"><div class="action-group">
        <button class="table-action danger" data-mobile-revoke="${escapeHtml(device.device_id)}" type="button">${active ? "Hủy ghép nối" : "Kích hoạt"}</button>
        <button class="table-action danger" data-mobile-delete="${escapeHtml(device.device_id)}" type="button" ${online ? "disabled" : ""}>Xóa</button>
      </div></td>
      <td><strong>${escapeHtml(device.name || device.device_id)}</strong><small class="cell-note">${escapeHtml(device.manufacturer || "")} ${escapeHtml(device.model || "")}</small></td>
      <td><span class="status ${statusClass}">${escapeHtml(statusText)}</span></td>
      <td>${escapeHtml(mobileFormatTime(device.last_seen_at))}<small class="cell-note">Quyền SMS: ${heartbeat.sms_permission ? "OK" : "-"}</small></td>
      <td>${escapeHtml(device.app_version || "-")}<small class="cell-note">Android ${escapeHtml(device.android_version || "-")}</small></td>
      <td>${escapeHtml(String(heartbeat.pending_sms || 0))}</td>
    </tr>`;
  }).join("") : emptyRow(6, "Chưa có thiết bị");
  document.querySelectorAll("[data-mobile-revoke]").forEach((button) => button.addEventListener("click", () => toggleMobileDeviceActive(button.dataset.mobileRevoke)));
  document.querySelectorAll("[data-mobile-delete]").forEach((button) => button.addEventListener("click", () => deleteMobileDevice(button.dataset.mobileDelete)));
}

function renderMobilePairingCountdown(statusText = "") {
  const box = $("#mobile-pairing-result");
  if (!box || !mobileGatewayActivePairingId) return;
  const code = box.dataset.pairingCode || "";
  const noExpiry = box.dataset.noExpiry === "true";
  let status = statusText;
  if (!status) {
    if (noExpiry) status = "Không hết hạn, đang chờ điện thoại ghép nối...";
    else {
      const expiresAt = Date.parse(mobileGatewayActivePairingExpiresAt || "");
      const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
      status = remaining > 0 ? `Còn ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}` : "Hết hạn";
      if (remaining <= 0) stopMobilePairingTimers();
    }
  }
  box.className = "mobile-pairing-result";
  box.innerHTML = `<strong>${escapeHtml(code)}</strong><span>${escapeHtml(status)}</span>`;
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
    box.dataset.noExpiry = result.no_expiry || result.ttl_seconds === 0 ? "true" : "false";
    box.className = "mobile-pairing-result";
    box.innerHTML = `<strong>${escapeHtml(result.pairing_code || "")}</strong><span>${result.no_expiry || result.ttl_seconds === 0 ? "Không hết hạn, đang chờ điện thoại ghép nối..." : `Hết hạn: ${escapeHtml(mobileFormatTime(result.expires_at))}`}</span>`;
  }
  startMobilePairingTimers();
  await loadMobilePairingCodes();
}

async function loadMobilePairingCodes() {
  const data = await api("/api/admin/mobile-gateway/pairing-codes");
  const codes = data.codes || [];
  const active = codes.find((code) => String(code.id) === String(mobileGatewayActivePairingId));
  if (active && (active.used_at || active.status === "used")) {
    await loadMobileGatewayDevices();
    renderMobilePairingCountdown(`Đã kết nối: ${mobileDeviceLabel(active.used_by_device_id)} lúc ${mobileFormatTime(active.used_at)}`);
    stopMobilePairingTimers();
    mobileGatewayActivePairingId = null;
  }
}

async function loadMobileGatewaySms({ force = false, markNew = false, silent = false } = {}) {
  const deviceId = $("#mobile-sms-device-filter")?.value || "";
  const sender = $("#mobile-sms-sender-filter")?.value || "";
  const query = $("#mobile-sms-query-filter")?.value || "";
  const dateFrom = mobileGatewayDateStart($("#mobile-sms-date-from")?.value || "");
  const dateTo = mobileGatewayDateEnd($("#mobile-sms-date-to")?.value || "");
  const simSlot = $("#mobile-sms-sim-filter")?.value || "";
  if (force && !silent) setTableLoading("#mobile-sms-table", 5, "Đang tải SMS...");
  const data = await api(`/api/admin/mobile-gateway/sms?page=${mobileGatewaySmsPage}&page_size=50&device_id=${encodeURIComponent(deviceId)}&sender=${encodeURIComponent(sender)}&query=${encodeURIComponent(query)}&date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}&sim_slot=${encodeURIComponent(simSlot)}`);
  mobileGatewaySmsHasMore = Boolean(data.has_more);
  renderMobileSmsTable(data.items || [], markNew);
  const pageInfo = $("#mobile-sms-page-info");
  if (pageInfo) pageInfo.textContent = `Trang ${mobileGatewaySmsPage}`;
}

function renderMobileSmsTable(items, markNew = false) {
  const table = $("#mobile-sms-table");
  if (!table) return;
  if (!window.mobileGatewayKnownSmsIds) window.mobileGatewayKnownSmsIds = new Set();
  const known = window.mobileGatewayKnownSmsIds;
  const ready = Boolean(window.mobileGatewayKnownSmsReady);
  table.replaceChildren();
  if (!items.length) {
    table.innerHTML = emptyRow(5, "Chưa có SMS");
    window.mobileGatewayKnownSmsReady = true;
    return;
  }
  items.forEach((sms) => {
    const row = document.createElement("tr");
    const smsId = String(sms.id || `${sms.device_id || ""}:${sms.external_id || ""}:${sms.received_at || ""}`);
    if (markNew && ready && !known.has(smsId)) row.classList.add("mobile-sms-new");
    [sms.sender || "", mobileFormatTime(sms.received_at), sms.body || sms.body_masked || "", mobileDeviceLabel(sms.device_id), sms.sim_slot ?? "-"].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    table.appendChild(row);
    known.add(smsId);
  });
  window.mobileGatewayKnownSmsReady = true;
}

function startMobileSmsAutoRefresh() {
  if (window.mobileGatewaySmsAutoRefresh) {
    clearInterval(window.mobileGatewaySmsAutoRefresh);
    window.mobileGatewaySmsAutoRefresh = null;
  }
}

function renderMobileOtpFilterForm() {
  const form = $("#mobile-otp-filter-form");
  if (!form || form.dataset.loaded === "true") return;
  const otpFilter = mobileGatewayOtpFilters.find((item) => item.filter_id === "onebss") || mobileGatewayOtpFilters[0];
  if (!otpFilter) return;
  form.dataset.loaded = "true";
  form.elements.namedItem("id").value = otpFilter.id || "";
  form.elements.namedItem("filter_id").value = otpFilter.filter_id || otpFilter.service_code || "onebss";
  form.elements.namedItem("sender_pattern").value = otpFilter.sender_pattern || "";
  form.elements.namedItem("otp_length").value = otpFilter.otp_length || 6;
  form.elements.namedItem("start_prefix").value = otpFilter.start_prefix || "";
  form.elements.namedItem("enabled").checked = Boolean(otpFilter.enabled);
}

function renderMobileOtpFilters() {
  const table = $("#mobile-otp-filters-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpFilters.length ? mobileGatewayOtpFilters.map((item) => `<tr>
    <td><strong>${escapeHtml(item.filter_id || item.service_code || item.id || "")}</strong></td>
    <td>${escapeHtml(item.sender_pattern || "")}</td>
    <td>${escapeHtml(String(item.otp_length || 6))}</td>
    <td>${escapeHtml(item.start_prefix || "-")}</td>
    <td><span class="status ${item.enabled ? "viewer" : "inactive"}">${item.enabled ? "Có" : "Không"}</span></td>
  </tr>`).join("") : emptyRow(5, "Chưa có quy tắc OTP");
}

async function saveMobileOtpFilter() {
  const form = $("#mobile-otp-filter-form");
  if (!form) return;
  const data = Object.fromEntries(new FormData(form));
  const otpCode = String(data.filter_id || "").trim().toLowerCase();
  const sender = String(data.sender_pattern || "").trim();
  if (!otpCode || !sender) return showToast("Nhập Mã OTP và người gửi.", "error");
  const payload = {
    id: data.id ? Number(data.id) : null,
    filter_id: otpCode,
    rule_name: otpCode,
    service_code: otpCode,
    sender_pattern: sender,
    sender_match_type: "contains",
    otp_length: Number(data.otp_length || 6),
    start_prefix: String(data.start_prefix || "").trim(),
    validity_seconds: 60,
    enabled: Boolean(form.elements.namedItem("enabled")?.checked),
    device_id: "",
    sim_slot: null,
    priority: 10,
  };
  const response = await api("/api/admin/mobile-gateway/otp/filters", { method: "POST", body: JSON.stringify(payload) });
  form.dataset.loaded = "";
  showToast(response.latest ? `Đã lưu và tìm thấy OTP ${response.latest.code}` : "Đã lưu quy tắc OTP.");
  await loadMobileOtpData();
}

function renderMobileOtpLatest() {
  const table = $("#mobile-otp-latest-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpLatest.length ? mobileGatewayOtpLatest.map((item) => {
    const statusInfo = mobileOtpLatestStatus(item);
    return `<tr>
      <td><strong>${escapeHtml(item.filter_id || item.service_code || "")}</strong></td>
      <td>${escapeHtml(item.sender || "")}</td>
      <td><strong>${escapeHtml(item.code || item.code_masked || "")}</strong></td>
      <td>${escapeHtml(mobileFormatTime(item.received_at))}</td>
      <td><span class="status ${statusInfo.className}">${escapeHtml(statusInfo.text)}${statusInfo.ttl !== "-" ? ` · ${escapeHtml(statusInfo.ttl)}` : ""}</span></td>
    </tr>`;
  }).join("") : emptyRow(5, "Chưa có OTP mới");
}

normalizeMobileGatewayUi();
