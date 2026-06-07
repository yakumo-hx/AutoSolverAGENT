const fallbackTrace = {
  best_score: 712.5276,
  best_strategy: "memory_reflect",
  steps: [
    {
      step_id: 1,
      strategy: "memory_reflect",
      score: 712.5276,
      valid: true,
      covered: "history",
      accepted: true,
      delta: 0,
      message: "小精灵读取历史 best、失败假设和 case 分数。",
      visual: { ledger_mark: "plus" },
    },
    {
      step_id: 2,
      strategy: "flow_ilp",
      score: 712.5276,
      valid: true,
      covered: "context",
      accepted: true,
      delta: 0,
      message: "小精灵把结构化上下文送进算法篮。",
      visual: { ledger_mark: "plus" },
    },
    {
      step_id: 3,
      strategy: "local_repair",
      score: 712.5276,
      valid: true,
      covered: "solver",
      accepted: true,
      delta: 0,
      message: "候选 Solver 被保存，等待平台打分。",
      visual: { ledger_mark: "plus" },
    },
  ],
};

const fallbackDashboard = {
  status: "READY",
  pending_version: null,
  best: {
    version: "v149_probe_tiny_budget400k",
    average: 712.5276,
    completed: "10/10",
    sha256: "766972C060513589B7D306499AD0828C2B5886181DCC2014F5197A6E0B531423",
  },
  score_series: [
    { version: "v1_test", average: 911.4898, decision: "baseline" },
    { version: "v15_formal_multi2_marginal", average: 719.6302, decision: "accepted_then_superseded" },
    { version: "v109_formal_guarded_triple_regular_only", average: 712.5276, decision: "accepted_then_preserved" },
    { version: "v149_probe_tiny_budget400k", average: 712.5276, decision: "best" },
  ],
  timeline: [],
  latest_cases: {},
  latest_result: {},
  score_analysis: {},
  recent_reflections: [],
  chat: [],
  mock_mode: true,
};

const assets = window.PIXEL_ASSETS;

const strategyMeta = {
  greedy_low_cost: { label: "贪心篮", color: "blue" },
  flow_ilp: { label: "流/ILP篮", color: "green" },
  local_repair: { label: "修复篮", color: "red" },
  memory_reflect: { label: "记忆篮", color: "gold" },
};

const kindToStrategy = {
  memory: "memory_reflect",
  context: "flow_ilp",
  llm: "local_repair",
  solver: "greedy_low_cost",
  human: "memory_reflect",
  pending_reminder: "memory_reflect",
  feedback: "local_repair",
};

const acceptedDecisions = new Set(["accepted", "accepted_then_preserved", "accepted_then_superseded", "best", "baseline"]);

const state = {
  trace: fallbackTrace,
  dashboard: fallbackDashboard,
  index: 0,
  running: false,
  animBest: Number.POSITIVE_INFINITY,
  fairyFrame: 0,
  flapTimer: null,
  lastAgentOutput: null,
  lastRuntime: null,
  deepseekApiKey: "",
  apiReady: false,
  dsMonitorTimer: null,
  lastMonitorId: "",
};

const sceneBoard = document.querySelector("#sceneBoard");
const agentDock = document.querySelector("#agentDock");
const scaleDock = document.querySelector("#scaleDock");
const ledgerDock = document.querySelector("#ledgerDock");
const bestScore = document.querySelector("#bestScore");
const agentState = document.querySelector("#agentState");
const stepCounter = document.querySelector("#stepCounter");
const traceStatus = document.querySelector("#traceStatus");
const playButton = document.querySelector("#playButton");
const nextButton = document.querySelector("#nextButton");
const resetButton = document.querySelector("#resetButton");
const startAgentButton = document.querySelector("#startAgentButton");
const strategyAdviceButton = document.querySelector("#strategyAdviceButton");
const labAgentButton = document.querySelector("#labAgentButton");
const liveAnimButton = document.querySelector("#liveAnimButton");
const demoAnimButton = document.querySelector("#demoAnimButton");
const copySolverButton = document.querySelector("#copySolverButton");
const discardPendingButton = document.querySelector("#discardPendingButton");
const sendFeedbackButton = document.querySelector("#sendFeedbackButton");
const solverOutput = document.querySelector("#solverOutput");
const feedbackInput = document.querySelector("#feedbackInput");
const deepseekTokenInput = document.querySelector("#deepseekTokenInput");
const sessionNotice = document.querySelector("#sessionNotice");
const chatLog = document.querySelector("#chatLog");
const scoreChart = document.querySelector("#scoreChart");
const versionList = document.querySelector("#versionList");
const caseTableBody = document.querySelector("#caseTableBody");
const errorTile = document.querySelector("#errorTile");
const reasonBox = document.querySelector("#reasonBox");
const reflectionBox = document.querySelector("#reflectionBox");
const ledgerList = document.querySelector("#ledgerList");
const message = document.querySelector("#message");
const scaleText = document.querySelector("#scaleText");
const scaleBar = document.querySelector("#scaleBar");
const fairy = document.querySelector("#fairySprite");
const fairyArt = document.querySelector("#fairyArt");
const carriedCoin = document.querySelector("#carriedCoin");
const timeline = document.querySelector("#timeline");
const dsStatus = document.querySelector("#dsStatus");
const dsElapsed = document.querySelector("#dsElapsed");
const dsFirstToken = document.querySelector("#dsFirstToken");
const dsChunks = document.querySelector("#dsChunks");
const dsChars = document.querySelector("#dsChars");
const dsUsage = document.querySelector("#dsUsage");
const dsEvents = document.querySelector("#dsEvents");
const dsPreview = document.querySelector("#dsPreview");

function renderPixelArt(node, sprite) {
  node.innerHTML = "";
  node.style.setProperty("--cols", sprite.rows[0].length);
  for (const row of sprite.rows) {
    for (const key of row) {
      const cell = document.createElement("span");
      if (key !== ".") {
        cell.style.background = sprite.palette[key] || "transparent";
      }
      node.appendChild(cell);
    }
  }
}

function renderFairyFrame() {
  const frame = assets.fairy.frames[state.fairyFrame % assets.fairy.frames.length];
  renderPixelArt(fairyArt, { palette: assets.fairy.palette, rows: frame });
  state.fairyFrame += 1;
}

function startWingFlap() {
  if (state.flapTimer) {
    window.clearInterval(state.flapTimer);
  }
  renderFairyFrame();
  state.flapTimer = window.setInterval(renderFairyFrame, 220);
}

function renderAllPixelArt() {
  startWingFlap();
  renderPixelArt(carriedCoin, assets.coin);
  document.querySelectorAll(".basket-art").forEach((node) => {
    renderBasketArt(node, node.dataset.kind);
  });
}

function renderBasketArt(node, kind) {
  const sprite = assets.baskets[kind];
  node.innerHTML = "";
  for (const row of sprite.rows) {
    for (const key of row) {
      const cell = document.createElement("span");
      if (key !== ".") {
        cell.style.background = sprite.palette[key] || "transparent";
      }
      node.appendChild(cell);
    }
  }
}

function renderInitial() {
  state.index = 0;
  state.animBest = Number.POSITIVE_INFINITY;
  scaleText.textContent = "WAIT";
  scaleBar.style.transform = "rotate(0deg)";
  ledgerList.innerHTML = "";
  fairy.classList.remove("carrying", "accepted", "rejected", "inspecting");
  document.querySelectorAll(".pixel-basket").forEach((node) => node.classList.remove("active"));
  renderTimeline();
  updateStepCounter();
  renderDashboard(state.dashboard);
  requestAnimationFrame(() => moveFairyTo(agentDock, { animate: false, dy: -14 }));
}

function renderTimeline() {
  timeline.innerHTML = "";
  state.trace.steps.forEach((step, index) => {
    const dot = document.createElement("span");
    dot.title = step.message || `step ${index + 1}`;
    timeline.appendChild(dot);
  });
}

function updateStepCounter() {
  stepCounter.textContent = `${state.index}/${state.trace.steps.length}`;
}

function setAnimationControls(disabled) {
  playButton.disabled = disabled;
  nextButton.disabled = disabled;
  resetButton.disabled = disabled;
}

function setAgentControls(disabled) {
  startAgentButton.disabled = disabled;
  strategyAdviceButton.disabled = disabled;
  labAgentButton.disabled = disabled;
  sendFeedbackButton.disabled = disabled;
  copySolverButton.disabled = disabled;
  discardPendingButton.disabled = disabled;
  liveAnimButton.disabled = disabled;
  demoAnimButton.disabled = disabled;
}

function moveFairyTo(target, options = {}) {
  const { animate = true, dx = 0, dy = 0 } = options;
  const boardRect = sceneBoard.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const fairyRect = fairy.getBoundingClientRect();
  const x = targetRect.left - boardRect.left + targetRect.width / 2 - fairyRect.width / 2 + dx;
  const y = targetRect.top - boardRect.top + targetRect.height / 2 - fairyRect.height / 2 + dy;
  if (!animate) {
    const oldTransition = fairy.style.transition;
    fairy.style.transition = "none";
    fairy.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    requestAnimationFrame(() => {
      fairy.style.transition = oldTransition;
    });
    return;
  }
  fairy.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function animateStep(rawStep) {
  const step = normalizeStep(rawStep, state.index);
  setAnimationControls(true);
  const basket = document.querySelector(`.pixel-basket[data-name="${step.strategy}"]`);
  if (!basket) {
    setAnimationControls(false);
    return;
  }

  document.querySelectorAll(".pixel-basket").forEach((node) => node.classList.remove("active"));
  fairy.classList.remove("accepted", "rejected", "inspecting");
  scaleDock.classList.remove("weighing");
  scaleBar.style.transform = "rotate(0deg)";

  message.textContent = "小精灵扇动翅膀，回到工作台领取金币。";
  moveFairyTo(agentDock, { dy: -14 });
  await wait(300);

  fairy.classList.add("carrying");
  message.textContent = `小精灵带着金币飞向 ${strategyLabel(step.strategy)}。`;
  basket.classList.add("active");
  moveFairyTo(basket, { dy: -34 });
  await wait(560);

  message.textContent = "算法篮产出候选信息，小精灵把它送上评分秤。";
  moveFairyTo(scaleDock, { dy: -108 });
  await wait(500);

  fairy.classList.add("inspecting");
  message.textContent = "小精灵飞起来查看 score 和运行风险。";
  scaleDock.classList.add("weighing");
  scaleBar.style.transform = step.accepted ? "rotate(-2deg)" : "rotate(3deg)";
  scaleText.textContent = step.score === null ? String(step.covered || "CHECK") : `SCORE ${formatScore(step.score)}`;
  await wait(540);

  const previousBest = state.animBest;
  if (step.accepted && step.score !== null && step.score < state.animBest) {
    state.animBest = step.score;
  }

  message.textContent = "小精灵飞到长期记账本，写下本轮判断。";
  fairy.classList.remove("inspecting");
  fairy.classList.add(step.accepted ? "accepted" : "rejected");
  moveFairyTo(ledgerDock, { dy: -112 });
  await wait(520);

  appendLedger(step, previousBest);
  fairy.classList.remove("carrying");
  await wait(180);

  message.textContent = step.message;
  markTimeline(step);
  state.index += 1;
  updateStepCounter();
  setAnimationControls(false);
}

function appendLedger(step, previousBest) {
  const li = document.createElement("li");
  li.className = step.accepted ? "plus" : "minus";

  const mark = document.createElement("span");
  mark.className = "mark";
  mark.textContent = step.accepted ? "+" : "-";

  const body = document.createElement("span");
  body.textContent = `${step.step_id}. ${strategyLabel(step.strategy)} / ${step.covered || "agent"}`;

  const score = document.createElement("span");
  score.className = "score";
  if (step.score === null) {
    score.textContent = step.accepted ? "KEEP" : "CHECK";
  } else {
    const deltaText = Number.isFinite(previousBest) ? signed(step.score - previousBest) : "FIRST";
    score.textContent = `${formatScore(step.score)} ${deltaText}`;
  }

  li.append(mark, body, score);
  ledgerList.appendChild(li);
  ledgerList.scrollTop = ledgerList.scrollHeight;
}

function markTimeline(step) {
  const dot = timeline.children[step.step_id - 1];
  if (!dot) {
    return;
  }
  dot.classList.add("done", step.accepted ? "plus" : "minus");
}

function strategyLabel(name) {
  return strategyMeta[name]?.label || name;
}

function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toFixed(4);
}

function signed(value) {
  if (Math.abs(value) < 0.0005) {
    return "+0.0000";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(4)}`;
}

async function runNext() {
  if (state.running || state.index >= state.trace.steps.length) {
    return;
  }
  state.running = true;
  await animateStep(state.trace.steps[state.index]);
  state.running = false;
}

async function playAll() {
  if (state.running) {
    return;
  }
  while (state.index < state.trace.steps.length) {
    await runNext();
    await wait(140);
  }
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const body = withRuntime(payload || {});
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${url} ${response.status}`);
  }
  return response.json();
}

function withRuntime(payload) {
  const body = { ...payload, deepseek_model: "deepseek-v4-flash" };
  if (state.deepseekApiKey) {
    body.deepseek_api_key = state.deepseekApiKey;
  }
  return body;
}

async function refreshDeepSeekMonitor() {
  if (!state.apiReady) {
    return "";
  }
  try {
    const data = await getJson("/api/ds_monitor");
    renderDeepSeekMonitor(data);
    return data.latest?.status || "";
  } catch (_err) {
    return "";
  }
}

function startDeepSeekMonitorPolling() {
  if (state.dsMonitorTimer) {
    window.clearInterval(state.dsMonitorTimer);
  }
  let finalTicks = 0;
  refreshDeepSeekMonitor();
  state.dsMonitorTimer = window.setInterval(async () => {
    const status = await refreshDeepSeekMonitor();
    if (["completed", "error", "mock"].includes(status)) {
      finalTicks += 1;
    } else {
      finalTicks = 0;
    }
    if (finalTicks >= 4) {
      window.clearInterval(state.dsMonitorTimer);
      state.dsMonitorTimer = null;
    }
  }, 1000);
}

function renderDeepSeekMonitor(data) {
  const latest = data?.latest;
  if (!latest) {
    dsStatus.textContent = "--";
    dsElapsed.textContent = "--";
    dsFirstToken.textContent = "--";
    dsChunks.textContent = "--";
    dsChars.textContent = "--";
    dsUsage.textContent = "--";
    dsEvents.textContent = "暂无 DeepSeek 调用。";
    dsPreview.textContent = "等待 DeepSeek 调用。";
    return;
  }
  state.lastMonitorId = latest.id || state.lastMonitorId;
  dsStatus.textContent = `${latest.status || "--"} / ${latest.kind || "--"} / ${latest.model || "--"}`;
  dsElapsed.textContent = formatMs(latest.elapsed_ms);
  dsFirstToken.textContent = formatMs(latest.first_token_ms);
  dsChunks.textContent = `${latest.chunk_count ?? "--"} / r${latest.reasoning_chars ?? 0}`;
  dsChars.textContent = `${latest.output_chars ?? "--"} out`;
  dsUsage.textContent = formatUsage(latest.usage);
  dsEvents.innerHTML = "";
  const rows = latest.events || [];
  rows.slice(-9).forEach((row) => {
    const item = document.createElement("div");
    item.className = `monitor-event ${safeClass(row.status || latest.status || "status")}`;
    item.textContent = `${row.time ? row.time.slice(11, 19) : "--"} / ${row.stage || "--"} / ${row.message || ""}`;
    dsEvents.appendChild(item);
  });
  dsEvents.scrollTop = dsEvents.scrollHeight;
  const prefix = `${latest.id || "--"}\n${latest.label || ""}\n\n`;
  const body = latest.error ? `ERROR:\n${latest.error}` : latest.preview_tail || "等待流式 token。";
  dsPreview.textContent = prefix + body;
}

function formatMs(value) {
  const number = toNullableNumber(value);
  if (number === null) {
    return "--";
  }
  if (number >= 1000) {
    return `${(number / 1000).toFixed(1)}s`;
  }
  return `${Math.round(number)}ms`;
}

function formatUsage(usage) {
  if (!usage || typeof usage !== "object" || !Object.keys(usage).length) {
    return "--";
  }
  const prompt = usage.prompt_tokens ?? usage.prompt_cache_hit_tokens ?? "?";
  const completion = usage.completion_tokens ?? "?";
  const total = usage.total_tokens ?? "?";
  return `p${prompt}/c${completion}/t${total}`;
}

async function loadDashboard() {
  try {
    const data = await getJson("/api/state");
    state.apiReady = true;
    state.dashboard = data;
    renderDashboard(data);
    if (data.status === "PENDING_SUBMISSION") {
      solverOutput.value = data.pending_solver_code || "";
      sessionNotice.textContent = `还有 Solver ${data.pending_version} 没有提交评分。请复制上面的 Solver，获得平台结果后粘贴反馈。`;
      state.trace = normalizeTrace({ mode: "pending_reminder", steps: [{ label: "发现未提交 Solver", kind: "memory", accepted: true }] });
      message.textContent = "小精灵发现上一版还没评分，先守住现场。";
    } else {
      sessionNotice.textContent = "READY：可以开始生成下一版 Solver。";
      message.textContent = "小精灵已读取记忆，等待开始。";
    }
  } catch (err) {
    state.apiReady = false;
    state.dashboard = fallbackDashboard;
    renderDashboard(fallbackDashboard);
    sessionNotice.textContent = "LOCAL：未连接后端，正在播放本地演示。";
    message.textContent = "本地演示模式已就绪。";
  }
  renderInitial();
  refreshDeepSeekMonitor();
}

async function startAgent() {
  setAgentControls(true);
  sessionNotice.textContent = "AGENT 正在构造上下文。";
  startDeepSeekMonitorPolling();
  try {
    const data = await postJson("/api/start", {
      deepseek_stream: true,
      deepseek_timeout_s: 180,
      max_tokens: 64000,
      monitor_kind: "solver_generation",
      monitor_label: "开始生成 Solver",
    });
    await handleAgentResponse(data);
  } catch (err) {
    sessionNotice.textContent = `开始失败：${err.message}`;
  } finally {
    setAgentControls(false);
  }
}

async function requestStrategyAdvice() {
  setAgentControls(true);
  sessionNotice.textContent = "DeepSeek 正在生成策略建议。";
  startDeepSeekMonitorPolling();
  try {
    const data = await postJson("/api/strategy_advice", {
      deepseek_stream: true,
      deepseek_timeout_s: 75,
      max_tokens: 2400,
    });
    await handleAgentResponse(data);
  } catch (err) {
    sessionNotice.textContent = `策略建议失败：${err.message}`;
  } finally {
    setAgentControls(false);
    refreshDeepSeekMonitor();
  }
}

async function runAgentLab() {
  setAgentControls(true);
  sessionNotice.textContent = "聪明 Agent 正在先请求策略建议，再生成候选、运行本地 scorer、审计硬编码。";
  startDeepSeekMonitorPolling();
  try {
    const data = await postJson("/api/lab", { iterations: 3 });
    await handleAgentResponse(data);
  } catch (err) {
    sessionNotice.textContent = `Agent Lab 失败：${err.message}`;
  } finally {
    setAgentControls(false);
  }
}

async function discardPending() {
  setAgentControls(true);
  sessionNotice.textContent = "正在放弃当前 pending。";
  try {
    const data = await postJson("/api/discard_pending", {});
    if (data.dashboard) {
      state.dashboard = data.dashboard;
    }
    solverOutput.value = data.dashboard?.pending_solver_code || "";
    state.trace = normalizeTrace(data.trace || fallbackTrace);
    renderDashboard(state.dashboard);
    sessionNotice.textContent = data.message || "Pending 已处理。";
    renderInitial();
  } catch (err) {
    sessionNotice.textContent = `放弃 pending 失败：${err.message}`;
  } finally {
    setAgentControls(false);
  }
}

async function sendFeedback() {
  const raw = feedbackInput.value.trim();
  if (!raw) {
    sessionNotice.textContent = "反馈为空，请先粘贴平台评分结果或 F12 JSON。";
    return;
  }
  setAgentControls(true);
  sessionNotice.textContent = "AGENT 正在解析反馈并复盘。";
  startDeepSeekMonitorPolling();
  try {
    const data = await postJson("/api/feedback", {
      raw_feedback: raw,
      deepseek_stream: true,
      deepseek_timeout_s: 180,
      max_tokens: 64000,
      monitor_kind: "solver_generation",
      monitor_label: "反馈后生成 Solver",
    });
    feedbackInput.value = "";
    await handleAgentResponse(data);
  } catch (err) {
    sessionNotice.textContent = `反馈发送失败：${err.message}`;
  } finally {
    setAgentControls(false);
  }
}

async function handleAgentResponse(data) {
  if (data.dashboard) {
    state.dashboard = data.dashboard;
  } else {
    state.dashboard = await getJson("/api/state");
  }
  if (data.agent_output) {
    state.lastAgentOutput = data.agent_output;
    if (data.agent_output._runtime) {
      state.lastRuntime = data.agent_output._runtime;
    }
  }
  if (data.solver_code) {
    solverOutput.value = data.solver_code;
  }
  renderDashboard(state.dashboard);

  if (data.type === "pending_reminder") {
    sessionNotice.textContent = data.message;
  } else if (data.type === "empty_feedback") {
    sessionNotice.textContent = data.message;
  } else if (data.type === "pending_discarded" || data.type === "no_pending") {
    sessionNotice.textContent = data.message;
  } else if (data.type === "strategy_advice_generated") {
    sessionNotice.textContent = `策略建议已生成：${data.agent_output?.strategy_focus || data.version || "ready"}`;
  } else if (data.version) {
    const labSuffix = data.type && data.type.includes("agent_lab") ? "（Agent Lab 本地工具筛选）" : "";
    sessionNotice.textContent = `已生成 ${data.version}${labSuffix}。复制 Solver 上传评分，拿到结果后粘贴反馈。`;
  } else {
    sessionNotice.textContent = "AGENT 已更新。";
  }

  state.trace = normalizeTrace(data.trace || fallbackTrace);
  renderInitial();
  refreshDeepSeekMonitor();
  await playAll();
}

function normalizeTrace(rawTrace) {
  const source = rawTrace && Array.isArray(rawTrace.steps) ? rawTrace : fallbackTrace;
  return {
    best_score: source.best_score || state.dashboard?.best?.average || fallbackTrace.best_score,
    best_strategy: source.best_strategy || "memory_reflect",
    steps: source.steps.map((step, index) => normalizeStep(step, index)),
  };
}

function normalizeStep(step, index) {
  if (step.strategy) {
    return {
      step_id: step.step_id || index + 1,
      strategy: step.strategy,
      score: toNullableNumber(step.score),
      valid: step.valid !== false,
      covered: step.covered || step.kind || "agent",
      accepted: step.accepted !== false,
      delta: step.delta || 0,
      message: step.message || step.label || "Agent step",
      visual: step.visual || {},
    };
  }
  const latestAverage = toNullableNumber(state.dashboard?.latest_result?.average);
  const bestAverage = toNullableNumber(state.dashboard?.best?.average);
  const score = latestAverage === null ? bestAverage : latestAverage;
  return {
    step_id: index + 1,
    strategy: kindToStrategy[step.kind] || "memory_reflect",
    score,
    valid: true,
    covered: step.kind || "agent",
    accepted: step.accepted !== false,
    delta: 0,
    message: step.label || step.message || "Agent step",
    visual: {},
  };
}

function makeDemoTrace() {
  const rows = state.dashboard?.timeline?.length ? state.dashboard.timeline : state.dashboard.score_series;
  const steps = (rows || []).map((item, index) => {
    const decision = item.decision || "";
    return {
      step_id: index + 1,
      strategy: strategyForDecision(decision, index),
      score: toNullableNumber(item.average),
      valid: !item.has_error_or_timeout,
      covered: item.completed || decision || "history",
      accepted: acceptedDecisions.has(decision) || decision.includes("accepted"),
      delta: 0,
      message: `${item.version || `v${index + 1}`}: ${item.reason || decision || "历史记录"}`,
      visual: {},
    };
  });
  return { best_score: state.dashboard?.best?.average || fallbackTrace.best_score, best_strategy: "memory_reflect", steps: steps.length ? steps : fallbackTrace.steps };
}

function strategyForDecision(decision, index) {
  if (decision.includes("reject")) {
    return "local_repair";
  }
  if (decision.includes("best") || decision.includes("accepted")) {
    return "memory_reflect";
  }
  return ["greedy_low_cost", "flow_ilp", "local_repair", "memory_reflect"][index % 4];
}

function renderDashboard(dashboard) {
  const best = dashboard?.best || {};
  bestScore.textContent = formatScore(best.average);
  agentState.textContent = statusLabel(dashboard?.status);
  traceStatus.textContent = runtimeLabel(dashboard);
  renderChat(dashboard?.chat || []);
  renderScoreChart(dashboard?.score_series || []);
  renderVersionList(dashboard?.timeline?.length ? dashboard.timeline : dashboard?.score_series || []);
  renderCaseTable(dashboard?.latest_cases || {});
  renderReview(dashboard || {});
}

function renderChat(rows) {
  chatLog.innerHTML = "";
  const visible = rows.length ? rows.slice(-8) : [{ role: "agent", content: "等待开始。", time: "" }];
  visible.forEach((row) => {
    const item = document.createElement("div");
    item.className = `chat-row ${row.role || "agent"}`;
    item.textContent = `${row.role || "agent"} ${row.time ? row.time.slice(11, 19) : ""} / ${row.content || ""}`;
    chatLog.appendChild(item);
  });
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderScoreChart(series) {
  scoreChart.innerHTML = "";
  const values = series.map((item) => toNullableNumber(item.average)).filter((value) => value !== null);
  if (!values.length) {
    scoreChart.textContent = "暂无分数";
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  series.forEach((item) => {
    const score = toNullableNumber(item.average);
    const bar = document.createElement("div");
    bar.className = `score-bar ${score === min ? "best" : ""}`;
    const fill = document.createElement("div");
    fill.className = "score-bar-fill";
    const height = score === null ? 14 : 28 + ((score - min) / range) * 132;
    fill.style.height = `${Math.round(height)}px`;
    const label = document.createElement("span");
    label.textContent = `${shortVersion(item.version)} ${formatScore(score)}`;
    bar.title = `${item.version || ""} / ${formatScore(score)} / ${item.decision || ""}`;
    bar.append(fill, label);
    scoreChart.appendChild(bar);
  });
}

function renderVersionList(rows) {
  versionList.innerHTML = "";
  if (!rows.length) {
    versionList.textContent = "暂无版本";
    return;
  }
  rows.slice(-12).forEach((item) => {
    const row = document.createElement("div");
    const decision = safeClass(item.decision || "unknown");
    row.className = `version-row ${decision}`;
    const dot = document.createElement("span");
    dot.className = "version-dot";
    const main = document.createElement("div");
    main.className = "version-main";
    const title = document.createElement("strong");
    title.textContent = item.version || "--";
    const meta = document.createElement("small");
    meta.textContent = `${formatScore(item.average)} / ${item.completed || "--"} / ${item.decision || "--"}`;
    const reason = document.createElement("small");
    reason.textContent = item.reason || "";
    main.append(title, meta, reason);
    row.append(dot, main);
    versionList.appendChild(row);
  });
}

function renderCaseTable(cases) {
  caseTableBody.innerHTML = "";
  const rows = Object.entries(cases || {}).sort((a, b) => {
    const left = toNullableNumber(a[1]?.score) || 0;
    const right = toNullableNumber(b[1]?.score) || 0;
    return right - left;
  });
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "暂无 case 明细";
    tr.appendChild(td);
    caseTableBody.appendChild(tr);
    return;
  }
  rows.forEach(([name, info]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="case-name">${escapeHtml(name)}</td>
      <td>${escapeHtml(formatScore(info.score))}</td>
      <td>${escapeHtml(info.completion || "--")}</td>
      <td>${escapeHtml(info.time_ms ?? "--")}</td>
    `;
    caseTableBody.appendChild(tr);
  });
}

function renderReview(dashboard) {
  const latest = dashboard.latest_result || {};
  const analysis = dashboard.score_analysis || {};
  const hasRisk = Boolean(latest.has_error_or_timeout || analysis.has_error_or_timeout);
  errorTile.className = `status-tile ${hasRisk ? "bad" : "ok"}`;
  errorTile.textContent = hasRisk ? "ERROR/TIMEOUT YES" : "ERROR/TIMEOUT NO";
  reasonBox.textContent = latest.reason || analysis.reason || "暂无保留/拒绝原因";
  const reflection =
    state.lastAgentOutput?.reflection ||
    state.lastAgentOutput?.agent_message ||
    firstReflectionExcerpt(dashboard.recent_reflections) ||
    "等待 Agent 反思";
  reflectionBox.textContent = stripMarkdown(reflection);
}

function firstReflectionExcerpt(rows) {
  if (!rows || !rows.length) {
    return "";
  }
  return rows[0].excerpt || "";
}

function toNullableNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function shortVersion(version) {
  if (!version) {
    return "--";
  }
  return version.length > 14 ? `${version.slice(0, 5)}..${version.slice(-5)}` : version;
}

function safeClass(value) {
  return String(value).replace(/[^A-Za-z0-9_-]/g, "_");
}

function statusLabel(status) {
  if (status === "PENDING_SUBMISSION") {
    return "PENDING";
  }
  return status || "--";
}

function runtimeLabel(dashboard) {
  if (state.lastRuntime?.mock_mode === false) {
    return "DS";
  }
  if (state.deepseekApiKey) {
    return "TOKEN";
  }
  return dashboard?.mock_mode ? "MOCK" : state.apiReady ? "API" : "LOCAL";
}

function stripMarkdown(text) {
  return String(text || "")
    .replace(/[#*_`>-]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function copySolver() {
  const text = solverOutput.value;
  if (!text) {
    sessionNotice.textContent = "当前没有可复制的 Solver。";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    sessionNotice.textContent = "Solver 已复制。";
  } catch (_err) {
    solverOutput.focus();
    solverOutput.select();
    document.execCommand("copy");
    sessionNotice.textContent = "Solver 已选中并复制。";
  }
}

function switchToLiveAnimation() {
  state.trace = normalizeTrace(state.trace);
  message.textContent = "实时动画已准备。";
  renderInitial();
}

function switchToDemoAnimation() {
  state.trace = makeDemoTrace();
  message.textContent = "历史回放已准备。";
  renderInitial();
}

playButton.addEventListener("click", playAll);
nextButton.addEventListener("click", runNext);
resetButton.addEventListener("click", renderInitial);
startAgentButton.addEventListener("click", startAgent);
strategyAdviceButton.addEventListener("click", requestStrategyAdvice);
labAgentButton.addEventListener("click", runAgentLab);
sendFeedbackButton.addEventListener("click", sendFeedback);
copySolverButton.addEventListener("click", copySolver);
discardPendingButton.addEventListener("click", discardPending);
liveAnimButton.addEventListener("click", switchToLiveAnimation);
demoAnimButton.addEventListener("click", switchToDemoAnimation);
deepseekTokenInput.addEventListener("input", () => {
  state.deepseekApiKey = deepseekTokenInput.value.trim();
  traceStatus.textContent = runtimeLabel(state.dashboard);
  if (state.deepseekApiKey) {
    sessionNotice.textContent = "DeepSeek Token 已临时启用：本页关闭或刷新后不会保存。模型固定 deepseek-v4-flash。";
  }
});
window.addEventListener("resize", () => moveFairyTo(agentDock, { animate: false, dy: -14 }));

renderAllPixelArt();
loadDashboard();
