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

## Validation on REAL data (UCI Online Retail)

Beyond the synthetic demo, the planner runs on a **real** transaction dataset — the UCI
*Online Retail* set (a UK online retailer, **541,909 transactions / 4,070 products**,
Dec 2010 – Dec 2011, [no-login download](https://archive.ics.uci.edu/static/public/352/online+retail.zip)):

```bash
pip install pandas openpyxl
python3 plan.py --real "Online Retail.xlsx" --n 40
```
`restock/real_data.py` aggregates quantity-per-product-per-day into a daily sales series.
On the top-40 products: **23 need reordering now**, recommended PO value **≈ $45k**, soonest
stockout in **15 days**. (Inventory level and COGS aren't in transaction data, so they're set
from documented assumptions — current stock ≈ 15–45 days of demand, COGS ≈ 40% of price.)

**Finding (real-data insight).** Real demand is highly **intermittent / bursty** (wholesale
orders, many zero-sale days), so the simple forecasters show **high MAPE on sparse SKUs** —
a genuine limitation that motivates **intermittent-demand methods (Croston's / SBA)** as the
next step. This is exactly the gap you cannot see on clean synthetic data.

## Plug in real data (your own CSV)

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
