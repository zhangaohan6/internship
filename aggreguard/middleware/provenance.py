"""Component 1 — data provenance tagging & trust boundaries.

Tags every piece of data flowing through the agent with a trust level and enforces
the core rule: content from an untrusted source must not *directly* drive a
high-privilege tool (send_email / transfer / external_post / delete).

This is a lightweight taint-tracking layer. A ``Tagged`` value carries its trust
level and origin; when values combine, the most-untrusted level dominates (taint
propagates). The action gate then queries the provenance of a tool call's arguments.

Plan ref: §4 Component 1 (design patterns paper + CaMeL).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable


class TrustLevel(IntEnum):
    """Trust ordering — higher value == more trusted. IntEnum so we can min()."""

    WEB = 0    # untrusted (web / RAG / tool output that embeds external content)
    TOOL = 1   # semi-trusted (tool results)
    USER = 2   # trusted (the originating user instruction)


# Aliases kept as strings for serialization / config readability.
_LABELS = {TrustLevel.USER: "user", TrustLevel.TOOL: "tool", TrustLevel.WEB: "web"}


@dataclass(frozen=True)
class Tagged:
    """A value annotated with provenance."""

    value: object
    level: TrustLevel
    source: str = ""              # human-readable origin, e.g. "email_body", "web:example.com"
    parents: tuple[str, ...] = field(default_factory=tuple)  # source trail for auditing

    @property
    def label(self) -> str:
        return _LABELS[self.level]


def tag(data: object, level: TrustLevel, source: str = "") -> Tagged:
    """Attach a provenance label to a data item."""
    return Tagged(value=data, level=level, source=source)


def combine_levels(levels: Iterable[TrustLevel]) -> TrustLevel:
    """Taint propagation: the least-trusted level dominates. Empty -> USER (no taint)."""
    levels = list(levels)
    if not levels:
        return TrustLevel.USER
    return TrustLevel(min(levels))


def derive(value: object, inputs: Iterable[Tagged], source: str = "") -> Tagged:
    """Produce a new Tagged value derived from several inputs, propagating taint."""
    inputs = list(inputs)
    level = combine_levels(t.level for t in inputs)
    parents = tuple(t.source for t in inputs if t.source)
    return Tagged(value=value, level=level, source=source, parents=parents)


def is_untrusted(t: Tagged) -> bool:
    return t.level <= TrustLevel.WEB


def trust_violation(
    tool_name: str,
    arg_provenance: Iterable[Tagged],
    high_risk_tools: set[str],
) -> bool:
    """True if a high-risk tool is being driven by untrusted data (boundary breach).

    The trust boundary: a high-privilege action whose arguments derive (even
    transitively) from a WEB-level source is a violation and should be gated.
    """
    if tool_name not in high_risk_tools:
        return False
    return any(is_untrusted(t) for t in arg_provenance)
