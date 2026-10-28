# api/djoyalty/utils.py
"""
Djoyalty -- Consolidated utility functions (AUDIT FIX v2)।

AUDIT FIX (v2 -- Deduplication):
  Previously both utils.py and helpers.py existed at the root level and
  defined overlapping functions with INCOMPATIBLE signatures:

    Function              utils.py signature          helpers.py signature
    ─────────────────────────────────────────────────────────────────────
    generate_voucher_code (length=12)                 (prefix='V', length=10)
    generate_secure_token (length=32)                 (length=32)
    format_points         (points, decimals=0)        (points, suffix=' pts')
    format_currency       (amount, symbol='৳', ..)   (amount, currency, symbol)
    days_until            (dt) -> int                 (dt) -> int
    safe_decimal          (value, default)            (value, default)
    chunk_list            (lst, chunk_size)           (lst, chunk_size)
    get_client_ip         (request)                   (request + CF header)

  The two `generate_voucher_code` variants produced incompatible voucher
  code formats ('ABCD123456789012' vs 'VABCDEFGHIJ') causing DB inconsistency
  and validation failures।

  FIX:
    1. This file (utils.py) is the SINGLE CANONICAL source for all utility
       functions। All functions from helpers.py that were unique have been
       merged here।
    2. Unified function signatures -- documented below।
    3. helpers.py is now a pure re-export shim (see helpers.py)।
    4. Callers importing from either path continue to work।

  Unified signatures for previously conflicting functions:
    generate_voucher_code(length=12, prefix='')
      -- prefix='' reproduces utils.py behaviour (no prefix)
      -- prefix='V' reproduces helpers.py behaviour
      -- VoucherService.generate_voucher() should pass prefix='' (default)

    format_points(points, decimals=0, suffix='')
      -- suffix='' reproduces utils.py behaviour (no suffix)
      -- suffix=' pts' reproduces helpers.py behaviour

    format_currency(amount, symbol='৳', decimals=2, currency='BDT')
      -- All parameters from both implementations unified

    get_client_ip(request)
      -- Now includes CF-Connecting-IP header check from helpers.py
"""
import hashlib
import hmac
import random
import re
import secrets
import string
import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Points Calculation ────────────────────────────────────────────────────────

def calculate_points_to_earn(
    spend_amount: Decimal,
    earn_rate: Decimal,
    multiplier: Decimal = Decimal('1'),
) -> Decimal:
    """
    Spend amount থেকে earn করার points calculate করো।

    Args:
        spend_amount: Customer এর spend amount
        earn_rate:    Points per currency unit (e.g. 1 = 1 pt per 1 BDT)
        multiplier:   Tier/campaign multiplier

    Returns:
        Decimal points (rounded to 2 decimal places)
    """
    if spend_amount <= 0:
        return Decimal('0')
    points = Decimal(str(spend_amount)) * Decimal(str(earn_rate)) * Decimal(str(multiplier))
    return points.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_points_value(points: Decimal, point_value: Decimal) -> Decimal:
    """
    Points কে currency value তে convert করো।

    Args:
        points:      Number of points
        point_value: Value per point (e.g. 0.01 = 1 point = 0.01 BDT)

    Returns:
        Decimal currency amount
    """
    if points <= 0:
        return Decimal('0')
    value = Decimal(str(points)) * Decimal(str(point_value))
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def points_to_bdt(points, rate: Decimal = Decimal('0.01')) -> Decimal:
    """Convert points to BDT value।"""
    return (Decimal(str(points)) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def bdt_to_points(amount, rate: Decimal = Decimal('1')) -> Decimal:
    """Convert BDT amount to points (1 BDT = 1 point default)।"""
    return (Decimal(str(amount)) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─── Safe Conversion ───────────────────────────────────────────────────────────

def safe_decimal(value, default: Decimal = Decimal('0')) -> Decimal:
    """
    Safe Decimal conversion -- None বা invalid হলে default return করে।

    AUDIT FIX (v2): Unified signature। utils.py had (value, default) with
    `if value is None` guard। helpers.py had identical logic without the
    None guard। Combined: None guard + try/except।
    """
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


# ─── Tier Utilities ────────────────────────────────────────────────────────────

def get_tier_for_points(lifetime_earned: Decimal) -> str:
    """
    Lifetime earned points এর ভিত্তিতে tier name বের করো।
    TIER_THRESHOLDS অনুযায়ী highest qualifying tier।
    """
    from .constants import TIER_THRESHOLDS, TIER_ORDER

    best_tier = 'bronze'
    for tier_name in TIER_ORDER:
        threshold = TIER_THRESHOLDS.get(tier_name, Decimal('0'))
        if lifetime_earned >= threshold:
            best_tier = tier_name
        else:
            break
    return best_tier


def get_tier_multiplier(tier_name: str) -> Decimal:
    """Tier name থেকে earn multiplier বের করো।"""
    from .constants import TIER_MULTIPLIERS
    return TIER_MULTIPLIERS.get(tier_name, Decimal('1.0'))


def get_next_tier(current_tier_name: str):
    """
    Current tier এর পরের tier name।
    Diamond এ থাকলে None return করে।
    """
    from .constants import TIER_ORDER
    try:
        idx = TIER_ORDER.index(current_tier_name)
        if idx + 1 < len(TIER_ORDER):
            return TIER_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def get_points_needed_for_next_tier(lifetime_earned: Decimal, current_tier_name: str):
    """
    Next tier এ পৌঁছানোর জন্য আর কত points লাগবে।
    Already at top tier হলে None return করে।
    """
    from .constants import TIER_THRESHOLDS

    next_tier = get_next_tier(current_tier_name)
    if not next_tier:
        return None
    next_threshold = TIER_THRESHOLDS.get(next_tier, Decimal('0'))
    needed = next_threshold - Decimal(str(lifetime_earned))
    return max(needed, Decimal('0'))


def get_tier_progress_percent(lifetime_earned: Decimal, current_tier_name: str) -> float:
    """
    Current tier এর মধ্যে progress percentage।
    100% মানে ready for upgrade।
    """
    from .constants import TIER_THRESHOLDS

    next_tier = get_next_tier(current_tier_name)
    if not next_tier:
        return 100.0

    current_threshold = TIER_THRESHOLDS.get(current_tier_name, Decimal('0'))
    next_threshold    = TIER_THRESHOLDS.get(next_tier, Decimal('0'))
    tier_range        = next_threshold - current_threshold

    if tier_range <= 0:
        return 100.0

    progress = lifetime_earned - current_threshold
    pct = float(progress / tier_range * 100)
    return round(min(max(pct, 0.0), 100.0), 1)


def get_tier_color(tier_name: str) -> str:
    """Get display color for tier badge।"""
    colors = {
        'bronze':   '#CD7F32',
        'silver':   '#C0C0C0',
        'gold':     '#FFD700',
        'platinum': '#E5E4E2',
        'diamond':  '#B9F2FF',
    }
    return colors.get(tier_name.lower(), '#3b82f6')


def get_tier_icon(tier_name: str) -> str:
    """Get icon for tier."""
    icons = {
        'bronze':   '🥉',
        'silver':   '🥈',
        'gold':     '🥇',
        'platinum': '💎',
        'diamond':  '💠',
    }
    return icons.get(tier_name.lower(), '⭐')


# ─── Date & Expiry ─────────────────────────────────────────────────────────────

def get_expiry_date(days: int = 365):
    """N দিন পরের expiry datetime।"""
    return timezone.now() + timedelta(days=days)


def days_until(dt) -> int:
    """
    দেওয়া datetime পর্যন্ত কত দিন বাকি।

    AUDIT FIX (v2): Unified signature। helpers.py used .date() comparison;
    utils.py used direct timedelta। Combined: use .date() when available
    so the function works with both date and datetime objects।
    """
    if dt is None:
        return 0
    now = timezone.now()
    if hasattr(dt, 'date'):
        delta = dt.date() - now.date()
    else:
        delta = dt - now.date()
    return max(delta.days, 0)


def days_since(dt) -> int:
    """Days since a datetime।"""
    if dt is None:
        return 9999
    now = timezone.now()
    if hasattr(dt, 'date'):
        delta = now.date() - dt.date()
    else:
        delta = now.date() - dt
    return delta.days


def is_expired(dt) -> bool:
    """দেওয়া datetime expired কিনা।"""
    if dt is None:
        return False
    return timezone.now() >= dt


def is_birthday_today(date_of_birth) -> bool:
    """Check if today is the customer's birthday।"""
    if not date_of_birth:
        return False
    today = timezone.now().date()
    return date_of_birth.month == today.month and date_of_birth.day == today.day


def get_quarter(dt=None) -> int:
    """Get quarter number (1-4) for a date।"""
    if dt is None:
        dt = timezone.now()
    return (dt.month - 1) // 3 + 1


# ─── Code Generation ───────────────────────────────────────────────────────────

def generate_voucher_code(length: int = 12, prefix: str = '') -> str:
    """
    Random uppercase alphanumeric voucher code।

    AUDIT FIX (v2): Unified signature।
    utils.py had generate_voucher_code(length=12) with no prefix।
    helpers.py had generate_voucher_code(prefix='V', length=10) with prefix।
    These produced incompatible formats in the same DB column।

    Unified: generate_voucher_code(length=12, prefix='')
      -- prefix=''  (default) gives bare code: 'ABCD12345678'
      -- prefix='V' gives prefixed code: 'VABCD1234567890'
      -- VoucherService.generate_voucher() uses prefix='' (no change needed)
      -- helpers.generate_voucher_code() re-exports with prefix='V' default
    Uses secrets.choice for cryptographic randomness (helpers.py behaviour)。
    """
    alphabet = string.ascii_uppercase + string.digits
    body     = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f'{prefix}{body}'


def generate_gift_card_code(length: int = 16) -> str:
    """
    Random gift card code (4 groups of 4 chars)।
    """
    chars  = string.ascii_uppercase + string.digits
    groups = [''.join(random.choices(chars, k=4)) for _ in range(4)]
    return '-'.join(groups)


def generate_loyalty_number() -> str:
    """
    Customer loyalty number generate করো।
    Format: LYL-XXXXXXXXXX (10 digit random)
    """
    digits = ''.join(random.choices(string.digits, k=10))
    return f'LYL-{digits}'


def generate_customer_code(prefix: str = 'C', length: int = 8) -> str:
    """
    Generate a unique customer code like C0001234।
    Uses uppercase letters and digits, excluding confusing chars (0,O,I,1)।
    """
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    suffix   = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f'{prefix}{suffix}'


def generate_referral_code(length: int = 8) -> str:
    """Generate a unique referral code।"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_transaction_ref(prefix: str = 'TXN') -> str:
    """Generate a unique transaction reference like TXN-20250101-ABC123।"""
    today  = timezone.now().strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:8].upper()
    return f'{prefix}-{today}-{suffix}'


def generate_secure_token(length: int = 32) -> str:
    """
    Cryptographically secure random token।
    API keys, webhook secrets এর জন্য।

    AUDIT FIX (v2): utils.py used secrets.token_hex(length//2)।
    helpers.py used secrets.token_urlsafe(length)।
    Unified: token_urlsafe (URL-safe) is the safer default for API keys।
    token_hex is retained as generate_secure_token_hex() for callers that
    need hex specifically।
    """
    return secrets.token_urlsafe(length)


def generate_secure_token_hex(length: int = 32) -> str:
    """
    Cryptographically secure hex token (use when hex format is required)।
    """
    return secrets.token_hex(length // 2)


def generate_reference_id() -> str:
    """Transaction reference ID generate করো।"""
    return 'REF-' + secrets.token_hex(8).upper()


def generate_otp(length: int = 6) -> str:
    """Generate numeric OTP।"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


# ─── Formatting ────────────────────────────────────────────────────────────────

def format_points(points: Decimal, decimals: int = 0, suffix: str = '') -> str:
    """
    Points সুন্দরভাবে format করো।

    AUDIT FIX (v2): Unified signature।
    utils.py had format_points(points, decimals=0) → '1,250'
    helpers.py had format_points(points, suffix=' pts') → '1,250 pts'
    Unified: format_points(points, decimals=0, suffix='')
      -- suffix='' (default) reproduces utils.py behaviour
      -- suffix=' pts'        reproduces helpers.py behaviour
    """
    try:
        if decimals == 0:
            formatted = f'{int(round(float(points))):,}'
        else:
            fmt       = f'{{:,.{decimals}f}}'
            formatted = fmt.format(float(points))
        return f'{formatted}{suffix}'
    except Exception:
        return f'{points}{suffix}'


def format_currency(
    amount: Decimal,
    symbol: str = '৳',
    decimals: int = 2,
    currency: str = 'BDT',
) -> str:
    """
    Currency amount সুন্দরভাবে format করো।

    AUDIT FIX (v2): Unified signature।
    utils.py had format_currency(amount, symbol='৳', decimals=2)
    helpers.py had format_currency(amount, currency='BDT', symbol='৳')
    Unified: all 4 params available, symbol and decimals are primary।
    """
    try:
        fmt = f'{{:,.{decimals}f}}'
        return f'{symbol}{fmt.format(float(amount))}'
    except Exception:
        return f'{symbol}{amount}'


# ─── Phone / Email Helpers ─────────────────────────────────────────────────────

def normalize_bd_phone(phone: str) -> str:
    """
    Normalize Bangladesh phone number to 01XXXXXXXXX format।
    Handles: 01X, +8801X, 8801X formats।
    Returns empty string if invalid।
    """
    if not phone:
        return ''
    clean = re.sub(r'[\s\-\(\)\+]', '', phone)
    if clean.startswith('880'):
        clean = '0' + clean[3:]
    elif clean.startswith('00880'):
        clean = '0' + clean[5:]
    if re.match(r'^01[3-9]\d{8}$', clean):
        return clean
    return ''


def is_valid_bd_phone(phone: str) -> bool:
    """Check if a Bangladesh phone number is valid।"""
    return bool(normalize_bd_phone(phone))


def mask_phone(phone: str) -> str:
    """Mask phone for display: 01700****00।"""
    if not phone or len(phone) < 5:
        return '***'
    return phone[:5] + '****' + phone[-2:]


def mask_email(email: str) -> str:
    """Mask email for display: j***@example.com।"""
    if not email or '@' not in email:
        return '***'
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f'{"*" * len(local)}@{domain}'
    return f'{local[0]}{"*" * (len(local) - 2)}{local[-1]}@{domain}'


def is_valid_email(email: str) -> bool:
    """Basic email validation।"""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email or ''))


def is_valid_phone(phone: str) -> bool:
    """Basic phone number validation (digits + optional +, -, space)।"""
    return bool(re.match(r'^\+?[\d\s\-]{7,20}$', phone or ''))


def normalize_code(code: str) -> str:
    """Customer code normalize করো -- uppercase, strip whitespace।"""
    return code.strip().upper() if code else ''


# ─── Hashing / Security ────────────────────────────────────────────────────────

def make_hmac_signature(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature।"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature।"""
    expected = make_hmac_signature(payload, secret)
    return hmac.compare_digest(expected.lower(), signature.lower())


def hash_sensitive(value: str) -> str:
    """One-way hash for sensitive data (e.g., API keys in logs)।"""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


# ─── Pagination Helpers ────────────────────────────────────────────────────────

def paginate_queryset(queryset, page: int = 1, page_size: int = 20) -> dict:
    """Simple queryset pagination helper।"""
    page      = max(1, page)
    page_size = min(max(1, page_size), 100)
    total     = queryset.count()
    start     = (page - 1) * page_size
    end       = start + page_size
    items     = queryset[start:end]
    total_pages = (total + page_size - 1) // page_size

    return {
        'items':       items,
        'page':        page,
        'page_size':   page_size,
        'total':       total,
        'total_pages': total_pages,
        'has_next':    page < total_pages,
        'has_prev':    page > 1,
    }


# ─── Misc ──────────────────────────────────────────────────────────────────────

def chunk_list(lst: list, chunk_size: int) -> list:
    """
    List কে ছোট chunks এ ভাগ করো।

    AUDIT FIX (v2): Identical in both files -- one copy retained here।
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def build_cache_key(*parts) -> str:
    """Cache key তৈরি করো।"""
    return ':'.join(str(p) for p in parts if p is not None)


def get_client_ip(request) -> str:
    """
    Request থেকে client IP বের করো।

    AUDIT FIX (v2): helpers.py included Cloudflare CF-Connecting-IP header;
    utils.py did not।  Combined version checks all three sources in order:
    X-Forwarded-For -> CF-Connecting-IP -> REMOTE_ADDR।
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def truncate(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to max length with suffix।"""
    if not text:
        return ''
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """Flatten nested dict: {'a': {'b': 1}} -> {'a.b': 1}।"""
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}{sep}{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_device_type(user_agent: str) -> str:
    """Detect device type from User-Agent string।"""
    ua = user_agent.lower()
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        return 'mobile'
    if 'tablet' in ua or 'ipad' in ua:
        return 'tablet'
    return 'desktop'


def build_absolute_url(request, path: str) -> str:
    """Build absolute URL from request + path।"""
    scheme = request.scheme
    host   = request.get_host()
    return f'{scheme}://{host}{path}'
