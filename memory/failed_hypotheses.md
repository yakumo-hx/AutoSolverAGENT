# Failed Hypotheses

## 过重搜索

- `window_reoptimize` 和宽 branch-and-bound 在 40-task scarce case 容易 timeout。
- regular30/40 的 generic compare、quad rebalance、过宽 beam 都已出现 timeout 或无收益。

## 直接硬编码 F12 detail

- F12 detail 不能直接回放，可能出现 task/courier 映射错位或 validity=false。
- public `large_seed301.txt` 的离线 MILP 解不能外推到线上隐藏 case。

## small hybrid guard

- small hybrid beam 的本地 benefit guard 不可靠，线上会选出更差行。

## low_w 宽搜索

- low_w 宽 pair beam / 三骑手强制探针容易 timeout 或无收益。

## tiny budget

- tiny deterministic exact `400000` 节点稳定；`220000` 节点会漂。

