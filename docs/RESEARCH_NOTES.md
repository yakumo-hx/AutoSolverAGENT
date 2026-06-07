# Research Notes

## 检索结论

当前主流 Agent 工程形态基本是：

- LLM 负责规划、选择工具、解释决策。
- 具体工具负责可验证计算。
- 系统记录 trace、score、tool result 和 memory。
- 关键任务会加 guardrail/fallback，避免 LLM 的不稳定性污染最终输出。

## 对本项目的落地方式

DeepSeek API 适合接在 `LlmPlanner`：

- 输入：任务数量、骑手数量、候选数量、pair 比例、平均 willingness、历史分数。
- 输出：策略顺序和简短 rationale。
- 工具：仍由 Python 策略和 scorer 执行。

这样既有 Agent 感，又不把线上 10 秒 solver 暴露给网络依赖。

## 参考链接

- DeepSeek API Docs: https://api-docs.deepseek.com/
- DeepSeek Function Calling: https://api-docs.deepseek.com/guides/function_calling
- DeepSeek JSON Output: https://api-docs.deepseek.com/guides/json_mode
- OpenAI Agents Guide: https://platform.openai.com/docs/guides/agents

