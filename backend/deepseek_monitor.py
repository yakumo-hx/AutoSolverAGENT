from __future__ import annotations

import datetime as _dt
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional


class DeepSeekMonitor:
    """Small persisted event log for DeepSeek streaming calls."""

    def __init__(self, root: Path, max_runs: int = 20, max_events: int = 140, tail_chars: int = 6000) -> None:
        self.root = root
        self.path = root / "memory" / "deepseek_monitor.json"
        self.max_runs = max_runs
        self.max_events = max_events
        self.tail_chars = tail_chars
        self._lock = threading.Lock()
        self._recover_interrupted()

    def begin(
        self,
        kind: str,
        label: str,
        model: str,
        token_source: str,
        mock_mode: bool,
        request_summary: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> str:
        now = _now()
        clean_kind = _safe_name(kind or "deepseek")
        monitor_id = run_id or f"ds_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{clean_kind}"
        run = {
            "id": monitor_id,
            "kind": kind,
            "label": label,
            "model": model,
            "token_source": token_source,
            "mock_mode": bool(mock_mode),
            "status": "mock" if mock_mode else "started",
            "started_at": now,
            "started_epoch": time.time(),
            "first_token_at": None,
            "first_token_ms": None,
            "finished_at": None,
            "elapsed_ms": None,
            "chunk_count": 0,
            "output_chars": 0,
            "reasoning_chars": 0,
            "finish_reason": "",
            "usage": {},
            "error": "",
            "preview_tail": "",
            "request_summary": request_summary or {},
            "events": [
                {
                    "time": now,
                    "stage": "begin",
                    "message": label,
                    "status": "mock" if mock_mode else "started",
                }
            ],
        }
        with self._lock:
            data = self._load_unlocked()
            data["latest_run_id"] = monitor_id
            data.setdefault("runs", []).append(run)
            data["runs"] = data["runs"][-self.max_runs :]
            self._save_unlocked(data)
        return monitor_id

    def event(self, run_id: str, stage: str, message: str = "", status: Optional[str] = None, **extra: Any) -> None:
        self._mutate_run(run_id, lambda run: self._append_event(run, stage, message, status, extra))

    def delta(
        self,
        run_id: str,
        text: str = "",
        reasoning_chars: int = 0,
        usage: Optional[Dict[str, Any]] = None,
        finish_reason: str = "",
    ) -> None:
        def mutate(run: Dict[str, Any]) -> None:
            now_epoch = time.time()
            if text or reasoning_chars:
                if not run.get("first_token_at"):
                    run["first_token_at"] = _now()
                    run["first_token_ms"] = round((now_epoch - float(run.get("started_epoch") or now_epoch)) * 1000, 1)
                    self._append_event(run, "first_token", f"{run['first_token_ms']} ms", "streaming", {})
                run["status"] = "streaming"
            if text:
                run["chunk_count"] = int(run.get("chunk_count") or 0) + 1
                run["output_chars"] = int(run.get("output_chars") or 0) + len(text)
                run["preview_tail"] = (str(run.get("preview_tail") or "") + text)[-self.tail_chars :]
            if reasoning_chars:
                run["reasoning_chars"] = int(run.get("reasoning_chars") or 0) + reasoning_chars
            if usage:
                run["usage"] = usage
            if finish_reason:
                run["finish_reason"] = finish_reason

        self._mutate_run(run_id, mutate)

    def finish(
        self,
        run_id: str,
        status: str = "completed",
        message: str = "",
        usage: Optional[Dict[str, Any]] = None,
        finish_reason: str = "",
        error: str = "",
    ) -> None:
        def mutate(run: Dict[str, Any]) -> None:
            now_epoch = time.time()
            run["finished_at"] = _now()
            run["elapsed_ms"] = round((now_epoch - float(run.get("started_epoch") or now_epoch)) * 1000, 1)
            run["status"] = status
            if usage:
                run["usage"] = usage
            if finish_reason:
                run["finish_reason"] = finish_reason
            if error:
                run["error"] = error
            self._append_event(run, "finish", message or status, status, {"error": error} if error else {})

        self._mutate_run(run_id, mutate)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            data = self._load_unlocked()
        runs = data.get("runs", [])
        latest = None
        latest_id = data.get("latest_run_id")
        if latest_id:
            latest = next((row for row in reversed(runs) if row.get("id") == latest_id), None)
        if latest is None and runs:
            latest = runs[-1]
        now_epoch = time.time()
        copied_runs = []
        for run in runs[-8:]:
            copied = dict(run)
            if copied.get("status") in {"started", "streaming"}:
                copied["elapsed_ms"] = round((now_epoch - float(copied.get("started_epoch") or now_epoch)) * 1000, 1)
            copied.pop("started_epoch", None)
            copied_runs.append(copied)
        latest_copy = dict(latest) if latest else None
        if latest_copy and latest_copy.get("status") in {"started", "streaming"}:
            latest_copy["elapsed_ms"] = round((now_epoch - float(latest_copy.get("started_epoch") or now_epoch)) * 1000, 1)
        if latest_copy:
            latest_copy.pop("started_epoch", None)
        return {"latest": latest_copy, "runs": copied_runs}

    def _mutate_run(self, run_id: str, mutate: Any) -> None:
        with self._lock:
            data = self._load_unlocked()
            for run in data.get("runs", []):
                if run.get("id") == run_id:
                    mutate(run)
                    break
            self._save_unlocked(data)

    def _append_event(
        self,
        run: Dict[str, Any],
        stage: str,
        message: str,
        status: Optional[str],
        extra: Dict[str, Any],
    ) -> None:
        if status:
            run["status"] = status
        event = {"time": _now(), "stage": stage, "message": message}
        if status:
            event["status"] = status
        if extra:
            event.update(extra)
        run.setdefault("events", []).append(event)
        run["events"] = run["events"][-self.max_events :]

    def _load_unlocked(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"latest_run_id": None, "runs": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"latest_run_id": None, "runs": []}
        if not isinstance(data, dict):
            return {"latest_run_id": None, "runs": []}
        data.setdefault("latest_run_id", None)
        data.setdefault("runs", [])
        return data

    def _save_unlocked(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _recover_interrupted(self) -> None:
        with self._lock:
            data = self._load_unlocked()
            changed = False
            now_epoch = time.time()
            for run in data.get("runs", []):
                if run.get("status") not in {"started", "streaming"}:
                    continue
                run["status"] = "interrupted"
                run["finished_at"] = _now()
                run["elapsed_ms"] = round((now_epoch - float(run.get("started_epoch") or now_epoch)) * 1000, 1)
                self._append_event(run, "finish", "server restarted or request cancelled", "interrupted", {})
                changed = True
            if changed:
                self._save_unlocked(data)


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name).strip())
    return clean[:48] or "deepseek"
