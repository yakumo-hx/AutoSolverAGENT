from __future__ import annotations

import argparse
from pathlib import Path

from autosolver_agent import AutoSolverAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AutoSolver Agent showcase trace.")
    parser.add_argument("--case", default="data/sample_case.tsv", help="Input case TSV.")
    parser.add_argument("--out", default="demo/trace.generated.json", help="Trace JSON output.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    case_path = (root / args.case).resolve()
    out_path = (root / args.out).resolve()
    input_text = case_path.read_text(encoding="utf-8")

    agent = AutoSolverAgent()
    trace = agent.run(input_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    agent.memory.export_trace(trace, out_path)

    print(f"trace: {out_path}")
    print(f"best_strategy: {trace.best_strategy}")
    print(f"best_score: {trace.best_score:.6f}")
    print(f"steps: {len(trace.steps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

