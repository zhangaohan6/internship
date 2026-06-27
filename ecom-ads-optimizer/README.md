# Ad Performance & ROAS Optimizer

A Python tool that turns multi-platform ad data (Google / Meta / TikTok) into a **budget
decision**: which campaigns are profitable, how much spend is **wasted below breakeven ROAS**,
and how much revenue a **budget reallocation** could unlock — the analysis a cross-border
PPC manager does, automated and auditable.

## What it computes

- Per-campaign and per-segment **ROAS, ACoS, CPA, CTR, CVR** (recomputed from raw counts).
- **Breakeven ROAS** from product margin (`1 / margin`) — spend below it is losing money.
- **Wasted spend** detection and a **budget-reallocation** projection (redeploy losing spend
  at the portfolio's top-quartile ROAS, discounted for diminishing returns).

## Quick start

```bash
pip install pandas
python3 analyze_ads.py                       # synthetic demo
python3 analyze_ads.py --real ads.csv --margin 0.30
```

## Validation on a real-structured dataset

Validated on the **Global Ads Performance (Google, Meta, TikTok)** dataset
([Kaggle](https://www.kaggle.com/datasets), 1,800 campaign-day rows across 3 platforms × 4
campaign types, 2024; **$11.1M spend → $54.2M revenue, blended ROAS 4.88**). *The dataset is
a simulated multi-platform set — real ad-spend data is rarely public — but the optimization
analysis is real.*

**Findings (at a 30% margin → breakeven ROAS 3.33):**
- **48% of spend ($5.4M) is below breakeven ROAS** — money-losing after product margin.
- **Google Ads holds 57% of the budget but the lowest ROAS (3.47)**, while **TikTok (ROAS
  7.62) is under-funded at 24%** — a clear reallocation signal.
- Redeploying the below-breakeven spend at top-quartile efficiency projects a large revenue
  upside from the *same* budget.

## Layout
```
ads/
  data.py      # load real CSV + synthetic fallback
  metrics.py   # ROAS/ACoS/CPA/CTR/CVR, breakeven, wasted spend
  optimize.py  # budget reallocation projection
  report.py    # markdown report
analyze_ads.py # CLI
app.py         # Streamlit dashboard
tests/         # 6 tests (metrics, wasted-spend, segmentation, reallocation)
```

## Tests
```bash
python3 -m pytest -q
```

*Author: Aohan Zhang · MIT License*
