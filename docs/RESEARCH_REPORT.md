# 配送算法优化 Agent 研究报告

## 结论摘要

本项目要交付的不是通用 Codex，也不是每次 `solve()` 在线调用大模型，而是一个固定领域的算法优化 Agent。

它的核心闭环是：

```text
读取历史 -> 构造上下文 -> DeepSeek 单次生成下一版 solver
-> 人工提交平台 -> 粘贴 F12/评分结果
-> 自动解析与复盘 -> 更新结构化记忆 -> 进入下一轮
```

平台 10 秒限制只约束最终 `solver.py`。Agent 的探索、记忆、复盘和生成发生在外层工作台。

## 资料依据

- DeepSeek API 使用 OpenAI/Anthropic 兼容格式，调用时需要显式传入 `messages`，因此长期记忆必须由本地文件维护，而不是假设模型记得上轮对话。DeepSeek 官方 Quick Start 同时列出 `base_url=https://api.deepseek.com`、API key、model 和 chat completions 示例。
- DeepSeek JSON Output 要求设置 `response_format={"type":"json_object"}`，并在 prompt 中包含 “json” 和目标 JSON 示例；官方也提示要设置合理 `max_tokens`，避免结构化输出被截断。
- DeepSeek Function Calling 文档强调模型只返回工具调用，具体函数执行由用户系统完成；这支持本项目采用“模型规划/生成，工具验证/记忆”的分层设计。
- ReAct 的价值是交替进行 reasoning 和 action。映射到本项目，就是模型提出算法假设，系统执行本地验证或等待平台反馈，再把观察结果纳入下一轮。
- Reflexion 的价值是把反馈转化为语言化反思和 episodic memory。映射到本项目，就是每次平台结果都生成保留/拒绝原因、失败假设和下一轮提示。
- SWE-agent 强调 Agent-Computer Interface。映射到本项目，就是给 Agent 固定文件结构、可运行工具、结果解析器、版本生成器，而不是让它“随便聊天”。

## 单骑手/多骑手与算法方法的关系

用户提出的疑问是正确的：过去的历史里大量优化集中在单骑手、多骑手，但题面提到的贪心、ILP、启发式、LLM 直接推理是另一层概念。

两者关系如下：

```text
解结构层：
  - 单骑手：一个 task_key 只给一个 courier
  - 多骑手：一个 task_key 给多个 courier，提高联合完成概率
  - 合单：一个 task_key 覆盖两个任务
  - pair/single 混合：单任务与双任务候选组合

求解方法层：
  - 贪心：按 cost/benefit/density/概率排序选
  - min-cost flow：把单任务匹配变成网络流
  - ILP/MIP/CP-SAT：把候选选择建成 0/1 决策变量
  - beam search：保留若干前沿状态
  - branch-and-bound：精确/半精确搜索
  - local search：swap、ejection chain、rebalance
  - Lagrangian/penalty repair：放松部分冲突后修复
  - large neighborhood search：固定大部分解，只重优化小邻域
  - Monte Carlo / multi-start：用不同初始策略扩大搜索覆盖
  - LLM direct reasoning：只适合提出假设、解释结果，不适合直接在 10 秒 solver 中输出隐藏 case 解
```

所以正确提示词不是“在单骑手和多骑手之间选一个”，而是：

```text
在可选解结构（单骑手、多骑手、合单、混合分配）上，尝试不同求解方法（贪心、流、ILP-like、beam、局部搜索、LNS、修复启发式），并用平台反馈筛选。
```

## Agent 产品形态

建议实现 L3 半自动 Agent：

- Agent 自动读历史、生成 solver、更新记忆。
- 人工负责平台提交和粘贴 F12/评分结果。
- Agent 不自动消耗提交次数。
- DeepSeek API 只在外层工作台调用，不进入线上 `solver.py`。

## 必须支持的状态机

```text
READY
  没有待提交 solver。
  用户点击开始 -> 构造 context pack -> DeepSeek/mocked DeepSeek -> 生成 candidate solver -> PENDING_SUBMISSION

PENDING_SUBMISSION
  有 solver 还没平台评分。
  重启后仍保持此状态。
  用户点击开始 -> 不调用 DeepSeek，只提示复制 candidate solver 去提交。
  用户粘贴 F12/评分结果并发送 -> 解析、反思、更新记忆 -> READY 或 PENDING_SUBMISSION
```

## 前端必须展示的数据

- 聊天式窗口：开始、提醒待提交、粘贴结果、输出新 solver。
- 当前 best：平均分、完成率、版本、SHA256。
- 分数曲线：版本 vs 平均分。
- 版本时间线：每个版本保留/拒绝、原因。
- case-level 分数表：每个 case 的 score、completion、time。
- error/timeout 标记。
- 保留/拒绝原因。
- Agent 反思。
- 两种动画模式：
  - 实时运行：本轮 start / feedback 的 trace。
  - 演示模式：历史多轮优化记录。

## 最小可运行目标

第一版不追求真的超越 `v149`，但必须做到：

1. 运行一个本地 Web 服务。
2. 打开网页能恢复上次状态。
3. 点击开始能根据结构化历史生成一版 solver。
4. 若有未评分 solver，重启后提示先提交，不再开始新轮。
5. 粘贴平台结果后能解析、更新曲线/时间线/case 表/反思。
6. DeepSeek 无 key 时使用 mock 模式，保证可演示；有 key 时走真实 API。

## 参考链接

- DeepSeek API Quick Start: https://api-docs.deepseek.com/
- DeepSeek JSON Output: https://api-docs.deepseek.com/guides/json_mode
- DeepSeek Function Calling: https://api-docs.deepseek.com/guides/function_calling
- ReAct: https://arxiv.org/abs/2210.03629
- Reflexion: https://arxiv.org/abs/2303.11366
- SWE-agent: https://arxiv.org/abs/2405.15793
- OR-Tools Assignment: https://developers.google.com/optimization/assignment/assignment_example
- OR-Tools Minimum Cost Flow: https://developers.google.com/optimization/flow/mincostflow
- OR-Tools CP-SAT: https://developers.google.com/optimization/cp/cp_solver

