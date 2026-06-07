from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .models import Assignment, Candidate, CaseData


def parse_case(input_text: str) -> CaseData:
    candidates: List[Candidate] = []
    tasks_seen: Dict[str, None] = {}
    couriers_seen: Dict[str, None] = {}
    best = {}

    for raw in input_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4 or parts[0] == "task_id_list":
            continue
        task_key, courier_id = parts[0], parts[1]
        try:
            total_score = float(parts[2])
            willingness = float(parts[3])
        except ValueError:
            continue
        tasks = tuple(t.strip() for t in task_key.split(",") if t.strip())
        if not tasks:
            continue
        rec = Candidate(task_key, courier_id, total_score, willingness, tasks)
        key = (task_key, courier_id)
        old = best.get(key)
        if old is None or candidate_cost(rec) < candidate_cost(old):
            best[key] = rec
        for task in tasks:
            tasks_seen[task] = None
        couriers_seen[courier_id] = None

    candidates = list(best.values())
    return CaseData(
        candidates=candidates,
        tasks=sorted(tasks_seen),
        couriers=sorted(couriers_seen),
    )


def candidate_cost(candidate: Candidate) -> float:
    task_count = len(candidate.tasks)
    return (
        candidate.willingness * candidate.total_score
        + (1.0 - candidate.willingness) * 100.0 * task_count
    )


def validate_and_score(case: CaseData, solution: Iterable[Assignment]) -> Tuple[bool, float, int, List[str]]:
    lookup = {(c.task_key, c.courier_id): c for c in case.candidates}
    used_couriers = set()
    covered_tasks = set()
    errors: List[str] = []
    score = 0.0

    for task_key, courier_ids in solution:
        if not isinstance(courier_ids, list) or not courier_ids:
            errors.append(f"{task_key}: courier list is empty or invalid")
            continue

        row_candidates = []
        for courier_id in courier_ids:
            candidate = lookup.get((task_key, courier_id))
            if candidate is None:
                errors.append(f"{task_key}/{courier_id}: candidate not found")
                continue
            if courier_id in used_couriers:
                errors.append(f"{courier_id}: duplicate courier")
                continue
            row_candidates.append(candidate)

        if not row_candidates:
            continue

        tasks = row_candidates[0].tasks
        if any(c.tasks != tasks for c in row_candidates):
            errors.append(f"{task_key}: mixed task sets")
            continue
        if any(task in covered_tasks for task in tasks):
            errors.append(f"{task_key}: duplicate task coverage")
            continue

        for candidate in row_candidates:
            used_couriers.add(candidate.courier_id)
        for task in tasks:
            covered_tasks.add(task)

        score += multi_courier_cost(row_candidates)

    score += 100.0 * (len(case.tasks) - len(covered_tasks))
    return not errors, score, len(covered_tasks), errors


def multi_courier_cost(candidates: List[Candidate]) -> float:
    if not candidates:
        return 0.0
    tasks = candidates[0].tasks
    fail_prob = 1.0
    weighted_score = 0.0
    weight_sum = 0.0
    for candidate in candidates:
        p = max(0.0, min(1.0, candidate.willingness))
        fail_prob *= 1.0 - p
        weighted_score += p * candidate.total_score
        weight_sum += p
    complete_prob = 1.0 - fail_prob
    accepted_score = weighted_score / weight_sum if weight_sum > 0 else 100.0 * len(tasks)
    return complete_prob * accepted_score + (1.0 - complete_prob) * 100.0 * len(tasks)

