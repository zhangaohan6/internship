"""PPC keyword analyzer — which keywords to bid on, and how much.

    python3 ppc_analyze.py                          # demo: a sample product + keyword pool
    python3 ppc_analyze.py --price 34.99 --breakeven-acos 0.45
    python3 ppc_analyze.py --keywords my_keywords.csv   # headers: term,search_volume,cpc,cvr,competing_products

For a real product, get its breakeven ACoS from analyze.py / ecom.profit first.
"""
from __future__ import annotations

import argparse
import csv
import os

from ecom.profit import compute_profit
from ecom.data import generate_products, generate_keywords
from ecom.ppc import Keyword, rank_keywords


def load_keywords_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(Keyword(term=r["term"], search_volume=int(float(r["search_volume"])),
                               cpc=float(r["cpc"]), cvr=float(r["cvr"]),
                               competing_products=int(float(r.get("competing_products", 0) or 0))))
    return out


def to_markdown(ranked, price, be, top_n=15):
    lines = [f"# PPC Keyword Plan  (price ${price:.2f}, breakeven-ACoS {be*100:.0f}%)", ""]
    lines.append("| # | Keyword | Vol | CPC | CVR | ACoS | ROAS | Max CPC | Rec. bid | $/sale | Score |")
    lines.append("|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for i, r in enumerate(ranked[:top_n], 1):
        flag = "" if r["profitable"] else " ⚠️"
        lines.append(
            f"| {i} | {r['term']}{flag} | {r['search_volume']} | ${r['cpc']:.2f} | "
            f"{r['cvr']*100:.0f}% | {r['acos']*100:.0f}% | {r['roas']:.1f} | "
            f"${r['max_profitable_cpc']:.2f} | ${r['recommended_bid']:.2f} | "
            f"${r['profit_per_sale']:.2f} | **{r['kw_score']:.0f}** |")
    n_prof = sum(1 for r in ranked if r["profitable"])
    lines += ["", f"**{n_prof}/{len(ranked)}** keywords are profitable at suggested CPC "
              "(ACoS < breakeven). ⚠️ = unprofitable (bid below Max CPC or skip).",
              "", "*Max CPC = highest bid that still breaks even; Rec. bid targets 70% of "
              "breakeven ACoS; ROAS = revenue / ad-spend.*"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="PPC keyword analyzer")
    ap.add_argument("--price", type=float)
    ap.add_argument("--breakeven-acos", type=float)
    ap.add_argument("--keywords", help="CSV of keywords")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    if args.price and args.breakeven_acos:
        price, be = args.price, args.breakeven_acos
    else:                                  # demo: derive from a sample product
        p = generate_products(1, seed=3)[0]
        pr = compute_profit(p)
        price, be = pr.price, pr.breakeven_acos
        print(f"(demo product: {p.title}  price ${price:.2f}  breakeven-ACoS {be*100:.0f}%)\n")

    kws = load_keywords_csv(args.keywords) if args.keywords else generate_keywords(40, seed=1)
    ranked = rank_keywords(price, be, kws)

    md = to_markdown(ranked, price, be, top_n=args.top)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ppc_plan.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"PPC plan written to {args.out}/ppc_plan.md")


if __name__ == "__main__":
    main()
