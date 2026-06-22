"""Component 5 — high-risk action gating + HITL.

Defines high-risk tools (send_email / transfer / external_post / delete); a hit
requires explicit confirmation. Policy is configurable: log / soft / hard.

Plan ref: §4 Component 5. Status: SKELETON (implement in Phase 3).
"""

from __future__ import annotations

from aggreguard.config import GuardConfig


def gate(tool_name: str, config: GuardConfig) -> str:
    """Return a gating decision for a tool call. TODO(Phase 3)."""
    raise NotImplementedError("action gating not implemented yet")
