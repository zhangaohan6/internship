"""Tests for ad metrics, wasted-spend, segmentation, and reallocation."""
import pandas as pd

from ads.metrics import add_derived, breakeven_roas, summarize, by_segment, wasted_spend
from ads.optimize import reallocation_plan
from ads.data import generate_synthetic


def _toy():
    return pd.DataFrame([
        # platform, type, impressions, clicks, spend, conversions, revenue  -> ROAS
        {"platform": "A", "campaign_type": "Search", "impressions": 1000, "clicks": 100,
         "ad_spend": 100.0, "conversions": 10, "revenue": 1000.0},   # ROAS 10  (good)
        {"platform": "B", "campaign_type": "Display", "impressions": 1000, "clicks": 50,
         "ad_spend": 200.0, "conversions": 2, "revenue": 100.0},     # ROAS 0.5 (wasted)
    ])


def test_breakeven_roas():
    assert breakeven_roas(0.30) == 3.33
    assert breakeven_roas(0.50) == 2.0


def test_derived_and_summary():
    df = add_derived(_toy())
    assert abs(df.loc[0, "ROAS"] - 10.0) < 1e-9
    assert abs(df.loc[1, "ROAS"] - 0.5) < 1e-9
    s = summarize(df)
    assert s["spend"] == 300.0 and s["revenue"] == 1100.0
    assert abs(s["roas"] - round(1100 / 300, 2)) < 1e-9


def test_wasted_spend_flags_below_breakeven():
    df = add_derived(_toy())
    w = wasted_spend(df, breakeven_roas(0.30))   # be 3.33: row B (0.5) is wasted
    assert w["rows_below"] == 1
    assert w["wasted_spend"] == 200.0


def test_by_segment_sorted_desc_roas():
    df = add_derived(_toy())
    g = by_segment(df, "platform")
    assert list(g["platform"]) == ["A", "B"]       # A (ROAS 10) before B (0.5)
    assert g.loc[0, "roas"] >= g.loc[1, "roas"]


def test_reallocation_positive_upside():
    df = add_derived(_toy())
    plan = reallocation_plan(df, breakeven_roas(0.30))
    assert plan["reallocatable_spend"] == 200.0     # the wasted row's spend
    assert plan["incremental_revenue"] > 0


def test_end_to_end_synthetic():
    df = add_derived(generate_synthetic(300, seed=1))
    s = summarize(df)
    assert s["rows"] == 300 and s["spend"] > 0
    g = by_segment(df, "campaign_type")
    assert (g["roas"].values[:-1] >= g["roas"].values[1:]).all()   # sorted desc
