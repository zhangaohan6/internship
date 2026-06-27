"""Streamlit dashboard for the Demand Forecast & Inventory Restock Planner.

Run:  streamlit run app.py     (needs: pip install streamlit pandas)
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from restock.data import generate_skus, load_skus_csv
from restock.forecast import best_forecast
from plan import build_rows

st.set_page_config(page_title="Restock Planner", page_icon="📦", layout="wide")
st.title("📦 Demand Forecast & Inventory Restock Planner")
st.caption("Per-SKU demand forecast (backtest-selected) · safety stock · reorder point · stockout risk")

with st.sidebar:
    st.header("Data")
    up = st.file_uploader("SKU CSV (optional)", type="csv")
    n = st.slider("Synthetic SKUs", 4, 40, 8, 2, disabled=up is not None)
    days = st.slider("History days", 90, 365, 180, 30, disabled=up is not None)
    seed = st.number_input("Seed", 0, 9999, 0, disabled=up is not None)
    service = st.select_slider("Service level", [0.80, 0.90, 0.95, 0.975, 0.99], value=0.95)
    horizon = st.slider("Forecast horizon (days)", 14, 60, 30, 7)

if up is not None:
    tmp = os.path.join("out", "_uploaded.csv"); os.makedirs("out", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(up.getvalue())
    skus = load_skus_csv(tmp)
else:
    skus = generate_skus(int(n), int(days), int(seed))

rows = build_rows(skus, horizon=int(horizon), service=float(service))
df = pd.DataFrame(rows)
sku_map = {s.sku: s for s in skus}

tab1, tab2, tab3 = st.tabs(["Restock Plan", "Forecast", "About"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SKUs", len(df))
    c2.metric("Reorder now", int(df["reorder_now"].sum()))
    po = (df["reorder_qty"] * df["unit_cost"]).sum()
    c3.metric("Recommended PO", f"${po:,.0f}")
    soon = df["stockout_in_days"].dropna()
    c4.metric("Soonest stockout", f"{soon.min():.0f} d" if len(soon) else "—")

    st.subheader("Days of cover by SKU")
    cover = df[["sku", "days_of_cover"]].dropna().set_index("sku")
    st.bar_chart(cover, height=260)

    st.subheader("Restock plan (most urgent first)")
    show = df[["sku", "avg_daily", "forecast_30", "method", "mape", "current_stock",
               "days_of_cover", "reorder_point", "stockout_in_days",
               "stockout_risk_lead_time", "reorder_now", "reorder_qty"]].copy()
    show["mape"] = (show["mape"] * 100).round(0)
    show["stockout_risk_lead_time"] = (show["stockout_risk_lead_time"] * 100).round(0)
    st.dataframe(show, use_container_width=True, height=420)

with tab2:
    st.subheader("Demand forecast per SKU")
    pick = st.selectbox("SKU", df["sku"].tolist())
    s = sku_map[pick]
    fc, method, mape = best_forecast(s.daily_sales, int(horizon))
    hist = s.daily_sales[-90:]
    h = len(hist)
    series = {
        "history": hist + [None] * len(fc),
        "forecast": [None] * h + [round(x, 1) for x in fc],
    }
    st.line_chart(pd.DataFrame(series), height=340)
    st.caption(f"Method auto-selected by backtest: **{method}** (MAPE {mape*100:.0f}%) · "
               f"avg {sum(hist)/len(hist):.1f}/day · forecast next {len(fc)} days = "
               f"{int(round(sum(fc)))} units")

with tab3:
    st.markdown("""
### What this is
A demand-forecasting + inventory-control tool for FBA restocking. Forecasts each SKU with
four interpretable methods (moving average / exponential smoothing / Holt trend / weekly
seasonal-naive), **backtest-selecting the best per SKU**, then computes safety stock, reorder
point, days of cover, stockout risk, and an MOQ-rounded reorder quantity.

- Zero-dependency analysis core (`restock/`), 8 unit tests.
- Plug in real Seller Central / ERP exports (CSV).
- Synthetic demo data is fabricated, not real sales.

*Author: Aohan Zhang · MIT License*
""")
