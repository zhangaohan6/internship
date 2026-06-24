"""Tests for the aggregation-inference suite evaluation (the C4 moat demo)."""

from eval.aggregation_eval import evaluate
from eval.attacks.aggregation_suite import load_scenarios


def test_suite_has_attacks_and_benign():
    kinds = {s.kind for s in load_scenarios()}
    assert kinds == {"attack", "benign"}


def test_c4_catches_aggregation_attacks_io_filter_misses():
    results, summary = evaluate()

    # I/O filter is blind to aggregation attacks (each step is benign text).
    assert summary["io_filter"]["attack_detection_rate"] == 0.0
    # C4 catches every aggregation attack...
    assert summary["aggreguard_c4"]["attack_detection_rate"] == 1.0
    # ...without false-positives on benign multi-step work.
    assert summary["aggreguard_c4"]["benign_fpr"] == 0.0


def test_attacks_fire_via_distinct_branches():
    results, _ = evaluate()
    by_name = {r.name: r for r in results}
    assert "budget" in by_name["budget_slow_leak"].c4_reason
    assert "anonymity set" in by_name["reidentification_qids"].c4_reason
