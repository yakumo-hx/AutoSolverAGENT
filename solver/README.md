# Solver

`solver.py` 是线上 10 秒执行器，接口为：

```python
def solve(input_text: str) -> list:
    ...
```

来源：

```text
MeiTuan26AiHackathon2.0/submissions/v149_probe_tiny_budget400k/solver.py
```

平台成绩：

- 平均惩罚分：`712.5276`
- 完成：`10/10`

它是 Agent 多轮实验和策略蒸馏后的稳定执行版本。不要在演示层代码里直接改它；后续若有新最好版本，再整体替换。

