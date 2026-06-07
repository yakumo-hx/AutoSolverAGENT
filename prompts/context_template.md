# Context Pack JSON

每次调用 DeepSeek 时，后端会发送：

```json
{
  "mode": "generate_solver 或 analyze_feedback",
  "task_card": "...",
  "platform_constraints": "...",
  "algorithm_playbook": "...",
  "known_results": {},
  "failed_hypotheses": "...",
  "run_state": {},
  "base_solver_code": "...",
  "user_feedback_raw": "...",
  "required_output_schema": {}
}
```

