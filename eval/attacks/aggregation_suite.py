"""Aggregation-inference attack suite ★ (the project's distinctive experiment).

Constructs multi-step tasks where each step is individually compliant but the
cumulative disclosure constitutes a sensitive leak / re-identification. Plugged into
the same harness interface as AgentDojo / IPI Arena suites.

Plan ref: §5.1. Status: SKELETON (implement in Phase 2).
"""

from __future__ import annotations


def load_tasks() -> list[dict]:
    """Return the aggregation-inference attack tasks. TODO(Phase 2)."""
    raise NotImplementedError
