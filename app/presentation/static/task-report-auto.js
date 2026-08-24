(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const emptyRow = app.emptyRow || ((colspan, title, description = "") => `<tr><td colspan="${colspan}">${title}${description ? ` ${description}` : ""}</td></tr>`);
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const markDataFresh = app.markDataFresh || (() => {});
  const markDataStale = app.markDataStale || (() => {});
  const repairDataEncoding = app.repairDataEncoding || ((value) => value);
  const setButtonLoading = app.setButtonLoading || (() => {});
  const setTableLoading = app.setTableLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});

  let tasks = [];
  let runs = [];
  let eventsBound = false;
  let pollTimer = 0;
  let sourceReports = { onebss: [], sql: [], ftp: [] };
  let sourceReportErrors = {};
  let sourceReportsLoaded = false;
  let sourceReportsPromise = null;

  const activeStatuses = new Set(["queued", "running"]);
  const sourceLabels = { onebss: "OneBSS", sql: "SQL", ftp: "FTP" };
  const scheduleFields = {
    Daily: ["run_time"],
    TimeWindow: ["time_slots"],
    Weekly: ["run_time", "weekday"],
    Monthly: ["run_time", "month_day"],
  };

  async function loadTaskReportAuto({ force = false } = {}) {
    bindEvents();
    ensureDialog();
    const taskTable = $("#task-report-auto-tasks-table");
    const runTable = $("#task-report-auto-runs-table");
    if (!taskTable || !runTable || !api) return;
    if (!force && isDataFresh("taskReportAuto")) {
      renderTasks();
      renderRuns();
      schedulePoll();
      return;
    }
    setTableLoading("#task-report-auto-tasks-table", 7, "Dang tai Task report auto...");
    setTableLoading("#task-report-auto-runs-table", 5, "Dang tai lich su chay...");
    try {
      const [taskData, runData] = await Promise.all([
        api("/api/admin/task-report-auto/tasks"),
        api("/api/admin/task-report-auto/runs?limit=30"),
      ]);
      tasks = taskData.tasks || [];
      runs = runData.runs || [];
      markDataFresh("taskReportAuto");
      renderTasks();
      renderRuns();
      schedulePoll();
      loadSourceReports({ force }).catch(() => {});
    } catch (error) {
      taskTable.innerHTML = emptyRow(7, "Khong tai duoc Task report auto", error.message);
      runTable.innerHTML = emptyRow(5, "Khong tai duoc lich su chay", error.message);
    }
  }

  function renderTasks() {
    const table = $("#task-report-auto-tasks-table");
    if (!table) return;
    table.innerHTML = tasks.length
      ? tasks.map(renderTaskRow).join("")
      : emptyRow(7, "Chua co Task report auto", "Bam Them task de tao lich moi.");
    document.querySelectorAll("[data-edit-task-report-auto]").forEach((button) => {
      button.addEventListener("click", () => openTask(button.dataset.editTaskReportAuto));
    });
    document.querySelectorAll("[data-run-task-report-auto]").forEach((button) => {
      button.addEventListener("click", () => runNow(button.dataset.runTaskReportAuto, button));
    });
    document.querySelectorAll("[data-delete-task-report-auto]").forEach((button) => {
      button.addEventListener("click", () => deleteTask(button.dataset.deleteTaskReportAuto));
    });
  }

  function renderTaskRow(task) {
    const source = `${String(task.source_type || "").toUpperCase()} ${task.source_code || ""}`.trim();
    const sheet = task.spreadsheet_url || task.spreadsheet_id || "";
    const last = task.last_run_at ? new Date(task.last_run_at).toLocaleString("vi-VN") : "-";
    const lastStatus = task.last_status ? `<small class="cell-note">${escapeHtml(task.last_status)}</small>` : "";
    const lastError = task.last_error ? `<small class="cell-note text-red-700">${escapeHtml(task.last_error)}</small>` : "";
    return `
      <tr>
        <td class="table-action-cell"><div class="action-group">
          <button class="table-action" data-edit-task-report-auto="${escapeHtml(task.task_id || "")}">Sua</button>
          <button class="table-action" data-run-task-report-auto="${escapeHtml(task.task_id || "")}"><span class="button-label">Chay</span><span class="spinner"></span></button>
          <button class="table-action danger" data-delete-task-report-auto="${escapeHtml(task.task_id || "")}">Xoa</button>
        </div></td>
        <td><strong>${escapeHtml(task.name || task.task_id || "")}</strong><small class="cell-note">${escapeHtml(task.task_id || "")}</small></td>
        <td><code>${escapeHtml(source)}</code><small class="cell-note">${escapeHtml(configSummary(task.source_config))}</small></td>
        <td>${escapeHtml(scheduleText(task))}<small class="cell-note">${task.is_active ? "Dang bat" : "Tam tat"}</small></td>
        <td><code>${escapeHtml(task.sheet_name || "DATA")}</code><small class="cell-note">${escapeHtml(sheet)}</small></td>
        <td><code>${escapeHtml(task.chat_id || "")}</code><small class="cell-note">${escapeHtml(task.chat_name || task.target_type || "")}</small></td>
        <td>${escapeHtml(last)}${lastStatus}${lastError}</td>
      </tr>`;
  }

  function renderRuns() {
    const table = $("#task-report-auto-runs-table");
    if (!table) return;
    table.innerHTML = runs.length
      ? runs.map(renderRunRow).join("")
      : emptyRow(5, "Chua co luot chay", "Task queued/running/success/failed se hien tai day.");
    const summary = $("#task-report-auto-runs-summary");
    if (summary) summary.textContent = runs.length ? `${runs.length} luot gan nhat` : "Chua co du lieu";
  }

  function renderRunRow(run) {
    const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
    const statusValue = String(run.status || "").toLowerCase();
    const statusClass = statusValue === "success" ? "viewer" : activeStatuses.has(statusValue) ? "admin" : "inactive";
    const task = tasks.find((item) => item.task_id === run.task_id);
    const result = run.result && typeof run.result === "object" ? run.result : {};
    const captureUrl = run.capture_url || result.capture?.capture_url || result.capture_url || "";
    const sheetText = run.sheet_name || result.sheet?.sheet_name || "";
    const resultLinks = [
      captureUrl ? `<a href="${escapeHtml(captureUrl)}" target="_blank" rel="noopener">Anh</a>` : "",
      sheetText ? `<code>${escapeHtml(sheetText)}</code>` : "",
    ].filter(Boolean).join(" ");
    return `
      <tr>
        <td>${escapeHtml(startedAt)}<small class="cell-note">${escapeHtml(run.run_id || "")}</small></td>
        <td><strong>${escapeHtml(task?.name || run.task_id || "")}</strong><small class="cell-note">${escapeHtml(run.source_type || "")}</small></td>
        <td><span class="status ${statusClass}">${escapeHtml(run.status || "-")}</span><small class="cell-note">${escapeHtml(run.message || "")}</small></td>
        <td><code>${escapeHtml(run.current_step || "-")}</code></td>
        <td>${resultLinks || "-"}${result.failed_step ? `<small class="cell-note text-red-700">${escapeHtml(result.failed_step)}: ${escapeHtml(result.message || "")}</small>` : ""}</td>
      </tr>`;
  }

  function scheduleText(task) {
    const type = task.schedule_type || "Daily";
    if (type === "TimeWindow") return `Khung gio ${Array.isArray(task.time_slots) ? task.time_slots.join(", ") : ""}`;
    if (type === "Weekly") return `Tuan ${task.weekday || "-"} ${task.run_time || "-"}`;
    if (type === "Monthly") return `Ngay ${task.month_day || 1} ${task.run_time || "-"}`;
    return `Ngay ${task.run_time || "-"}`;
  }

  function configSummary(config) {
    if (!config || typeof config !== "object") return "";
    const keys = Object.keys(config).filter((key) => !["parameters", "filters"].includes(key));
    const nested = ["parameters", "filters"].filter((key) => config[key] && typeof config[key] === "object");
    return [...nested, ...keys].slice(0, 4).join(", ");
  }

  async function loadSourceReports({ force = false } = {}) {
    if (!api) return sourceReports;
    if (!force && sourceReportsLoaded) return sourceReports;
    if (!force && sourceReportsPromise) return sourceReportsPromise;
    sourceReportsPromise = api("/api/admin/task-report-auto/source-configs")
      .then((data) => {
        const reports = data.reports || {};
        sourceReports = {
          onebss: normalizeReports(reports.onebss),
          sql: normalizeReports(reports.sql),
          ftp: normalizeReports(reports.ftp),
        };
        sourceReportErrors = data.errors || {};
        sourceReportsLoaded = true;
        return sourceReports;
      })
      .catch((error) => {
        sourceReportErrors = { all: error.message };
        throw error;
      })
      .finally(() => {
        sourceReportsPromise = null;
      });
    return sourceReportsPromise;
  }

  function normalizeReports(value) {
    const repaired = repairDataEncoding(value);
    return Array.isArray(repaired) ? repaired.filter((item) => item && typeof item === "object") : [];
  }

  function reportCode(report) {
    return String(report?.ma_bao_cao || report?.code || report?.report_code || "").trim();
  }

  function reportName(report) {
    return String(report?.ten_bao_cao || report?.name || reportCode(report)).trim();
  }

  function reportLabel(report) {
    const code = reportCode(report);
    const name = reportName(report);
    if (code && name && code !== name) return `${code} - ${name}`;
    return code || name || "Khong co ma";
  }

  function reportSummary(report, sourceType) {
    if (!report) return "";
    const parts = [];
    const params = sourceType === "sql" ? report.cac_tham_so : report.danh_sach_bien;
    if (Array.isArray(params) && params.length) parts.push(`Bien: ${params.slice(0, 8).join(", ")}`);
    if (sourceType === "ftp" && report.folder_path) parts.push(`Thu muc: ${report.folder_path}`);
    if (sourceType === "ftp" && report.file_name_template) parts.push(`File: ${report.file_name_template}`);
    if (report.connection_code) parts.push(`Ket noi: ${report.connection_code}`);
    if (report.otp_service_code) parts.push(`OTP: ${report.otp_service_code}`);
    return parts.join(" | ");
  }

  function selectedReport(form) {
    const type = form.elements.namedItem("source_type")?.value || "onebss";
    const code = form.elements.namedItem("source_code")?.value || "";
    return (sourceReports[type] || []).find((report) => reportCode(report) === code) || null;
  }

  function refreshSourceReportSelect(form, selectedCode = "") {
    const select = form.elements.namedItem("source_code");
    const type = form.elements.namedItem("source_type")?.value || "onebss";
    if (!select) return;
    const reports = sourceReports[type] || [];
    const currentCode = selectedCode || select.value || "";
    select.innerHTML = "";
    const placeholder = new Option(sourceReportsLoaded ? `Chon lenh ${sourceLabels[type] || type}` : "Dang tai danh sach...", "");
    select.add(placeholder);
    reports.forEach((report) => {
      const code = reportCode(report);
      if (!code) return;
      select.add(new Option(reportLabel(report), code));
    });
    if (currentCode && !reports.some((report) => reportCode(report) === currentCode)) {
      select.add(new Option(`${currentCode} (dang dung)`, currentCode));
    }
    select.value = currentCode;
    updateSourceReportNote(form);
  }

  function updateSourceReportNote(form, { updateName = false } = {}) {
    const note = $("#task-report-auto-source-note");
    const type = form.elements.namedItem("source_type")?.value || "onebss";
    const reports = sourceReports[type] || [];
    const report = selectedReport(form);
    if (!note) return;
    if (sourceReportErrors.all || sourceReportErrors[type]) {
      note.textContent = sourceReportErrors[type] || sourceReportErrors.all;
      note.className = "task-auto-report-note error";
      return;
    }
    if (!sourceReportsLoaded) {
      note.textContent = "Dang tai danh sach lenh da cau hinh...";
      note.className = "task-auto-report-note";
      return;
    }
    if (!form.elements.namedItem("source_code")?.value) {
      note.textContent = reports.length ? `${reports.length} lenh ${sourceLabels[type] || type} da cau hinh.` : `Chua co lenh ${sourceLabels[type] || type} dang bat.`;
      note.className = reports.length ? "task-auto-report-note" : "task-auto-report-note warning";
      return;
    }
    const summary = reportSummary(report, type);
    note.textContent = summary || "Lenh da duoc chon.";
    note.className = "task-auto-report-note";
    if (updateName && report && !form.elements.namedItem("name")?.value.trim()) {
      form.elements.namedItem("name").value = reportName(report);
    }
  }

  function updateScheduleFields(form) {
    const type = form.elements.namedItem("schedule_type")?.value || "Daily";
    const visible = new Set(scheduleFields[type] || scheduleFields.Daily);
    form.querySelectorAll("[data-schedule-field]").forEach((field) => {
      field.classList.toggle("hidden", !visible.has(field.dataset.scheduleField));
    });
  }

  function shouldOpenAdvanced(task) {
    if (!task) return false;
    const config = task.source_config && typeof task.source_config === "object" ? task.source_config : {};
    return Boolean(
      Object.keys(config).length
      || task.public_wait_selector
      || Number(task.retry_limit ?? 2) !== 2
      || !task.is_active
    );
  }

  function ensureDialog() {
    if ($("#task-report-auto-dialog")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "task-report-auto-dialog";
    dialog.innerHTML = `
      <form id="task-report-auto-form" class="dialog-form task-auto-form">
        <input type="hidden" name="task_id" />
        <div class="dialog-heading">
          <div><p class="eyebrow">Task report auto</p><h2 id="task-report-auto-dialog-title">Them task</h2></div>
          <button class="icon-button" type="button" data-close-task-report-auto>&times;</button>
        </div>
        <div class="task-auto-dialog-body">
          <fieldset class="task-auto-section">
            <legend>Nguon du lieu</legend>
            <div class="task-auto-form-grid">
              <label class="task-auto-wide">Ten task<input class="form-control" name="name" required /></label>
              <label>Nguon<select class="form-control" name="source_type"><option value="onebss">OneBSS</option><option value="sql">SQL</option><option value="ftp">FTP</option></select></label>
              <label>Lenh da cau hinh<select class="form-control" name="source_code" required></select></label>
              <div class="task-auto-report-note task-auto-wide" id="task-report-auto-source-note"></div>
            </div>
          </fieldset>
          <fieldset class="task-auto-section">
            <legend>Lich chay</legend>
            <div class="task-auto-form-grid">
              <label>Loai lich<select class="form-control" name="schedule_type"><option value="Daily">Daily</option><option value="TimeWindow">TimeWindow</option><option value="Weekly">Weekly</option><option value="Monthly">Monthly</option></select></label>
              <label data-schedule-field="run_time">Gio chay<input class="form-control" name="run_time" type="time" value="07:00" /></label>
              <label data-schedule-field="time_slots">Khung gio<input class="form-control" name="time_slots" placeholder="07:00, 11:30, 17:00" /></label>
              <label data-schedule-field="weekday">Thu<input class="form-control" name="weekday" placeholder="mon, tue, thu 2..." /></label>
              <label data-schedule-field="month_day">Ngay thang<input class="form-control" name="month_day" type="number" min="1" max="31" value="1" /></label>
            </div>
          </fieldset>
          <fieldset class="task-auto-section">
            <legend>Dich nap du lieu</legend>
            <div class="task-auto-form-grid">
              <label class="task-auto-wide">Google Sheet URL/ID<input class="form-control" name="spreadsheet_url" required /></label>
              <label>Ten tab<input class="form-control" name="sheet_name" value="DATA" required /></label>
            </div>
          </fieldset>
          <details class="task-auto-advanced">
            <summary>Nang cao</summary>
            <div class="task-auto-form-grid">
              <label>Retry<input class="form-control" name="retry_limit" type="number" min="0" max="5" value="2" /></label>
              <label class="task-auto-wide">Source config JSON<textarea class="form-control font-mono text-xs" name="source_config_json" rows="7" placeholder='{"parameters":{},"filters":{}}'></textarea></label>
              <label class="checkbox-row task-auto-wide"><input name="is_active" type="checkbox" checked /> Bat task</label>
            </div>
          </details>
        </div>
        <div class="result hidden" id="task-report-auto-form-message"></div>
        <div class="dialog-actions"><button class="btn-secondary" type="button" data-close-task-report-auto>Dong</button><button class="btn-primary" id="save-task-report-auto-button" type="submit"><span class="button-label">Luu task</span><span class="spinner"></span></button></div>
      </form>`;
    document.body.appendChild(dialog);
    const form = dialog.querySelector("#task-report-auto-form");
    dialog.querySelectorAll("[data-close-task-report-auto]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    form?.addEventListener("submit", saveTask);
    form?.elements.namedItem("source_type")?.addEventListener("change", () => {
      refreshSourceReportSelect(form, "");
    });
    form?.elements.namedItem("source_code")?.addEventListener("change", () => updateSourceReportNote(form, { updateName: true }));
    form?.elements.namedItem("schedule_type")?.addEventListener("change", () => updateScheduleFields(form));
  }

  async function openTask(taskId = "") {
    ensureDialog();
    const task = tasks.find((item) => item.task_id === taskId);
    const form = $("#task-report-auto-form");
    if (!form) return;
    const sourceCode = task?.source_code || "";
    form.elements.namedItem("task_id").value = task?.task_id || "";
    form.elements.namedItem("name").value = task?.name || "";
    form.elements.namedItem("source_type").value = task?.source_type || "onebss";
    form.elements.namedItem("schedule_type").value = task?.schedule_type || "Daily";
    form.elements.namedItem("run_time").value = task?.run_time || "07:00";
    form.elements.namedItem("time_slots").value = Array.isArray(task?.time_slots) ? task.time_slots.join(", ") : "";
    form.elements.namedItem("weekday").value = task?.weekday || "";
    form.elements.namedItem("month_day").value = task?.month_day || 1;
    form.elements.namedItem("spreadsheet_url").value = task?.spreadsheet_url || task?.spreadsheet_id || "";
    form.elements.namedItem("sheet_name").value = task?.sheet_name || "DATA";
    form.elements.namedItem("retry_limit").value = task?.retry_limit ?? 2;
    form.elements.namedItem("source_config_json").value = JSON.stringify(task?.source_config || {}, null, 2);
    form.elements.namedItem("is_active").checked = task ? Boolean(task.is_active) : true;
    form.querySelector(".task-auto-advanced").open = shouldOpenAdvanced(task);
    $("#task-report-auto-dialog-title").textContent = task ? "Sua task" : "Them task";
    $("#task-report-auto-form-message").className = "result hidden";
    refreshSourceReportSelect(form, sourceCode);
    updateScheduleFields(form);
    $("#task-report-auto-dialog")?.showModal();
    try {
      await loadSourceReports();
      refreshSourceReportSelect(form, sourceCode);
      updateSourceReportNote(form, { updateName: !task });
    } catch (error) {
      refreshSourceReportSelect(form, sourceCode);
      showMessage($("#task-report-auto-form-message"), error.message, "error");
    }
  }

  async function saveTask(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    let sourceConfig = {};
    try {
      sourceConfig = data.source_config_json ? JSON.parse(data.source_config_json) : {};
    } catch {
      showMessage($("#task-report-auto-form-message"), "Source config JSON chua hop le.", "error");
      return;
    }
    const payload = {
      task_id: data.task_id || "",
      name: data.name || "",
      source_type: data.source_type || "onebss",
      source_code: data.source_code || "",
      source_config: sourceConfig,
      schedule_type: data.schedule_type || "Daily",
      time_slots: data.schedule_type === "TimeWindow" ? parseSlots(data.time_slots) : [],
      run_time: data.run_time || "07:00",
      weekday: data.weekday || "",
      month_day: Number(data.month_day || 1),
      spreadsheet_url: data.spreadsheet_url || "",
      sheet_name: data.sheet_name || "DATA",
      public_url: "",
      public_wait_selector: "",
      target_type: "group",
      chat_id: "",
      chat_name: "",
      caption: "",
      retry_limit: Number(data.retry_limit || 0),
      is_active: Boolean(form.elements.namedItem("is_active")?.checked),
    };
    const button = $("#save-task-report-auto-button");
    setButtonLoading(button, true);
    try {
      await api("/api/admin/task-report-auto/tasks", { method: "POST", body: JSON.stringify(payload) });
      $("#task-report-auto-dialog")?.close();
      markDataStale("taskReportAuto");
      showMessage($("#task-report-auto-message"), "Da luu Task report auto.");
      showToast("Da luu Task report auto.");
      await loadTaskReportAuto({ force: true });
    } catch (error) {
      showMessage($("#task-report-auto-form-message"), error.message, "error");
      showToast(error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  function parseSlots(value) {
    return String(value || "")
      .split(/[\s,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function runNow(taskId, button) {
    setButtonLoading(button, true);
    try {
      const response = await api(`/api/admin/task-report-auto/tasks/${encodeURIComponent(taskId)}/run-now`, {
        method: "POST",
        body: JSON.stringify({ source_config: {} }),
      });
      markDataStale("taskReportAuto");
      showMessage($("#task-report-auto-message"), response.run?.message || "Da dua Task report auto vao hang doi.");
      await loadTaskReportAuto({ force: true });
    } catch (error) {
      showMessage($("#task-report-auto-message"), error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function deleteTask(taskId) {
    if (!confirm(`Xoa Task report auto ${taskId}?`)) return;
    try {
      await api(`/api/admin/task-report-auto/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
      markDataStale("taskReportAuto");
      showMessage($("#task-report-auto-message"), "Da xoa Task report auto.");
      await loadTaskReportAuto({ force: true });
    } catch (error) {
      showMessage($("#task-report-auto-message"), error.message, "error");
    }
  }

  function schedulePoll() {
    window.clearTimeout(pollTimer);
    if (!runs.some((run) => activeStatuses.has(String(run.status || "").toLowerCase()))) return;
    pollTimer = window.setTimeout(() => loadTaskReportAuto({ force: true }), 5000);
  }

  function bindEvents() {
    if (eventsBound) return;
    eventsBound = true;
    $("#refresh-task-report-auto")?.addEventListener("click", () => loadTaskReportAuto({ force: true }));
    $("#add-task-report-auto")?.addEventListener("click", () => openTask(""));
  }

  bindEvents();
  window.VNPTTaskReportAuto = { loadTaskReportAuto, openTask };
})();
