"""
api/monetization_tools/utils.py
=================================
Utility helpers used across the monetization_tools app.
"""

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Decimal / Currency helpers
# ---------------------------------------------------------------------------

def round_currency(value: Decimal, places: int = 2) -> Decimal:
    """Round a Decimal to the given number of decimal places."""
    quantize_str = Decimal(10) ** -places
    return value.quantize(quantize_str, rounding=ROUND_HALF_UP)


def usd_to_coins(usd_amount: Decimal, rate: Decimal = Decimal('100')) -> Decimal:
    """
    Convert USD payout to user coins.
    Default rate: 1 USD = 100 coins.
    """
    return round_currency(usd_amount * rate, places=2)


def coins_to_usd(coins: Decimal, rate: Decimal = Decimal('100')) -> Decimal:
    """Convert coins back to approximate USD value."""
    return round_currency(coins / rate, places=4)


def calculate_ecpm(revenue: Decimal, impressions: int) -> Decimal:
    """Calculate effective CPM: (revenue / impressions) * 1000"""
    if not impressions:
        return Decimal('0.0000')
    return round_currency((revenue / impressions) * 1000, places=4)


def calculate_ctr(clicks: int, impressions: int) -> Decimal:
    """Click-through rate as percentage."""
    if not impressions:
        return Decimal('0.00')
    return round_currency(Decimal(clicks) / Decimal(impressions) * 100, places=2)


def calculate_cvr(conversions: int, clicks: int) -> Decimal:
    """Conversion rate as percentage."""
    if not clicks:
        return Decimal('0.00')
    return round_currency(Decimal(conversions) / Decimal(clicks) * 100, places=2)


# ---------------------------------------------------------------------------
# Security / Postback helpers
# ---------------------------------------------------------------------------

def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:length - 32] if length > 32 else uuid.uuid4().hex[:length]


def verify_hmac_signature(payload: str, signature: str, secret: str,
                           algorithm: str = 'sha256') -> bool:
    """
    Verify HMAC signature from ad-network postback callbacks.
    Returns True if signature is valid.
    """
    try:
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            algorithm,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.warning("HMAC verification error: %s", exc)
        return False


def hash_ip_address(ip: str) -> str:
    """One-way hash an IP address for privacy-safe storage."""
    salt = getattr(settings, 'SECRET_KEY', 'default-salt')[:16]
    return hashlib.sha256(f"{salt}{ip}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Date / Period helpers
# ---------------------------------------------------------------------------

def get_date_range(period: str, reference_date: Optional[date] = None):
    """
    Return (start_date, end_date) for common period strings.
    period: 'today' | 'yesterday' | 'this_week' | 'last_week' |
            'this_month' | 'last_month' | 'last_7d' | 'last_30d' | 'last_90d'
    """
    today = reference_date or timezone.now().date()

    if period == 'today':
        return today, today
    elif period == 'yesterday':
        d = today - timedelta(days=1)
        return d, d
    elif period == 'last_7d':
        return today - timedelta(days=6), today
    elif period == 'last_30d':
        return today - timedelta(days=29), today
    elif period == 'last_90d':
        return today - timedelta(days=89), today
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end   = start + timedelta(days=6)
        return start, end
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, today
    elif period == 'last_month':
        first_this = today.replace(day=1)
        last_prev  = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    else:
        return today - timedelta(days=29), today


def period_label_for_week(d: date) -> str:
    """Return ISO week label like '2025-W12'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def period_label_for_month(d: date) -> str:
    """Return month label like '2025-03'."""
    return d.strftime('%Y-%m')


# ---------------------------------------------------------------------------
# Offer helpers
# ---------------------------------------------------------------------------

def is_offer_available_for_country(offer, country_code: str) -> bool:
    """Check if an offer is targeted to the given country."""
    if not offer.target_countries:
        return True
    return country_code.upper() in [c.upper() for c in offer.target_countries]


def is_offer_available_for_device(offer, device_type: str) -> bool:
    """Check if an offer is targeted to the given device type."""
    if not offer.target_devices:
        return True
    return device_type.lower() in [d.lower() for d in offer.target_devices]


# ---------------------------------------------------------------------------
# Fraud / Risk helpers
# ---------------------------------------------------------------------------

FRAUD_SIGNALS = {
    'vpn':          20,
    'proxy':        15,
    'tor':          30,
    'datacenter_ip': 25,
    'too_fast':     20,   # completed too quickly
    'duplicate_ip': 10,
}


def calculate_fraud_score(signals: List[str]) -> int:
    """
    Compute a fraud score (0-100) from a list of signal keys.
    Example: calculate_fraud_score(['vpn', 'too_fast']) → 40
    """
    score = sum(FRAUD_SIGNALS.get(s, 0) for s in signals)
    return min(score, 100)


def is_high_risk(fraud_score: int, threshold: int = 70) -> bool:
    return fraud_score >= threshold


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

def paginate_queryset(queryset, page: int, page_size: int):
    """Simple in-memory paginator for non-DRF contexts."""
    start = (page - 1) * page_size
    end   = start + page_size
    total = queryset.count()
    items = list(queryset[start:end])
    return {
        'results':    items,
        'total':      total,
        'page':       page,
        'page_size':  page_size,
        'total_pages': -(-total // page_size),  # ceiling division
        'has_next':   end < total,
        'has_prev':   page > 1,
    }


# ---------------------------------------------------------------------------
# Response formatter
# ---------------------------------------------------------------------------

def success_payload(data=None, message: str = '', meta: dict = None) -> dict:
    payload = {'success': True, 'message': message, 'data': data}
    if meta:
        payload['meta'] = meta
    return payload


def error_payload(message: str = '', errors=None, code: str = 'error') -> dict:
    return {'success': False, 'message': message, 'errors': errors, 'code': code}


# ---------------------------------------------------------------------------
# Marketing / Business helpers
# ---------------------------------------------------------------------------

def calculate_arpu(total_revenue: Decimal, active_users: int) -> Decimal:
    """Average Revenue Per User."""
    if not active_users:
        return Decimal('0.0000')
    return (total_revenue / active_users).quantize(Decimal('0.0001'))


def calculate_ltv(arpu: Decimal, avg_lifetime_months: Decimal) -> Decimal:
    """Lifetime Value = ARPU × avg_lifetime_months."""
    return (arpu * avg_lifetime_months).quantize(Decimal('0.01'))


def calculate_roas(revenue: Decimal, ad_spend: Decimal) -> Decimal:
    """Return on Ad Spend = revenue / ad_spend."""
    if not ad_spend:
        return Decimal('0.0000')
    return (revenue / ad_spend).quantize(Decimal('0.0001'))


def calculate_fill_rate(impressions: int, requests: int) -> Decimal:
    """Ad fill rate as %."""
    if not requests:
        return Decimal('0.0000')
    return (Decimal(impressions) / Decimal(requests) * 100).quantize(Decimal('0.0001'))


def calculate_rpm(revenue: Decimal, sessions: int) -> Decimal:
    """Revenue per 1000 sessions."""
    if not sessions:
        return Decimal('0.0000')
    return (revenue / sessions * 1000).quantize(Decimal('0.0001'))


def coins_needed_for_usd(usd_amount: Decimal, coins_per_usd: Decimal = Decimal('100')) -> Decimal:
    """How many coins needed to equal a given USD amount."""
    return (usd_amount * coins_per_usd).quantize(Decimal('0.01'))


def apply_multiplier(base_value: Decimal, multiplier: Decimal) -> Decimal:
    """Apply a multiplier to a coin/point value."""
    return (base_value * multiplier).quantize(Decimal('0.01'))


def format_coins(amount: Decimal) -> str:
    """Format coins for display, e.g. 1500.00 → '1,500'"""
    return f"{int(amount):,}"


def format_usd(amount: Decimal) -> str:
    """Format USD for display, e.g. 1234.56 → '$1,234.56'"""
    return f"${amount:,.2f}"


def percentage_change(old_value: Decimal, new_value: Decimal) -> Decimal:
    """Calculate percentage change between two values."""
    if not old_value:
        return Decimal('0.00')
    return ((new_value - old_value) / old_value * 100).quantize(Decimal('0.01'))


def truncate_to_hour(dt) -> object:
    """Truncate a datetime to the hour (for AdPerformanceHourly buckets)."""
    return dt.replace(minute=0, second=0, microsecond=0)


def get_current_utc_hour():
    """Get current UTC datetime truncated to hour."""
    from django.utils import timezone
    return truncate_to_hour(timezone.now())


def build_postback_url(base_url: str, params: dict) -> str:
    """Build a postback URL with query parameters."""
    from urllib.parse import urlencode, urljoin
    return f"{base_url}?{urlencode(params)}"


def extract_country_from_ip(ip: str) -> str:
    """
    Stub for GeoIP lookup. In production use django-ipware + GeoIP2.
    Returns 2-letter country code or empty string.
    """
    return ''


def safe_decimal(value, default: Decimal = Decimal('0.00')) -> Decimal:
    """Safely convert any value to Decimal, returning default on failure."""
    try:
        return Decimal(str(value))
    except Exception:
        return default


def chunk_list(lst: list, size: int):
    """Split a list into chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def generate_unique_code(prefix: str = '', length: int = 8) -> str:
    """Generate a unique alphanumeric code."""
    import random, string
    chars = string.ascii_uppercase + string.digits
    code  = ''.join(random.choices(chars, k=length))
    return f"{prefix}{code}" if prefix else code


def mask_account_number(number: str) -> str:
    """Mask sensitive account number: '01711111111' → '0171****111'"""
    if len(number) <= 6:
        return '***'
    return number[:4] + '*' * (len(number) - 7) + number[-3:]
