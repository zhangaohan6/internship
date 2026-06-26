"""Render a ranked product-selection shortlist to Markdown + CSV."""
from __future__ import annotations

import csv


def to_markdown(ranked, top_n: int = 15) -> str:
    lines = ["# Product Selection Shortlist", ""]
    lines.append(f"Ranked {len(ranked)} candidates by Opportunity Score "
                 "(demand × profitability × low barrier × low competition).")
    lines.append("")
    lines.append("| # | Product | Cat | Price | Net/unit | Margin | ROI | BE-ACoS | Mo.Sales | Reviews | Score |")
    lines.append("|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for i, r in enumerate(ranked[:top_n], 1):
        flag = "" if r["viable"] else " ⚠️"
        lines.append(
            f"| {i} | {r['title']}{flag} | {r['category']} | ${r['price']:.2f} | "
            f"${r['net_profit']:.2f} | {r['margin']*100:.0f}% | {r['roi']*100:.0f}% | "
            f"{r['breakeven_acos']*100:.0f}% | {r['monthly_sales']} | {r['avg_review_count']} | "
            f"**{r['opportunity_score']:.0f}** |")
    lines.append("")
    n_viable = sum(1 for r in ranked if r["viable"])
    lines.append(f"**{n_viable}/{len(ranked)}** candidates clear the margin gate; "
                 "⚠️ = below the minimum-margin threshold (shown but de-ranked).")
    lines.append("")
    lines.append("*Columns: Net/unit = landed net profit after referral + FBA + storage + COGS "
                 "+ freight + ad spend; ROI = net / cash invested; BE-ACoS = breakeven ad cost.*")
    return "\n".join(lines) + "\n"


def to_csv(ranked, path: str):
    if not ranked:
        return
    cols = ["asin", "title", "category", "price", "net_profit", "margin", "roi",
            "breakeven_acos", "monthly_sales", "avg_review_count", "num_sellers",
            "opportunity_score", "viable"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in ranked:
            w.writerow(r)
