"""Tests for the aggregation monitor (Component 4): budget + k-anonymity branches."""

from aggreguard.config import AggregationConfig
from aggreguard.middleware.aggregation import ALLOW, ESCALATE_HITL, AggregationMonitor


def test_non_untrusted_sink_is_allowed():
    mon = AggregationMonitor()
    out = mon.on_disclosure(
        session_id="s1", entity="alice", attr="ssn", value="x",
        sink_type="internal", now=0.0,
    )
    assert out.decision == ALLOW
    assert out.anonymity_set is None


def test_budget_escalates_when_threshold_crossed():
    # tau low enough that a single high-weight disclosure trips it.
    mon = AggregationMonitor(AggregationConfig(tau=0.9))
    out = mon.on_disclosure(
        session_id="s1", entity="alice", attr="ssn", value="123-45-6789",
        sink_type="untrusted", now=0.0,
    )
    assert out.decision == ESCALATE_HITL
    assert out.sensitivity >= 0.9


def test_budget_accumulates_over_benign_steps():
    # Each step below tau individually, but they sum past it.
    cfg = AggregationConfig(tau=1.0, weights={"zip": 0.3, "dob": 0.5, "city": 0.4})
    mon = AggregationMonitor(cfg)
    d1 = mon.on_disclosure(session_id="s", entity="bob", attr="zip", value="10001",
                           sink_type="untrusted", now=0.0)
    d2 = mon.on_disclosure(session_id="s", entity="bob", attr="dob", value="1990-01-01",
                           sink_type="untrusted", now=0.0)
    assert d1.decision == ALLOW  # 0.3 < 1.0
    assert d2.decision == ALLOW  # 0.8 < 1.0
    d3 = mon.on_disclosure(session_id="s", entity="bob", attr="city", value="NYC",
                           sink_type="untrusted", now=0.0)
    assert d3.decision == ESCALATE_HITL  # 1.2 >= 1.0


def test_k_anonymity_reidentification_branch():
    # 4 people; disclosing zip+gender+dob narrows to a unique individual (anon=1 < k=2).
    population = [
        {"zip": "10001", "gender": "F", "dob": "1990-01-01"},
        {"zip": "10001", "gender": "M", "dob": "1985-05-05"},
        {"zip": "10001", "gender": "F", "dob": "1992-02-02"},
        {"zip": "20002", "gender": "F", "dob": "1990-01-01"},
    ]
    cfg = AggregationConfig(tau=999.0, k=2,  # disable budget branch; test k-anon only
                            quasi_identifiers={"zip", "gender", "dob"},
                            weights={"zip": 0.0, "gender": 0.0, "dob": 0.0})
    mon = AggregationMonitor(cfg, population=population)
    mon.on_disclosure(session_id="s", entity="t", attr="zip", value="10001",
                      sink_type="untrusted", now=0.0)         # anon=3
    d2 = mon.on_disclosure(session_id="s", entity="t", attr="gender", value="F",
                           sink_type="untrusted", now=0.0)    # anon=2 (still >= k)
    assert d2.decision == ALLOW and d2.anonymity_set == 2
    d3 = mon.on_disclosure(session_id="s", entity="t", attr="dob", value="1990-01-01",
                           sink_type="untrusted", now=0.0)    # anon=1 < k=2
    assert d3.decision == ESCALATE_HITL and d3.anonymity_set == 1


def test_reset_clears_ledger():
    mon = AggregationMonitor(AggregationConfig(tau=0.9))
    mon.on_disclosure(session_id="s", entity="a", attr="ssn", value="x",
                      sink_type="untrusted", now=0.0)
    mon.reset()
    out = mon.on_disclosure(session_id="s", entity="a", attr="zip", value="10001",
                            sink_type="untrusted", now=0.0)
    assert out.decision == ALLOW  # ledger was cleared, only a low-weight disclosure now
