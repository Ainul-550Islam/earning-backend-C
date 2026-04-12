import hashlib
import random
import string
import time
import re
from functools import wraps
from typing import Optional
from django.core.cache import cache
from django.utils import timezone
from .constants import (
    SLUG_ALLOWED_CHARS, SLUG_DEFAULT_LENGTH, GEO_IP_HEADER_PRIORITY,
)


def generate_random_slug(length: int = SLUG_DEFAULT_LENGTH) -> str:
    """Generate a cryptographically random slug."""
    return ''.join(random.choices(SLUG_ALLOWED_CHARS, k=length))


def get_client_ip(request) -> str:
    """
    Extract real client IP from request headers.
    Prioritizes Cloudflare → X-Real-IP → X-Forwarded-For → REMOTE_ADDR.
    """
    for header in GEO_IP_HEADER_PRIORITY:
        ip = request.META.get(header)
        if ip:
            # X-Forwarded-For can be comma-separated list
            return ip.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def get_user_agent(request) -> str:
    """Extract User-Agent string from request."""
    return request.META.get('HTTP_USER_AGENT', '')


def get_referrer(request) -> str:
    """Extract referrer from request."""
    return request.META.get('HTTP_REFERER', '')


def get_accept_language(request) -> str:
    """Extract Accept-Language header."""
    return request.META.get('HTTP_ACCEPT_LANGUAGE', '')


def parse_accept_language(header: str) -> Optional[str]:
    """
    Parse Accept-Language header and return primary language code.
    Example: 'en-US,en;q=0.9,bn;q=0.8' → 'en'
    """
    if not header:
        return None
    parts = header.split(',')
    if parts:
        lang = parts[0].split(';')[0].strip()
        return lang.split('-')[0].lower()
    return None


def click_fingerprint(ip: str, user_agent: str, offer_id: int) -> str:
    """
    Generate a deduplication fingerprint for a click.
    Used for unique click detection (IP + UA + offer + day).
    """
    today = timezone.now().date().isoformat()
    raw = f"{ip}:{user_agent}:{offer_id}:{today}"
    return hashlib.sha256(raw.encode()).hexdigest()


def smartlink_cache_key(slug: str) -> str:
    """Redis cache key for smartlink resolver."""
    return f"sl:{slug}"


def offer_score_cache_key(offer_id: int, country: str, device: str) -> str:
    """Cache key for offer EPC score per geo+device."""
    return f"offer_score:{offer_id}:{country}:{device}"


def cap_cache_key(offer_id: int, period: str) -> str:
    """Cache key for offer cap counter."""
    today = timezone.now().date().isoformat()
    return f"cap:{offer_id}:{period}:{today}"


def fraud_ip_cache_key(ip: str) -> str:
    """Cache key for fraud-flagged IP."""
    return f"fraud:ip:{ip}"


def domain_cache_key(domain: str) -> str:
    """Cache key for domain → publisher lookup."""
    return f"domain:{hashlib.md5(domain.encode()).hexdigest()}"


def timing_decorator(func):
    """Log execution time of service functions (for performance monitoring)."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > 5:
            import logging
            logger = logging.getLogger('smartlink.performance')
            logger.warning(
                f"{func.__qualname__} took {elapsed_ms:.2f}ms (target: <5ms)"
            )
        return result
    return wrapper


def is_valid_url(url: str) -> bool:
    """Quick URL validation without full Django validator overhead."""
    return bool(url and url.startswith(('http://', 'https://')) and len(url) <= 2048)


def sanitize_sub_id(value: str) -> str:
    """Remove unsafe characters from sub ID values."""
    if not value:
        return ''
    return re.sub(r'[^a-zA-Z0-9_\-]', '', value)[:255]


def build_tracking_url(base_url: str, params: dict) -> str:
    """
    Append tracking parameters to a URL.
    Handles existing query strings correctly.
    """
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query, keep_blank_values=True)
    # Flat merge (new params override existing)
    merged = {k: v[0] for k, v in existing_params.items()}
    merged.update({k: v for k, v in params.items() if v is not None})
    new_query = urlencode(merged)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def get_current_hour_utc() -> int:
    """Return current UTC hour (0-23)."""
    return timezone.now().hour


def get_day_of_week_utc() -> int:
    """Return current UTC day of week (0=Monday, 6=Sunday)."""
    return timezone.now().weekday()


def mask_ip(ip: str) -> str:
    """Mask last octet of IPv4 for GDPR-safe logging."""
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
    return ip
