from __future__ import annotations

from typing import Callable, Dict, List

from .models import Assignment, CaseData
from .scorer import candidate_cost


StrategyFn = Callable[[CaseData], List[Assignment]]


def greedy_low_cost(case: CaseData) -> List[Assignment]:
    return _greedy(case, sorted(range(len(case.candidates)), key=lambda i: candidate_cost(case.candidates[i])))


def greedy_high_willingness(case: CaseData) -> List[Assignment]:
    return _greedy(
        case,
        sorted(
            range(len(case.candidates)),
            key=lambda i: (-case.candidates[i].willingness, candidate_cost(case.candidates[i])),
        ),
    )


def pair_first(case: CaseData) -> List[Assignment]:
    return _greedy(
        case,
        sorted(
            range(len(case.candidates)),
            key=lambda i: (
                -len(case.candidates[i].tasks),
                candidate_cost(case.candidates[i]) / len(case.candidates[i].tasks),
            ),
        ),
    )


def diversity_demo(case: CaseData) -> List[Assignment]:
    order = sorted(
        range(len(case.candidates)),
        key=lambda i: (
            case.candidates[i].courier_id[-1:],
            candidate_cost(case.candidates[i]) / len(case.candidates[i].tasks),
        ),
    )
    return _greedy(case, order)


def _greedy(case: CaseData, order: List[int]) -> List[Assignment]:
    used_couriers = set()
    covered_tasks = set()
    result: List[Assignment] = []
    for idx in order:
        candidate = case.candidates[idx]
        if candidate.courier_id in used_couriers:
            continue
        if any(task in covered_tasks for task in candidate.tasks):
            continue
        result.append((candidate.task_key, [candidate.courier_id]))
        used_couriers.add(candidate.courier_id)
        covered_tasks.update(candidate.tasks)
    return result


STRATEGIES: Dict[str, StrategyFn] = {
    "greedy_low_cost": greedy_low_cost,
    "greedy_high_willingness": greedy_high_willingness,
    "pair_first": pair_first,
    "diversity_demo": diversity_demo,
}

