"""
MARKETPLACE_SAFETY/price_manipulation.py — Price Manipulation Detection
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# If price drops more than 90% suddenly → suspicious
MAX_INSTANT_DISCOUNT_PCT = Decimal("90")
# If price is 10x category average → suspicious
MAX_PRICE_MULTIPLIER     = 10


def check_price_change(product, new_price: Decimal) -> dict:
    """Validate a price change before saving."""
    flags = []
    old_price = product.base_price

    if old_price and old_price > 0:
        change_pct = abs(new_price - old_price) / old_price * 100
        if change_pct > MAX_INSTANT_DISCOUNT_PCT:
            flags.append({
                "type": "extreme_price_change",
                "old_price": str(old_price),
                "new_price": str(new_price),
                "change_pct": str(round(change_pct, 1)),
                "severity": "high",
            })

    if new_price <= Decimal("0.01"):
        flags.append({"type": "near_zero_price", "severity": "high"})

    # Check vs category average
    if product.category:
        from api.marketplace.models import Product
        from django.db.models import Avg
        cat_avg = Product.objects.filter(
            category=product.category, status="active"
        ).aggregate(avg=Avg("base_price"))["avg"]
        if cat_avg and new_price > cat_avg * MAX_PRICE_MULTIPLIER:
            flags.append({
                "type":     "price_far_above_category",
                "cat_avg":  str(round(cat_avg, 2)),
                "new_price":str(new_price),
                "severity": "medium",
            })

    return {"allowed": len([f for f in flags if f["severity"]=="high"]) == 0,
            "flags": flags}


def detect_price_spiking(tenant, days: int = 7) -> list:
    """Find products whose price increased dramatically recently."""
    from api.marketplace.models import Product
    from django.utils import timezone
    suspicious = []
    for p in Product.objects.filter(tenant=tenant, status="active"):
        if p.sale_price and p.base_price:
            fake_discount = (p.base_price - p.sale_price) / p.base_price * 100
            if fake_discount > 80:
                suspicious.append({
                    "product_id":   p.pk,
                    "name":         p.name,
                    "base_price":   str(p.base_price),
                    "sale_price":   str(p.sale_price),
                    "fake_discount":str(round(fake_discount, 1)) + "%",
                })
    return suspicious
