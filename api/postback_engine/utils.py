"""
utils.py
─────────
General utility functions for the Postback Engine.
Helpers used across multiple modules: formatting, parsing, geo, time, string.
"""
from __future__ import annotations
import hashlib
import ipaddress
import logging
import re
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── String / ID Utilities ──────────────────────────────────────────────────────

def generate_unique_id(prefix: str = "", length: int = 32) -> str:
    """Generate a cryptographically secure unique ID."""
    token = secrets.token_urlsafe(length)
    return f"{prefix}_{token}" if prefix else token


def slugify_network_key(name: str) -> str:
    """Convert a network name to a URL-safe network key."""
    slug = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    slug = re.sub(r'\s+', '_', slug.strip()).lower()
    return slug[:64]


def mask_secret(value: str, visible: int = 6) -> str:
    """Mask a secret key for safe display."""
    if not value or len(value) <= visible:
        return "***"
    return value[:visible] + "..." + value[-4:]


def truncate(value: str, max_length: int = 255) -> str:
    """Truncate a string to max_length."""
    if not value:
        return ""
    return value[:max_length] if len(value) > max_length else value


# ── Decimal / Payout Utilities ────────────────────────────────────────────────

def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert any value to Decimal."""
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return default


def format_usd(amount: Decimal) -> str:
    """Format a decimal as USD string."""
    return f"${float(amount):,.4f}"


def round_payout(amount: Decimal, places: int = 4) -> Decimal:
    """Round payout to specified decimal places."""
    from decimal import ROUND_HALF_UP
    quantize = Decimal("0." + "0" * places)
    return amount.quantize(quantize, rounding=ROUND_HALF_UP)


# ── IP Utilities ──────────────────────────────────────────────────────────────

def is_valid_ip(ip: str) -> bool:
    """Check if a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except (ValueError, TypeError):
        return False


def is_private_ip(ip: str) -> bool:
    """Check if IP is in a private/loopback range."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback
    except (ValueError, TypeError):
        return False


def get_ip_from_request(request) -> str:
    """Extract the real client IP from a Django request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def anonymise_ip(ip: str) -> str:
    """Anonymise an IP (zero last octet) for GDPR-safe logging."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.version == 4:
            parts = ip.split(".")
            parts[-1] = "0"
            return ".".join(parts)
        else:
            # IPv6: zero last 80 bits
            network = ipaddress.ip_network(f"{ip}/48", strict=False)
            return str(network.network_address)
    except (ValueError, TypeError):
        return ip


# ── URL / Macro Utilities ─────────────────────────────────────────────────────

def expand_url_macros(url_template: str, context: Dict[str, Any]) -> str:
    """Replace {macro} placeholders in a URL template."""
    if not url_template:
        return url_template

    def replace(match: re.Match) -> str:
        key = match.group(1)
        val = context.get(key)
        return urllib.parse.quote(str(val), safe="") if val is not None else match.group(0)

    return re.sub(r'\{(\w+)\}', replace, url_template)


def build_query_string(params: dict) -> str:
    """Build a sorted URL query string from a dict."""
    sorted_params = sorted(params.items())
    return urllib.parse.urlencode(sorted_params)


def parse_query_string(query_string: str) -> dict:
    """Parse a URL query string into a dict."""
    return dict(urllib.parse.parse_qsl(query_string))


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid HTTP/HTTPS URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


# ── Time Utilities ─────────────────────────────────────────────────────────────

def now_timestamp() -> str:
    """Return current Unix timestamp as string."""
    return str(int(time.time()))


def seconds_to_human(seconds: int) -> str:
    """Convert seconds to human-readable string (e.g. '2h 30m')."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d {h}h"


def get_date_range(days: int):
    """Return (start_date, end_date) tuple for a rolling N-day window."""
    from django.utils import timezone
    end = timezone.now()
    start = end - timedelta(days=days)
    return start, end


# ── Hash Utilities ─────────────────────────────────────────────────────────────

def sha256_hex(value: str) -> str:
    """Return SHA-256 hex digest of a string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def md5_hex(value: str) -> str:
    """Return MD5 hex digest of a string."""
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def short_hash(value: str, length: int = 16) -> str:
    """Return a short hash prefix for use in cache keys."""
    return sha256_hex(value)[:length]


# ── Header Utilities ──────────────────────────────────────────────────────────

SENSITIVE_HEADERS = {
    "authorization", "x-api-key", "x-postback-signature",
    "cookie", "x-auth-token", "x-secret", "x-access-token",
}


def sanitise_headers(headers: dict) -> dict:
    """Remove sensitive headers for safe logging/storage."""
    return {
        k: "***REDACTED***" if k.lower() in SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }


def extract_device_type(user_agent: str) -> str:
    """Extract device type from User-Agent string."""
    ua = (user_agent or "").lower()
    if any(kw in ua for kw in ("iphone", "android", "mobile", "blackberry", "windows phone")):
        return "mobile"
    if any(kw in ua for kw in ("ipad", "tablet")):
        return "tablet"
    if any(kw in ua for kw in ("smart-tv", "smarttv", "appletv", "roku", "tv")):
        return "tv"
    return "desktop"


# ── Pagination Utilities ───────────────────────────────────────────────────────

def paginate_queryset(qs, page: int = 1, page_size: int = 50) -> Tuple[Any, dict]:
    """Simple queryset pagination. Returns (page_qs, meta)."""
    from django.core.paginator import Paginator
    page_size = min(page_size, 500)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return page_obj.object_list, {
        "page": page,
        "page_size": page_size,
        "total": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_prev": page_obj.has_previous(),
    }
