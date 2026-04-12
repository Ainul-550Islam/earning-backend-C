# api/publisher_tools/utils.py
"""
Publisher Tools — Utility functions।
Helper methods যা বিভিন্ন জায়গায় ব্যবহার হয়।
"""
import uuid
import hashlib
import hmac
import re
import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.utils import timezone
from django.conf import settings


# ──────────────────────────────────────────────────────────────────────────────
# ID GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def generate_publisher_id(count: int) -> str:
    """PUB000001 format-এ Publisher ID generate করে"""
    from .constants import PUBLISHER_ID_PREFIX, PUBLISHER_ID_LENGTH
    return f"{PUBLISHER_ID_PREFIX}{count:0{PUBLISHER_ID_LENGTH}d}"


def generate_site_id(count: int) -> str:
    """SITE000001 format-এ Site ID generate করে"""
    from .constants import SITE_ID_PREFIX, SITE_ID_LENGTH
    return f"{SITE_ID_PREFIX}{count:0{SITE_ID_LENGTH}d}"


def generate_app_id(count: int) -> str:
    """APP000001 format-এ App ID generate করে"""
    from .constants import APP_ID_PREFIX, APP_ID_LENGTH
    return f"{APP_ID_PREFIX}{count:0{APP_ID_LENGTH}d}"


def generate_unit_id(count: int) -> str:
    """UNIT000001 format-এ Ad Unit ID generate করে"""
    from .constants import UNIT_ID_PREFIX, UNIT_ID_LENGTH
    return f"{UNIT_ID_PREFIX}{count:0{UNIT_ID_LENGTH}d}"


def generate_invoice_number(year: int, month: int, count: int) -> str:
    """INV-2024-01-000001 format-এ Invoice Number generate করে"""
    return f"INV-{year}-{month:02d}-{count:06d}"


def generate_verification_token() -> str:
    """Unique verification token generate করে"""
    return uuid.uuid4().hex


def generate_api_key() -> str:
    """64-character API key generate করে"""
    return uuid.uuid4().hex + uuid.uuid4().hex[:32]


def generate_api_secret() -> str:
    """128-character API secret generate করে"""
    return uuid.uuid4().hex * 2 + uuid.uuid4().hex[:32]


# ──────────────────────────────────────────────────────────────────────────────
# DOMAIN UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def clean_domain(domain: str) -> str:
    """
    Domain থেকে protocol ও trailing slash সরিয়ে clean করে।
    'https://www.example.com/' → 'example.com'
    """
    domain = domain.strip().lower()
    for prefix in ['https://', 'http://']:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    if domain.startswith('www.'):
        domain = domain[4:]
    domain = domain.rstrip('/')
    return domain


def get_root_domain(domain: str) -> str:
    """
    Subdomain থেকে root domain বের করে।
    'blog.example.com' → 'example.com'
    """
    parts = domain.split('.')
    if len(parts) > 2:
        return '.'.join(parts[-2:])
    return domain


def build_ads_txt_url(domain: str) -> str:
    """ads.txt URL build করে"""
    return f"https://{domain}/ads.txt"


def build_verification_meta_tag(token: str) -> str:
    """HTML meta tag verification code build করে"""
    return f'<meta name="publisher-verification" content="{token}" />'


def build_verification_dns_record(token: str) -> str:
    """DNS TXT record verification code build করে"""
    return f'publisher-verification={token}'


def build_ads_txt_entry(publisher_id: str, network_domain: str = 'ads.example.com') -> str:
    """ads.txt এ যোগ করার জন্য entry build করে"""
    return f"{network_domain}, {publisher_id}, DIRECT, f08c47fec0942fa0"


# ──────────────────────────────────────────────────────────────────────────────
# FINANCIAL CALCULATIONS
# ──────────────────────────────────────────────────────────────────────────────

def calculate_ecpm(revenue: Decimal, impressions: int) -> Decimal:
    """
    eCPM (Effective Cost Per Mille) calculate করে।
    eCPM = (Revenue / Impressions) * 1000
    """
    if impressions <= 0:
        return Decimal('0.0000')
    ecpm = (Decimal(str(revenue)) / Decimal(str(impressions))) * 1000
    return ecpm.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_ctr(clicks: int, impressions: int) -> Decimal:
    """
    CTR (Click-Through Rate) calculate করে।
    CTR = (Clicks / Impressions) * 100
    """
    if impressions <= 0:
        return Decimal('0.0000')
    ctr = (Decimal(str(clicks)) / Decimal(str(impressions))) * 100
    return ctr.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_fill_rate(impressions: int, requests: int) -> Decimal:
    """
    Fill Rate calculate করে।
    Fill Rate = (Impressions / Ad Requests) * 100
    """
    if requests <= 0:
        return Decimal('0.00')
    fill = (Decimal(str(impressions)) / Decimal(str(requests))) * 100
    return fill.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_rpm(revenue: Decimal, pageviews: int) -> Decimal:
    """
    RPM (Revenue Per Mille pageviews) calculate করে।
    RPM = (Revenue / Pageviews) * 1000
    """
    if pageviews <= 0:
        return Decimal('0.0000')
    rpm = (Decimal(str(revenue)) / Decimal(str(pageviews))) * 1000
    return rpm.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_publisher_revenue(
    gross_revenue: Decimal,
    revenue_share_percentage: Decimal,
    ivt_deduction: Decimal = Decimal('0'),
) -> Decimal:
    """
    Publisher-এর actual revenue calculate করে।
    Publisher Revenue = (Gross Revenue * Revenue Share%) - IVT Deduction
    """
    share = Decimal(str(gross_revenue)) * (Decimal(str(revenue_share_percentage)) / 100)
    return max(Decimal('0'), share - Decimal(str(ivt_deduction)))


def calculate_processing_fee(
    amount: Decimal,
    flat_fee: Decimal,
    percentage_fee: Decimal,
) -> Decimal:
    """Processing fee calculate করে (flat + percentage combined)"""
    percentage_amount = Decimal(str(amount)) * (Decimal(str(percentage_fee)) / 100)
    total = Decimal(str(flat_fee)) + percentage_amount
    return total.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_withholding_tax(amount: Decimal, tax_rate: Decimal) -> Decimal:
    """Withholding tax calculate করে"""
    tax = Decimal(str(amount)) * (Decimal(str(tax_rate)) / 100)
    return tax.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_net_payable(
    publisher_revenue: Decimal,
    ivt_deduction: Decimal,
    adjustment: Decimal,
    processing_fee: Decimal,
    withholding_tax: Decimal,
) -> Decimal:
    """Net payable amount calculate করে"""
    net = (
        Decimal(str(publisher_revenue))
        - Decimal(str(ivt_deduction))
        + Decimal(str(adjustment))
        - Decimal(str(processing_fee))
        - Decimal(str(withholding_tax))
    )
    return max(Decimal('0'), net.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


# ──────────────────────────────────────────────────────────────────────────────
# QUALITY SCORE CALCULATION
# ──────────────────────────────────────────────────────────────────────────────

def calculate_quality_score(
    viewability_rate: float,
    content_score: int,
    invalid_traffic_percentage: float,
    page_speed_score: int = 50,
) -> int:
    """
    Composite quality score calculate করে।
    Weights: Viewability 35%, Content 30%, Traffic 25%, Performance 10%
    """
    from .constants import (
        QUALITY_WEIGHT_VIEWABILITY, QUALITY_WEIGHT_CONTENT,
        QUALITY_WEIGHT_TRAFFIC, QUALITY_WEIGHT_PERFORMANCE
    )
    viewability_component = min(viewability_rate, 100) * QUALITY_WEIGHT_VIEWABILITY
    content_component     = content_score * QUALITY_WEIGHT_CONTENT
    traffic_quality       = max(0, 100 - invalid_traffic_percentage) * QUALITY_WEIGHT_TRAFFIC
    performance           = (page_speed_score or 50) * QUALITY_WEIGHT_PERFORMANCE

    score = viewability_component + content_component + traffic_quality + performance
    return max(0, min(100, round(score)))


# ──────────────────────────────────────────────────────────────────────────────
# STATISTICAL / A/B TEST UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def calculate_statistical_significance(
    control_impressions: int,
    control_conversions: int,
    variant_impressions: int,
    variant_conversions: int,
) -> float:
    """
    Two-proportion z-test দিয়ে statistical significance calculate করে।
    Returns confidence level (0-100).
    """
    if control_impressions == 0 or variant_impressions == 0:
        return 0.0

    p1 = control_conversions / control_impressions
    p2 = variant_conversions / variant_impressions
    p_pooled = (control_conversions + variant_conversions) / (control_impressions + variant_impressions)

    if p_pooled == 0 or p_pooled == 1:
        return 0.0

    se = math.sqrt(p_pooled * (1 - p_pooled) * (1/control_impressions + 1/variant_impressions))
    if se == 0:
        return 0.0

    z_score = abs(p1 - p2) / se

    # Normal distribution CDF approximation
    def normal_cdf(x):
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    confidence = normal_cdf(z_score) * 100
    return round(confidence, 2)


def calculate_uplift(control_value: float, variant_value: float) -> float:
    """
    Uplift percentage calculate করে।
    Uplift = ((Variant - Control) / Control) * 100
    """
    if control_value == 0:
        return 0.0
    uplift = ((variant_value - control_value) / control_value) * 100
    return round(uplift, 2)


def calculate_required_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    confidence_level: float = 0.95,
    power: float = 0.80,
) -> int:
    """
    Statistical power-এর জন্য required sample size calculate করে।
    """
    if baseline_rate <= 0 or baseline_rate >= 1:
        return 1000

    # Z-scores for common confidence levels and power
    z_alpha = 1.96 if confidence_level >= 0.95 else 1.645
    z_beta = 0.842 if power >= 0.80 else 0.674

    p1 = baseline_rate
    p2 = baseline_rate * (1 + minimum_detectable_effect / 100)
    p2 = min(p2, 0.99)

    p_avg = (p1 + p2) / 2
    n = (z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) + z_beta * math.sqrt(
        p1 * (1 - p1) + p2 * (1 - p2)
    )) ** 2 / (p2 - p1) ** 2

    return max(1000, math.ceil(n))


# ──────────────────────────────────────────────────────────────────────────────
# SECURITY / HASH UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def generate_webhook_signature(payload: str, secret: str) -> str:
    """HMAC-SHA256 দিয়ে webhook signature generate করে"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Webhook signature verify করে"""
    expected = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Sensitive data mask করে।
    'sk-abcdefghijk' → 'sk-a*******ijk'
    """
    if len(data) <= visible_chars * 2:
        return '*' * len(data)
    return data[:visible_chars] + '*' * (len(data) - visible_chars * 2) + data[-visible_chars:]


# ──────────────────────────────────────────────────────────────────────────────
# DATE / TIME UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def get_date_range(period: str, reference_date=None):
    """
    Period string থেকে start ও end date calculate করে।
    period: 'today', 'yesterday', 'last_7_days', 'last_30_days',
             'this_month', 'last_month', 'this_year'
    """
    if reference_date is None:
        reference_date = timezone.now().date()

    if period == 'today':
        return reference_date, reference_date
    elif period == 'yesterday':
        d = reference_date - timedelta(days=1)
        return d, d
    elif period == 'last_7_days':
        return reference_date - timedelta(days=6), reference_date
    elif period == 'last_30_days':
        return reference_date - timedelta(days=29), reference_date
    elif period == 'this_month':
        start = reference_date.replace(day=1)
        return start, reference_date
    elif period == 'last_month':
        first_of_this_month = reference_date.replace(day=1)
        end = first_of_this_month - timedelta(days=1)
        start = end.replace(day=1)
        return start, end
    elif period == 'this_year':
        start = reference_date.replace(month=1, day=1)
        return start, reference_date
    else:
        # Default: last 30 days
        return reference_date - timedelta(days=29), reference_date


def format_currency(amount: Decimal, currency: str = 'USD') -> str:
    """Currency format করে display করার জন্য"""
    from .constants import CURRENCY_SYMBOLS
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), '$')
    return f"{symbol}{float(amount):,.2f}"


def format_large_number(value: int) -> str:
    """Large numbers readable format-এ দেখায়: 1234567 → 1.2M"""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


# ──────────────────────────────────────────────────────────────────────────────
# CACHE UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def build_cache_key(*args) -> str:
    """Cache key build করে"""
    from .constants import CACHE_KEY_PREFIX
    parts = [str(a) for a in args]
    return f"{CACHE_KEY_PREFIX}:{'_'.join(parts)}"


def get_publisher_cache_key(publisher_id: str, suffix: str) -> str:
    return build_cache_key('publisher', publisher_id, suffix)


def get_site_cache_key(site_id: str, suffix: str) -> str:
    return build_cache_key('site', site_id, suffix)


def get_unit_cache_key(unit_id: str, suffix: str) -> str:
    return build_cache_key('unit', unit_id, suffix)
