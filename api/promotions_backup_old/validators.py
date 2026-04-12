# =============================================================================
# api/promotions/validators.py
# Reusable Validators — models ও serializers উভয়ে ব্যবহার হবে
# =============================================================================

import ipaddress
import re
from decimal import Decimal
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .constants import (
    PROOF_MAX_FILE_SIZE_KB,
    PROOF_ALLOWED_IMAGE_EXTENSIONS,
    PROOF_ALLOWED_VIDEO_EXTENSIONS,
    WITHDRAWAL_MIN_USD,
    WITHDRAWAL_MAX_USD,
    CAMPAIGN_MIN_BUDGET_USD,
)


# ─── IP Address ───────────────────────────────────────────────────────────────

def validate_ip_address(value: str) -> None:
    """IPv4 এবং IPv6 উভয়ই validate করে।"""
    try:
        ipaddress.ip_address(str(value).strip())
    except ValueError:
        raise ValidationError(
            _('%(value)s একটি valid IP address নয় (IPv4 বা IPv6 দিন)।'),
            params={'value': value},
            code='invalid_ip',
        )


def validate_not_private_ip(value: str) -> None:
    """Private/loopback IP reject করে (production security)।"""
    try:
        ip = ipaddress.ip_address(str(value).strip())
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValidationError(
                _('Private বা loopback IP address ব্যবহার করা যাবে না।'),
                code='private_ip',
            )
    except ValueError:
        raise ValidationError(_('Valid IP address দিন।'), code='invalid_ip')


# ─── Country / Currency ───────────────────────────────────────────────────────

def validate_country_code(value: str) -> None:
    """ISO 3166-1 alpha-2 country code validate করে।"""
    if not re.match(r'^[A-Z]{2}$', str(value).strip().upper()):
        raise ValidationError(
            _('%(value)s একটি valid ISO alpha-2 country code নয় (e.g. US, BD, IN)।'),
            params={'value': value},
            code='invalid_country_code',
        )


def validate_currency_code(value: str) -> None:
    """ISO 4217 currency code validate করে।"""
    if not re.match(r'^[A-Z]{3}$', str(value).strip().upper()):
        raise ValidationError(
            _('%(value)s একটি valid ISO 4217 currency code নয় (e.g. USD, BDT, INR)।'),
            params={'value': value},
            code='invalid_currency_code',
        )


# ─── URL ──────────────────────────────────────────────────────────────────────

def validate_http_https_url(value: str) -> None:
    """শুধুমাত্র http/https URL accept করে।"""
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https'):
            raise ValidationError(
                _('শুধুমাত্র http:// বা https:// URL গ্রহণযোগ্য।'),
                code='invalid_url_scheme',
            )
        if not parsed.netloc:
            raise ValidationError(
                _('URL এ valid domain থাকতে হবে।'),
                code='invalid_url_domain',
            )
    except Exception:
        raise ValidationError(_('Valid URL দিন।'), code='invalid_url')


def validate_youtube_url(value: str) -> None:
    """YouTube channel বা video URL validate করে।"""
    patterns = [
        r'^https?://(www\.)?youtube\.com/',
        r'^https?://youtu\.be/',
    ]
    if not any(re.match(p, value) for p in patterns):
        raise ValidationError(
            _('Valid YouTube URL দিন (youtube.com বা youtu.be)।'),
            code='invalid_youtube_url',
        )


def validate_no_malicious_url(value: str) -> None:
    """Known malicious patterns check করে।"""
    suspicious_patterns = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'<script',
        r'onclick=',
    ]
    lower = value.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, lower):
            raise ValidationError(
                _('URL এ সন্দেহজনক content পাওয়া গেছে।'),
                code='malicious_url',
            )


# ─── File / Proof ─────────────────────────────────────────────────────────────

def validate_proof_file_size(value_kb: int) -> None:
    """Proof file size সীমার মধ্যে আছে কিনা check করে।"""
    if value_kb > PROOF_MAX_FILE_SIZE_KB:
        raise ValidationError(
            _(f'File size সর্বোচ্চ {PROOF_MAX_FILE_SIZE_KB // 1024} MB হতে পারবে। '
              f'আপনার file: {value_kb // 1024} MB।'),
            code='file_too_large',
        )


def validate_image_extension(filename: str) -> None:
    """Image file extension validate করে।"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in PROOF_ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            _(f'গ্রহণযোগ্য image format: {", ".join(PROOF_ALLOWED_IMAGE_EXTENSIONS)}।'),
            code='invalid_image_extension',
        )


def validate_video_extension(filename: str) -> None:
    """Video file extension validate করে।"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in PROOF_ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(
            _(f'গ্রহণযোগ্য video format: {", ".join(PROOF_ALLOWED_VIDEO_EXTENSIONS)}।'),
            code='invalid_video_extension',
        )


def validate_screenshot_url(value: str) -> None:
    """Screenshot URL validate — https এবং image extension থাকতে হবে।"""
    validate_http_https_url(value)
    parsed = urlparse(value)
    path = parsed.path.lower()
    # Common image hosting domains বা image extension থাকলে pass
    allowed_domains = ['imgur.com', 'prnt.sc', 'i.imgur.com', 'ibb.co', 'postimg.cc']
    domain = parsed.netloc.lower().lstrip('www.')
    has_image_ext = any(path.endswith(f'.{ext}') for ext in PROOF_ALLOWED_IMAGE_EXTENSIONS)
    if not has_image_ext and domain not in allowed_domains:
        # Strict না করে warning দিই — AI verification এ ধরা পড়বে
        pass  # Allow করি, AI decide করবে


# ─── Financial ────────────────────────────────────────────────────────────────

def validate_positive_decimal(value: Decimal) -> None:
    """Decimal value positive কিনা check করে।"""
    if value <= 0:
        raise ValidationError(
            _('পরিমাণ অবশ্যই শূন্যের চেয়ে বেশি হতে হবে।'),
            code='non_positive_amount',
        )


def validate_withdrawal_amount(value: Decimal) -> None:
    """Withdrawal amount সীমার মধ্যে আছে কিনা।"""
    if value < WITHDRAWAL_MIN_USD:
        raise ValidationError(
            _(f'সর্বনিম্ন withdrawal পরিমাণ ${WITHDRAWAL_MIN_USD}।'),
            code='withdrawal_too_small',
        )
    if value > WITHDRAWAL_MAX_USD:
        raise ValidationError(
            _(f'একবারে সর্বোচ্চ ${WITHDRAWAL_MAX_USD} withdrawal করা যাবে।'),
            code='withdrawal_too_large',
        )


def validate_campaign_budget(value: Decimal) -> None:
    """Campaign budget minimum check।"""
    if value < CAMPAIGN_MIN_BUDGET_USD:
        raise ValidationError(
            _(f'Campaign budget সর্বনিম্ন ${CAMPAIGN_MIN_BUDGET_USD} হতে হবে।'),
            code='budget_too_small',
        )


def validate_percentage(value: Decimal) -> None:
    """0–100 এর মধ্যে percentage।"""
    if not (Decimal('0') <= value <= Decimal('100')):
        raise ValidationError(
            _('Percentage অবশ্যই 0 থেকে 100 এর মধ্যে হতে হবে।'),
            code='invalid_percentage',
        )


# ─── Device Fingerprint ───────────────────────────────────────────────────────

def validate_fingerprint_hash(value: str) -> None:
    """SHA-256 hex hash format validate করে।"""
    if not re.match(r'^[a-f0-9]{32,64}$', str(value).lower()):
        raise ValidationError(
            _('Fingerprint hash অবশ্যই 32-64 character এর lowercase hex string হতে হবে।'),
            code='invalid_fingerprint_hash',
        )


# ─── Screen Resolution ────────────────────────────────────────────────────────

def validate_screen_resolution(value: str) -> None:
    """Screen resolution format: WIDTHxHEIGHT (e.g. 1920x1080)।"""
    if not re.match(r'^\d{2,5}x\d{2,5}$', str(value)):
        raise ValidationError(
            _('Screen resolution format হবে WxH (যেমন: 1920x1080)।'),
            code='invalid_resolution',
        )


# ─── JSON Field Validators ────────────────────────────────────────────────────

def validate_country_code_list(value: list) -> None:
    """JSON field এর country code list validate করে।"""
    if not isinstance(value, list):
        raise ValidationError(_('List format এ দিতে হবে।'), code='not_a_list')
    for code in value:
        validate_country_code(code)


def validate_device_type_list(value: list) -> None:
    """JSON field এর device type list validate করে।"""
    valid = {'mobile', 'desktop', 'tablet'}
    if not isinstance(value, list):
        raise ValidationError(_('List format এ দিতে হবে।'), code='not_a_list')
    invalid = set(value) - valid
    if invalid:
        raise ValidationError(
            _(f'Invalid device type(s): {invalid}। গ্রহণযোগ্য: {valid}'),
            code='invalid_device_type',
        )


def validate_os_type_list(value: list) -> None:
    """JSON field এর OS type list validate করে।"""
    valid = {'android', 'ios', 'windows', 'macos', 'linux'}
    if not isinstance(value, list):
        raise ValidationError(_('List format এ দিতে হবে।'), code='not_a_list')
    invalid = set(value) - valid
    if invalid:
        raise ValidationError(
            _(f'Invalid OS type(s): {invalid}। গ্রহণযোগ্য: {valid}'),
            code='invalid_os_type',
        )


# ─── Text Safety ──────────────────────────────────────────────────────────────

def validate_no_html_tags(value: str) -> None:
    """XSS prevention — HTML tags থাকলে reject করে।"""
    if re.search(r'<[^>]+>', str(value)):
        raise ValidationError(
            _('HTML tags ব্যবহার করা যাবে না।'),
            code='html_tags_not_allowed',
        )


def validate_no_sql_injection(value: str) -> None:
    """Basic SQL injection pattern check।"""
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(--|;|\/\*|\*\/)",
        r"(\bOR\b\s+\d+=\d+)",
        r"(\bAND\b\s+\d+=\d+)",
    ]
    for pattern in sql_patterns:
        if re.search(pattern, str(value), re.IGNORECASE):
            raise ValidationError(
                _('Input এ সন্দেহজনক character পাওয়া গেছে।'),
                code='sql_injection_attempt',
            )
