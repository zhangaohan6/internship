# Phase 1 findings — baseline ASR on a local model

## Setup
- Suite: AgentDojo `workspace` (v1.2.1), 40 user tasks.
- Model: `llama3.1:8b` via Ollama (`local` provider, OpenAI-compatible :11434).
- Attack: `important_instructions` (AgentDojo's model-addressing IPI attack).
- Harness: `python -m eval.compare` (this repo).

## Runs
| run | scope | clean_utility | ASR | wall |
|-----|-------|--------------:|----:|-----:|
| smoke | 3 user × 2 injection | 0.333 | 0.0 | ~86 s |
| **sweep** | **40 user × 3 injection (120 attack runs)** | **0.025** | **0.0** | ~16 min |

## Conclusion
On `llama3.1:8b`, the workspace baseline is **ASR = 0 with ~2.5% clean utility**.
The model is too weak to *complete* the tasks and too weak to be *hijacked* by the
injection — across 120 attack runs none succeeded. There is therefore **no baseline
ASR for a defense to reduce**, so running AggreGuard here cannot demonstrate value
(you cannot drive 0 lower).

This is the expected "immune through incompetence" regime: meaningful IPI ASR on
AgentDojo requires a capable instruction-following model.

## Implication for the Phase 1 exit
The Phase 1 deliverable (a *visible ASR drop* with the defense on) needs a stronger
backend. Options, in order of expected signal:
1. **Hosted API model** (Claude / GPT-4o) — highest baseline ASR, cleanest result.
2. A larger local model (e.g. `qwen2.5:14b`) — may still under-trigger; slower.

The evaluation harness, `local`/`api` backends, defense composition, and report
generation are all verified working end to end; only the model choice gates the
scientific result.
