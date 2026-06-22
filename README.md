# AggreGuard

Trace-level, **aggregation-aware** safety guardrail middleware + reproducible
attack/defense evaluation harness for LLM agents.

Unlike I/O text filters (Lakera, LLM Guard, NeMo, Llama Guard), AggreGuard inspects the
agent's **execution trace** (which tools were called, where data flowed) and uniquely
handles **aggregation / inference attacks**: a stream of individually-benign queries that
together cross a sensitivity threshold.

See [AggreGuard_项目计划.md](AggreGuard_项目计划.md) for the full plan.

## Status

**Phase 1 — MVP middleware.** Components implemented:

- **C1 provenance / trust boundary** — taint-tracking (`Tagged` values, least-trusted
  propagation) + a trust-violation check (untrusted data must not drive high-risk tools).
- **C2 injection detection** — pluggable interface; zero-dep keyword baseline +
  lazy-loaded HuggingFace detector (default ProtectAI deberta-v3 prompt-injection-v2).
- **C3 task alignment** — Task-Shield-style monitor: structured `UserIntent` + rule
  baseline (read-only / allowlist) with a pluggable LLM-judge hook.
- **C4 aggregation** (algorithm scaffold), **C5 action gating**, **C6 decision logging**.

**Composition + integration:** `aggreguard/guard.py` strings C1/C2/C3/C5/C6 into one
per-step `AggreGuard.evaluate()` decision (BLOCK > ESCALATE_HITL > ALLOW).
`aggreguard/integrations/agentdojo_defense.py` exposes it as an AgentDojo defense — the
runner accepts `--defense aggreguard`, inserting the AggreGuard PI detector into the
tools-execution loop.

Still needed for the Phase 1 exit: run a model backend to produce the
no-defense vs AggreGuard comparison table (expected ASR drop).

## Layout

```
aggreguard/middleware/   # Components 1–6 (provenance, injection, task-align,
                         #                 aggregation★, action-gate, logging)
aggreguard/integrations/ # LangGraph node / Claude SDK hook / MCP proxy
eval/                    # Product A: attack suites, metrics, runner, report
benchmarks/results/      # comparison tables + figures
tests/                   # smoke + behavioral tests
```

## Dev setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # core + dev tooling
pip install -e ".[eval]"       # AgentDojo (verify Python compatibility)
pytest -q
```

## Roadmap

- **Phase 0** geardown: reproduce no-defense AgentDojo baseline (ASR / utility).
- **Phase 1** MVP: Components 1 + 3, baseline injection detector, first comparison table.
- **Phase 2** core: Component 4 (aggregation monitor) + own attack suite + FPR tests.
- **Phase 3** ablation, full comparison vs LLM Guard / Lakera, open-source, paper draft.

License: Apache-2.0
