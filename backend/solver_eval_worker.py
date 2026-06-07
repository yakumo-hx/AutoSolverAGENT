from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from autosolver_agent.scorer import parse_case, validate_and_score


def _load_solver(path: Path):
    spec = importlib.util.spec_from_file_location(f"autosolver_candidate_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load solver: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    solve = getattr(module, "solve", None)
    if not callable(solve):
        raise RuntimeError("solver.py must define callable solve(input_text)")
    return solve


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return f"<LOCAL_PROJECT>/{path.name}"


def evaluate(solver_path: Path, suite_path: Path) -> Dict[str, Any]:
    solve = _load_solver(solver_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    case_rows: List[Dict[str, Any]] = []
    total_score = 0.0
    valid_count = 0
    max_runtime_ms = 0.0

    for case in suite["cases"]:
        name = case["name"]
        input_text = case["input_text"]
        case_data = parse_case(input_text)
        started = time.perf_counter()
        try:
            solution = solve(input_text)
            runtime_ms = (time.perf_counter() - started) * 1000.0
            valid, score, covered, errors = validate_and_score(case_data, solution)
        except Exception as exc:
            runtime_ms = (time.perf_counter() - started) * 1000.0
            valid, score, covered, errors = False, 100.0 * len(case_data.tasks), 0, [repr(exc)]

        max_runtime_ms = max(max_runtime_ms, runtime_ms)
        if valid:
            valid_count += 1
        total_score += score
        case_rows.append(
            {
                "case": name,
                "score": score,
                "valid": valid,
                "covered": covered,
                "task_count": len(case_data.tasks),
                "candidate_count": len(case_data.candidates),
                "courier_count": len(case_data.couriers),
                "runtime_ms": runtime_ms,
                "errors": errors[:5],
            }
        )

    average = total_score / len(case_rows) if case_rows else None
    return {
        "solver_path": _portable_path(solver_path),
        "case_count": len(case_rows),
        "valid_cases": valid_count,
        "average_score": average,
        "max_runtime_ms": max_runtime_ms,
        "cases": case_rows,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"error": "usage: solver_eval_worker.py solver.py suite.json"}))
        return 2
    try:
        result = evaluate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": repr(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
