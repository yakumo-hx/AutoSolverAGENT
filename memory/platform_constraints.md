# Platform Constraints

- 最终提交只上传 `solver.py`。
- 必须定义 `solve(input_text: str) -> list`。
- 线上 solver 不读本地文件。
- 线上 solver 不访问网络。
- 线上 solver 不打印日志。
- 线上 solver 不依赖 DeepSeek、Codex 或其他外部服务。
- 尽量纯 Python。
- 10 秒/算例。
- 每个骑手最多使用一次。
- 每个任务最多覆盖一次。
- 可以返回多骑手列表，但必须保证候选存在、骑手不重复、任务不重复。
- 稳定性优先级高于局部冲榜：`10/10` 完成优先于平均分。

