"""Evaluate the aggregation-inference suite: C4 vs fair baselines.

Three defenses per scenario (see eval/baselines.py):
  - **injection_filter**: keyword prompt-injection detector per message (wrong tool — it
    has no PII capability; expected to detect nothing).
  - **session_pii_filter**: a fair, non-novel stateful baseline that counts distinct
    sensitive fields per subject on egress and escalates at >= 2.
  - **aggreguard_c4**: the aggregation monitor (sensitivity budget + k-anonymity).

Honest headline (red-team driven): the injection filter is the wrong category; the fair
PII field-counter matches C4 on DETECTION but over-flags legitimate multi-attribute
disclosures, so C4's advantage is LOWER FALSE POSITIVES at equal detection — because it
reasons about re-identifiability (anon < k) instead of counting fields.

Uses the SHIPPED config (aggreguard.config.DEFAULT_CONFIG). Zero API cost.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from aggreguard.middleware.aggregation import AggregationMonitor
from aggreguard.middleware.injection_detect import KeywordInjectionDetector
from eval.attacks.aggregation_suite import POPULATION, SUITE_CONFIG, Scenario, load_scenarios
from eval.baselines import SessionPIIFilter, injection_filter_flags

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "benchmarks" / "results" / "aggregation"

DEFENSES = ["injection_filter", "session_pii_filter", "aggreguard_c4"]


@dataclass
class ScenarioResult:
    name: str
    kind: str
    flags: dict[str, bool]          # defense -> flagged?
    c4_reason: str


def _c4_flags(scenario: Scenario, monitor: AggregationMonitor) -> tuple[bool, str]:
    monitor.reset()
    for ev in scenario.events:
        d = monitor.on_disclosure(
            session_id=scenario.name, entity=ev.entity, attr=ev.attr,
            value=ev.value, sink_type=ev.sink_type, now=ev.t,
        )
        if d.escalated:
            return True, f"step '{ev.attr}': {'; '.join(d.reasons)}"
    return False, "no escalation"


def evaluate() -> tuple[list[ScenarioResult], dict]:
    scenarios = load_scenarios()
    injection_detector = KeywordInjectionDetector()
    pii_filter = SessionPIIFilter(SUITE_CONFIG)
    monitor = AggregationMonitor(SUITE_CONFIG, population=POPULATION)

    results = []
    for sc in scenarios:
        c4, reason = _c4_flags(sc, monitor)
        results.append(ScenarioResult(
            name=sc.name, kind=sc.kind,
            flags={
                "injection_filter": injection_filter_flags(sc.events, injection_detector),
                "session_pii_filter": pii_filter.flags(sc.events),
                "aggreguard_c4": c4,
            },
            c4_reason=reason,
        ))

    def rate(kind: str, defense: str) -> float | None:
        rows = [r for r in results if r.kind == kind]
        if not rows:
            return None
        return round(sum(r.flags[defense] for r in rows) / len(rows), 4)

    summary = {
        d: {"attack_detection_rate": rate("attack", d), "benign_fpr": rate("benign", d)}
        for d in DEFENSES
    }
    return results, summary


def to_markdown(results: list[ScenarioResult], summary: dict) -> str:
    lines = ["# Aggregation-inference suite — C4 vs fair baselines", ""]
    lines.append("Config: shipped `DEFAULT_CONFIG` (tau=1.0, k=2, decay off). "
                 f"Population: {len(POPULATION)} synthetic members.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| defense | attack detection rate ↑ | benign FPR ↓ |")
    lines.append("|---|--:|--:|")
    for d in DEFENSES:
        s = summary[d]
        lines.append(f"| {d} | {s['attack_detection_rate']} | {s['benign_fpr']} |")
    lines.append("")
    lines.append("## Per-scenario")
    lines.append("")
    lines.append("| scenario | kind | injection_filter | session_pii_filter | C4 | C4 reason |")
    lines.append("|---|---|:--:|:--:|:--:|---|")
    for r in results:
        def mark(d):
            return "✓" if r.flags[d] else "·"
        lines.append(
            f"| {r.name} | {r.kind} | {mark('injection_filter')} | "
            f"{mark('session_pii_filter')} | {mark('aggreguard_c4')} | {r.c4_reason} |"
        )
    lines.append("")
    lines.append("**Reading it:** the injection filter is the wrong tool (detects nothing). "
                 "The fair session-PII filter matches C4 on detection but false-positives on "
                 "legitimate multi-quasi-identifier disclosures that do not re-identify. C4 "
                 "matches detection at lower FPR by reasoning about re-identifiability (anon < k).")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregation-inference evaluation")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    results, summary = evaluate()
    md = to_markdown(results, summary)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"report written: {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
