# Task Card

## 任务名称

美团 AI Hackathon 命题四 AutoSolver。

## 固定目标

优化配送分配算法，使平台平均惩罚分尽量低，同时保持 `10/10` 完成。

## 平台入口

```python
def solve(input_text: str) -> list:
    ...
```

## 输入格式

```text
task_id_list courier_id total_score willingness
```

## 输出格式

```python
[(task_key, [courier_id, ...]), ...]
```

## 已知评分代理

单骑手候选：

```text
candidate_cost = willingness * total_score + (1 - willingness) * 100 * len(tasks)
```

多骑手候选：

```text
p_complete ≈ 1 - prod(1 - p_i)
accepted_score ≈ willingness-weighted total_score
```

## 当前最佳

```text
v149_probe_tiny_budget400k
average = 712.5276
completed = 10/10
```

## 主要瓶颈

- `low_willingness_seed501`
- `scarce_couriers_seed401`
- `large_seed301`
- `medium_seed202/203`
- `small_seed100`

