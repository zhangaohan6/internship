"""Real LLM Guard (Protect AI) comparison on the aggregation suite — no straw man.

Runs LLM Guard's *actual* scanners over each message of the aggregation-inference
scenarios and reports sequence-level detection / benign FPR, to be set beside C4.

Two real LLM Guard scanners:
  - PromptInjection (input scanner): the wrong tool — detects override phrasing, not PII.
  - Sensitive (output scanner, Presidio-backed): a real production PII detector, but
    STATELESS per message — it has no session memory, so it cannot reason about cumulative
    disclosure or re-identification across a sequence.

Expected, honest finding: the injection scanner detects ~nothing; the PII scanner, lacking
aggregation state, cannot separate attack sequences from benign multi-field disclosures —
it flags by per-message PII presence, not by re-identifiability — so it has no detection/FPR
tradeoff at the sequence level. This is the same conclusion as the fair field-counter
baseline, now established with the real package rather than a stand-in.

Run under the isolated env that has llm-guard installed:
    .venv-llmguard/bin/python -m eval.llmguard_compare
(llm-guard requires Python <3.13; the main repo venv is 3.14, hence a separate env.)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eval.attacks.aggregation_suite import load_scenarios

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "benchmarks" / "results" / "aggregation"


def _load_scanners():
    """Lazily build the real LLM Guard scanners; returns {name: callable(text)->flagged}."""
    scanners = {}
    try:
        from llm_guard.input_scanners import PromptInjection
        pi = PromptInjection()
        scanners["llmguard_prompt_injection"] = lambda t: not pi.scan(t)[1]
    except Exception as e:  # pragma: no cover - environment dependent
        scanners["llmguard_prompt_injection"] = ("unavailable", repr(e))
    try:
        from llm_guard.output_scanners import Sensitive
        sn = Sensitive()
        # output scanner: scan(prompt, output) -> (sanitized, is_valid, score)
        scanners["llmguard_sensitive_pii"] = lambda t: not sn.scan("", t)[1]
    except Exception as e:  # pragma: no cover
        scanners["llmguard_sensitive_pii"] = ("unavailable", repr(e))
    return scanners


def evaluate():
    scenarios = load_scenarios()
    attacks = [s for s in scenarios if s.kind == "attack"]
    benign = [s for s in scenarios if s.kind == "benign"]
    scanners = _load_scanners()

    summary = {}
    for name, fn in scanners.items():
        if isinstance(fn, tuple):
            summary[name] = {"status": fn[0], "error": fn[1]}
            continue

        def flagged(sc):
            return any(fn(ev.message) for ev in sc.events)

        det = sum(flagged(s) for s in attacks) / len(attacks)
        fpr = sum(flagged(s) for s in benign) / len(benign)
        summary[name] = {"attack_detection": round(det, 4), "benign_fpr": round(fpr, 4)}
    return summary


def to_markdown(summary: dict) -> str:
    lines = ["# Real LLM Guard (Protect AI) on the aggregation suite", ""]
    lines.append("Per-message scan with LLM Guard's *actual* scanners; a scenario is "
                 "flagged if any of its messages is flagged. Set beside C4 from "
                 "`report.md` (C4: detection 1.00, FPR 0.00).")
    lines.append("")
    lines.append("| scanner | attack detection ↑ | benign FPR ↓ |")
    lines.append("|---|--:|--:|")
    for name, s in summary.items():
        if "status" in s:
            lines.append(f"| {name} | _{s['status']}_ | — |")
        else:
            lines.append(f"| {name} | {s['attack_detection']} | {s['benign_fpr']} |")
    lines.append("")
    lines.append("**Reading it:** the prompt-injection scanner is the wrong category "
                 "(it has no PII notion). The Sensitive/Presidio PII scanner is a real "
                 "production detector but stateless per message — it flags by per-message "
                 "PII presence, not by cumulative re-identifiability, so it cannot match C4's "
                 "detection-at-low-FPR. C4's session-scoped anonymity reasoning is what "
                 "off-the-shelf I/O filters structurally lack.")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Real LLM Guard comparison")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    summary = evaluate()
    md = to_markdown(summary)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "llmguard_compare.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"report written: {args.out / 'llmguard_compare.md'}")


if __name__ == "__main__":
    main()
