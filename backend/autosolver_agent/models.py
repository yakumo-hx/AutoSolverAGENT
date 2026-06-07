from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple


Assignment = Tuple[str, List[str]]


@dataclass(frozen=True)
class Candidate:
    task_key: str
    courier_id: str
    total_score: float
    willingness: float
    tasks: Tuple[str, ...]


@dataclass
class CaseData:
    candidates: List[Candidate]
    tasks: List[str]
    couriers: List[str]


@dataclass
class StrategyResult:
    name: str
    solution: List[Assignment]
    score: float
    valid: bool
    covered: int
    notes: str = ""


@dataclass
class TraceStep:
    step_id: int
    strategy: str
    score: float
    valid: bool
    covered: int
    accepted: bool
    delta: float
    message: str
    visual: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTrace:
    title: str
    best_score: float
    best_strategy: str
    steps: List[TraceStep]
    final_solution: Sequence[Assignment]

