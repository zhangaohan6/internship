"""Adapter for REAL retail data — the UCI 'Online Retail' dataset (a UK online retailer,
541,909 transactions over 4,070 products, Dec 2010 – Dec 2011).
Download (no login): https://archive.ics.uci.edu/static/public/352/online+retail.zip

It maps real transactions to the SKU schema by aggregating quantity-per-product-per-day into
a daily sales series. Two fields are NOT present in transaction data and are set from
documented assumptions (exactly what a seller does in practice):
  * current_stock — assumed ≈ 15–45 days of recent demand (inventory isn't in sales data)
  * unit_cost     — assumed COGS ≈ 40% of selling price

Requires pandas + openpyxl (only for this real-data path; the synthetic core stays zero-dep).
"""
from __future__ import annotations

import random

from .data import SKU


def load_online_retail(path, top_n=50, country=None, min_active_days=20,
                       cogs_frac=0.40, seed=0):
    import pandas as pd

    df = pd.read_excel(path) if str(path).lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    df = df[df["Quantity"] > 0].copy()                         # drop returns / cancellations
    if country:
        df = df[df["Country"] == country]
    df["date"] = pd.to_datetime(df["InvoiceDate"]).dt.normalize()

    top = (df.groupby("StockCode")["Quantity"].sum()
             .sort_values(ascending=False).head(top_n).index)
    sub = df[df["StockCode"].isin(top)]
    full = pd.date_range(sub["date"].min(), sub["date"].max(), freq="D")

    rng = random.Random(seed)
    skus = []
    for code in top:
        g = sub[sub["StockCode"] == code]
        daily = g.groupby("date")["Quantity"].sum().reindex(full, fill_value=0)
        series = [int(x) for x in daily.values]
        if sum(1 for d in series if d > 0) < min_active_days:   # need a real signal
            continue
        desc = g["Description"].dropna()
        title = (str(desc.iloc[0])[:40] if len(desc) else str(code)).strip().title()
        price = float(g["UnitPrice"].replace(0, pd.NA).dropna().median() or 1.0)
        avg = sum(series[-30:]) / 30 or 1
        skus.append(SKU(
            sku=str(code), title=title, daily_sales=series,
            current_stock=int(avg * rng.uniform(15, 45)),       # assumption (documented)
            lead_time_days=rng.choice([14, 21, 30]),
            min_order_qty=rng.choice([50, 100, 200]),
            unit_cost=round(price * cogs_frac, 2),              # assumption (documented)
        ))
    return skus
