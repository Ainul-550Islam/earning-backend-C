# api/djoyalty/utils.py
"""
Djoyalty utility functions — pure helpers, no side effects।
"""

import hashlib
import hmac
import logging
import random
import string
import uuid
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, Union
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)


# ==================== POINTS CALCULATIONS ====================

def calculate_points_to_earn(
    spend_amount: Decimal,
    earn_rate: Decimal,
    multiplier: Decimal = Decimal('1.0'),
    bonus: Decimal = Decimal('0'),
) -> Decimal:
    """
    খরচের পরিমাণ থেকে অর্জিত পয়েন্ট হিসাব করো।
    
    Args:
        spend_amount: খরচের পরিমাণ
        earn_rate: প্রতি ১ unit spend এ কত পয়েন্ট
        multiplier: tier বা campaign multiplier
        bonus: extra flat bonus পয়েন্ট
    
    Returns:
        অর্জিত পয়েন্ট (২ decimal places)
    """
    if spend_amount <= 0:
        return Decimal('0')
    base_points = spend_amount * earn_rate * multiplier
    total_points = base_points + bonus
    return total_points.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_points_value(
    points: Decimal,
    point_value: Decimal,
) -> Decimal:
    """
    পয়েন্টের টাকার মূল্য হিসাব করো।
    
    Args:
        points: পয়েন্টের পরিমাণ
        point_value: প্রতি পয়েন্টের মূল্য
    
    Returns:
        টাকার মূল্য
    """
    if points <= 0:
        return Decimal('0')
    return (points * point_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def safe_decimal(value, default=Decimal('0')) -> Decimal:
    """
    যেকোনো value কে safely Decimal এ convert করো।
    """
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        logger.debug('Could not convert %s to Decimal, using default %s', value, default)
        return default


def round_points(value: Decimal, places: int = 2) -> Decimal:
    """পয়েন্ট round করো।"""
    quantizer = Decimal('0.' + '0' * places)
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


# ==================== CODE GENERATION ====================

def generate_voucher_code(length: int = 12) -> str:
    """
    Unique voucher code generate করো।
    Format: XXXX-XXXX-XXXX (uppercase alphanumeric)
    """
    from .constants import VOUCHER_CODE_LENGTH
    length = length or VOUCHER_CODE_LENGTH
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    raw = ''.join(random.choices(chars, k=length))
    # Groups of 4
    groups = [raw[i:i+4] for i in range(0, len(raw), 4)]
    return '-'.join(groups)


def generate_gift_card_code(prefix: str = 'GC', length: int = 16) -> str:
    """Gift card code generate করো।"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    raw = ''.join(random.choices(chars, k=length))
    return f'{prefix}-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}'


def generate_referral_code(customer_code: str) -> str:
    """Customer referral code generate করো।"""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    base = customer_code[:6].upper() if customer_code else 'REF'
    return f'{base}{suffix}'


def generate_secure_token(length: int = 32) -> str:
    """Cryptographically secure random token।"""
    return uuid.uuid4().hex[:length]


# ==================== TIER HELPERS ====================

def get_tier_for_points(total_points: Decimal) -> str:
    """
    Points এর উপর ভিত্তি করে tier নির্ধারণ করো।
    
    Returns:
        tier name (bronze/silver/gold/platinum/diamond)
    """
    from .constants import TIER_THRESHOLDS
    current_tier = 'bronze'
    for tier_name, threshold in sorted(
        TIER_THRESHOLDS.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        if total_points >= threshold:
            current_tier = tier_name
            break
    return current_tier


def get_next_tier(current_tier: str) -> Optional[str]:
    """
    পরবর্তী tier কোনটি।
    Diamond হলে None।
    """
    from .choices import TIER_RANK
    tier_order = sorted(TIER_RANK.items(), key=lambda x: x[1])
    tier_names = [t[0] for t in tier_order]
    try:
        idx = tier_names.index(current_tier)
        if idx + 1 < len(tier_names):
            return tier_names[idx + 1]
        return None
    except ValueError:
        return None


def get_points_needed_for_next_tier(
    total_points: Decimal,
    current_tier: str,
) -> Optional[Decimal]:
    """
    Next tier এর জন্য কত পয়েন্ট বাকি।
    """
    from .constants import TIER_THRESHOLDS
    next_tier = get_next_tier(current_tier)
    if not next_tier:
        return None
    next_threshold = TIER_THRESHOLDS.get(next_tier)
    if next_threshold is None:
        return None
    needed = next_threshold - total_points
    return max(Decimal('0'), needed)


def get_tier_multiplier(tier_name: str) -> Decimal:
    """Tier এর earn multiplier।"""
    from .constants import TIER_EARN_MULTIPLIERS
    return TIER_EARN_MULTIPLIERS.get(tier_name, Decimal('1.0'))


# ==================== DATE HELPERS ====================

def get_expiry_date(days: int) -> Optional['datetime']:
    """
    আজ থেকে X দিন পরের expiry date।
    days=0 মানে কখনো expire হবে না।
    """
    if not days or days <= 0:
        return None
    return timezone.now() + timedelta(days=days)


def days_until_expiry(expires_at) -> Optional[int]:
    """
    Expiry পর্যন্ত কত দিন বাকি।
    None মানে expire হবে না।
    """
    if expires_at is None:
        return None
    now = timezone.now()
    if expires_at <= now:
        return 0
    delta = expires_at - now
    return delta.days


def is_birthday_today(birth_date: date) -> bool:
    """আজ customer এর জন্মদিন কিনা।"""
    if not birth_date:
        return False
    today = timezone.now().date()
    return birth_date.month == today.month and birth_date.day == today.day


def get_period_start(period: str = 'month') -> 'datetime':
    """
    Period এর শুরু timestamp।
    period: 'day', 'week', 'month', 'year'
    """
    now = timezone.now()
    if period == 'day':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now


# ==================== HMAC / SECURITY ====================

def generate_hmac_signature(payload: bytes, secret: str) -> str:
    """
    Webhook payload এর HMAC-SHA256 signature।
    """
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f'sha256={signature}'


def verify_hmac_signature(payload: bytes, secret: str, signature: str) -> bool:
    """
    HMAC signature verify করো।
    Timing-attack safe।
    """
    expected = generate_hmac_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


def mask_sensitive_value(value: str, visible: int = 4) -> str:
    """
    Sensitive value mask করো।
    Example: 'ABCDEF1234' → 'ABCD******'
    """
    if not value:
        return '****'
    value = str(value)
    if len(value) <= visible:
        return '*' * len(value)
    return value[:visible] + '*' * (len(value) - visible)


# ==================== FORMATTING ====================

def format_points(points: Decimal, suffix: str = 'pts') -> str:
    """Points কে human-readable format এ।"""
    if points >= 1_000_000:
        return f'{points / 1_000_000:.1f}M {suffix}'
    elif points >= 1_000:
        return f'{points / 1_000:.1f}K {suffix}'
    return f'{points:.0f} {suffix}'


def format_currency(amount: Decimal, currency: str = 'BDT') -> str:
    """Amount কে currency format এ।"""
    return f'{currency} {amount:,.2f}'


def get_tier_badge_emoji(tier_name: str) -> str:
    """Tier badge emoji।"""
    badges = {
        'bronze': '🥉',
        'silver': '🥈',
        'gold': '🥇',
        'platinum': '💎',
        'diamond': '💠',
    }
    return badges.get(tier_name, '⭐')


# ==================== PAGINATION HELPERS ====================

def build_pagination_meta(page, paginator) -> dict:
    """DRF pagination meta data।"""
    return {
        'page': page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_next': page.has_next(),
        'has_previous': page.has_previous(),
    }


# ==================== SAFE OPERATIONS ====================

def safe_divide(numerator, denominator, default=Decimal('0')) -> Decimal:
    """Zero-division safe divide।"""
    try:
        num = Decimal(str(numerator))
        den = Decimal(str(denominator))
        if den == 0:
            return default
        return num / den
    except (InvalidOperation, TypeError, ValueError):
        return default


def clamp(value, min_val, max_val):
    """Value কে min-max এর মধ্যে রাখো।"""
    return max(min_val, min(max_val, value))


def chunks(lst, n):
    """List কে n-size chunk এ ভাগ করো।"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ==================== TENANT HELPERS ====================

def get_tenant_from_request(request) -> Optional[object]:
    """Request থেকে tenant নিরাপদে নাও।"""
    return getattr(request, 'tenant', None)


def filter_by_tenant(queryset, tenant):
    """Queryset কে tenant দিয়ে filter করো।"""
    if tenant is None:
        return queryset
    return queryset.filter(tenant=tenant)


# ==================== AUDIT HELPERS ====================

def build_audit_log_message(action: str, actor, target, extra: dict = None) -> str:
    """Audit log message তৈরি করো।"""
    parts = [f'[{action.upper()}]']
    if actor:
        parts.append(f'by={actor}')
    if target:
        parts.append(f'target={target}')
    if extra:
        for k, v in extra.items():
            parts.append(f'{k}={v}')
    return ' '.join(parts)
