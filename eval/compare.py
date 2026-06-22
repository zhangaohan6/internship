"""Comparison driver — run several defenses over the same tasks and emit ONE table.

This is the Phase 1 deliverable: a no-defense vs AggreGuard (and any other defense)
comparison on a chosen suite/subset, written to a single report.md + report.html.

Example (small local smoke run):
    python -m eval.compare --backend local --model local \
        --user-tasks user_task_0 user_task_1 --injection-tasks injection_task_0 \
        --defenses none aggreguard
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from eval.report import write_report
from eval.runner import DEFAULT_LOGDIR, run


def main() -> None:
    parser = argparse.ArgumentParser(description="AggreGuard defense comparison")
    parser.add_argument("--suite", default="workspace")
    parser.add_argument("--backend", default="local", choices=["local", "api"])
    parser.add_argument("--model", default="local")
    parser.add_argument("--attack", default="important_instructions")
    parser.add_argument("--defenses", nargs="*", default=["none", "aggreguard"],
                        help="defense keys to compare ('none' = no-defense baseline)")
    parser.add_argument("--user-tasks", nargs="*", default=None)
    parser.add_argument("--injection-tasks", nargs="*", default=None)
    parser.add_argument("--logdir", type=Path, default=DEFAULT_LOGDIR)
    args = parser.parse_args()

    rows = []
    for defense in args.defenses:
        defense_arg = None if defense == "none" else defense
        print(f"\n=== running defense={defense} ===")
        t0 = time.perf_counter()
        row = run(
            suite_name=args.suite, model=args.model, backend=args.backend,
            defense=defense_arg, attack_name=args.attack,
            user_tasks=args.user_tasks, injection_tasks=args.injection_tasks,
            logdir=args.logdir / defense,
        )
        elapsed = time.perf_counter() - t0
        rows.append({
            "suite": args.suite, "backend": args.backend, "model": args.model,
            "defense": defense, "attack": args.attack,
            "wall_seconds": round(elapsed, 1), **row,
        })
        for k, v in rows[-1].items():
            print(f"  {k}: {v}")

    md_path, html_path = write_report(rows, outdir=args.logdir,
                                      title="AggreGuard: no-defense vs AggreGuard")
    print(f"\ncomparison report written:\n  {md_path}\n  {html_path}")


if __name__ == "__main__":
    main()
