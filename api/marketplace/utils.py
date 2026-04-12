"""
marketplace/utils.py — Utility Functions
"""

from __future__ import annotations

import random
import string
import uuid
from decimal import Decimal
from typing import Optional
from django.utils.text import slugify


# ──────────────────────────────────────────────
# ID & Code Generators
# ──────────────────────────────────────────────

def generate_order_number() -> str:
    """ORD + 8 random digits. e.g. ORD84729301"""
    return f"ORD{random.randint(10_000_000, 99_999_999)}"


def generate_coupon_code(length: int = 8) -> str:
    """Uppercase alphanumeric coupon code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def generate_sku(product_name: str, variant_suffix: str = "") -> str:
    """SKU from product name slug + random 4 chars."""
    base = slugify(product_name).upper().replace("-", "")[:8]
    rand = "".join(random.choices(string.digits, k=4))
    suffix = f"-{variant_suffix.upper()}" if variant_suffix else ""
    return f"{base}-{rand}{suffix}"


def generate_transaction_ref() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


# ──────────────────────────────────────────────
# Price Calculations
# ──────────────────────────────────────────────

def calculate_discount_amount(price: Decimal, percent: Decimal) -> Decimal:
    """Calculate discount given price and percent (0–100)."""
    return (price * percent / 100).quantize(Decimal("0.01"))


def apply_discount(price: Decimal, percent: Decimal) -> Decimal:
    return price - calculate_discount_amount(price, percent)


def round_price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def format_price(value: Decimal, currency: str = "BDT") -> str:
    return f"{currency} {value:,.2f}"


# ──────────────────────────────────────────────
# Slug Helpers
# ──────────────────────────────────────────────

def unique_slugify(model_class, name: str, instance=None) -> str:
    """Generate a unique slug for a model, appending a number if needed."""
    base = slugify(name)
    slug = base
    n = 1
    qs = model_class.objects.filter(slug=slug)
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.exists():
        slug = f"{base}-{n}"
        n += 1
        qs = model_class.objects.filter(slug=slug)
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
    return slug


# ──────────────────────────────────────────────
# Pagination Helper
# ──────────────────────────────────────────────

def paginate_queryset(queryset, page: int = 1, page_size: int = 20) -> dict:
    from django.core.paginator import Paginator, EmptyPage
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return {
        "results": list(page_obj.object_list),
        "count": paginator.count,
        "num_pages": paginator.num_pages,
        "current_page": page_obj.number,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }


# ──────────────────────────────────────────────
# Bangladesh-Specific Helpers
# ──────────────────────────────────────────────

BD_DIVISIONS = [
    "Dhaka", "Chittagong", "Rajshahi", "Khulna",
    "Barisal", "Sylhet", "Rangpur", "Mymensingh",
]

BD_DISTRICTS = [
    "Dhaka", "Gazipur", "Narayanganj", "Narsingdi",
    "Manikganj", "Munshiganj", "Rajbari", "Faridpur",
    "Chittagong", "Cox's Bazar", "Comilla", "Sylhet",
    # …add remaining 64 as needed
]


def normalize_phone_bd(phone: str) -> str:
    """Normalize to +8801XXXXXXXXX format."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "+880" + phone[1:]
    elif phone.startswith("880"):
        phone = "+" + phone
    elif not phone.startswith("+880"):
        phone = "+880" + phone
    return phone


# ──────────────────────────────────────────────
# Date Helpers
# ──────────────────────────────────────────────

def days_until(dt) -> int:
    from django.utils import timezone
    delta = dt - timezone.now()
    return max(0, delta.days)


def is_expired(dt) -> bool:
    from django.utils import timezone
    return dt < timezone.now()
