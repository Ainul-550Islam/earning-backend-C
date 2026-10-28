"""
api/tasks/helpers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure utility functions shared across all task modules.
No Django models imported at module level — only inside functions.
All functions are pure / side-effect free unless explicitly noted.
"""

import hashlib
import hmac
import json
import logging
import math
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STRING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def generate_transaction_id(prefix: str = 'txn') -> str:
    """Generate a unique transaction ID: txn_<timestamp>_<uuid8>."""
    ts  = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts}_{uid}"


def generate_click_id() -> str:
    """Generate a unique 32-character click tracking ID."""
    return hashlib.sha256(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()[:32]


def generate_session_id() -> str:
    """Generate a secure session ID for content lockers / quizzes."""
    return secrets.token_urlsafe(32)


def generate_api_key(prefix: str = 'pk') -> Tuple[str, str]:
    """
    Generate an API key pair.
    Returns: (raw_key, hashed_key)
    raw_key is shown once; hashed_key is stored in DB.
    """
    raw_key    = f"{prefix}_{secrets.token_urlsafe(48)}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key


def mask_sensitive(value: str, visible_chars: int = 4, mask_char: str = '*') -> str:
    """
    Mask a sensitive string showing only last `visible_chars` characters.
    mask_sensitive('sk_live_abc123xyz', 4) → '**************xyz'
    """
    if not value or len(value) <= visible_chars:
        return mask_char * max(len(value), 4)
    return mask_char * (len(value) - visible_chars) + value[-visible_chars:]


def mask_email(email: str) -> str:
    """
    Mask an email address for display.
    mask_email('john.doe@example.com') → 'jo**@example.com'
    """
    if '@' not in email:
        return mask_sensitive(email)
    local, domain = email.split('@', 1)
    masked_local  = local[:2] + '*' * max(len(local) - 2, 2)
    return f"{masked_local}@{domain}"


def truncate(text: str, max_length: int = 100, suffix: str = '…') -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def slugify_task_name(name: str) -> str:
    """Convert a task name to a safe Celery task name format."""
    return re.sub(r'[^a-z0-9_.]', '_', name.lower()).strip('_')


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


# ══════════════════════════════════════════════════════════════════════════════
# DECIMAL / MONEY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def to_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """Safely convert any value to Decimal."""
    try:
        return Decimal(str(value)).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
    except Exception:
        return default


def money_str(amount: Union[Decimal, float, str, int],
              currency: str = 'USD',
              decimals: int = 2) -> str:
    """Format a monetary amount as a human-readable string."""
    try:
        d = Decimal(str(amount))
        fmt = f"{{:,.{decimals}f}}"
        return f"{currency} {fmt.format(d)}"
    except Exception:
        return f"{currency} 0.00"


def revenue_split(gross: Decimal, publisher_rate: Decimal = Decimal('0.70')) -> Dict[str, Decimal]:
    """
    Split gross revenue between publisher and platform.
    Returns: {'publisher': ..., 'platform': ..., 'gross': ...}
    """
    publisher = (gross * publisher_rate).quantize(Decimal('0.00000001'), ROUND_HALF_UP)
    platform  = gross - publisher
    return {
        'gross':     gross,
        'publisher': publisher,
        'platform':  platform,
        'rate':      publisher_rate,
    }


def apply_platform_fee(amount: Decimal, fee_rate: Decimal = Decimal('0.30')) -> Dict[str, Decimal]:
    """Calculate net amount after platform fee."""
    fee = (amount * fee_rate).quantize(Decimal('0.00000001'), ROUND_HALF_UP)
    return {'gross': amount, 'fee': fee, 'net': amount - fee}


def usd_to_tokens(usd_amount: Decimal, rate_per_dollar: int = 1000) -> int:
    """Convert USD amount to community points/virtual currency."""
    return int(usd_amount * rate_per_dollar)


def tokens_to_usd(tokens: int, rate_per_dollar: int = 1000) -> Decimal:
    """Convert community points back to USD."""
    return Decimal(str(tokens)) / Decimal(str(rate_per_dollar))


def calculate_percentage(part: Union[int, float, Decimal],
                          total: Union[int, float, Decimal],
                          decimals: int = 2) -> float:
    """Calculate percentage safely (avoids ZeroDivisionError)."""
    try:
        return round(float(part) / float(total) * 100, decimals)
    except (ZeroDivisionError, TypeError, ValueError):
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY / CRYPTO HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def compute_hmac_sha256(payload: Union[str, bytes], secret: str) -> str:
    """Compute HMAC-SHA256 signature for postback/webhook verification."""
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def verify_hmac_sha256(payload: Union[str, bytes], secret: str,
                        signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature (timing-safe comparison).
    Accepts signature with or without 'sha256=' prefix.
    """
    expected = f"sha256={compute_hmac_sha256(payload, secret)}"
    received = signature if signature.startswith('sha256=') else f"sha256={signature}"
    return hmac.compare_digest(expected.encode(), received.encode())


def hash_ip(ip_address: str) -> str:
    """Hash an IP address for anonymized storage."""
    return hashlib.md5(ip_address.encode()).hexdigest()


def hash_email(email: str) -> str:
    """Hash an email address for deduplication without storing PII."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP of given length."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


def safe_token_compare(token_a: str, token_b: str) -> bool:
    """Timing-safe string comparison for tokens."""
    return hmac.compare_digest(token_a.encode(), token_b.encode())


# ══════════════════════════════════════════════════════════════════════════════
# DATE / TIME HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return timezone.now().isoformat()


def now_unix() -> int:
    """Return current UTC time as Unix timestamp (seconds)."""
    return int(timezone.now().timestamp())


def parse_date_str(date_str: str, fmt: str = '%Y-%m-%d') -> Optional[datetime]:
    """Safely parse a date string, returning None on failure."""
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


def date_range(start: datetime, end: datetime) -> List[datetime]:
    """Generate a list of dates between start and end (inclusive)."""
    dates   = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def days_since(dt: datetime) -> int:
    """Return number of days since a datetime."""
    return (timezone.now() - dt).days


def hours_since(dt: datetime) -> float:
    """Return number of hours since a datetime."""
    return (timezone.now() - dt).total_seconds() / 3600


def seconds_until(dt: datetime) -> float:
    """Return seconds until a future datetime (negative if past)."""
    return (dt - timezone.now()).total_seconds()


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds/60:.1f}m"
    if seconds < 86400:
        return f"{seconds/3600:.1f}h"
    return f"{seconds/86400:.1f}d"


def get_period_bounds(period: str = 'daily', reference: datetime = None) -> Tuple[datetime, datetime]:
    """
    Get start and end datetimes for a named period.
    period: 'hourly' | 'daily' | 'weekly' | 'monthly'
    Returns: (period_start, period_end)
    """
    now = reference or timezone.now()

    if period == 'hourly':
        start = now.replace(minute=0, second=0, microsecond=0)
        end   = start + timedelta(hours=1)
    elif period == 'daily':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=1)
    elif period == 'weekly':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(weeks=1)
    elif period == 'monthly':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
    else:
        start = now - timedelta(hours=24)
        end   = now

    return start, end


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_valid_email(email: str) -> bool:
    """Check if an email address has a valid format."""
    return bool(re.match(
        r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$',
        email.strip()
    ))


def is_disposable_email(email: str) -> bool:
    """Check if email domain is a known disposable provider."""
    DISPOSABLE = {
        'mailinator.com', 'guerrillamail.com', 'tempmail.com',
        'throwam.com', 'yopmail.com', '10minutemail.com',
        'sharklasers.com', 'maildrop.cc', 'trashmail.com',
        'fakeinbox.com', 'spamgourmet.com', 'dispostable.com',
        'mailnull.com', 'spam4.me', 'grr.la', 'airmail.cc',
    }
    if '@' not in email:
        return False
    domain = email.split('@')[-1].lower()
    return domain in DISPOSABLE


def is_valid_url(url: str, require_https: bool = False) -> bool:
    """Check if a URL has a valid format."""
    pattern = r'^https?://' if not require_https else r'^https://'
    return bool(re.match(
        pattern + r'[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+$',
        url.strip()
    ))


def is_valid_evm_address(address: str) -> bool:
    """Validate Ethereum/EVM wallet address (0x + 40 hex chars)."""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def is_valid_trc20_address(address: str) -> bool:
    """Validate Tron TRC20 wallet address (T + 33 chars)."""
    return bool(re.match(r'^T[a-zA-Z0-9]{33}$', address))


def is_valid_bitcoin_address(address: str) -> bool:
    """Validate Bitcoin address (P2PKH, P2SH, Bech32)."""
    return bool(re.match(r'^(1|3|bc1)[a-zA-Z0-9]{25,62}$', address))


def validate_crypto_address(address: str, crypto_type: str) -> Tuple[bool, str]:
    """
    Validate a crypto wallet address.
    Returns: (is_valid, error_message)
    """
    address = address.strip()
    validators = {
        'usdt_trc20': (is_valid_trc20_address,  'TRC20: must start with T, 34 chars total'),
        'usdt_erc20': (is_valid_evm_address,     'ERC20: must be 0x + 40 hex chars'),
        'ethereum':   (is_valid_evm_address,     'ETH: must be 0x + 40 hex chars'),
        'bitcoin':    (is_valid_bitcoin_address, 'BTC: invalid format'),
        'bnb':        (is_valid_evm_address,     'BNB: must be 0x + 40 hex chars'),
        'polygon':    (is_valid_evm_address,     'MATIC: must be 0x + 40 hex chars'),
    }
    validator_fn, error_msg = validators.get(crypto_type.lower(), (lambda x: len(x) >= 20, 'Unknown crypto type'))
    is_valid = validator_fn(address)
    return is_valid, ('' if is_valid else error_msg)


# ══════════════════════════════════════════════════════════════════════════════
# GEO / TRAFFIC HELPERS
# ══════════════════════════════════════════════════════════════════════════════

TIER_1_COUNTRIES = frozenset({
    'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'NL', 'SE', 'NO', 'DK',
    'FI', 'CH', 'AT', 'BE', 'IE', 'NZ', 'SG', 'JP', 'KR', 'HK',
    'AE', 'IL', 'IT', 'ES', 'PT', 'LU', 'IS', 'MT', 'CY',
})

TIER_2_COUNTRIES = frozenset({
    'BR', 'MX', 'AR', 'CL', 'CO', 'PE', 'VE', 'EC', 'BO',
    'PL', 'CZ', 'SK', 'HU', 'RO', 'BG', 'HR', 'SI', 'EE', 'LV', 'LT',
    'ZA', 'NG', 'KE', 'GH', 'TZ', 'EG', 'MA', 'DZ', 'TN',
    'TH', 'MY', 'PH', 'ID', 'VN', 'IN', 'PK', 'BD', 'LK',
    'TR', 'SA', 'QA', 'KW', 'OM', 'BH', 'JO',
})


def get_traffic_tier(country_code: str) -> str:
    """Return traffic tier for a country code."""
    if not country_code:
        return 'tier_3'
    code = country_code.upper()
    if code in TIER_1_COUNTRIES:
        return 'tier_1'
    if code in TIER_2_COUNTRIES:
        return 'tier_2'
    return 'tier_3'


def get_default_ppc_rate(country: str = 'US', device: str = 'desktop') -> Decimal:
    """Get default PPC rate for country+device combination."""
    rates = {
        ('US', 'desktop'): Decimal('0.05'),
        ('US', 'mobile'):  Decimal('0.03'),
        ('GB', 'desktop'): Decimal('0.04'),
        ('GB', 'mobile'):  Decimal('0.025'),
        ('CA', 'desktop'): Decimal('0.04'),
        ('AU', 'desktop'): Decimal('0.035'),
        ('DE', 'desktop'): Decimal('0.03'),
        ('FR', 'desktop'): Decimal('0.025'),
    }
    return rates.get((country.upper(), device.lower()), Decimal('0.01'))


def extract_country_from_ip(ip_address: str) -> str:
    """
    Extract country code from IP address using geoip library.
    Returns 'US' as fallback if lookup fails.
    """
    try:
        import geoip2.database
        from django.conf import settings
        db_path = getattr(settings, 'GEOIP_DB_PATH', '/usr/share/GeoIP/GeoLite2-Country.mmdb')
        with geoip2.database.Reader(db_path) as reader:
            response = reader.country(ip_address)
            return response.country.iso_code or 'US'
    except Exception:
        return 'US'


# ══════════════════════════════════════════════════════════════════════════════
# TASK SYSTEM HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def build_dedup_key(prefix: str, *parts: Any, ttl: int = 86400) -> str:
    """Build a deduplication cache key from parts."""
    key_data = ':'.join(str(p) for p in parts)
    key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
    return f"{prefix}_{key_hash}"


def build_task_result(status: str = 'success', **kwargs) -> Dict[str, Any]:
    """Build a standard task result dictionary."""
    return {
        'status':    status,
        'timestamp': now_iso(),
        **kwargs,
    }


def success_result(**kwargs) -> Dict[str, Any]:
    return build_task_result('success', **kwargs)


def error_result(message: str = '', code: str = 'error', **kwargs) -> Dict[str, Any]:
    return build_task_result('error', message=message, error_code=code, **kwargs)


def skipped_result(reason: str = '', **kwargs) -> Dict[str, Any]:
    return build_task_result('skipped', reason=reason, **kwargs)


def duplicate_result(**kwargs) -> Dict[str, Any]:
    return build_task_result('duplicate', **kwargs)


def fraud_result(score: int = 0, reason: str = '', **kwargs) -> Dict[str, Any]:
    return build_task_result('fraud_detected', fraud_score=score, reason=reason, **kwargs)


def chunk_list(lst: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of given size."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def safe_json(obj: Any) -> str:
    """Serialize object to JSON, handling Decimal and datetime."""
    def default(o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=default)


def parse_json_safe(text: str, default: Any = None) -> Any:
    """Parse JSON safely, returning default on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def compute_fraud_score_from_signals(signals: Dict[str, Any]) -> int:
    """
    Compute a fraud risk score (0-100) from a dict of signals.
    signals keys: velocity, ip_diversity, account_age_hours,
                  reward_anomaly, new_account, ip_blocked
    """
    score = 0

    if signals.get('ip_blocked'):
        return 100   # Hard block

    velocity = signals.get('velocity', 0)
    if velocity > 100:
        score += min(int((velocity - 100) / 10) * 3, 30)
    elif velocity > 50:
        score += 15

    if signals.get('ip_diversity') == 1 and velocity > 20:
        score += 20   # Single IP, many completions

    age_hours = signals.get('account_age_hours', 999)
    if age_hours < 24:
        score += 20
    elif age_hours < 72:
        score += 10

    if signals.get('reward_anomaly'):
        score += 25

    if signals.get('new_account') and velocity > 10:
        score += 10

    return min(score, 100)


def get_retry_countdown(attempt: int, base_delay: int = 60,
                        multiplier: float = 2.0, max_delay: int = 3600) -> int:
    """Calculate exponential backoff countdown for Celery retries."""
    delay = base_delay * (multiplier ** (attempt - 1))
    return min(int(delay), max_delay)


def is_business_hours(dt: datetime = None, tz_offset_hours: int = 0) -> bool:
    """Check if a datetime falls within business hours (9am-6pm Mon-Fri)."""
    now = (dt or timezone.now()).replace(tzinfo=None)
    now = now + timedelta(hours=tz_offset_hours)
    if now.weekday() >= 5:   # Saturday/Sunday
        return False
    return 9 <= now.hour < 18


def compute_p_value_z_test(conv_a: int, n_a: int, conv_b: int, n_b: int) -> Tuple[float, float, bool]:
    """
    Two-proportion z-test for A/B testing.
    Returns: (z_score, p_value, is_significant_at_95pct)
    """
    if n_a == 0 or n_b == 0:
        return 0.0, 1.0, False
    p_a    = conv_a / n_a
    p_b    = conv_b / n_b
    p_pool = (conv_a + conv_b) / (n_a + n_b)
    se     = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return 0.0, 1.0, False
    z = (p_a - p_b) / se
    p = 2 * (1 - _norm_cdf(abs(z)))
    return round(z, 4), round(p, 4), p < 0.05


def _norm_cdf(x: float) -> float:
    """Normal CDF approximation using erf."""
    import math
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


# ══════════════════════════════════════════════════════════════════════════════
# CACHE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def cache_set_safe(key: str, value: Any, ttl: int = 3600) -> bool:
    """Set a cache key safely, ignoring errors."""
    try:
        from django.core.cache import cache
        cache.set(key, value, timeout=ttl)
        return True
    except Exception as e:
        logger.debug(f"[CACHE SET] {key}: {e}")
        return False


def cache_get_safe(key: str, default: Any = None) -> Any:
    """Get a cache key safely, returning default on errors."""
    try:
        from django.core.cache import cache
        return cache.get(key, default)
    except Exception as e:
        logger.debug(f"[CACHE GET] {key}: {e}")
        return default


def cache_delete_safe(*keys: str) -> int:
    """Delete multiple cache keys safely. Returns count deleted."""
    deleted = 0
    try:
        from django.core.cache import cache
        for key in keys:
            cache.delete(key)
            deleted += 1
    except Exception as e:
        logger.debug(f"[CACHE DELETE]: {e}")
    return deleted


def cache_incr_safe(key: str, amount: int = 1, ttl: int = 3600) -> int:
    """Increment a cache counter safely."""
    try:
        from django.core.cache import cache
        current = cache.get(key, 0)
        new_val = current + amount
        cache.set(key, new_val, timeout=ttl)
        return new_val
    except Exception:
        return 0


def bulk_cache_set(data: Dict[str, Any], ttl: int = 3600) -> int:
    """Set multiple cache keys at once. Returns count set."""
    count = 0
    for key, value in data.items():
        if cache_set_safe(key, value, ttl):
            count += 1
    return count


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # String
    'generate_transaction_id', 'generate_click_id', 'generate_session_id',
    'generate_api_key', 'mask_sensitive', 'mask_email', 'truncate',
    'slugify_task_name', 'camel_to_snake', 'snake_to_camel',
    # Money
    'to_decimal', 'money_str', 'revenue_split', 'apply_platform_fee',
    'usd_to_tokens', 'tokens_to_usd', 'calculate_percentage',
    # Security
    'compute_hmac_sha256', 'verify_hmac_sha256', 'hash_ip', 'hash_email',
    'generate_otp', 'safe_token_compare',
    # Date/Time
    'now_iso', 'now_unix', 'parse_date_str', 'date_range',
    'days_since', 'hours_since', 'seconds_until', 'format_duration',
    'get_period_bounds',
    # Validation
    'is_valid_email', 'is_disposable_email', 'is_valid_url',
    'is_valid_evm_address', 'is_valid_trc20_address', 'is_valid_bitcoin_address',
    'validate_crypto_address',
    # Geo
    'TIER_1_COUNTRIES', 'TIER_2_COUNTRIES', 'get_traffic_tier',
    'get_default_ppc_rate', 'extract_country_from_ip',
    # Task system
    'build_dedup_key', 'build_task_result', 'success_result', 'error_result',
    'skipped_result', 'duplicate_result', 'fraud_result',
    'chunk_list', 'safe_json', 'parse_json_safe',
    'compute_fraud_score_from_signals', 'get_retry_countdown',
    'is_business_hours', 'compute_p_value_z_test',
    # Cache
    'cache_set_safe', 'cache_get_safe', 'cache_delete_safe',
    'cache_incr_safe', 'bulk_cache_set',
]
