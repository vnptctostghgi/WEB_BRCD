const $ = (selector) => document.querySelector(selector);

const navFeatureConfig = {
  quanlycongviec: { view: "work-tasks", icon: "list", keywords: "quan ly cong viec task lich telegram nhac viec" },
  taikhoanweb: { view: "vault", icon: "vault", keywords: "tai khoan web mat khau" },
  quantringuoidung: { view: "users", icon: "users", keywords: "quan tri nguoi dung user" },
  quantrimenu: { view: "menu-admin", icon: "list", keywords: "quan tri menu sap xep di chuyen module" },
  quantridanhmuc: { view: "catalogs", icon: "list", keywords: "quan tri danh muc phan vung vai tro bien" },
  quantriketnoi: { view: "system", icon: "plug", keywords: "quan tri ket noi api db ftp drive telegram zalo email" },
  internalemail: { view: "internal-email", icon: "audit", keywords: "mail email noi bo imap otp webmail email.vnpt.vn" },
  mobilegateway: { view: "mobile-gateway", icon: "database", keywords: "mobile gateway sms otp android onebss" },
  maytram: { view: "workstation", icon: "database", keywords: "may tram workstation onebss sql export excel redis queue backup drive scheduler" },
  phanquyennguoidung: { view: "permissions", icon: "shield", keywords: "phan quyen nguoi dung chuc nang" },
  phanquyendulieunguoidung: { view: "data-permissions", icon: "database", keywords: "phan quyen du lieu phan vung" },
  nhatkyhoatdong: { view: "audit", icon: "audit", keywords: "nhat ky audit log" },
  truyvansql: { view: "reports", icon: "chart", keywords: "truy van sql bao cao thong ke bieu do" },
  thietkelayoutbaocao: { view: "dashboard-builder", icon: "chart", keywords: "dashboard builder thiet ke layout bao cao tab bieu do" },
  daodulieuonebss: { view: "onebss-mining", icon: "database", keywords: "dao du lieu onebss bao cao excel" },
  linkbaocao: { view: "report-links", icon: "download", keywords: "link bao cao google drive sheet doc slides pdf copy tai xuong" },
  publicmessages: { view: "public-messages", icon: "audit", keywords: "noi dung public sms email otp copy" },
};

const navGroupOnlyFeatureCodes = new Set(["dashboard", "baocaomoi"]);
const navGroupIcons = {
  quantriweb: "shield",
  quantridanhmuc: "list",
  quantriketnoi: "plug",
  taikhoanweb: "vault",
  dashboard: "dashboard",
  truyvansql: "chart",
  baocaomoi: "chart",
};

let dashboardFeatureCodes = new Set();
let dashboardPageIdByFeatureCode = new Map();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[character]));
}

async function api(url, options = {}) {
  const hasJsonBody = options.body !== undefined && !(options.body instanceof FormData);
  const response = await fetch(url, {
    ...options,
    headers: options.body instanceof FormData
      ? (options.headers || {})
      : { ...(hasJsonBody ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  const text = await response.text();
  const body = text.trim() ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(body.detail || "Request failed.");
  return body;
}

function featurePathFromCode(code) {
  const normalized = String(code || "").trim().replace(/^\/+|\/+$/g, "");
  return normalized ? `/${encodeURIComponent(normalized)}` : "/";
}

function syncSidebarExpandedState(open) {
  const sidebar = $("#sidebar");
  const button = $("#menu-button");
  if (!sidebar || !button) return;
  sidebar.classList.toggle("menu-open", open);
  button.setAttribute("aria-expanded", String(open));
  if (window.matchMedia("(min-width: 1024px)").matches) {
    localStorage.setItem("sidebarExpanded", open ? "true" : "false");
  }
}

$("#menu-button")?.addEventListener("click", () => {
  syncSidebarExpandedState(!$("#sidebar")?.classList.contains("menu-open"));
});

if (localStorage.getItem("sidebarExpanded") === "true" && window.matchMedia("(min-width: 1024px)").matches) {
  syncSidebarExpandedState(true);
}

function filterNavigation(keyword) {
  const query = String(keyword || "").trim().toLowerCase();
  let visibleItems = 0;
  document.querySelectorAll(".nav-group").forEach((group) => {
    let groupHasVisibleChild = false;
    group.querySelectorAll(".nav-item").forEach((item) => {
      const text = `${item.textContent} ${item.dataset.keywords || ""}`.toLowerCase();
      const visible = !query || text.includes(query);
      item.classList.toggle("hidden-by-search", !visible);
      if (visible) {
        groupHasVisibleChild = true;
        visibleItems += 1;
      }
    });
    group.classList.toggle("hidden-by-search", !groupHasVisibleChild);
    if (query && groupHasVisibleChild) group.open = true;
  });
  document.querySelectorAll("#nav-tree > .nav-item").forEach((item) => {
    const text = `${item.textContent} ${item.dataset.keywords || ""}`.toLowerCase();
    const visible = !query || text.includes(query);
    item.classList.toggle("hidden-by-search", !visible);
    if (visible) visibleItems += 1;
  });
  $("#nav-empty")?.classList.toggle("hidden", visibleItems > 0);
}

$("#menu-search")?.addEventListener("input", (event) => filterNavigation(event.currentTarget.value));

function featureSortValue(feature) {
  return Number(feature.sort_order ?? 0);
}

function buildFeatureTree(sourceFeatures) {
  const nodes = new Map(sourceFeatures.map((feature) => [feature.code, { feature, children: [] }]));
  const roots = [];
  nodes.forEach((node) => {
    const parent = node.feature.parent_code ? nodes.get(node.feature.parent_code) : null;
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  });
  const sortNodes = (items) => {
    items.sort((left, right) => (
      featureSortValue(left.feature) - featureSortValue(right.feature)
      || String(left.feature.name || "").localeCompare(String(right.feature.name || ""), "vi")
      || String(left.feature.code).localeCompare(String(right.feature.code))
    ));
    items.forEach((item) => sortNodes(item.children));
    return items;
  };
  return sortNodes(roots);
}

function dashboardFeatureCodeForPageId(pageId) {
  const compact = String(pageId || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (compact === "dashboardkinhdoanh") return "dashboard";
  if (compact === "reports") return "truyvansql";
  return compact || "dashboard";
}

function applyDashboardLayoutList(layouts = []) {
  const pageEntries = [];
  (Array.isArray(layouts) ? layouts : []).forEach((layout) => {
    const pageId = layout.page_id || "";
    const compactCode = dashboardFeatureCodeForPageId(pageId);
    const underscoreCode = String(pageId).trim().toLowerCase();
    if (compactCode && pageId) pageEntries.push([compactCode, pageId]);
    if (underscoreCode && pageId) pageEntries.push([underscoreCode, pageId]);
  });
  dashboardPageIdByFeatureCode = new Map(pageEntries);
  dashboardFeatureCodes = new Set(dashboardPageIdByFeatureCode.keys());
}

function dashboardPageIdFromFeatureCode(code) {
  if (code === "dashboard") return "DASHBOARD_KINH_DOANH";
  const mappedPageId = dashboardPageIdByFeatureCode.get(code);
  if (mappedPageId) return mappedPageId;
  return String(code || "").replace(/[^A-Za-z0-9]+/g, "").toUpperCase() || "DASHBOARD_KINH_DOANH";
}

function featureNavigationConfig(feature) {
  if (navGroupOnlyFeatureCodes.has(feature.code)) return null;
  const staticConfig = navFeatureConfig[feature.code];
  if (staticConfig) return staticConfig;
  const dashboardPageId = dashboardPageIdFromFeatureCode(feature.code);
  if (feature.parent_code === "truyvansql" || feature.parent_code === "reports" || dashboardFeatureCodes.has(feature.code)) {
    return {
      view: "dashboard",
      icon: "chart",
      keywords: `dashboard bao cao thong ke ${feature.name || ""} ${feature.code || ""}`,
      dashboardPageId,
    };
  }
  return null;
}

function featureIcon(feature) {
  return featureNavigationConfig(feature)?.icon || navGroupIcons[feature.code] || "list";
}

function iconMarkup(icon) {
  return `<svg class="nav-svg"><use href="#icon-${escapeHtml(icon)}"></use></svg>`;
}

function navNodeHasVisibleItem(node) {
  if (navGroupOnlyFeatureCodes.has(node.feature.code)) return true;
  if (featureNavigationConfig(node.feature)?.view) return true;
  return node.children.some((child) => navNodeHasVisibleItem(child));
}

function renderNavigationButton(feature, level) {
  const config = featureNavigationConfig(feature);
  if (!config?.view) return "";
  const classes = ["nav-item"];
  if (level > 0) classes.push("child");
  if (level > 1) classes.push("subchild");
  const title = feature.name || feature.code;
  const keywords = `${config.keywords || ""} ${feature.name || ""} ${feature.code}`;
  const dashboardPageAttr = config.dashboardPageId ? ` data-dashboard-page-id="${escapeHtml(config.dashboardPageId)}"` : "";
  return `
    <button class="${classes.join(" ")}" data-feature-code="${escapeHtml(feature.code)}" data-view="${escapeHtml(config.view)}" data-title="${escapeHtml(title)}" data-keywords="${escapeHtml(keywords)}"${dashboardPageAttr}>
      ${iconMarkup(config.icon || "list")}<span>${escapeHtml(title)}</span>
    </button>
  `;
}

function renderNavigationNode(node, level = 0) {
  const visibleChildren = node.children.filter((child) => navNodeHasVisibleItem(child));
  if (!visibleChildren.length && navGroupOnlyFeatureCodes.has(node.feature.code)) {
    const groupClass = `nav-group${level > 0 ? " nav-subgroup" : ""}`;
    return `
      <details class="${groupClass}">
        <summary data-feature-code="${escapeHtml(node.feature.code)}">
          <span class="chevron">&rsaquo;</span>${iconMarkup(featureIcon(node.feature))}<strong>${escapeHtml(node.feature.name || node.feature.code)}</strong>
        </summary>
      </details>
    `;
  }
  if (!visibleChildren.length) return renderNavigationButton(node.feature, level);
  const groupClass = `nav-group${level > 0 ? " nav-subgroup" : ""}`;
  const children = visibleChildren.map((child) => renderNavigationNode(child, level + 1)).join("");
  return `
    <details class="${groupClass}">
      <summary data-feature-code="${escapeHtml(node.feature.code)}">
        <span class="chevron">&rsaquo;</span>${iconMarkup(featureIcon(node.feature))}<strong>${escapeHtml(node.feature.name || node.feature.code)}</strong>
      </summary>
      ${children}
    </details>
  `;
}

async function syncNavigationFromFeatures() {
  try {
    const navigationData = await api("/api/navigation");
    applyDashboardLayoutList(navigationData.dashboard_layouts || []);
    const tree = $("#nav-tree");
    if (!tree) return;
    const html = buildFeatureTree(navigationData.features || [])
      .filter((node) => navNodeHasVisibleItem(node))
      .map((node) => renderNavigationNode(node))
      .join("");
    if (html.trim()) tree.innerHTML = html;
    filterNavigation($("#menu-search")?.value || "");
  } catch {
    filterNavigation($("#menu-search")?.value || "");
  } finally {
    document.body.classList.remove("app-booting", "view-loading");
    document.body.classList.add("app-shell-idle");
  }
}

$("#nav-tree")?.addEventListener("click", (event) => {
  const item = event.target.closest(".nav-item[data-feature-code]");
  if (!item || !$("#nav-tree")?.contains(item)) return;
  event.preventDefault();
  syncSidebarExpandedState(false);
  window.location.href = featurePathFromCode(item.dataset.featureCode);
});

function closeTopDropdowns(except = null) {
  ["notification-menu", "user-menu"].forEach((id) => {
    const menu = $(`#${id}`);
    if (menu && menu !== except) menu.classList.add("hidden");
  });
  ["notification-toggle", "user-menu-toggle"].forEach((id) => {
    const button = $(`#${id}`);
    if (button && (except === null || button.getAttribute("aria-controls") !== except?.id)) {
      button.setAttribute("aria-expanded", "false");
    }
  });
}

function toggleTopDropdown(buttonSelector, menuSelector) {
  const button = $(buttonSelector);
  const menu = $(menuSelector);
  if (!button || !menu) return;
  button.setAttribute("aria-controls", menu.id);
  button.addEventListener("click", async (event) => {
    event.stopPropagation();
    const willOpen = menu.classList.contains("hidden");
    closeTopDropdowns(menu);
    menu.classList.toggle("hidden", !willOpen);
    button.setAttribute("aria-expanded", String(willOpen));
    if (willOpen && menu.id === "notification-menu") await loadNotifications();
  });
}

async function loadNotifications() {
  const list = $("#notification-list");
  if (!list) return;
  list.innerHTML = `<div class="dropdown-empty">Dang tai thong bao...</div>`;
  try {
    const data = await api("/api/notifications");
    list.innerHTML = data.notifications?.length ? data.notifications.map((item) => `
      <article class="notification-item">
        <strong>${escapeHtml(item.title)}</strong>
        <p>${escapeHtml(item.message)}</p>
        <small>${new Date(item.created_at).toLocaleString("vi-VN")}</small>
      </article>
    `).join("") : `<div class="dropdown-empty">Chua co thong bao moi.</div>`;
  } catch (error) {
    list.innerHTML = `<div class="dropdown-empty error">${escapeHtml(error.message)}</div>`;
  }
}

toggleTopDropdown("#notification-toggle", "#notification-menu");
toggleTopDropdown("#user-menu-toggle", "#user-menu");

document.addEventListener("click", (event) => {
  if (!event.target.closest(".dropdown-wrap")) closeTopDropdowns();
});

document.querySelectorAll("[data-open-dialog]").forEach((button) => button.addEventListener("click", () => {
  const dialog = $(`#${button.dataset.openDialog}`);
  if (dialog?.showModal) dialog.showModal();
}));

document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog")?.close());
});

document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
}));

$("#password-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const result = form.querySelector(".result");
  const data = Object.fromEntries(new FormData(form));
  try {
    await api("/api/auth/change-password", { method: "POST", body: JSON.stringify(data) });
    if (result) {
      result.textContent = "Da doi mat khau.";
      result.className = "result success";
    }
    form.closest("dialog")?.close();
  } catch (error) {
    if (result) {
      result.textContent = error.message;
      result.className = "result error";
    }
  }
});

if (["1", "True", "true"].includes(document.body.dataset.mustChange)) {
  const dialog = $("#password-dialog");
  if (dialog && !dialog.open) dialog.showModal();
}

syncNavigationFromFeatures();

function warmFeatureBundle() {
  if (document.querySelector("link[data-feature-bundle-warm='true']")) return;
  const link = document.createElement("link");
  link.rel = "preload";
  link.as = "script";
  link.href = "/static/app.js?v=170";
  link.dataset.featureBundleWarm = "true";
  document.head.appendChild(link);
}

const scheduleIdle = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 1500));
scheduleIdle(warmFeatureBundle, { timeout: 3500 });
