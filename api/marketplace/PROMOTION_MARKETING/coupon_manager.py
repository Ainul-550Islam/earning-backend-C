"""PROMOTION_MARKETING/coupon_manager.py — Coupon CRUD helpers"""
from api.marketplace.models import Coupon
from api.marketplace.utils import generate_coupon_code
from django.utils import timezone


def create_coupon(tenant, created_by, name: str, discount_value, coupon_type: str,
                  valid_from=None, valid_until=None, **kwargs) -> Coupon:
    from datetime import timedelta
    code = generate_coupon_code()
    return Coupon.objects.create(
        tenant=tenant,
        created_by=created_by,
        code=code,
        name=name,
        coupon_type=coupon_type,
        discount_value=discount_value,
        valid_from=valid_from or timezone.now(),
        valid_until=valid_until or timezone.now() + timedelta(days=30),
        **kwargs,
    )


def deactivate_expired_coupons(tenant) -> int:
    now = timezone.now()
    return Coupon.objects.filter(tenant=tenant, valid_until__lt=now, is_active=True
                                  ).update(is_active=False)
