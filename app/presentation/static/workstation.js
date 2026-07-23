(() => {
  const app = window.VNPTApp || {};
  const $ = app.$ || ((selector) => document.querySelector(selector));
  const api = app.api;
  const emptyRow = app.emptyRow;
  const escapeHtml = app.escapeHtml || ((value) => String(value ?? ""));
  const isDataFresh = app.isDataFresh || (() => false);
  const loadingRow = app.loadingRow;
  const markDataFresh = app.markDataFresh || (() => {});
  const repairDataEncoding = app.repairDataEncoding || ((value) => value);
  const showMessage = app.showMessage || (() => {});
  let workstationOverview = null;

  async function loadWorkstation({ force = false } = {}) {
    if (!api || !loadingRow || !emptyRow) throw new Error("Module May tram chua san sang.");
    if (!force && isDataFresh("workstation") && workstationOverview) {
      renderWorkstationOverview();
      return;
    }
    const cards = $("#workstation-cards");
    const workers = $("#workstation-workers-table");
    const runs = $("#workstation-runs-table");
    if (cards) cards.innerHTML = loadingRow(1, "Dang tai trang thai may tram...");
    if (workers) workers.innerHTML = loadingRow(5, "Dang tai worker...");
    if (runs) runs.innerHTML = loadingRow(5, "Dang tai task OneBSS...");
    try {
      workstationOverview = repairDataEncoding(await api("/api/admin/workstation/overview"));
      markDataFresh("workstation");
      renderWorkstationOverview();
    } catch (error) {
      showMessage($("#workstation-message"), error.message, "error");
      if (cards) cards.innerHTML = "";
      if (workers) workers.innerHTML = emptyRow(5, "Khong tai duoc trang thai may tram", error.message);
      if (runs) runs.innerHTML = emptyRow(5, "Khong tai duoc task OneBSS", error.message);
    }
  }

  function workstationStatusLabel(status) {
    const value = String(status || "").toLowerCase();
    if (value === "online") return "Online";
    if (value === "recent") return "Moi thay";
    if (value === "offline") return "Offline";
    return "Chua ro";
  }

  function workstationStatusClass(status) {
    const value = String(status || "").toLowerCase();
    if (value === "online") return "success";
    if (value === "recent") return "viewer";
    if (value === "offline") return "disabled";
    return "warning";
  }

  function workstationAgeText(seconds) {
    const value = Number(seconds || 0);
    if (!value) return "-";
    if (value < 60) return `${Math.round(value)} giay truoc`;
    if (value < 3600) return `${Math.round(value / 60)} phut truoc`;
    return `${Math.round(value / 3600)} gio truoc`;
  }

  function workstationIssueCount(config, queue) {
    return [
      !config.internal_api_token_configured,
      Boolean(config.internal_api_mock_mode),
      !config.google_drive_server_configured,
      Number(queue.waiting_otp || 0) > 0,
    ].filter(Boolean).length;
  }

  function renderWorkstationOverview() {
    const data = workstationOverview || {};
    const queue = data.queue || {};
    const config = data.config || {};
    const workers = Array.isArray(data.workers) ? data.workers : [];
    const onlineWorkers = workers.filter((worker) => String(worker.status || "").toLowerCase() === "online").length;
    const cards = [
      ["WS", "Worker online", `${onlineWorkers}/${workers.length || 0}`],
      ["JOB", "OneBSS", `${Number(queue.queued || 0)} cho / ${Number(queue.active || 0)} chay`],
      ["OTP", "Doi OTP", Number(queue.waiting_otp || 0)],
      ["CFG", "Can xu ly", workstationIssueCount(config, queue)],
    ];
    const cardsEl = $("#workstation-cards");
    if (cardsEl) {
      cardsEl.innerHTML = cards
        .map(([icon, label, value]) => `<article class="metric-card"><div class="metric-icon">${escapeHtml(icon)}</div><div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div></article>`)
        .join("");
    }
    renderWorkstationWorkers(data.workers || []);
    renderWorkstationRuns(queue.latest_runs || [], queue.error || "");
    renderWorkstationSetup(data);
    showMessage($("#workstation-message"), "");
  }

  function renderWorkstationWorkers(workers) {
    const table = $("#workstation-workers-table");
    if (!table) return;
    if (!workers.length) {
      table.innerHTML = emptyRow(5, "Chua thay worker online", "Cai bo setup tren may tram de worker tu bao trang thai ve web.");
      return;
    }
    table.innerHTML = workers.map((worker) => `
        <tr>
          <td><code class="compact-code">${escapeHtml(worker.worker_id || "")}</code></td>
          <td><span class="status ${workstationStatusClass(worker.status)}">${escapeHtml(workstationStatusLabel(worker.status))}</span></td>
          <td>${escapeHtml(workstationAgeText(worker.last_seen_age_seconds))}<small class="cell-note">${escapeHtml(worker.last_seen_at || "")}</small></td>
          <td>${escapeHtml(worker.last_task_report || "-")}<small class="cell-note">${escapeHtml(worker.last_task_status || "")}</small></td>
          <td>${escapeHtml(worker.message || worker.last_task_message || "-")}</td>
        </tr>
    `).join("");
  }

  function renderWorkstationRuns(runs, errorMessage = "") {
    const table = $("#workstation-runs-table");
    if (!table) return;
    if (errorMessage) {
      table.innerHTML = emptyRow(5, "Chua doc duoc task OneBSS", errorMessage);
      return;
    }
    if (!runs.length) {
      table.innerHTML = emptyRow(5, "Chua co task OneBSS", "Task gan nhat se hien tai day khi web bat dau dao du lieu.");
      return;
    }
    table.innerHTML = runs.map((run) => `
      <tr>
        <td>${escapeHtml(run.updated_at || "")}</td>
        <td>${escapeHtml(run.report || "")}</td>
        <td><span class="status viewer">${escapeHtml(run.status || "")}</span></td>
        <td>${escapeHtml(run.worker_id || "-")}</td>
        <td>${escapeHtml(run.message || "-")}</td>
      </tr>
    `).join("");
  }

  function renderWorkstationSetup(data) {
    const setup = data.setup || {};
    const config = data.config || {};
    const packageLink = $("#workstation-setup-package");
    if (packageLink) packageLink.href = setup.package_url || "/api/admin/workstation/setup-package";
    const panel = $("#workstation-admin-panel");
    if (panel) {
      const checks = [
        ["Token worker", config.internal_api_token_configured, "Dung de nhan task va gui heartbeat."],
        ["API du lieu", !config.internal_api_mock_mode, config.internal_api_mock_mode ? "Dang o che do mock." : config.internal_api_url || ""],
        ["Google Drive", config.google_drive_server_configured, "Dung cho upload file ket qua."],
        ["Bo cai", true, setup.script_name || "SETUP_VNPTCTO_WORKSTATION.bat"],
      ];
      panel.innerHTML = checks.map(([label, ok, note]) => `
        <div class="workstation-admin-row">
          <span class="status ${ok ? "success" : "warning"}">${ok ? "OK" : "Can cau hinh"}</span>
          <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(note || "")}</small></div>
        </div>
      `).join("");
    }
    const tasks = $("#workstation-task-list");
    if (tasks) {
      const taskNames = Array.isArray(setup.task_names) ? setup.task_names : [];
      tasks.innerHTML = taskNames.slice(0, 4).map((task) => `<span class="status viewer">${escapeHtml(task)}</span>`).join("");
    }
  }

  window.VNPTWorkstation = { loadWorkstation };
})();
