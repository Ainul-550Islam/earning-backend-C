"""
PRODUCT_MANAGEMENT/product_coupon.py — Product-level coupon checks
"""
from api.marketplace.models import Coupon


def get_applicable_coupons(tenant, product):
    from django.utils import timezone
    now = timezone.now()
    return Coupon.objects.filter(
        tenant=tenant, is_active=True,
        valid_from__lte=now, valid_until__gte=now,
    ).filter(
        applicable_products=product
    ) | Coupon.objects.filter(
        tenant=tenant, is_active=True,
        valid_from__lte=now, valid_until__gte=now,
        applicable_categories=product.category,
    ) | Coupon.objects.filter(
        tenant=tenant, is_active=True,
        valid_from__lte=now, valid_until__gte=now,
        applicable_to="all",
    )
