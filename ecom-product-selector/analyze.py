"""E-Commerce Product Selection & Profit Analyzer — CLI.

Load (or synthesise) candidate products, compute the landed-profit waterfall for each, score
them for sourcing opportunity, and write a ranked shortlist.

    python3 analyze.py                       # synthetic demo data
    python3 analyze.py --csv my_export.csv   # your Helium10/JungleScout export (mapped headers)
    python3 analyze.py --n 300 --top 20 --out out/
"""
from __future__ import annotations

import argparse
import os

from ecom.data import generate_products, load_products_csv
from ecom.profit import compute_profit
from ecom.scoring import score_products
from ecom.report import to_markdown, to_csv


def build_rows(products):
    rows = []
    for p in products:
        pr = compute_profit(p)
        rows.append({
            # identity + economics
            "asin": p.asin, "title": p.title, "category": p.category,
            "price": pr.price, "net_profit": pr.net_profit, "margin": pr.margin,
            "roi": pr.roi, "breakeven_acos": pr.breakeven_acos,
            # market signals for scoring
            "monthly_sales": p.monthly_sales, "avg_review_count": p.avg_review_count,
            "num_sellers": p.num_sellers,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Product selection & profit analyzer")
    ap.add_argument("--csv", help="CSV of products (headers match the Product schema)")
    ap.add_argument("--n", type=int, default=200, help="synthetic products if no --csv")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-margin", type=float, default=0.10)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    products = load_products_csv(args.csv) if args.csv else generate_products(args.n, args.seed)
    rows = build_rows(products)
    ranked = score_products(rows, min_margin=args.min_margin)

    os.makedirs(args.out, exist_ok=True)
    md = to_markdown(ranked, top_n=args.top)
    with open(os.path.join(args.out, "shortlist.md"), "w", encoding="utf-8") as f:
        f.write(md)
    to_csv(ranked, os.path.join(args.out, "shortlist.csv"))

    n_viable = sum(1 for r in ranked if r["viable"])
    print(md)
    print(f"Analysed {len(ranked)} products · {n_viable} viable (margin ≥ {args.min_margin:.0%}) · "
          f"top pick: {ranked[0]['title']} (score {ranked[0]['opportunity_score']:.0f}, "
          f"{ranked[0]['margin']*100:.0f}% margin, {ranked[0]['roi']*100:.0f}% ROI)")
    print(f"Reports written to {args.out}/shortlist.md and shortlist.csv")


if __name__ == "__main__":
    main()
