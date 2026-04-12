"""PROMOTION_MARKETING/discount_engine.py — Unified discount resolution"""
from decimal import Decimal
from api.marketplace.models import Coupon, PromotionCampaign
from django.utils import timezone


def best_discount(tenant, product, order_amount: Decimal, coupon_code: str = "") -> Decimal:
    discounts = []

    # Campaign discount
    now = timezone.now()
    campaign = PromotionCampaign.objects.filter(
        tenant=tenant, is_active=True,
        starts_at__lte=now, ends_at__gte=now,
        products=product,
    ).first()
    if campaign:
        if campaign.discount_type == "percent":
            discounts.append(order_amount * campaign.discount_value / 100)
        else:
            discounts.append(campaign.discount_value)

    # Coupon discount
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, tenant=tenant)
            if coupon.is_valid:
                discounts.append(coupon.calculate_discount(order_amount))
        except Coupon.DoesNotExist:
            pass

    return max(discounts, default=Decimal("0.00"))
