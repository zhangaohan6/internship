"""Demand Forecast & Inventory Restock Planner — CLI.

    python3 plan.py                      # synthetic demo (8 SKUs)
    python3 plan.py --n 20 --service 0.95 --horizon 30
    python3 plan.py --csv my_skus.csv    # sku,title,daily_sales(|-sep),current_stock,lead_time_days,min_order_qty,unit_cost
"""
from __future__ import annotations

import argparse
import os

from restock.data import generate_skus, load_skus_csv
from restock.forecast import best_forecast
from restock.inventory import demand_stats, recommend
from restock.report import to_markdown, to_csv


def build_rows(skus, horizon=30, service=0.95, review_period=14):
    rows = []
    for s in skus:
        fc, method, mape = best_forecast(s.daily_sales, horizon)
        avg_daily, sigma = demand_stats(s.daily_sales)
        rec = recommend(avg_daily, sigma, s.current_stock, s.lead_time_days,
                        service_level=service, review_period=review_period, moq=s.min_order_qty)
        rows.append({
            "sku": s.sku, "title": s.title, "method": method, "mape": mape,
            "forecast_30": int(round(sum(fc))), "unit_cost": s.unit_cost, **rec,
        })
    # urgency: reorder-now first, then soonest stockout
    rows.sort(key=lambda r: (not r["reorder_now"],
                             r["stockout_in_days"] if r["stockout_in_days"] is not None else 1e9))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Demand forecast & restock planner")
    ap.add_argument("--csv", help="SKU CSV")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--service", type=float, default=0.95)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    skus = load_skus_csv(args.csv) if args.csv else generate_skus(args.n, args.days, args.seed)
    rows = build_rows(skus, horizon=args.horizon, service=args.service)

    os.makedirs(args.out, exist_ok=True)
    md = to_markdown(rows)
    with open(os.path.join(args.out, "restock_plan.md"), "w", encoding="utf-8") as f:
        f.write(md)
    to_csv(rows, os.path.join(args.out, "restock_plan.csv"))
    print(md)
    n_reorder = sum(1 for r in rows if r["reorder_now"])
    urgent = [r for r in rows if r["reorder_now"]]
    soonest = min((r["stockout_in_days"] for r in rows if r["stockout_in_days"] is not None),
                  default=None)
    print(f"{n_reorder}/{len(rows)} SKUs need reorder · soonest stockout in "
          f"{soonest} days · plan written to {args.out}/restock_plan.md")


if __name__ == "__main__":
    main()
