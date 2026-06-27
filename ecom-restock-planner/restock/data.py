"""Synthetic daily-sales history per SKU (so the repo runs with zero real data) + CSV loader.

Each SKU gets a daily sales series with: a base demand level, a mild trend, weekly
seasonality (weekend lift), random noise, and occasional promo/Prime-Day spikes — the kind
of structure real FBA sales show, so the forecasters have something to learn.
"""
from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field


@dataclass
class SKU:
    sku: str
    title: str
    daily_sales: list           # most-recent-last
    current_stock: int
    lead_time_days: int = 30     # inbound (manufacture + freight) to FBA
    min_order_qty: int = 50
    unit_cost: float = 5.0


def generate_skus(n: int = 8, days: int = 180, seed: int = 0):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        base = rng.uniform(5, 40)                  # avg units/day
        trend = rng.uniform(-0.03, 0.06)           # units/day drift
        weekend_lift = rng.uniform(1.1, 1.7)
        noise = rng.uniform(0.15, 0.35)            # CV of noise
        series = []
        for t in range(days):
            level = base + trend * t
            dow = t % 7
            seas = weekend_lift if dow in (5, 6) else 1.0
            val = level * seas * (1 + rng.gauss(0, noise))
            if rng.random() < 0.02:                # ~2% promo spike days
                val *= rng.uniform(2.0, 4.0)
            series.append(max(0, int(round(val))))
        avg = sum(series[-30:]) / 30
        out.append(SKU(
            sku=f"SKU-{i:03d}", title=f"Product {i:03d}",
            daily_sales=series,
            current_stock=int(avg * rng.uniform(10, 60)),   # 10-60 days of cover
            lead_time_days=rng.choice([14, 21, 30, 45]),
            min_order_qty=rng.choice([50, 100, 200]),
            unit_cost=round(rng.uniform(2, 12), 2),
        ))
    return out


def load_skus_csv(path: str):
    """CSV: one row per SKU with a daily_sales column of '|'-separated integers, plus
    sku,title,current_stock,lead_time_days,min_order_qty,unit_cost."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            series = [int(float(x)) for x in r["daily_sales"].split("|") if x != ""]
            out.append(SKU(
                sku=r["sku"], title=r.get("title", r["sku"]),
                daily_sales=series, current_stock=int(float(r["current_stock"])),
                lead_time_days=int(float(r.get("lead_time_days", 30))),
                min_order_qty=int(float(r.get("min_order_qty", 50))),
                unit_cost=float(r.get("unit_cost", 5.0)),
            ))
    return out
