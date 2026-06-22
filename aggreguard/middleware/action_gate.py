"""Component 5 — high-risk action gating + HITL.

Defines high-risk tools (send_email / transfer / external_post / delete); a hit
triggers a policy-configurable response:

  - ``log``  : record the decision, allow the action (observability only)
  - ``soft`` : escalate to a human-in-the-loop confirmation (default; favors low FPR)
  - ``hard`` : block the action outright

Plan ref: §4 Component 5. The high-risk tool set and mode come from ``GuardConfig``.
"""

from __future__ import annotations

from enum import Enum

from aggreguard.config import GuardConfig


class GateDecision(str, Enum):
    ALLOW = "allow"
    ESCALATE_HITL = "escalate_hitl"
    BLOCK = "block"


def is_high_risk(tool_name: str, config: GuardConfig) -> bool:
    return tool_name in config.high_risk_tools


def gate(tool_name: str, config: GuardConfig) -> GateDecision:
    """Return a gating decision for a tool call given the configured policy mode."""
    if not is_high_risk(tool_name, config):
        return GateDecision.ALLOW

    mode = config.action_gate_mode
    if mode == "log":
        return GateDecision.ALLOW
    if mode == "hard":
        return GateDecision.BLOCK
    if mode == "soft":
        return GateDecision.ESCALATE_HITL
    raise ValueError(f"unknown action_gate_mode: {mode!r} (expected log|soft|hard)")
