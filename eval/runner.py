"""Evaluation harness entry point (Product A main flow).

Runs (agent × defense config × attack suite) over AgentDojo and emits a comparison
table. Phase 0 goal: reproduce the no-defense baseline (clean utility, ASR under a
standard injection attack).

Model backend is configurable and decided at run time, not hard-coded:

  - Local (Ollama / any OpenAI-compatible server):
        ollama pull llama3.1            # once
        ollama serve                    # exposes :11434
        python -m eval.runner --backend local --model local
    AgentDojo's ``local`` provider talks to http://localhost:$LOCAL_LLM_PORT/v1 ;
    this runner sets LOCAL_LLM_PORT=11434 by default so it points at Ollama.

  - Hosted API (Claude / OpenAI):
        export ANTHROPIC_API_KEY=...    # or OPENAI_API_KEY
        python -m eval.runner --backend api --model claude-3-5-sonnet-20241022

This module imports AgentDojo lazily so `--help` works without the eval extra.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# AgentDojo benchmark version pinned for reproducibility (plan §9: report version).
BENCHMARK_VERSION = "v1.2.1"
DEFAULT_LOGDIR = Path(__file__).resolve().parent.parent / "benchmarks" / "results"


def _build_pipeline(model: str, defense: str | None):
    from agentdojo.agent_pipeline import AgentPipeline, PipelineConfig

    config = PipelineConfig(
        llm=model,
        defense=defense,
        system_message_name=None,
        system_message=None,
    )
    return AgentPipeline.from_config(config)


def run(
    *,
    suite_name: str,
    model: str,
    backend: str,
    defense: str | None,
    attack_name: str,
    user_tasks: list[str] | None,
    logdir: Path,
) -> dict:
    from agentdojo.attacks.attack_registry import load_attack
    from agentdojo.benchmark import (
        benchmark_suite_with_injections,
        benchmark_suite_without_injections,
    )
    from agentdojo.task_suite.load_suites import get_suites

    from eval import metrics

    if backend == "local":
        # Point AgentDojo's local provider at Ollama's OpenAI-compatible port.
        os.environ.setdefault("LOCAL_LLM_PORT", "11434")
        os.environ.setdefault("OPENAI_API_KEY", "ollama")  # client requires a non-empty key

    suites = get_suites(BENCHMARK_VERSION)
    if suite_name not in suites:
        raise SystemExit(f"unknown suite {suite_name!r}; available: {list(suites)}")
    suite = suites[suite_name]

    pipeline = _build_pipeline(model, defense)
    logdir.mkdir(parents=True, exist_ok=True)

    # 1) Clean utility — no injections.
    clean = benchmark_suite_without_injections(
        pipeline, suite, logdir=logdir, force_rerun=False,
        user_tasks=user_tasks, benchmark_version=BENCHMARK_VERSION,
    )

    # 2) Under attack — ASR + utility-under-attack.
    attack = load_attack(attack_name, suite, pipeline)
    attacked = benchmark_suite_with_injections(
        pipeline, suite, attack, logdir=logdir, force_rerun=False,
        user_tasks=user_tasks, benchmark_version=BENCHMARK_VERSION,
    )

    return metrics.summarize(
        clean_utility=metrics.utility(clean["utility_results"]),
        asr=metrics.attack_success_rate(attacked["security_results"]),
        utility_under_attack=metrics.utility(attacked["utility_results"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AggreGuard evaluation harness")
    parser.add_argument("--suite", default="workspace",
                        help="AgentDojo suite: workspace | travel | banking | slack")
    parser.add_argument("--backend", default="local", choices=["local", "api"],
                        help="local = Ollama/OpenAI-compatible; api = hosted Claude/OpenAI")
    parser.add_argument("--model", default="local",
                        help="model id (use 'local' for the Ollama-served model)")
    parser.add_argument("--defense", default=None,
                        help="AgentDojo defense key, or None for the no-defense baseline")
    parser.add_argument("--attack", default="important_instructions",
                        help="attack key from AgentDojo's registry")
    parser.add_argument("--user-tasks", nargs="*", default=None,
                        help="optional subset of user task ids (smaller = faster smoke run)")
    parser.add_argument("--logdir", type=Path, default=DEFAULT_LOGDIR)
    args = parser.parse_args()

    row = run(
        suite_name=args.suite, model=args.model, backend=args.backend,
        defense=args.defense, attack_name=args.attack,
        user_tasks=args.user_tasks, logdir=args.logdir,
    )
    print("=== AggreGuard baseline row ===")
    print(f"suite={args.suite} backend={args.backend} model={args.model} "
          f"defense={args.defense or 'none'} attack={args.attack}")
    for k, v in row.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
