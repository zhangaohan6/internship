# Demand Forecast & Inventory Restock Planner

A **zero-dependency** Python tool that solves an FBA seller's #1 operational headache:
**when to reorder, and how much**. It forecasts each SKU's demand, then computes the
inventory-control quantities that prevent both stockouts (lost sales + lost ranking) and
overstock (tied-up cash + storage fees).

> Demand forecasting + inventory optimisation — the quantitative ops work behind every
> healthy FBA account, automated and auditable.

## What it computes

**Forecasting** (`restock/forecast.py`) — four interpretable methods (trailing moving
average, simple exponential smoothing, **Holt's linear trend**, **weekly seasonal-naive**),
with a **backtest** that auto-selects the lowest-error method per SKU (reports MAPE).

**Inventory control** (`restock/inventory.py`):
```
safety_stock  = z · σ_daily · √lead_time
reorder_point = avg_daily · lead_time + safety_stock
days_of_cover = current_stock / avg_daily
reorder_qty   = order-up-to target − current_stock   (rounded to MOQ)
stockout_risk = P(demand over lead time > current stock)
```

## Quick start (no install, no data needed)

```bash
python3 plan.py                      # synthetic demo: 8 SKUs
python3 plan.py --n 20 --service 0.95 --horizon 30
python3 plan.py --csv my_skus.csv    # your data (schema below)
```
Outputs an urgency-ranked restock plan to stdout and `out/restock_plan.{md,csv}`.

Example (synthetic, seed 0): **5/8 SKUs need reordering now**, recommended PO value **$21k**,
soonest stockout in **11 days**.

## Interactive dashboard

```bash
pip install streamlit pandas
streamlit run app.py
```
Tabs: **Restock Plan** (urgency-ranked table + days-of-cover bar + PO-value metric),
**Forecast** (pick a SKU → sales history vs forecast line chart, with the auto-selected method
and MAPE), and **About**. Tune service level / horizon or upload a real SKU CSV in the sidebar.

## Plug in real data

A CSV with one row per SKU: `sku,title,daily_sales,current_stock,lead_time_days,
min_order_qty,unit_cost`, where `daily_sales` is a `|`-separated series of daily units
(most-recent last). Export from Seller Central / your ERP and reshape to this.

## Layout
```
restock/
  data.py       # synthetic daily-sales generator + CSV loader
  forecast.py   # moving-avg / SES / Holt / seasonal-naive + backtest selector
  inventory.py  # safety stock, reorder point, stockout risk, reorder qty
  report.py     # markdown + CSV restock plan
plan.py         # CLI
app.py          # Streamlit dashboard
tests/          # 8 tests (forecast shapes, Holt trend, safety-stock math, stockout risk)
```

## Tests
```bash
python3 -m pytest -q
```

## Notes
- Forecasts are intentionally simple and interpretable (no black-box) — easy to defend and
  extend (e.g., add Croston for intermittent demand, or a learned model).
- Synthetic data is fabricated for demonstration; it is **not** real sales data.

*Author: Aohan Zhang · MIT License*
