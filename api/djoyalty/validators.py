# api/djoyalty/validators.py
"""
Djoyalty -- custom validators।
Model field validators + serializer validators।
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
import re


def validate_positive(value):
    """Value অবশ্যই positive হতে হবে।"""
    if value is not None and value < 0:
        raise ValidationError(f'Value must be positive. Got: {value}')


def validate_non_negative(value):
    """Value negative হতে পারবে না।"""
    if value is not None and value < 0:
        raise ValidationError(f'Value cannot be negative. Got: {value}')


def validate_percentage(value):
    """Value 0-100 এর মধ্যে হতে হবে।"""
    if value is not None:
        val = Decimal(str(value))
        if not (Decimal('0') <= val <= Decimal('100')):
            raise ValidationError(f'Percentage must be between 0 and 100. Got: {value}')


def validate_multiplier(value):
    """Multiplier অবশ্যই > 0 হতে হবে।"""
    if value is not None and Decimal(str(value)) <= Decimal('0'):
        raise ValidationError(f'Multiplier must be greater than 0. Got: {value}')


def validate_customer_code(value):
    """
    Customer code validation।
    Only uppercase letters, digits, hyphens allowed।
    """
    if value and not re.match(r'^[A-Z0-9\-_]+$', value):
        raise ValidationError(
            'Customer code can only contain uppercase letters, digits, hyphens, and underscores.'
        )


def validate_voucher_code(value):
    """Voucher code validation -- uppercase alphanumeric।"""
    if value and not re.match(r'^[A-Z0-9\-]+$', value):
        raise ValidationError(
            'Voucher code can only contain uppercase letters, digits, and hyphens.'
        )


def validate_api_key(value):
    """API key format validation।"""
    if value and len(value) < 8:
        raise ValidationError('API key must be at least 8 characters long.')


def validate_points_amount(value):
    """Points amount -- positive decimal।"""
    try:
        decimal_value = Decimal(str(value))
        if decimal_value <= Decimal('0'):
            raise ValidationError('Points amount must be greater than 0.')
    except Exception:
        raise ValidationError('Invalid points amount.')


def validate_tier_name(value):
    """Valid tier name।"""
    from .constants import TIER_ORDER
    if value and value not in TIER_ORDER:
        raise ValidationError(
            f'Invalid tier name: {value}. Must be one of: {", ".join(TIER_ORDER)}'
        )


def validate_earn_rate(value):
    """Earn rate must be > 0 and <= 100।"""
    try:
        val = Decimal(str(value))
        if not (Decimal('0') < val <= Decimal('100')):
            raise ValidationError('Earn rate must be between 0 (exclusive) and 100.')
    except ValidationError:
        raise
    except Exception:
        raise ValidationError('Invalid earn rate.')


def validate_phone_number(value):
    """Phone number format।"""
    if value and not re.match(r'^\+?[\d\s\-]{7,20}$', value):
        raise ValidationError('Enter a valid phone number.')


def validate_https_url(value):
    """URL must be HTTPS।"""
    if value and not value.startswith('https://'):
        raise ValidationError('URL must use HTTPS.')


def validate_webhook_secret(value):
    """Webhook secret minimum length।"""
    if value and len(value) < 16:
        raise ValidationError('Webhook secret must be at least 16 characters.')


def validate_date_range(start, end):
    """End date must be after start date।"""
    if start and end and end <= start:
        raise ValidationError('End date must be after start date.')
