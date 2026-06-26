"""Synthetic product dataset (so the repo runs with zero real data / zero API) and a CSV
loader so you can drop in real exports (Helium 10 / Jungle Scout / Amazon) mapped to the
Product schema.

NOTE: the generated data is fabricated for demonstration; it is not real marketplace data.
"""
from __future__ import annotations

import csv
import random

from .profit import Product
from .ppc import Keyword

_KW_HEAD = ["best", "cheap", "portable", "stainless", "for travel", "heavy duty",
            "with lid", "set of 2", "for kids", "rechargeable", "bpa free", "large"]
_KW_ROOT = ["water bottle", "desk organizer", "yoga mat", "dog brush", "led lamp",
            "phone holder", "knife set", "cable clip", "spray bottle", "step tracker"]


def generate_keywords(n: int = 40, seed: int = 0):
    """Synthetic keyword pool (search volume, suggested CPC, conversion rate, competition)."""
    rng = random.Random(seed)
    kws = []
    for _ in range(n):
        term = f"{rng.choice(_KW_HEAD)} {rng.choice(_KW_ROOT)}"
        kws.append(Keyword(
            term=term,
            search_volume=int(rng.lognormvariate(7.0, 1.0)),     # monthly searches
            cpc=round(rng.uniform(0.35, 2.20), 2),
            cvr=round(rng.uniform(0.05, 0.18), 3),
            competing_products=rng.randint(50, 3000),
        ))
    return kws

CATEGORIES = ["home_kitchen", "beauty", "sports", "tools", "pet", "office", "toys", "electronics"]
_ADJ = ["Premium", "Eco", "Compact", "Pro", "Smart", "Portable", "Heavy-Duty", "Mini", "Deluxe"]
_NOUN = ["Organizer", "Bottle", "Holder", "Brush", "Mat", "Lamp", "Cutter", "Stand", "Pump", "Tracker"]


def generate_products(n: int = 200, seed: int = 0):
    rng = random.Random(seed)
    products = []
    for i in range(n):
        cat = rng.choice(CATEGORIES)
        price = round(rng.uniform(12, 60), 2)
        weight = round(rng.uniform(0.2, 4.0), 2)
        cogs = round(price * rng.uniform(0.18, 0.42), 2)        # 18-42% of price
        inbound = round(weight * rng.uniform(0.4, 1.1), 2)      # freight scales with weight
        # demand: heavy-tailed (most niches small, a few big)
        monthly_sales = int(rng.lognormvariate(5.7, 0.9))       # ~ a few hundred typical
        reviews = int(rng.lognormvariate(5.5, 1.1))             # incumbent review barrier
        sellers = rng.randint(3, 40)
        rating = round(rng.uniform(3.6, 4.8), 1)
        acos = round(rng.uniform(0.12, 0.40), 2)
        products.append(Product(
            asin=f"B0{i:06d}", title=f"{rng.choice(_ADJ)} {rng.choice(_NOUN)}",
            category=cat, price=price, cogs=cogs, inbound_shipping=inbound,
            weight_lb=weight, longest_in=round(rng.uniform(5, 16), 1),
            volume_cuft=round(rng.uniform(0.03, 0.4), 3), acos=acos,
            monthly_sales=monthly_sales, avg_review_count=reviews,
            num_sellers=sellers, avg_rating=rating,
        ))
    return products


_NUMERIC = {"price", "cogs", "inbound_shipping", "weight_lb", "longest_in",
            "volume_cuft", "acos", "months_of_stock", "avg_rating"}
_INT = {"monthly_sales", "avg_review_count", "num_sellers"}


def load_products_csv(path: str):
    """Load products from a CSV whose header matches the Product fields."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kw = {}
            for k, v in row.items():
                if v is None or v == "":
                    continue
                if k in _NUMERIC:
                    kw[k] = float(v)
                elif k in _INT:
                    kw[k] = int(float(v))
                else:
                    kw[k] = v
            out.append(Product(**kw))
    return out
