"""Unit tests for eval metrics — exercises the ASR/utility math without a live model."""

from eval import metrics


def test_asr_and_utility_math():
    # 4 attack cases, 2 succeeded -> ASR 0.5
    security = {("u1", "i1"): True, ("u2", "i1"): False, ("u3", "i2"): True, ("u4", "i2"): False}
    assert metrics.attack_success_rate(security) == 0.5

    # 5 tasks, 4 completed -> utility 0.8
    util = {("u1", ""): True, ("u2", ""): True, ("u3", ""): True, ("u4", ""): True, ("u5", ""): False}
    assert metrics.utility(util) == 0.8


def test_empty_inputs_are_zero():
    assert metrics.attack_success_rate({}) == 0.0
    assert metrics.utility({}) == 0.0


def test_summarize_shape():
    row = metrics.summarize(clean_utility=0.9, asr=0.3, utility_under_attack=0.7)
    assert row["clean_utility"] == 0.9
    assert row["asr"] == 0.3
    assert row["utility_under_attack"] == 0.7
    assert "latency_p50_ms" in row
