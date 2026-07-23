(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const emptyRow = app.emptyRow;
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const markDataFresh = app.markDataFresh || (() => {});
  const renderCompactCode = app.renderCompactCode || ((value) => `<code>${escapeHtml(value)}</code>`);
  const setButtonLoading = app.setButtonLoading || (() => {});
  const setTableLoading = app.setTableLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});
  let dataMiningSchedules = [];
  let dataMiningRuns = [];
  let eventsBound = false;

  async function loadDataMining({ force = false } = {}) {
    bindDataMiningEvents();
    const scheduleTable = $("#data-mining-schedules-table");
    const runsTable = $("#data-mining-runs-table");
    if (!scheduleTable || !runsTable) return;
    if (!force && isDataFresh("dataMining")) {
      renderDataMiningSchedules();
      renderDataMiningRuns();
      return;
    }
    setTableLoading("#data-mining-schedules-table", 7, "Đang tải lịch đào dữ liệu...");
    setTableLoading("#data-mining-runs-table", 5, "Đang tải nhật ký đào dữ liệu...");
    try {
      const [scheduleData, runData] = await Promise.all([
        api("/api/admin/data-mining/schedules"),
        api("/api/admin/data-mining/runs?limit=20"),
      ]);
      dataMiningSchedules = scheduleData.schedules || [];
      dataMiningRuns = runData.runs || [];
      markDataFresh("dataMining");
      renderDataMiningSchedules();
      renderDataMiningRuns();
    } catch (error) {
      scheduleTable.innerHTML = emptyRow(7, "Không tải được lịch đào dữ liệu", error.message);
      runsTable.innerHTML = emptyRow(5, "Không tải được nhật ký đào dữ liệu", error.message);
    }
  }

  function dataMiningScheduleText(schedule) {
    if (schedule.schedule_type === "Weekly") return `Hàng tuần ${schedule.weekday || "-"} lúc ${schedule.run_time || "-"}`;
    if (schedule.schedule_type === "Monthly") return `Ngày ${schedule.month_day || 1} hàng tháng lúc ${schedule.run_time || "-"}`;
    return `Hàng ngày lúc ${schedule.run_time || "-"}`;
  }

  function renderDataMiningSchedules() {
    const table = $("#data-mining-schedules-table");
    if (!table) return;
    table.innerHTML = dataMiningSchedules.length
      ? dataMiningSchedules.map((schedule) => renderDataMiningScheduleRow(schedule)).join("")
      : emptyRow(7, "Chưa có lịch đào dữ liệu", "Bấm Thêm lịch để cấu hình tự động lấy báo cáo OneBSS.");
    document.querySelectorAll("[data-edit-data-mining]").forEach((button) => button.addEventListener("click", () => openDataMiningSchedule(button.dataset.editDataMining)));
    document.querySelectorAll("[data-run-data-mining]").forEach((button) => button.addEventListener("click", () => runDataMiningScheduleNow(button.dataset.runDataMining, button)));
    document.querySelectorAll("[data-delete-data-mining]").forEach((button) => button.addEventListener("click", () => deleteDataMiningSchedule(button.dataset.deleteDataMining)));
  }

  function renderDataMiningScheduleRow(schedule) {
    const paramsText = JSON.stringify(schedule.parameters || {});
    const lastRun = schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString("vi-VN") : "";
    const fileText = schedule.file_name_template || "Theo tên báo cáo";
    const storageText = schedule.storage_link || "Lưu nội bộ";
    return `
      <tr>
        <td><strong>${escapeHtml(schedule.name || schedule.schedule_id)}</strong><small class="cell-note">${escapeHtml(schedule.report_url || "")}</small></td>
        <td>${escapeHtml(dataMiningScheduleText(schedule))}</td>
        <td><code>${escapeHtml(fileText)}</code><small class="cell-note">${escapeHtml(storageText)}</small></td>
        <td class="compact-code-cell">${renderCompactCode(paramsText)}</td>
        <td><span class="status ${schedule.is_active ? "viewer" : "inactive"}">${schedule.is_active ? "Đang bật" : "Tạm tắt"}</span>${schedule.last_status ? `<small class="cell-note">${escapeHtml(schedule.last_status)}</small>` : ""}${schedule.last_error ? `<small class="cell-note text-red-700">${escapeHtml(schedule.last_error)}</small>` : ""}</td>
        <td>${lastRun ? escapeHtml(lastRun) : "-"}${schedule.last_file_name ? `<small class="cell-note">${escapeHtml(schedule.last_file_name)}</small>` : ""}</td>
        <td class="table-action-cell"><div class="action-group"><button class="table-action" data-edit-data-mining="${escapeHtml(schedule.schedule_id)}">Sửa</button><button class="table-action" data-run-data-mining="${escapeHtml(schedule.schedule_id)}"><span class="button-label">Chạy thử</span><span class="spinner"></span></button><button class="table-action danger" data-delete-data-mining="${escapeHtml(schedule.schedule_id)}">Xóa</button></div></td>
      </tr>`;
  }

  function renderDataMiningRuns() {
    const table = $("#data-mining-runs-table");
    if (!table) return;
    table.innerHTML = dataMiningRuns.length
      ? dataMiningRuns.map((run) => renderDataMiningRunRow(run)).join("")
      : emptyRow(5, "Chưa có lượt chạy", "Khi lịch chạy hoặc bấm Chạy thử, kết quả sẽ xuất hiện ở đây.");
  }

  function renderDataMiningRunRow(run) {
    const startedAt = run.started_at ? new Date(run.started_at).toLocaleString("vi-VN") : "-";
    const ok = run.status === "success";
    const storageLink = run.storage_link && /^https?:\/\//.test(run.storage_link)
      ? `<small class="cell-note"><a href="${escapeHtml(run.storage_link)}" target="_blank" rel="noopener">Mở file lưu trữ</a></small>`
      : "";
    const file = run.file_path ? `<code>${escapeHtml(run.file_name || run.file_path)}</code><small class="cell-note">${escapeHtml(run.file_path)}</small>${storageLink}` : (storageLink || "-");
    return `
      <tr>
        <td>${escapeHtml(startedAt)}</td>
        <td><code>${escapeHtml(run.schedule_id || "")}</code><small class="cell-note">${escapeHtml(run.run_id || "")}</small></td>
        <td><span class="status ${ok ? "viewer" : "inactive"}">${escapeHtml(run.status || "-")}</span></td>
        <td>${file}${run.storage_status ? `<small class="cell-note">${escapeHtml(run.storage_status)}</small>` : ""}</td>
        <td>${escapeHtml(run.message || "")}</td>
      </tr>`;
  }

  function openDataMiningSchedule(scheduleId = "") {
    bindDataMiningEvents();
    const schedule = dataMiningSchedules.find((item) => item.schedule_id === scheduleId);
    const form = $("#data-mining-form");
    if (!form) return;
    form.elements.namedItem("schedule_id").value = schedule?.schedule_id || "";
    form.elements.namedItem("name").value = schedule?.name || "";
    form.elements.namedItem("report_url").value = schedule?.report_url || "";
    form.elements.namedItem("schedule_type").value = schedule?.schedule_type || "Daily";
    form.elements.namedItem("run_time").value = schedule?.run_time || "07:00";
    form.elements.namedItem("weekday").value = schedule?.weekday || "";
    form.elements.namedItem("month_day").value = schedule?.month_day || 1;
    form.elements.namedItem("storage_link").value = schedule?.storage_link || "";
    form.elements.namedItem("file_name_template").value = schedule?.file_name_template || "";
    form.elements.namedItem("parameters_json").value = JSON.stringify(schedule?.parameters || {}, null, 2);
    form.elements.namedItem("is_active").checked = schedule ? Boolean(schedule.is_active) : true;
    form.querySelector(".result").className = "result hidden";
    $("#data-mining-dialog")?.showModal();
  }

  async function saveDataMiningSchedule(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    let parameters = {};
    try {
      parameters = data.parameters_json ? JSON.parse(data.parameters_json) : {};
    } catch {
      showMessage(form.querySelector(".result"), "Tham số JSON chưa đúng định dạng.", "error");
      return;
    }
    try {
      await api("/api/admin/data-mining/schedules", { method: "POST", body: JSON.stringify({
        schedule_id: data.schedule_id || "",
        name: data.name || "",
        report_url: data.report_url || "",
        schedule_type: data.schedule_type || "Daily",
        run_time: data.run_time || "07:00",
        weekday: data.weekday || "",
        month_day: Number(data.month_day || 1),
        storage_link: data.storage_link || "",
        file_name_template: data.file_name_template || "",
        parameters,
        is_active: Boolean(form.elements.namedItem("is_active")?.checked),
      })});
      $("#data-mining-dialog")?.close();
      showMessage($("#data-mining-result"), "Đã lưu lịch đào dữ liệu.");
      showToast("Đã lưu lịch đào dữ liệu.");
      await loadDataMining({ force: true });
    } catch (error) {
      showMessage(form.querySelector(".result"), error.message, "error");
      showToast(error.message, "error");
    }
  }

  async function runDataMiningScheduleNow(scheduleId, button) {
    const schedule = dataMiningSchedules.find((item) => item.schedule_id === scheduleId);
    const otp = prompt("Nhập OTP OneBSS nếu đang có mã. Có thể để trống nếu phiên OneBSS còn hiệu lực.");
    if (otp === null) return;
    const defaultParameters = JSON.stringify(schedule?.parameters || {}, null, 2);
    const parametersText = prompt("Nhập JSON tham số cho lần chạy này. Để trống nếu muốn dùng tham số trong lịch.", defaultParameters);
    if (parametersText === null) return;
    let parameters = {};
    try {
      parameters = parametersText.trim() ? JSON.parse(parametersText) : {};
    } catch {
      showMessage($("#data-mining-result"), "Tham số JSON chạy thử chưa đúng định dạng.", "error");
      return;
    }
    setButtonLoading(button, true);
    try {
      const response = await api(`/api/admin/data-mining/schedules/${encodeURIComponent(scheduleId)}/run-now`, {
        method: "POST",
        body: JSON.stringify({ otp, allow_device_registration: true, parameters }),
      });
      const message = response.message || response.result?.message || (response.ok ? "Đã đưa lịch đào dữ liệu vào hàng đợi." : "Chưa chạy xong lịch đào dữ liệu.");
      showMessage($("#data-mining-result"), message, response.ok ? "success" : "error");
      await loadDataMining({ force: true });
    } catch (error) {
      showMessage($("#data-mining-result"), error.message, "error");
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function deleteDataMiningSchedule(scheduleId) {
    if (!confirm(`Xóa lịch đào dữ liệu ${scheduleId}?`)) return;
    try {
      await api(`/api/admin/data-mining/schedules/${encodeURIComponent(scheduleId)}`, { method: "DELETE" });
      showMessage($("#data-mining-result"), `Đã xóa lịch ${scheduleId}.`);
      await loadDataMining({ force: true });
    } catch (error) {
      showMessage($("#data-mining-result"), error.message, "error");
    }
  }

  function bindDataMiningEvents() {
    if (eventsBound) return;
    eventsBound = true;
    $("#refresh-data-mining")?.addEventListener("click", () => loadDataMining({ force: true }));
    $("#add-data-mining-schedule")?.addEventListener("click", () => openDataMiningSchedule(""));
    $("#data-mining-form")?.addEventListener("submit", saveDataMiningSchedule);
    $("#save-data-mining-button")?.addEventListener("click", () => $("#data-mining-form")?.requestSubmit());
  }

  bindDataMiningEvents();
  window.VNPTDataMining = { loadDataMining, openDataMiningSchedule };
})();
