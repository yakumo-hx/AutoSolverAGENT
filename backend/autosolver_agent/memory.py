from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import AgentTrace, TraceStep


class MemoryLedger:
    """Append-only ledger for strategy attempts."""

    def __init__(self) -> None:
        self.steps: list[TraceStep] = []

    def append(self, step: TraceStep) -> None:
        self.steps.append(step)

    def export_trace(self, trace: AgentTrace, path: str | Path) -> None:
        data = {
            "title": trace.title,
            "best_score": trace.best_score,
            "best_strategy": trace.best_strategy,
            "final_solution": list(trace.final_solution),
            "steps": [step.__dict__ for step in trace.steps],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def strategy_history(self) -> Iterable[TraceStep]:
        return tuple(self.steps)

