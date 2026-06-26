"""Product-selection opportunity scoring.

Turns the raw market signals + profit metrics into a single 0-100 **Opportunity Score**,
the way a sourcing analyst would weigh a niche — but reproducibly and at scale. Four
transparent sub-scores, min-max normalised across the candidate set:

  demand        ↑  monthly sales (market size)
  profitability ↑  net margin (unit economics)
  low_barrier   ↑  fewer incumbent reviews  (easier to rank / enter)
  low_competition ↑ fewer sellers per unit of demand (less crowded)

Opportunity = 100 * Σ wᵢ · sub_scoreᵢ  (weights configurable).
"""
from __future__ import annotations

DEFAULT_WEIGHTS = {
    "demand": 0.30,
    "profitability": 0.35,
    "low_barrier": 0.20,
    "low_competition": 0.15,
}


def _minmax(values):
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def score_products(rows, weights=None, min_margin=0.10):
    """rows: list of dicts with keys monthly_sales, margin, avg_review_count, num_sellers.
    Returns the same rows annotated with sub-scores + opportunity_score, ranked desc.
    A hard profitability gate drops products below `min_margin` (flagged, not silently kept).
    """
    weights = weights or DEFAULT_WEIGHTS
    if not rows:
        return []

    demand = _minmax([r["monthly_sales"] for r in rows])
    profit = _minmax([r["margin"] for r in rows])
    # barriers: invert so that LOWER reviews / sellers => HIGHER score
    barrier = _minmax([-r["avg_review_count"] for r in rows])
    # competition: sellers per unit of demand (crowdedness); fewer is better
    crowd = [r["num_sellers"] / max(r["monthly_sales"], 1) for r in rows]
    low_comp = _minmax([-c for c in crowd])

    out = []
    for r, d, p, b, c in zip(rows, demand, profit, barrier, low_comp):
        sub = {"demand": d, "profitability": p, "low_barrier": b, "low_competition": c}
        score = 100.0 * sum(weights[k] * sub[k] for k in weights)
        viable = r["margin"] >= min_margin
        out.append({**r, **{f"s_{k}": round(v, 3) for k, v in sub.items()},
                    "opportunity_score": round(score, 1),
                    "viable": viable})
    # non-viable products sink to the bottom regardless of score
    out.sort(key=lambda r: (r["viable"], r["opportunity_score"]), reverse=True)
    return out
