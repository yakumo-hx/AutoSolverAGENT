# Frontend

像素风 Agent 工作台，入口：

```text
http://localhost:8027/frontend/index.html
```

当前页面包含：

- 带蝴蝶翅膀的小精灵：进入页面后持续扇动翅膀。
- 实时动画：播放本轮 `start` / `feedback` 的 Agent trace。
- 历史回放：根据版本时间线演示过去多轮优化记录。
- Agent 控制台：开始、复制 Solver、粘贴平台/F12 反馈。
- DeepSeek Token 输入框：仅当前页面临时使用，刷新/关闭后不保存。
- 数据面板：分数曲线、版本时间线、case-level 分数、error/timeout、保留/拒绝原因、Agent 反思。

启动：

```powershell
cd E:\Python_project\Hackathon\AutoSolverAgentShowcase
powershell -ExecutionPolicy Bypass -File scripts\run_workbench.ps1
```

没有 `DEEPSEEK_API_KEY` 时会进入 mock 模式，仍可验证完整交互闭环。

后端会向上查找 `.env`，例如 `E:\Python_project\.env`。网页输入的 token 优先于 `.env`，模型固定 `deepseek-v4-flash`。
