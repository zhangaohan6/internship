"""Budget reallocation: move spend from below-breakeven ad rows to high-ROAS ones.

A simple, defensible projection: the spend currently sitting on money-losing rows
(ROAS < breakeven) could be redeployed at the efficiency of the portfolio's *top-quartile*
ROAS, with a discount factor for diminishing returns (you can't infinitely scale a winner).
"""
from __future__ import annotations

import pandas as pd


def reallocation_plan(df: pd.DataFrame, be_roas: float, scale_discount: float = 0.6) -> dict:
    bad = df[df["ROAS"] < be_roas]
    good = df[df["ROAS"] >= be_roas]
    reallocatable = bad["ad_spend"].sum()
    current_rev = bad["revenue"].sum()

    # efficiency to redeploy at = top-quartile ROAS of profitable rows, discounted
    target_roas = (good["ROAS"].quantile(0.75) if len(good) else df["ROAS"].max())
    eff_roas = target_roas * scale_discount
    projected_rev = reallocatable * eff_roas
    return {
        "reallocatable_spend": round(reallocatable, 2),
        "current_revenue_on_it": round(current_rev, 2),
        "target_roas": round(target_roas, 2),
        "assumed_redeploy_roas": round(eff_roas, 2),
        "projected_revenue": round(projected_rev, 2),
        "incremental_revenue": round(projected_rev - current_rev, 2),
    }
