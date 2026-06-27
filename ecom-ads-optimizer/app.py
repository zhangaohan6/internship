"""Streamlit dashboard for the Ad Performance & ROAS Optimizer.

Run:  streamlit run app.py     (needs: pip install streamlit pandas)
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from ads.data import load_csv, generate_synthetic
from ads.metrics import add_derived, breakeven_roas, summarize, by_segment, wasted_spend
from ads.optimize import reallocation_plan

st.set_page_config(page_title="ROAS Optimizer", page_icon="📣", layout="wide")
st.title("📣 Ad Performance & ROAS Optimizer")
st.caption("Multi-platform ad analysis · wasted-spend detection · budget reallocation")

with st.sidebar:
    st.header("Data")
    up = st.file_uploader("Ad performance CSV (optional)", type="csv")
    margin = st.slider("Product gross margin", 0.10, 0.70, 0.30, 0.05)
    be = breakeven_roas(margin)
    st.metric("Breakeven ROAS", be)

if up is not None:
    tmp = os.path.join("out", "_up.csv"); os.makedirs("out", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(up.getvalue())
    df = load_csv(tmp)
else:
    df = generate_synthetic()
df = add_derived(df)

s = summarize(df)
w = wasted_spend(df, be)
plan = reallocation_plan(df, be)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Spend", f"${s['spend']:,.0f}")
c2.metric("Revenue", f"${s['revenue']:,.0f}")
c3.metric("Blended ROAS", f"{s['roas']:.2f}")
c4.metric("Wasted (below breakeven)", f"{w['wasted_share']*100:.0f}%")

st.info(f"**{w['rows_below']} campaign rows** are below breakeven ROAS {be} — "
        f"**${w['wasted_spend']:,.0f}** of spend losing money. Reallocating it at top-quartile "
        f"efficiency projects **≈ ${plan['incremental_revenue']:,.0f} incremental revenue**.")

tab1, tab2 = st.tabs(["By platform", "By campaign type"])
for tab, dim in [(tab1, "platform"), (tab2, "campaign_type")]:
    with tab:
        g = by_segment(df, dim)
        st.bar_chart(g.set_index(dim)["roas"], height=260)
        show = g.copy()
        show["acos"] = (show["acos"] * 100).round(0)
        show["spend_share"] = (show["spend_share"] * 100).round(0)
        st.dataframe(show, use_container_width=True)
