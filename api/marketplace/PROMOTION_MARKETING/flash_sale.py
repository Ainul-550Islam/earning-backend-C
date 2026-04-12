"""
PROMOTION_MARKETING/flash_sale.py — Flash Sale Management
"""
from __future__ import annotations
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import PromotionCampaign, Product
from api.marketplace.enums import PromotionType


def active_flash_sales(tenant) -> list:
    """Get all currently live flash sales."""
    now = timezone.now()
    return list(
        PromotionCampaign.objects.filter(
            tenant=tenant, promotion_type=PromotionType.FLASH_SALE,
            is_active=True, starts_at__lte=now, ends_at__gte=now,
        ).prefetch_related("products","categories")
    )


def upcoming_flash_sales(tenant, hours: int = 24) -> list:
    """Flash sales starting within the next N hours."""
    now     = timezone.now()
    future  = now + timezone.timedelta(hours=hours)
    return list(
        PromotionCampaign.objects.filter(
            tenant=tenant, promotion_type=PromotionType.FLASH_SALE,
            is_active=True, starts_at__gt=now, starts_at__lte=future,
        )
    )


@transaction.atomic
def create_flash_sale(tenant, created_by, name: str, discount_value: Decimal,
                       discount_type: str, starts_at, ends_at,
                       product_ids: list = None, max_items: int = None) -> PromotionCampaign:
    from api.marketplace.utils import unique_slugify
    slug = unique_slugify(PromotionCampaign, name)
    campaign = PromotionCampaign.objects.create(
        tenant=tenant, created_by=created_by, name=name, slug=slug,
        promotion_type=PromotionType.FLASH_SALE,
        discount_value=discount_value, discount_type=discount_type,
        starts_at=starts_at, ends_at=ends_at,
        is_active=True, max_items=max_items,
    )
    if product_ids:
        campaign.products.set(Product.objects.filter(pk__in=product_ids, tenant=tenant))
    return campaign


def get_flash_sale_products(campaign: PromotionCampaign) -> list:
    """Get all products in a flash sale with discounted prices."""
    products = campaign.products.filter(status="active")
    result   = []
    for p in products:
        if campaign.discount_type == "percent":
            disc_price = p.effective_price * (1 - campaign.discount_value / 100)
        else:
            disc_price = max(Decimal("0"), p.effective_price - campaign.discount_value)
        result.append({
            "product_id":       p.pk,
            "name":             p.name,
            "original_price":   str(p.effective_price),
            "flash_price":      str(disc_price.quantize(Decimal("0.01"))),
            "discount_percent": float(campaign.discount_value) if campaign.discount_type == "percent" else
                                round((p.effective_price - disc_price) / p.effective_price * 100, 1),
            "time_remaining":   _time_remaining(campaign),
        })
    return result


def _time_remaining(campaign: PromotionCampaign) -> dict:
    now   = timezone.now()
    delta = campaign.ends_at - now
    if delta.total_seconds() <= 0:
        return {"hours": 0, "minutes": 0, "seconds": 0, "ended": True}
    total_seconds = int(delta.total_seconds())
    return {
        "hours":   total_seconds // 3600,
        "minutes": (total_seconds % 3600) // 60,
        "seconds": total_seconds % 60,
        "ended":   False,
    }


def flash_sale_performance(campaign: PromotionCampaign) -> dict:
    from api.marketplace.models import OrderItem
    from django.db.models import Sum, Count
    product_ids = list(campaign.products.values_list("pk",flat=True))
    items = OrderItem.objects.filter(
        variant__product_id__in=product_ids,
        order__created_at__range=[campaign.starts_at, campaign.ends_at],
    )
    agg = items.aggregate(revenue=Sum("subtotal"), orders=Count("order",distinct=True), units=Sum("quantity"))
    return {
        "name":     campaign.name,
        "started":  campaign.starts_at.strftime("%Y-%m-%d %H:%M"),
        "ended":    campaign.ends_at.strftime("%Y-%m-%d %H:%M"),
        "revenue":  str(agg["revenue"] or 0),
        "orders":   agg["orders"] or 0,
        "units":    agg["units"] or 0,
        "products": campaign.products.count(),
    }
