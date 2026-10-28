# api/admin_panel/validator.py
"""
Admin Panel Validators — reusable validation functions.
Used in serializers, viewsets, management commands.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_positive_amount(value: Any, field: str = 'amount') -> Decimal:
    """Validate value is a positive decimal amount."""
    try:
        d = Decimal(str(value))
        if d <= 0:
            raise ValidationError(_(f'{field} must be greater than zero.'))
        if d > Decimal('999999999.99'):
            raise ValidationError(_(f'{field} is unreasonably large.'))
        return d
    except InvalidOperation:
        raise ValidationError(_(f'{field} must be a valid number.'))


def validate_ip_address(ip: str) -> str:
    """Validate IPv4 address format."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        raise ValidationError(_(f'Invalid IP address: {ip}'))
    parts = ip.split('.')
    if not all(0 <= int(p) <= 255 for p in parts):
        raise ValidationError(_(f'Invalid IP address: {ip}'))
    return ip


def validate_ip_not_private(ip: str) -> str:
    """Ensure IP is not a private/loopback address."""
    validate_ip_address(ip)
    private_ranges = [
        r'^10\.',
        r'^172\.(1[6-9]|2\d|3[01])\.',
        r'^192\.168\.',
        r'^127\.',
        r'^::1$',
    ]
    for pattern in private_ranges:
        if re.match(pattern, ip):
            raise ValidationError(_(f'Cannot block private IP: {ip}'))
    return ip


def validate_percentage(value: Any, field: str = 'percentage') -> int:
    """Validate 0-100 percentage."""
    try:
        v = int(value)
        if not 0 <= v <= 100:
            raise ValidationError(_(f'{field} must be between 0 and 100.'))
        return v
    except (TypeError, ValueError):
        raise ValidationError(_(f'{field} must be an integer.'))


def validate_config_key(key: str) -> str:
    """Validate system config key format: snake_case, max 200 chars."""
    if not key:
        raise ValidationError(_('Config key cannot be empty.'))
    if len(key) > 200:
        raise ValidationError(_('Config key max 200 characters.'))
    if not re.match(r'^[a-z0-9_]+$', key):
        raise ValidationError(_('Config key must be lowercase letters, numbers, underscores only.'))
    return key


def validate_flag_key(key: str) -> str:
    """Validate feature flag key."""
    if not re.match(r'^[a-z0-9_]+$', key):
        raise ValidationError(_('Flag key must be lowercase, numbers, underscores only.'))
    if len(key) > 100:
        raise ValidationError(_('Flag key max 100 characters.'))
    return key


def validate_ban_reason(reason: str) -> str:
    """Ban reason must be meaningful."""
    if not reason or len(reason.strip()) < 5:
        raise ValidationError(_('Ban reason must be at least 5 characters.'))
    if len(reason) > 500:
        raise ValidationError(_('Ban reason max 500 characters.'))
    return reason.strip()


def validate_withdrawal_amount(amount: Any, min_amount: Decimal = None, max_amount: Decimal = None) -> Decimal:
    """Validate withdrawal amount against system limits."""
    value = validate_positive_amount(amount, 'amount')
    if min_amount and value < min_amount:
        raise ValidationError(_(f'Minimum withdrawal amount is {min_amount}.'))
    if max_amount and value > max_amount:
        raise ValidationError(_(f'Maximum withdrawal amount is {max_amount}.'))
    return value


def validate_user_ids(user_ids: List[Any], max_count: int = 5000) -> List[int]:
    """Validate a list of user IDs."""
    if not user_ids:
        raise ValidationError(_('user_ids cannot be empty.'))
    if len(user_ids) > max_count:
        raise ValidationError(_(f'Maximum {max_count} user IDs allowed.'))
    try:
        return [int(uid) for uid in user_ids]
    except (TypeError, ValueError):
        raise ValidationError(_('All user_ids must be integers.'))


def validate_date_range(start_date, end_date) -> None:
    """Validate start_date is before end_date."""
    if start_date and end_date and start_date > end_date:
        raise ValidationError(_('start_date must be before end_date.'))


def validate_json_payload(data: Any, max_size_kb: int = 100) -> dict:
    """Validate JSON payload size."""
    import json
    if not isinstance(data, dict):
        raise ValidationError(_('Payload must be a JSON object.'))
    size = len(json.dumps(data))
    if size > max_size_kb * 1024:
        raise ValidationError(_(f'Payload too large. Max {max_size_kb}KB.'))
    return data


def validate_cron_expression(cron: str) -> str:
    """Basic cron expression format validation."""
    parts = cron.strip().split()
    if len(parts) not in (5, 6):
        raise ValidationError(_('Invalid cron expression. Expected 5 or 6 fields.'))
    return cron.strip()


def validate_phone_number(phone: str) -> str:
    """Validate international phone number format."""
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if not re.match(r'^\+?[1-9]\d{6,14}$', cleaned):
        raise ValidationError(_('Invalid phone number format.'))
    return cleaned


def validate_gateway_type(gateway: str) -> str:
    """Validate payment gateway name."""
    valid = ['bkash', 'nagad', 'rocket', 'upay', 'tap', 'paypal', 'stripe',
             'bank_transfer', 'crypto', 'payoneer', 'wise']
    if gateway.lower() not in valid:
        raise ValidationError(_(f'Invalid gateway. Choose from: {valid}'))
    return gateway.lower()