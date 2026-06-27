"""Demand forecasting — a few interpretable methods + a backtest that picks the best.

Methods (all pure-Python, no heavy deps):
  moving_average  — flat forecast at the trailing-window mean
  ses             — simple exponential smoothing (flat at the smoothed level)
  holt            — Holt's linear trend (level + trend, projected forward)
  seasonal_naive  — repeat the last weekly cycle (captures weekend lift)

`best_forecast` backtests each on a holdout tail and returns the lowest-error forecast.
"""
from __future__ import annotations

import statistics


def moving_average(series, horizon, window=14):
    w = series[-window:] if len(series) >= window else series
    level = sum(w) / len(w)
    return [level] * horizon


def ses(series, horizon, alpha=0.3):
    level = series[0]
    for x in series[1:]:
        level = alpha * x + (1 - alpha) * level
    return [level] * horizon


def holt(series, horizon, alpha=0.2, beta=0.1):
    if len(series) < 2:
        return moving_average(series, horizon)
    level = series[0]
    trend = series[1] - series[0]
    for x in series[1:]:
        prev = level
        level = alpha * x + (1 - alpha) * (level + trend)
        trend = beta * (level - prev) + (1 - beta) * trend
    return [max(0.0, level + trend * (h + 1)) for h in range(horizon)]


def seasonal_naive(series, horizon, period=7):
    if len(series) < period:
        return moving_average(series, horizon)
    last = series[-period:]
    return [last[h % period] for h in range(horizon)]


METHODS = {
    "moving_average": moving_average,
    "ses": ses,
    "holt": holt,
    "seasonal_naive": seasonal_naive,
}


def _mape(actual, pred):
    errs = [abs(a - p) / max(a, 1.0) for a, p in zip(actual, pred)]
    return sum(errs) / len(errs)


def backtest(series, method, horizon=14):
    """Holdout the last `horizon` days, fit on the rest, return MAPE."""
    if len(series) <= horizon + 7:
        return float("inf")
    train, test = series[:-horizon], series[-horizon:]
    pred = method(train, horizon)
    return _mape(test, pred)


def best_forecast(series, horizon=30, bt_horizon=14):
    """Return (forecast, method_name, backtest_mape) for the best-backtesting method."""
    scored = [(name, backtest(series, fn, bt_horizon)) for name, fn in METHODS.items()]
    scored.sort(key=lambda x: x[1])
    name = scored[0][0]
    return METHODS[name](series, horizon), name, round(scored[0][1], 3)
