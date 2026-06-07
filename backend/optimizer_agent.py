from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from deepseek_monitor import DeepSeekMonitor
from smart_agent_lab import SmartAgentLab


CASE_NAMES = [
    "high_noise_seed601",
    "large_seed301",
    "large_seed302",
    "low_willingness_seed501",
    "medium_seed201",
    "medium_seed202",
    "medium_seed203",
    "scarce_couriers_seed401",
    "small_seed100",
    "tiny_seed42",
]


class JsonStore:
    def __init__(self, path: Path, default: Any) -> None:
        self.path = path
        self.default = default

    def load(self) -> Any:
        if not self.path.exists():
            return self.default
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class DeepSeekClient:
    def __init__(self, root: Path, monitor: Optional[DeepSeekMonitor] = None) -> None:
        self.root = root
        self.monitor = monitor
        self.env_files = _load_dotenv_upward(root)
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.force_mock = os.environ.get("AUTOSOLVER_AGENT_MOCK", "").lower() in {"1", "true", "yes"}
        self.mock = self.force_mock or not self.api_key

    def complete_json(
        self,
        system_prompt: str,
        context: Dict[str, Any],
        runtime: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        runtime = runtime or {}
        request_key = runtime.get("deepseek_api_key", "").strip()
        api_key = request_key or self.api_key
        model = (runtime.get("deepseek_model") or self.model or "deepseek-v4-flash").strip()
        token_source = "request" if request_key else ("env" if self.api_key else "none")
        use_mock = self.force_mock or not api_key
        stream = _truthy(runtime.get("deepseek_stream", "false"))
        monitor_id = self._begin_monitor(context, runtime, model, token_source, use_mock, stream)
        started = time.perf_counter()
        if use_mock:
            response = self._mock_response(context)
            response["_runtime"] = {
                "mock_mode": True,
                "model": model,
                "token_source": token_source,
                "env_files": self.env_files,
                "monitor_id": monitor_id,
                "stream": stream,
                "elapsed_ms": 0.0,
            }
            if monitor_id and self.monitor:
                self.monitor.finish(monitor_id, status="mock", message="mock response")
            return response

        max_tokens = int(runtime.get("max_tokens") or runtime.get("deepseek_max_tokens") or 64000)
        timeout_s = int(runtime.get("deepseek_timeout_s") or os.environ.get("DEEPSEEK_TIMEOUT_S", "120"))
        total_timeout_s = int(runtime.get("deepseek_total_timeout_s") or runtime.get("deepseek_timeout_s") or os.environ.get("DEEPSEEK_TIMEOUT_S", "120"))

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请基于以下 json context 输出严格 json：\n"
                    + json.dumps(context, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": stream,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}

        response_meta: Dict[str, Any] = {}
        try:
            if monitor_id and self.monitor:
                self.monitor.event(monitor_id, "request", f"POST chat/completions timeout={timeout_s}s total={total_timeout_s}s max_tokens={max_tokens}")
            if stream:
                content, response_meta = self._request_stream(payload, api_key, timeout_s, total_timeout_s, monitor_id)
            else:
                content, response_meta = self._request_blocking(payload, api_key, timeout_s, monitor_id)
            parsed = self._parse_json_content(content)
        except Exception as exc:
            if monitor_id and self.monitor:
                self.monitor.finish(monitor_id, status="error", message="DeepSeek 调用失败", error=repr(exc))
            raise

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        if monitor_id and self.monitor:
            self.monitor.finish(
                monitor_id,
                status="completed",
                message=f"parsed json in {elapsed_ms} ms",
                usage=response_meta.get("usage") if isinstance(response_meta, dict) else None,
                finish_reason=str(response_meta.get("finish_reason") or ""),
            )
        if isinstance(parsed, dict):
            parsed["_runtime"] = {
                "mock_mode": False,
                "model": model,
                "token_source": token_source,
                "env_files": self.env_files,
                "monitor_id": monitor_id,
                "stream": stream,
                "elapsed_ms": elapsed_ms,
            }
            return parsed
        return {
            "solver_code": "",
            "agent_message": "DeepSeek returned non-object JSON.",
            "_runtime": {
                "mock_mode": False,
                "model": model,
                "token_source": token_source,
                "env_files": self.env_files,
                "monitor_id": monitor_id,
                "stream": stream,
                "elapsed_ms": elapsed_ms,
            },
        }

    def _begin_monitor(
        self,
        context: Dict[str, Any],
        runtime: Dict[str, str],
        model: str,
        token_source: str,
        use_mock: bool,
        stream: bool,
    ) -> Optional[str]:
        if self.monitor is None or _truthy(runtime.get("disable_monitor", "false")):
            return None
        mode = str(context.get("mode") or runtime.get("monitor_kind") or "deepseek")
        kind = str(runtime.get("monitor_kind") or mode)
        label = str(runtime.get("monitor_label") or f"{kind} / {context.get('suggested_version') or context.get('lab_run_id') or ''}").strip()
        context_chars = len(json.dumps(context, ensure_ascii=False))
        max_tokens = runtime.get("max_tokens") or runtime.get("deepseek_max_tokens") or "64000"
        timeout_s = runtime.get("deepseek_timeout_s") or os.environ.get("DEEPSEEK_TIMEOUT_S", "120")
        total_timeout_s = runtime.get("deepseek_total_timeout_s") or timeout_s
        return self.monitor.begin(
            kind=kind,
            label=label,
            model=model,
            token_source=token_source,
            mock_mode=use_mock,
            request_summary={
                "mode": mode,
                "stream": stream,
                "context_chars": context_chars,
                "max_tokens": int(max_tokens),
                "timeout_s": int(timeout_s),
                "total_timeout_s": int(total_timeout_s),
            },
        )

    def _request_blocking(
        self,
        payload: Dict[str, Any],
        api_key: str,
        timeout_s: int,
        monitor_id: Optional[str],
    ) -> Tuple[str, Dict[str, Any]]:
        req = self._request(payload, api_key)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        body = json.loads(raw)
        choice = body["choices"][0]
        content = choice["message"]["content"]
        if monitor_id and self.monitor:
            self.monitor.delta(
                monitor_id,
                text=content,
                usage=body.get("usage") or {},
                finish_reason=str(choice.get("finish_reason") or ""),
            )
        return content, {"usage": body.get("usage") or {}, "finish_reason": choice.get("finish_reason")}

    def _request_stream(
        self,
        payload: Dict[str, Any],
        api_key: str,
        timeout_s: int,
        total_timeout_s: int,
        monitor_id: Optional[str],
    ) -> Tuple[str, Dict[str, Any]]:
        req = self._request(payload, api_key)
        content_parts: List[str] = []
        pending_parts: List[str] = []
        usage: Dict[str, Any] = {}
        finish_reason = ""
        last_flush = time.perf_counter()
        started = time.perf_counter()

        def flush(force: bool = False) -> None:
            nonlocal last_flush
            if not monitor_id or not self.monitor or not pending_parts:
                return
            if not force and time.perf_counter() - last_flush < 0.45 and len(pending_parts) < 16:
                return
            text = "".join(pending_parts)
            pending_parts.clear()
            last_flush = time.perf_counter()
            self.monitor.delta(monitor_id, text=text, usage=usage, finish_reason=finish_reason)

        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                for raw_line in response:
                    if total_timeout_s > 0 and time.perf_counter() - started > total_timeout_s:
                        raise TimeoutError(f"DeepSeek stream total timeout after {total_timeout_s}s")
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        if monitor_id and self.monitor:
                            self.monitor.event(monitor_id, "done_signal", "[DONE]", "streaming")
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        if monitor_id and self.monitor:
                            self.monitor.event(monitor_id, "bad_chunk", data[:240], "streaming")
                        continue
                    if chunk.get("usage"):
                        usage = chunk.get("usage") or {}
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finish_reason = str(choice.get("finish_reason") or "")
                    delta = choice.get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    if reasoning and monitor_id and self.monitor:
                        self.monitor.delta(monitor_id, reasoning_chars=len(str(reasoning)))
                    text = delta.get("content") or ""
                    if text:
                        content_parts.append(text)
                        pending_parts.append(text)
                        flush(force=False)
                flush(force=True)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        return "".join(content_parts), {"usage": usage, "finish_reason": finish_reason}

    def _request(self, payload: Dict[str, Any], api_key: str) -> urllib.request.Request:
        return urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

    def _parse_json_content(self, content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", content, flags=re.S)
            if match:
                return json.loads(match.group(1))
            raise

    def _mock_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        base_solver = context.get("base_solver_code", "")
        version = context.get("suggested_version", "v000_agent_mock")
        mode = context.get("mode", "generate_solver")
        latest = context.get("latest_result_summary", {})
        if mode == "strategy_advice":
            return {
                "agent_message": "Mock 策略建议：先缩小上下文，优先让本地工具验证 clean solver 的 guarded repair / pair density / multi-start 贪心组合。",
                "version_name": version,
                "strategy_focus": "先用轻量策略建议确定方向，再由本地候选池和 scorer 验证。",
                "suggested_algorithms": ["multi-start greedy", "pair-density heuristic", "guarded local repair", "small-case multi-courier ensemble"],
                "experiment_plan": [
                    "保留 current best 作为参照组，但标记硬编码风险",
                    "生成无固定 T/C 映射的 clean 候选并在 synthetic suite 上跑分",
                    "对低意愿/骑手稀缺 case 加 guard，避免 timeout",
                ],
                "guardrails": ["solver.py 不联网不读文件", "搜索必须有规模 guard", "优先 10/10 完成率"],
                "expected_effect": f"当前 latest summary: {latest}",
                "rejected_options": ["固定平台 ID 映射", "无 guard 的全局组合爆搜"],
                "next_solver_brief": "让 Lab 先测 clean_multi_courier_guarded，再考虑 DS 生成的差异化候选。",
                "reflection": "Mock 策略建议用于跑通流程；真实 DeepSeek 会补充更具体的实验方向。",
            }
        target = "low_willingness / scarce / regular30 guarded local repair"
        if mode == "analyze_feedback":
            target = "根据刚粘贴的平台反馈，继续做受保护的小邻域候选探索"
        return {
            "agent_message": "Mock 模式：未检测到 DEEPSEEK_API_KEY，因此复制当前 best solver，并生成一轮结构化候选。设置 DEEPSEEK_API_KEY 后会调用真实 DeepSeek。",
            "version_name": version,
            "hypothesis": target,
            "changes": [
                "保留当前 best solver 作为安全候选",
                "把本轮重点写入 Agent 记忆，等待真实 DeepSeek 进一步生成差异化代码",
            ],
            "risk_notes": [
                "Mock 候选预计与 best 同分，主要用于验证闭环",
                "真实 API 模式下需要检查生成代码是否仍满足 10 秒和平台约束",
            ],
            "expected_effect": f"当前 latest summary: {latest}",
            "solver_code": base_solver,
            "reflection": "Mock 反思：流程、持久状态和前端工作台已可运行；真实优化需要 API key。",
            "next_user_action": "请复制 solver 上传平台；拿到平台结果或 F12 明细后粘贴到反馈框并发送。",
        }


class PlatformResultParser:
    def parse(self, raw: str, version: str) -> Dict[str, Any]:
        parsed = self._parse_json_like(raw) or {}
        text_result = self._parse_text(raw)
        result = {
            "version": version,
            "average": parsed.get("average") or text_result.get("average"),
            "completed": parsed.get("completed") or text_result.get("completed"),
            "cases": parsed.get("cases") or text_result.get("cases") or {},
            "raw_length": len(raw),
        }
        result["has_error_or_timeout"] = self._has_error_or_timeout(raw, result)
        return result

    def _parse_json_like(self, raw: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"(\{.*\})", raw, flags=re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except Exception:
            return None
        return self._extract_from_obj(data)

    def _extract_from_obj(self, data: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {"cases": {}}

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                keys = {str(k).lower(): k for k in obj}
                for avg_key in ("average", "avg_score", "average_score", "avgPenalty", "avg_penalty"):
                    if avg_key.lower() in keys and result.get("average") is None:
                        result["average"] = _to_float(obj[keys[avg_key.lower()]])
                if result.get("completed") is None and "success_count" in keys and "case_count" in keys:
                    success = obj[keys["success_count"]]
                    total = obj[keys["case_count"]]
                    result["completed"] = f"{success}/{total}"
                for done_key in ("completed", "completion", "completed_cases", "success"):
                    if done_key.lower() in keys and result.get("completed") is None:
                        result["completed"] = str(obj[keys[done_key.lower()]])
                name = obj.get("case") or obj.get("case_name") or obj.get("case_file") or obj.get("name") or obj.get("filename")
                if isinstance(name, str):
                    clean_name = _case_name_from_text(name)
                    if clean_name:
                        score = _first_float(obj, ["total_score", "score", "penalty", "result", "avg_score"])
                        time_ms = _first_float(obj, ["elapsed_ms", "time_ms", "runtime_ms", "time", "elapsed"])
                        completion = obj.get("completion") or obj.get("completed") or obj.get("complete")
                        if completion is None and obj.get("assigned_count") is not None:
                            assigned = obj.get("assigned_count")
                            unassigned = obj.get("unassigned_count") or 0
                            try:
                                completion = f"{int(assigned)}/{int(assigned) + int(unassigned)}"
                            except Exception:
                                completion = str(assigned)
                        result["cases"][clean_name] = {
                            "score": score,
                            "completion": str(completion) if completion is not None else "",
                            "time_ms": time_ms,
                        }
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        result["average"] = None
        result["completed"] = None
        walk(data)
        return result

    def _parse_text(self, raw: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"cases": {}}
        avg_match = re.search(r"(?:平均惩罚分数|平均分|average(?: penalty)?|avg)[^\d]*(\d+(?:\.\d+)?)", raw, re.I)
        if avg_match:
            result["average"] = float(avg_match.group(1))
        comp_match = re.search(r"(?:完成算例|completed|完成)[^\d]*(\d+\s*/\s*\d+)", raw, re.I)
        if comp_match:
            result["completed"] = comp_match.group(1).replace(" ", "")
        for case in CASE_NAMES:
            idx = raw.find(case)
            if idx < 0:
                continue
            snippet = raw[idx : idx + 260]
            nums = re.findall(r"\d+(?:\.\d+)?", snippet)
            score = float(nums[0]) if nums else None
            time_ms = None
            time_match = re.search(r"(\d+)\s*ms", snippet, re.I)
            if time_match:
                time_ms = float(time_match.group(1))
            completion = ""
            comp = re.search(r"(\d+\s*/\s*\d+)", snippet)
            if comp:
                completion = comp.group(1).replace(" ", "")
            result["cases"][case] = {"score": score, "completion": completion, "time_ms": time_ms}
        return result

    def _has_error_or_timeout(self, raw: str, result: Dict[str, Any]) -> bool:
        low = raw.lower()
        if "timeout" in low or "traceback" in low or "validity=false" in low:
            return True
        if re.search(r'"status"\s*:\s*"(?:error|failed|timeout)"', raw, re.I):
            return True
        completed = str(result.get("completed") or "")
        if "/" in completed:
            left, right = completed.split("/", 1)
            try:
                return int(left.strip()) < int(right.strip())
            except ValueError:
                return False
        return False


class OptimizerAgent:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.monitor = DeepSeekMonitor(root)
        self.known_store = JsonStore(root / "memory" / "known_results.json", {})
        self.state_store = JsonStore(root / "memory" / "run_state.json", {"status": "READY", "chat": []})
        self.best_store = JsonStore(root / "memory" / "best_solver_registry.json", {})
        self.deepseek = DeepSeekClient(root, self.monitor)
        self.parser = PlatformResultParser()

    def dashboard(self) -> Dict[str, Any]:
        known = self.known_store.load()
        state = self.state_store.load()
        best = self.best_store.load()
        history = known.get("history", [])
        latest = history[-1] if history else {}
        pending_code = ""
        if state.get("status") == "PENDING_SUBMISSION":
            pending_code = self._read_optional(state.get("pending_solver_path"))
        return {
            "status": state.get("status", "READY"),
            "pending_version": state.get("pending_version"),
            "pending_solver_path": state.get("pending_solver_path"),
            "pending_solver_code": pending_code,
            "best": {
                "version": best.get("version") or known.get("best_version"),
                "average": best.get("average") or known.get("best_average"),
                "completed": best.get("completed") or known.get("completed"),
                "sha256": best.get("sha256") or known.get("sha256"),
                "path": best.get("path") or known.get("best_solver_path"),
            },
            "score_series": [
                {
                    "version": item.get("version"),
                    "average": item.get("average"),
                    "decision": item.get("decision", ""),
                }
                for item in history
                if item.get("average") is not None
            ],
            "timeline": [
                {
                    "version": item.get("version"),
                    "average": item.get("average"),
                    "completed": item.get("completed"),
                    "decision": item.get("decision", ""),
                    "reason": item.get("reason", ""),
                    "has_error_or_timeout": item.get("has_error_or_timeout", False),
                }
                for item in history[-12:]
            ],
            "latest_result": latest,
            "latest_cases": latest.get("cases", {}) if latest else {},
            "score_analysis": self._case_score_analysis(known),
            "recent_reflections": self._recent_reflections(),
            "chat": state.get("chat", []),
            "mock_mode": self.deepseek.mock,
        }

    def deepseek_monitor(self) -> Dict[str, Any]:
        return self.monitor.snapshot()

    def strategy_advice(self, runtime: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        version = self._next_version(prefix="strategy_advice")
        context = self._build_strategy_context(suggested_version=version)
        call_runtime = dict(runtime or {})
        call_runtime.setdefault("deepseek_stream", "true")
        call_runtime.setdefault("deepseek_timeout_s", "75")
        call_runtime.setdefault("max_tokens", "2400")
        call_runtime.setdefault("monitor_kind", "strategy_advice")
        call_runtime.setdefault("monitor_label", f"策略建议 {version}")
        response = self.deepseek.complete_json(self._strategy_prompt(), context, runtime=call_runtime)
        response.setdefault("version_name", version)
        self._save_strategy_advice(version, response)
        self._append_chat("agent", response.get("agent_message", "策略建议已生成。"))
        return {
            "type": "strategy_advice_generated",
            "version": version,
            "agent_output": response,
            "dashboard": self.dashboard(),
            "trace": self._strategy_trace(response),
        }

    def start(self, runtime: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        state = self.state_store.load()
        if state.get("status") == "PENDING_SUBMISSION":
            solver_code = self._read_optional(state.get("pending_solver_path"))
            return {
                "type": "pending_reminder",
                "message": f"还有 Solver {state.get('pending_version')} 没有提交评分。请先复制该 Solver 上传，获得平台结果后粘贴反馈。",
                "solver_code": solver_code,
                "dashboard": self.dashboard(),
                "trace": self._trace("pending_reminder"),
            }

        version = self._next_version()
        context = self._build_context("generate_solver", suggested_version=version)
        response = self.deepseek.complete_json(self._system_prompt(), context, runtime=runtime)
        saved = self._save_candidate(response, version)
        self._append_chat("agent", response.get("agent_message", "已生成新候选 Solver。"))
        return {
            "type": "candidate_generated",
            "version": saved["version"],
            "solver_code": saved["solver_code"],
            "agent_output": response,
            "dashboard": self.dashboard(),
            "trace": self._trace("generate_solver", response),
        }

    def feedback(self, raw_feedback: str, runtime: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not raw_feedback.strip():
            return {
                "type": "empty_feedback",
                "message": "反馈为空。请粘贴平台评分结果或 F12 暴露的 JSON 后再发送。",
                "dashboard": self.dashboard(),
                "trace": self._trace("empty_feedback"),
            }

        state = self.state_store.load()
        version = state.get("pending_version") or self._next_version(prefix="v_feedback")
        raw_path = self.root / "memory" / "raw_feedback" / f"{version}.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_feedback, encoding="utf-8")

        parsed = self.parser.parse(raw_feedback, version)
        structured_path = self.root / "memory" / "structured" / f"{version}.json"
        structured_path.parent.mkdir(parents=True, exist_ok=True)
        structured_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

        reflection = self._update_known_results(parsed)
        self._write_reflection(version, parsed, reflection)
        self._append_chat("user", f"粘贴了 {version} 平台反馈，解析 average={parsed.get('average')} completed={parsed.get('completed')}")
        self._append_chat("agent", reflection["summary"])

        # After feedback, immediately generate the next solver.
        next_version = self._next_version()
        context = self._build_context(
            "analyze_feedback",
            suggested_version=next_version,
            feedback_result=parsed,
            reflection=reflection,
            raw_feedback=raw_feedback[:12000],
        )
        response = self.deepseek.complete_json(self._system_prompt(), context, runtime=runtime)
        saved = self._save_candidate(response, next_version)
        self._append_chat("agent", response.get("agent_message", "已基于反馈生成下一版 Solver。"))

        return {
            "type": "feedback_analyzed_next_candidate_generated",
            "parsed_result": parsed,
            "reflection": reflection,
            "version": saved["version"],
            "solver_code": saved["solver_code"],
            "agent_output": response,
            "dashboard": self.dashboard(),
            "trace": self._trace("feedback_then_generate", response),
        }

    def lab(
        self,
        iterations: int = 3,
        preview_only: bool = False,
        force: bool = False,
        runtime: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        state = self.state_store.load()
        if state.get("status") == "PENDING_SUBMISSION" and not preview_only and not force:
            solver_code = self._read_optional(state.get("pending_solver_path"))
            return {
                "type": "pending_reminder",
                "message": (
                    f"还有 Solver {state.get('pending_version')} 没有提交评分。"
                    "Agent Lab 不会覆盖 pending；请先提交/粘贴反馈，或放弃该 pending。"
                ),
                "solver_code": solver_code,
                "dashboard": self.dashboard(),
                "trace": self._trace("pending_reminder"),
            }

        version = self._next_version().replace("_agent_", "_lab_")
        context = self._build_context("agent_lab", suggested_version=version)
        lab = SmartAgentLab(self.root, self.deepseek, self._system_prompt(), runtime=runtime)
        iteration_count = int(iterations if iterations is not None else 3)
        response = lab.run(
            base_solver_code=context["base_solver_code"],
            context=context,
            run_id=version,
            iterations=max(0, min(iteration_count, 5)),
        )
        self._append_chat("agent", response.get("agent_message", "Agent Lab 已完成本地工具循环。"))

        if preview_only:
            return {
                "type": "agent_lab_preview",
                "version": version,
                "solver_code": response.get("solver_code", ""),
                "agent_output": response,
                "dashboard": self.dashboard(),
                "trace": self._lab_trace(response.get("lab_report", {})),
            }

        saved = self._save_candidate(response, version)
        return {
            "type": "agent_lab_candidate_generated",
            "version": saved["version"],
            "solver_code": saved["solver_code"],
            "agent_output": response,
            "dashboard": self.dashboard(),
            "trace": self._lab_trace(response.get("lab_report", {})),
        }

    def discard_pending(self) -> Dict[str, Any]:
        state = self.state_store.load()
        old_version = state.get("pending_version")
        if state.get("status") != "PENDING_SUBMISSION":
            return {
                "type": "no_pending",
                "message": "当前没有待提交 Solver。",
                "dashboard": self.dashboard(),
                "trace": self._trace("no_pending"),
            }
        state.update(
            {
                "status": "READY",
                "pending_version": None,
                "pending_solver_path": None,
                "pending_created_at": None,
                "pending_sha256": None,
                "last_event": "pending_discarded",
            }
        )
        self.state_store.save(state)
        self._append_chat("agent", f"已放弃 pending Solver {old_version}。文件仍保留在 solvers/generated 中。")
        return {
            "type": "pending_discarded",
            "message": f"已放弃 pending Solver {old_version}，可以重新开始或运行 Agent Lab。",
            "dashboard": self.dashboard(),
            "trace": self._trace("pending_discarded"),
        }

    def _build_context(self, mode: str, **extra: Any) -> Dict[str, Any]:
        known = self.known_store.load()
        state = self.state_store.load()
        best = self.best_store.load()
        base_solver = (self.root / (best.get("path") or "solvers/best/solver.py")).read_text(encoding="utf-8")
        context = {
            "mode": mode,
            "generated_at": _now(),
            "suggested_version": extra.get("suggested_version"),
            "task_card": self._read("memory/task_card.md"),
            "platform_constraints": self._read("memory/platform_constraints.md"),
            "algorithm_playbook": self._read("docs/ALGORITHM_PLAYBOOK.md"),
            "failed_hypotheses": self._read("memory/failed_hypotheses.md"),
            "known_results": known,
            "run_state": state,
            "best_solver_registry": best,
            "latest_result_summary": self._latest_summary(known),
            "score_analysis": self._case_score_analysis(known),
            "recent_raw_feedbacks": self._recent_raw_feedbacks(),
            "recent_agent_outputs": self._recent_agent_outputs(),
            "base_solver_code": base_solver,
            "current_requirement": (
                "只优化配送算法。生成完整 solver.py。每轮提出 1-2 个有 guard 的算法假设，"
                "优先 10/10 完成率和 10 秒内稳定性。"
            ),
            "required_output_schema": {
                "agent_message": "string",
                "version_name": "string",
                "hypothesis": "string",
                "changes": ["string"],
                "risk_notes": ["string"],
                "expected_effect": "string",
                "solver_code": "complete Python code",
                "reflection": "string",
                "next_user_action": "string",
            },
        }
        context.update(extra)
        return context

    def _build_strategy_context(self, suggested_version: str) -> Dict[str, Any]:
        known = self.known_store.load()
        best = self.best_store.load()
        base_path = self.root / (best.get("path") or "solvers/best/solver.py")
        base_solver = base_path.read_text(encoding="utf-8")
        return {
            "mode": "strategy_advice",
            "generated_at": _now(),
            "suggested_version": suggested_version,
            "task_card": self._read("memory/task_card.md"),
            "platform_constraints": self._read("memory/platform_constraints.md"),
            "algorithm_playbook": self._read("docs/ALGORITHM_PLAYBOOK.md"),
            "failed_hypotheses": self._read("memory/failed_hypotheses.md"),
            "known_results": known,
            "best_solver_registry": best,
            "latest_result_summary": self._latest_summary(known),
            "score_analysis": self._case_score_analysis(known),
            "recent_agent_outputs": self._recent_agent_outputs(limit=3),
            "base_solver_fingerprint": {
                "path": str(base_path.relative_to(self.root)),
                "chars": len(base_solver),
                "sha256": hashlib.sha256(base_solver.encode("utf-8")).hexdigest().upper(),
                "has_hardcoded_pairs_hint": bool(re.search(r'\("T\d{4}(?:,T\d{4})?",\s*"C\d{3}"\)', base_solver)),
            },
            "required_output_schema": {
                "agent_message": "string",
                "version_name": "string",
                "strategy_focus": "string",
                "suggested_algorithms": ["string"],
                "experiment_plan": ["string"],
                "guardrails": ["string"],
                "expected_effect": "string",
                "rejected_options": ["string"],
                "next_solver_brief": "string",
                "reflection": "string",
            },
        }

    def _save_candidate(self, response: Dict[str, Any], fallback_version: str) -> Dict[str, str]:
        if not isinstance(response, dict):
            response = {
                "version_name": fallback_version,
                "agent_message": "DeepSeek 输出不是 JSON object，已回退到当前 best solver。",
                "solver_code": self._read("solvers/best/solver.py"),
            }
        version = _safe_name(response.get("version_name") or fallback_version)
        solver_code = response.get("solver_code") or self._read("solvers/best/solver.py")
        if "def solve" not in solver_code:
            solver_code = self._read("solvers/best/solver.py")
        out_path = self.root / "solvers" / "generated" / f"{version}.py"
        out_path.write_text(solver_code, encoding="utf-8")
        sha = hashlib.sha256(solver_code.encode("utf-8")).hexdigest().upper()
        state = self.state_store.load()
        state.update(
            {
                "status": "PENDING_SUBMISSION",
                "pending_version": version,
                "pending_solver_path": str(out_path.relative_to(self.root)),
                "pending_created_at": _now(),
                "pending_sha256": sha,
                "last_event": "candidate_generated",
            }
        )
        self.state_store.save(state)
        self._save_agent_output(version, response, sha)
        return {"version": version, "solver_code": solver_code}

    def _update_known_results(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        known = self.known_store.load()
        best = self.best_store.load()
        avg = parsed.get("average")
        best_avg = best.get("average") or known.get("best_average")
        has_error = parsed.get("has_error_or_timeout")
        completed = parsed.get("completed") or ""
        is_complete = str(completed).startswith("10/10") or ("/" not in str(completed) and not has_error)
        accepted = avg is not None and (best_avg is None or avg < best_avg) and is_complete and not has_error
        decision = "accepted" if accepted else ("rejected" if has_error or not is_complete else "not_better")
        reason = self._decision_reason(parsed, best_avg, decision)

        entry = {
            "version": parsed.get("version"),
            "average": avg,
            "completed": completed,
            "decision": decision,
            "reason": reason,
            "cases": parsed.get("cases", {}),
            "has_error_or_timeout": has_error,
            "recorded_at": _now(),
        }
        known.setdefault("history", []).append(entry)
        if accepted:
            known["best_version"] = parsed.get("version")
            known["best_average"] = avg
            known["completed"] = completed
            best.update(
                {
                    "version": parsed.get("version"),
                    "path": "solvers/best/solver.py",
                    "average": avg,
                    "completed": completed,
                }
            )
            pending_path = self.state_store.load().get("pending_solver_path")
            if pending_path:
                pending_code = self._read(pending_path)
                (self.root / "solvers" / "best" / "solver.py").write_text(pending_code, encoding="utf-8")
                best["sha256"] = hashlib.sha256(pending_code.encode("utf-8")).hexdigest().upper()
        self.known_store.save(known)
        self.best_store.save(best)

        state = self.state_store.load()
        state.update(
            {
                "status": "READY",
                "pending_version": None,
                "pending_solver_path": None,
                "pending_created_at": None,
                "last_event": "feedback_ingested",
            }
        )
        self.state_store.save(state)

        return {"decision": decision, "reason": reason, "summary": f"{parsed.get('version')} {decision}: {reason}"}

    def _decision_reason(self, parsed: Dict[str, Any], best_avg: Optional[float], decision: str) -> str:
        if parsed.get("has_error_or_timeout"):
            return "出现 error/timeout 或完成率下降，拒绝保留。"
        if parsed.get("average") is None:
            return "未解析到平均分，仅记录原始反馈。"
        if decision == "accepted":
            return f"平均分 {parsed.get('average')} 优于当前 best {best_avg}，且无 error/timeout。"
        return f"平均分 {parsed.get('average')} 未优于当前 best {best_avg}，不更新 best。"

    def _write_reflection(self, version: str, parsed: Dict[str, Any], reflection: Dict[str, Any]) -> None:
        path = self.root / "reports" / "reflections" / f"{version}.md"
        cases = parsed.get("cases", {})
        case_lines = "\n".join(
            f"- {name}: score={info.get('score')} completion={info.get('completion')} time_ms={info.get('time_ms')}"
            for name, info in cases.items()
        )
        path.write_text(
            "# Reflection\n\n"
            f"## Version\n{version}\n\n"
            f"## Decision\n{reflection.get('decision')}\n\n"
            f"## Reason\n{reflection.get('reason')}\n\n"
            f"## Average\n{parsed.get('average')}\n\n"
            f"## Completed\n{parsed.get('completed')}\n\n"
            "## Cases\n"
            + case_lines
            + "\n",
            encoding="utf-8",
        )

    def _trace(self, mode: str, response: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "mode": mode,
            "steps": [
                {"label": "读取记忆", "kind": "memory", "accepted": True},
                {"label": "构造上下文", "kind": "context", "accepted": True},
                {"label": "DeepSeek/Mock 单次调用", "kind": "llm", "accepted": not self.deepseek.mock},
                {"label": "保存 Solver", "kind": "solver", "accepted": True},
                {"label": response.get("next_user_action", "等待平台反馈") if response else "等待平台反馈", "kind": "human", "accepted": True},
            ],
        }

    def _lab_trace(self, report: Dict[str, Any]) -> Dict[str, Any]:
        chosen = report.get("chosen", {})
        observations = report.get("observations", [])
        advice = report.get("strategy_advice") or {}
        steps = [
            {
                "label": (
                    "DeepSeek 策略建议："
                    + str(advice.get("strategy_focus") or advice.get("status") or "未返回")
                ),
                "kind": "llm",
                "accepted": advice.get("status") != "error",
            },
            {"label": "生成候选池", "kind": "memory", "accepted": True},
            {"label": "运行本地 scorer", "kind": "context", "accepted": True},
            {"label": "审计硬编码", "kind": "llm", "accepted": True},
        ]
        for row in observations[:4]:
            steps.append(
                {
                    "label": f"{row.get('name')} avg={_fmt(row.get('average_score'))} hard={row.get('hardcoded_pair_count')}",
                    "kind": "solver",
                    "accepted": row.get("name") == chosen.get("name"),
                }
            )
        steps.append(
            {
                "label": f"选择 {chosen.get('name', 'candidate')}，等待平台反馈",
                "kind": "human",
                "accepted": True,
            }
        )
        return {"mode": "agent_lab", "steps": steps}

    def _strategy_trace(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "mode": "strategy_advice",
            "steps": [
                {"label": "读取历史分数和失败假设", "kind": "memory", "accepted": True},
                {"label": "压缩上下文，只请求策略建议", "kind": "context", "accepted": True},
                {
                    "label": response.get("strategy_focus") or response.get("agent_message") or "DeepSeek 返回策略建议",
                    "kind": "llm",
                    "accepted": not response.get("_runtime", {}).get("mock_mode", False),
                },
                {"label": response.get("next_solver_brief") or "把建议交给本地候选生成器", "kind": "solver", "accepted": True},
            ],
        }

    def _save_agent_output(self, version: str, response: Dict[str, Any], solver_sha: str) -> None:
        output = dict(response)
        output["solver_sha256"] = solver_sha
        output["saved_at"] = _now()
        path = self.root / "memory" / "agent_outputs" / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_strategy_advice(self, version: str, response: Dict[str, Any]) -> None:
        path = self.root / "memory" / "strategy_advice" / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(response)
        payload["saved_at"] = _now()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _recent_agent_outputs(self, limit: int = 4) -> List[Dict[str, Any]]:
        root = self.root / "memory" / "agent_outputs"
        if not root.exists():
            return []
        outputs: List[Dict[str, Any]] = []
        for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            solver_code = data.pop("solver_code", "")
            data["solver_code_chars"] = len(solver_code)
            data["solver_code_sha256"] = hashlib.sha256(solver_code.encode("utf-8")).hexdigest().upper() if solver_code else data.get("solver_sha256")
            data["file"] = str(path.relative_to(self.root))
            outputs.append(data)
        return outputs

    def _recent_raw_feedbacks(self, limit: int = 4) -> List[Dict[str, Any]]:
        root = self.root / "memory" / "raw_feedback"
        if not root.exists():
            return []
        feedbacks: List[Dict[str, Any]] = []
        for path in sorted(root.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            raw = path.read_text(encoding="utf-8", errors="replace")
            feedbacks.append(
                {
                    "version": path.stem,
                    "file": str(path.relative_to(self.root)),
                    "chars": len(raw),
                    "excerpt": raw[:4000],
                }
            )
        return feedbacks

    def _recent_reflections(self, limit: int = 6) -> List[Dict[str, str]]:
        root = self.root / "reports" / "reflections"
        if not root.exists():
            return []
        rows: List[Dict[str, str]] = []
        for path in sorted(root.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            text = path.read_text(encoding="utf-8", errors="replace")
            rows.append({"version": path.stem, "file": str(path.relative_to(self.root)), "excerpt": text[:1200]})
        return rows

    def _case_score_analysis(self, known: Dict[str, Any]) -> Dict[str, Any]:
        history = known.get("history", [])
        latest = history[-1] if history else {}
        cases = latest.get("cases", {}) or {}
        scored = [
            {
                "case": name,
                "score": info.get("score"),
                "completion": info.get("completion"),
                "time_ms": info.get("time_ms"),
            }
            for name, info in cases.items()
            if isinstance(info, dict)
        ]
        scored_with_score = [row for row in scored if row.get("score") is not None]
        slow = sorted(
            [row for row in scored if row.get("time_ms") is not None],
            key=lambda row: float(row.get("time_ms") or 0),
            reverse=True,
        )[:3]
        worst = sorted(scored_with_score, key=lambda row: float(row.get("score") or 0), reverse=True)[:3]
        best_cases = sorted(scored_with_score, key=lambda row: float(row.get("score") or 0))[:3]
        return {
            "latest_version": latest.get("version"),
            "latest_average": latest.get("average"),
            "worst_cases": worst,
            "best_cases": best_cases,
            "slow_cases": slow,
            "has_error_or_timeout": latest.get("has_error_or_timeout", False),
            "decision": latest.get("decision", ""),
            "reason": latest.get("reason", ""),
        }

    def _next_version(self, prefix: str = "v") -> str:
        known = self.known_store.load()
        count = len(known.get("history", [])) + len(list((self.root / "solvers" / "generated").glob("*.py"))) + 1
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        if prefix == "v":
            return f"v{count:03d}_agent_{stamp}"
        return f"{prefix}_{count:03d}_{stamp}"

    def _latest_summary(self, known: Dict[str, Any]) -> Dict[str, Any]:
        history = known.get("history", [])
        return history[-1] if history else {}

    def _append_chat(self, role: str, content: str) -> None:
        state = self.state_store.load()
        state.setdefault("chat", []).append({"role": role, "content": content, "time": _now()})
        state["chat"] = state["chat"][-30:]
        self.state_store.save(state)

    def _system_prompt(self) -> str:
        return self._read("prompts/deepseek_system.md")

    def _strategy_prompt(self) -> str:
        return (
            "你是美团 AutoSolver 配送算法优化 Agent 的策略顾问。"
            "你不输出 solver_code，只输出严格 JSON。"
            "目标是在已知分数、case-level 分析、失败假设和算法 playbook 的基础上，"
            "提出下一轮最值得由本地工具生成/验证的算法方向。"
            "必须区分“单骑手/多骑手是解结构”与“greedy、flow/ILP-like、beam、local search、LNS、repair heuristic 是算法方法”。"
            "不要建议固定 Txxxx/Cxxx 映射或平台特例硬编码。"
            "JSON 字段必须包含：agent_message, version_name, strategy_focus, suggested_algorithms, "
            "experiment_plan, guardrails, expected_effect, rejected_options, next_solver_brief, reflection。"
        )

    def _read(self, rel_path: str) -> str:
        return (self.root / rel_path).read_text(encoding="utf-8")

    def _read_optional(self, rel_path: Optional[str]) -> str:
        if not rel_path:
            return ""
        path = self.root / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else ""


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _load_dotenv_upward(root: Path) -> List[str]:
    candidates: List[Path] = []
    for directory in [root, *root.parents]:
        path = directory / ".env"
        if path not in candidates:
            candidates.append(path)
    explicit = Path("E:/Python_project/.env")
    if explicit not in candidates:
        candidates.append(explicit)

    loaded: List[str] = []
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    continue
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
            loaded.append(str(path))
        except Exception:
            continue
    return loaded


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return clean[:96] or "candidate_solver"


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _first_float(obj: Dict[str, Any], keys: List[str]) -> Optional[float]:
    lower = {str(k).lower(): k for k in obj}
    for key in keys:
        real = lower.get(key.lower())
        if real is not None:
            value = _to_float(obj[real])
            if value is not None:
                return value
    return None


def _case_name_from_text(text: str) -> Optional[str]:
    for case in CASE_NAMES:
        if case in text:
            return case
    return None


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "--"


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
