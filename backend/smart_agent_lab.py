from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LabCandidate:
    name: str
    source: str
    hypothesis: str
    solver_code: str


class SmartAgentLab:
    """Local tool loop: candidate pool -> scorer -> hardcode audit -> selection."""

    def __init__(
        self,
        root: Path,
        deepseek_client: Any = None,
        system_prompt: str = "",
        runtime: Optional[Dict[str, str]] = None,
    ) -> None:
        self.root = root
        self.deepseek = deepseek_client
        self.system_prompt = system_prompt
        self.runtime = runtime or {}

    def run(self, base_solver_code: str, context: Dict[str, Any], run_id: str, iterations: int = 3) -> Dict[str, Any]:
        suite = self._build_suite()
        lab_dir = self.root / "solvers" / "lab" / run_id
        lab_dir.mkdir(parents=True, exist_ok=True)

        strategy_advice = self._deepseek_strategy_advice(context, run_id, iterations)
        lab_context = dict(context)
        lab_context["strategy_advice"] = strategy_advice

        candidates = self._candidate_pool(base_solver_code, lab_context, run_id, iterations)
        evaluated: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []

        for candidate in candidates:
            self._evaluate_candidate(candidate, lab_dir, suite, evaluated, observations)

        for candidate in self._deepseek_candidate_pool(lab_context, run_id, observations, iterations):
            self._evaluate_candidate(candidate, lab_dir, suite, evaluated, observations)

        chosen = self._choose_candidate(evaluated)
        chosen_code = (self.root / chosen["path"]).read_text(encoding="utf-8")
        report = {
            "run_id": run_id,
            "generated_at": _now(),
            "suite": {
                "case_count": len(suite["cases"]),
                "cases": [
                    {
                        "name": c["name"],
                        "kind": c["kind"],
                        "task_count": c["task_count"],
                        "courier_count": c["courier_count"],
                        "candidate_count": c["candidate_count"],
                    }
                    for c in suite["cases"]
                ],
            },
            "strategy_advice": strategy_advice,
            "observations": observations,
            "candidates": evaluated,
            "chosen": {
                "name": chosen["name"],
                "path": chosen["path"],
                "sha256": chosen["sha256"],
                "selection_score": chosen["selection_score"],
                "average_score": chosen["evaluation"].get("average_score"),
                "valid_cases": chosen["evaluation"].get("valid_cases"),
                "case_count": chosen["evaluation"].get("case_count"),
                "hardcoded_pair_count": chosen["hardcode_audit"].get("explicit_pair_count"),
            },
            "policy": (
                "优先选择本地 suite 全合法、无固定 Txxxx/Cxxx 映射、平均分低的候选。"
                "当前 suite 是脱敏/合成验证，不等价于平台隐藏分。"
            ),
        }
        self._write_report(report)

        return {
            "agent_message": (
                "Agent Lab 已完成本地工具循环：先请求策略建议，再生成候选、运行脱敏/合成 case、审计硬编码、"
                f"选择 {chosen['name']}。"
            ),
            "version_name": run_id,
            "hypothesis": chosen.get("hypothesis", "local tool selected candidate"),
            "changes": [
                "不再只做单次 LLM 返回；增加本地 scorer/runner/hardcode-audit 工具循环",
                "候选进入 solvers/lab，最终候选进入 solvers/generated",
                "选择策略偏向可泛化 clean solver，而不是固定平台 ID 映射",
                "DeepSeek 策略建议作为第一步写入 Lab report，用于指导下一轮候选方向",
            ],
            "risk_notes": [
                "本地 synthetic suite 不能替代平台隐藏评测",
                "DeepSeek 无 key 时使用本地模板候选；有 key 时可追加 LLM 候选进入同一工具循环",
            ],
            "expected_effect": self._expected_effect(chosen),
            "solver_code": chosen_code,
            "reflection": self._reflection(report),
            "next_user_action": "请复制 Agent Lab 选出的 Solver 上传平台；拿到平台/F12 结果后粘贴反馈。",
            "lab_report": report,
        }

    def _evaluate_candidate(
        self,
        candidate: LabCandidate,
        lab_dir: Path,
        suite: Dict[str, Any],
        evaluated: List[Dict[str, Any]],
        observations: List[Dict[str, Any]],
    ) -> None:
        round_no = len(evaluated) + 1
        candidate_path = lab_dir / f"{round_no:02d}_{_safe_name(candidate.name)}.py"
        candidate_path.write_text(candidate.solver_code, encoding="utf-8", newline="\n")
        audit = self._hardcode_audit(candidate.solver_code)
        evaluation = self._evaluate_solver(candidate_path, suite)
        record = {
            "round": round_no,
            "name": candidate.name,
            "source": candidate.source,
            "hypothesis": candidate.hypothesis,
            "path": str(candidate_path.relative_to(self.root)),
            "sha256": hashlib.sha256(candidate.solver_code.encode("utf-8")).hexdigest().upper(),
            "hardcode_audit": audit,
            "evaluation": evaluation,
        }
        record["selection_score"] = self._selection_score(record)
        evaluated.append(record)
        observations.append(self._observation_summary(record))

    def _candidate_pool(
        self, base_solver_code: str, context: Dict[str, Any], run_id: str, iterations: int
    ) -> List[LabCandidate]:
        return [
            LabCandidate(
                name="current_best_reference",
                source="best_solver",
                hypothesis="当前 best 作为参照组；如果它赢但有硬编码，报告会明确标红。",
                solver_code=base_solver_code,
            ),
            LabCandidate(
                name="clean_greedy_portfolio",
                source="local_template",
                hypothesis="去掉固定 ID，使用多排序贪心组合和局部替换。",
                solver_code=CLEAN_GREEDY_PORTFOLIO_SOLVER,
            ),
            LabCandidate(
                name="clean_pair_density",
                source="local_template",
                hypothesis="优先 pair/bundle 的收益密度，适合骑手较少或合单收益明显的 case。",
                solver_code=CLEAN_PAIR_DENSITY_SOLVER,
            ),
            LabCandidate(
                name="clean_multi_courier_guarded",
                source="local_template",
                hypothesis="对低意愿单任务尝试 guarded multi-courier，提升完成概率。",
                solver_code=CLEAN_MULTI_COURIER_SOLVER,
            ),
        ]

    def _deepseek_candidate_pool(
        self,
        context: Dict[str, Any],
        run_id: str,
        observations: List[Dict[str, Any]],
        iterations: int,
    ) -> List[LabCandidate]:
        if not self._can_call_deepseek():
            return []

        max_llm_candidates = 1 if iterations > 0 else 0
        candidates: List[LabCandidate] = []
        for idx in range(max_llm_candidates):
            llm_context = self._compact_llm_context(context, run_id, idx + 1, observations)
            runtime = dict(self.runtime)
            runtime.setdefault("deepseek_timeout_s", "180")
            runtime.setdefault("max_tokens", "32000")
            runtime.setdefault("deepseek_stream", "true")
            runtime.setdefault("monitor_kind", "solver_generation")
            runtime.setdefault("monitor_label", f"DS Solver 生成 {run_id}")
            try:
                response = self.deepseek.complete_json(self.system_prompt, llm_context, runtime=runtime)
            except Exception as exc:
                candidates.append(
                    LabCandidate(
                        name=f"deepseek_timeout_or_error_{idx + 1}",
                        source="deepseek_error",
                        hypothesis=f"DeepSeek 限时调用失败：{exc!r}",
                        solver_code=CLEAN_GREEDY_PORTFOLIO_SOLVER,
                    )
                )
                continue
            solver_code = response.get("solver_code", "")
            if isinstance(solver_code, str) and "def solve" in solver_code:
                candidates.append(
                    LabCandidate(
                        name=response.get("version_name") or f"deepseek_candidate_{idx + 1}",
                        source="deepseek",
                        hypothesis=response.get("hypothesis", "DeepSeek generated candidate"),
                        solver_code=solver_code,
                    )
                )
        return candidates

    def _deepseek_strategy_advice(self, context: Dict[str, Any], run_id: str, iterations: int) -> Dict[str, Any]:
        if iterations <= 0:
            return {"status": "skipped", "agent_message": "iterations=0，本轮跳过 DeepSeek 策略建议。"}
        if not self._can_call_deepseek():
            return {"status": "skipped", "agent_message": "未检测到 DeepSeek key，本轮跳过真实策略建议。"}

        known = context.get("known_results", {})
        history = known.get("history", []) if isinstance(known, dict) else []
        advice_context = {
            "mode": "strategy_advice",
            "lab_run_id": run_id,
            "task_card": context.get("task_card", ""),
            "platform_constraints": context.get("platform_constraints", ""),
            "algorithm_playbook": context.get("algorithm_playbook", ""),
            "failed_hypotheses": context.get("failed_hypotheses", ""),
            "latest_result_summary": context.get("latest_result_summary", {}),
            "score_analysis": context.get("score_analysis", {}),
            "history_tail": history[-8:],
            "best_solver_registry": context.get("best_solver_registry", {}),
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
        runtime = dict(self.runtime)
        runtime.setdefault("deepseek_timeout_s", "75")
        runtime.setdefault("max_tokens", "2400")
        runtime.setdefault("deepseek_stream", "true")
        runtime.setdefault("monitor_kind", "strategy_advice")
        runtime.setdefault("monitor_label", f"Lab 策略建议 {run_id}")
        try:
            response = self.deepseek.complete_json(STRATEGY_ADVICE_PROMPT, advice_context, runtime=runtime)
        except Exception as exc:
            return {"status": "error", "agent_message": "DeepSeek 策略建议失败。", "error": repr(exc)}
        if isinstance(response, dict):
            response.setdefault("status", "completed")
            return response
        return {"status": "error", "agent_message": "DeepSeek 策略建议不是 JSON object。"}

    def _can_call_deepseek(self) -> bool:
        request_key = self.runtime.get("deepseek_api_key", "").strip()
        return self.deepseek is not None and bool(request_key or not getattr(self.deepseek, "mock", True))

    def _compact_llm_context(
        self,
        context: Dict[str, Any],
        run_id: str,
        candidate_index: int,
        observations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        known = context.get("known_results", {})
        history = known.get("history", []) if isinstance(known, dict) else []
        return {
            "mode": "agent_lab_candidate",
            "lab_run_id": run_id,
            "candidate_index": candidate_index,
            "task_card": context.get("task_card", ""),
            "platform_constraints": context.get("platform_constraints", ""),
            "algorithm_playbook": context.get("algorithm_playbook", ""),
            "latest_result_summary": context.get("latest_result_summary", {}),
            "score_analysis": context.get("score_analysis", {}),
            "history_tail": history[-6:],
            "local_observations": observations,
            "strategy_advice": context.get("strategy_advice", {}),
            "clean_reference_solver_code": CLEAN_GREEDY_PORTFOLIO_SOLVER,
            "required_output_schema": context.get("required_output_schema", {}),
            "local_tool_contract": (
                "输出完整 solver_code。不要包含固定 Txxxx/Cxxx 答案表。"
                "候选会立刻通过本地 scorer、runtime check 和 hardcode audit。"
                "优先改进 clean_reference_solver_code，而不是复制当前 hardcoded best。"
                "先参考 strategy_advice，但若建议会导致无 guard 爆搜或硬编码，必须拒绝。"
            ),
        }

    def _build_suite(self) -> Dict[str, Any]:
        cases = []
        sample_path = self.root / "data" / "sample_case.tsv"
        if sample_path.exists():
            text = sample_path.read_text(encoding="utf-8")
            cases.append(self._case_meta("sample_case", "sample", text))
        cases.append(self._case_meta("synth_tiny_pair", "tiny", self._synthetic_case(6, 10, 41, pair_ratio=0.38, low_w=False)))
        cases.append(self._case_meta("synth_regular30", "regular", self._synthetic_case(30, 64, 201, pair_ratio=0.28, low_w=False)))
        cases.append(self._case_meta("synth_low_willingness", "low_w", self._synthetic_case(24, 58, 501, pair_ratio=0.18, low_w=True)))
        cases.append(self._case_meta("synth_scarce_couriers", "scarce", self._synthetic_case(32, 20, 401, pair_ratio=0.36, low_w=False)))
        return {"cases": cases}

    def _case_meta(self, name: str, kind: str, input_text: str) -> Dict[str, Any]:
        task_ids = set()
        courier_ids = set()
        candidate_count = 0
        for raw in input_text.splitlines():
            parts = raw.strip().split()
            if len(parts) < 4 or parts[0] == "task_id_list":
                continue
            candidate_count += 1
            courier_ids.add(parts[1])
            for task_id in parts[0].split(","):
                task_ids.add(task_id)
        return {
            "name": name,
            "kind": kind,
            "input_text": input_text,
            "task_count": len(task_ids),
            "courier_count": len(courier_ids),
            "candidate_count": candidate_count,
        }

    def _synthetic_case(
        self, task_count: int, courier_count: int, seed: int, pair_ratio: float, low_w: bool
    ) -> str:
        rng = random.Random(seed)
        tasks = [f"T{i:04d}" for i in range(task_count)]
        couriers = [f"C{i:03d}" for i in range(courier_count)]
        rows = ["task_id_list\tcourier_id\ttotal_score\twillingness"]
        used = set()

        def add(task_key: str, courier_id: str, score: float, willingness: float) -> None:
            key = (task_key, courier_id)
            if key in used:
                return
            used.add(key)
            rows.append(f"{task_key}\t{courier_id}\t{score:.4f}\t{willingness:.4f}")

        for task in tasks:
            degree = 3 if courier_count <= task_count else 5
            if low_w:
                degree += 2
            for courier in rng.sample(couriers, min(degree, courier_count)):
                base = rng.uniform(18.0, 92.0)
                willingness = rng.uniform(0.18, 0.52) if low_w else rng.uniform(0.45, 0.94)
                add(task, courier, base, willingness)

        pair_attempts = int(task_count * courier_count * pair_ratio / 2)
        for _ in range(pair_attempts):
            t1, t2 = rng.sample(tasks, 2)
            task_key = ",".join(sorted([t1, t2]))
            courier = rng.choice(couriers)
            score = rng.uniform(42.0, 160.0)
            willingness = rng.uniform(0.18, 0.56) if low_w else rng.uniform(0.38, 0.86)
            add(task_key, courier, score, willingness)

        return "\n".join(rows) + "\n"

    def _evaluate_solver(self, solver_path: Path, suite: Dict[str, Any]) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="autosolver_suite_") as tmp:
            suite_path = Path(tmp) / "suite.json"
            suite_path.write_text(json.dumps(suite, ensure_ascii=False), encoding="utf-8")
            cmd = [sys.executable, str(self.root / "backend" / "solver_eval_worker.py"), str(solver_path), str(suite_path)]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.root),
                    text=True,
                    capture_output=True,
                    timeout=8,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {
                    "case_count": len(suite["cases"]),
                    "valid_cases": 0,
                    "average_score": None,
                    "max_runtime_ms": 8000.0,
                    "timeout": True,
                    "cases": [],
                    "errors": ["local evaluation timeout"],
                }
        try:
            data = json.loads(proc.stdout.strip() or "{}")
        except json.JSONDecodeError:
            data = {"error": proc.stdout[-1000:], "stderr": proc.stderr[-1000:]}
        if proc.returncode != 0 and "error" not in data:
            data["error"] = proc.stderr[-1000:] or f"returncode={proc.returncode}"
        data["timeout"] = False
        return data

    def _hardcode_audit(self, code: str) -> Dict[str, Any]:
        pair_pattern = re.compile(r'\("T\d{4}(?:,T\d{4})?",\s*"C\d{3}"\)')
        explicit_pairs = pair_pattern.findall(code)
        task_ids = set(re.findall(r'"(T\d{4})"', code))
        courier_ids = set(re.findall(r'"(C\d{3})"', code))
        suspicious_names = re.findall(r"hard_[A-Za-z0-9_]*|scarce_[A-Za-z0-9_]*|direct_[A-Za-z0-9_]*", code)
        return {
            "explicit_pair_count": len(explicit_pairs),
            "unique_task_literal_count": len(task_ids),
            "unique_courier_literal_count": len(courier_ids),
            "suspicious_name_count": len(suspicious_names),
            "sample_pairs": explicit_pairs[:8],
            "risk": "high" if len(explicit_pairs) >= 5 else ("medium" if task_ids or courier_ids else "low"),
        }

    def _selection_score(self, record: Dict[str, Any]) -> float:
        evaluation = record["evaluation"]
        average = evaluation.get("average_score")
        if average is None:
            average = 1_000_000.0
        invalid = int(evaluation.get("case_count") or 0) - int(evaluation.get("valid_cases") or 0)
        hardcode_pairs = int(record["hardcode_audit"].get("explicit_pair_count") or 0)
        timeout = 1 if evaluation.get("timeout") else 0
        return float(average) + invalid * 10_000.0 + timeout * 100_000.0 + hardcode_pairs * 250.0

    def _choose_candidate(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        clean_valid = [
            r
            for r in records
            if r["hardcode_audit"].get("explicit_pair_count") == 0
            and r["evaluation"].get("valid_cases") == r["evaluation"].get("case_count")
            and not r["evaluation"].get("timeout")
        ]
        pool = clean_valid or records
        return sorted(pool, key=lambda r: (r["selection_score"], r["evaluation"].get("average_score") or math.inf))[0]

    def _observation_summary(self, record: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = record["evaluation"]
        return {
            "round": record["round"],
            "name": record["name"],
            "source": record["source"],
            "average_score": evaluation.get("average_score"),
            "valid_cases": f"{evaluation.get('valid_cases')}/{evaluation.get('case_count')}",
            "max_runtime_ms": evaluation.get("max_runtime_ms"),
            "hardcode_risk": record["hardcode_audit"].get("risk"),
            "hardcoded_pair_count": record["hardcode_audit"].get("explicit_pair_count"),
            "selection_score": record["selection_score"],
        }

    def _expected_effect(self, chosen: Dict[str, Any]) -> str:
        ev = chosen["evaluation"]
        audit = chosen["hardcode_audit"]
        return (
            f"本地 suite average={ev.get('average_score')}, valid={ev.get('valid_cases')}/{ev.get('case_count')}, "
            f"hardcoded_pairs={audit.get('explicit_pair_count')}。"
        )

    def _reflection(self, report: Dict[str, Any]) -> str:
        chosen = report["chosen"]
        lines = [
            "这版已经不是单次聊天式返回，而是经过本地工具循环筛选。",
            f"策略建议状态：{report.get('strategy_advice', {}).get('status', '--')}。",
            f"候选数量：{len(report['candidates'])}。",
            f"选中：{chosen['name']}，本地平均分 {chosen['average_score']}，合法 {chosen['valid_cases']}/{chosen['case_count']}。",
            f"硬编码固定映射数量：{chosen['hardcoded_pair_count']}。",
            "下一步应把平台真实反馈粘回工作台，用真实分数校正本地 synthetic suite 的偏差。",
        ]
        return "\n".join(lines)

    def _write_report(self, report: Dict[str, Any]) -> None:
        out_dir = self.root / "reports" / "lab"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"{report['run_id']}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path = out_dir / f"{report['run_id']}.md"
        obs = "\n".join(
            "- {name}: avg={average_score}, valid={valid_cases}, hardcode={hardcoded_pair_count}, score={selection_score}".format(
                **row
            )
            for row in report["observations"]
        )
        advice = report.get("strategy_advice", {})
        md_path.write_text(
            "# Agent Lab Report\n\n"
            f"Run: `{report['run_id']}`\n\n"
            "## Strategy Advice\n"
            f"- status: {advice.get('status', '--')}\n"
            f"- focus: {advice.get('strategy_focus', advice.get('agent_message', '--'))}\n\n"
            "## Chosen\n"
            f"- name: {report['chosen']['name']}\n"
            f"- average_score: {report['chosen']['average_score']}\n"
            f"- valid: {report['chosen']['valid_cases']}/{report['chosen']['case_count']}\n"
            f"- hardcoded_pair_count: {report['chosen']['hardcoded_pair_count']}\n\n"
            "## Observations\n"
            f"{obs}\n",
            encoding="utf-8",
        )


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name).strip())
    return clean[:80] or "candidate"


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


STRATEGY_ADVICE_PROMPT = (
    "你是美团 AutoSolver 配送算法优化 Agent 的策略顾问。"
    "你不输出 solver_code，只输出严格 JSON。"
    "目标是在已知分数、case-level 分析、失败假设和算法 playbook 的基础上，"
    "提出下一轮最值得由本地工具生成/验证的算法方向。"
    "必须区分“单骑手/多骑手是解结构”与“greedy、flow/ILP-like、beam、local search、LNS、repair heuristic 是算法方法”。"
    "不要建议固定 Txxxx/Cxxx 映射或平台特例硬编码。"
    "JSON 字段必须包含：agent_message, version_name, strategy_focus, suggested_algorithms, "
    "experiment_plan, guardrails, expected_effect, rejected_options, next_solver_brief, reflection。"
)


CLEAN_SOLVER_COMMON = r'''
def solve(input_text: str) -> list:
    try:
        eps = 1e-9
        rows_raw = []
        best = {}
        tasks_seen = {}
        for line_no, raw in enumerate(input_text.splitlines()):
            parts = raw.strip().split()
            if len(parts) < 4 or parts[0] == "task_id_list":
                continue
            task_key = parts[0].strip()
            courier_id = parts[1].strip()
            try:
                total_score = float(parts[2])
                willingness = float(parts[3])
            except Exception:
                continue
            tasks = tuple(t.strip() for t in task_key.split(",") if t.strip())
            if not tasks:
                continue
            task_count = len(tasks)
            expected_cost = willingness * total_score + (1.0 - willingness) * 100.0 * task_count
            benefit = 100.0 * task_count - expected_cost
            rec = [task_key, tasks, courier_id, expected_cost, benefit, total_score, willingness, task_count, line_no]
            key = (task_key, courier_id)
            old = best.get(key)
            if old is None or (expected_cost, line_no) < (old[3], old[8]):
                best[key] = rec
            for t in tasks:
                tasks_seen[t] = 1
        rows = list(best.values())
        if not rows:
            return []
        all_tasks = sorted(tasks_seen)
        by_task = {}
        by_key = {}
        by_courier = {}
        for i, row in enumerate(rows):
            by_key.setdefault(row[0], []).append(i)
            by_courier.setdefault(row[2], []).append(i)
            for t in row[1]:
                by_task.setdefault(t, []).append(i)
        for d in (by_task, by_key, by_courier):
            for key in d:
                d[key].sort(key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], -rows[i][6], rows[i][0], rows[i][2]))

        def multi_cost(indices):
            if not indices:
                return 0.0
            tasks = rows[indices[0]][1]
            fail = 1.0
            weighted = 0.0
            denom = 0.0
            for idx in indices:
                p = rows[idx][6]
                if p < 0.0:
                    p = 0.0
                if p > 1.0:
                    p = 1.0
                fail *= (1.0 - p)
                weighted += p * rows[idx][5]
                denom += p
            done = 1.0 - fail
            accepted_score = weighted / denom if denom > eps else 100.0 * len(tasks)
            return done * accepted_score + (1.0 - done) * 100.0 * len(tasks)

        def row_gain(idx):
            return 100.0 * rows[idx][7] - multi_cost([idx])

        def clean(sol):
            used_c = {}
            covered = {}
            out = []
            for item in sol:
                if isinstance(item, int):
                    cand = [item]
                else:
                    cand = list(item)
                if not cand:
                    continue
                tasks = rows[cand[0]][1]
                bad = False
                seen_local = {}
                for idx in cand:
                    if idx < 0 or idx >= len(rows) or rows[idx][1] != tasks:
                        bad = True
                        break
                    c = rows[idx][2]
                    if c in used_c or c in seen_local:
                        bad = True
                        break
                    seen_local[c] = 1
                for t in tasks:
                    if t in covered:
                        bad = True
                        break
                if bad:
                    continue
                gain = 100.0 * len(tasks) - multi_cost(cand)
                if gain <= eps:
                    continue
                for idx in cand:
                    used_c[rows[idx][2]] = 1
                for t in tasks:
                    covered[t] = 1
                out.append(cand)
            return out

        def score_sol(sol):
            cleaned = clean(sol)
            covered = {}
            gain = 0.0
            for cand in cleaned:
                gain += 100.0 * len(rows[cand[0]][1]) - multi_cost(cand)
                for t in rows[cand[0]][1]:
                    covered[t] = 1
            return cleaned, gain, len(covered)

        def greedy(order):
            used_c = {}
            covered = {}
            sol = []
            for idx in order:
                row = rows[idx]
                if row[2] in used_c:
                    continue
                if any(t in covered for t in row[1]):
                    continue
                if row_gain(idx) <= eps:
                    continue
                sol.append([idx])
                used_c[row[2]] = 1
                for t in row[1]:
                    covered[t] = 1
            return sol

        def improve(sol):
            sol, best_gain, _ = score_sol(sol)
            for _ in range(3):
                changed = False
                used_c = {}
                covered = {}
                owner_c = {}
                owner_t = {}
                for pos, cand in enumerate(sol):
                    for idx in cand:
                        used_c[rows[idx][2]] = 1
                        owner_c[rows[idx][2]] = pos
                    for t in rows[cand[0]][1]:
                        covered[t] = 1
                        owner_t[t] = pos
                order = sorted(range(len(rows)), key=lambda i: (-row_gain(i), rows[i][3], rows[i][0], rows[i][2]))[:3500]
                for idx in order:
                    row = rows[idx]
                    conflicts = {}
                    if row[2] in owner_c:
                        conflicts[owner_c[row[2]]] = 1
                    for t in row[1]:
                        if t in owner_t:
                            conflicts[owner_t[t]] = 1
                    trial = []
                    for pos, cand in enumerate(sol):
                        if pos not in conflicts:
                            trial.append(cand)
                    trial.append([idx])
                    trial, gain, _ = score_sol(trial)
                    if gain > best_gain + eps:
                        sol = trial
                        best_gain = gain
                        changed = True
                        break
                if not changed:
                    break
            return sol

        orders = []
        orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][3] / rows[i][7], rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (-rows[i][4], rows[i][3], rows[i][0], rows[i][2])))
        orders.append(sorted(range(len(rows)), key=lambda i: (-rows[i][6], rows[i][3], -rows[i][4], rows[i][0], rows[i][2])))
        EXTRA_ORDERS

        best_sol = []
        best_gain = -1.0
        for order in orders:
            sol = improve(greedy(order))
            sol, gain, _ = score_sol(sol)
            if gain > best_gain + eps:
                best_sol = sol
                best_gain = gain

        EXTRA_SEARCH

        result = []
        best_sol.sort(key=lambda cand: (rows[cand[0]][0].split(",")[0], rows[cand[0]][0], ",".join(rows[i][2] for i in cand)))
        for cand in best_sol:
            result.append((rows[cand[0]][0], [rows[i][2] for i in cand]))
        return result
    except Exception:
        return []
'''


CLEAN_GREEDY_PORTFOLIO_SOLVER = CLEAN_SOLVER_COMMON.replace(
    "EXTRA_ORDERS",
    "orders.append(sorted(range(len(rows)), key=lambda i: (len(by_task.get(rows[i][1][0], [])) if rows[i][1] else 999999, rows[i][3] / rows[i][7], -rows[i][4], rows[i][0], rows[i][2])))",
).replace(
    "EXTRA_SEARCH",
    "pass",
)


CLEAN_PAIR_DENSITY_SOLVER = CLEAN_SOLVER_COMMON.replace(
    "EXTRA_ORDERS",
    "orders.append(sorted(range(len(rows)), key=lambda i: (-rows[i][7], rows[i][3] / rows[i][7], -rows[i][4], rows[i][0], rows[i][2])))",
).replace(
    "EXTRA_SEARCH",
    "pass",
)


CLEAN_MULTI_COURIER_SOLVER = CLEAN_SOLVER_COMMON.replace(
    "EXTRA_ORDERS",
    "orders.append(sorted(range(len(rows)), key=lambda i: (rows[i][7], -rows[i][6], rows[i][3], rows[i][0], rows[i][2])))",
).replace(
    "EXTRA_SEARCH",
    r'''
        if len(all_tasks) <= 36:
            base = best_sol[:]
            for limit in (2, 3):
                trial = []
                used_extra = {}
                covered_keys = {}
                for cand in base:
                    task_key = rows[cand[0]][0]
                    if rows[cand[0]][7] == 1 and rows[cand[0]][6] < 0.62:
                        options = []
                        for idx in by_key.get(task_key, []):
                            if idx in cand:
                                options.append(idx)
                            elif rows[idx][2] not in used_extra and row_gain(idx) > -20.0:
                                options.append(idx)
                            if len(options) >= limit:
                                break
                        trial.append(options)
                        for idx in options:
                            used_extra[rows[idx][2]] = 1
                    else:
                        trial.append(cand)
                        for idx in cand:
                            used_extra[rows[idx][2]] = 1
                trial, gain, _ = score_sol(trial)
                if gain > best_gain + eps:
                    best_sol = trial
                    best_gain = gain
    ''',
)
