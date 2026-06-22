"""Component 2 — prompt-injection detection (wraps off-the-shelf detectors).

Baseline detectors only (not the project's novelty): ProtectAI deberta-v3-base
prompt-injection-v2 / Meta Prompt-Guard-86M, optionally Lakera API.

Plan ref: §4 Component 2. Status: SKELETON (implement in Phase 1).
"""

from __future__ import annotations


def detect_injection(text: str) -> float:
    """Return injection probability in [0, 1]. TODO(Phase 1): load HF detector."""
    raise NotImplementedError("injection detector not wired up yet")
