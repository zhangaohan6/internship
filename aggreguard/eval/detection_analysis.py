"""Offline injection-detection analysis over cached AgentDojo traces.

Demonstrates Component 2's value WITHOUT new API calls: replay the tool outputs the
agent actually received (from saved traces) through the AggreGuard injection detector
and report the flag rate on attacked vs clean traces.

This separates two questions the end-to-end ASR conflates:
  - Did the *attack succeed* (end-to-end)? — depends on the model's own resistance.
  - Would the *guardrail flag* the injected content? — depends only on the detector.

A capable model can self-defend (ASR=0) while the guardrail still correctly flags the
injection; this analysis surfaces that signal.

Usage:
    python -m eval.detection_analysis benchmarks/results/api_claude37/none
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aggreguard.middleware.injection_detect import KeywordInjectionDetector


def _tool_texts(trace: dict) -> list[str]:
    """Extract the text of every tool-role message in a trace."""
    out = []
    for m in trace.get("messages", []):
        if m.get("role") != "tool":
            continue
        c = m.get("content")
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            for block in c:
                if isinstance(block, dict):
                    out.append(str(block.get("content") or block.get("text") or ""))
        elif c is not None:
            out.append(json.dumps(c))
    return out


def analyze(traces_dir: Path, threshold: float = 0.5) -> dict:
    det = KeywordInjectionDetector(threshold=threshold)
    attacked_total = attacked_flagged = 0
    clean_total = clean_flagged = 0

    for f in sorted(traces_dir.rglob("*.json")):
        try:
            trace = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(trace, dict) or "messages" not in trace:
            continue
        # Attacked traces carry a non-empty injection_task_id / injections payload.
        is_attacked = bool(trace.get("injection_task_id")) or bool(trace.get("injections"))
        flagged = any(det.detect(t) >= threshold for t in _tool_texts(trace))
        if is_attacked:
            attacked_total += 1
            attacked_flagged += int(flagged)
        else:
            clean_total += 1
            clean_flagged += int(flagged)

    return {
        "traces_dir": str(traces_dir),
        "attacked_total": attacked_total,
        "attacked_flagged": attacked_flagged,
        "attacked_flag_rate": round(attacked_flagged / attacked_total, 4) if attacked_total else None,
        "clean_total": clean_total,
        "clean_flagged": clean_flagged,
        "clean_false_positive_rate": round(clean_flagged / clean_total, 4) if clean_total else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline injection-detection analysis")
    parser.add_argument("traces_dir", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not args.traces_dir.exists():
        sys.exit(f"no such dir: {args.traces_dir}")
    result = analyze(args.traces_dir, args.threshold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
