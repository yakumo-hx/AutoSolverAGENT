# AutoSolverAGENT

像素风配送算法优化 Agent 工作台。这个仓库是比赛提交/展示用的干净版本：包含核心代码、可单独提交的 best solver、最新 Agent 候选、结构化平台分数、DeepSeek 真实调用记录和 reflection。

## 快速运行

```powershell
python backend/web_server.py
```

打开：

```text
http://localhost:8027/frontend/index.html
```

DeepSeek key 有两种方式：

- 在网页右侧输入框临时输入，刷新/关闭后不保存。
- 在本机父级目录放 `.env`，例如 `DEEPSEEK_API_KEY=...`。仓库只提供 `backend/.env.example`，不会提交真实 key。

默认模型：`deepseek-v4-flash`。

## 可提交 Solver

- `solver/solver.py`：当前历史 best，可直接单独提交到平台。
- `solvers/best/solver.py`：同一份历史 best 归档。
- `solvers/generated/v151_clean_multi_guard.py`：最新 Agent 根据第二轮平台反馈生成的 clean candidate。
- `solvers/generated/v010_rollback_clean_v149.py`：第一轮反馈后的回退候选。

线上 solver 不依赖 DeepSeek、不联网、不读文件、不打印；只暴露 `solve(input_text)`。

## 真实运行证据

核心证据都在 `logs/`：

- `logs/run_manifest.json`：反馈到生成的主证据链。
- `logs/deepseek_runs_sanitized.json`：真实 DeepSeek 流式调用记录，包含模型、耗时、usage、事件。
- `logs/structured_feedback/*.json`：平台 F12 结果的结构化分数，不是截图。
- `logs/reflections/*.md`：每轮保留/拒绝原因。
- `logs/agent_outputs/*.sanitized.json`：Agent 输出摘要，去掉大段 solver_code 和本地 `.env` 路径。
- `logs/score_history.json`：历史分数曲线数据。
- `logs/verification_summary.json`：本地验证摘要。

两轮关键闭环：

1. `v008_lab_20260607_220900` 平台反馈 `907.3511 / 10/10 / not_better` -> DeepSeek run `ds_20260607_221417_solver_generation` -> 生成 `v010_rollback_clean_v149.py`。
2. `v010_rollback_clean_v149` 平台反馈 `906.6899 / 10/10 / not_better` -> DeepSeek run `ds_20260607_222554_solver_generation` -> 生成 `v151_clean_multi_guard.py`。

## 前端展示

前端第一屏就是 Agent 工作台，不是静态介绍页。它展示：

- 像素小精灵 Agent 动画
- 分数曲线
- 版本时间线
- case-level 分数
- error/timeout 状态
- 保留/拒绝原因
- Agent reflection
- DeepSeek 流式监控面板

截图示例：`demo/screenshots/ds-flash-monitor.png`。

## 本地验证

已验证：

- Python 编译通过：`backend/*.py`、`solver/solver.py`、`solvers/generated/v151_clean_multi_guard.py`
- best solver 本地 synthetic suite：`5/5` 合法，无 timeout
- `v151_clean_multi_guard.py` 本地 synthetic suite：`5/5` 合法，无 timeout
- secret scan：未发现 `sk-...`、`DEEPSEEK_API_KEY=真实值`、`Authorization: Bearer ...`

注意：历史 best solver 保留了比赛探索中形成的固定映射痕迹；最新 clean candidate `v151_clean_multi_guard.py` 的硬编码审计为 low risk。

