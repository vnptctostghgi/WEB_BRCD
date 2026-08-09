(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const TABLE_HISTORY_LIMIT = app.TABLE_HISTORY_LIMIT || 20;
  const TABLE_SHORT_PAGE_SIZE = app.TABLE_SHORT_PAGE_SIZE || 10;
  const api = app.api;
  const dashboardReportParams = app.dashboardReportParams || (() => []);
  const emptyRow = app.emptyRow || ((colspan, title, description = "") => `<tr><td colspan="${colspan}">${title}${description ? ` ${description}` : ""}</td></tr>`);
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const repairDataEncoding = app.repairDataEncoding || ((value) => value);
  const renderCompactCode = app.renderCompactCode || ((value) => `<code>${escapeHtml(value)}</code>`);
  const setButtonLoading = app.setButtonLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});
  const sleep = app.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  let sqlReports = [];
  let oneBssReports = [];
  let oneBssReportRuns = [];
  let oneBssPendingSessionId = "";
  let oneBssPendingOtpRequestId = "";
  let oneBssPendingJobId = "";
  let oneBssOtpPollTimer = null;
  let oneBssOtpPollToken = 0;
  let oneBssOtpManualSubmitStarted = false;
  let oneBssManualOtpTimer = null;
  let oneBssJobPollTimer = null;
  let oneBssJobPollToken = 0;
  let oneBssRunInProgress = false;
  let oneBssRunParameterEditing = false;
  let dynamicReportExportJobs = [];
  const dynamicReportHistoryPollingJobs = new Set();
  let reportsRuntimeEventsBound = false;

function newOneBssRunId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, "");
  return `onebss${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

async function loadDynamicReports() {
  if (!sqlReports.length) {
    try {
      const data = await api("/api/reports/configs");
      sqlReports = data.reports || [];
      markDataFresh("reportConfigs");
    } catch (error) {
      showMessage($("#dynamic-report-message"), error.message, "error");
      return;
    }
  }
  fillDynamicReportSelect();
  renderDynamicReportFilters();
  clearDynamicReportCache();
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
    container.innerHTML = "";
    container.classList.add("hidden");
    return;
  }
  const params = dashboardReportParams(report);
  if (!params.length) {
    container.innerHTML = "";
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");
  container.innerHTML = params.map((param) => {
    const lower = param.toLowerCase();
    if (lower.includes("ngay") || lower.includes("date")) {
      return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" type="date" /></label>`;
    }
    if (lower.includes("status") || lower.includes("trang_thai")) {
      return `<label>${escapeHtml(param)}<select class="form-control dynamic-filter" name="${escapeHtml(param)}"><option value="">Tất cả</option><option value="1">Đang hoạt động</option><option value="0">Không hoạt động</option></select></label>`;
    }
    return `<label>${escapeHtml(param)}<input class="form-control dynamic-filter" name="${escapeHtml(param)}" placeholder="Nhập ${escapeHtml(param)}" /></label>`;
  }).join("");
}

function dynamicReportFilters() {
  const filters = {};
  document.querySelectorAll(".dynamic-filter").forEach((input) => {
    if (input.value) filters[input.name] = input.value;
  });
  return filters;
}

function dynamicReportPayload({ page = 1 } = {}) {
  return {
    ma_bao_cao: $("#dynamic-report-select")?.value || "",
    filters: dynamicReportFilters(),
    search: "",
    search_columns: [],
    page,
    page_size: 20,
  };
}

function clearDynamicReportCache() {
  return;
}

function dynamicReportHistoryItemKey(job) {
  const current = job || {};
  return current.history_id || current.job_id || current.local_id || `local-${Date.now()}`;
}

function dynamicReportExportStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "cancel_requested") return "Đang ngừng";
  if (normalized === "cancelled") return "Đã ngừng";
  if (normalized === "success") return "Đã lấy";
  if (normalized === "complete") return "Hoàn tất";
  if (normalized === "failed") return "Lỗi";
  if (normalized === "running") return "Đang chạy";
  if (normalized === "running_worker") return "Máy trạm đang chạy";
  if (normalized === "queued") return "Đang chờ";
  if (normalized === "queued_worker") return "Chờ máy trạm";
  return status || "-";
}

function dynamicReportExportStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "cancel_requested") return "pending";
  if (normalized === "cancelled") return "inactive";
  if (normalized === "success") return "active";
  if (normalized === "complete") return "active";
  if (normalized === "failed") return "inactive";
  if (normalized === "running") return "admin";
  if (normalized === "running_worker") return "admin";
  return "pending";
}

function dynamicReportProgressSteps(job, status) {
  const steps = Array.isArray(job?.progress_steps) ? job.progress_steps.filter((step) => step && typeof step === "object") : [];
  if (steps.length) return steps.slice(-6);
  const fallback = job?.message || dynamicReportExportStatusLabel(status);
  return fallback ? [{ message: fallback, status }] : [];
}

function dynamicReportDateMs(value) {
  if (value === null || value === undefined || value === "") return 0;
  if (typeof value === "number") return Number.isFinite(value) ? (value > 0 && value < 1000000000000 ? value * 1000 : value) : 0;
  const text = String(value).trim();
  if (!text) return 0;
  if (/^\d+(\.\d+)?$/.test(text)) return dynamicReportDateMs(Number(text));
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dynamicReportDateText(value) {
  const ms = dynamicReportDateMs(value);
  return ms ? new Date(ms).toLocaleString("vi-VN") : "-";
}

function dynamicReportDurationText(ms) {
  const seconds = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  if (seconds < 60) return `${seconds} giây`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút`;
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return restMinutes ? `${hours} giờ ${restMinutes} phút` : `${hours} giờ`;
}

function dynamicReportLastUpdateMs(job) {
  const steps = dynamicReportProgressSteps(job, job?.status);
  const latestStepMs = steps.reduce((latest, step) => Math.max(latest, dynamicReportDateMs(step.at)), 0);
  return dynamicReportDateMs(job?.updated_at) || latestStepMs || dynamicReportDateMs(job?.created_at);
}

function dynamicReportProgressHint(job, status) {
  const normalized = String(status || "").toLowerCase();
  const createdMs = dynamicReportDateMs(job?.created_at);
  const updatedMs = dynamicReportLastUpdateMs(job);
  const waitText = createdMs ? dynamicReportDurationText(Date.now() - createdMs) : "";
  const updateText = updatedMs ? dynamicReportDurationText(Date.now() - updatedMs) : "";
  const workerId = job?.worker_id ? ` (${job.worker_id})` : "";
  let text = "";
  let kind = "pending";
  if (normalized === "queued_worker") {
    const workerState = job?.worker_state && typeof job.worker_state === "object" ? job.worker_state : {};
    if (workerState.status === "ready") {
      text = `${workerState.message || "Đã thấy máy trạm online. Web đang chờ máy trạm nhận lệnh SQL."}${waitText ? ` · đã chờ ${waitText}` : ""}`;
    } else if (workerState.status === "busy") {
      kind = "admin";
      text = `${workerState.message || "Máy trạm SQL online nhưng đang bận xử lý task khác."}${waitText ? ` · đã chờ ${waitText}` : ""}`;
    } else if (workerState.status === "no_sql_worker") {
      text = `${workerState.message || "Đã thấy health-check nhưng chưa thấy worker SQL đang chạy."}${waitText ? ` · đã chờ ${waitText}` : ""}`;
    } else if (workerState.status === "no_online_worker") {
      text = `${workerState.message || "Chưa thấy máy trạm online để nhận lệnh SQL."}${waitText ? ` · đã chờ ${waitText}` : ""}`;
    } else {
      text = `Chưa có máy trạm nhận lệnh${waitText ? ` · đã chờ ${waitText}` : ""}.`;
    }
    if (createdMs && Date.now() - createdMs > 60000 && ["no_online_worker", "no_sql_worker"].includes(workerState.status)) text += " Nếu vẫn đứng ở đây, hãy mở trang Máy trạm để kiểm tra worker online.";
  } else if (normalized === "running_worker") {
    kind = "admin";
    text = `Máy trạm${workerId} đã nhận lệnh và đang xử lý${updateText ? ` · cập nhật ${updateText} trước` : ""}.`;
    if (updatedMs && Date.now() - updatedMs > 300000) text += " Chưa có cập nhật mới từ máy trạm trong vài phút.";
  } else if (normalized === "queued") {
    text = `Đang chờ trong hàng đợi web${waitText ? ` · đã chờ ${waitText}` : ""}.`;
  } else if (normalized === "running") {
    kind = "admin";
    text = `Web đang xử lý${updateText ? ` · cập nhật ${updateText} trước` : ""}.`;
  } else if (normalized === "complete" || normalized === "success") {
    kind = "active";
    text = `Đã hoàn tất${updateText ? ` · cập nhật ${updateText} trước` : ""}.`;
  } else if (normalized === "failed" || normalized === "cancelled") {
    kind = "inactive";
    text = updateText ? `Cập nhật cuối ${updateText} trước.` : "";
  }
  return text ? `<div class="sql-progress-hint ${kind}">${escapeHtml(text)}</div>` : "";
}

function dynamicReportProgressHtml(job, status) {
  const steps = dynamicReportProgressSteps(job, status);
  const items = steps.map((step, index) => {
    const stepStatus = String(step.status || status || "").toLowerCase();
    const isLatest = index === steps.length - 1;
    const className = `sql-progress-step ${isLatest ? "current" : ""} ${dynamicReportExportStatusClass(stepStatus)}`;
    return `<li class="${className}"><span class="sql-progress-dot" aria-hidden="true"></span><span>${escapeHtml(step.message || dynamicReportExportStatusLabel(stepStatus))}</span></li>`;
  }).join("");
  return `<div class="sql-progress"><span class="status ${dynamicReportExportStatusClass(status)}">${escapeHtml(dynamicReportExportStatusLabel(status))}</span>${dynamicReportProgressHint(job, status)}${items ? `<ol class="sql-progress-steps">${items}</ol>` : ""}</div>`;
}

function upsertDynamicReportExportJob(job) {
  const current = repairDataEncoding(job || {});
  const jobId = dynamicReportHistoryItemKey(current);
  const existing = dynamicReportExportJobs.find((item) => dynamicReportHistoryItemKey(item) === jobId) || {};
  const selected = $("#dynamic-report-select");
  const merged = {
    ...existing,
    ...current,
    job_id: jobId,
    history_id: current.history_id || existing.history_id || jobId,
    event_type: current.event_type || existing.event_type || "export",
    queue_position: current.queue_position || existing.queue_position || 0,
    can_cancel: current.can_cancel ?? existing.can_cancel ?? dynamicReportExportIsActive(current),
    created_at: current.created_at || existing.created_at || new Date().toISOString(),
    updated_at: current.updated_at || existing.updated_at || current.created_at || existing.created_at || new Date().toISOString(),
    worker_id: current.worker_id || existing.worker_id || "",
    report_code: current.report_code || existing.report_code || selected?.value || "",
    report_name: current.report_name || existing.report_name || selected?.selectedOptions?.[0]?.textContent || "",
  };
  dynamicReportExportJobs = [
    merged,
    ...dynamicReportExportJobs.filter((item) => dynamicReportHistoryItemKey(item) !== jobId),
  ].slice(0, TABLE_HISTORY_LIMIT);
  renderDynamicReportExportJobs();
  return merged;
}

function dynamicReportExportIsActive(job) {
  const status = String(job?.status || "").toLowerCase();
  return ["queued", "queued_worker", "running", "running_worker", "cancel_requested"].includes(status);
}

function dynamicReportExportResultHtml(job, status) {
  const link = job.drive_url || job.download_url || "";
  const action = [];
  if (link) {
    action.push(`<a class="table-action" href="${escapeHtml(link)}" target="_blank" rel="noopener">Mở file</a>`);
    if (job.drive_url) action.push(`<a class="table-action" href="${escapeHtml(job.drive_url)}" target="_blank" rel="noopener">Link Drive</a>`);
  } else {
    action.push(`<span>${escapeHtml(job.message || (status === "failed" ? "Lấy dữ liệu lỗi" : "Đang xử lý"))}</span>`);
  }
  if (job.can_cancel || dynamicReportExportIsActive(job)) {
    const isStopping = status === "cancel_requested";
    const label = status === "queued" ? "Xóa lệnh" : isStopping ? "Đang ngừng" : "Ngừng lệnh";
    action.push(`<button class="table-action danger" data-dynamic-report-job-action="cancel" data-job-id="${escapeHtml(job.job_id || "")}" type="button" ${isStopping ? "disabled" : ""}>${label}</button>`);
  }
  return `<div class="action-group">${action.join("")}</div>`;
}

function renderDynamicReportExportJobs() {
  const body = $("#dynamic-report-export-results");
  if (!body) return;
  const heading = document.querySelector(".dynamic-report-export-heading h2");
  if (heading) heading.textContent = "Kết quả lấy dữ liệu";
  const head = body.closest("table")?.querySelector("thead");
  if (head) head.innerHTML = "<tr><th>Thời gian</th><th>Báo cáo</th><th>Tiến trình</th><th>File / link Drive</th></tr>";
  if (!dynamicReportExportJobs.length) {
    body.innerHTML = emptyRow(4, "Chưa có dữ liệu", "File và link Drive sẽ xuất hiện ở đây sau khi máy trạm xử lý xong.");
    return;
  }
  body.innerHTML = dynamicReportExportJobs.map((job) => {
    const createdAt = dynamicReportDateText(job.created_at);
    const updatedMs = dynamicReportLastUpdateMs(job);
    const updatedText = updatedMs ? dynamicReportDurationText(Date.now() - updatedMs) : "";
    const status = String(job.status || "queued").toLowerCase();
    return `
      <tr>
        <td>${escapeHtml(createdAt)}${updatedText ? `<small class="cell-note">Cập nhật ${escapeHtml(updatedText)} trước</small>` : ""}</td>
        <td><strong>${escapeHtml(job.report_code || job.ma_bao_cao || "-")}</strong><small class="cell-note">${escapeHtml(job.report_name || job.ten_bao_cao || "")}</small></td>
        <td class="sql-progress-cell">${dynamicReportProgressHtml(job, status)}</td>
        <td class="table-action-cell">${dynamicReportExportResultHtml(job, status)}</td>
      </tr>
    `;
  }).join("");
}

function setDynamicReportExportStatus(text, type = "success", job = null) {
  const box = $("#dynamic-report-message");
  if (box) {
    box.textContent = "";
    box.classList.add("hidden");
    box.setAttribute("aria-hidden", "true");
  }
  showToast(text || job?.message || "", type);
}

function dynamicReportExportJobTime(job) {
  return dynamicReportDateMs(job?.created_at || job?.updated_at || 0);
}

function mergeDynamicReportExportJobs(items) {
  const merged = new Map();
  [...dynamicReportExportJobs, ...(items || [])].forEach((raw) => {
    const job = repairDataEncoding(raw || {});
    const key = dynamicReportHistoryItemKey(job);
    const existing = merged.get(key) || {};
    merged.set(key, {
      ...existing,
      ...job,
      job_id: job.job_id || existing.job_id || key,
      history_id: job.history_id || existing.history_id || key,
    });
  });
  dynamicReportExportJobs = Array.from(merged.values())
    .sort((left, right) => {
      const leftActive = dynamicReportExportIsActive(left) ? 1 : 0;
      const rightActive = dynamicReportExportIsActive(right) ? 1 : 0;
      if (leftActive !== rightActive) return rightActive - leftActive;
      return dynamicReportExportJobTime(right) - dynamicReportExportJobTime(left);
    })
    .slice(0, TABLE_HISTORY_LIMIT);
  renderDynamicReportExportJobs();
  dynamicReportExportJobs.forEach((job) => {
    if (dynamicReportExportIsActive(job) && job.job_id) monitorDynamicReportExportJob(job.job_id);
  });
}

async function loadDynamicReportHistory({ silent = false } = {}) {
  try {
    const [historyData, queueData] = await Promise.all([
      api(`/api/reports/history?limit=${TABLE_HISTORY_LIMIT}`),
      api(`/api/reports/export-jobs?limit=${TABLE_HISTORY_LIMIT}`),
    ]);
    mergeDynamicReportExportJobs([...(historyData.items || []), ...(queueData.jobs || [])]);
  } catch (error) {
    if (!silent) showToast(error.message, "error");
  }
}

async function monitorDynamicReportExportJob(jobId) {
  if (!jobId || dynamicReportHistoryPollingJobs.has(jobId)) return;
  dynamicReportHistoryPollingJobs.add(jobId);
  try {
    for (let attempt = 0; attempt < 900; attempt += 1) {
      await sleep(attempt === 0 ? 1500 : 2500);
      const job = repairDataEncoding(await api(`/api/reports/export-jobs/${encodeURIComponent(jobId)}`));
      upsertDynamicReportExportJob(job);
      if (!dynamicReportExportIsActive(job)) {
        if (job.status === "complete") showToast(job.message || "Đã lấy dữ liệu xong. Bấm Mở file trong bảng kết quả.");
        if (job.status === "cancelled") showToast(job.message || "Đã ngừng lệnh lấy dữ liệu.");
        break;
      }
    }
  } catch (error) {
    const message = error.message || "";
    if (/job/i.test(message) && /Excel/i.test(message)) {
      upsertDynamicReportExportJob({
        job_id: jobId,
        status: "failed",
        message: "Lenh lay du lieu nay khong con trong hang doi web. Hay bam Lay du lieu lai.",
        can_cancel: false,
      });
    } else {
      showToast(message, "error");
    }
  } finally {
    dynamicReportHistoryPollingJobs.delete(jobId);
    loadDynamicReportHistory({ silent: true }).catch(() => {});
  }
}

async function handleDynamicReportExportAction(event) {
  const button = event.target.closest("[data-dynamic-report-job-action]");
  if (!button) return;
  const action = button.dataset.dynamicReportJobAction;
  const jobId = button.dataset.jobId || "";
  if (action !== "cancel" || !jobId) return;
  button.disabled = true;
  try {
    const job = repairDataEncoding(await api(`/api/reports/export-jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" }));
    upsertDynamicReportExportJob(job);
    showToast(job.message || "Đã gửi lệnh ngừng/xóa job.");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    loadDynamicReportHistory({ silent: true }).catch(() => {});
  }
}

async function exportDynamicReport({ buttonSelector = "#run-dynamic-report", includeSearch = false } = {}) {
  const select = $("#dynamic-report-select");
  const message = $("#dynamic-report-message");
  const button = $(buttonSelector);
  let activeExportJob = null;
  if (!select || !select.value) {
    showMessage(message, "Chọn loại báo cáo trước khi lấy dữ liệu.", "error");
    return;
  }
  setButtonLoading(button, true);
  try {
    const started = repairDataEncoding(await api("/api/reports/export-jobs", {
      method: "POST",
      body: JSON.stringify(dynamicReportPayload({ page: 1, includeSearch })),
    }));
    activeExportJob = upsertDynamicReportExportJob({
      ...started,
      report_code: select.value,
      report_name: select.selectedOptions?.[0]?.textContent || "",
      created_at: new Date().toISOString(),
    });
    if (!started.job_id) throw new Error("Không thấy job lấy dữ liệu.");
    showMessage(message, started.message || "Đang lấy dữ liệu trên máy trạm.");
    setDynamicReportExportStatus(started.message || "Đang lấy dữ liệu trên máy trạm.");
    monitorDynamicReportExportJob(started.job_id);
    loadDynamicReportHistory({ silent: true }).catch(() => {});
    showMessage(message, "Đã đưa lệnh lấy dữ liệu vào hàng đợi. Khi xong, file và link Drive sẽ hiện ở bảng bên dưới.");
    return;
  } catch (error) {
    upsertDynamicReportExportJob({
      ...(activeExportJob || {
        local_id: `local-${Date.now()}`,
        report_code: select?.value || "",
        report_name: select?.selectedOptions?.[0]?.textContent || "",
        created_at: new Date().toISOString(),
      }),
      status: "failed",
      message: error.message,
    });
    setDynamicReportExportStatus(error.message, "error");
    showMessage(message, error.message, "error");
  } finally {
    button?.removeAttribute("title");
    setButtonLoading(button, false);
  }
}

async function loadOneBssMining({ force = false } = {}) {
  if (!force && isDataFresh("oneBssMining")) {
    fillOneBssRunSelect();
    renderOneBssRunParameters();
    renderOneBssRunHistory();
    resumeOneBssActiveJobPolling();
    return;
  }
  try {
    const [configData, runData] = await Promise.all([
      api("/api/onebss-reports/configs"),
      api("/api/onebss-reports/runs?limit=30"),
    ]);
    oneBssReports = (configData.reports || []).map((report) => repairDataEncoding(report));
    oneBssReportRuns = (runData.runs || []).map((run) => repairDataEncoding(run));
    markDataFresh("oneBssReports");
    markDataFresh("oneBssMining");
    fillOneBssRunSelect();
    renderOneBssRunParameters();
    renderOneBssRunHistory();
    resumeOneBssActiveJobPolling();
  } catch (error) {
    showMessage($("#onebss-run-message"), error.message, "error");
    const history = $("#onebss-run-history");
    if (history) history.innerHTML = emptyRow(6, "Không tải được dữ liệu OneBSS", error.message);
  }
}

function fillOneBssRunSelect() {
  const select = $("#onebss-run-report-select");
  if (!select) return;
  const current = select.value;
  select.innerHTML = oneBssReports.length
    ? oneBssReports.map((report) => `<option value="${escapeHtml(report.ma_bao_cao)}">${escapeHtml(report.ten_bao_cao)} (${escapeHtml(report.ma_bao_cao)})</option>`).join("")
    : `<option value="">Chưa có báo cáo OneBSS</option>`;
  if (current && oneBssReports.some((report) => report.ma_bao_cao === current)) select.value = current;
}

function selectedOneBssReport() {
  const code = $("#onebss-run-report-select")?.value || "";
  return oneBssReports.find((report) => report.ma_bao_cao === code) || null;
}

function renderOneBssRunParameters() {
  const container = $("#onebss-run-parameters");
  if (!container) return;
  const report = selectedOneBssReport();
  const variables = report?.danh_sach_bien || [];
  if (!report) {
    container.innerHTML = "";
    return;
  }
  const jsonTemplate = JSON.stringify(report?.parameters || {}, null, 2);
  container.innerHTML = `
    ${variables.length ? `<div class="compact-code-cell">${renderCompactCode(variables.join(", "))}</div>` : ""}
    <small class="cell-note">Bien ngay ho tro: {{today}}, {today;yyyyMMdd}, {today;MM/yyyy}, {today-7d;dd/MM/yyyy}.</small>
    <label>Tham số đã cấu hình<textarea class="form-control onebss-param-json font-mono text-xs" rows="9" readonly placeholder="Chưa cấu hình tham số trong Quản trị dữ liệu OneBSS">${escapeHtml(jsonTemplate === "{}" ? "" : jsonTemplate)}</textarea></label>
  `;
}

function collectOneBssRunParameters() {
  const parameters = {};
  document.querySelectorAll(".onebss-param-input").forEach((input) => {
    parameters[input.name] = input.value || "";
  });
  const jsonBox = $(".onebss-param-json");
  if (jsonBox && jsonBox.value.trim()) {
    try {
      return JSON.parse(jsonBox.value);
    } catch {
      throw new Error("Tham số lọc JSON chưa đúng định dạng.");
    }
  }
  const report = selectedOneBssReport();
  if (report?.parameters && Object.keys(report.parameters).length) return report.parameters;
  return parameters;
}

function stopOneBssOtpPolling() {
  oneBssOtpPollToken += 1;
  if (oneBssOtpPollTimer) clearTimeout(oneBssOtpPollTimer);
  oneBssOtpPollTimer = null;
}

function stopOneBssJobPolling() {
  oneBssJobPollToken += 1;
  if (oneBssJobPollTimer) clearTimeout(oneBssJobPollTimer);
  oneBssJobPollTimer = null;
}

function clearOneBssManualOtpTimer() {
  if (oneBssManualOtpTimer) clearTimeout(oneBssManualOtpTimer);
  oneBssManualOtpTimer = null;
}

function setOneBssOtpStatus(message = "", tone = "info") {
  const status = $("#onebss-otp-status");
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
  status.classList.toggle("hidden", !message);
}

function resetOneBssOtpState({ hidePanel = true } = {}) {
  stopOneBssOtpPolling();
  clearOneBssManualOtpTimer();
  oneBssPendingOtpRequestId = "";
  oneBssOtpManualSubmitStarted = false;
  const input = $("#onebss-otp-input");
  if (input) {
    input.value = "";
    input.placeholder = "Nhap OTP";
  }
  setOneBssOtpStatus("");
  if (hidePanel) $("#onebss-otp-panel")?.classList.add("hidden");
}

function showOneBssOtpPanel(message = "") {
  $("#onebss-otp-panel")?.classList.remove("hidden");
  if (message) setOneBssOtpStatus(message);
  $("#onebss-otp-input")?.focus();
}

function startOneBssOtpPolling(otpRequestId) {
  const requestId = String(otpRequestId || "").trim();
  if (!requestId) return;
  stopOneBssOtpPolling();
  oneBssPendingOtpRequestId = requestId;
  oneBssOtpManualSubmitStarted = false;
  const token = oneBssOtpPollToken;
  setOneBssOtpStatus("Dang doi OTP tu tin nhan. Anh co the nhap tay neu nhan duoc truoc.");

  const poll = async () => {
    if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
    try {
      const response = await api(`/api/onebss-reports/otp-requests/${encodeURIComponent(requestId)}`);
      if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
      if (response.status === "matched") {
        clearOneBssManualOtpTimer();
        const input = $("#onebss-otp-input");
        if (input) {
          input.value = response.otp ? String(response.otp).replace(/\D/g, "").slice(0, 8) : "";
          input.placeholder = response.code_masked ? `OTP ${response.code_masked}` : "OTP tu dong da san sang";
        }
        setOneBssOtpStatus("Da boc tach OTP tu tin nhan. Dang dang nhap...", "success");
        stopOneBssOtpPolling();
        await runOneBssReport(response.otp || "", { otpRequestId: requestId, otpSource: "auto", jobId: oneBssPendingJobId });
        return;
      }
      if (["waiting", "created"].includes(response.status || "")) {
        oneBssOtpPollTimer = setTimeout(poll, 2000);
        return;
      }
      setOneBssOtpStatus(response.message || "Chua nhan duoc OTP tu tin nhan.", "warning");
    } catch (error) {
      if (token !== oneBssOtpPollToken || oneBssOtpManualSubmitStarted || !oneBssPendingSessionId) return;
      setOneBssOtpStatus(error.message || "Khong kiem tra duoc tin nhan OTP.", "warning");
      oneBssOtpPollTimer = setTimeout(poll, 4000);
    }
  };

  oneBssOtpPollTimer = setTimeout(poll, 900);
}

function oneBssJobIsActive(status) {
  return ["queued", "running", "otp_required", "otp_invalid", "manual_otp_required"].includes(String(status || "").toLowerCase());
}

function oneBssRunStatusLabel(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "queued") return "Đang chờ";
  if (normalized === "running") return "Đang chạy";
  if (normalized === "otp_required" || normalized === "manual_otp_required") return "Chờ OTP";
  if (normalized === "otp_invalid") return "OTP lỗi";
  if (normalized === "success") return "Hoàn tất";
  if (normalized === "cancelled") return "Đã hủy";
  if (normalized === "failed") return "Lỗi";
  if (normalized === "google_drive_upload_failed") return "Lỗi Drive";
  if (normalized === "google_drive_not_configured") return "Thiếu Drive";
  if (normalized === "storage_failed") return "Lỗi lưu";
  return status || "-";
}

function oneBssRunStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "success") return "viewer";
  if (normalized === "queued" || normalized === "otp_required" || normalized === "manual_otp_required") return "pending";
  if (normalized === "running" || normalized === "otp_invalid") return "admin";
  return "inactive";
}

function oneBssRunKey(run) {
  return run?.run_id || run?.job_id || "";
}

function oneBssRunCanCancel(run) {
  if (run?.can_cancel === true) return true;
  return oneBssJobIsActive(run?.status);
}

function upsertOneBssRun(run) {
  if (!run) return;
  const normalized = repairDataEncoding(run);
  const key = oneBssRunKey(normalized);
  const index = oneBssReportRuns.findIndex((item) => oneBssRunKey(item) === key && key);
  if (index >= 0) {
    oneBssReportRuns[index] = { ...oneBssReportRuns[index], ...normalized };
  } else {
    oneBssReportRuns.unshift(normalized);
  }
  oneBssReportRuns = oneBssReportRuns.slice(0, TABLE_HISTORY_LIMIT);
}

function handleOneBssJobResponse(response, { interactive = true } = {}) {
  const job = repairDataEncoding(response || {});
  const status = String(job.status || "").toLowerCase();
  const message = $("#onebss-run-message");
  if (interactive && job.job_id) oneBssPendingJobId = job.job_id;
  upsertOneBssRun(job.run || job);
  renderOneBssRunHistory();

  if (!interactive) return;

  if (["otp_required", "otp_invalid", "manual_otp_required"].includes(status) && job.session_id) {
    oneBssPendingSessionId = job.session_id || oneBssPendingSessionId;
    oneBssPendingOtpRequestId = job.otp_request_id || oneBssPendingOtpRequestId;
    if (status === "otp_invalid") oneBssOtpManualSubmitStarted = false;
    showOneBssOtpPanel(oneBssPendingOtpRequestId ? "Dang doi OTP tu tin nhan. Anh co the nhap tay neu nhan duoc truoc." : "");
    if (oneBssPendingOtpRequestId && !oneBssOtpManualSubmitStarted) startOneBssOtpPolling(oneBssPendingOtpRequestId);
    showMessage(message, job.message || "OneBSS yeu cau OTP.", status === "otp_invalid" ? "error" : "info");
    return;
  }

  if (status === "queued" || status === "running") {
    showMessage(message, job.message || "Dang lay du lieu OneBSS trong nen.", "info");
    return;
  }

  if (status) {
    oneBssPendingSessionId = "";
    oneBssPendingOtpRequestId = "";
    oneBssPendingJobId = "";
    resetOneBssOtpState();
    stopOneBssJobPolling();
    showMessage(message, job.message || (job.ok ? "Da lay bao cao OneBSS." : "Lay bao cao OneBSS loi."), job.ok ? "success" : "error");
  }
}

function startOneBssJobPolling(jobId, { interactive = true } = {}) {
  const id = String(jobId || "").trim();
  if (!id) return;
  stopOneBssJobPolling();
  if (interactive) oneBssPendingJobId = id;
  const token = oneBssJobPollToken;
  const poll = async () => {
    if (token !== oneBssJobPollToken) return;
    try {
      const response = await api(`/api/onebss-reports/jobs/${encodeURIComponent(id)}`);
      if (token !== oneBssJobPollToken) return;
      handleOneBssJobResponse(response, { interactive });
      if (oneBssJobIsActive(response.status)) {
        const status = String(response.status || "").toLowerCase();
        oneBssJobPollTimer = setTimeout(poll, ["otp_required", "otp_invalid", "manual_otp_required"].includes(status) ? 4000 : 2500);
      } else {
        await refreshOneBssRunHistory($("#onebss-run-report-select")?.value || "");
      }
    } catch (error) {
      if (token !== oneBssJobPollToken) return;
      if (interactive) showMessage($("#onebss-run-message"), error.message || "Khong kiem tra duoc job OneBSS.", "warning");
      oneBssJobPollTimer = setTimeout(poll, 5000);
    }
  };
  oneBssJobPollTimer = setTimeout(poll, 1200);
}

function resumeOneBssActiveJobPolling() {
  // Old active rows are shown in history only. Auto-resuming them on page load
  // can reopen OTP prompts and keep warning the user before a new run starts.
  return;
}

async function runOneBssReport(otp = "", options = {}) {
  if (oneBssRunInProgress) return;
  const select = $("#onebss-run-report-select");
  const button = $("#run-onebss-report");
  const message = $("#onebss-run-message");
  const report = selectedOneBssReport();
  if (!select || !select.value || !report) {
    showMessage(message, "Chưa có cấu hình báo cáo OneBSS.", "error");
    return;
  }
  let parameters = {};
  try {
    parameters = collectOneBssRunParameters();
  } catch (error) {
    showMessage(message, error.message, "error");
    return;
  }
  oneBssRunInProgress = true;
  setButtonLoading(button, true);
  try {
    const requestedOtp = String(otp || "").trim();
    const requestedJobId = requestedOtp ? (options.jobId || oneBssPendingJobId) : (options.jobId || "");
    const clientRequestId = options.clientRequestId || requestedJobId || "";
    const requestedOtpRequestId = requestedOtp ? (options.otpRequestId || oneBssPendingOtpRequestId) : "";
    const response = await api("/api/onebss-reports/run", {
      method: "POST",
      body: JSON.stringify({
        ma_bao_cao: select.value,
        parameters,
        otp: requestedOtp,
        session_id: oneBssPendingSessionId,
        otp_request_id: requestedOtpRequestId,
        otp_source: options.otpSource || "",
        job_id: requestedJobId,
        client_request_id: clientRequestId,
      }),
    });
    if (response.job_id) {
      handleOneBssJobResponse(response);
      if (oneBssJobIsActive(response.status)) startOneBssJobPolling(response.job_id, { interactive: true });
      return;
    }
    if (response.status === "otp_required" || response.status === "otp_invalid" || response.status === "manual_otp_required") {
      oneBssPendingSessionId = response.session_id || oneBssPendingSessionId;
      oneBssPendingOtpRequestId = response.otp_request_id || oneBssPendingOtpRequestId;
      if (response.status === "otp_invalid") oneBssOtpManualSubmitStarted = false;
      showOneBssOtpPanel(oneBssPendingOtpRequestId ? "Dang doi OTP tu tin nhan. Anh co the nhap tay neu nhan duoc truoc." : "");
      if (oneBssPendingOtpRequestId && !oneBssOtpManualSubmitStarted) startOneBssOtpPolling(oneBssPendingOtpRequestId);
      showMessage(message, response.message || "OneBSS yêu cầu OTP.", response.status === "otp_invalid" ? "error" : "info");
      return;
    }
    oneBssPendingSessionId = "";
    resetOneBssOtpState();
    showMessage(message, response.message || (response.ok ? "Đã lấy báo cáo OneBSS." : "Lấy báo cáo OneBSS lỗi."), response.ok ? "success" : "error");
    await refreshOneBssRunHistory(select.value);
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    oneBssRunInProgress = false;
    setButtonLoading(button, false);
  }
}

async function refreshOneBssRunHistory(maBaoCao = "") {
  const query = maBaoCao ? `?ma_bao_cao=${encodeURIComponent(maBaoCao)}&limit=30` : "?limit=30";
  const data = await api(`/api/onebss-reports/runs${query}`);
  oneBssReportRuns = (data.runs || []).map((run) => repairDataEncoding(run));
  renderOneBssRunHistory();
  resumeOneBssActiveJobPolling();
}

function renderOneBssRunHistory() {
  const table = $("#onebss-run-history");
  if (!table) return;
  table.innerHTML = oneBssReportRuns.length
    ? oneBssReportRuns.map((run) => renderOneBssRunRow(run)).join("")
    : emptyRow(6, "Chưa có lượt lấy báo cáo", "Kết quả lấy OneBSS sẽ xuất hiện ở đây sau khi bấm Lấy báo cáo.");
}

function renderOneBssRunRow(run) {
  run = repairDataEncoding(run);
  const startedAt = run.started_at_label || formatOneBssRunTime(run.started_at) || "-";
  const ok = run.status === "success";
  const storageStatus = run.storage_status || "";
  const isUploadedDriveFile = /^uploaded_google_drive:/i.test(storageStatus);
  const isDirectFileLink = run.storage_link
    && /^https?:\/\//.test(run.storage_link)
    && (isUploadedDriveFile || /\/file\/d\/|[?&]id=/.test(run.storage_link));
  const fileLink = isDirectFileLink
    ? `<a href="${escapeHtml(run.storage_link)}" target="_blank" rel="noopener">Mở file</a>`
    : (run.file_path ? `<code>${escapeHtml(run.file_name || run.file_path)}</code><small class="cell-note">${escapeHtml(run.file_path)}</small>` : "-");
  return `
    <tr>
      <td>${escapeHtml(startedAt)}</td>
      <td><strong>${escapeHtml(run.ten_bao_cao || run.ma_bao_cao)}</strong><small class="cell-note">${escapeHtml(run.ma_bao_cao || "")}</small></td>
      <td><span class="status ${ok ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
      <td class="compact-code-cell">${renderCompactCode(JSON.stringify(run.parameters || {}))}</td>
      <td>${fileLink}${storageStatus ? `<small class="cell-note">${escapeHtml(storageStatus)}</small>` : ""}</td>
      <td>${escapeHtml(run.message || "")}</td>
    </tr>`;
}

function normalizeOneBssRunShellText() {
  const summary = $("#onebss-run-history-summary");
  if (summary && !summary.dataset.normalized) {
    summary.textContent = "Ch\u01b0a c\u00f3 d\u1eef li\u1ec7u";
    summary.dataset.normalized = "1";
  }
  const historyTitle = $(".onebss-history-header h2");
  if (historyTitle && !historyTitle.dataset.normalized) {
    historyTitle.textContent = "L\u1ecbch s\u1eed l\u1ea5y d\u1eef li\u1ec7u";
    historyTitle.dataset.normalized = "1";
  }
  const clearButton = $("#clear-onebss-run-history");
  if (clearButton && !clearButton.dataset.normalized) {
    clearButton.textContent = "D\u1ecdn l\u1ecbch s\u1eed";
    clearButton.dataset.normalized = "1";
  }
  const tableHeader = $(".onebss-run-table thead tr");
  if (tableHeader && !tableHeader.dataset.normalized) {
    tableHeader.innerHTML = "<th>Th\u1eddi gian</th><th>B\u00e1o c\u00e1o</th><th>K\u1ebft qu\u1ea3</th><th>File</th><th>Th\u00f4ng b\u00e1o</th><th>Thao t\u00e1c</th>";
    tableHeader.dataset.normalized = "1";
  }
}

function renderOneBssRunParameters() {
  const container = $("#onebss-run-parameters");
  if (!container) return;
  normalizeOneBssRunShellText();
  const report = selectedOneBssReport();
  const variables = report?.danh_sach_bien || [];
  if (!report) {
    container.innerHTML = "";
    updateOneBssParameterEditButton();
    return;
  }
  const jsonTemplate = JSON.stringify(report?.parameters || {}, null, 2);
  const chips = variables.length
    ? variables.map((variable) => `<span>${escapeHtml(variable)}</span>`).join("")
    : "<span>Kh\u00f4ng c\u00f3 bi\u1ebfn c\u1ea5u h\u00ecnh</span>";
  container.innerHTML = `
    <div class="onebss-variable-panel"><span class="onebss-field-title">Danh s\u00e1ch bi\u1ebfn</span><div class="onebss-variable-list">${chips}</div></div>
    <label class="onebss-json-panel">
      <span class="onebss-field-title">Tham s\u1ed1 l\u1ea7n ch\u1ea1y n\u00e0y</span>
      <textarea class="form-control onebss-param-json font-mono text-xs" rows="${oneBssRunParameterEditing ? 10 : 5}" ${oneBssRunParameterEditing ? "" : "readonly"} placeholder="{}">${escapeHtml(jsonTemplate === "{}" ? "" : jsonTemplate)}</textarea>
      <small class="cell-note">Bien ngay ho tro: {{today}}, {today;yyyyMMdd}, {today;MM/yyyy}, {today-7d;dd/MM/yyyy}.</small>
    </label>
  `;
  updateOneBssParameterEditButton();
}

function updateOneBssParameterEditButton() {
  const button = $("#toggle-onebss-param-edit");
  if (!button) return;
  button.textContent = oneBssRunParameterEditing ? "D\u1eebng s\u1eeda" : "Ch\u1ec9nh tham s\u1ed1";
  button.classList.toggle("active", oneBssRunParameterEditing);
}

function toggleOneBssRunParameterEditing() {
  oneBssRunParameterEditing = !oneBssRunParameterEditing;
  renderOneBssRunParameters();
  if (oneBssRunParameterEditing) $(".onebss-param-json")?.focus();
}

function renderOneBssRunHistory() {
  normalizeOneBssRunShellText();
  const table = $("#onebss-run-history");
  const summary = $("#onebss-run-history-summary");
  if (summary) {
    const successCount = oneBssReportRuns.filter((run) => run.status === "success").length;
    summary.textContent = oneBssReportRuns.length ? `${oneBssReportRuns.length} l\u01b0\u1ee3t g\u1ea7n nh\u1ea5t, ${successCount} th\u00e0nh c\u00f4ng` : "Ch\u01b0a c\u00f3 d\u1eef li\u1ec7u";
  }
  if (!table) return;
  const visibleRuns = oneBssReportRuns.slice(0, TABLE_SHORT_PAGE_SIZE);
  table.innerHTML = visibleRuns.length
    ? visibleRuns.map((run) => renderOneBssRunRow(run)).join("")
    : emptyRow(6, "Ch\u01b0a c\u00f3 l\u01b0\u1ee3t l\u1ea5y b\u00e1o c\u00e1o", "K\u1ebft qu\u1ea3 l\u1ea5y OneBSS s\u1ebd xu\u1ea5t hi\u1ec7n \u1edf \u0111\u00e2y sau khi b\u1ea5m L\u1ea5y b\u00e1o c\u00e1o.");
}

function renderOneBssRunRow(run) {
  run = repairDataEncoding(run);
  const startedAt = run.started_at_label || formatOneBssRunTime(run.started_at) || "-";
  const statusValue = String(run.status || "").toLowerCase();
  const storageStatus = run.storage_status || "";
  const fileUrl = String(run.file_url || run.storage_link || run.download_url || "").trim();
  const hasExternalFileUrl = /^https?:\/\//.test(fileUrl);
  const fileLabel = hasExternalFileUrl && /drive\.google\.com/i.test(fileUrl) ? "M\u1edf file tr\u00ean Drive" : (hasExternalFileUrl ? "M\u1edf file" : "T\u1ea3i file");
  const fileNote = run.file_name || (hasExternalFileUrl ? "Link Google Drive" : "");
  const fileLink = fileUrl
    ? `<a class="onebss-file-link onebss-file-link-primary" href="${escapeHtml(fileUrl)}" ${hasExternalFileUrl ? 'target="_blank" rel="noopener"' : ""}>${fileLabel}</a>${fileNote ? `<small class="cell-note">${escapeHtml(fileNote)}</small>` : ""}`
    : (run.file_path ? `<span class="onebss-file-name">${escapeHtml(run.file_name || run.file_path)}</span>` : "-");
  const storageNote = storageStatus && !/^uploaded_google_drive/i.test(storageStatus)
    ? `<small class="cell-note">${escapeHtml(truncateText(storageStatus, 60))}</small>`
    : "";
  const message = truncateText(run.message || "", 180);
  const runId = oneBssRunKey(run);
  const actions = oneBssRunCanCancel(run) && runId
    ? `<button class="table-action danger" data-onebss-run-action="cancel" data-run-id="${escapeHtml(runId)}" type="button">H\u1ee7y</button>`
    : `<span class="cell-note">-</span>`;
  return `
    <tr>
      <td class="onebss-time-cell">${escapeHtml(startedAt)}</td>
      <td><strong>${escapeHtml(run.ten_bao_cao || run.ma_bao_cao)}</strong><small class="cell-note">${escapeHtml(run.ma_bao_cao || "")}</small></td>
      <td><span class="status ${oneBssRunStatusClass(statusValue)}">${escapeHtml(oneBssRunStatusLabel(statusValue))}</span></td>
      <td>${fileLink}${storageNote}</td>
      <td><span title="${escapeHtml(run.message || "")}">${escapeHtml(message)}</span></td>
      <td class="table-action-cell"><div class="action-group onebss-row-actions">${actions}</div></td>
    </tr>`;
}

function formatOneBssRunTime(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime()) || parsed.getFullYear() < 2020) return text;
  return parsed.toLocaleString("vi-VN", { hour12: false });
}

function truncateText(value, maxLength = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

async function cancelOneBssRun(runId, button = null) {
  const id = String(runId || "").trim();
  const message = $("#onebss-run-message");
  if (!id) return;
  if (!confirm("Hủy task lấy báo cáo OneBSS này?")) return;
  try {
    if (button) button.disabled = true;
    const response = repairDataEncoding(await api(`/api/onebss-reports/runs/${encodeURIComponent(id)}/cancel`, { method: "POST" }));
    upsertOneBssRun(response.run || response);
    oneBssPendingSessionId = "";
    oneBssPendingOtpRequestId = "";
    oneBssPendingJobId = "";
    stopOneBssJobPolling();
    resetOneBssOtpState();
    renderOneBssRunHistory();
    showMessage(message, response.message || "Đã hủy task OneBSS.");
    await refreshOneBssRunHistory($("#onebss-run-report-select")?.value || "");
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    if (button) button.disabled = false;
  }
}

function handleOneBssRunHistoryAction(event) {
  const button = event.target.closest("[data-onebss-run-action]");
  if (!button) return;
  const action = button.dataset.onebssRunAction || "";
  if (action === "cancel") {
    cancelOneBssRun(button.dataset.runId || "", button);
  }
}

async function clearOneBssRunHistory() {
  const select = $("#onebss-run-report-select");
  const code = select?.value || "";
  const message = $("#onebss-run-message");
  const button = $("#clear-onebss-run-history");
  if (!confirm("X\u00f3a l\u1ecbch s\u1eed l\u1ea5y d\u1eef li\u1ec7u OneBSS \u0111ang hi\u1ec3n th\u1ecb?")) return;
  const query = code ? `?ma_bao_cao=${encodeURIComponent(code)}` : "";
  try {
    if (button) setButtonLoading(button, true);
    let response;
    try {
      response = await api(`/api/onebss-reports/runs${query}`, { method: "DELETE" });
    } catch (deleteError) {
      response = await api(`/api/onebss-reports/runs/clear${query}`, { method: "POST" });
    }
    showMessage(message, `\u0110\u00e3 d\u1ecdn ${response.deleted || 0} d\u00f2ng l\u1ecbch s\u1eed.`);
    oneBssReportRuns = [];
    renderOneBssRunHistory();
    await refreshOneBssRunHistory(code);
  } catch (error) {
    showMessage(message, error.message, "error");
  } finally {
    if (button) setButtonLoading(button, false);
  }
}


function bindReportsRuntimeEvents() {
  if (reportsRuntimeEventsBound) return;
  reportsRuntimeEventsBound = true;
  $("#onebss-run-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (form?.dataset.onebssSubmitting === "1") return;
    const submitId = newOneBssRunId();
    if (form) form.dataset.onebssSubmitting = "1";
    try {
      oneBssPendingSessionId = "";
      oneBssPendingJobId = submitId;
      stopOneBssJobPolling();
      resetOneBssOtpState();
      await runOneBssReport("", { jobId: submitId, clientRequestId: submitId });
    } finally {
      if (form?.dataset.onebssSubmitting === "1") delete form.dataset.onebssSubmitting;
    }
  });
  $("#toggle-onebss-param-edit")?.addEventListener("click", toggleOneBssRunParameterEditing);
  $("#clear-onebss-run-history")?.addEventListener("click", clearOneBssRunHistory);
  $("#onebss-run-history")?.addEventListener("click", handleOneBssRunHistoryAction);
  $("#onebss-run-report-select")?.addEventListener("change", () => {
    oneBssPendingSessionId = "";
    oneBssPendingJobId = "";
    stopOneBssJobPolling();
    resetOneBssOtpState();
    oneBssRunParameterEditing = false;
    renderOneBssRunParameters();
  });
  $("#onebss-otp-input")?.addEventListener("input", async (event) => {
    const value = event.currentTarget.value.replace(/\D/g, "").slice(0, 8);
    event.currentTarget.value = value;
    clearOneBssManualOtpTimer();
    if (value.length >= 4 && oneBssPendingSessionId && !oneBssRunInProgress) {
      const delay = value.length >= 6 ? 250 : 900;
      oneBssManualOtpTimer = setTimeout(async () => {
        const currentValue = $("#onebss-otp-input")?.value || "";
        if (currentValue !== value || !oneBssPendingSessionId || oneBssRunInProgress) return;
        oneBssOtpManualSubmitStarted = true;
        stopOneBssOtpPolling();
        setOneBssOtpStatus("Dang dung OTP nhap tay de dang nhap...", "info");
        await runOneBssReport(value, { otpRequestId: oneBssPendingOtpRequestId, otpSource: "manual", jobId: oneBssPendingJobId });
      }, delay);
    }
  });
  $("#dynamic-report-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await exportDynamicReport({ buttonSelector: "#run-dynamic-report", includeSearch: false });
  });
  $("#dynamic-report-export-results")?.addEventListener("click", handleDynamicReportExportAction);
  renderDynamicReportExportJobs();
  loadDynamicReportHistory({ silent: true }).catch(() => {});
  $("#dynamic-report-select")?.addEventListener("change", () => {
    clearDynamicReportCache();
    renderDynamicReportFilters();
  });
}

bindReportsRuntimeEvents();
window.VNPTReportsRuntime = { loadDynamicReports, loadOneBssMining, fillDynamicReportSelect, fillOneBssRunSelect };
})();
