# Smart Agent Upgrade

## 之前的形态

旧工作台不是纯聊天窗口，因为它有：

- 持久状态。
- 版本落盘。
- 平台反馈解析。
- 结构化历史记忆。

但它仍然主要是：

```text
打包上下文 -> DeepSeek 单次返回 solver -> 等待人工平台评分
```

因此它更像“带记忆的单次 Coder”，不是完整工具型 Agent。

## 现在的形态

新增 Agent Lab：

```text
生成候选池
-> 本地运行 solver.py
-> 脱敏/合成 case scorer
-> 合法性、分数、runtime 检查
-> hardcode audit
-> 选择本地最可信候选
-> 输出 Solver 等待平台反馈
```

对应文件：

- `backend/smart_agent_lab.py`
- `backend/solver_eval_worker.py`
- `reports/lab/<run_id>.json`
- `solvers/lab/<run_id>/`

## DeepSeek 的位置

DeepSeek API 仍然是无状态单次请求。真正的 Agent 是本地 orchestrator。

有 `DEEPSEEK_API_KEY` 时：

```text
DeepSeek 生成 1-3 个候选
本地工具逐个评测
不合格/硬编码候选不会直接输出
```

无 key 时：

```text
使用本地 clean solver 模板候选
同样跑 scorer 和 hardcode audit
```

## Hardcode Audit

Agent Lab 会扫描候选代码里的固定映射：

```text
("T0025,T0028", "C006")
```

这类固定 `Txxxx/Cxxx` 表会被标记为高风险，并在选择分中加入惩罚。

## 选择策略

优先级：

1. 本地 suite 全合法。
2. 无固定平台 ID 映射。
3. 平均分更低。
4. runtime 更稳定。

本地 synthetic suite 不是平台隐藏评测，只是防止 Agent 盲改和包装成聊天窗口。
