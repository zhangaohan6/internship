"""Tests for the aggregation-inference suite evaluation (the C4 moat demo).

The honest, red-team-driven claim: C4 *matches* a fair session-aware PII baseline on
attack detection but with strictly lower false positives, because it reasons about
re-identifiability instead of counting fields.
"""

from eval.aggregation_eval import evaluate
from eval.attacks.aggregation_suite import load_scenarios


def test_suite_has_attacks_and_benign():
    kinds = {s.kind for s in load_scenarios()}
    assert kinds == {"attack", "benign"}


def test_injection_filter_is_wrong_tool():
    _, summary = evaluate()
    # A prompt-injection detector has no PII capability — detects none of these.
    assert summary["injection_filter"]["attack_detection_rate"] == 0.0


def test_c4_matches_fair_baseline_on_detection_with_lower_fpr():
    _, summary = evaluate()
    c4 = summary["aggreguard_c4"]
    pii = summary["session_pii_filter"]

    # Both fair defenses catch every aggregation attack.
    assert c4["attack_detection_rate"] == 1.0
    assert pii["attack_detection_rate"] == 1.0

    # C4's advantage is strictly lower false positives at equal detection.
    assert c4["benign_fpr"] == 0.0
    assert pii["benign_fpr"] > c4["benign_fpr"]


def test_c4_passes_nonreidentifying_qids_that_pii_filter_flags():
    results, _ = evaluate()
    by_name = {r.name: r for r in results}
    # The discriminating cases: legitimate multi-QID disclosures C4 correctly allows
    # but the field-counting baseline over-flags.
    for name in ("benign_nonreidentifying_qids", "benign_out_of_population_qids"):
        assert by_name[name].flags["aggreguard_c4"] is False
        assert by_name[name].flags["session_pii_filter"] is True


def test_attacks_fire_via_distinct_branches():
    results, _ = evaluate()
    by_name = {r.name: r for r in results}
    assert "budget" in by_name["budget_slow_leak"].c4_reason
    assert "anonymity set" in by_name["reidentification_unique"].c4_reason
