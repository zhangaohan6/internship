# AggreGuard

Trace-level, **aggregation-aware** safety guardrail middleware + reproducible
attack/defense evaluation harness for LLM agents.

Unlike I/O text filters (Lakera, LLM Guard, NeMo, Llama Guard), AggreGuard inspects the
agent's **execution trace** (which tools were called, where data flowed) and uniquely
handles **aggregation / inference attacks**: a stream of individually-benign queries that
together cross a sensitivity threshold.

See [AggreGuard_项目计划.md](AggreGuard_项目计划.md) for the full plan.

## Status

**Phase 0 — scaffolding.** Repository skeleton in place; component modules are stubs.
Model backend (local Ollama vs Claude/GPT API) not yet chosen.

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
