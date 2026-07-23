// Internal email admin UI. Kept separate from Mobile Gateway on purpose.
const INTERNAL_EMAIL_TABLE_LIMIT = 20;
const INTERNAL_EMAIL_TABS = ["messages", "email"];
let internalEmailPublicRules = [];

function getInternalEmailRoot() {
  return $("#view-internal-email");
}

function getInternalEmailActiveTab() {
  const root = getInternalEmailRoot();
  return root?.querySelector("[data-internal-email-tab].active")?.dataset.internalEmailTab || "messages";
}

function activateInternalEmailTab(tabName = "messages") {
  const root = getInternalEmailRoot();
  if (!root) return;
  const safeTab = INTERNAL_EMAIL_TABS.includes(tabName) ? tabName : "messages";
  root.querySelectorAll("[data-internal-email-tab]").forEach((button) => {
    const active = button.dataset.internalEmailTab === safeTab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  root.querySelectorAll("[data-internal-email-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.internalEmailPanel === safeTab);
  });
}

function internalEmailFormatTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return "-";
  }
}

function bindInternalEmailEvents() {
  const root = getInternalEmailRoot();
  const bind = (selector, eventName, handler) => {
    const element = $(selector);
    if (!element) return;
    const key = `boundInternalEmail${eventName}`;
    if (element.dataset[key]) return;
    element.dataset[key] = "true";
    element.addEventListener(eventName, handler);
  };
  bind("#internal-email-refresh", "click", () => loadInternalEmail({ force: true }));
  bind("#internal-email-sync", "click", syncInternalEmail);
  bind("#internal-email-test", "click", testInternalEmail);
  bind("#internal-email-public-save", "click", saveInternalEmailPublicRule);
  bind("#internal-email-otp-only", "change", () => loadInternalEmailMessages({ force: true }));
  bind("#internal-email-public-rules-table", "click", async (event) => {
    const deleteButton = event.target.closest("[data-internal-email-public-delete]");
    const toggleButton = event.target.closest("[data-internal-email-public-toggle]");
    if (deleteButton) await deleteInternalEmailPublicRule(deleteButton.dataset.internalEmailPublicDelete);
    if (toggleButton) await toggleInternalEmailPublicRule(toggleButton.dataset.internalEmailPublicToggle);
  });
  bind("#internal-email-messages-table", "click", (event) => {
    const button = event.target.closest("[data-internal-email-copy-otp]");
    if (button) copyInternalEmailOtpFromButton(button);
  });
  bind("#internal-email-messages-table", "dblclick", (event) => {
    const code = event.target.closest("[data-internal-email-otp-code]");
    if (code) selectElementText(code);
  });
  root?.querySelectorAll("[data-internal-email-tab]").forEach((button) => {
    if (button.dataset.boundInternalEmailTab) return;
    button.dataset.boundInternalEmailTab = "true";
    button.addEventListener("click", async () => {
      const tabName = button.dataset.internalEmailTab || "messages";
      activateInternalEmailTab(tabName);
      try {
        if (tabName === "email") {
          await Promise.all([loadInternalEmailStatus({ force: true }), loadInternalEmailPublicRules()]);
        } else {
          await loadInternalEmailMessages({ force: true });
        }
      } catch (error) {
        showMessage($("#internal-email-message"), error.message || "Không tải được dữ liệu Mail nội bộ.", "error");
      }
    });
  });
}

async function copyInternalEmailOtpFromButton(button) {
  const code = button?.dataset.internalEmailCopyOtp || "";
  if (!code || code === "null") return;
  try {
    await copyTextToClipboard(code);
    showToast(`Đã sao chép OTP ${code}.`);
  } catch (error) {
    showToast(error.message || "Không sao chép được OTP.", "error");
  }
}

function renderInternalEmailOtpCopyCell(code) {
  const value = String(code || "").trim();
  const canCopy = value && value !== "null" && !value.includes("*");
  return `
    <div class="mobile-otp-copy-cell internal-email-otp-copy-cell">
      <code class="mobile-otp-code" data-internal-email-otp-code tabindex="0">${escapeHtml(value || "null")}</code>
      <button class="table-action mobile-otp-copy-button" data-internal-email-copy-otp="${escapeHtml(value)}" type="button" ${canCopy ? "" : "disabled"}>Copy</button>
    </div>`;
}

async function loadInternalEmail({ force = false } = {}) {
  bindInternalEmailEvents();
  activateInternalEmailTab(getInternalEmailActiveTab());
  await Promise.all([
    loadInternalEmailStatus({ force }),
    loadInternalEmailMessages({ force }),
    loadInternalEmailPublicRules(),
  ]);
}

async function loadInternalEmailStatus({ force = false } = {}) {
  const target = $("#internal-email-status-cards");
  if (force && target) {
    target.innerHTML = `<article class="metric-card"><span>IMAP</span><strong>Đang tải...</strong></article>`;
  }
  const data = await api("/api/admin/internal-email/status");
  window.internalEmailStatus = data;
  renderInternalEmailStatus(data);
}

function renderInternalEmailStatus(data = {}) {
  const target = $("#internal-email-status-cards");
  if (!target) return;
  const details = data.details || {};
  const statusText = data.ok ? (details.enabled ? "Đang bật" : "Chưa bật") : "Cần cấu hình";
  const statusClass = data.ok && details.enabled ? "viewer" : (data.ok ? "pending" : "inactive");
  const configuredText = `${details.username_configured ? "user OK" : "thiếu user"} / ${details.password_configured ? "pass OK" : "thiếu pass"}`;
  const host = `${details.host || "email.vnpt.vn"}:${details.port || 993}`;
  const latest = details.latest_message_at ? internalEmailFormatTime(details.latest_message_at) : "Chưa có";
  target.innerHTML = `
    <article class="metric-card"><span>Trạng thái</span><strong><span class="status ${statusClass}">${escapeHtml(statusText)}</span></strong></article>
    <article class="metric-card"><span>Máy chủ</span><strong>${escapeHtml(host)}</strong><small>${escapeHtml(details.mailbox || "INBOX")}</small></article>
    <article class="metric-card"><span>Tài khoản</span><strong>${escapeHtml(configuredText)}</strong><small>${escapeHtml(details.account_key || "internal_email")}</small></article>
    <article class="metric-card"><span>Email mới nhất</span><strong>${escapeHtml(latest)}</strong><small>${escapeHtml(data.message || "")}</small></article>`;
}

async function loadInternalEmailMessages({ force = false } = {}) {
  const table = $("#internal-email-messages-table");
  if (force && table) setTableLoading("#internal-email-messages-table", 5, "Đang tải email...");
  const otpOnly = $("#internal-email-otp-only")?.checked ?? true;
  const data = await api(`/api/admin/internal-email/messages?limit=${INTERNAL_EMAIL_TABLE_LIMIT}&otp_only=${otpOnly ? "true" : "false"}`);
  window.internalEmailMessages = data.messages || [];
  renderInternalEmailMessages(window.internalEmailMessages);
}

function renderInternalEmailMessages(messages = []) {
  const table = $("#internal-email-messages-table");
  if (!table) return;
  if (!messages.length) {
    table.innerHTML = emptyRow(5, "Chưa có email OTP", "Đồng bộ IMAP hoặc bộ lọc OTP chưa tìm thấy thư phù hợp.");
    return;
  }
  table.innerHTML = messages.map((message) => {
    const otp = message.otp_code || message.otp_code_masked || "";
    const status = message.is_otp_candidate ? renderInternalEmailOtpCopyCell(otp || "") : `<span class="status pending">-</span>`;
    const sender = message.sender || message.sender_email || "";
    const subject = message.subject || "";
    const preview = message.body_masked || "";
    return `<tr>
      <td>${escapeHtml(internalEmailFormatTime(message.received_at))}</td>
      <td>${escapeHtml(sender)}</td>
      <td>${escapeHtml(subject)}</td>
      <td>${status}</td>
      <td>${escapeHtml(preview)}</td>
    </tr>`;
  }).join("");
}

function renderInternalEmailPublicRules(rules = []) {
  const table = $("#internal-email-public-rules-table");
  if (!table) return;
  if (!rules.length) {
    table.innerHTML = emptyRow(4, "Ch\u01b0a c\u00f3 ng\u01b0\u1eddi g\u1eedi public");
    return;
  }
  table.innerHTML = rules.map((rule) => `<tr>
    <td><strong>${escapeHtml(rule.sender_pattern || "")}</strong></td>
    <td>${escapeHtml(rule.label || "")}</td>
    <td><span class="status ${rule.is_active ? "viewer" : "inactive"}">${rule.is_active ? "\u0110ang public" : "\u0110ang t\u1eaft"}</span></td>
    <td class="table-action-cell"><div class="action-group">
      <button class="table-action" data-internal-email-public-toggle="${escapeHtml(rule.id)}" type="button">${rule.is_active ? "T\u1eaft" : "B\u1eadt"}</button>
      <button class="table-action danger" data-internal-email-public-delete="${escapeHtml(rule.id)}" type="button">X\u00f3a</button>
    </div></td>
  </tr>`).join("");
}

async function loadInternalEmailPublicRules() {
  const table = $("#internal-email-public-rules-table");
  if (!table) return;
  try {
    internalEmailPublicRules = await getPublicMessageRules("email");
    renderInternalEmailPublicRules(internalEmailPublicRules);
  } catch (error) {
    table.innerHTML = emptyRow(4, "Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public", error.message);
  }
}

async function saveInternalEmailPublicRule() {
  const form = $("#internal-email-public-form");
  if (!form) return;
  const sender = String(form.elements.namedItem("sender_pattern")?.value || "").trim();
  const label = String(form.elements.namedItem("label")?.value || "").trim();
  const isActive = Boolean(form.elements.namedItem("is_active")?.checked);
  if (!sender) return showToast("Nh\u1eadp ng\u01b0\u1eddi g\u1eedi mail c\u1ea7n public.", "error");
  try {
    await savePublicMessageRule({ source_type: "email", sender_pattern: sender, label, is_active: isActive });
    form.reset();
    form.elements.namedItem("is_active").checked = true;
    showToast("\u0110\u00e3 l\u01b0u c\u1ea5u h\u00ecnh public mail.");
    await loadInternalEmailPublicRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng l\u01b0u \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public mail.", "error");
  }
}

async function toggleInternalEmailPublicRule(ruleId) {
  const rule = internalEmailPublicRules.find((item) => String(item.id) === String(ruleId));
  if (!rule) return;
  try {
    await savePublicMessageRule({
      source_type: "email",
      sender_pattern: rule.sender_pattern || "",
      label: rule.label || "",
      is_active: !rule.is_active,
    });
    await loadInternalEmailPublicRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng c\u1eadp nh\u1eadt \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public mail.", "error");
  }
}

async function deleteInternalEmailPublicRule(ruleId) {
  if (!ruleId) return;
  try {
    await deletePublicMessageRule(ruleId);
    showToast("\u0110\u00e3 x\u00f3a c\u1ea5u h\u00ecnh public mail.");
    await loadInternalEmailPublicRules();
  } catch (error) {
    showToast(error.message || "Kh\u00f4ng x\u00f3a \u0111\u01b0\u1ee3c c\u1ea5u h\u00ecnh public mail.", "error");
  }
}

async function syncInternalEmail() {
  const button = $("#internal-email-sync");
  const message = $("#internal-email-message");
  if (button) setButtonLoading(button, true);
  try {
    const result = await api("/api/admin/internal-email/sync", { method: "POST" });
    const details = result.details || {};
    showMessage(message, `Đã đồng bộ email sang Tin nhắn: lưu ${details.saved || 0}, OTP ${details.otp_records || 0}.`);
    await Promise.all([
      loadInternalEmailStatus({ force: true }),
      loadInternalEmailMessages({ force: true }),
    ]);
    activateInternalEmailTab("messages");
  } catch (error) {
    showMessage(message, error.message || "Không đồng bộ được email nội bộ.", "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}

async function testInternalEmail() {
  const button = $("#internal-email-test");
  const message = $("#internal-email-message");
  if (button) setButtonLoading(button, true);
  try {
    const result = await api("/api/admin/internal-email/test", { method: "POST" });
    showMessage(message, result.message || (result.ok ? "Kết nối IMAP sẵn sàng." : "Kết nối IMAP chưa sẵn sàng."), result.ok ? "success" : "error");
    renderInternalEmailStatus(result);
  } catch (error) {
    showMessage(message, error.message || "Không kiểm tra được IMAP.", "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}
