"""PPC / advertising keyword economics, tied to the product's unit profit.

For each candidate keyword we answer the questions a PPC manager actually asks:
  * cost per conversion = CPC / conversion-rate
  * ACoS = cost-per-conversion / price                 (ad spend / ad revenue)
  * is it profitable?  ACoS < breakeven-ACoS of the product
  * max profitable CPC = breakeven-ACoS · price · CVR  (highest bid that still breaks even)
  * recommended bid at a target ACoS
  * ROAS, and profit-per-sale after ad cost

`breakeven_acos` comes from ecom.profit.compute_profit(...).breakeven_acos.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Keyword:
    term: str
    search_volume: int       # monthly searches
    cpc: float               # suggested cost-per-click (USD)
    cvr: float               # conversion rate (sales / clicks), e.g. 0.10
    competing_products: int = 0


def analyze_keyword(term_price: float, breakeven_acos: float, kw: Keyword,
                    target_acos: float | None = None):
    """Return per-keyword PPC economics. target_acos defaults to 70% of breakeven."""
    cvr = max(kw.cvr, 1e-6)
    cost_per_conv = kw.cpc / cvr
    acos = cost_per_conv / term_price if term_price else float("inf")
    headroom = breakeven_acos - acos                      # >0 => profitable at this CPC
    roas = (1.0 / acos) if acos > 0 else float("inf")
    max_profitable_cpc = breakeven_acos * term_price * cvr
    tgt = target_acos if target_acos is not None else 0.7 * breakeven_acos
    recommended_bid = tgt * term_price * cvr
    profit_per_sale = breakeven_acos * term_price - cost_per_conv  # pre-ad profit minus ad cost
    return {
        "term": kw.term, "search_volume": kw.search_volume, "cpc": round(kw.cpc, 2),
        "cvr": round(kw.cvr, 3), "cost_per_conversion": round(cost_per_conv, 2),
        "acos": round(acos, 3), "breakeven_acos": round(breakeven_acos, 3),
        "headroom": round(headroom, 3), "roas": round(roas, 2),
        "max_profitable_cpc": round(max_profitable_cpc, 2),
        "recommended_bid": round(recommended_bid, 2),
        "profit_per_sale": round(profit_per_sale, 2),
        "profitable": headroom > 0,
        "competing_products": kw.competing_products,
    }


def _minmax(vals):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5 for _ in vals]
    return [(v - lo) / (hi - lo) for v in vals]


def rank_keywords(term_price, breakeven_acos, keywords, weights=None, target_acos=None):
    """Score & rank keywords by volume ↑, profit headroom ↑, low competition ↑.
    Unprofitable keywords are kept but de-ranked."""
    weights = weights or {"volume": 0.4, "headroom": 0.4, "low_competition": 0.2}
    rows = [analyze_keyword(term_price, breakeven_acos, k, target_acos) for k in keywords]
    if not rows:
        return []
    vol = _minmax([r["search_volume"] for r in rows])
    head = _minmax([r["headroom"] for r in rows])
    comp = _minmax([-r["competing_products"] for r in rows])
    for r, v, h, c in zip(rows, vol, head, comp):
        r["kw_score"] = round(100 * (weights["volume"] * v + weights["headroom"] * h
                                     + weights["low_competition"] * c), 1)
    rows.sort(key=lambda r: (r["profitable"], r["kw_score"]), reverse=True)
    return rows
