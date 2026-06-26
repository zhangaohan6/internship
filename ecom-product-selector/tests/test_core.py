"""Behavioural tests for the profit waterfall, fees, and scoring."""
from ecom.fees import referral_fee, fba_fulfilment_fee
from ecom.profit import Product, compute_profit
from ecom.scoring import score_products
from ecom.data import generate_products


def test_referral_fee_rate_and_minimum():
    assert abs(referral_fee(20.0, "home_kitchen") - 3.0) < 1e-9      # 15%
    assert abs(referral_fee(0.5, "default") - 0.30) < 1e-9           # min fee floor


def test_fba_fee_monotone_in_weight():
    fees = [fba_fulfilment_fee(w, 10) for w in (0.2, 0.6, 1.0, 2.0, 4.0)]
    assert fees == sorted(fees)                                       # heavier costs more


def test_profit_waterfall_math():
    p = Product(asin="X", title="t", category="home_kitchen",
                price=30.0, cogs=6.0, inbound_shipping=1.0, weight_lb=0.5,
                volume_cuft=0.0, acos=0.20)
    r = compute_profit(p)
    # referral = 4.5, fba(0.5lb small) = 3.27, storage 0, ppc = 30*0.2 = 6.0
    # pre_ad = 30 - 4.5 - 3.27 - 0 - 6 - 1 = 15.23 ; net = 15.23 - 6 = 9.23
    assert abs(r.referral - 4.5) < 1e-9
    assert abs(r.ppc - 6.0) < 1e-9
    assert abs(r.net_profit - 9.23) < 0.01
    assert abs(r.margin - 9.23 / 30.0) < 1e-3
    assert abs(r.roi - 9.23 / 7.0) < 1e-3                             # invested = cogs + inbound
    # breakeven ACoS = pre_ad / price
    assert abs(r.breakeven_acos - 15.23 / 30.0) < 1e-3


def test_negative_margin_flagged_not_viable():
    p = Product(asin="Y", title="loss", category="default",
                price=15.0, cogs=10.0, inbound_shipping=3.0, weight_lb=3.0, acos=0.30)
    r = compute_profit(p)
    assert r.net_profit < 0
    rows = [{"asin": "Y", "title": "loss", "category": "default", "price": r.price,
             "net_profit": r.net_profit, "margin": r.margin, "roi": r.roi,
             "breakeven_acos": r.breakeven_acos, "monthly_sales": 500,
             "avg_review_count": 50, "num_sellers": 5}]
    ranked = score_products(rows)
    assert ranked[0]["viable"] is False


def test_scoring_prefers_higher_margin_demand_lower_barrier():
    base = dict(category="x", price=30, net_profit=5, roi=1.0, breakeven_acos=0.4,
                num_sellers=10)
    good = {"asin": "G", "title": "good", **base, "margin": 0.40,
            "monthly_sales": 3000, "avg_review_count": 50}
    bad = {"asin": "B", "title": "bad", **base, "margin": 0.12,
           "monthly_sales": 200, "avg_review_count": 5000}
    ranked = score_products([bad, good])
    assert ranked[0]["asin"] == "G"
    assert ranked[0]["opportunity_score"] > ranked[1]["opportunity_score"]


def test_end_to_end_runs_and_ranks():
    from analyze import build_rows
    products = generate_products(n=120, seed=1)
    ranked = score_products(build_rows(products))
    assert len(ranked) == 120
    scores = [r["opportunity_score"] for r in ranked if r["viable"]]
    assert scores == sorted(scores, reverse=True)                    # viable block is sorted desc


def test_ppc_economics_and_breakeven():
    from ecom.ppc import Keyword, analyze_keyword
    # price 40, breakeven ACoS 0.35; CPC 1.0 at 10% CVR => cost/conv = 10 => ACoS 0.25 < 0.35 => profitable
    r = analyze_keyword(40.0, 0.35, Keyword("k", 1000, cpc=1.0, cvr=0.10))
    assert abs(r["cost_per_conversion"] - 10.0) < 1e-9
    assert abs(r["acos"] - 0.25) < 1e-9
    assert r["profitable"] is True
    # max profitable CPC = breakeven_acos * price * cvr = 0.35*40*0.10 = 1.40
    assert abs(r["max_profitable_cpc"] - 1.40) < 1e-9
    # a CPC above max profitable should flip to unprofitable
    r2 = analyze_keyword(40.0, 0.35, Keyword("k2", 1000, cpc=2.0, cvr=0.10))
    assert r2["profitable"] is False and r2["headroom"] < 0


def test_ppc_ranking_prefers_profitable_high_volume():
    from ecom.ppc import Keyword, rank_keywords
    kws = [Keyword("lowvol", 100, cpc=0.5, cvr=0.12),
           Keyword("highvol", 9000, cpc=0.5, cvr=0.12),
           Keyword("unprofitable", 5000, cpc=3.0, cvr=0.05)]
    ranked = rank_keywords(40.0, 0.35, kws)
    assert ranked[0]["term"] == "highvol"
    assert ranked[-1]["profitable"] is False
