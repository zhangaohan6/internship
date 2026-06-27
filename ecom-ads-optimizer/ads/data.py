"""Load a real ad-performance CSV, or generate a small synthetic one so the repo runs
without any data file.

Real dataset used for validation: 'Global Ads Performance (Google, Meta, TikTok)' (Kaggle,
1,800 campaign-day rows, 2024). It is a *simulated* multi-platform dataset (real ad-spend
data is rarely public) — the value here is the optimization analysis, which is real.
"""
from __future__ import annotations

import random

import pandas as pd

REQUIRED = ["platform", "campaign_type", "impressions", "clicks",
            "ad_spend", "conversions", "revenue"]
PLATFORMS = ["Google Ads", "Meta Ads", "TikTok Ads"]
TYPES = ["Search", "Video", "Shopping", "Display"]


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    return df


def generate_synthetic(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        impr = rng.randint(2000, 200000)
        clicks = max(1, int(impr * rng.uniform(0.005, 0.05)))
        spend = round(clicks * rng.uniform(0.20, 3.00), 2)
        conv = int(clicks * rng.uniform(0.01, 0.12))
        revenue = round(conv * rng.uniform(15, 80), 2)
        rows.append({
            "platform": rng.choice(PLATFORMS), "campaign_type": rng.choice(TYPES),
            "country": rng.choice(["US", "UK", "DE", "AU"]),
            "impressions": impr, "clicks": clicks, "ad_spend": spend,
            "conversions": conv, "revenue": revenue,
        })
    return pd.DataFrame(rows)
