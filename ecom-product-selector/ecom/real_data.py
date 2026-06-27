"""Adapter for a REAL Amazon products dataset (1,001 listings scraped via Bright Data;
no-login mirror: github.com/luminati-io/Amazon-dataset-samples → amazon-products.csv).

Maps real columns (final_price, reviews_count, categories, number_of_sellers, item_weight,
rating, root_bs_rank, asin) onto the Product schema. Two fields aren't in the listing data
and use documented assumptions — exactly what a seller estimates:
  * cogs  — assumed ≈ 35% of selling price
  * acos  — assumed 0.25 (typical ad cost of sale)
And monthly_sales is a *proxy* derived from Best-Sellers Rank (lower rank ⇒ higher sales).

Requires pandas (only for this real-data path; the analysis core stays zero-dependency).
"""
from __future__ import annotations

import re

from .profit import Product


def _num(x):
    if x is None:
        return None
    s = re.sub(r"[^0-9.]", "", str(x).replace(",", ""))
    try:
        return float(s) if s not in ("", ".") else None
    except ValueError:
        return None


def _weight_lb(x):
    s = str(x).lower()
    n = _num(s)
    if n is None:
        return None
    if "ounce" in s or " oz" in s:
        return round(n / 16.0, 2)
    if "kg" in s or "kilogram" in s:
        return round(n * 2.205, 2)
    if "gram" in s or re.search(r"\b\d+\s*g\b", s):
        return round(n / 453.6, 2)
    return round(n, 2)  # default: pounds


def _first_category(x):
    s = str(x)
    s = re.sub(r"[\[\]'\"]", "", s)
    for sep in ("›", "|", ",", ">"):
        if sep in s:
            return s.split(sep)[0].strip()[:24] or "general"
    return s.strip()[:24] or "general"


def _demand_proxy(bs_rank, reviews):
    rank = _num(bs_rank)
    if rank and rank > 0:
        return int(max(5, min(8000, 40000 / (rank ** 0.5))))   # monotone in rank
    r = _num(reviews) or 0
    return int(max(5, r / 2))                                   # fallback: from reviews


def load_amazon_csv(path, cogs_frac=0.35, default_acos=0.25, max_rows=None):
    import pandas as pd

    df = pd.read_csv(path)
    products = []
    for i, row in df.iterrows():
        if max_rows and len(products) >= max_rows:
            break
        price = _num(row.get("final_price")) or _num(row.get("initial_price"))
        if not price or price <= 0:
            continue
        weight = _weight_lb(row.get("item_weight")) or 0.5
        reviews = int(_num(row.get("reviews_count")) or 0)
        sellers = int(_num(row.get("number_of_sellers")) or 1)
        products.append(Product(
            asin=str(row.get("asin") or f"row{i}"),
            title=str(row.get("title") or "")[:40],
            category=_first_category(row.get("categories")),
            price=round(price, 2),
            cogs=round(price * cogs_frac, 2),                 # assumption
            inbound_shipping=round(weight * 0.6, 2),          # assumption (freight ~ weight)
            weight_lb=weight,
            acos=default_acos,                                # assumption
            monthly_sales=_demand_proxy(row.get("root_bs_rank"), reviews),  # proxy from BSR
            avg_review_count=reviews,
            num_sellers=max(sellers, 1),
            avg_rating=round(_num(row.get("rating")) or 4.3, 1),
        ))
    return products
