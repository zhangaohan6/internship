# AggreGuard — résumé bullets

Quantified, honest bullets drawn from the measured results in this repo. Pick 2–3.

## One-line project summary
**AggreGuard** — a trace-level, *aggregation-aware* safety-guardrail middleware for LLM
agents + a reproducible attack/defense evaluation harness. Catches multi-step privacy
inference attacks that per-message I/O filters (Lakera, LLM Guard) structurally miss.

## Bullets (strongest first)

- Built **AggreGuard**, a trace-level aggregation-aware guardrail middleware for LLM agents
  (Python, 6 composable components, **49 tests**, Apache-2.0) that tracks tool-call
  provenance and **per-subject cumulative information disclosure** — a threat class that
  per-message I/O filters (Lakera, LLM Guard, NeMo) structurally cannot see.

- Designed a **k-anonymity + sensitivity-budget aggregation monitor** that flags multi-step
  inference attacks at **0.989 detection vs 0.663** for a fair stateful field-counter at a
  **2% false-positive budget** (stable across 8 population×scenario seeds), proving the
  right feature space — re-identifiability, not field-counting — drives the gain.

- Built a **reproducible, zero-cost attack/defense evaluation harness**: an own
  aggregation-inference attack suite (354 labelled scenarios over a 371-member synthetic
  population) + AgentDojo integration, a (τ, k) parameter sweep tracing the detection–FPR
  frontier, and a **component ablation** isolating the load-bearing component (C4 alone == full guard).

- Engineered the guard as **framework-agnostic composable middleware** (provenance/trust
  boundary, off-the-shelf injection detector, task-alignment, action gating, aggregation
  monitor, decision logging) with a single severity-ordered per-step decision and an
  AgentDojo defense adapter; emphasized low false-positives via HITL escalation over hard blocks.

## Interview talking points (honest framing)
- **Novelty:** ports classical inference control (k-anonymity, query auditing, DP budget)
  from statistical databases onto the agent's tool-call trace — no existing agent guardrail
  does cumulative, subject-scoped disclosure accounting.
- **Rigor:** ground truth is an *independent* privacy standard; the monitor estimates
  anonymity from an *incomplete* reference sample (not an oracle); claims are scoped to
  "right feature space beats field-counting," not "detects an arbitrary privacy standard."
- **Honesty signal:** AgentDojo single-step injection is reported as a *null result*
  (baseline ASR already 0 on both backends) rather than spun — shows experimental maturity.

## Tech stack
Python 3.11+ · AgentDojo · HuggingFace (ProtectAI deberta prompt-injection) · pandas ·
pytest · ruff · Langfuse (observability) · Apache-2.0
