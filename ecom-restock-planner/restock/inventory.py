"""Inventory / restock math on top of a demand forecast.

Given average daily demand, its volatility, and the supplier lead time, compute the standard
inventory-control quantities an FBA seller restocks by:

  safety_stock   = z · σ_daily · √lead_time          (buffer for demand variability)
  reorder_point  = avg_daily · lead_time + safety_stock
  days_of_cover  = current_stock / avg_daily
  reorder_qty    = order-up-to target − current_stock (rounded up to MOQ)
  stockout_date  = days until current stock runs out at avg demand
  stockout_risk  = P(demand over the lead time exceeds current stock)   (normal approx)
"""
from __future__ import annotations

import math
import statistics

# z-multipliers for common service levels (cycle service level)
Z_TABLE = {0.80: 0.84, 0.90: 1.28, 0.95: 1.65, 0.975: 1.96, 0.99: 2.33}


def z_for_service(service_level: float) -> float:
    # nearest tabulated service level
    return Z_TABLE[min(Z_TABLE, key=lambda s: abs(s - service_level))]


def demand_stats(series, recent: int = 30, vol_window: int = 60):
    avg_daily = sum(series[-recent:]) / min(recent, len(series))
    w = series[-vol_window:] if len(series) >= 2 else series
    sigma = statistics.pstdev(w) if len(w) > 1 else 0.0
    return avg_daily, sigma


def _phi(x):  # standard normal CDF
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def recommend(avg_daily, sigma, current_stock, lead_time, *,
              service_level=0.95, review_period=14, moq=50):
    z = z_for_service(service_level)
    safety = z * sigma * math.sqrt(max(lead_time, 0))
    rop = avg_daily * lead_time + safety
    doc = current_stock / avg_daily if avg_daily > 0 else float("inf")
    # order-up-to target covers lead time + review period + safety
    target = avg_daily * (lead_time + review_period) + safety
    raw_qty = max(0.0, target - current_stock)
    qty = int(math.ceil(raw_qty / moq) * moq) if raw_qty > 0 else 0
    stockout_days = current_stock / avg_daily if avg_daily > 0 else float("inf")
    # stockout risk over the lead time (normal approx of cumulative demand)
    mean_lt = avg_daily * lead_time
    sd_lt = sigma * math.sqrt(max(lead_time, 0))
    if sd_lt > 0:
        risk = 1 - _phi((current_stock - mean_lt) / sd_lt)
    else:
        risk = 1.0 if current_stock < mean_lt else 0.0
    return {
        "avg_daily": round(avg_daily, 2),
        "sigma_daily": round(sigma, 2),
        "safety_stock": int(math.ceil(safety)),
        "reorder_point": int(math.ceil(rop)),
        "days_of_cover": round(doc, 1) if doc != float("inf") else None,
        "current_stock": int(current_stock),
        "reorder_now": current_stock <= rop,
        "reorder_qty": qty,
        "stockout_in_days": round(stockout_days, 1) if stockout_days != float("inf") else None,
        "stockout_risk_lead_time": round(risk, 3),
    }
