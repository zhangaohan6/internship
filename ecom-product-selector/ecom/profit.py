"""Landed-profit waterfall for an FBA product.

Per unit:  net = price - referral - fba - storage - cogs - inbound_shipping - ppc
Key outputs every sourcing decision needs:
  * net_profit / unit
  * margin           = net_profit / price
  * roi              = net_profit / cash_invested (cogs + inbound)   ← the number sourcing cares about
  * breakeven_acos   = max ad cost (% of revenue) before the unit loses money
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .fees import referral_fee, fba_fulfilment_fee, monthly_storage_fee_per_unit


@dataclass
class Product:
    asin: str
    title: str
    category: str
    price: float            # selling price (USD)
    cogs: float             # manufacturing cost / unit (USD)
    inbound_shipping: float # freight to FBA / unit (USD)
    weight_lb: float
    longest_in: float = 10.0
    volume_cuft: float = 0.10
    acos: float = 0.25      # advertising cost of sale (ad spend / ad revenue)
    months_of_stock: float = 1.0
    # market signals (used by scoring, not profit)
    monthly_sales: int = 0
    avg_review_count: int = 0   # review barrier of incumbents
    num_sellers: int = 0
    avg_rating: float = 4.3


@dataclass
class ProfitResult:
    asin: str
    title: str
    price: float
    referral: float
    fba: float
    storage: float
    cogs: float
    inbound: float
    ppc: float
    net_profit: float
    margin: float
    roi: float
    breakeven_acos: float

    def as_dict(self):
        return asdict(self)


def compute_profit(p: Product) -> ProfitResult:
    referral = referral_fee(p.price, p.category)
    fba = fba_fulfilment_fee(p.weight_lb, p.longest_in)
    storage = monthly_storage_fee_per_unit(p.volume_cuft, p.months_of_stock)
    ppc = p.price * p.acos                       # ad spend attributed per unit sold
    pre_ad = p.price - referral - fba - storage - p.cogs - p.inbound_shipping
    net = pre_ad - ppc
    margin = net / p.price if p.price else 0.0
    invested = p.cogs + p.inbound_shipping
    roi = net / invested if invested else 0.0
    breakeven_acos = pre_ad / p.price if p.price else 0.0  # ad fraction that zeroes profit
    return ProfitResult(
        asin=p.asin, title=p.title, price=round(p.price, 2),
        referral=round(referral, 2), fba=round(fba, 2), storage=round(storage, 2),
        cogs=round(p.cogs, 2), inbound=round(p.inbound_shipping, 2), ppc=round(ppc, 2),
        net_profit=round(net, 2), margin=round(margin, 4), roi=round(roi, 4),
        breakeven_acos=round(breakeven_acos, 4),
    )
