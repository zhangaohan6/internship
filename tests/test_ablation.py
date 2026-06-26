"""Component ablation behavior: on the aggregation suite, C4 is load-bearing and the
other components add no false positives."""

from eval.ablation import evaluate


def test_ablation_isolates_c4():
    summary = evaluate()

    # Full guard and C4-alone both catch every aggregation attack at zero FPR.
    assert summary["all (C1-C5)"]["attack_detection"] == 1.0
    assert summary["all (C1-C5)"]["benign_fpr"] == 0.0
    assert summary["aggregation_only (C4)"]["attack_detection"] == 1.0
    assert summary["aggregation_only (C4)"]["benign_fpr"] == 0.0

    # Dropping C4 collapses detection to zero.
    assert summary["no_aggregation (−C4)"]["attack_detection"] == 0.0

    # No single non-aggregation component catches the aggregation threat.
    for label in ("injection_only (C2)", "provenance_only (C1)",
                  "task_align_only (C3)", "action_gate_only (C5)", "none"):
        assert summary[label]["attack_detection"] == 0.0
        assert summary[label]["benign_fpr"] == 0.0
