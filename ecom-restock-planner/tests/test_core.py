"""Tests for forecasting + inventory math."""
import math

from restock.forecast import (moving_average, ses, holt, seasonal_naive,
                              backtest, best_forecast, METHODS)
from restock.inventory import z_for_service, demand_stats, recommend
from restock.data import generate_skus


def test_forecast_methods_return_horizon_length():
    s = [10 + (i % 7) for i in range(120)]
    for fn in METHODS.values():
        assert len(fn(s, 30)) == 30


def test_holt_projects_upward_trend():
    s = list(range(1, 101))                     # strictly increasing
    fc = holt(s, 10)
    assert fc[-1] > fc[0] > 0                    # trend carried forward


def test_seasonal_naive_repeats_weekly_pattern():
    s = [1, 2, 3, 4, 5, 6, 7] * 20
    fc = seasonal_naive(s, 7, period=7)
    assert fc == [1, 2, 3, 4, 5, 6, 7]


def test_backtest_and_best_forecast():
    s = [20 + 5 * (i % 7 in (5, 6)) for i in range(150)]   # weekly seasonality
    name_fn = list(METHODS.items())[0]
    assert backtest(s, name_fn[1], 14) >= 0
    fc, method, mape = best_forecast(s, 30)
    assert len(fc) == 30 and method in METHODS and mape >= 0


def test_z_table_service_level():
    assert z_for_service(0.95) == 1.65
    assert z_for_service(0.99) == 2.33


def test_inventory_safety_stock_and_reorder_point():
    # avg 10/day, sigma 4, lead 16 days, 95% service (z=1.65)
    rec = recommend(10.0, 4.0, current_stock=100, lead_time=16, service_level=0.95,
                    review_period=0, moq=50)
    # safety = 1.65 * 4 * sqrt(16) = 1.65*4*4 = 26.4 -> ceil 27
    assert rec["safety_stock"] == 27
    # rop = 10*16 + 26.4 = 186.4 -> ceil 187
    assert rec["reorder_point"] == 187
    assert rec["reorder_now"] is True            # 100 <= 187
    assert rec["reorder_qty"] % 50 == 0          # rounded to MOQ


def test_stockout_risk_higher_with_less_stock():
    low = recommend(10, 4, current_stock=50, lead_time=16)["stockout_risk_lead_time"]
    high = recommend(10, 4, current_stock=300, lead_time=16)["stockout_risk_lead_time"]
    assert low > high


def test_end_to_end_plan():
    from plan import build_rows
    rows = build_rows(generate_skus(10, days=180, seed=1))
    assert len(rows) == 10
    # urgent (reorder_now) SKUs sorted ahead of the rest
    flags = [r["reorder_now"] for r in rows]
    assert flags == sorted(flags, reverse=True)
