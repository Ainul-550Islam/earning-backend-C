# api/publisher_tools/validators.py
"""
Publisher Tools — Custom Validators।
Model ও Serializer উভয়তে ব্যবহৃত হয়।
"""
import re
import ipaddress
from urllib.parse import urlparse
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


# ──────────────────────────────────────────────────────────────────────────────
# DOMAIN VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

DOMAIN_REGEX = re.compile(
    r'^(?:[a-zA-Z0-9]'
    r'(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)'
    r'+[a-zA-Z]{2,}$'
)

BLACKLISTED_DOMAINS = [
    'localhost', '127.0.0.1', 'example.com', 'test.com',
    'invalid.com', 'placeholder.com',
]


def validate_domain(value):
    """
    Domain format validate করে।
    'https://'-সহ দিলেও handle করে।
    """
    # Strip protocol if provided
    domain = value.strip()
    for prefix in ['https://', 'http://', 'www.']:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.rstrip('/')

    if not DOMAIN_REGEX.match(domain):
        raise ValidationError(
            _('Invalid domain format. Use: example.com (without https://)'),
            code='invalid_domain'
        )

    if domain.lower() in BLACKLISTED_DOMAINS:
        raise ValidationError(
            _('This domain is not allowed.'),
            code='blacklisted_domain'
        )

    return domain


def validate_url_is_reachable_format(value):
    """URL format ঠিক আছে কিনা চেক করে (actual network request ছাড়া)"""
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https'):
            raise ValidationError(
                _('URL must start with http:// or https://'),
                code='invalid_url_scheme'
            )
        if not parsed.netloc:
            raise ValidationError(
                _('Invalid URL: missing domain.'),
                code='invalid_url'
            )
    except Exception:
        raise ValidationError(
            _('Invalid URL format.'),
            code='invalid_url'
        )


# ──────────────────────────────────────────────────────────────────────────────
# PACKAGE NAME VALIDATORS (Android / iOS)
# ──────────────────────────────────────────────────────────────────────────────

ANDROID_PACKAGE_REGEX = re.compile(
    r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
)

IOS_BUNDLE_REGEX = re.compile(
    r'^[A-Za-z0-9\-\.]+$'
)


def validate_android_package_name(value):
    """Android package name validate করে: com.example.myapp"""
    if not ANDROID_PACKAGE_REGEX.match(value):
        raise ValidationError(
            _('Invalid Android package name. Format: com.example.myapp'),
            code='invalid_package_name'
        )
    if len(value) > 255:
        raise ValidationError(
            _('Package name is too long (max 255 characters).'),
            code='package_name_too_long'
        )


def validate_ios_bundle_id(value):
    """iOS Bundle ID validate করে"""
    if not IOS_BUNDLE_REGEX.match(value):
        raise ValidationError(
            _('Invalid iOS Bundle ID format.'),
            code='invalid_bundle_id'
        )


def validate_package_name(value):
    """Android package name বা iOS bundle ID — দুটোই accept করে"""
    if '.' in value and value.islower():
        return validate_android_package_name(value)
    return validate_ios_bundle_id(value)


# ──────────────────────────────────────────────────────────────────────────────
# FINANCIAL VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_revenue_share(value):
    """Revenue share percentage: 30% থেকে 95% এর মধ্যে হতে হবে"""
    from .constants import MIN_REVENUE_SHARE, MAX_REVENUE_SHARE
    val = Decimal(str(value))
    if val < Decimal(str(MIN_REVENUE_SHARE)):
        raise ValidationError(
            _(f'Revenue share must be at least {MIN_REVENUE_SHARE}%.'),
            code='revenue_share_too_low'
        )
    if val > Decimal(str(MAX_REVENUE_SHARE)):
        raise ValidationError(
            _(f'Revenue share cannot exceed {MAX_REVENUE_SHARE}%.'),
            code='revenue_share_too_high'
        )


def validate_floor_price(value):
    """Floor price: 0 থেকে 100 USD CPM এর মধ্যে হতে হবে"""
    val = Decimal(str(value))
    if val < 0:
        raise ValidationError(
            _('Floor price cannot be negative.'),
            code='negative_floor_price'
        )
    if val > 100:
        raise ValidationError(
            _('Floor price cannot exceed $100 CPM.'),
            code='floor_price_too_high'
        )


def validate_payout_threshold(value):
    """Minimum payout threshold >= $1"""
    val = Decimal(str(value))
    if val < Decimal('1.00'):
        raise ValidationError(
            _('Minimum payout threshold must be at least $1.00'),
            code='threshold_too_low'
        )
    if val > Decimal('10000.00'):
        raise ValidationError(
            _('Payout threshold cannot exceed $10,000.'),
            code='threshold_too_high'
        )


def validate_positive_amount(value):
    """Amount must be positive"""
    if Decimal(str(value)) <= 0:
        raise ValidationError(
            _('Amount must be greater than zero.'),
            code='non_positive_amount'
        )


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_ad_size(width, height):
    """Ad size validate করে — খুব ছোট বা খুব বড় হলে reject"""
    if width is not None and height is not None:
        if width < 50 or height < 20:
            raise ValidationError(
                _('Ad size is too small. Minimum 50x20 pixels.'),
                code='ad_size_too_small'
            )
        if width > 1920 or height > 1080:
            raise ValidationError(
                _('Ad size is too large. Maximum 1920x1080 pixels.'),
                code='ad_size_too_large'
            )


def validate_refresh_interval(value):
    """Refresh interval: 15 to 300 seconds"""
    from .constants import MIN_REFRESH_INTERVAL, MAX_REFRESH_INTERVAL
    if value < MIN_REFRESH_INTERVAL:
        raise ValidationError(
            _(f'Refresh interval must be at least {MIN_REFRESH_INTERVAL} seconds.'),
            code='refresh_too_fast'
        )
    if value > MAX_REFRESH_INTERVAL:
        raise ValidationError(
            _(f'Refresh interval cannot exceed {MAX_REFRESH_INTERVAL} seconds.'),
            code='refresh_too_slow'
        )


def validate_bid_timeout(value):
    """Bid timeout: 100ms to 5000ms"""
    from .constants import MIN_BID_TIMEOUT_MS, MAX_BID_TIMEOUT_MS
    if value < MIN_BID_TIMEOUT_MS:
        raise ValidationError(
            _(f'Bid timeout must be at least {MIN_BID_TIMEOUT_MS}ms.'),
            code='timeout_too_short'
        )
    if value > MAX_BID_TIMEOUT_MS:
        raise ValidationError(
            _(f'Bid timeout cannot exceed {MAX_BID_TIMEOUT_MS}ms.'),
            code='timeout_too_long'
        )


# ──────────────────────────────────────────────────────────────────────────────
# WATERFALL VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_waterfall_priority(value):
    """Priority: 1-20 এর মধ্যে হতে হবে"""
    if value < 1:
        raise ValidationError(
            _('Priority must be at least 1.'),
            code='invalid_priority'
        )
    if value > 20:
        raise ValidationError(
            _('Priority cannot exceed 20 (maximum waterfall items).'),
            code='priority_too_high'
        )


# ──────────────────────────────────────────────────────────────────────────────
# IP ADDRESS VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_ip_address(value):
    """Valid IPv4 বা IPv6 address কিনা চেক করে"""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError(
            _('Invalid IP address format.'),
            code='invalid_ip'
        )


def validate_ip_range(value):
    """Valid CIDR notation কিনা চেক করে (e.g., 192.168.0.0/24)"""
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ValidationError(
            _('Invalid IP range format. Use CIDR notation: 192.168.0.0/24'),
            code='invalid_ip_range'
        )


# ──────────────────────────────────────────────────────────────────────────────
# DATE VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_future_date(value):
    """Date must be in the future"""
    if value <= timezone.now():
        raise ValidationError(
            _('Date must be in the future.'),
            code='date_not_future'
        )


def validate_date_range(start_date, end_date):
    """Start date must be before end date"""
    if start_date >= end_date:
        raise ValidationError(
            _('Start date must be before end date.'),
            code='invalid_date_range'
        )
    
    from .constants import MAX_REPORT_DAYS
    delta = (end_date - start_date).days
    if delta > MAX_REPORT_DAYS:
        raise ValidationError(
            _(f'Date range cannot exceed {MAX_REPORT_DAYS} days.'),
            code='date_range_too_large'
        )


# ──────────────────────────────────────────────────────────────────────────────
# QUALITY SCORE VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_percentage(value):
    """0-100% range"""
    if value < 0 or value > 100:
        raise ValidationError(
            _('Value must be between 0 and 100 percent.'),
            code='invalid_percentage'
        )


def validate_score(value):
    """0-100 score range"""
    if value < 0 or value > 100:
        raise ValidationError(
            _('Score must be between 0 and 100.'),
            code='invalid_score'
        )


# ──────────────────────────────────────────────────────────────────────────────
# TARGETING VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

VALID_COUNTRY_CODES = {
    'ALL', 'AF', 'AL', 'DZ', 'AD', 'AO', 'AG', 'AR', 'AM', 'AU', 'AT',
    'AZ', 'BS', 'BH', 'BD', 'BB', 'BY', 'BE', 'BZ', 'BJ', 'BT', 'BO',
    'BA', 'BW', 'BR', 'BN', 'BG', 'BF', 'BI', 'CV', 'KH', 'CM', 'CA',
    'CF', 'TD', 'CL', 'CN', 'CO', 'KM', 'CG', 'CD', 'CR', 'CI', 'HR',
    'CU', 'CY', 'CZ', 'DK', 'DJ', 'DM', 'DO', 'EC', 'EG', 'SV', 'GQ',
    'ER', 'EE', 'SZ', 'ET', 'FJ', 'FI', 'FR', 'GA', 'GM', 'GE', 'DE',
    'GH', 'GR', 'GD', 'GT', 'GN', 'GW', 'GY', 'HT', 'HN', 'HU', 'IS',
    'IN', 'ID', 'IR', 'IQ', 'IE', 'IL', 'IT', 'JM', 'JP', 'JO', 'KZ',
    'KE', 'KI', 'KP', 'KR', 'KW', 'KG', 'LA', 'LV', 'LB', 'LS', 'LR',
    'LY', 'LI', 'LT', 'LU', 'MG', 'MW', 'MY', 'MV', 'ML', 'MT', 'MH',
    'MR', 'MU', 'MX', 'FM', 'MD', 'MC', 'MN', 'ME', 'MA', 'MZ', 'MM',
    'NA', 'NR', 'NP', 'NL', 'NZ', 'NI', 'NE', 'NG', 'MK', 'NO', 'OM',
    'PK', 'PW', 'PA', 'PG', 'PY', 'PE', 'PH', 'PL', 'PT', 'QA', 'RO',
    'RU', 'RW', 'KN', 'LC', 'VC', 'WS', 'SM', 'ST', 'SA', 'SN', 'RS',
    'SC', 'SL', 'SG', 'SK', 'SI', 'SB', 'SO', 'ZA', 'SS', 'ES', 'LK',
    'SD', 'SR', 'SE', 'CH', 'SY', 'TW', 'TJ', 'TZ', 'TH', 'TL', 'TG',
    'TO', 'TT', 'TN', 'TR', 'TM', 'TV', 'UG', 'UA', 'AE', 'GB', 'US',
    'UY', 'UZ', 'VU', 'VE', 'VN', 'YE', 'ZM', 'ZW',
}


def validate_country_codes(value):
    """Country code list validate করে"""
    if not isinstance(value, list):
        raise ValidationError(
            _('Country codes must be a list.'),
            code='invalid_type'
        )
    for code in value:
        if code.upper() not in VALID_COUNTRY_CODES:
            raise ValidationError(
                _(f'Invalid country code: {code}'),
                code='invalid_country_code'
            )


def validate_schedule_hours(start_hour, end_hour):
    """Schedule hours range validate করে"""
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        raise ValidationError(
            _('Hours must be between 0 and 23.'),
            code='invalid_hour'
        )
    if start_hour > end_hour:
        raise ValidationError(
            _('Start hour must be less than or equal to end hour.'),
            code='invalid_hour_range'
        )


# ──────────────────────────────────────────────────────────────────────────────
# A/B TESTING VALIDATORS
# ──────────────────────────────────────────────────────────────────────────────

def validate_traffic_split(variants):
    """
    A/B test variant traffic split validate করে।
    সব variants-এর percentage মোট 100% হতে হবে।
    """
    if not variants:
        raise ValidationError(
            _('At least 2 variants are required.'),
            code='not_enough_variants'
        )
    if len(variants) > 5:
        raise ValidationError(
            _('Maximum 5 variants allowed.'),
            code='too_many_variants'
        )

    total = sum(v.get('traffic_split', 0) for v in variants)
    if abs(total - 100.0) > 0.01:
        raise ValidationError(
            _(f'Traffic splits must sum to 100%. Current sum: {total}%'),
            code='invalid_traffic_split'
        )
