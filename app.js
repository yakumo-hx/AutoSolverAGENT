const fallbackState = {
  mode: "static_replay",
  status: "READY",
  pending_version: "v155_retarget_loww_swap",
  best: { version: "v149_probe_tiny_budget400k", average: 712.5276, completed: "10/10" },
  latest_result: { version: "v153_scarce_loww_boost", average: 717.33, completed: "10/10", decision: "not_better" },
  latest_cases: {},
  score_series: [
    { version: "v1_baseline", average: 911.4898, decision: "baseline", completed: "10/10" },
    { version: "v149_probe_tiny_budget400k", average: 712.5276, decision: "best", completed: "10/10" },
    { version: "v151_clean_multi_guard", average: 713.17, decision: "not_better", completed: "10/10" },
    { version: "v152_fix_scarce_entry", average: 716.98, decision: "not_better", completed: "10/10" },
    { version: "v153_scarce_loww_boost", average: 717.33, decision: "not_better", completed: "10/10" },
  ],
  timeline: [],
  recent_reflections: [],
  pending_solver_code: "",
  best_solver_code: "",
  score_analysis: { delta_vs_best: 4.8024, worst_cases: [] },
};

const fallbackMonitor = { latest_run_id: "", runs: [] };
const assets = window.PIXEL_ASSETS || {};
const els = {
  bestStat: document.querySelector("#bestStat"),
  latestStat: document.querySelector("#latestStat"),
  runStat: document.querySelector("#runStat"),
  stateStat: document.querySelector("#stateStat"),
  sceneMessage: document.querySelector("#sceneMessage"),
  scaleBar: document.querySelector("#scaleBar"),
  scaleText: document.querySelector("#scaleText"),
  ledgerList: document.querySelector("#ledgerList"),
  fairy: document.querySelector("#fairy"),
  fairyArt: document.querySelector("#fairyArt"),
  coinArt: document.querySelector("#coinArt"),
  playButton: document.querySelector("#playButton"),
  stepButton: document.querySelector("#stepButton"),
  resetButton: document.querySelector("#resetButton"),
  stepDots: document.querySelector("#stepDots"),
  pendingVersion: document.querySelector("#pendingVersion"),
  completedCases: document.querySelector("#completedCases"),
  errorStatus: document.querySelector("#errorStatus"),
  deltaStat: document.querySelector("#deltaStat"),
  reflectionBox: document.querySelector("#reflectionBox"),
  scoreChart: document.querySelector("#scoreChart"),
  versionTimeline: document.querySelector("#versionTimeline"),
  caseRows: document.querySelector("#caseRows"),
  dsStatus: document.querySelector("#dsStatus"),
  dsElapsed: document.querySelector("#dsElapsed"),
  dsFirst: document.querySelector("#dsFirst"),
  dsChunks: document.querySelector("#dsChunks"),
  dsEvents: document.querySelector("#dsEvents"),
  showCandidate: document.querySelector("#showCandidate"),
  showBest: document.querySelector("#showBest"),
  copySolver: document.querySelector("#copySolver"),
  solverText: document.querySelector("#solverText"),
};

const app = {
  state: fallbackState,
  monitor: fallbackMonitor,
  steps: [],
  index: 0,
  timer: null,
  fairyFrame: 0,
  showing: "candidate",
};

function fmtScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(2);
}

function fmtMs(value) {
  if (value === null || value === undefined || value === "") return "--";
  return `${Math.round(Number(value))}ms`;
}

function fmtDuration(ms) {
  if (!ms && ms !== 0) return "--";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function readJson(path, fallback) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  } catch {
    return fallback;
  }
}

function renderPixelArt(node, sprite, cols) {
  if (!node || !sprite?.rows) return;
  node.innerHTML = "";
  node.style.gridTemplateColumns = `repeat(${cols || sprite.rows[0].length}, 1fr)`;
  for (const row of sprite.rows) {
    for (const key of row) {
      const cell = document.createElement("span");
      if (key !== ".") cell.style.background = sprite.palette[key] || "transparent";
      node.appendChild(cell);
    }
  }
}

function startFairy() {
  if (!assets.fairy?.frames) return;
  window.setInterval(() => {
    const rows = assets.fairy.frames[app.fairyFrame % assets.fairy.frames.length];
    renderPixelArt(els.fairyArt, { palette: assets.fairy.palette, rows }, 16);
    app.fairyFrame += 1;
  }, 220);
  if (assets.coin) renderPixelArt(els.coinArt, assets.coin, 8);
  document.querySelectorAll(".basket-art").forEach((node) => {
    const kind = node.dataset.kind;
    renderPixelArt(node, assets.baskets?.[kind], 8);
  });
}

function normalizeDecision(decision) {
  if (["best", "baseline", "accepted", "accepted_then_preserved", "accepted_then_superseded"].includes(decision)) {
    return "accepted";
  }
  if (decision === "not_better" || decision === "rejected") return "not_better";
  return decision || "recorded";
}

function pickBasket(item, index) {
  const version = String(item.version || "").toLowerCase();
  if (version.includes("v1_baseline")) return "memory";
  if (version.includes("151") || version.includes("153") || version.includes("155")) return "repair";
  if (version.includes("152") || version.includes("109")) return "flow";
  return ["memory", "greedy", "flow", "repair"][index % 4];
}

function buildSteps() {
  const timeline = app.state.timeline?.length ? app.state.timeline : app.state.score_series || [];
  const selected = timeline.filter((item) => item.average !== null && item.average !== undefined).slice(-8);
  app.steps = selected.map((item, index) => {
    const decision = normalizeDecision(item.decision);
    return {
      version: item.version,
      score: item.average,
      completed: item.completed,
      decision,
      reason: item.reason || item.decision || "recorded",
      basket: pickBasket(item, index),
      message: `${item.version}: ${fmtScore(item.average)} / ${item.completed || "--"}`,
    };
  });
  const latestRun = [...(app.monitor.runs || [])].reverse().find((run) => run.status === "completed");
  if (latestRun) {
    app.steps.push({
      version: latestRun.id,
      score: app.state.latest_result?.average,
      completed: "DeepSeek",
      decision: "accepted",
      reason: `${latestRun.model} streamed ${latestRun.chunk_count || 0} chunks in ${fmtDuration(latestRun.elapsed_ms)}.`,
      basket: "memory",
      message: `DeepSeek reflection: ${fmtDuration(latestRun.elapsed_ms)} / ${latestRun.model}`,
    });
  }
}

function renderTopStats() {
  const best = app.state.best || {};
  const latest = app.state.latest_result || {};
  const completedRuns = (app.monitor.runs || []).filter((run) => !run.mock_mode && run.status === "completed").length;
  els.bestStat.textContent = fmtScore(best.average);
  els.latestStat.textContent = fmtScore(latest.average);
  els.runStat.textContent = String(completedRuns);
  els.stateStat.textContent = app.state.mode === "static_replay" ? "REPLAY" : app.state.status || "--";
  els.pendingVersion.textContent = app.state.pending_version || "--";
  els.completedCases.textContent = latest.completed || "--";
  els.errorStatus.textContent = latest.has_error_or_timeout ? "YES" : "NO";
  const delta = app.state.score_analysis?.delta_vs_best;
  els.deltaStat.textContent = delta === undefined || delta === null ? "--" : `${delta > 0 ? "+" : ""}${Number(delta).toFixed(4)}`;
}

function renderStepDots() {
  els.stepDots.innerHTML = "";
  app.steps.forEach((_, index) => {
    const dot = document.createElement("span");
    if (index < app.index) dot.className = "done";
    els.stepDots.appendChild(dot);
  });
}

function renderLedger() {
  els.ledgerList.innerHTML = "";
  app.steps.slice(0, app.index).forEach((step) => {
    const li = document.createElement("li");
    li.className = step.decision === "accepted" ? "plus" : "minus";
    li.innerHTML = `<strong>${escapeHtml(step.version)}</strong><small>${escapeHtml(step.reason)}</small>`;
    els.ledgerList.appendChild(li);
  });
}

function moveFairy(target) {
  els.fairy.className = "fairy carrying";
  if (target === "memory") els.fairy.classList.add("to-memory");
  if (target === "greedy") els.fairy.classList.add("to-greedy");
  if (target === "flow") els.fairy.classList.add("to-flow");
  if (target === "repair") els.fairy.classList.add("to-repair");
  if (target === "scale") els.fairy.classList.add("to-scale");
  if (target === "ledger") els.fairy.classList.add("to-ledger");
}

function markBasket(name) {
  document.querySelectorAll(".basket").forEach((node) => {
    node.classList.toggle("active", node.dataset.basket === name);
  });
}

function renderCurrentStep() {
  const step = app.steps[Math.max(0, app.index - 1)];
  if (!step) {
    els.sceneMessage.textContent = "Replay ready. Agent memory is loaded.";
    els.scaleText.textContent = "WAIT";
    els.scaleBar.style.transform = "rotate(0deg)";
    moveFairy("memory");
    markBasket("");
    renderLedger();
    renderStepDots();
    return;
  }
  markBasket(step.basket);
  moveFairy(step.basket);
  window.setTimeout(() => moveFairy("scale"), 520);
  window.setTimeout(() => moveFairy("ledger"), 1040);
  els.sceneMessage.textContent = step.message;
  els.scaleText.textContent = fmtScore(step.score);
  els.scaleBar.style.transform = step.decision === "accepted" ? "rotate(-8deg)" : "rotate(8deg)";
  renderLedger();
  renderStepDots();
}

function stepOnce() {
  if (!app.steps.length) return;
  app.index = Math.min(app.steps.length, app.index + 1);
  renderCurrentStep();
}

function playAll() {
  window.clearInterval(app.timer);
  if (app.index >= app.steps.length) app.index = 0;
  renderCurrentStep();
  app.timer = window.setInterval(() => {
    if (app.index >= app.steps.length) {
      window.clearInterval(app.timer);
      return;
    }
    stepOnce();
  }, 1500);
}

function resetReplay() {
  window.clearInterval(app.timer);
  app.index = 0;
  renderCurrentStep();
}

function renderChart() {
  const series = (app.state.score_series || []).filter((item) => item.average !== null && item.average !== undefined);
  if (!series.length) {
    els.scoreChart.textContent = "--";
    return;
  }
  const width = 760;
  const height = 290;
  const pad = 38;
  const values = series.map((item) => Number(item.average));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const points = series.map((item, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(1, series.length - 1);
    const y = height - pad - ((Number(item.average) - min) * (height - pad * 2)) / span;
    return { x, y, item };
  });
  const poly = points.map((point) => `${point.x},${point.y}`).join(" ");
  const circles = points
    .map((point) => {
      const decision = normalizeDecision(point.item.decision);
      const color = decision === "accepted" ? "var(--green)" : "var(--red)";
      return `<circle cx="${point.x}" cy="${point.y}" r="6" fill="${color}"><title>${escapeHtml(point.item.version)} ${fmtScore(point.item.average)}</title></circle>`;
    })
    .join("");
  const labels = points
    .filter((_, index) => index === 0 || index === points.length - 1 || series[index].decision === "best")
    .map((point) => `<text class="point-label" x="${point.x + 8}" y="${point.y - 8}">${fmtScore(point.item.average)}</text>`)
    .join("");
  els.scoreChart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="score curve">
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#4d5c84" stroke-width="2" />
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#4d5c84" stroke-width="2" />
      <text class="axis-label" x="${pad}" y="22">lower is better</text>
      <polyline points="${poly}" fill="none" stroke="var(--cyan)" stroke-width="4" />
      ${circles}
      ${labels}
    </svg>`;
}

function renderTimeline() {
  const items = app.state.timeline?.length ? app.state.timeline : app.state.score_series || [];
  els.versionTimeline.innerHTML = "";
  items.slice().reverse().forEach((item) => {
    const decision = normalizeDecision(item.decision);
    const card = document.createElement("article");
    card.className = `version-card ${decision}`;
    card.innerHTML = `
      <strong>${escapeHtml(item.version)}</strong>
      <strong>${fmtScore(item.average)}</strong>
      <span>${escapeHtml(item.completed || "--")} / ${escapeHtml(item.decision || "recorded")}</span>
      <span>${escapeHtml(item.reason || "")}</span>`;
    els.versionTimeline.appendChild(card);
  });
}

function renderCases() {
  const cases = app.state.latest_cases || {};
  const rows = Object.entries(cases).sort(([a], [b]) => a.localeCompare(b));
  els.caseRows.innerHTML = "";
  rows.forEach(([name, info]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(name)}</td>
      <td>${fmtScore(info.score)}</td>
      <td>${escapeHtml(info.completion || "--")}</td>
      <td>${fmtMs(info.time_ms)}</td>`;
    els.caseRows.appendChild(tr);
  });
}

function renderReflection() {
  const latestVersion = app.state.latest_result?.version;
  const reflection =
    (app.state.recent_reflections || []).find((item) => item.version === latestVersion) ||
    (app.state.recent_reflections || []).at(-1);
  if (!reflection) {
    els.reflectionBox.textContent = app.state.latest_result?.reason || "--";
    return;
  }
  els.reflectionBox.textContent = reflection.text || reflection.reason || "--";
}

function renderMonitor() {
  const runs = app.monitor.runs || [];
  const latestId = app.monitor.latest_run_id;
  const latest = runs.find((run) => run.id === latestId) || runs.at(-1) || {};
  els.dsStatus.textContent = latest.status || "--";
  els.dsElapsed.textContent = fmtDuration(latest.elapsed_ms);
  els.dsFirst.textContent = fmtDuration(latest.first_token_ms);
  els.dsChunks.textContent = latest.chunk_count ?? "--";
  els.dsEvents.innerHTML = "";
  const eventRows = latest.events?.length ? latest.events : runs.slice(-5).map((run) => ({
    time: run.finished_at || run.started_at,
    status: run.status,
    stage: run.kind,
    message: `${run.id} / ${fmtDuration(run.elapsed_ms)}`,
  }));
  eventRows.slice(-8).forEach((event) => {
    const div = document.createElement("div");
    div.className = `event ${event.status || ""}`;
    div.innerHTML = `<strong>${escapeHtml(event.stage || "event")}</strong> <span>${escapeHtml(event.message || "")}</span>`;
    els.dsEvents.appendChild(div);
  });
}

function renderSolver() {
  const candidate = app.state.pending_solver_code || "";
  const best = app.state.best_solver_code || "";
  els.solverText.value = app.showing === "best" ? best : candidate || best;
}

async function copySolver() {
  const text = els.solverText.value || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    els.solverText.select();
    document.execCommand("copy");
  }
}

function bindEvents() {
  els.playButton.addEventListener("click", playAll);
  els.stepButton.addEventListener("click", stepOnce);
  els.resetButton.addEventListener("click", resetReplay);
  els.showCandidate.addEventListener("click", () => {
    app.showing = "candidate";
    renderSolver();
  });
  els.showBest.addEventListener("click", () => {
    app.showing = "best";
    renderSolver();
  });
  els.copySolver.addEventListener("click", copySolver);
}

async function init() {
  const [stateData, monitorData] = await Promise.all([
    readJson("./data/state.json", fallbackState),
    readJson("./data/ds_monitor.json", fallbackMonitor),
  ]);
  app.state = stateData;
  app.monitor = monitorData;
  startFairy();
  buildSteps();
  bindEvents();
  renderTopStats();
  renderChart();
  renderTimeline();
  renderCases();
  renderReflection();
  renderMonitor();
  renderSolver();
  resetReplay();
}

init();
