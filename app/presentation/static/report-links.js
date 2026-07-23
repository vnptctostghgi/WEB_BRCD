(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const copyTextToClipboard = app.copyTextToClipboard;
  const emptyRow = app.emptyRow;
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const loadingRow = app.loadingRow;
  const markDataFresh = app.markDataFresh || (() => {});
  const markDataStale = app.markDataStale || (() => {});
  const role = app.role || document.body.dataset.role || "";
  const setButtonLoading = app.setButtonLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});
  let reportLinks = [];
  let reportLinkDrafts = [];

  const reportLinkTypeLabels = {
    auto: "Tự nhận diện",
    google_sheet: "Google Sheet",
    google_doc: "Google Doc",
    google_slide: "Google Slides",
    google_form: "Google Form",
    pdf: "PDF",
    other: "Link khác",
  };

  function reportLinkTypeOptions(selected = "auto") {
    return Object.entries(reportLinkTypeLabels)
      .map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`)
      .join("");
  }

  function reportLinkMatchesSearch(report, query) {
    if (!query) return true;
    const text = [
      report.ma_bao_cao,
      report.ten_bao_cao,
      report.link,
      report.link_type_label,
      report.link_type,
    ].join(" ").toLowerCase();
    return text.includes(query);
  }

  async function loadReportLinks({ force = false } = {}) {
    if (!api || !emptyRow) throw new Error("Module Link báo cáo chưa sẵn sàng.");
    if (!force && isDataFresh("reportLinks")) {
      renderReportLinksTable();
      renderReportLinkAdminEditor();
      return;
    }
    if (!reportLinks.length || force) {
      const table = $("#report-links-table");
      if (table) table.innerHTML = loadingRow(5, "Đang tải danh sách link báo cáo...");
      renderReportLinkAdminLoading("Đang tải cấu hình link báo cáo...");
    }
    try {
      const data = await api("/api/report-links");
      reportLinks = data.links || [];
      markDataFresh("reportLinks");
      renderReportLinksTable();
      renderReportLinkAdminEditor();
    } catch (error) {
      const table = $("#report-links-table");
      if (table) table.innerHTML = emptyRow(5, "Không tải được danh sách link báo cáo", error.message);
      const editor = $("#report-link-admin-editor");
      if (editor) editor.innerHTML = `<div class="empty-state"><div><strong>Không tải được cấu hình link</strong><p>${escapeHtml(error.message)}</p></div></div>`;
    }
  }

  function renderReportLinksTable() {
    const table = $("#report-links-table");
    if (!table) return;
    const query = ($("#report-link-search")?.value || "").trim().toLowerCase();
    const rows = reportLinks.filter((report) => reportLinkMatchesSearch(report, query));
    table.innerHTML = rows.length
      ? rows.map((report) => renderReportLinkRow(report)).join("")
      : emptyRow(5, "Chưa có link báo cáo", query ? "Không có link nào khớp điều kiện tìm kiếm." : "Quản trị viên có thể thêm link trong Quản trị kết nối.");
    document.querySelectorAll("[data-copy-report-link]").forEach((button) => {
      button.addEventListener("click", () => copyReportLink(button.dataset.copyReportLink));
    });
  }

  function renderReportLinkRow(report) {
    const downloadAction = report.download_url
      ? `<a class="table-action" href="${escapeHtml(report.download_url)}"><svg class="button-svg"><use href="#icon-download"></use></svg><span>Tải</span></a>`
      : "";
    const statusBadge = report.is_active
      ? `<span class="status active">Bật</span>`
      : `<span class="status inactive">Tắt</span>`;
    return `
      <tr>
        <td class="table-action-cell"><div class="action-group report-link-actions">
          <a class="table-action" href="${escapeHtml(report.link || "#")}" target="_blank" rel="noopener">Mở</a>
          <button class="table-action" type="button" data-copy-report-link="${escapeHtml(report.link || "")}">Copy</button>
          ${downloadAction}
        </div></td>
        <td><code class="compact-code">${escapeHtml(report.ma_bao_cao || "")}</code></td>
        <td><strong>${escapeHtml(report.ten_bao_cao || "")}</strong><small class="cell-note">${escapeHtml(report.link_type_label || reportLinkTypeLabels[report.link_type] || report.link_type || "Link khác")} ${role === "admin" ? ` · ${statusBadge}` : ""}</small></td>
        <td><a class="report-link-url" href="${escapeHtml(report.link || "#")}" target="_blank" rel="noopener">${escapeHtml(report.link || "")}</a></td>
        <td>${statusBadge}</td>
      </tr>`;
  }

  async function copyReportLink(link) {
    try {
      await copyTextToClipboard(link);
      showToast("Đã sao chép link.");
    } catch (error) {
      showToast(error.message || "Không sao chép được link.", "error");
    }
  }

  function renderReportLinkAdminLoading(text) {
    const editor = $("#report-link-admin-editor");
    if (editor) editor.innerHTML = `<div class="loading-row">${escapeHtml(text)}</div>`;
  }

  function refreshReportLinkPicker() {
    const picker = $("#report-link-picker");
    if (!picker) return;
    const search = ($("#report-link-admin-search")?.value || "").trim().toLowerCase();
    const current = picker.value;
    const filtered = reportLinks.filter((report) => reportLinkMatchesSearch(report, search));
    picker.innerHTML = `<option value="">Thêm link mới / chưa chọn link</option>${filtered.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")}`;
    if (current && filtered.some((report) => report.ma_bao_cao === current)) picker.value = current;
  }

  function createReportLinkDraft() {
    const draft = {
      _draft: true,
      _rowKey: "draft-new-report-link",
      id: "",
      ma_bao_cao: "",
      ten_bao_cao: "",
      link: "",
      link_type: "auto",
      is_active: true,
    };
    reportLinkDrafts = [draft];
    return draft;
  }

  function renderReportLinkAdminEditor() {
    const editor = $("#report-link-admin-editor");
    if (!editor) return;
    refreshReportLinkPicker();
    const pickedCode = $("#report-link-picker")?.value || "";
    const selected = pickedCode ? reportLinks.find((report) => report.ma_bao_cao === pickedCode) : null;
    const draft = reportLinkDrafts[0] || createReportLinkDraft();
    editor.innerHTML = renderReportLinkEditor(selected || draft, !selected);
    document.querySelectorAll("[data-inline-report-link-field]").forEach((field) => {
      field.addEventListener("input", () => markReportLinkDirty(field.closest("[data-report-link-row]")));
      field.addEventListener("change", () => markReportLinkDirty(field.closest("[data-report-link-row]")));
    });
    document.querySelectorAll("[data-inline-report-link-active]").forEach((field) => {
      field.addEventListener("change", () => markReportLinkDirty(field.closest("[data-report-link-row]")));
    });
    document.querySelectorAll("[data-save-report-link-inline]").forEach((button) => {
      button.addEventListener("click", () => saveInlineReportLink(button.dataset.saveReportLinkInline, button));
    });
    document.querySelectorAll("[data-delete-report-link]").forEach((button) => {
      button.addEventListener("click", () => deleteInlineReportLink(button.dataset.deleteReportLink));
    });
  }

  function renderReportLinkEditor(report, isDraft = false) {
    const rowKey = report._rowKey || `report-link-${report.id}`;
    const linkType = report.link_type || "auto";
    return `
      <div class="sql-report-editor-card report-link-editor-card" data-report-link-row="${escapeHtml(rowKey)}" data-report-link-id="${escapeHtml(report.id || "")}">
        <div class="section-heading">
          <div><p class="eyebrow">${isDraft ? "Thêm link" : "Chỉnh link"}</p><h3>${isDraft ? "Tạo link báo cáo mới" : escapeHtml(report.ten_bao_cao || report.ma_bao_cao)}</h3></div>
          <div class="action-group"><button class="table-action ${isDraft ? "" : "hidden"}" data-save-report-link-inline="${escapeHtml(rowKey)}">Lưu</button>${isDraft ? "" : `<button class="table-action danger" data-delete-report-link="${escapeHtml(rowKey)}">Xóa</button>`}</div>
        </div>
        <label>Mã báo cáo<input class="form-control inline-admin-input" data-inline-report-link-field="ma_bao_cao" value="${escapeHtml(report.ma_bao_cao || "")}" placeholder="Tự sinh khi lưu" readonly /></label>
        <label>Tên báo cáo<input class="form-control inline-admin-input" data-inline-report-link-field="ten_bao_cao" value="${escapeHtml(report.ten_bao_cao || "")}" placeholder="Tên báo cáo" /></label>
        <label>Link<input class="form-control inline-admin-input" data-inline-report-link-field="link" value="${escapeHtml(report.link || "")}" placeholder="https://docs.google.com/..." /></label>
        <label>Loại link<select class="form-control inline-admin-input" data-inline-report-link-field="link_type">${reportLinkTypeOptions(linkType)}</select><small class="cell-note">Sheet tải xuống dạng Excel chỉ chứa value; Doc tải Word, Slides tải PPTX, PDF tải PDF. Google Form và link khác không hiện nút tải.</small></label>
        <label class="checkbox-label inline-checkbox"><input type="checkbox" data-inline-report-link-active ${report.is_active ? "checked" : ""} /> Bật cho tất cả người dùng</label>
      </div>`;
  }

  function markReportLinkDirty(row) {
    row?.querySelector("[data-save-report-link-inline]")?.classList.remove("hidden");
  }

  function addInlineReportLink() {
    reportLinkDrafts = [createReportLinkDraft()];
    if ($("#report-link-picker")) $("#report-link-picker").value = "";
    if ($("#report-link-admin-search")) $("#report-link-admin-search").value = "";
    renderReportLinkAdminEditor();
    document.querySelector('[data-report-link-row="draft-new-report-link"]')?.querySelector("input")?.focus();
  }

  async function saveInlineReportLink(rowKey, button) {
    const row = document.querySelector(`[data-report-link-row="${CSS.escape(rowKey)}"]`);
    if (!row) return;
    const payload = {
      id: row.dataset.reportLinkId ? Number(row.dataset.reportLinkId) : null,
      ma_bao_cao: row.querySelector('[data-inline-report-link-field="ma_bao_cao"]')?.value.trim() || "",
      ten_bao_cao: row.querySelector('[data-inline-report-link-field="ten_bao_cao"]')?.value.trim() || "",
      link: row.querySelector('[data-inline-report-link-field="link"]')?.value.trim() || "",
      link_type: row.querySelector('[data-inline-report-link-field="link_type"]')?.value || "other",
      is_active: Boolean(row.querySelector("[data-inline-report-link-active]")?.checked),
    };
    if (!payload.ten_bao_cao || !payload.link) {
      showToast("Vui lòng nhập tên báo cáo và link.", "error");
      return;
    }
    setButtonLoading(button, true);
    try {
      const response = await api("/api/admin/report-links", { method: "POST", body: JSON.stringify(payload) });
      reportLinkDrafts = reportLinkDrafts.filter((item) => item._rowKey !== rowKey);
      markDataStale("reportLinks");
      showMessage($("#report-link-admin-message"), "Đã lưu link báo cáo.");
      showToast("Đã lưu link báo cáo.");
      await loadReportLinks({ force: true });
      const picker = $("#report-link-picker");
      if (picker && response.ma_bao_cao) {
        picker.value = response.ma_bao_cao;
        renderReportLinkAdminEditor();
      }
    } catch (error) {
      showMessage($("#report-link-admin-message"), error.message, "error");
      showToast(error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function deleteInlineReportLink(rowKey) {
    if (rowKey.startsWith("draft-")) {
      reportLinkDrafts = reportLinkDrafts.filter((item) => item._rowKey !== rowKey);
      renderReportLinkAdminEditor();
      return;
    }
    const row = document.querySelector(`[data-report-link-row="${CSS.escape(rowKey)}"]`);
    const reportId = row?.dataset.reportLinkId;
    if (!reportId || !confirm("Xóa link báo cáo này?")) return;
    try {
      await api(`/api/admin/report-links/${reportId}`, { method: "DELETE" });
      markDataStale("reportLinks");
      showMessage($("#report-link-admin-message"), "Đã xóa link báo cáo.");
      await loadReportLinks({ force: true });
    } catch (error) {
      showMessage($("#report-link-admin-message"), error.message, "error");
    }
  }

  window.VNPTReportLinks = {
    addInlineReportLink,
    loadReportLinks,
    renderReportLinkAdminEditor,
    renderReportLinksTable,
  };
})();
