"""
marketplace/validators.py — Custom Validators
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def validate_positive_decimal(value):
    if value is not None and value < Decimal("0.00"):
        raise ValidationError(_("Value must be zero or positive."))


def validate_future_date(value):
    if value and value < timezone.now():
        raise ValidationError(_("Date must be in the future."))


def validate_coupon_code(value):
    if not value.isalnum():
        raise ValidationError(_("Coupon code must be alphanumeric (letters and digits only)."))
    if len(value) < 4 or len(value) > 50:
        raise ValidationError(_("Coupon code must be between 4 and 50 characters."))


def validate_sku(value):
    import re
    if not re.match(r"^[A-Za-z0-9\-_]+$", value):
        raise ValidationError(_("SKU can only contain letters, digits, hyphens, and underscores."))


def validate_rating(value):
    if value < 1 or value > 5:
        raise ValidationError(_("Rating must be between 1 and 5."))


def validate_phone_bd(value):
    import re
    pattern = r"^(?:\+880|880|0)?1[3-9]\d{8}$"
    if not re.match(pattern, value):
        raise ValidationError(_("Enter a valid Bangladeshi phone number."))


def validate_nid_number(value):
    cleaned = value.replace(" ", "").replace("-", "")
    if not cleaned.isdigit():
        raise ValidationError(_("NID number must contain only digits."))
    if len(cleaned) not in (10, 13, 17):
        raise ValidationError(_("NID number must be 10, 13, or 17 digits long."))


def validate_image_size(image, max_mb=5):
    """Validate image does not exceed max_mb."""
    limit = max_mb * 1024 * 1024
    if image.size > limit:
        raise ValidationError(_(f"Image size must not exceed {max_mb}MB."))


def validate_date_range(start, end):
    """Ensure start < end."""
    if start and end and start >= end:
        raise ValidationError(_("Start date must be before end date."))


def validate_commission_rate(value):
    if value < Decimal("0") or value > Decimal("100"):
        raise ValidationError(_("Commission rate must be between 0% and 100%."))
