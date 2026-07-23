// Focused Mobile Gateway UI for SMS + OTP. Loaded after app.js on purpose.
const MOBILE_GATEWAY_TABLE_PAGE_SIZE = window.TABLE_PAGE_SIZE || 20;
let mobilePublicSmsRules = [];

function mobileFormatTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return "-";
  }
}

function mobileDeviceLabel(deviceId) {
  const device = mobileGatewayDevices.find((item) => item.device_id === deviceId);
  return device ? `${device.name || device.device_id}` : (deviceId || "-");
}

function mobileGatewayDateStart(value) {
  return value ? `${value}T00:00:00+00:00` : "";
}

function mobileGatewayDateEnd(value) {
  return value ? `${value}T23:59:59+00:00` : "";
}

function normalizeMobileGatewayUi() {
  const root = $("#view-mobile-gateway");
  if (!root) return;
  const activeTab = root.querySelector("[data-mobile-tab].active")?.dataset.mobileTab || "overview";
  const safeTab = ["overview", "devices-config", "sms", "send", "otp"].includes(activeTab) ? activeTab : "overview";
  const actionGroup = root.querySelector(".page-header .action-group");
  if (actionGroup) actionGroup.innerHTML = "";
  const tabs = root.querySelector(".mobile-gateway-tabs");
  if (tabs) {
    tabs.innerHTML = `
      <button class="mobile-gateway-tab ${safeTab === "overview" ? "active" : ""}" data-mobile-tab="overview" type="button">Tổng quan</button>
      <button class="mobile-gateway-tab ${safeTab === "devices-config" ? "active" : ""}" data-mobile-tab="devices-config" type="button">Thiết bị</button>
      <button class="mobile-gateway-tab ${safeTab === "sms" ? "active" : ""}" data-mobile-tab="sms" type="button">SMS</button>
      <button class="mobile-gateway-tab ${safeTab === "send" ? "active" : ""}" data-mobile-tab="send" type="button">Gửi</button>
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
        <div class="public-sender-panel mt-4">
          <div class="section-heading compact"><div><p class="eyebrow">Public</p><h2>Public SMS theo ng&#432;&#7901;i g&#7917;i</h2></div><button class="btn-primary" id="mobile-public-sms-save" type="button">L&#432;u</button></div>
          <form id="mobile-public-sms-form" class="admin-inline-toolbar">
            <label>Ng&#432;&#7901;i g&#7917;i<input class="form-control" name="sender_pattern" placeholder="VD: VNPT" required /></label>
            <label>T&#234;n hi&#7875;n th&#7883;<input class="form-control" name="label" placeholder="VD: OTP OneBSS" /></label>
            <label class="checkbox-label"><input type="checkbox" name="is_active" checked /> &#272;ang public</label>
          </form>
          <div class="table-scroll mt-4"><table class="compact-admin-table inline-admin-table"><thead><tr><th>Ng&#432;&#7901;i g&#7917;i</th><th>T&#234;n hi&#7875;n th&#7883;</th><th>Tr&#7841;ng th&#225;i</th><th>Thao t&#225;c</th></tr></thead><tbody id="mobile-public-sms-rules-table"></tbody></table></div>
        </div>
        <div class="table-scroll"><table><thead><tr><th>Người gửi</th><th>Thời gian nhận</th><th>Nội dung tin nhắn</th><th>Thiết bị</th><th>SIM</th></tr></thead><tbody id="mobile-sms-table"></tbody></table></div>
        <div class="mt-4 flex items-center justify-between gap-3"><span id="mobile-sms-page-info">Trang 1</span><div class="action-group"><button class="btn-secondary" id="mobile-sms-prev" type="button">Trang trước</button><button class="btn-secondary" id="mobile-sms-next" type="button">Trang sau</button></div></div>
      </section>`;
  }
  let sendPanel = root.querySelector('[data-mobile-panel="send"]');
  if (!sendPanel) {
    sendPanel = document.createElement("section");
    sendPanel.className = "mobile-gateway-panel";
    sendPanel.dataset.mobilePanel = "send";
    root.querySelector('[data-mobile-panel="sms"]')?.after(sendPanel);
  }
  if (sendPanel) {
    sendPanel.classList.toggle("active", safeTab === "send");
    sendPanel.innerHTML = `
      <section class="data-card mobile-send-card">
        <div class="section-heading compact"><div><p class="eyebrow">SMS outgoing</p><h2>G&#7917;i tin nh&#7855;n t&#7915; &#273;i&#7879;n tho&#7841;i</h2></div></div>
        <form id="mobile-send-sms-form" class="mobile-send-form">
          <label>Thi&#7871;t b&#7883;<select class="form-control" id="mobile-send-device" required></select></label>
          <label>Ng&#432;&#7901;i nh&#7853;n<input class="form-control" id="mobile-send-recipient" inputmode="tel" autocomplete="off" placeholder="Nh&#7853;p s&#7889; li&#234;n h&#7879;" required /></label>
          <label class="mobile-send-body-label">N&#7897;i dung tin nh&#7855;n<textarea class="form-control" id="mobile-send-body" rows="5" required></textarea></label>
          <div class="mobile-send-actions"><button class="btn-primary" id="mobile-send-submit" type="submit">G&#7917;i SMS</button><div id="mobile-send-result" class="result hidden"></div></div>
        </form>
      </section>
      <section class="data-card mt-4">
        <div class="section-heading compact"><div><p class="eyebrow">Theo d&#245;i</p><h2>L&#7879;nh g&#7917;i SMS</h2></div><button class="btn-secondary" id="mobile-refresh-send" type="button">L&#224;m m&#7899;i</button></div>
        <div class="table-scroll"><table><thead><tr><th>Th&#7901;i gian</th><th>Thi&#7871;t b&#7883;</th><th>Ng&#432;&#7901;i nh&#7853;n</th><th>Tr&#7841;ng th&#225;i</th><th>G&#7917;i xong</th><th>L&#7895;i</th></tr></thead><tbody id="mobile-send-history-table"></tbody></table></div>
      </section>`;
  }
  const otpPanel = root.querySelector('[data-mobile-panel="otp"]');
  if (otpPanel) {
    otpPanel.classList.toggle("active", safeTab === "otp");
    otpPanel.innerHTML = `
      <section class="mobile-otp-layout">
        <div class="data-card mobile-otp-card mobile-otp-rule-card">
          <div class="section-heading compact"><div><p class="eyebrow">Quy tắc</p><h2>Lọc OTP theo SMS</h2></div><button class="btn-primary" id="mobile-save-otp-filter" type="button">Lưu</button></div>
          <form id="mobile-otp-filter-form" class="mobile-otp-form-inline">
            <input type="hidden" name="id" />
            <label>Mã OTP<input class="form-control" name="filter_id" value="onebss" required /></label>
            <label>Người gửi<input class="form-control" name="sender_pattern" value="293" required /></label>
            <label>Số ký tự<input class="form-control" name="otp_length" type="number" value="6" min="1" max="12" /></label>
            <label>Cắt từ<input class="form-control" name="start_prefix" type="number" min="0" value="0" /></label>
            <label class="checkbox-label mobile-otp-auto"><input type="checkbox" name="enabled" checked /> Tự động</label>
          </form>
          <div class="table-scroll mt-4"><table><thead><tr><th>Mã OTP</th><th>Người gửi</th><th>Số ký tự</th><th>Cắt từ vị trí</th><th>Tự động</th></tr></thead><tbody id="mobile-otp-filters-table"></tbody></table></div>
        </div>
        <div class="data-card mobile-otp-card">
          <div class="section-heading compact"><div><p class="eyebrow">OTP</p><h2>OTP mới nhất</h2></div></div>
          <div class="table-scroll"><table><thead><tr><th>Mã OTP</th><th>Người gửi</th><th>OTP</th><th>Thời gian nhận SMS</th><th>Trạng thái 60s</th></tr></thead><tbody id="mobile-otp-latest-table"></tbody></table></div>
        </div>
      </section>`;
  }
  normalizeMobileOtpFormDefaults(root);
  ["commands", "logs", "settings", "notifications", "media"].forEach((name) => root.querySelector(`[data-mobile-panel="${name}"]`)?.remove());
  bindMobileGatewayFocusedEvents();
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

function normalizeMobileGatewayTabName(tabName) {
  return tabName === "devices" ? "devices-config" : (tabName || "overview");
}

function activateMobileGatewayTab(tabName) {
  const root = $("#view-mobile-gateway");
  if (!root) return;
  const allowedTabs = ["overview", "devices-config", "sms", "send", "otp"];
  const activeTab = normalizeMobileGatewayTabName(tabName);
  const safeTab = allowedTabs.includes(activeTab) ? activeTab : "overview";
  root.querySelectorAll("[data-mobile-tab]").forEach((button) => {
    const buttonTab = normalizeMobileGatewayTabName(button.dataset.mobileTab);
    const isActive = buttonTab === safeTab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  root.querySelectorAll("[data-mobile-panel]").forEach((panel) => {
    const panelTab = normalizeMobileGatewayTabName(panel.dataset.mobilePanel);
    panel.classList.toggle("active", panelTab === safeTab);
  });
  if (safeTab === "devices-config") {
    loadMobileGatewayDevices().catch((error) => showToast(error.message, "error"));
    loadMobilePairingCodes().catch((error) => showToast(error.message, "error"));
  } else if (safeTab === "sms") {
    loadMobileGatewaySms().catch((error) => showToast(error.message, "error"));
    loadMobilePublicSmsRules().catch((error) => showToast(error.message, "error"));
  } else if (safeTab === "send") {
    loadMobileSendCommands().catch((error) => showToast(error.message, "error"));
  } else if (safeTab === "otp") {
    loadMobileOtpData().catch((error) => showToast(error.message, "error"));
  }
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
  bind("#mobile-public-sms-save", "click", saveMobilePublicSmsRule);
  bind("#mobile-public-sms-rules-table", "click", async (event) => {
    const deleteButton = event.target.closest("[data-mobile-public-sms-delete]");
    const toggleButton = event.target.closest("[data-mobile-public-sms-toggle]");
    if (deleteButton) await deleteMobilePublicSmsRule(deleteButton.dataset.mobilePublicSmsDelete);
    if (toggleButton) await toggleMobilePublicSmsRule(toggleButton.dataset.mobilePublicSmsToggle);
  });
  bind("#mobile-save-otp-filter", "click", saveMobileOtpFilter);
  bind("#mobile-send-sms-form", "submit", (event) => {
    event.preventDefault();
    sendMobileSms();
  });
  bind("#mobile-refresh-send", "click", () => loadMobileSendCommands({ force: true }));
  bind("#mobile-otp-latest-table", "click", (event) => {
    const button = event.target.closest("[data-mobile-copy-otp]");
    if (button) copyMobileOtpFromButton(button);
  });
  bind("#mobile-otp-latest-table", "dblclick", (event) => {
    const code = event.target.closest("[data-mobile-otp-code]");
    if (code) selectElementText(code);
  });
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
      loadMobilePublicSmsRules(),
      loadMobileOtpData(),
      loadMobileSendCommands(),
    ]);
    mobileGatewayLoaded = true;
    renderMobileGatewayOverview();
    startMobileOtpTicker();
    startMobileGatewayEvents();
    startMobileSmsAutoRefresh();
    startMobileSendStatusRefresh();
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

async function loadMobileGatewayDevices() {
  const data = await api("/api/admin/mobile-gateway/devices");
  mobileGatewayDevices = data.devices || [];
  renderMobileGatewayDevices();
  renderMobileGatewayDeviceOptions();
}

function renderMobileGatewayOverview() {
  const overviewTarget = $("#mobile-overview-cards");
  if (overviewTarget) {
    overviewTarget.classList.add("mobile-overview-device-grid");
    overviewTarget.innerHTML = mobileGatewayDevices.length ? mobileGatewayDevices.map((device) => {
      const heartbeat = device.heartbeat || {};
      const active = Boolean(device.is_active);
      const online = Boolean(device.online);
      const statusClass = !active ? "inactive" : (online ? "viewer" : "pending");
      const statusText = !active ? "Đã hủy ghép nối" : (online ? "Đã ghép nối - online" : "Đã ghép nối - offline");
      const signal = mobileHeartbeatSignals(heartbeat);
      const error = mobileLatestDeviceError(device.device_id);
      return `<article class="mobile-overview-device-card">
        <div class="mobile-overview-device-head">
          <strong>${escapeHtml(device.name || device.device_id || "-")}</strong>
          <span class="status ${statusClass}">${escapeHtml(statusText)}</span>
        </div>
        <dl class="mobile-overview-device-metrics">
          <div><dt>Lỗi</dt><dd class="${error ? "mobile-error-text" : ""}">${escapeHtml(error || "Không có")}</dd></div>
          <div><dt>PIN</dt><dd>${heartbeat.battery_percent == null ? "-" : `${escapeHtml(String(heartbeat.battery_percent))}%`}</dd></div>
          <div><dt>Sóng mạng</dt><dd>${escapeHtml(signal.network)}</dd></div>
          <div><dt>Sóng SIM</dt><dd>${escapeHtml(signal.sim)}</dd></div>
          <div><dt>Heartbeat</dt><dd>${escapeHtml(mobileFormatTime(device.last_seen_at || heartbeat.created_at))}</dd></div>
        </dl>
      </article>`;
    }).join("") : `<article class="mobile-overview-device-card"><strong>Chưa có thiết bị</strong><p>Hãy tạo mã ghép nối và kết nối điện thoại chứa SIM.</p></article>`;
  }
  renderMobileRecentSms(mobileGatewayOverview.recent_sms || []);
}

function mobileHeartbeatSignals(heartbeat = {}) {
  const raw = String(heartbeat.network_type || "").trim();
  if (!raw) return { network: "-", sim: "-" };
  const parts = raw.split("|").map((part) => part.trim()).filter(Boolean);
  const sim = parts.find((part) => /^sim\b/i.test(part)) || "";
  const network = parts.find((part) => !/^sim\b/i.test(part)) || raw;
  return { network: network || "-", sim: sim || "-" };
}

function mobileLatestDeviceError(deviceId) {
  const commands = window.mobileGatewaySendCommands || [];
  const command = commands.find((item) => item.device_id === deviceId && item.status === "failed" && item.sanitized_error);
  return command?.sanitized_error || "";
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
  const sendSelect = $("#mobile-send-device");
  if (sendSelect) sendSelect.innerHTML = options || `<option value="">Chưa có thiết bị</option>`;
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
  renderMobileGatewayDeviceOptions();
  renderMobileGatewayOverview();
}

async function toggleMobileDeviceActive(deviceId) {
  const device = mobileGatewayDevices.find((item) => item.device_id === deviceId);
  if (!device) return;
  const action = device.is_active ? "revoke" : "reactivate";
  await api(`/api/admin/mobile-gateway/devices/${encodeURIComponent(deviceId)}/${action}`, { method: "POST" });
  await loadMobileGatewayDevices();
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

function renderMobilePublicSmsRules(rules = []) {
  const table = $("#mobile-public-sms-rules-table");
  if (!table) return;
  if (!rules.length) {
    table.innerHTML = emptyRow(4, "Ch\u01b0a c\u00f3 ng\u01b0\u1eddi g\u1eedi SMS public");
    return;
  }
  table.innerHTML = rules.map((rule) => `<tr>
    <td><strong>${escapeHtml(rule.sender_pattern || "")}</strong></td>
    <td>${escapeHtml(rule.label || "")}</td>
    <td><span class="status ${rule.is_active ? "viewer" : "inactive"}">${rule.is_active ? "\u0110ang public" : "\u0110ang t\u1eaft"}</span></td>
    <td class="table-action-cell"><div class="action-group">
      <button class="table-action" data-mobile-public-sms-toggle="${escapeHtml(rule.id)}" type="button">${rule.is_active ? "T\u1eaft" : "B\u1eadt"}</button>
      <button class="table-action danger" data-mobile-public-sms-delete="${escapeHtml(rule.id)}" type="button">X\u00f3a</button>
    </div></td>
  </tr>`).join("");
}

async function loadMobilePublicSmsRules() {
  const table = $("#mobile-public-sms-rules-table");
  if (!table) return;
  try {
    mobilePublicSmsRules = await getPublicMessageRules("sms");
    renderMobilePublicSmsRules(mobilePublicSmsRules);
  } catch (error) {
    table.innerHTML = emptyRow(4, "Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public SMS", error.message);
  }
}

async function saveMobilePublicSmsRule() {
  const form = $("#mobile-public-sms-form");
  if (!form) return;
  const sender = String(form.elements.namedItem("sender_pattern")?.value || "").trim();
  const label = String(form.elements.namedItem("label")?.value || "").trim();
  const isActive = Boolean(form.elements.namedItem("is_active")?.checked);
  if (!sender) return showToast("Nh\u1eadp ng\u01b0\u1eddi g\u1eedi SMS c\u1ea7n public.", "error");
  try {
    await savePublicMessageRule({ source_type: "sms", sender_pattern: sender, label, is_active: isActive });
    form.reset();
    form.elements.namedItem("is_active").checked = true;
    showToast("\u0110\u00e3 l\u01b0u c\u1ea5u h\u00ecnh public SMS.");
    await loadMobilePublicSmsRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng l\u01b0u \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public SMS.", "error");
  }
}

async function toggleMobilePublicSmsRule(ruleId) {
  const rule = mobilePublicSmsRules.find((item) => String(item.id) === String(ruleId));
  if (!rule) return;
  try {
    await savePublicMessageRule({
      source_type: "sms",
      sender_pattern: rule.sender_pattern || "",
      label: rule.label || "",
      is_active: !rule.is_active,
    });
    await loadMobilePublicSmsRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng c\u1eadp nh\u1eadt \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public SMS.", "error");
  }
}

async function deleteMobilePublicSmsRule(ruleId) {
  if (!ruleId) return;
  try {
    await deletePublicMessageRule(ruleId);
    showToast("\u0110\u00e3 x\u00f3a c\u1ea5u h\u00ecnh public SMS.");
    await loadMobilePublicSmsRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng x\u00f3a \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public SMS.", "error");
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
  const data = await api(`/api/admin/mobile-gateway/sms?page=${mobileGatewaySmsPage}&page_size=${MOBILE_GATEWAY_TABLE_PAGE_SIZE}&device_id=${encodeURIComponent(deviceId)}&sender=${encodeURIComponent(sender)}&query=${encodeURIComponent(query)}&date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}&sim_slot=${encodeURIComponent(simSlot)}`);
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
  if (window.mobileGatewaySmsAutoRefresh) return;
  window.mobileGatewayLastSmsEventAt = window.mobileGatewayLastSmsEventAt || 0;
  window.mobileGatewaySmsAutoRefresh = setInterval(async () => {
    const root = $("#view-mobile-gateway");
    if (!root?.classList.contains("active")) return;
    const eventStreamStale = !window.mobileGatewayEventSource
      || !window.mobileGatewayLastSmsEventAt
      || Date.now() - window.mobileGatewayLastSmsEventAt > 12000;
    if (!eventStreamStale || window.mobileGatewaySmsFallbackLoading) return;
    window.mobileGatewaySmsFallbackLoading = true;
    try {
      mobileGatewaySmsPage = 1;
      await loadMobileGatewaySms({ silent: true, markNew: true });
      await loadMobileOtpData();
    } catch (error) {
      console.warn("Mobile Gateway fallback refresh failed", error);
    } finally {
      window.mobileGatewaySmsFallbackLoading = false;
    }
  }, 3000);
}

function startMobileGatewayEvents() {
  if (window.mobileGatewayEventSource || typeof EventSource === "undefined") return;
  const source = new EventSource("/api/admin/mobile-gateway/events");
  window.mobileGatewayEventSource = source;
  const reloadFromEvent = () => {
    window.mobileGatewayLastSmsEventAt = Date.now();
    clearTimeout(window.mobileGatewayEventReloadTimer);
    window.mobileGatewayEventReloadTimer = setTimeout(() => {
      if (!$("#view-mobile-gateway")?.classList.contains("active")) return;
      mobileGatewaySmsPage = 1;
      loadMobileGatewaySms({ silent: true, markNew: true });
      loadMobileGatewayOverview();
      loadMobileOtpData();
    }, 250);
  };
  source.onopen = () => {
    window.mobileGatewayLastSmsEventAt = Date.now();
  };
  source.addEventListener("ready", () => {
    window.mobileGatewayLastSmsEventAt = Date.now();
  });
  source.addEventListener("sms_batch", reloadFromEvent);
  source.onerror = () => {
    source.close();
    window.mobileGatewayEventSource = null;
    clearTimeout(window.mobileGatewayEventReconnectTimer);
    window.mobileGatewayEventReconnectTimer = setTimeout(() => {
      if ($("#view-mobile-gateway")?.classList.contains("active")) startMobileGatewayEvents();
    }, 1500);
  };
}

async function loadMobileSendCommands({ force = false } = {}) {
  const table = $("#mobile-send-history-table");
  if (force && table) setTableLoading("#mobile-send-history-table", 6, "Đang tải lệnh gửi SMS...");
  const data = await api(`/api/admin/mobile-gateway/commands?limit=${MOBILE_GATEWAY_TABLE_PAGE_SIZE}`);
  window.mobileGatewaySendCommands = (data.commands || []).filter((command) => command.command_type === "send_sms");
  renderMobileSendHistory();
  renderMobileGatewayOverview();
}

function renderMobileSendHistory() {
  const table = $("#mobile-send-history-table");
  if (!table) return;
  const commands = window.mobileGatewaySendCommands || [];
  table.innerHTML = commands.length ? commands.map((command) => {
    const payload = mobileCommandPayload(command);
    const status = command.status || "";
    return `<tr>
      <td>${escapeHtml(mobileFormatTime(command.created_at))}</td>
      <td>${escapeHtml(mobileDeviceLabel(command.device_id))}</td>
      <td>${escapeHtml(mobileSendRecipientLabel(payload.recipient || payload.phone_number || ""))}</td>
      <td><span class="status ${mobileCommandStatusClass(status)}">${escapeHtml(status || "-")}</span></td>
      <td>${escapeHtml(mobileFormatTime(command.completed_at || command.acknowledged_at || command.delivered_at))}</td>
      <td>${escapeHtml(command.sanitized_error || "")}</td>
    </tr>`;
  }).join("") : emptyRow(6, "Chưa có lệnh gửi SMS");
}

function mobileCommandPayload(command) {
  const payload = command?.payload || {};
  if (typeof payload === "string") {
    try {
      return JSON.parse(payload);
    } catch (error) {
      return {};
    }
  }
  return payload && typeof payload === "object" ? payload : {};
}

function mobileCommandStatusClass(status) {
  if (status === "completed") return "viewer";
  if (status === "failed") return "inactive";
  return "pending";
}

function mobileSendRecipientLabel(value) {
  const text = String(value || "").trim();
  if (text.length <= 4) return text || "-";
  return `${"*".repeat(Math.max(0, text.length - 4))}${text.slice(-4)}`;
}

async function sendMobileSms() {
  const result = $("#mobile-send-result");
  const submit = $("#mobile-send-submit");
  const deviceId = $("#mobile-send-device")?.value || "";
  const recipient = ($("#mobile-send-recipient")?.value || "").trim();
  const body = ($("#mobile-send-body")?.value || "").trim();
  if (!deviceId) return showMessage(result, "Hãy chọn thiết bị.", "error");
  if (!recipient) return showMessage(result, "Hãy nhập số liên hệ.", "error");
  if (!body) return showMessage(result, "Hãy nhập nội dung tin nhắn.", "error");
  if (submit) submit.disabled = true;
  try {
    await api("/api/admin/mobile-gateway/commands", {
      method: "POST",
      body: JSON.stringify({
        device_id: deviceId,
        command_type: "send_sms",
        ttl_seconds: 300,
        payload: { recipient, body },
      }),
    });
    showMessage(result, "Đã tạo lệnh gửi SMS. Điện thoại sẽ gửi ngay khi nhận lệnh.", "success");
    const bodyInput = $("#mobile-send-body");
    if (bodyInput) bodyInput.value = "";
    await loadMobileSendCommands({ force: true });
  } catch (error) {
    showMessage(result, error.message || "Không gửi được lệnh SMS.", "error");
  } finally {
    if (submit) submit.disabled = false;
  }
}

function startMobileSendStatusRefresh() {
  if (window.mobileGatewaySendStatusRefresh) return;
  window.mobileGatewaySendStatusRefresh = setInterval(() => {
    const root = $("#view-mobile-gateway");
    if (!root?.classList.contains("active")) return;
    loadMobileSendCommands().catch((error) => console.warn("Mobile send status refresh failed", error));
  }, 5000);
}

async function loadMobileOtpData() {
  const [filters, latest] = await Promise.all([
    api("/api/admin/mobile-gateway/otp/filters"),
    api(`/api/admin/mobile-gateway/otp/latest?limit=${MOBILE_GATEWAY_TABLE_PAGE_SIZE}`),
  ]);
  mobileGatewayOtpFilters = filters.filters || [];
  mobileGatewayOtpLatest = latest.items || [];
  renderMobileOtpFilterForm();
  renderMobileOtpFilters();
  renderMobileOtpLatest();
}

function startMobileOtpTicker() {
  if (window.mobileGatewayOtpTicker) return;
  window.mobileGatewayOtpTicker = setInterval(renderMobileOtpLatest, 1000);
  window.mobileGatewayOtpRefresh = setInterval(() => {
    if ($("#view-mobile-gateway")?.classList.contains("active")) {
      loadMobileOtpData().catch((error) => console.warn("Mobile OTP refresh failed", error));
    }
  }, 15000);
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
  form.elements.namedItem("start_prefix").value = otpFilter.start_prefix || "0";
  form.elements.namedItem("enabled").checked = Boolean(otpFilter.enabled);
}

function renderMobileOtpFilters() {
  const table = $("#mobile-otp-filters-table");
  if (!table) return;
  table.innerHTML = mobileGatewayOtpFilters.length ? mobileGatewayOtpFilters.map((item) => `<tr>
    <td><strong>${escapeHtml(item.filter_id || item.service_code || item.id || "")}</strong></td>
    <td>${escapeHtml(item.sender_pattern || "")}</td>
    <td>${escapeHtml(String(item.otp_length || 6))}</td>
    <td>${escapeHtml(item.start_prefix || "0")}</td>
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
  showToast(response.latest ? `Đã lưu và tìm thấy OTP ${response.latest.code}` : "Đã lưu quy tắc OTP, kết quả hiện là null.");
  await loadMobileOtpData();
}

function mobileOtpLatestStatus(item) {
  if (!item || item.status === "missing" || !(item.code || item.code_masked)) {
    return { text: "Không tìm thấy SMS", className: "inactive", ttl: "null" };
  }
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
      <td><strong>${escapeHtml(item.filter_id || item.service_code || "")}</strong></td>
      <td>${escapeHtml(item.sender || "")}</td>
      <td>${renderMobileOtpCopyCell(code)}</td>
      <td>${escapeHtml(item.received_at ? mobileFormatTime(item.received_at) : "null")}</td>
      <td><span class="status ${statusInfo.className}">${escapeHtml(statusInfo.text)}${statusInfo.ttl !== "-" ? ` · ${escapeHtml(statusInfo.ttl)}` : ""}</span></td>
    </tr>`;
  }).join("") : emptyRow(5, "Chưa có OTP mới");
}

normalizeMobileGatewayUi();
