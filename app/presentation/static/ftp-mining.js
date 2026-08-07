(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const emptyRow = app.emptyRow || ((colspan, title, description = "") => `<tr><td colspan="${colspan}">${title}${description ? ` ${description}` : ""}</td></tr>`);
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const markDataFresh = app.markDataFresh || (() => {});
  const markDataStale = app.markDataStale || (() => {});
  const setButtonLoading = app.setButtonLoading || (() => {});
  const setTableLoading = app.setTableLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});
  const repairDataEncoding = app.repairDataEncoding || ((value) => value);
  let ftpReports = [];
  let ftpReportDrafts = [];
  let ftpRuns = [];
  let eventsBound = false;
  let pollTimer = 0;

  function activeStatuses() {
    return new Set(["queued", "running"]);
  }

  function parseFtpVariablesText(text) {
    const variables = {};
    String(text || "").replace(/\r/g, "\n").split("\n").forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) return;
      const separatorIndex = line.includes("=") ? line.indexOf("=") : line.indexOf(":");
      if (separatorIndex <= 0) return;
      const key = line.slice(0, separatorIndex).trim();
      if (!key) return;
      variables[key] = line.slice(separatorIndex + 1).trim();
    });
    return variables;
  }

  function variablesToText(variables) {
    if (!variables || typeof variables !== "object") return "";
    return Object.entries(variables).map(([key, value]) => `${key}=${value ?? ""}`).join("\n");
  }

  function parseFtpSourcesText(text) {
    const sources = [];
    const errors = [];
    String(text || "").replace(/\r/g, "\n").split("\n").forEach((rawLine, index) => {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) return;
      const parts = line.split("|").map((part) => part.trim());
      if (parts.length < 3 || !parts[0] || !parts[1] || !parts[2]) {
        errors.push(`Dong nguon ${index + 1} phai co dang TEN|LINK_THU_MUC|TEN_FILE.`);
        return;
      }
      sources.push({ name: parts[0], folder_path: parts[1], file_name_template: parts.slice(2).join("|") });
    });
    return { sources, errors };
  }

  function sourcesToText(sources) {
    if (!Array.isArray(sources)) return "";
    return sources
      .map((source) => `${source.name || source.label || ""}|${source.folder_path || ""}|${source.file_name_template || source.file || ""}`)
      .join("\n");
  }

  function parseFtpStoredConfig(report) {
    const rawTemplate = String(report?.file_name_template || "").trim();
    let config = {};
    if (rawTemplate.startsWith("{")) {
      try {
        const parsed = JSON.parse(rawTemplate);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) config = parsed;
      } catch {
        config = {};
      }
    }
    const isAdvanced = Boolean(config.sources || config.variables || config.file_name_template || config.output_file_name_template);
    const sources = Array.isArray(config.sources) ? config.sources : [];
    return {
      isAdvanced,
      variables: config.variables && typeof config.variables === "object" ? config.variables : {},
      sources,
      file_name_template: isAdvanced ? String(config.file_name_template || "") : rawTemplate,
      output_file_name_template: isAdvanced ? String(config.output_file_name_template || config.file_name_template || "") : rawTemplate,
    };
  }

  function buildStoredFileTemplate(fileTemplate, variablesText, sourcesText) {
    const variables = parseFtpVariablesText(variablesText);
    const parsedSources = parseFtpSourcesText(sourcesText);
    if (parsedSources.errors.length) {
      return { ok: false, message: parsedSources.errors[0], value: "" };
    }
    const cleanFileTemplate = String(fileTemplate || "").trim();
    if (!parsedSources.sources.length && !Object.keys(variables).length) {
      return { ok: true, value: cleanFileTemplate, sources: [] };
    }
    const outputTemplate = cleanFileTemplate || "ftp_tong_hop_{yyyyMMdd}.xlsx";
    return {
      ok: true,
      sources: parsedSources.sources,
      value: JSON.stringify({
        version: 1,
        file_name_template: outputTemplate,
        output_file_name_template: outputTemplate,
        variables,
        sources: parsedSources.sources,
      }),
    };
  }

  function fileTemplateForRun(report, fileTemplate) {
    const config = parseFtpStoredConfig(report);
    if (!config.isAdvanced) return String(fileTemplate || "").trim();
    const nextConfig = {
      version: 1,
      file_name_template: config.file_name_template || String(fileTemplate || "").trim(),
      output_file_name_template: String(fileTemplate || config.output_file_name_template || config.file_name_template || "").trim(),
      variables: config.variables,
      sources: config.sources,
    };
    if (!nextConfig.sources.length) {
      nextConfig.file_name_template = nextConfig.output_file_name_template;
    }
    return JSON.stringify(nextConfig);
  }

  function ftpTemplateLabel(value) {
    const config = parseFtpStoredConfig({ file_name_template: value });
    if (config.sources.length) {
      return `Gop ${config.sources.length} nguon -> ${config.output_file_name_template || "ftp_tong_hop.xlsx"}`;
    }
    return config.file_name_template || value || "";
  }

  async function loadFtpReports({ force = false } = {}) {
    bindFtpEvents();
    const editor = $("#ftp-report-editor");
    if (!editor) return;
    if (!force && isDataFresh("ftpReports") && ftpReports.length) {
      renderFtpReports();
      return;
    }
    editor.innerHTML = `<div class="loading-row">Dang tai cau hinh FTP...</div>`;
    try {
      const data = repairDataEncoding(await api("/api/admin/ftp-reports"));
      ftpReports = data.reports || [];
      markDataFresh("ftpReports");
      renderFtpReports();
    } catch (error) {
      editor.innerHTML = `<div class="empty-state"><div><strong>Khong tai duoc cau hinh FTP</strong><p>${escapeHtml(error.message)}</p></div></div>`;
    }
  }

  async function loadFtpMining({ force = false } = {}) {
    bindFtpEvents();
    const select = $("#ftp-run-report-select");
    const history = $("#ftp-run-history");
    if (!select || !history) return;
    if (!force && isDataFresh("ftpMining") && ftpReports.length) {
      renderFtpRunSelect();
      renderFtpRunHistory();
      return;
    }
    setTableLoading("#ftp-run-history", 5, "Dang tai lich su FTP...");
    try {
      const [configData, runData] = await Promise.all([
        api("/api/ftp-reports/configs"),
        api("/api/ftp-reports/runs?limit=30"),
      ]);
      ftpReports = repairDataEncoding(configData).reports || [];
      ftpRuns = repairDataEncoding(runData).runs || [];
      markDataFresh("ftpMining");
      renderFtpRunSelect();
      renderFtpRunOverrides();
      renderFtpRunHistory();
      scheduleFtpPollingIfNeeded();
    } catch (error) {
      showMessage($("#ftp-run-message"), error.message, "error");
      history.innerHTML = emptyRow(5, "Khong tai duoc lich su FTP", error.message);
    }
  }

  function renderFtpReports() {
    const editor = $("#ftp-report-editor");
    if (!editor) return;
    refreshFtpReportPicker();
    const pickedCode = $("#ftp-report-picker")?.value || "";
    const search = ($("#ftp-report-search")?.value || "").trim().toLowerCase();
    let rows = [...ftpReportDrafts, ...ftpReports];
    if (pickedCode) rows = rows.filter((item) => item.ma_bao_cao === pickedCode);
    if (search) {
      rows = rows.filter((item) => {
        const config = parseFtpStoredConfig(item);
        return [item.ma_bao_cao, item.ten_bao_cao, item.folder_path, item.file_name_template, item.connection_code, sourcesToText(config.sources), variablesToText(config.variables)]
          .join(" ").toLowerCase().includes(search);
      });
    }
    editor.innerHTML = rows.length
      ? rows.map((report) => renderFtpReportCard(report)).join("")
      : `<div class="empty-state"><div><strong>Chua co cau hinh FTP</strong><p>Bam Them bao cao FTP de cau hinh lan dau.</p></div></div>`;
    document.querySelectorAll("[data-inline-ftp-field]").forEach((field) => {
      field.addEventListener("input", () => markFtpReportDirty(field.closest("[data-ftp-row]")));
      field.addEventListener("change", () => markFtpReportDirty(field.closest("[data-ftp-row]")));
    });
    document.querySelectorAll("[data-save-ftp-report-inline]").forEach((button) => {
      button.addEventListener("click", () => saveInlineFtpReport(button.dataset.saveFtpReportInline, button));
    });
    document.querySelectorAll("[data-delete-ftp-report]").forEach((button) => {
      button.addEventListener("click", () => deleteInlineFtpReport(button.dataset.deleteFtpReport));
    });
  }

  function refreshFtpReportPicker() {
    const picker = $("#ftp-report-picker");
    if (!picker) return;
    const current = picker.value;
    picker.innerHTML = `<option value="">Them bao cao moi / chua chon bao cao</option>${ftpReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao || report.ma_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")}`;
    if (current && ftpReports.some((report) => report.ma_bao_cao === current)) picker.value = current;
  }

  function createFtpReportDraft() {
    return {
      _rowKey: "draft-new-ftp-report",
      id: "",
      ma_bao_cao: "",
      ten_bao_cao: "",
      folder_path: "",
      file_name_template: "",
      connection_code: "ftp_storage",
      is_active: true,
    };
  }

  function renderFtpReportCard(report) {
    const rowKey = report._rowKey || `ftp-${report.id}`;
    const isDraft = rowKey.startsWith("draft-");
    const config = parseFtpStoredConfig(report);
    const templateValue = config.isAdvanced ? config.output_file_name_template : report.file_name_template || "";
    return `
    <div class="sql-report-editor-card" data-ftp-row="${escapeHtml(rowKey)}" data-ftp-report-id="${escapeHtml(report.id || "")}">
      <div class="section-heading compact">
        <div><p class="eyebrow">${isDraft ? "Them bao cao FTP" : "Chinh bao cao FTP"}</p><h3>${isDraft ? "Tao cau hinh FTP moi" : escapeHtml(report.ten_bao_cao || report.ma_bao_cao)}</h3></div>
        <div class="action-group"><button class="table-action ${isDraft ? "" : "hidden"}" data-save-ftp-report-inline="${escapeHtml(rowKey)}">Luu</button>${isDraft ? "" : `<button class="table-action danger" data-delete-ftp-report="${escapeHtml(rowKey)}">Xoa</button>`}</div>
      </div>
      <label>Ma bao cao<input class="form-control inline-admin-input" data-inline-ftp-field="ma_bao_cao" value="${escapeHtml(report.ma_bao_cao || "")}" placeholder="Tu sinh neu de trong" /></label>
      <label>Ten bao cao<input class="form-control inline-admin-input" data-inline-ftp-field="ten_bao_cao" value="${escapeHtml(report.ten_bao_cao || "")}" placeholder="Ten bao cao FTP" /></label>
      <label>Link thu muc<input class="form-control inline-admin-input" data-inline-ftp-field="folder_path" value="${escapeHtml(report.folder_path || "")}" placeholder="/DATA_BILLING/CTO/FiberPTM/{yyyyMM}" /></label>
      <label>Ten file / file xuat<input class="form-control inline-admin-input" data-inline-ftp-field="file_name_template" value="${escapeHtml(templateValue)}" placeholder="bao_cao_{yyyymmdd}.xlsx hoac ftp_tong_hop_{thang}.xlsx" /><small class="cell-note">{yyyyMM}, {yyyymmdd}, {ddmmyyyy}, {today}, {yesterday}, {last_dd}, {thang}</small></label>
      <label>Bien mac dinh<textarea class="form-control inline-admin-input font-mono text-xs" data-inline-ftp-field="variables_text" rows="2" placeholder="thang={yyyyMM}">${escapeHtml(variablesToText(config.variables))}</textarea></label>
      <label>Nguon gop FTP<textarea class="form-control inline-admin-input font-mono text-xs" data-inline-ftp-field="sources_text" rows="4" placeholder="CTO|/DATA_BILLING/CTO/FiberPTM/{thang}|CTO_Fiber_PTM_LK_ngay_{last_dd}.xlsx&#10;HGA|/DATA_BILLING/HGA/FiberPTM/{thang}|HGA_Fiber_PTM_LK_ngay_{last_dd}.xlsx&#10;STG|/DATA_BILLING/STG/FiberPTM/{thang}|STG_Fiber_PTM_LK_ngay_{last_dd}.xlsx">${escapeHtml(sourcesToText(config.sources))}</textarea><small class="cell-note">Bo trong neu chi tai 1 file. Moi dong: TEN|LINK_THU_MUC|TEN_FILE.</small></label>
      <label>Ket noi<input class="form-control inline-admin-input" data-inline-ftp-field="connection_code" value="${escapeHtml(report.connection_code || "ftp_storage")}" placeholder="ftp_storage" /></label>
      <label class="checkbox-label inline-checkbox"><input type="checkbox" data-inline-ftp-field="is_active" ${report.is_active !== false ? "checked" : ""} /> Dang su dung</label>
    </div>`;
  }

  function markFtpReportDirty(row) {
    row?.querySelector("[data-save-ftp-report-inline]")?.classList.remove("hidden");
  }

  function addInlineFtpReport() {
    ftpReportDrafts = [createFtpReportDraft()];
    if ($("#ftp-report-picker")) $("#ftp-report-picker").value = "";
    if ($("#ftp-report-search")) $("#ftp-report-search").value = "";
    renderFtpReports();
    document.querySelector('[data-ftp-row="draft-new-ftp-report"]')?.querySelector("input")?.focus();
  }

  async function saveInlineFtpReport(rowKey, button) {
    const row = document.querySelector(`[data-ftp-row="${CSS.escape(rowKey)}"]`);
    if (!row) return;
    const sourceInput = row.querySelector('[data-inline-ftp-field="sources_text"]')?.value || "";
    const variableInput = row.querySelector('[data-inline-ftp-field="variables_text"]')?.value || "";
    const storedTemplate = buildStoredFileTemplate(
      row.querySelector('[data-inline-ftp-field="file_name_template"]')?.value.trim() || "",
      variableInput,
      sourceInput,
    );
    if (!storedTemplate.ok) {
      showToast(storedTemplate.message, "error");
      return;
    }
    const payload = {
      id: row.dataset.ftpReportId ? Number(row.dataset.ftpReportId) : null,
      ma_bao_cao: row.querySelector('[data-inline-ftp-field="ma_bao_cao"]')?.value.trim() || "",
      ten_bao_cao: row.querySelector('[data-inline-ftp-field="ten_bao_cao"]')?.value.trim() || "",
      folder_path: row.querySelector('[data-inline-ftp-field="folder_path"]')?.value.trim() || "",
      file_name_template: storedTemplate.value,
      connection_code: row.querySelector('[data-inline-ftp-field="connection_code"]')?.value.trim() || "ftp_storage",
      is_active: Boolean(row.querySelector('[data-inline-ftp-field="is_active"]')?.checked),
    };
    if (!payload.folder_path && storedTemplate.sources?.length) payload.folder_path = storedTemplate.sources[0].folder_path;
    if (!payload.ten_bao_cao || !payload.folder_path || !payload.file_name_template) {
      showToast("Vui long nhap ten bao cao, link thu muc va ten file FTP.", "error");
      return;
    }
    setButtonLoading(button, true);
    try {
      const response = await api("/api/admin/ftp-reports", { method: "POST", body: JSON.stringify(payload) });
      ftpReportDrafts = ftpReportDrafts.filter((item) => item._rowKey !== rowKey);
      markDataStale("ftpReports", "ftpMining");
      showMessage($("#ftp-reports-message"), "Da luu cau hinh FTP.");
      showToast("Da luu cau hinh FTP.");
      await loadFtpReports({ force: true });
      const picker = $("#ftp-report-picker");
      if (picker && response.ma_bao_cao) {
        picker.value = response.ma_bao_cao;
        renderFtpReports();
      }
    } catch (error) {
      showMessage($("#ftp-reports-message"), error.message, "error");
      showToast(error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function deleteInlineFtpReport(rowKey) {
    if (rowKey.startsWith("draft-")) {
      ftpReportDrafts = ftpReportDrafts.filter((item) => item._rowKey !== rowKey);
      renderFtpReports();
      return;
    }
    const row = document.querySelector(`[data-ftp-row="${CSS.escape(rowKey)}"]`);
    const reportId = row?.dataset.ftpReportId;
    if (!reportId || !confirm("Xoa cau hinh bao cao FTP nay?")) return;
    try {
      await api(`/api/admin/ftp-reports/${reportId}`, { method: "DELETE" });
      markDataStale("ftpReports", "ftpMining");
      showMessage($("#ftp-reports-message"), "Da xoa cau hinh FTP.");
      await loadFtpReports({ force: true });
    } catch (error) {
      showMessage($("#ftp-reports-message"), error.message, "error");
    }
  }

  function renderFtpRunSelect() {
    const select = $("#ftp-run-report-select");
    if (!select) return;
    const current = select.value;
    select.innerHTML = ftpReports.length
      ? ftpReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao || report.ma_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")
      : `<option value="">Chua co cau hinh FTP</option>`;
    if (current && ftpReports.some((report) => report.ma_bao_cao === current)) select.value = current;
  }

  function selectedFtpReport() {
    const code = $("#ftp-run-report-select")?.value || "";
    return ftpReports.find((report) => report.ma_bao_cao === code) || null;
  }

  function renderFtpRunOverrides() {
    const report = selectedFtpReport();
    const config = parseFtpStoredConfig(report);
    const folder = $("#ftp-run-folder-path");
    const fileName = $("#ftp-run-file-template");
    const variables = $("#ftp-run-variables");
    const summary = $("#ftp-run-source-summary");
    if (folder) folder.value = report?.folder_path || "";
    if (fileName) fileName.value = config.isAdvanced ? config.output_file_name_template : report?.file_name_template || "";
    if (variables) variables.value = variablesToText(config.variables);
    if (summary) {
      summary.textContent = config.sources.length
        ? `Bao cao nay se tai ${config.sources.length} nguon FTP va gop thanh 1 file.`
        : "Bao cao don: co the sua link thu muc, ten file va bien truoc khi chay.";
    }
    refreshFtpRunHistory(report?.ma_bao_cao || "");
  }

  async function runFtpReport(event) {
    event.preventDefault();
    const report = selectedFtpReport();
    const button = $("#run-ftp-report");
    if (!report) {
      showMessage($("#ftp-run-message"), "Chua chon bao cao FTP.", "error");
      return;
    }
    setButtonLoading(button, true);
    try {
      const response = repairDataEncoding(await api("/api/ftp-reports/run", {
        method: "POST",
        body: JSON.stringify({
          ma_bao_cao: report.ma_bao_cao,
          folder_path: $("#ftp-run-folder-path")?.value.trim() || "",
          file_name_template: fileTemplateForRun(report, $("#ftp-run-file-template")?.value.trim() || ""),
          variables: parseFtpVariablesText($("#ftp-run-variables")?.value || ""),
        }),
      }));
      showMessage($("#ftp-run-message"), response.message || "Da dua task FTP vao hang doi may tram.", "success");
      await refreshFtpRunHistory(report.ma_bao_cao);
      scheduleFtpPollingIfNeeded();
    } catch (error) {
      showMessage($("#ftp-run-message"), error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function refreshFtpRunHistory(maBaoCao = "") {
    const query = maBaoCao ? `?ma_bao_cao=${encodeURIComponent(maBaoCao)}&limit=30` : "?limit=30";
    const data = repairDataEncoding(await api(`/api/ftp-reports/runs${query}`));
    ftpRuns = data.runs || [];
    renderFtpRunHistory();
    scheduleFtpPollingIfNeeded();
  }

  function renderFtpRunHistory() {
    const table = $("#ftp-run-history");
    if (!table) return;
    const summary = $("#ftp-run-history-summary");
    if (summary) summary.textContent = ftpRuns.length ? `${ftpRuns.length} lan lay gan nhat` : "Chua co du lieu";
    table.innerHTML = ftpRuns.length
      ? ftpRuns.map((run) => renderFtpRunRow(run)).join("")
      : emptyRow(5, "Chua co lich su lay FTP", "Bam Lay bao cao de tao task moi tren may tram.");
    table.querySelectorAll("[data-ftp-run-action='cancel']").forEach((button) => {
      button.addEventListener("click", () => cancelFtpRun(button.dataset.runId));
    });
  }

  function renderFtpRunRow(run) {
    const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
    const statusValue = String(run.status || "").toLowerCase();
    const ok = statusValue === "success";
    const fileUrl = run.file_url || run.download_url || run.storage_link || "";
    const fileLabel = run.file_name || run.resolved_file_name || "Tai file";
    const file = fileUrl
      ? `<a class="onebss-file-link onebss-file-link-primary" href="${escapeHtml(fileUrl)}" ${/^https?:\/\//.test(fileUrl) ? 'target="_blank" rel="noopener"' : ""}>${escapeHtml(fileLabel)}</a>${run.storage_status ? `<small class="cell-note">${escapeHtml(run.storage_status)}</small>` : ""}`
      : (run.file_name || run.resolved_file_name ? `<span class="onebss-file-name">${escapeHtml(run.file_name || run.resolved_file_name)}</span>` : "-");
    const actions = run.can_cancel ? `<button class="table-action danger" data-ftp-run-action="cancel" data-run-id="${escapeHtml(run.run_id || "")}" type="button">Huy</button>` : "";
    return `
      <tr>
        <td class="onebss-time-cell">${escapeHtml(startedAt)}</td>
        <td>${escapeHtml(run.ten_bao_cao || run.ma_bao_cao || "")}<small class="cell-note">${escapeHtml(run.resolved_file_name || ftpTemplateLabel(run.file_name_template) || "")}</small></td>
        <td><span class="status ${ok ? "success" : activeStatuses().has(statusValue) ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
        <td>${file}</td>
        <td>${escapeHtml(run.message || "")}${actions ? `<div class="action-group onebss-row-actions">${actions}</div>` : ""}</td>
      </tr>`;
  }

  async function cancelFtpRun(runId) {
    if (!runId || !confirm("Huy task FTP nay?")) return;
    try {
      const response = repairDataEncoding(await api(`/api/ftp-reports/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }));
      showMessage($("#ftp-run-message"), response.message || "Da huy task FTP.");
      await refreshFtpRunHistory($("#ftp-run-report-select")?.value || "");
    } catch (error) {
      showMessage($("#ftp-run-message"), error.message, "error");
    }
  }

  async function clearFtpRunHistory() {
    const code = $("#ftp-run-report-select")?.value || "";
    if (!confirm(code ? `Don lich su FTP cua ${code}?` : "Don toan bo lich su FTP?")) return;
    const query = code ? `?ma_bao_cao=${encodeURIComponent(code)}` : "";
    try {
      const response = await api(`/api/ftp-reports/runs${query}`, { method: "DELETE" });
      showMessage($("#ftp-run-message"), `Da xoa ${response.deleted || 0} dong lich su FTP.`);
      await refreshFtpRunHistory(code);
    } catch (error) {
      showMessage($("#ftp-run-message"), error.message, "error");
    }
  }

  function scheduleFtpPollingIfNeeded() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = 0;
    }
    if (!ftpRuns.some((run) => activeStatuses().has(String(run.status || "").toLowerCase()))) return;
    pollTimer = window.setTimeout(() => {
      refreshFtpRunHistory($("#ftp-run-report-select")?.value || "").catch((error) => showMessage($("#ftp-run-message"), error.message, "warning"));
    }, 3000);
  }

  function bindFtpEvents() {
    if (eventsBound) return;
    eventsBound = true;
    $("#add-inline-ftp-report")?.addEventListener("click", addInlineFtpReport);
    $("#ftp-report-search")?.addEventListener("input", renderFtpReports);
    $("#ftp-report-picker")?.addEventListener("change", renderFtpReports);
    $("#ftp-run-form")?.addEventListener("submit", runFtpReport);
    $("#ftp-run-report-select")?.addEventListener("change", renderFtpRunOverrides);
    $("#refresh-ftp-runs")?.addEventListener("click", () => refreshFtpRunHistory($("#ftp-run-report-select")?.value || ""));
    $("#clear-ftp-run-history")?.addEventListener("click", clearFtpRunHistory);
  }

  bindFtpEvents();
  window.VNPTFtpMining = { loadFtpReports, loadFtpMining, addInlineFtpReport };
})();
