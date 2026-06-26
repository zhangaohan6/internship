"""Amazon US marketplace fee model (simplified, configurable, ~2024-2026 schedule).

Fees here are approximations of Amazon's published schedules and are intended to be
configurable — adjust the tables for your category/marketplace. Two fees dominate the
landed-profit waterfall:

  * Referral fee  — a % of the sale price, category-dependent (most categories 15%).
  * FBA fulfilment fee — a flat per-unit fee determined by size tier + shipping weight.

References: Amazon Selling on Amazon Fee Schedule; FBA fulfilment fee tiers.
"""
from __future__ import annotations

# Referral fee rate by category (fraction of sale price). Default 0.15.
REFERRAL_RATES = {
    "electronics": 0.08,
    "home_kitchen": 0.15,
    "toys": 0.15,
    "beauty": 0.15,        # 0.08 if price <= $10 in some sub-cats
    "sports": 0.15,
    "tools": 0.15,
    "pet": 0.15,
    "office": 0.15,
    "apparel": 0.17,
    "jewelry": 0.20,
    "default": 0.15,
}

MIN_REFERRAL_FEE = 0.30  # Amazon's per-item minimum referral fee (USD)


def referral_fee(price: float, category: str = "default") -> float:
    rate = REFERRAL_RATES.get(category, REFERRAL_RATES["default"])
    return max(price * rate, MIN_REFERRAL_FEE)


# FBA fulfilment fee: size tier inferred from weight + dimensions, then a weight-based fee.
# Simplified standard-size schedule (USD per unit).
def _size_tier(weight_lb: float, longest_in: float) -> str:
    if weight_lb <= 1.0 and longest_in <= 15:
        return "small_standard"
    if weight_lb <= 20 and longest_in <= 18:
        return "large_standard"
    return "oversize"


def fba_fulfilment_fee(weight_lb: float, longest_in: float = 10.0) -> float:
    tier = _size_tier(weight_lb, longest_in)
    if tier == "small_standard":
        # up to 16 oz, banded
        if weight_lb <= 0.25:
            return 3.06
        if weight_lb <= 0.50:
            return 3.27
        if weight_lb <= 0.75:
            return 3.48
        return 3.65
    if tier == "large_standard":
        if weight_lb <= 0.75:
            return 3.86
        if weight_lb <= 1.5:
            return 4.31
        if weight_lb <= 3.0:
            return 5.36
        # +$0.38 per half-lb above 3 lb (approx)
        return 5.36 + ((weight_lb - 3.0) / 0.5) * 0.38
    # oversize (rough)
    return 9.0 + weight_lb * 0.40


def monthly_storage_fee_per_unit(volume_cuft: float, months_of_stock: float = 1.0) -> float:
    """Approx FBA storage: ~$0.87/cu ft/month (Jan-Sep standard). Per unit over stock period."""
    return volume_cuft * 0.87 * months_of_stock
