"""
PROMOTION_MARKETING/promo_code_generator.py — Promotional Code Generation Engine
"""
import random, string
from api.marketplace.models import Coupon
from api.marketplace.enums import CouponType
from django.utils import timezone
from datetime import timedelta


def generate_bulk_codes(tenant, created_by, count: int, prefix: str = "",
                         discount_value=10, coupon_type=CouponType.PERCENTAGE,
                         valid_days: int = 30) -> list:
    codes = []
    for _ in range(count):
        code = prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c = Coupon.objects.create(
            tenant=tenant, created_by=created_by, code=code, name=f"Promo {code}",
            coupon_type=coupon_type, discount_value=discount_value,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timedelta(days=valid_days),
            usage_limit=1, is_active=True,
        )
        codes.append(c.code)
    return codes


def generate_personalized_code(user, tenant, discount: int = 10) -> str:
    code = f"VIP{user.pk:06d}{random.randint(100,999)}"
    existing = Coupon.objects.filter(code=code).exists()
    if existing:
        code += str(random.randint(10,99))
    return code


def validate_code_pattern(code: str) -> bool:
    return code.isalnum() and 4 <= len(code) <= 50
