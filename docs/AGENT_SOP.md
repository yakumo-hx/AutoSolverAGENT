# 配送算法优化 Agent SOP

## 1. 角色

本 Agent 只服务于美团 AutoSolver 配送算法优化。

它不需要每轮重新读赛题，不做通用编程问答，不自动提交平台。

## 2. 输入

- 当前 best solver。
- 历史提交结构化结果。
- 历史失败假设。
- 当前未提交 candidate。
- 用户粘贴的平台/F12 结果。
- 用户本轮目标。

## 3. 输出

- 可复制的完整 `solver.py`。
- candidate 版本号。
- 本轮算法假设。
- 预期收益和风险。
- 保留/拒绝建议。
- 更新后的结构化数据。
- 前端动画 trace。

## 4. 状态机

### READY

无待提交 solver。

动作：

```text
Start -> ContextBuilder -> DeepSeekPlannerCoder -> save candidate -> PENDING_SUBMISSION
```

### PENDING_SUBMISSION

已有 candidate solver，但尚未粘贴平台结果。

动作：

```text
Start -> reminder only
Feedback -> parse result -> Reflector -> update memory -> READY
```

## 5. DeepSeek 调用规则

- 单次调用必须包含必要上下文。
- 不依赖模型跨请求记忆。
- 要求输出 JSON。
- JSON 中必须包含 `solver_code`。
- 若 API key 缺失，使用 mock 生成器。

## 6. 版本规则

版本格式：

```text
vNNN_agent_YYYYMMDD_HHMMSS
```

每个版本保存：

- `solvers/generated/<version>.py`
- `reports/reflections/<version>.md`
- `memory/structured/<version>.json`
- `memory/raw_feedback/<version>.txt`

## 7. 保留/拒绝规则

保留条件：

- 完成率 10/10。
- 平均分低于 best。
- 无新增 error/timeout 风险。

拒绝条件：

- 完成率下降。
- 有 error/timeout。
- 平均分显著回退。
- 只改善小 case 但破坏关键 case。

部分保留：

- 平均分未赢，但某个 case 有真实收益。
- 写入 finding，不更新 best。

