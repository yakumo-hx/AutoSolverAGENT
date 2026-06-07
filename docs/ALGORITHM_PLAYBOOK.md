# 配送算法优化方法库

## 解结构

- 单骑手 single-courier：每个 task_key 只选择一个 courier。
- 多骑手 multi-courier：每个 task_key 选择多个 courier，提高完成概率。
- 单任务 single-task：一个 task_key 覆盖一个任务。
- 合单 pair/bundle：一个 task_key 覆盖两个任务。
- 混合结构：single、pair、多骑手共同存在。

## 求解方法

- Greedy portfolio：按 cost、benefit、benefit density、willingness、scarcity 等排序。
- Min-cost flow：适合单任务匹配，骑手/任务一对一或近似一对一。
- ILP/MIP：候选行作为 0/1 变量，约束任务和骑手不冲突。
- CP-SAT：表达复杂离散约束，适合小/中规模 exact 或局部 exact。
- Beam search：保留 top-k 部分解，适合低概率、多骑手组合。
- Branch-and-bound：适合 tiny/small 或严格限节点的小邻域。
- Local search：swap、two-opt、split/merge、ejection chain。
- Large neighborhood search：固定 incumbent 大部分结构，重优化局部任务集合。
- Repair heuristic：先构造冲突理想解，再修复重复骑手/重复任务。
- Case-typed policy：按任务数、骑手数、平均 willingness、pair 比例分支。
- Multi-start：多种初始解并行尝试，保留 incumbent。

## 提示词注意

不要把“单骑手/多骑手”误当成算法方法。它们是解结构。

正确表达：

```text
请在 single/multi courier、single/pair task 混合结构上，尝试 greedy、flow、ILP-like、beam、LNS、repair、local search 等方法，并严格控制 10 秒风险。
```

