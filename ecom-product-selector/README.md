# E-Commerce Product Selection & Profit Analyzer

A **zero-dependency** Python tool that automates the spreadsheet work cross-border
e-commerce teams do by hand: compute the full **FBA landed-profit waterfall** for each
candidate product and rank a niche by a transparent **product-selection Opportunity Score**.

> Built to demonstrate data-driven product sourcing — the analysis an operations analyst
> does in Excel, made reproducible, auditable, and scalable.

## What it computes

**Per-unit profit waterfall** (`ecom/profit.py`):
`net = price − referral fee − FBA fulfilment − storage − COGS − inbound freight − ad spend`
→ **net profit, margin, ROI** (return on cash invested), and **breakeven ACoS** (the max ad
cost a unit can carry before it loses money).

**Opportunity Score** (`ecom/scoring.py`) — a 0–100 score from four min-max-normalised,
transparently-weighted sub-scores, with a hard minimum-margin gate:
`demand ↑ · profitability ↑ · low review barrier ↑ · low competition ↑`.

## Quick start (no install, no data needed)

```bash
python3 analyze.py                       # synthetic demo: ranks 200 products
python3 analyze.py --n 300 --top 20      # bigger run
python3 analyze.py --csv my_export.csv   # your real data (see schema below)
```
Outputs a ranked shortlist to stdout and to `out/shortlist.md` + `out/shortlist.csv`.

Example (synthetic, seed 0): of 200 candidates, **94 clear a 10% margin gate**; the top pick
scores **84** with **41% margin / 202% ROI / 58% breakeven-ACoS**.

## Validation on REAL Amazon data

Beyond the synthetic demo, the analyzer runs on a **real** Amazon products dataset (1,001
listings scraped via Bright Data; no-login mirror
[here](https://raw.githubusercontent.com/luminati-io/Amazon-dataset-samples/main/amazon-products.csv)):

```bash
pip install pandas
python3 analyze.py --real amazon-products.csv --top 10
```
`ecom/real_data.py` maps the real columns (price, reviews, category, sellers, weight, rating,
Best-Sellers Rank) onto the schema; COGS and ACoS use documented seller assumptions, and
monthly sales is a proxy derived from BSR.

**Finding (real-data insight).** Of 1,001 real products, only **376 (38%) clear a 10% margin
gate** once Amazon's referral + FBA + storage fees and ad spend are subtracted — many
electronics are squeezed below viability. This is the kind of unit-economics reality a raw
keyword tool (Helium 10) shows you the *inputs* for but doesn't *decide* on; this tool adds
the profit-and-selection decision layer on top.

## Interactive dashboard

```bash
pip install streamlit pandas
streamlit run app.py
```
Three tabs — **Product Selection** (opportunity-map scatter + ranked shortlist), **PPC
Planner** (pick a product → keyword plan with an ACoS-vs-volume scatter), and **About**.
Upload a real product CSV or tune the scoring weights / margin gate live in the sidebar.

## PPC keyword analyzer

`ppc_analyze.py` ties advertising economics to the product's unit profit — which keywords to
bid on and how much:

```bash
python3 ppc_analyze.py                              # demo product + keyword pool
python3 ppc_analyze.py --price 34.99 --breakeven-acos 0.45
python3 ppc_analyze.py --keywords my_keywords.csv   # term,search_volume,cpc,cvr,competing_products
```
Per keyword it computes **ACoS, ROAS, max-profitable CPC, a recommended bid** (target 70% of
breakeven), and **profit-per-sale**, then ranks by volume × profit-headroom × low-competition.
Example: of 40 keywords, **27 are profitable** at suggested CPC; top keyword ROAS 3.5, max
profitable CPC $1.24.

## Plug in real data

Export from Helium 10 / Jungle Scout / an Amazon report and map the headers to the
`Product` schema (`ecom/profit.py`): `asin,title,category,price,cogs,inbound_shipping,
weight_lb,longest_in,volume_cuft,acos,monthly_sales,avg_review_count,num_sellers,avg_rating`,
then `python3 analyze.py --csv your_file.csv`.

## Layout
```
ecom/
  fees.py      # Amazon referral % + FBA fulfilment fee tiers (configurable)
  profit.py    # landed-profit waterfall (margin / ROI / breakeven ACoS)
  scoring.py   # product-selection Opportunity Score
  data.py      # synthetic generator + CSV loader
  report.py    # markdown + CSV shortlist
  ppc.py       # PPC keyword economics (ACoS / ROAS / max-CPC / recommended bid)
analyze.py     # CLI: product selection shortlist
ppc_analyze.py # CLI: PPC keyword plan
tests/         # 8 behavioural tests (profit math, fees, scoring, PPC)
```

## Tests
```bash
python3 -m pytest -q            # or: pip install pytest first
```

## Notes
- Fee tables approximate Amazon's published US schedule (2024–2026) and are **configurable**
  for your category/marketplace — edit `ecom/fees.py`.
- The synthetic dataset is fabricated for demonstration; it is **not** real marketplace data.

*Author: Aohan Zhang · MIT License*
