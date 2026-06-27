"""Render the ad-performance optimization report to Markdown."""
from __future__ import annotations


def _seg_table(g, dim_label):
    lines = [f"### By {dim_label}", "",
             f"| {dim_label} | Spend | Revenue | ROAS | ACoS | CPA | Spend share |",
             "|---|--:|--:|--:|--:|--:|--:|"]
    dim = g.columns[0]
    for _, r in g.iterrows():
        lines.append(f"| {r[dim]} | ${r['spend']:,.0f} | ${r['revenue']:,.0f} | "
                     f"{r['roas']:.2f} | {r['acos']*100:.0f}% | ${r['cpa']:.2f} | "
                     f"{r['spend_share']*100:.0f}% |")
    return "\n".join(lines) + "\n"


def to_markdown(summary, by_platform, by_type, wasted, plan, margin) -> str:
    s = summary
    L = ["# Ad Performance & ROAS Optimization", ""]
    L.append(f"**{s['rows']} campaign rows** · spend **${s['spend']:,.0f}** · revenue "
             f"**${s['revenue']:,.0f}** · blended **ROAS {s['roas']:.2f}** · "
             f"ACoS {s['acos']*100:.0f}% · CPA ${s['cpa']:.2f} · CTR {s['ctr']*100:.2f}% · "
             f"CVR {s['cvr']*100:.1f}%")
    L.append("")
    L.append(f"Breakeven ROAS at a **{margin*100:.0f}% product margin** is "
             f"**{wasted['breakeven_roas']}** — spend on rows below it is losing money.")
    L.append("")
    L.append("## Wasted spend (below breakeven ROAS)")
    L.append(f"- **{wasted['rows_below']} rows** are below breakeven ROAS")
    L.append(f"- **${wasted['wasted_spend']:,.0f}** of spend ({wasted['wasted_share']*100:.0f}% "
             f"of total) is below breakeven, returning only ${wasted['revenue_from_wasted']:,.0f}")
    L.append("")
    L.append("## Budget reallocation opportunity")
    L.append(f"- Redeploying the **${plan['reallocatable_spend']:,.0f}** of below-breakeven "
             f"spend at the portfolio's top-quartile ROAS ({plan['target_roas']}, discounted "
             f"to {plan['assumed_redeploy_roas']} for diminishing returns):")
    L.append(f"  - projected revenue **${plan['projected_revenue']:,.0f}** vs current "
             f"**${plan['current_revenue_on_it']:,.0f}**")
    L.append(f"  - **≈ ${plan['incremental_revenue']:,.0f} incremental revenue** from the same budget")
    L.append("")
    L.append(_seg_table(by_platform, "Platform"))
    L.append(_seg_table(by_type, "Campaign type"))
    L.append("*ROAS = revenue / ad-spend; ACoS = ad-spend / revenue; CPA = spend / conversion.*")
    return "\n".join(L) + "\n"
