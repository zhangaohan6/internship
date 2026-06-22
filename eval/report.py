"""Report generation (Product A, plan §5.3).

Takes a list of result rows — one per (agent × defense config × attack suite) — and
emits ``report.md`` + ``report.html`` with the headline metrics side by side.

Each row is a flat dict; the canonical metric keys come from ``eval.metrics.summarize``
(clean_utility, asr, utility_under_attack, latency_p50_ms, latency_p95_ms) plus the
identifying columns the runner attaches (suite, model, defense, attack).

Usage:
    from eval.report import write_report
    write_report(rows, outdir=Path("benchmarks/results"))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Column order for the comparison table: identifiers first, then metrics (§5.2 order).
ID_COLS = ["suite", "model", "backend", "defense", "attack"]
METRIC_COLS = [
    "clean_utility",
    "utility_under_attack",
    "asr",
    "concealment_rate",
    "fpr",
    "latency_p50_ms",
    "latency_p95_ms",
    "cost_overhead",
]

# Human-readable headers + whether lower is better (for the report legend).
METRIC_LABELS = {
    "clean_utility": ("Clean utility", "higher"),
    "utility_under_attack": ("Utility under attack", "higher"),
    "asr": ("ASR", "lower"),
    "concealment_rate": ("Concealment rate", "lower"),
    "fpr": ("FPR", "lower"),
    "latency_p50_ms": ("Latency p50 (ms)", "lower"),
    "latency_p95_ms": ("Latency p95 (ms)", "lower"),
    "cost_overhead": ("Cost overhead", "lower"),
}


def build_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Normalize rows into a stable-column DataFrame, missing metrics as NaN."""
    df = pd.DataFrame(rows)
    # Ensure every expected column exists so the table shape is stable across runs.
    for col in ID_COLS + METRIC_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    ordered = [c for c in ID_COLS + METRIC_COLS if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    return df[ordered + extra]


def _legend_md() -> str:
    lines = ["**Metric legend** (target direction):", ""]
    for key in METRIC_COLS:
        label, direction = METRIC_LABELS.get(key, (key, ""))
        arrow = "↓ lower is better" if direction == "lower" else "↑ higher is better"
        lines.append(f"- **{label}** — {arrow}")
    return "\n".join(lines)


def to_markdown(rows: list[dict], *, title: str = "AggreGuard benchmark") -> str:
    df = build_dataframe(rows)
    parts = [f"# {title}", "", f"{len(df)} configuration row(s).", ""]
    parts.append(df.to_markdown(index=False))
    parts.append("")
    parts.append(_legend_md())
    return "\n".join(parts) + "\n"


def to_html(rows: list[dict], *, title: str = "AggreGuard benchmark") -> str:
    df = build_dataframe(rows)
    table_html = df.to_html(index=False, na_rep="—", border=0, classes="benchmark")
    style = (
        "body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;color:#1a1a1a}"
        "table.benchmark{border-collapse:collapse;font-size:14px}"
        "table.benchmark th,table.benchmark td{padding:6px 12px;border-bottom:1px solid #e0e0e0;text-align:right}"
        "table.benchmark th{background:#f5f5f5;text-align:left}"
        "table.benchmark td:first-child,table.benchmark th:first-child{text-align:left}"
        ".legend{margin-top:1.5rem;font-size:13px;color:#555}"
    )
    legend_items = "".join(
        f"<li><b>{METRIC_LABELS[k][0]}</b> — "
        f"{'↓ lower is better' if METRIC_LABELS[k][1] == 'lower' else '↑ higher is better'}</li>"
        for k in METRIC_COLS
    )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
        f"<style>{style}</style></head><body>"
        f"<h1>{title}</h1><p>{len(df)} configuration row(s).</p>{table_html}"
        f"<div class='legend'><b>Metric legend</b><ul>{legend_items}</ul></div>"
        f"</body></html>"
    )


def write_report(
    rows: list[dict],
    *,
    outdir: Path,
    title: str = "AggreGuard benchmark",
    stem: str = "report",
) -> tuple[Path, Path]:
    """Write report.md + report.html into outdir; return their paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    md_path = outdir / f"{stem}.md"
    html_path = outdir / f"{stem}.html"
    md_path.write_text(to_markdown(rows, title=title), encoding="utf-8")
    html_path.write_text(to_html(rows, title=title), encoding="utf-8")
    return md_path, html_path
