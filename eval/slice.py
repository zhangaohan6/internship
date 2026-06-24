"""Run ONE (defense × user-task) slice and emit raw per-task results as JSON.

Designed for parallel data collection: each slice is independent and writes a JSON
file with per-(user_task, injection_task) booleans, so an external aggregator can
compute ASR/utility correctly across all slices. Deterministic — no LLM in the
aggregation path.

Output JSON schema:
    {
      "defense": "none",
      "model": "claude-sonnet-4-6",
      "clean":   [{"user_task": "user_task_0", "completed": true}, ...],
      "attacked":[{"user_task": "...", "injection_task": "...",
                   "attack_succeeded": false, "utility": true}, ...]
    }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.runner import run_raw


def _serialize(clean: dict, attacked: dict) -> dict:
    clean_rows = [
        {"user_task": k[0] if isinstance(k, tuple) else k, "completed": bool(v)}
        for k, v in clean["utility_results"].items()
    ]
    util = attacked["utility_results"]
    attacked_rows = []
    for k, succeeded in attacked["security_results"].items():
        ut, it = (k if isinstance(k, tuple) else (k, ""))
        attacked_rows.append({
            "user_task": ut,
            "injection_task": it,
            "attack_succeeded": bool(succeeded),
            "utility": bool(util.get(k, False)),
        })
    return {"clean": clean_rows, "attacked": attacked_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="AggreGuard eval slice")
    parser.add_argument("--suite", default="workspace")
    parser.add_argument("--backend", default="api", choices=["local", "api"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--defense", default="none", help="'none' or a defense key")
    parser.add_argument("--attack", default="important_instructions")
    parser.add_argument("--user-tasks", nargs="+", required=True)
    parser.add_argument("--injection-tasks", nargs="+", required=True)
    parser.add_argument("--logdir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    defense = None if args.defense == "none" else args.defense
    clean, attacked = run_raw(
        suite_name=args.suite, model=args.model, backend=args.backend, defense=defense,
        attack_name=args.attack, user_tasks=args.user_tasks,
        injection_tasks=args.injection_tasks, logdir=args.logdir,
    )
    payload = {"defense": args.defense, "model": args.model, **_serialize(clean, attacked)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"SLICE_OK {args.out} clean={len(payload['clean'])} attacked={len(payload['attacked'])}")


if __name__ == "__main__":
    main()
