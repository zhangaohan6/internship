"""Render a restock plan to Markdown + CSV, most-urgent first."""
from __future__ import annotations

import csv


def to_markdown(rows, top_n=30) -> str:
    lines = ["# Restock Plan", ""]
    lines.append("Most urgent first (reorder-now, then soonest stockout). "
                 "Forecast method auto-selected by backtest MAPE per SKU.")
    lines.append("")
    lines.append("| SKU | Avg/day | 30d fcst | Method | MAPE | Stock | Cover(d) | ROP | "
                 "Stockout(d) | Risk | Reorder? | Qty |")
    lines.append("|---|--:|--:|---|--:|--:|--:|--:|--:|--:|:--:|--:|")
    for r in rows[:top_n]:
        flag = "🔴" if r["reorder_now"] else "·"
        lines.append(
            f"| {r['sku']} | {r['avg_daily']:.1f} | {r['forecast_30']} | {r['method']} | "
            f"{r['mape']*100:.0f}% | {r['current_stock']} | "
            f"{r['days_of_cover'] if r['days_of_cover'] is not None else '∞'} | "
            f"{r['reorder_point']} | "
            f"{r['stockout_in_days'] if r['stockout_in_days'] is not None else '∞'} | "
            f"{r['stockout_risk_lead_time']*100:.0f}% | {flag} | {r['reorder_qty']} |")
    n_reorder = sum(1 for r in rows if r["reorder_now"])
    cost = sum(r["reorder_qty"] * r["unit_cost"] for r in rows)
    lines += ["", f"**{n_reorder}/{len(rows)}** SKUs need reordering now · "
              f"recommended PO value **${cost:,.0f}**.",
              "", "*Cover = days of stock left; ROP = reorder point (lead-time demand + safety "
              "stock); Risk = P(stockout during lead time).*"]
    return "\n".join(lines) + "\n"


def to_csv(rows, path):
    if not rows:
        return
    cols = ["sku", "title", "avg_daily", "forecast_30", "method", "mape", "current_stock",
            "days_of_cover", "reorder_point", "reorder_now", "reorder_qty",
            "stockout_in_days", "stockout_risk_lead_time", "safety_stock", "unit_cost"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
