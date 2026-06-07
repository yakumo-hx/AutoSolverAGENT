from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"
ARTIFACTS = PUBLIC / "artifacts"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize_text(value: str) -> str:
    value = value.replace(str(ROOT), "<LOCAL_PROJECT>/AutoSolverAGENT_GitHub")
    value = value.replace(str(ROOT).replace("\\", "/"), "<LOCAL_PROJECT>/AutoSolverAGENT_GitHub")
    value = re.sub(r"[A-Za-z]:\\(?:[^\\\s]+\\)*\.env", "<LOCAL_PROJECT>/.env", value)
    value = re.sub(r"[A-Za-z]:\\Python_project\\Hackathon\\AutoSolverAGENT_GitHub", "<LOCAL_PROJECT>/AutoSolverAGENT_GitHub", value)
    value = re.sub(r"sk-[A-Za-z0-9_\-]{12,}", "sk-<redacted>", value)
    value = re.sub(r"(DEEPSEEK_API_KEY\s*=\s*)\S+", r"\1<redacted>", value)
    return value


def sanitize(obj: Any) -> Any:
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, list):
        return [sanitize(item) for item in obj]
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if key in {"solver_code", "raw_feedback", "prompt", "messages"}:
                continue
            result[key] = sanitize(value)
        return result
    return obj


def compact_monitor() -> dict[str, Any]:
    monitor = load_json(ROOT / "memory" / "deepseek_monitor.json", {"runs": []})
    runs = []
    for run in monitor.get("runs", []):
        runs.append(
            {
                "id": run.get("id"),
                "kind": run.get("kind"),
                "label": run.get("label"),
                "model": run.get("model"),
                "mock_mode": bool(run.get("mock_mode")),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "first_token_at": run.get("first_token_at"),
                "first_token_ms": run.get("first_token_ms"),
                "finished_at": run.get("finished_at"),
                "elapsed_ms": run.get("elapsed_ms"),
                "chunk_count": run.get("chunk_count"),
                "output_chars": run.get("output_chars"),
                "reasoning_chars": run.get("reasoning_chars"),
                "finish_reason": run.get("finish_reason"),
                "usage": run.get("usage", {}),
                "request_summary": run.get("request_summary", {}),
                "events": run.get("events", []),
            }
        )
    return sanitize({"latest_run_id": monitor.get("latest_run_id"), "runs": runs})


def reflection_entries(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for item in history:
        version = item.get("version")
        if not version:
            continue
        cases = item.get("cases", {}) if isinstance(item.get("cases"), dict) else {}
        case_lines = "\n".join(
            f"- {name}: score={info.get('score')} completion={info.get('completion')} time_ms={info.get('time_ms')}"
            for name, info in cases.items()
            if isinstance(info, dict)
        )
        text = "\n\n".join(
            [
                "# Reflection",
                "## Version\n" + str(version),
                "## Decision\n" + str(item.get("decision") or "recorded"),
                "## Reason\n" + str(item.get("reason") or ""),
                "## Average\n" + str(item.get("average") or "--"),
                "## Completed\n" + str(item.get("completed") or "--"),
                "## Cases\n" + (case_lines or "--"),
            ]
        )
        entries.append(
            {
                "version": version,
                "decision": item.get("decision"),
                "average": item.get("average"),
                "completed": item.get("completed"),
                "reason": item.get("reason"),
                "text": sanitize_text(text.strip()),
            }
        )
    return entries


def build_state() -> dict[str, Any]:
    known = load_json(ROOT / "memory" / "known_results.json", {})
    run_state = load_json(ROOT / "memory" / "run_state.json", {})
    best_registry = load_json(ROOT / "memory" / "best_solver_registry.json", {})
    history = known.get("history", [])
    latest = run_state.get("latest_feedback") or (history[-1] if history else {})
    pending_path = run_state.get("pending_solver_path")
    pending_code = ""
    if pending_path and (ROOT / pending_path).exists():
        pending_code = (ROOT / pending_path).read_text(encoding="utf-8")

    best_path = best_registry.get("path") or known.get("best_solver_path") or "solver/solver.py"
    best_code = ""
    if (ROOT / best_path).exists():
        best_code = (ROOT / best_path).read_text(encoding="utf-8")

    score_series = [
        {
            "version": item.get("version"),
            "average": item.get("average"),
            "completed": item.get("completed"),
            "decision": item.get("decision"),
        }
        for item in history
        if item.get("average") is not None
    ]
    latest_cases = latest.get("cases", {})
    case_rows = [
        {"case": name, **info}
        for name, info in sorted(latest_cases.items(), key=lambda pair: pair[0])
        if isinstance(info, dict)
    ]
    worst_cases = sorted(
        case_rows,
        key=lambda row: float(row.get("score") or 0),
        reverse=True,
    )[:3]

    return sanitize(
        {
            "mode": "static_replay",
            "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "status": run_state.get("status"),
            "pending_version": run_state.get("pending_version"),
            "pending_solver_path": pending_path,
            "pending_solver_code": pending_code,
            "best_solver_code": best_code,
            "best": {
                "version": best_registry.get("version") or known.get("best_version"),
                "average": best_registry.get("average") or known.get("best_average"),
                "completed": best_registry.get("completed") or known.get("completed"),
                "sha256": best_registry.get("sha256") or known.get("sha256"),
                "path": best_path,
            },
            "latest_result": latest,
            "latest_cases": latest_cases,
            "score_series": score_series,
            "timeline": history,
            "chat": run_state.get("chat", [])[-18:],
            "recent_reflections": reflection_entries(history[-8:]),
            "score_analysis": {
                "best_average": best_registry.get("average") or known.get("best_average"),
                "latest_average": latest.get("average"),
                "delta_vs_best": round(float(latest.get("average") or 0) - float(best_registry.get("average") or known.get("best_average") or 0), 4),
                "worst_cases": worst_cases,
            },
        }
    )


def build_manifest(state: dict[str, Any], monitor: dict[str, Any]) -> dict[str, Any]:
    runs = monitor.get("runs", [])
    real_runs = [run for run in runs if not run.get("mock_mode") and run.get("status") == "completed"]
    return {
        "project": "AutoSolverAGENT",
        "site": "static_replay_dashboard",
        "generated_from": [
            "memory/known_results.json",
            "memory/run_state.json",
            "memory/deepseek_monitor.json",
            "reports/reflections/*.md",
        ],
        "no_backend_required": True,
        "api_key_committed": False,
        "best_solver": state.get("best"),
        "pending_candidate": {
            "version": state.get("pending_version"),
            "path": state.get("pending_solver_path"),
        },
        "platform_feedback_count": len(state.get("timeline", [])),
        "real_deepseek_completed_runs": len(real_runs),
        "latest_deepseek_run_id": monitor.get("latest_run_id"),
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    source_assets = ROOT / "frontend" / "pixel-assets.js"
    target_assets = PUBLIC / "pixel-assets.js"
    if source_assets.exists():
        shutil.copyfile(source_assets, target_assets)

    state = build_state()
    monitor = compact_monitor()
    write_json(DATA / "state.json", state)
    write_json(DATA / "ds_monitor.json", monitor)
    write_json(DATA / "score_history.json", state.get("score_series", []))
    write_json(DATA / "reflections.json", state.get("recent_reflections", []))
    write_json(DATA / "run_manifest.json", build_manifest(state, monitor))

    if state.get("best_solver_code"):
        (ARTIFACTS / "best_solver.py").write_text(state["best_solver_code"], encoding="utf-8")
    if state.get("pending_solver_code") and state.get("pending_version"):
        (ARTIFACTS / f"{state['pending_version']}.py").write_text(state["pending_solver_code"], encoding="utf-8")

    print(f"static replay exported to {PUBLIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
