# api/referral/helpers.py
# Utility helper functions used across the referral module
# Pure utility — no business logic, no direct DB calls from outside
# ============================================================

import re
import uuid
import hashlib
import secrets
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Code Generation ───────────────────────────────────────────────────────────

def generate_referral_code(prefix: str = 'EARN', length: int = 8) -> str:
    """
    Generate a unique referral code.
    Format: EARN + 8 random alphanumeric uppercase chars.

    Example: EARNABC12345
    """
    chars = secrets.token_hex(length).upper()[:length]
    return f'{prefix}{chars}'


def generate_tracking_token(length: int = 32) -> str:
    """
    Generate a URL-safe tracking token for email invitations.
    """
    return secrets.token_urlsafe(length)


def generate_campaign_slug(name: str) -> str:
    """
    Convert a campaign name to a URL-safe slug.
    'Summer Bonus 2025' → 'summer-bonus-2025'
    """
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    # Add unique suffix to avoid collisions
    suffix = uuid.uuid4().hex[:6]
    return f'{slug}-{suffix}'


def hash_ip_address(ip: str) -> str:
    """
    One-way hash of IP address for privacy-compliant storage.
    Useful for GDPR compliance.
    """
    salt = getattr(settings, 'SECRET_KEY', 'default-salt')[:16]
    return hashlib.sha256(f'{salt}{ip}'.encode()).hexdigest()[:32]


def mask_email(email: str) -> str:
    """
    Mask email for display: 'user@example.com' → 'u***@e***.com'
    """
    if '@' not in email:
        return '***'
    local, domain = email.split('@', 1)
    masked_local = local[0] + '***' if len(local) > 1 else '***'
    domain_parts = domain.split('.')
    masked_domain = domain_parts[0][0] + '***' if len(domain_parts[0]) > 1 else '***'
    tld = '.'.join(domain_parts[1:])
    return f'{masked_local}@{masked_domain}.{tld}'


def mask_phone(phone: str) -> str:
    """
    Mask phone number: '+8801712345678' → '+880171***5678'
    """
    if len(phone) < 8:
        return '***'
    return phone[:6] + '***' + phone[-4:]


# ── Amount Helpers ────────────────────────────────────────────────────────────

def round_commission(amount: Decimal, places: int = 4) -> Decimal:
    """
    Round commission to specified decimal places using ROUND_HALF_UP.
    Default 4 decimal places for precision.
    """
    quantizer = Decimal(f'0.{"0" * places}')
    return amount.quantize(quantizer, rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal, currency: str = '৳') -> str:
    """
    Format amount for display.
    Decimal('1234.5678') → '৳1,234.57'
    """
    rounded = float(round_commission(amount, 2))
    return f'{currency}{rounded:,.2f}'


def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """
    Safely convert any value to Decimal.
    Returns default if conversion fails.
    """
    try:
        return Decimal(str(value))
    except Exception:
        return default


def percentage_of(part: Decimal, total: Decimal) -> Decimal:
    """
    Calculate what percentage `part` is of `total`.
    Returns 0 if total is 0.
    """
    if not total or total == Decimal('0'):
        return Decimal('0')
    return round_commission((part / total) * Decimal('100'), 2)


# ── Date / Time Helpers ───────────────────────────────────────────────────────

def get_week_bounds(date=None) -> Tuple:
    """
    Get start and end of the week containing `date`.
    Returns (monday, sunday) as date objects.
    """
    if date is None:
        date = timezone.now().date()
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_month_bounds(date=None) -> Tuple:
    """
    Get first and last day of the month containing `date`.
    """
    import calendar
    if date is None:
        date = timezone.now().date()
    first = date.replace(day=1)
    last_day = calendar.monthrange(date.year, date.month)[1]
    last = date.replace(day=last_day)
    return first, last


def days_since(dt) -> int:
    """
    Return number of days since a datetime.
    """
    if dt is None:
        return 9999
    if hasattr(dt, 'date'):
        dt = dt.date()
    return (timezone.now().date() - dt).days


def format_timedelta_human(td: timedelta) -> str:
    """
    Convert timedelta to human-readable string.
    timedelta(days=3, hours=2) → '3 days 2 hours'
    """
    total_seconds = int(td.total_seconds())
    days = td.days
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    parts = []
    if days: parts.append(f'{days}d')
    if hours: parts.append(f'{hours}h')
    if minutes and not days: parts.append(f'{minutes}m')
    return ' '.join(parts) if parts else '< 1m'


# ── URL / Link Helpers ────────────────────────────────────────────────────────

def build_referral_url(code: str, base_url: str = None) -> str:
    """
    Build a full referral URL for a given code.
    """
    if base_url is None:
        base_url = getattr(settings, 'FRONTEND_URL', 'https://yourplatform.com')
    return f'{base_url.rstrip("/")}/go/{code}/'


def build_invite_url(token: str, base_url: str = None) -> str:
    """
    Build email invitation tracking URL.
    """
    if base_url is None:
        base_url = getattr(settings, 'FRONTEND_URL', 'https://yourplatform.com')
    return f'{base_url.rstrip("/")}/referral/invite/track/{token}/'


def build_registration_url(code: str, base_url: str = None) -> str:
    """
    Build registration URL with referral code pre-filled.
    """
    if base_url is None:
        base_url = getattr(settings, 'FRONTEND_URL', 'https://yourplatform.com')
    return f'{base_url.rstrip("/")}/register/?ref={code}'


def extract_ip(request) -> str:
    """
    Extract real client IP from Django request.
    Handles X-Forwarded-For, X-Real-IP, REMOTE_ADDR.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    x_real = request.META.get('HTTP_X_REAL_IP', '')
    if x_real:
        return x_real.strip()
    return request.META.get('REMOTE_ADDR', '')


def extract_user_agent(request) -> str:
    """Extract User-Agent string from request."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


# ── Validation Helpers ────────────────────────────────────────────────────────

def is_valid_referral_code_format(code: str) -> bool:
    """
    Quick format check without DB query.
    Returns True if code looks like a valid format.
    """
    if not code or len(code) < 4 or len(code) > 30:
        return False
    return bool(re.match(r'^[A-Z0-9_-]+$', code.upper()))


def is_private_ip(ip: str) -> bool:
    """
    Check if IP is a private/local address.
    Used in fraud detection — private IPs get lower suspicion.
    """
    private_ranges = [
        r'^10\.', r'^172\.(1[6-9]|2[0-9]|3[01])\.',
        r'^192\.168\.', r'^127\.', r'^::1$', r'^localhost$',
    ]
    for pattern in private_ranges:
        if re.match(pattern, ip):
            return True
    return False


def normalize_code(code: str) -> str:
    """
    Normalize referral code — uppercase, trim whitespace.
    """
    return code.strip().upper() if code else ''


# ── Data Helpers ──────────────────────────────────────────────────────────────

def chunk_list(lst: List, size: int) -> List[List]:
    """
    Split a list into chunks of given size.
    Useful for bulk operations.
    chunk_list([1,2,3,4,5], 2) → [[1,2],[3,4],[5]]
    """
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten nested dict to dot-notation keys.
    {'a': {'b': 1}} → {'a.b': 1}
    """
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}{sep}{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def safe_get(d: Dict, *keys, default=None):
    """
    Safely navigate nested dicts.
    safe_get({'a': {'b': 1}}, 'a', 'b') → 1
    safe_get({'a': {}}, 'a', 'c', default=0) → 0
    """
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def truncate_string(s: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Truncate string to max_length, adding suffix if truncated.
    """
    if not s or len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


# ── Batch Processing Helpers ──────────────────────────────────────────────────

def batch_process(items: List, processor, batch_size: int = 100) -> Dict:
    """
    Process a large list in batches.
    Returns {'processed': N, 'errors': N, 'error_details': [...]}.
    """
    processed = 0
    errors = 0
    error_details = []

    for chunk in chunk_list(items, batch_size):
        for item in chunk:
            try:
                processor(item)
                processed += 1
            except Exception as e:
                errors += 1
                error_details.append({'item': str(item), 'error': str(e)})
                logger.warning(f'[helpers.batch_process] item failed: {e}')

    return {'processed': processed, 'errors': errors, 'error_details': error_details[:10]}


# ── Serialization Helpers ─────────────────────────────────────────────────────

def decimal_to_str(d: Decimal, places: int = 2) -> str:
    """Format Decimal to fixed-point string."""
    return str(round_commission(d, places))


def model_to_dict_safe(instance, fields: List[str]) -> Dict:
    """
    Safely serialize model instance to dict.
    Only includes fields that exist on the model.
    """
    result = {}
    for field in fields:
        val = getattr(instance, field, None)
        if isinstance(val, Decimal):
            result[field] = float(val)
        elif hasattr(val, 'isoformat'):
            result[field] = val.isoformat()
        elif hasattr(val, 'pk'):
            result[field] = val.pk
        else:
            result[field] = val
    return result