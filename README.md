# AggreGuard

Trace-level, **aggregation-aware** safety guardrail middleware + reproducible
attack/defense evaluation harness for LLM agents.

Unlike I/O text filters (Lakera, LLM Guard, NeMo, Llama Guard), AggreGuard inspects the
agent's **execution trace** (which tools were called, where data flowed) and uniquely
handles **aggregation / inference attacks**: a stream of individually-benign queries that
together cross a sensitivity threshold.

See [AggreGuard_项目计划.md](AggreGuard_项目计划.md) for the full plan, and
[RESUME.md](RESUME.md) for a one-page summary.

## Results at a glance

- **Aggregation moat:** against a *fair* stateful PII field-counter that matches it on raw
  detection, the aggregation monitor attains **0.989 vs 0.663 detection at a 2%
  false-positive budget** (stable across 8 seeds) — it reasons about re-identifiability
  (anon < k), not field counts. On the core suite: **100% detection at 0% FPR vs the
  field-counter's 40% FPR**. Verified against the **real LLM Guard (Protect AI) package**
  (`eval/llmguard_compare.py`): its prompt-injection scanner detects **0%** (wrong tool) and
  its Sensitive/Presidio PII scanner only **0.50 detection at 0.20 FPR** — it catches overt
  PII but misses quasi-identifier re-identification and has no session state — vs C4's
  **1.00 / 0.00**.
- **Component ablation:** C4 (the aggregation monitor) alone reproduces the full guard
  (detection 1.00 / FPR 0.00); dropping it collapses detection to 0 — and composing the
  other components adds no false positives.
- **Engineering:** 6 composable middleware components, an AgentDojo defense adapter, a
  reproducible zero-cost eval harness, **49 passing tests**, Apache-2.0.
- **Honest scope:** single-step injection on AgentDojo is a reported *null result* (baseline
  ASR already 0 on both backends) — the contribution is the orthogonal aggregation monitor.

## Status

**Phase 1 — MVP middleware.** Components implemented:

- **C1 provenance / trust boundary** — taint-tracking (`Tagged` values, least-trusted
  propagation) + a trust-violation check (untrusted data must not drive high-risk tools).
- **C2 injection detection** — pluggable interface; zero-dep keyword baseline +
  lazy-loaded HuggingFace detector (default ProtectAI deberta-v3 prompt-injection-v2).
- **C3 task alignment** — Task-Shield-style monitor: structured `UserIntent` + rule
  baseline (read-only / allowlist) with a pluggable LLM-judge hook.
- **C4 aggregation ★** — cumulative-disclosure monitor (sensitivity budget + k-anonymity
  re-identification over a reference population). **C5 action gating**, **C6 logging**.

**Composition + integration:** `aggreguard/guard.py` strings all six components into one
`AggreGuard.evaluate()` decision (BLOCK > ESCALATE_HITL > ALLOW). C1/C2/C3/C5 are stateless
per-step checks; **C4 is stateful** — the guard holds one `AggregationMonitor` across the
session and each `GuardStep` carries the `Disclosure`s the tool call makes.
`aggreguard/integrations/agentdojo_defense.py` exposes it as an AgentDojo defense
(`--defense aggreguard`).

**Phase 2 — aggregation moat (the novelty).** `eval/attacks/aggregation_suite.py` is the
project's own multi-step inference attack suite; `eval/aggregation_eval.py` contrasts C4
against two baselines under the **shipped** config (`benchmarks/results/aggregation/report.md`):

| defense | aggregation-attack detection ↑ | benign FPR ↓ |
|---|--:|--:|
| injection_filter (prompt-injection detector — wrong tool) | 0.00 | 0.00 |
| session_pii_filter (fair stateful field-counter) | **1.00** | 0.40 |
| **aggreguard_c4** | **1.00** | **0.00** |

The honest result (after an adversarial red-team, see `benchmarks/AGGREGATION_REDTEAM.md`):
a stateless injection filter is the wrong tool; a *fair* session-aware PII field-counter
*matches* C4 on detection but over-flags legitimate multi-attribute disclosures. C4's
genuine advantage is **lower false positives at equal detection** — it distinguishes a
re-identifying quasi-identifier combination (anon < k) from a harmless one (anon ≥ k)
rather than counting fields.

**Detection–FPR tradeoff sweep (plan §9).** `eval/sweep.py` runs the monitor across a
(tau, k) grid against a 371-member population and 354 ground-truth-labelled scenarios
(ground truth = an *independent* privacy standard; C4 estimates anonymity from an
*incomplete* reference sample, so it is not an oracle). The curve
(`benchmarks/results/aggregation/tradeoff_curve.png`) shows C4's frontier dominating the
field-counter's — at **≤2% FPR, C4 detection ≈ 0.98–1.00 vs field-counter ≈ 0.66–0.68**
(robust across 8 population×scenario seeds); the field-counter needs ~25% FPR to reach
C4's detection. This demonstrates the *right feature space* (weighted sensitivity +
anonymity) beats field-counting, not that C4 detects an arbitrary privacy standard.

**Component ablation (Phase 3).** `eval/ablation.py` runs the full composed guard over the
aggregation suite with component subsets toggled (`AggreGuard(enabled=...)`), writing
`benchmarks/results/aggregation/ablation.md`. Result: enabling **only C4** reproduces the
full guard (detection 1.00, FPR 0.00); every subset without C4 — including each other
component alone — detects nothing, and dropping C4 collapses detection to zero. C4 is the
sole load-bearing component for this threat, and composing the others around it adds no
false positives (composition is safe).

**AgentDojo injection results (Phase 1):** baseline ASR is 0 on both backends tried
(local `llama3.1:8b` too weak; api `claude-sonnet-4-6` self-defends), so an end-to-end
ASR drop isn't demonstrable there yet — see `benchmarks/PHASE1_FINDINGS.md`.

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
