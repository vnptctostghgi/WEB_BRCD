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
  let workstationTestResults = {};

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
    if (workers) workers.innerHTML = loadingRow(7, "Dang tai worker...");
    if (runs) runs.innerHTML = loadingRow(5, "Dang tai task OneBSS...");
    try {
      workstationOverview = repairDataEncoding(await api("/api/admin/workstation/overview"));
      markDataFresh("workstation");
      renderWorkstationOverview();
    } catch (error) {
      showMessage($("#workstation-message"), error.message, "error");
      if (cards) cards.innerHTML = "";
      if (workers) workers.innerHTML = emptyRow(7, "Khong tai duoc trang thai may tram", error.message);
      if (runs) runs.innerHTML = emptyRow(5, "Khong tai duoc task OneBSS", error.message);
    }
  }

  function workstationStatusLabel(status) {
    const value = String(status || "").toLowerCase();
    if (value === "online") return "Online";
    if (value === "recent") return "Moi thay";
    if (value === "offline") return "Offline";
    if (value === "disabled") return "Da tat";
    return "Chua ro";
  }

  function workstationStatusClass(status) {
    const value = String(status || "").toLowerCase();
    if (value === "online") return "success";
    if (value === "recent") return "viewer";
    if (value === "offline") return "disabled";
    if (value === "disabled") return "disabled";
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
    const setupMissing = Array.isArray(config.one_click_setup_missing_items)
      ? config.one_click_setup_missing_items.length
      : [
          !config.internal_api_token_configured,
          Boolean(config.internal_api_mock_mode),
          !config.google_drive_oauth_ready,
          !config.oracle_config_ready,
        ].filter(Boolean).length;
    return setupMissing + (Number(queue.waiting_otp || 0) > 0 ? 1 : 0);
  }

  function renderWorkstationOverview() {
    const data = workstationOverview || {};
    const queue = data.queue || {};
    const config = data.config || {};
    const workers = Array.isArray(data.workers) ? data.workers : [];
    const onlineWorkers = workers.filter((worker) => String(worker.status || "").toLowerCase() === "online").length;
    const cards = [
      ["WS", "Worker online", `${onlineWorkers}/${workers.length || 0}`],
      ["JOB", "Task nen", `${Number(queue.queued || 0)} cho / ${Number(queue.active || 0)} chay`],
      ["OTP", "Doi OTP", Number(queue.waiting_otp || 0)],
      ["SET", "Bo cai", config.one_click_setup_ready ? "San sang" : `${workstationIssueCount(config, queue)} viec`],
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
      table.innerHTML = emptyRow(7, "Chua thay worker online", "Cai bo setup tren may tram de worker tu bao trang thai ve web.");
      return;
    }
    table.innerHTML = workers.map((worker) => `
        <tr>
          <td>
            <input class="workstation-inline-input" data-workstation-field="display_name" data-worker-id="${escapeHtml(worker.worker_id || "")}" value="${escapeHtml(worker.display_name || worker.worker_id || "")}" aria-label="Ten may tram">
            <small class="cell-note"><code class="compact-code">${escapeHtml(worker.worker_id || "")}</code></small>
          </td>
          <td>
            <input class="workstation-priority-input" type="number" min="1" max="999" step="1" data-workstation-field="priority" data-worker-id="${escapeHtml(worker.worker_id || "")}" value="${escapeHtml(String(worker.priority || 100))}" aria-label="Uu tien">
          </td>
          <td><span class="status ${workstationStatusClass(worker.status)}">${escapeHtml(workstationStatusLabel(worker.status))}</span></td>
          <td>${escapeHtml(workstationAgeText(worker.last_seen_age_seconds))}<small class="cell-note">${escapeHtml(worker.last_seen_at || "")}</small></td>
          <td>${escapeHtml(worker.last_task_report || "-")}<small class="cell-note">${escapeHtml(worker.last_task_status || "")}</small></td>
          <td>
            ${escapeHtml(worker.message || worker.last_task_message || "-")}
            <small class="cell-note">${escapeHtml([worker.version || "", ...(Array.isArray(worker.roles) ? worker.roles : [])].filter(Boolean).join(" - ") || "Chua ro phien ban/role")}</small>
            ${renderWorkstationTestResult(worker.worker_id)}
          </td>
          <td class="table-actions">
            <button class="btn-secondary btn-compact" type="button" data-workstation-action="test" data-worker-id="${escapeHtml(worker.worker_id || "")}">Test</button>
            <button class="btn-secondary btn-compact" type="button" data-workstation-action="save" data-worker-id="${escapeHtml(worker.worker_id || "")}">Luu</button>
            <button class="btn-danger btn-compact" type="button" data-workstation-action="delete" data-worker-id="${escapeHtml(worker.worker_id || "")}">Xoa</button>
          </td>
        </tr>
    `).join("");
  }

  function renderWorkstationTestResult(workerId) {
    const result = workstationTestResults[workerId];
    if (!result) return "";
    const checks = Array.isArray(result.checks) ? result.checks : [];
    const chips = checks.map((check) => {
      const cls = check.status === "ok" ? "success" : (check.status === "warning" ? "warning" : "disabled");
      return `<span class="status ${cls}" title="${escapeHtml(check.message || "")}">${escapeHtml(check.label || check.code || "")}</span>`;
    }).join("");
    return `<div class="workstation-test-result"><strong>${escapeHtml(result.message || "")}</strong><div class="workstation-task-list">${chips}</div></div>`;
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
      const missingItems = Array.isArray(config.one_click_setup_missing_items) ? config.one_click_setup_missing_items : [];
      const setupReady = Boolean(config.one_click_setup_ready);
      const setupMessage = config.one_click_setup_message || (
        setupReady
          ? "Bo cai da co san cau hinh. Tai ve may tram va chay mot lan."
          : `Bo cai chua san sang: ${missingItems.join(", ") || "thieu cau hinh tren web"}.`
      );
      const driveNote = config.google_drive_oauth_ready
        ? `Drive ${config.google_drive_folder_id || ""}`.trim()
        : "Drive chua san sang tren web.";
      const oracleNote = config.oracle_config_ready
        ? "Oracle da co trong bo cai."
        : "Oracle chua san sang tren web.";
      const checks = [
        ["Bo cai mot lan", setupReady, setupMessage],
        ["Oracle dong bo", config.oracle_config_ready, oracleNote],
        ["Thu muc Drive", config.google_drive_oauth_ready, driveNote],
      ];
      panel.innerHTML = checks.map(([label, ok, note]) => `
        <div class="workstation-admin-row">
          <span class="status ${ok ? "success" : "warning"}">${ok ? "OK" : "Chua san sang"}</span>
          <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(note || "")}</small></div>
        </div>
      `).join("");
    }
    const tasks = $("#workstation-task-list");
    if (tasks) {
      const taskNames = Array.isArray(setup.task_names) ? setup.task_names : [];
      tasks.innerHTML = [
        setup.script_name || "SETUP_VNPTCTO_WORKSTATION.bat",
        `v${setup.package_version || ""}`,
        ...taskNames.slice(0, 2),
      ].filter(Boolean).map((task) => `<span class="status viewer">${escapeHtml(task)}</span>`).join("");
    }
  }

  function findWorkstationInput(workerId, field) {
    if (!window.CSS?.escape) {
      return document.querySelector(`[data-workstation-field="${field}"][data-worker-id="${workerId.replace(/"/g, '\\"')}"]`);
    }
    return document.querySelector(`[data-workstation-field="${field}"][data-worker-id="${CSS.escape(workerId)}"]`);
  }

  async function handleWorkstationAction(event) {
    const button = event.target.closest("[data-workstation-action]");
    if (!button || !api) return;
    const action = button.dataset.workstationAction;
    const workerId = button.dataset.workerId || "";
    if (!workerId) return;
    try {
      button.disabled = true;
      if (action === "test") {
        workstationTestResults[workerId] = repairDataEncoding(await api(`/api/admin/workstation/${encodeURIComponent(workerId)}/test`, { method: "POST" }));
        renderWorkstationOverview();
        showMessage($("#workstation-message"), workstationTestResults[workerId].message || "Da test may tram.", workstationTestResults[workerId].ok ? "success" : "error");
      } else if (action === "save") {
        const nameInput = findWorkstationInput(workerId, "display_name");
        const priorityInput = findWorkstationInput(workerId, "priority");
        await api("/api/admin/workstation/profile", {
          method: "POST",
          body: JSON.stringify({
            worker_id: workerId,
            display_name: nameInput?.value || workerId,
            priority: Number(priorityInput?.value || 100),
            enabled: true,
          }),
        });
        showMessage($("#workstation-message"), "Da luu ten va uu tien may tram.");
        await loadWorkstation({ force: true });
      } else if (action === "delete") {
        if (!window.confirm(`Xoa may tram ${workerId}? May nay se khong duoc nhan task nua neu con chay worker.`)) return;
        await api(`/api/admin/workstation/${encodeURIComponent(workerId)}`, { method: "DELETE" });
        delete workstationTestResults[workerId];
        showMessage($("#workstation-message"), "Da xoa may tram khoi danh sach.");
        await loadWorkstation({ force: true });
      }
    } catch (error) {
      showMessage($("#workstation-message"), error.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", handleWorkstationAction);

  window.VNPTWorkstation = { loadWorkstation };
})();
