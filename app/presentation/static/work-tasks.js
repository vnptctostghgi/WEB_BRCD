(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const emptyRow = app.emptyRow;
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const markDataFresh = app.markDataFresh || (() => {});
  const setTableLoading = app.setTableLoading || (() => {});
  const showMessage = app.showMessage || (() => {});
  const showToast = app.showToast || (() => {});
  let workTasks = [];
  let eventsBound = false;

  async function loadWorkTasks({ force = false } = {}) {
    if (!api || !emptyRow) throw new Error("Module Quản lý công việc chưa sẵn sàng.");
    bindWorkTaskEvents();
    if (!force && isDataFresh("workTasks")) {
      renderWorkTasks();
      return;
    }
    if (workTasks.length && !force) {
      renderWorkTasks();
    }
    if (!workTasks.length || force) setTableLoading("#work-tasks-table", 9, "Đang tải lịch công việc...");
    workTasks = (await api("/api/admin/work-tasks")).tasks;
    markDataFresh("workTasks");
    renderWorkTasks();
  }

  function renderWorkTasks() {
    const table = $("#work-tasks-table");
    if (!table) return;
    table.innerHTML = workTasks.length ? workTasks.map((task) => `
      <tr>
        <td class="table-action-cell">
          <div class="action-group">
            <button class="table-action" data-edit-work-task="${escapeHtml(task.task_id)}">Sửa</button>
            <button class="table-action" data-complete-work-task="${escapeHtml(task.task_id)}">Hoàn thành</button>
            <button class="table-action danger" data-delete-work-task="${escapeHtml(task.task_id)}">Xóa</button>
          </div>
        </td>
        <td><strong>${escapeHtml(task.task_id)}</strong></td>
        <td>${escapeHtml(task.ten_cong_viec)}${task.last_notified_at ? `<small class="cell-note">Đã nhắc: ${escapeHtml(new Date(task.last_notified_at).toLocaleString("vi-VN"))}</small>` : ""}</td>
        <td><span class="status viewer">${escapeHtml(task.type)}</span></td>
        <td><strong>${escapeHtml(task.time)}</strong></td>
        <td>${escapeHtml(task.weekday || "-")}</td>
        <td>${escapeHtml(task.once_date || "-")}</td>
        <td>${escapeHtml(task.group || "-")}</td>
        <td><span class="status ${task.check ? "active" : "inactive"}">${task.check ? "Đã xong" : "Đang chờ"}</span></td>
      </tr>
    `).join("") : emptyRow(9, "Chưa có lịch công việc", "Hãy thêm công việc để hệ thống nhắc qua Telegram đúng giờ.");
    document.querySelectorAll("[data-edit-work-task]").forEach((button) => button.addEventListener("click", () => openWorkTask(button.dataset.editWorkTask)));
    document.querySelectorAll("[data-complete-work-task]").forEach((button) => button.addEventListener("click", () => completeWorkTask(button.dataset.completeWorkTask)));
    document.querySelectorAll("[data-delete-work-task]").forEach((button) => button.addEventListener("click", () => deleteWorkTask(button.dataset.deleteWorkTask)));
  }

  function openWorkTask(taskId = "") {
    bindWorkTaskEvents();
    const task = workTasks.find((item) => item.task_id === taskId);
    const form = $("#work-task-form");
    if (!form) return;
    form.elements.namedItem("task_id").value = task?.task_id || "";
    form.elements.namedItem("task_id").readOnly = true;
    form.elements.namedItem("ten_cong_viec").value = task?.ten_cong_viec || "";
    form.elements.namedItem("type").value = task?.type || "Daily";
    form.elements.namedItem("time").value = task?.time || "07:00";
    form.elements.namedItem("weekday").value = task?.weekday || "";
    form.elements.namedItem("once_date").value = task?.once_date || "";
    form.elements.namedItem("group").value = task?.group || "ME";
    form.elements.namedItem("check").checked = task ? Boolean(task.check) : false;
    form.querySelector(".result").className = "result hidden";
    $("#work-task-dialog")?.showModal();
  }

  async function saveWorkTask(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      await api("/api/admin/work-tasks", { method: "POST", body: JSON.stringify({
        task_id: data.task_id,
        ten_cong_viec: data.ten_cong_viec,
        type: data.type,
        time: data.time,
        weekday: data.weekday || "",
        once_date: data.once_date || "",
        group: data.group || "",
        check: form.check.checked,
      })});
      form.reset();
      form.elements.namedItem("task_id").readOnly = true;
      form.elements.namedItem("type").value = "Daily";
      form.elements.namedItem("time").value = "07:00";
      form.elements.namedItem("group").value = "ME";
      $("#work-task-dialog")?.close();
      showMessage($("#work-tasks-message"), "Đã lưu công việc.");
      showToast("Đã lưu lịch công việc.");
      await loadWorkTasks({ force: true });
    } catch (error) {
      showMessage(form.querySelector(".result"), error.message, "error");
      showToast(error.message, "error");
    }
  }

  async function completeWorkTask(taskId) {
    if (!confirm(`Xác nhận đã hoàn thành ${taskId}? Lịch này sẽ được tắt và ẩn khỏi danh sách.`)) return;
    try {
      const result = await api(`/api/admin/work-tasks/${encodeURIComponent(taskId)}/complete`, { method: "POST" });
      showMessage($("#work-tasks-message"), result.message || "Đã hoàn thành công việc.");
      await loadWorkTasks({ force: true });
    } catch (error) {
      showMessage($("#work-tasks-message"), error.message, "error");
    }
  }

  async function deleteWorkTask(taskId) {
    if (!confirm(`Xóa lịch công việc ${taskId}?`)) return;
    try {
      await api(`/api/admin/work-tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
      showMessage($("#work-tasks-message"), `Đã xóa lịch ${taskId}.`);
      await loadWorkTasks({ force: true });
    } catch (error) {
      showMessage($("#work-tasks-message"), error.message, "error");
    }
  }

  function bindWorkTaskEvents() {
    if (eventsBound) return;
    eventsBound = true;
    $("#work-task-form")?.addEventListener("submit", saveWorkTask);
    $("#save-work-task-button")?.addEventListener("click", () => $("#work-task-form")?.requestSubmit());
  }

  bindWorkTaskEvents();
  window.VNPTWorkTasks = { loadWorkTasks, openWorkTask };
})();
