from __future__ import annotations

from math import inf
from typing import Dict, List

from .llm_planner import LlmPlanner, PlannerMode
from .memory import MemoryLedger
from .models import AgentTrace, Assignment, CaseData, StrategyResult, TraceStep
from .scorer import parse_case, validate_and_score
from .strategies import STRATEGIES


class AutoSolverAgent:
    """Showcase agent that tries algorithm baskets and records a visual trace."""

    def __init__(self, planner_mode: PlannerMode = PlannerMode.MOCK) -> None:
        self.planner = LlmPlanner(planner_mode)
        self.memory = MemoryLedger()

    def run(self, input_text: str) -> AgentTrace:
        case = parse_case(input_text)
        features = self._features(case)
        strategy_names = list(STRATEGIES)
        decision = self.planner.plan(features, strategy_names)

        best_score = inf
        best_strategy = "none"
        best_solution: List[Assignment] = []

        for step_id, strategy_name in enumerate(decision.strategy_order, start=1):
            strategy = STRATEGIES[strategy_name]
            solution = strategy(case)
            valid, score, covered, errors = validate_and_score(case, solution)
            accepted = valid and score < best_score
            delta = 0.0 if best_score == inf else score - best_score
            if accepted:
                best_score = score
                best_strategy = strategy_name
                best_solution = solution

            step = TraceStep(
                step_id=step_id,
                strategy=strategy_name,
                score=score,
                valid=valid,
                covered=covered,
                accepted=accepted,
                delta=delta,
                message=self._message(strategy_name, valid, score, accepted, errors),
                visual={
                    "coin": f"solution-{step_id}",
                    "basket": strategy_name,
                    "scale": "lower-is-better",
                    "ledger_mark": "plus" if accepted else "minus",
                },
            )
            self.memory.append(step)

        return AgentTrace(
            title="AutoSolver Agent Demo Trace",
            best_score=best_score,
            best_strategy=best_strategy,
            steps=list(self.memory.strategy_history()),
            final_solution=best_solution,
        )

    def _features(self, case: CaseData) -> Dict[str, float]:
        pair_count = sum(1 for candidate in case.candidates if len(candidate.tasks) > 1)
        avg_w = (
            sum(candidate.willingness for candidate in case.candidates) / len(case.candidates)
            if case.candidates
            else 0.0
        )
        return {
            "task_count": float(len(case.tasks)),
            "courier_count": float(len(case.couriers)),
            "candidate_count": float(len(case.candidates)),
            "pair_ratio": pair_count / len(case.candidates) if case.candidates else 0.0,
            "avg_willingness": avg_w,
        }

    def _message(self, strategy: str, valid: bool, score: float, accepted: bool, errors: List[str]) -> str:
        if not valid:
            return f"{strategy} produced invalid output: {errors[:2]}"
        if accepted:
            return f"{strategy} found a new lower score: {score:.3f}"
        return f"{strategy} was valid but did not beat the current best: {score:.3f}"

