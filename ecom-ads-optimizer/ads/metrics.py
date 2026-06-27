"""Ad-performance metrics + wasted-spend detection.

Works on a DataFrame with at least: platform, campaign_type, impressions, clicks, ad_spend,
conversions, revenue. Derived metrics are recomputed from raw counts (don't trust any
pre-computed columns) so the analysis is auditable.

Breakeven ROAS: a unit is profitable when revenue·margin ≥ ad_spend, i.e. ROAS ≥ 1/margin.
Spend on segments below breakeven ROAS is *wasted* (losing money after product margin).
"""
from __future__ import annotations

import pandas as pd


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["CTR"] = df["clicks"] / df["impressions"].replace(0, pd.NA)
    df["CVR"] = df["conversions"] / df["clicks"].replace(0, pd.NA)
    df["CPC"] = df["ad_spend"] / df["clicks"].replace(0, pd.NA)
    df["CPA"] = df["ad_spend"] / df["conversions"].replace(0, pd.NA)
    df["ROAS"] = df["revenue"] / df["ad_spend"].replace(0, pd.NA)
    return df


def breakeven_roas(margin: float) -> float:
    """Minimum ROAS to break even given product gross margin (e.g. margin 0.30 → 3.33)."""
    return round(1.0 / margin, 2)


def summarize(df: pd.DataFrame) -> dict:
    spend, rev = df["ad_spend"].sum(), df["revenue"].sum()
    conv, clicks, impr = df["conversions"].sum(), df["clicks"].sum(), df["impressions"].sum()
    return {
        "rows": len(df),
        "spend": round(spend, 2), "revenue": round(rev, 2),
        "roas": round(rev / spend, 2) if spend else 0.0,
        "acos": round(spend / rev, 4) if rev else 0.0,
        "cpa": round(spend / conv, 2) if conv else 0.0,
        "ctr": round(clicks / impr, 4) if impr else 0.0,
        "cvr": round(conv / clicks, 4) if clicks else 0.0,
    }


def by_segment(df: pd.DataFrame, by) -> pd.DataFrame:
    g = (df.groupby(by)
           .agg(spend=("ad_spend", "sum"), revenue=("revenue", "sum"),
                conversions=("conversions", "sum"), clicks=("clicks", "sum"),
                impressions=("impressions", "sum"))
           .reset_index())
    g["roas"] = (g["revenue"] / g["spend"]).round(2)
    g["acos"] = (g["spend"] / g["revenue"]).round(4)
    g["cpa"] = (g["spend"] / g["conversions"]).round(2)
    g["spend_share"] = (g["spend"] / g["spend"].sum()).round(4)
    return g.sort_values("roas", ascending=False).reset_index(drop=True)


def wasted_spend(df: pd.DataFrame, be_roas: float) -> dict:
    """Spend on rows whose ROAS is below breakeven (money-losing after margin)."""
    bad = df[df["ROAS"] < be_roas]
    total = df["ad_spend"].sum()
    return {
        "breakeven_roas": be_roas,
        "rows_below": int(len(bad)),
        "wasted_spend": round(bad["ad_spend"].sum(), 2),
        "wasted_share": round(bad["ad_spend"].sum() / total, 4) if total else 0.0,
        "revenue_from_wasted": round(bad["revenue"].sum(), 2),
    }
