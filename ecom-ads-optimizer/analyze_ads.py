"""Ad Performance & ROAS Optimizer — CLI.

    python3 analyze_ads.py                         # synthetic demo data
    python3 analyze_ads.py --real ads.csv          # real Global Ads Performance CSV
    python3 analyze_ads.py --real ads.csv --margin 0.30 --by platform

Flags below-breakeven (money-losing) ad spend and quantifies a budget-reallocation upside.
"""
from __future__ import annotations

import argparse
import os

from ads.data import load_csv, generate_synthetic
from ads.metrics import add_derived, breakeven_roas, summarize, by_segment, wasted_spend
from ads.optimize import reallocation_plan
from ads.report import to_markdown


def main():
    ap = argparse.ArgumentParser(description="Ad performance & ROAS optimizer")
    ap.add_argument("--real", help="path to a Global Ads Performance CSV")
    ap.add_argument("--margin", type=float, default=0.30, help="product gross margin (sets breakeven ROAS)")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    df = load_csv(args.real) if args.real else generate_synthetic()
    df = add_derived(df)

    be = breakeven_roas(args.margin)
    summary = summarize(df)
    seg_platform = by_segment(df, "platform")
    seg_type = by_segment(df, "campaign_type")
    wasted = wasted_spend(df, be)
    plan = reallocation_plan(df, be)

    md = to_markdown(summary, seg_platform, seg_type, wasted, plan, args.margin)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ads_report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    seg_platform.to_csv(os.path.join(args.out, "by_platform.csv"), index=False)
    print(md)
    print(f"{wasted['rows_below']} rows below breakeven ROAS {be} · "
          f"${wasted['wasted_spend']:,.0f} wasted ({wasted['wasted_share']*100:.0f}%) · "
          f"reallocation upside ≈ ${plan['incremental_revenue']:,.0f}")
    print(f"Report written to {args.out}/ads_report.md")


if __name__ == "__main__":
    main()
