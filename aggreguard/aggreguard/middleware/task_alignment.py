"""Component 3 — task-alignment monitor (Task Shield approach).

Holds a structured representation of the original user intent and, before each tool
call, checks whether the action serves that intent; deviations are flagged.

Phase 1 ships a deterministic rule-based baseline (fast, zero-dependency) plus a
pluggable ``judge`` hook so a small LLM can be dropped in later without changing the
call sites. Example caught by the baseline: intent "summarize my emails" (read-only)
but the agent calls ``send_email`` to an external address -> misaligned.

Plan ref: §4 Component 3 (arXiv 2412.16682 Task Shield).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Alignment(str, Enum):
    ALIGNED = "aligned"
    MISALIGNED = "misaligned"
    UNKNOWN = "unknown"


@dataclass
class UserIntent:
    """Structured intent extracted from the user's original instruction."""

    description: str
    # Tool names the user implicitly authorized (empty => unknown, fall back to judge).
    allowed_tools: set[str] = field(default_factory=set)
    # If True, the task is read-only; exfiltration/mutation tools are off-intent.
    read_only: bool = False


# Tools that move data out of the trust boundary or mutate external state.
_EXFIL_OR_MUTATE = {"send_email", "transfer", "external_post", "delete", "forward_email"}

# A judge takes (intent, action) and returns an Alignment; None => defer to rules.
Judge = Callable[[UserIntent, dict], Alignment | None]


@dataclass
class TaskAlignmentMonitor:
    """Checks proposed actions against the user's intent."""

    intent: UserIntent
    judge: Judge | None = None

    def check(self, proposed_action: dict) -> Alignment:
        """Return alignment for a proposed action.

        proposed_action: {"tool": str, "args": dict, ...}
        Resolution order: LLM/judge hook (if it commits) -> deterministic rules.
        """
        tool = proposed_action.get("tool", "")

        if self.judge is not None:
            verdict = self.judge(self.intent, proposed_action)
            if verdict is not None:
                return verdict

        # Rule 1: a read-only intent must not invoke exfiltration/mutation tools.
        if self.intent.read_only and tool in _EXFIL_OR_MUTATE:
            return Alignment.MISALIGNED

        # Rule 2: if the user authorized an explicit tool set, anything outside is off-intent.
        if self.intent.allowed_tools and tool not in self.intent.allowed_tools:
            return Alignment.MISALIGNED

        # Rule 3: no explicit allowlist and not obviously exfiltrating -> treat as aligned.
        if not self.intent.allowed_tools:
            return Alignment.ALIGNED

        return Alignment.ALIGNED


def is_aligned(user_intent: UserIntent, proposed_action: dict, judge: Judge | None = None) -> bool:
    """Convenience wrapper: True iff the action is aligned with the intent."""
    return TaskAlignmentMonitor(user_intent, judge).check(proposed_action) == Alignment.ALIGNED
