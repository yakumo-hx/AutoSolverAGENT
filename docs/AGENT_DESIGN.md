# Agent Design

## 双层架构

平台只评测 `solve(input_text)` 的 10 秒执行结果。

因此作品采用：

```text
离线/演示 Agent 层 -> 策略探索、打分、记忆、可视化
线上 solver 层     -> 10 秒内稳定输出最终方案
```

## Agent 映射

- 小精灵：`AutoSolverAgent`
- 金币：候选 solution
- 算法篮子：`strategies.py` 中的策略函数
- 秤：`scorer.py` 的 validate + score
- 记账本：`MemoryLedger`
- 色彩 + / -：新 incumbent 或失败尝试
- 搬运动作：一次 strategy attempt

## 运行时链路

```text
parse case
  -> extract features
  -> planner chooses strategy order
  -> run each strategy
  -> validate and score
  -> accept if lower score
  -> append trace step
  -> export JSON for frontend animation
```

## DeepSeek 位置

DeepSeek 不应该进入线上判分 `solver.py`。

它适合放在展示层：

- 根据 case 特征选择策略顺序。
- 解释为什么尝试某个算法篮子。
- 生成评审可读的反思文本。

没有 API key 时，系统使用 mock planner，保证演示可复现。

