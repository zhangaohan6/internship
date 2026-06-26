"""Test the detection-FPR sweep: C4's frontier should dominate the field-counter's.

Deterministic (seeded), no plotting / no API.
"""

from eval.sweep import (
    _max_tpr_at_fpr,
    build_population,
    build_reference,
    generate_scenarios,
    run_sweep,
)


def test_c4_frontier_dominates_field_counter_at_low_fpr():
    pop = build_population(0)
    ref = build_reference(pop)
    scenarios = generate_scenarios(pop, 1)
    # Sanity: a real labelled set with both classes.
    n_harm = sum(s.label for s in scenarios)
    assert n_harm > 20 and (len(scenarios) - n_harm) > 20

    sweep = run_sweep(pop, scenarios, ref)
    # At a tight FPR budget, C4 achieves materially higher detection than the
    # field-counting baseline (the whole point of reasoning about re-identifiability).
    # Use a 2% budget: the advantage is robust there across seeds (an exact-0%-FPR bin
    # is a brittle knife-edge under an incomplete reference, so it is not the headline).
    c4 = _max_tpr_at_fpr(sweep["c4"], 0.02)
    pii = _max_tpr_at_fpr(sweep["pii"], 0.02)
    assert c4 > pii + 0.2

    # C4 is realistic, not a perfect oracle (incomplete reference sample).
    assert _max_tpr_at_fpr(sweep["c4"], 0.0) < 1.0
