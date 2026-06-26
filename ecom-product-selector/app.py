"""Streamlit dashboard for the E-Commerce Product Selection & Profit Analyzer.

Run:  streamlit run app.py
(needs:  pip install streamlit pandas)
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from ecom.data import generate_products, load_products_csv, generate_keywords
from ecom.profit import compute_profit
from ecom.scoring import score_products, DEFAULT_WEIGHTS
from ecom.ppc import rank_keywords
from analyze import build_rows

st.set_page_config(page_title="E-Commerce Product Selector", page_icon="🛒", layout="wide")
st.title("🛒 E-Commerce Product Selection & Profit Analyzer")
st.caption("FBA landed-profit waterfall · product-selection opportunity score · PPC keyword economics")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Data")
    up = st.file_uploader("Product CSV (optional)", type="csv")
    n = st.slider("Synthetic products", 50, 500, 200, 50, disabled=up is not None)
    seed = st.number_input("Seed", 0, 9999, 0, disabled=up is not None)
    min_margin = st.slider("Minimum margin gate", 0.0, 0.4, 0.10, 0.01)
    st.header("Scoring weights")
    w = {k: st.slider(k, 0.0, 1.0, float(v), 0.05) for k, v in DEFAULT_WEIGHTS.items()}
    tot = sum(w.values()) or 1.0
    w = {k: v / tot for k, v in w.items()}

# ── Load + analyse ────────────────────────────────────────────────────────────
if up is not None:
    tmp = os.path.join("out", "_uploaded.csv"); os.makedirs("out", exist_ok=True)
    with open(tmp, "wb") as f:
        f.write(up.getvalue())
    products = load_products_csv(tmp)
else:
    products = generate_products(int(n), int(seed))

ranked = score_products(build_rows(products), weights=w, min_margin=min_margin)
df = pd.DataFrame(ranked)

tab1, tab2, tab3 = st.tabs(["Product Selection", "PPC Planner", "About"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", len(df))
    c2.metric("Viable (≥ margin gate)", int(df["viable"].sum()))
    c3.metric("Median margin", f"{df['margin'].median()*100:.0f}%")
    c4.metric("Top score", f"{df['opportunity_score'].max():.0f}")

    st.subheader("Opportunity map")
    st.caption("x = monthly sales (demand) · y = margin · bubble shade = opportunity score")
    chart_df = df[["monthly_sales", "margin", "opportunity_score", "title"]].copy()
    st.scatter_chart(chart_df, x="monthly_sales", y="margin", color="opportunity_score",
                     size="opportunity_score", height=360)

    st.subheader("Ranked shortlist")
    show = df[["title", "category", "price", "net_profit", "margin", "roi",
               "breakeven_acos", "monthly_sales", "avg_review_count",
               "opportunity_score", "viable"]].copy()
    show["margin"] = (show["margin"] * 100).round(0)
    show["roi"] = (show["roi"] * 100).round(0)
    show["breakeven_acos"] = (show["breakeven_acos"] * 100).round(0)
    st.dataframe(show, use_container_width=True, height=420)

with tab2:
    st.subheader("PPC keyword plan")
    viable_titles = df[df["viable"]]["title"].tolist()
    pick = st.selectbox("Pick a product (uses its price + breakeven ACoS)",
                        viable_titles or df["title"].tolist())
    row = df[df["title"] == pick].iloc[0]
    price, be = float(row["price"]), float(row["breakeven_acos"])
    st.write(f"**{pick}** — price ${price:.2f}, breakeven ACoS {be*100:.0f}%")
    kws = generate_keywords(40, seed=1)
    kr = pd.DataFrame(rank_keywords(price, be, kws))
    m1, m2 = st.columns(2)
    m1.metric("Profitable keywords", f"{int(kr['profitable'].sum())}/{len(kr)}")
    m2.metric("Best ROAS", f"{kr['roas'].max():.1f}")
    st.caption("x = search volume · y = ACoS (lower better) · shade = profitable")
    st.scatter_chart(kr.assign(prof=kr["profitable"].astype(int)),
                     x="search_volume", y="acos", color="prof", height=320)
    kshow = kr[["term", "search_volume", "cpc", "acos", "roas", "max_profitable_cpc",
                "recommended_bid", "profit_per_sale", "kw_score", "profitable"]].copy()
    kshow["acos"] = (kshow["acos"] * 100).round(0)
    st.dataframe(kshow, use_container_width=True, height=420)

with tab3:
    st.markdown("""
### What this is
A data-driven cross-border e-commerce sourcing tool. It computes the full **FBA landed-profit
waterfall** (referral + FBA + storage + COGS + freight + ad spend → net margin, ROI,
breakeven ACoS), ranks a niche by a transparent **Opportunity Score**, and plans **PPC**
keyword bids tied to unit profit.

- Zero-dependency analysis core (`ecom/`), 8 unit tests.
- Plug in real Helium 10 / Jungle Scout exports (CSV).
- Synthetic demo data is fabricated, not real marketplace data.

*Author: Aohan Zhang · MIT License*
""")
