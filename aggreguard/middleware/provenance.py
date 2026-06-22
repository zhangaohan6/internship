"""Component 1 — data provenance tagging & trust boundaries.

Tags every piece of data flowing through the agent with a trust level and enforces
that untrusted content cannot directly trigger high-privilege tools.

Plan ref: §4 Component 1. Status: SKELETON (implement in Phase 1).
"""

from __future__ import annotations

from enum import Enum


class TrustLevel(str, Enum):
    USER = "user"        # trusted
    TOOL = "tool"        # semi-trusted
    WEB = "web"          # untrusted (web / RAG)


def tag(data: object, level: TrustLevel) -> object:
    """Attach a provenance label to a data item. TODO(Phase 1)."""
    raise NotImplementedError("provenance tagging not implemented yet")
