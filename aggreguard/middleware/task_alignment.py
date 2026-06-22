"""Component 3 — task-alignment monitor (Task Shield approach).

Maintains a structured representation of the original user intent and checks, before
each tool call, whether the action serves that intent; flags deviations.

Plan ref: §4 Component 3. Status: SKELETON (implement in Phase 1).
"""

from __future__ import annotations


def is_aligned(user_intent: str, proposed_action: dict) -> bool:
    """Whether proposed_action serves user_intent. TODO(Phase 1)."""
    raise NotImplementedError("task-alignment check not implemented yet")
