# api/wallet/helpers.py
"""
General-purpose helper functions for the wallet app.
These are used across views, services, tasks, and serializers.
"""
import hashlib
import hmac
import logging
import re
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional, Dict, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("wallet.helpers")


# ══════════════════════════════════════════════════
# DECIMAL / AMOUNT HELPERS
# ══════════════════════════════════════════════════

def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert any value to Decimal. Never raises."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return default


def round_bdt(amount: Decimal, places: int = 2) -> Decimal:
    """Round BDT amount to given decimal places."""
    quantize = Decimal("0." + "0" * places)
    return safe_decimal(amount).quantize(quantize, rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal, currency: str = "BDT", places: int = 2) -> str:
    """Format amount as human-readable string. e.g. '1,500.00 BDT'"""
    try:
        return f"{float(amount):,.{places}f} {currency}"
    except Exception:
        return f"0.00 {currency}"


def amount_to_paisa(amount: Decimal) -> int:
    """Convert BDT Decimal to paisa integer (for atomic Redis ops)."""
    return int(safe_decimal(amount) * 100)


def paisa_to_amount(paisa: int) -> Decimal:
    """Convert paisa integer back to BDT Decimal."""
    return Decimal(str(paisa)) / 100


def clamp_positive(value: Decimal) -> Decimal:
    """Ensure value is >= 0."""
    return max(safe_decimal(value), Decimal("0"))


def calculate_percentage(amount: Decimal, percent: Decimal) -> Decimal:
    """Calculate percent of amount. e.g. 10% of 500 = 50."""
    return (safe_decimal(amount) * safe_decimal(percent) / 100).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )


def apply_fee(amount: Decimal, fee_percent: Decimal, flat_fee: Decimal = Decimal("0"),
              min_fee: Decimal = Decimal("0"), max_fee: Optional[Decimal] = None) -> Decimal:
    """
    Calculate withdrawal fee.
    fee = max(min_fee, min(percent_fee + flat_fee, max_fee))
    """
    percent_fee = calculate_percentage(amount, fee_percent)
    fee = percent_fee + safe_decimal(flat_fee)
    fee = max(fee, safe_decimal(min_fee))
    if max_fee is not None:
        fee = min(fee, safe_decimal(max_fee))
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ══════════════════════════════════════════════════
# STRING / ID HELPERS
# ══════════════════════════════════════════════════

def generate_uuid() -> str:
    """Generate a UUID4 hex string."""
    return uuid.uuid4().hex


def generate_idempotency_key(prefix: str = "wal") -> str:
    """Generate a unique idempotency key."""
    return f"{prefix}_{uuid.uuid4().hex}"


def mask_account(number: str, visible: int = 4) -> str:
    """Mask account/card number. e.g. '01712345678' → '****5678'"""
    s = str(number or "")
    if len(s) <= visible:
        return s
    return "*" * (len(s) - visible) + s[-visible:]


def mask_email(email: str) -> str:
    """Mask email address. e.g. 'john@example.com' → 'jo**@example.com'"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return email
    return local[:2] + "*" * (len(local) - 2) + "@" + domain


def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate string to max_length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def slugify_reference(reference: str) -> str:
    """Make a reference ID safe for storage (alphanumeric + dash only)."""
    return re.sub(r"[^a-zA-Z0-9\-_]", "", str(reference))[:100]


# ══════════════════════════════════════════════════
# IP / NETWORK HELPERS
# ══════════════════════════════════════════════════

def extract_client_ip(request) -> str:
    """Extract real client IP from Django request, handling proxies."""
    for header in [
        "HTTP_X_FORWARDED_FOR",
        "HTTP_CF_CONNECTING_IP",
        "HTTP_X_REAL_IP",
        "HTTP_CLIENT_IP",
        "REMOTE_ADDR",
    ]:
        value = request.META.get(header, "")
        if value:
            ip = value.split(",")[0].strip()
            if ip and ip not in ("", "unknown", "null", "None"):
                return ip
    return "127.0.0.1"


def is_private_ip(ip: str) -> bool:
    """Check if IP is a private/loopback address."""
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback
    except ValueError:
        return False


def get_country_from_ip(ip: str) -> str:
    """Get country code from IP (requires geoip2 or similar)."""
    try:
        import geoip2.database
        from django.conf import settings
        db_path = getattr(settings, "GEOIP_PATH", "")
        if db_path:
            with geoip2.database.Reader(db_path) as reader:
                response = reader.country(ip)
                return response.country.iso_code or "BD"
    except Exception:
        pass
    return "BD"  # Default to Bangladesh


# ══════════════════════════════════════════════════
# HMAC / SIGNATURE HELPERS
# ══════════════════════════════════════════════════

def compute_hmac(payload: str, secret: str, algorithm: str = "sha256") -> str:
    """Compute HMAC signature for webhook/API signing."""
    import hashlib as _hashlib
    h = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        getattr(_hashlib, algorithm, _hashlib.sha256)
    )
    return h.hexdigest()


def verify_hmac(payload: str, signature: str, secret: str, algorithm: str = "sha256") -> bool:
    """Verify HMAC signature. Constant-time comparison."""
    expected = compute_hmac(payload, secret, algorithm)
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False


def generate_api_key(prefix: str = "wk") -> Tuple[str, str]:
    """
    Generate API key pair (key, hashed_key).
    Store only hashed_key in DB; return key to user once.
    """
    raw_key    = f"{prefix}_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key


# ══════════════════════════════════════════════════
# DATE / TIME HELPERS
# ══════════════════════════════════════════════════

def get_period_range(period: str) -> Tuple:
    """
    Return (start_datetime, end_datetime) for named periods.
    period: today, yesterday, this_week, this_month, last_30_days, this_year
    """
    from datetime import date, timedelta, datetime
    today = timezone.now().date()

    if period == "today":
        start, end = today, today
    elif period == "yesterday":
        start = today - timedelta(days=1)
        end   = start
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())
        end   = today
    elif period == "this_month":
        start = today.replace(day=1)
        end   = today
    elif period == "last_7_days":
        start = today - timedelta(days=7)
        end   = today
    elif period == "last_30_days":
        start = today - timedelta(days=30)
        end   = today
    elif period == "last_90_days":
        start = today - timedelta(days=90)
        end   = today
    elif period == "this_year":
        start = today.replace(month=1, day=1)
        end   = today
    else:
        start = today
        end   = today

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()), tz)
    end_dt   = timezone.make_aware(datetime.combine(end, datetime.max.time()), tz)
    return start_dt, end_dt


def time_ago(dt) -> str:
    """Return human-readable time difference. e.g. '2 hours ago'"""
    from django.utils.timesince import timesince
    return timesince(dt, timezone.now()) + " ago"


def is_same_day(dt1, dt2) -> bool:
    """Check if two datetimes are on the same calendar day."""
    return dt1.date() == dt2.date()


# ══════════════════════════════════════════════════
# CACHE HELPERS
# ══════════════════════════════════════════════════

def cache_get_or_set(key: str, factory_func, timeout: int = 60):
    """Get from cache or compute and store."""
    value = cache.get(key)
    if value is None:
        value = factory_func()
        cache.set(key, value, timeout)
    return value


def cache_invalidate_pattern(pattern: str) -> int:
    """Delete all cache keys matching pattern (Redis only)."""
    count = 0
    try:
        if hasattr(cache, "delete_pattern"):
            count = cache.delete_pattern(pattern)
    except Exception as e:
        logger.debug(f"cache_invalidate_pattern({pattern}): {e}")
    return count


def atomic_cache_increment(key: str, amount: int = 1, ttl: int = 86400) -> int:
    """Atomically increment a cache counter."""
    try:
        return cache.incr(key, amount)
    except Exception:
        cache.set(key, amount, ttl)
        return amount


# ══════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════

def is_valid_bd_mobile(number: str) -> bool:
    """Validate Bangladesh mobile number (01XXXXXXXXX format)."""
    cleaned = re.sub(r"[^\d]", "", str(number))
    if cleaned.startswith("880"):
        cleaned = "0" + cleaned[3:]
    return bool(re.match(r"^01[3-9]\d{8}$", cleaned))


def normalize_bd_mobile(number: str) -> str:
    """Normalize BD mobile to 01XXXXXXXXX format."""
    cleaned = re.sub(r"[^\d]", "", str(number))
    if cleaned.startswith("+880"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("880"):
        cleaned = "0" + cleaned[3:]
    return cleaned


def is_valid_crypto_address(address: str, network: str = "trc20") -> bool:
    """Validate crypto wallet address."""
    if "trc" in network.lower():
        return bool(address and address.startswith("T") and len(address) == 34)
    if "erc" in network.lower():
        return bool(address and address.startswith("0x") and len(address) == 42)
    return bool(address and len(address) > 10)


# ══════════════════════════════════════════════════
# RESPONSE HELPERS
# ══════════════════════════════════════════════════

def success_response(data=None, message: str = "", status_code: int = 200) -> dict:
    """Build standard success response dict."""
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if message:
        resp["message"] = message
    return resp


def error_response(error: str, code: str = None, status_code: int = 400) -> dict:
    """Build standard error response dict."""
    resp = {"success": False, "error": error}
    if code:
        resp["code"] = code
    return resp


def paginated_response(data, page: int, total: int, page_size: int) -> dict:
    """Build paginated response."""
    import math
    return {
        "success":      True,
        "count":        total,
        "page":         page,
        "page_size":    page_size,
        "total_pages":  math.ceil(total / page_size) if page_size > 0 else 0,
        "results":      data,
    }


# ══════════════════════════════════════════════════
# RETRY HELPER
# ══════════════════════════════════════════════════

def retry(func, max_retries: int = 3, delay: float = 1.0,
          exceptions=(Exception,), backoff: float = 2.0):
    """
    Retry a function with exponential backoff.
    Usage:
        result = retry(lambda: requests.post(url), max_retries=3)
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exc = e
            if attempt < max_retries - 1:
                wait = delay * (backoff ** attempt)
                logger.warning(f"Retry {attempt+1}/{max_retries} after {wait:.1f}s: {e}")
                time.sleep(wait)
    raise last_exc


# ══════════════════════════════════════════════════
# BATCH HELPER
# ══════════════════════════════════════════════════

def batch(iterable, size: int = 100):
    """Split iterable into chunks of given size."""
    lst = list(iterable)
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def bulk_create_safe(model_class, objects: list, batch_size: int = 500,
                     ignore_conflicts: bool = True) -> int:
    """
    Safe bulk_create with batching and conflict handling.
    Returns count of created objects.
    """
    total = 0
    for chunk in batch(objects, batch_size):
        try:
            created = model_class.objects.bulk_create(
                chunk, batch_size=batch_size, ignore_conflicts=ignore_conflicts
            )
            total += len(created)
        except Exception as e:
            logger.error(f"bulk_create_safe error: {e}")
    return total
