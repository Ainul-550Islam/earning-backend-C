"""
DATABASE_MODELS/coupon_table.py — Coupon Table Reference & Queries
"""
from api.marketplace.models import Coupon
from api.marketplace.enums import CouponType
from django.db.models import Sum
from django.utils import timezone


def active_coupons(tenant) -> list:
    now = timezone.now()
    return list(Coupon.objects.filter(
        tenant=tenant, is_active=True, valid_from__lte=now, valid_until__gte=now
    ).order_by("-created_at"))


def coupon_usage_stats(tenant) -> list:
    return list(
        Coupon.objects.filter(tenant=tenant)
        .values("code","coupon_type","discount_value","usage_limit","used_count")
        .order_by("-used_count")[:20]
    )


def expiring_soon(tenant, days: int = 3) -> list:
    deadline = timezone.now() + timezone.timedelta(days=days)
    return list(Coupon.objects.filter(
        tenant=tenant, is_active=True, valid_until__lte=deadline,
        valid_until__gte=timezone.now()
    ))


__all__ = ["Coupon","CouponType","active_coupons","coupon_usage_stats","expiring_soon"]
