"""Component 6 — decision logging / observability.

Emits a structured trace record for every allow / block / escalate decision
(action, hit component, reason, confidence). Visualized via self-hosted Langfuse.

Plan ref: §4 Component 6. Status: SKELETON (implement in Phase 3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DecisionLog:
    action: str
    component: str
    decision: str
    reason: str
    confidence: float


def log_decision(record: DecisionLog) -> None:
    """Persist a decision record (stdout now; Langfuse later). TODO(Phase 3)."""
    raise NotImplementedError("decision logging not wired up yet")
