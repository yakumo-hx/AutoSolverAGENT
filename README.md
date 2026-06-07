# AutoSolverAGENT

像素风配送算法优化 Agent 工作台。这个仓库是面向交付的完整版本：包含核心代码、可单独提交的 best solver、最新 Agent 候选、结构化平台分数、DeepSeek 真实调用记录和 Agent 反思。

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
- `solvers/generated/v151_clean_multi_guard.py`：最新 Agent 根据第二轮平台反馈生成的泛化候选。
- `solvers/generated/v010_rollback_clean_v149.py`：第一轮反馈后的回退候选。

线上 solver 保持纯函数式提交形态：仅暴露 `solve(input_text)`，无需 DeepSeek、网络访问、文件读取或控制台输出。

## 真实运行证据

核心证据都在 `logs/`：

- `logs/run_manifest.json`：反馈到生成的主证据链。
- `logs/deepseek_runs_sanitized.json`：真实 DeepSeek 流式调用记录，包含模型、耗时、usage、事件。
- `logs/structured_feedback/*.json`：平台 F12 结果的结构化评分明细。
- `logs/reflections/*.md`：每轮保留/拒绝原因。
- `logs/agent_outputs/*.sanitized.json`：Agent 输出摘要，去掉大段 solver_code 和本地 `.env` 路径。
- `logs/score_history.json`：历史分数曲线数据。
- `logs/verification_summary.json`：质量门禁摘要。

两轮关键闭环：

1. `v008_lab_20260607_220900` 平台反馈 `907.3511 / 10/10 / not_better` -> DeepSeek run `ds_20260607_221417_solver_generation` -> 生成 `v010_rollback_clean_v149.py`。
2. `v010_rollback_clean_v149` 平台反馈 `906.6899 / 10/10 / not_better` -> DeepSeek run `ds_20260607_222554_solver_generation` -> 生成 `v151_clean_multi_guard.py`。

## 前端展示

前端第一屏即为可操作 Agent 工作台。它展示：

- 像素小精灵 Agent 动画
- 分数曲线
- 版本时间线
- case-level 分数
- 运行异常状态
- 保留/拒绝原因
- Agent reflection
- DeepSeek 流式监控面板

界面快照：`demo/screenshots/ds-flash-monitor.png`。

## 质量门禁

已验证：

- Python 编译通过：`backend/*.py`、`solver/solver.py`、`solvers/generated/v151_clean_multi_guard.py`
- best solver 内置评估集：`5/5` 合法，无 timeout
- `v151_clean_multi_guard.py` 内置评估集：`5/5` 合法，无 timeout
- secret scan：未发现 `sk-...`、`DEEPSEEK_API_KEY=真实值`、`Authorization: Bearer ...`

提交策略：`solver/solver.py` 保留当前最高分提交件；`v151_clean_multi_guard.py` 作为泛化候选持续迭代。两条线分层保留，便于同时维护分数表现和算法可迁移性。
