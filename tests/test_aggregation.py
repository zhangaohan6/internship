"""Smoke tests for the aggregation monitor scaffold (Component 4).

Confirms the package imports and the budget/escalation logic behaves on a simple
trace. Real behavioral tests come with the Phase 2 implementation.
"""

from aggreguard.config import AggregationConfig
from aggreguard.middleware.aggregation import ALLOW, ESCALATE_HITL, AggregationMonitor


def test_non_untrusted_sink_is_allowed():
    mon = AggregationMonitor()
    out = mon.on_disclosure(
        session_id="s1", entity="alice", attr="ssn", value="x",
        sink_type="internal", now=0.0,
    )
    assert out == ALLOW


def test_budget_escalates_when_threshold_crossed():
    # tau low enough that a single high-weight disclosure trips it.
    mon = AggregationMonitor(AggregationConfig(tau=0.9))
    out = mon.on_disclosure(
        session_id="s1", entity="alice", attr="ssn", value="123-45-6789",
        sink_type="untrusted", now=0.0,
    )
    assert out == ESCALATE_HITL
