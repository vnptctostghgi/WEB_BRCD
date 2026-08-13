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
  let tasks = [];
  let runs = [];
  let eventsBound = false;
  let pollTimer = 0;

  const activeStatuses = new Set(["queued", "running"]);

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

  function ensureDialog() {
    if ($("#task-report-auto-dialog")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "task-report-auto-dialog";
    dialog.innerHTML = `
      <form id="task-report-auto-form" class="dialog-form">
        <input type="hidden" name="task_id" />
        <div class="dialog-heading"><div><p class="eyebrow">Task report auto</p><h2 id="task-report-auto-dialog-title">Them task</h2></div><button class="dialog-close" type="button" data-close-task-report-auto>&times;</button></div>
        <div class="form-grid two">
          <label>Ten task<input class="form-control" name="name" /></label>
          <label>Nguon<select class="form-control" name="source_type"><option value="onebss">OneBSS</option><option value="sql">SQL</option><option value="ftp">FTP</option></select></label>
          <label>Ma bao cao<input class="form-control" name="source_code" /></label>
          <label>Lich<select class="form-control" name="schedule_type"><option value="Daily">Daily</option><option value="TimeWindow">TimeWindow</option><option value="Weekly">Weekly</option><option value="Monthly">Monthly</option></select></label>
          <label>Gio chay<input class="form-control" name="run_time" type="time" value="07:00" /></label>
          <label>Khung gio<input class="form-control" name="time_slots" placeholder="07:00, 11:30, 17:00" /></label>
          <label>Thu<input class="form-control" name="weekday" placeholder="mon, tue, thu 2..." /></label>
          <label>Ngay thang<input class="form-control" name="month_day" type="number" min="1" max="31" value="1" /></label>
          <label>Google Sheet URL/ID<input class="form-control" name="spreadsheet_url" /></label>
          <label>Ten tab<input class="form-control" name="sheet_name" value="DATA" /></label>
          <label>Public web<input class="form-control" name="public_url" /></label>
          <label>Wait selector<input class="form-control" name="public_wait_selector" placeholder="#report-root" /></label>
          <label>Zalo type<select class="form-control" name="target_type"><option value="group">group</option><option value="person">person</option></select></label>
          <label>Zalo chat_id<input class="form-control" name="chat_id" /></label>
          <label>Zalo name<input class="form-control" name="chat_name" /></label>
          <label>Retry<input class="form-control" name="retry_limit" type="number" min="0" max="5" value="2" /></label>
        </div>
        <label>Caption<textarea class="form-control" name="caption" rows="2"></textarea></label>
        <label>Source config JSON<textarea class="form-control font-mono text-xs" name="source_config_json" rows="7" placeholder='{"parameters":{},"filters":{}}'></textarea></label>
        <label class="checkbox-row"><input name="is_active" type="checkbox" checked /> Bat task</label>
        <div class="result hidden" id="task-report-auto-form-message"></div>
        <div class="dialog-actions"><button class="btn-secondary" type="button" data-close-task-report-auto>Dong</button><button class="btn-primary" id="save-task-report-auto-button" type="submit"><span class="button-label">Luu task</span><span class="spinner"></span></button></div>
      </form>`;
    document.body.appendChild(dialog);
    dialog.querySelectorAll("[data-close-task-report-auto]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    dialog.querySelector("#task-report-auto-form")?.addEventListener("submit", saveTask);
  }

  function openTask(taskId = "") {
    ensureDialog();
    const task = tasks.find((item) => item.task_id === taskId);
    const form = $("#task-report-auto-form");
    if (!form) return;
    form.elements.namedItem("task_id").value = task?.task_id || "";
    form.elements.namedItem("name").value = task?.name || "";
    form.elements.namedItem("source_type").value = task?.source_type || "onebss";
    form.elements.namedItem("source_code").value = task?.source_code || "";
    form.elements.namedItem("schedule_type").value = task?.schedule_type || "Daily";
    form.elements.namedItem("run_time").value = task?.run_time || "07:00";
    form.elements.namedItem("time_slots").value = Array.isArray(task?.time_slots) ? task.time_slots.join(", ") : "";
    form.elements.namedItem("weekday").value = task?.weekday || "";
    form.elements.namedItem("month_day").value = task?.month_day || 1;
    form.elements.namedItem("spreadsheet_url").value = task?.spreadsheet_url || task?.spreadsheet_id || "";
    form.elements.namedItem("sheet_name").value = task?.sheet_name || "DATA";
    form.elements.namedItem("public_url").value = task?.public_url || "";
    form.elements.namedItem("public_wait_selector").value = task?.public_wait_selector || "";
    form.elements.namedItem("target_type").value = task?.target_type || "group";
    form.elements.namedItem("chat_id").value = task?.chat_id || "";
    form.elements.namedItem("chat_name").value = task?.chat_name || "";
    form.elements.namedItem("caption").value = task?.caption || "";
    form.elements.namedItem("retry_limit").value = task?.retry_limit ?? 2;
    form.elements.namedItem("source_config_json").value = JSON.stringify(task?.source_config || {}, null, 2);
    form.elements.namedItem("is_active").checked = task ? Boolean(task.is_active) : true;
    $("#task-report-auto-dialog-title").textContent = task ? "Sua task" : "Them task";
    $("#task-report-auto-form-message").className = "result hidden";
    $("#task-report-auto-dialog")?.showModal();
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
      time_slots: parseSlots(data.time_slots),
      run_time: data.run_time || "07:00",
      weekday: data.weekday || "",
      month_day: Number(data.month_day || 1),
      spreadsheet_url: data.spreadsheet_url || "",
      sheet_name: data.sheet_name || "DATA",
      public_url: data.public_url || "",
      public_wait_selector: data.public_wait_selector || "",
      target_type: data.target_type || "group",
      chat_id: data.chat_id || "",
      chat_name: data.chat_name || "",
      caption: data.caption || "",
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
