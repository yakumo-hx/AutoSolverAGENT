from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class PlannerMode(str, Enum):
    MOCK = "mock"
    DEEPSEEK = "deepseek"


@dataclass
class PlannerDecision:
    strategy_order: List[str]
    rationale: str


class LlmPlanner:
    """Planner facade.

    Mock mode is the default so the demo works without network or an API key.
    DeepSeek mode is intentionally small and isolated.
    """

    def __init__(self, mode: PlannerMode = PlannerMode.MOCK) -> None:
        self.mode = mode

    def plan(self, features: Dict[str, float], strategies: List[str]) -> PlannerDecision:
        if self.mode == PlannerMode.DEEPSEEK:
            return self._deepseek_plan(features, strategies)
        return PlannerDecision(
            strategy_order=strategies,
            rationale="Mock planner tries every basket once, then lets the scorer accept the best coin.",
        )

    def _deepseek_plan(self, features: Dict[str, float], strategies: List[str]) -> PlannerDecision:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
        if not api_key:
            return PlannerDecision(strategy_order=strategies, rationale="Missing DEEPSEEK_API_KEY; fallback to mock.")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You choose solver strategy order. Return compact JSON only.",
                },
                {
                    "role": "user",
                    "content": json.dumps({"features": features, "strategies": strategies}, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            order = [name for name in parsed.get("strategy_order", []) if name in strategies]
            return PlannerDecision(
                strategy_order=order or strategies,
                rationale=parsed.get("rationale", "DeepSeek planner returned a strategy order."),
            )
        except Exception as exc:
            return PlannerDecision(strategy_order=strategies, rationale=f"DeepSeek planner fallback: {exc}")
