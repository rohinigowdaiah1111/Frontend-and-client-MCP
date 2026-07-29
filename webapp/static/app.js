// Review Pulse Console — frontend logic. Talks only to /api/* on this same origin.

const state = {
  dashboard: null,
  activeCategory: null, // null = all
  lastDocUrl: null,
};

const $ = (id) => document.getElementById(id);

const CATEGORY_COLORS = {
  positive: "#10b981",
  payments: "#ef4444",
  kyc: "#f59e0b",
  onboarding: "#6366f1",
  statements: "#0ea5e9",
  withdrawals: "#a855f7",
  other: "#94a3b8",
};

function colorFor(categoryId) {
  return CATEGORY_COLORS[categoryId] || "#64748b";
}

function logStatus(message, kind = "info") {
  const el = document.createElement("div");
  const styles = {
    info: "text-slate-500",
    success: "text-emerald-600",
    error: "text-red-600",
  };
  el.className = styles[kind] || styles.info;
  const time = new Date().toLocaleTimeString();
  el.textContent = `[${time}] ${message}`;
  $("status-log").prepend(el);
}

class AuthRequiredError extends Error {}

async function apiGet(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (res.status === 401) throw new AuthRequiredError("Login required");
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${path} failed (${res.status})`);
  return data;
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (res.status === 401) throw new AuthRequiredError("Login required");
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${path} failed (${res.status})`);
  return data;
}

function showLogin() {
  $("login-overlay").classList.remove("hidden");
  $("app-main").classList.add("hidden");
}

function hideLogin() {
  $("login-overlay").classList.add("hidden");
  $("app-main").classList.remove("hidden");
  $("logout-btn").classList.remove("hidden");
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = $("login-password").value;
  const errBox = $("login-error");
  errBox.classList.add("hidden");
  try {
    await apiPost("/api/login", { password });
    hideLogin();
    loadDashboard();
  } catch (err) {
    errBox.textContent = "Incorrect password.";
    errBox.classList.remove("hidden");
  }
});

$("logout-btn").addEventListener("click", async () => {
  await apiPost("/api/logout", {}).catch(() => {});
  showLogin();
});

let chartInstance = null;

function renderChart(categories) {
  const ctx = $("category-chart").getContext("2d");
  const labels = categories.map((c) => c.label);
  const counts = categories.map((c) => c.count);
  const colors = categories.map((c) => colorFor(c.id));

  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Reviews", data: counts, backgroundColor: colors, borderRadius: 4 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderPills(categories) {
  const wrap = $("category-pills");
  wrap.innerHTML = "";

  const allPill = document.createElement("span");
  allPill.className = `cat-pill px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 ${state.activeCategory === null ? "active" : ""}`;
  allPill.textContent = `All (${categories.reduce((sum, c) => sum + c.count, 0)})`;
  allPill.onclick = () => { state.activeCategory = null; renderAll(); };
  wrap.appendChild(allPill);

  categories.forEach((c) => {
    const pill = document.createElement("span");
    pill.className = `cat-pill px-3 py-1 rounded-full text-xs font-medium text-white ${state.activeCategory === c.id ? "active" : ""}`;
    pill.style.backgroundColor = colorFor(c.id);
    pill.textContent = `${c.label} (${c.count})`;
    pill.onclick = () => { state.activeCategory = c.id; renderAll(); };
    wrap.appendChild(pill);
  });
}

function renderReviewList(reviews) {
  const filtered = state.activeCategory
    ? reviews.filter((r) => r.category_id === state.activeCategory)
    : reviews;

  $("review-count-label").textContent = `(${filtered.length} of ${reviews.length})`;

  const list = $("review-list");
  list.innerHTML = "";
  if (filtered.length === 0) {
    list.innerHTML = `<div class="py-6 text-sm text-slate-400">No reviews in this category.</div>`;
    return;
  }

  filtered.slice(0, 200).forEach((r) => {
    const row = document.createElement("div");
    row.className = "py-3 flex items-start gap-3";
    const stars = r.rating ? "★".repeat(r.rating) + "☆".repeat(5 - r.rating) : "—";
    row.innerHTML = `
      <span class="mt-0.5 shrink-0 px-2 py-0.5 rounded text-[11px] font-medium text-white" style="background-color:${colorFor(r.category_id)}">${r.category_label}</span>
      <div class="flex-1 min-w-0">
        <div class="text-sm text-slate-800">${escapeHtml(r.text || "(no text)")}</div>
        <div class="text-xs text-slate-400 mt-0.5">${r.store} · ${stars} · ${r.date}</div>
      </div>
    `;
    list.appendChild(row);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderStats(d) {
  $("stat-total").textContent = d.total_reviews ?? 0;
  $("stat-app").textContent = d.by_store?.app_store ?? 0;
  $("stat-play").textContent = d.by_store?.play_store ?? 0;
  const positive = (d.categories || []).find((c) => c.id === "positive");
  $("stat-positive").textContent = positive ? positive.count : 0;
  $("week-badge").textContent = d.week_of ? `Week of ${d.week_of}` : "";

  const note = $("limitation-note");
  if (d.limitation_note) {
    note.textContent = d.limitation_note;
    note.classList.remove("hidden");
  } else {
    note.classList.add("hidden");
  }
}

function renderAll() {
  const d = state.dashboard;
  if (!d) return;
  renderStats(d);
  renderChart(d.categories || []);
  renderPills(d.categories || []);
  renderReviewList(d.reviews || []);
}

async function loadDashboard() {
  try {
    logStatus("Loading reviews from data/raw…");
    const d = await apiGet("/api/dashboard");
    if (d.blocked) {
      logStatus(`Blocked: ${d.block_reason}`, "error");
    }
    state.dashboard = d;
    renderAll();
    logStatus(`Loaded ${d.total_reviews} reviews.`, "success");
  } catch (err) {
    if (err instanceof AuthRequiredError) { showLogin(); return; }
    logStatus(err.message, "error");
  }
}

async function runCompose() {
  const btn = $("compose-btn");
  btn.disabled = true;
  btn.textContent = "Generating…";
  try {
    logStatus("Calling Groq to write the report + email (Phase 4b)…");
    const result = await apiPost("/api/compose");
    $("report-box").value = result.report_markdown || "";
    $("subject-box").value = result.email_subject || "";
    $("message-box").value = result.email_body || "";
    $("to-box").value = state.dashboard?.delivery_gmail_to || $("to-box").value;
    $("compose-panel").classList.remove("hidden");
    logStatus(`Groq report ready (${result.word_count} words, model ${result.model}).`, "success");
  } catch (err) {
    if (err instanceof AuthRequiredError) { showLogin(); return; }
    logStatus(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate report + email (Groq)";
  }
}

async function runPublishDoc() {
  const btn = $("publish-doc-btn");
  btn.disabled = true;
  try {
    logStatus("Publishing report to Google Doc (Phase 5)…");
    const result = await apiPost("/api/deliver/doc", { text: $("report-box").value });
    state.lastDocUrl = result.url;
    logStatus(`Published to Google Doc: ${result.url}`, "success");
  } catch (err) {
    if (err instanceof AuthRequiredError) { showLogin(); return; }
    logStatus(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function runCreateDraft() {
  const btn = $("create-draft-btn");
  btn.disabled = true;
  try {
    logStatus("Creating Gmail draft (Phase 6, draft-only)…");
    const result = await apiPost("/api/deliver/draft", {
      to: $("to-box").value || undefined,
      subject: $("subject-box").value || undefined,
      body: $("message-box").value || undefined,
      doc_url: state.lastDocUrl || undefined,
    });
    logStatus(`Gmail draft created: ${result.server_response}`, "success");
  } catch (err) {
    if (err instanceof AuthRequiredError) { showLogin(); return; }
    logStatus(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

$("refresh-btn").addEventListener("click", loadDashboard);
$("compose-btn").addEventListener("click", runCompose);
$("publish-doc-btn").addEventListener("click", runPublishDoc);
$("create-draft-btn").addEventListener("click", runCreateDraft);

loadDashboard();
