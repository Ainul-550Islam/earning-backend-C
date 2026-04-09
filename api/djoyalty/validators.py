# api/djoyalty/validators.py
"""
Djoyalty validators — model field এবং serializer উভয়ের জন্য।
"""

import re
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError

logger = logging.getLogger(__name__)


# ==================== POINTS VALIDATORS ====================

def validate_positive_points(value):
    """Points অবশ্যই positive হতে হবে।"""
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid points value.')
    if dec_val <= 0:
        raise DjangoValidationError(f'Points must be positive. Got: {value}')
    return dec_val


def validate_non_negative_points(value):
    """Points 0 বা positive হতে হবে।"""
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid points value.')
    if dec_val < 0:
        raise DjangoValidationError(f'Points cannot be negative. Got: {value}')
    return dec_val


def validate_points_range(value, min_points=None, max_points=None):
    """Points range validation।"""
    from .constants import MIN_REDEMPTION_POINTS, MAX_REDEMPTION_POINTS
    min_p = min_points or Decimal(str(MIN_REDEMPTION_POINTS))
    max_p = max_points or Decimal(str(MAX_REDEMPTION_POINTS))
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid points value.')
    if dec_val < min_p:
        raise DjangoValidationError(
            f'Points must be at least {min_p}. Got: {dec_val}'
        )
    if dec_val > max_p:
        raise DjangoValidationError(
            f'Points cannot exceed {max_p}. Got: {dec_val}'
        )
    return dec_val


def validate_transfer_amount(value):
    """Transfer amount validation।"""
    from .constants import TRANSFER_MIN_POINTS, TRANSFER_MAX_POINTS
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid transfer amount.')
    if dec_val < TRANSFER_MIN_POINTS:
        raise DjangoValidationError(
            f'Minimum transfer is {TRANSFER_MIN_POINTS} points.'
        )
    if dec_val > TRANSFER_MAX_POINTS:
        raise DjangoValidationError(
            f'Maximum transfer is {TRANSFER_MAX_POINTS} points.'
        )
    return dec_val


# ==================== CUSTOMER CODE VALIDATORS ====================

def validate_customer_code(value):
    """
    Customer code:
    - 3–32 characters
    - Alphanumeric + hyphen + underscore
    - Case insensitive (stored uppercase)
    """
    if not value or not str(value).strip():
        raise DjangoValidationError('Customer code cannot be empty.')
    code = str(value).strip().upper()
    if len(code) < 3:
        raise DjangoValidationError('Customer code must be at least 3 characters.')
    if len(code) > 32:
        raise DjangoValidationError('Customer code cannot exceed 32 characters.')
    if not re.match(r'^[A-Z0-9_\-]+$', code):
        raise DjangoValidationError(
            'Customer code can only contain letters, numbers, hyphens, and underscores.'
        )
    return code


# ==================== EMAIL VALIDATORS ====================

def validate_loyalty_email(value):
    """Simple email validation — blank/None OK।"""
    if not value:
        return value
    value = str(value).strip().lower()
    if '@' not in value or '.' not in value.split('@')[-1]:
        raise DjangoValidationError(f'Invalid email address: {value}')
    if len(value) > 254:
        raise DjangoValidationError('Email address is too long.')
    return value


# ==================== PHONE VALIDATORS ====================

def validate_phone_number(value):
    """Phone number — digits, +, spaces, hyphens।"""
    if not value:
        return value
    phone = re.sub(r'[\s\-\(\)]', '', str(value))
    if not re.match(r'^\+?[0-9]{6,15}$', phone):
        raise DjangoValidationError(f'Invalid phone number: {value}')
    return value


# ==================== VOUCHER CODE VALIDATORS ====================

def validate_voucher_code(value):
    """Voucher code format।"""
    if not value or not str(value).strip():
        raise DjangoValidationError('Voucher code cannot be empty.')
    code = str(value).strip().upper()
    if len(code) < 6:
        raise DjangoValidationError('Voucher code must be at least 6 characters.')
    if len(code) > 32:
        raise DjangoValidationError('Voucher code cannot exceed 32 characters.')
    if not re.match(r'^[A-Z0-9_\-]+$', code):
        raise DjangoValidationError(
            'Voucher code can only contain letters, numbers, hyphens, and underscores.'
        )
    return code


# ==================== DISCOUNT VALIDATORS ====================

def validate_discount_value(value, voucher_type):
    """Voucher discount value validation।"""
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid discount value.')
    if dec_val <= 0:
        raise DjangoValidationError('Discount value must be positive.')
    if voucher_type == 'percent' and dec_val > 100:
        raise DjangoValidationError('Percentage discount cannot exceed 100%.')
    return dec_val


# ==================== TIER VALIDATORS ====================

def validate_tier_name(value):
    """Tier name must be valid choice।"""
    from .choices import TIER_CHOICES
    valid_tiers = [t[0] for t in TIER_CHOICES]
    if value not in valid_tiers:
        raise DjangoValidationError(
            f'Invalid tier: {value}. Must be one of: {", ".join(valid_tiers)}'
        )
    return value


# ==================== DATE VALIDATORS ====================

def validate_future_date(value):
    """Date must be in the future।"""
    from django.utils import timezone
    if value and value <= timezone.now():
        raise DjangoValidationError('Date must be in the future.')
    return value


def validate_date_range(start, end):
    """End date must be after start date।"""
    if start and end and end <= start:
        raise DjangoValidationError('End date must be after start date.')


# ==================== EARN RATE VALIDATORS ====================

def validate_earn_rate(value):
    """Earn rate must be positive and reasonable।"""
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid earn rate.')
    if dec_val <= 0:
        raise DjangoValidationError('Earn rate must be positive.')
    if dec_val > 1000:
        raise DjangoValidationError('Earn rate seems unreasonably high (max 1000).')
    return dec_val


def validate_multiplier(value):
    """Multiplier: 0.1x to 100x।"""
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid multiplier value.')
    if dec_val < Decimal('0.1'):
        raise DjangoValidationError('Multiplier must be at least 0.1x.')
    if dec_val > 100:
        raise DjangoValidationError('Multiplier cannot exceed 100x.')
    return dec_val


# ==================== GIFT CARD VALIDATORS ====================

def validate_gift_card_value(value):
    """Gift card value range।"""
    from .constants import GIFT_CARD_MIN_VALUE, GIFT_CARD_MAX_VALUE
    try:
        dec_val = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DjangoValidationError('Invalid gift card value.')
    if dec_val < GIFT_CARD_MIN_VALUE:
        raise DjangoValidationError(
            f'Gift card minimum value is {GIFT_CARD_MIN_VALUE}.'
        )
    if dec_val > GIFT_CARD_MAX_VALUE:
        raise DjangoValidationError(
            f'Gift card maximum value is {GIFT_CARD_MAX_VALUE}.'
        )
    return dec_val


# ==================== WEBHOOK URL VALIDATORS ====================

def validate_webhook_url(value):
    """Webhook URL must be HTTPS।"""
    if not value:
        return value
    if not value.startswith('https://'):
        raise DjangoValidationError('Webhook URL must use HTTPS.')
    if len(value) > 500:
        raise DjangoValidationError('Webhook URL is too long.')
    return value


# ==================== COLOR VALIDATORS ====================

def validate_hex_color(value):
    """Hex color code — #RRGGBB বা #RGB।"""
    if not value:
        return value
    if not re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', str(value)):
        raise DjangoValidationError(
            f'Invalid hex color: {value}. Use format #RRGGBB or #RGB.'
        )
    return value


# ==================== ACTION NAME VALIDATORS ====================

def validate_action_name(value):
    """Event action name — lowercase, underscores।"""
    if not value or not str(value).strip():
        raise DjangoValidationError('Action name cannot be empty.')
    action = str(value).strip().lower()
    if len(action) > 128:
        raise DjangoValidationError('Action name cannot exceed 128 characters.')
    if not re.match(r'^[a-z0-9_]+$', action):
        raise DjangoValidationError(
            'Action name can only contain lowercase letters, numbers, and underscores.'
        )
    return action


# ==================== DRF SERIALIZER VALIDATORS ====================

class UniqueForTenantValidator:
    """
    Tenant-scoped uniqueness validator।
    Serializer এ ব্যবহার করা যাবে।
    """
    def __init__(self, model, field_name, message=None):
        self.model = model
        self.field_name = field_name
        self.message = message or f'This {field_name} already exists for this tenant.'

    def __call__(self, attrs):
        tenant = attrs.get('tenant')
        field_value = attrs.get(self.field_name)
        if tenant and field_value:
            qs = self.model.objects.filter(
                tenant=tenant,
                **{self.field_name: field_value}
            )
            instance = getattr(self, 'instance', None)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise DRFValidationError({self.field_name: self.message})

    def set_context(self, serializer):
        self.instance = getattr(serializer, 'instance', None)
