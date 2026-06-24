"""Evaluate the aggregation-inference suite: C4 vs an I/O-filter baseline.

For every scenario we ask two defenses whether they would flag it:
  - **io_filter**: the keyword injection detector (Component 2) applied to each step's
    outgoing text. Stands in for I/O text filters (Lakera / LLM Guard) — it sees one
    benign message at a time and has no session memory.
  - **aggreguard_c4**: the aggregation monitor (Component 4), which scores cumulative
    disclosure per (session, subject) and escalates on budget or re-identification.

Headline: aggregation attacks are invisible to the I/O filter but caught by C4, while
C4's false-positive rate on benign multi-step work stays low.

Zero API cost — the attack lives entirely in the disclosure trace.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from aggreguard.middleware.aggregation import AggregationMonitor
from aggreguard.middleware.injection_detect import KeywordInjectionDetector
from eval.attacks.aggregation_suite import POPULATION, SUITE_CONFIG, Scenario, load_scenarios

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "benchmarks" / "results" / "aggregation"


@dataclass
class ScenarioResult:
    name: str
    kind: str
    io_flagged: bool
    c4_flagged: bool
    c4_reason: str


def _io_flags(scenario: Scenario, detector: KeywordInjectionDetector) -> bool:
    return any(detector.detect(ev.message) >= detector.threshold for ev in scenario.events)


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
    detector = KeywordInjectionDetector()
    monitor = AggregationMonitor(SUITE_CONFIG, population=POPULATION)

    results = []
    for sc in scenarios:
        io = _io_flags(sc, detector)
        c4, reason = _c4_flags(sc, monitor)
        results.append(ScenarioResult(sc.name, sc.kind, io, c4, reason))

    def rate(kind: str, attr: str) -> float | None:
        rows = [r for r in results if r.kind == kind]
        if not rows:
            return None
        return round(sum(getattr(r, attr) for r in rows) / len(rows), 4)

    summary = {
        "io_filter": {
            "attack_detection_rate": rate("attack", "io_flagged"),
            "benign_fpr": rate("benign", "io_flagged"),
        },
        "aggreguard_c4": {
            "attack_detection_rate": rate("attack", "c4_flagged"),
            "benign_fpr": rate("benign", "c4_flagged"),
        },
    }
    return results, summary


def to_markdown(results: list[ScenarioResult], summary: dict) -> str:
    lines = ["# Aggregation-inference suite — C4 vs I/O filter", ""]
    lines.append("## Summary")
    lines.append("")
    lines.append("| defense | attack detection rate ↑ | benign FPR ↓ |")
    lines.append("|---|--:|--:|")
    for d in ("io_filter", "aggreguard_c4"):
        s = summary[d]
        lines.append(f"| {d} | {s['attack_detection_rate']} | {s['benign_fpr']} |")
    lines.append("")
    lines.append("## Per-scenario")
    lines.append("")
    lines.append("| scenario | kind | io_filter flags | C4 flags | C4 reason |")
    lines.append("|---|---|:--:|:--:|---|")
    for r in results:
        lines.append(
            f"| {r.name} | {r.kind} | {'✓' if r.io_flagged else '·'} | "
            f"{'✓' if r.c4_flagged else '·'} | {r.c4_reason} |"
        )
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
