# api/offer_inventory/validators.py
"""
Bulletproof validators — ধরে নাও ইউজার সবসময় ভুল করবে।
"""
import re
import hmac
import hashlib
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .constants import (
    MIN_WITHDRAWAL_BDT, MAX_WITHDRAWAL_BDT,
    MAX_UPLOAD_SIZE_MB, ALLOWED_IMAGE_TYPES,
)


# ── Amount Validators ────────────────────────────────────────────

def validate_positive_decimal(value):
    """Amount অবশ্যই positive হতে হবে।"""
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(_('বৈধ সংখ্যা দিন।'))
    if d <= 0:
        raise ValidationError(_('পরিমাণ অবশ্যই শূন্যের চেয়ে বেশি হতে হবে।'))
    return d


def validate_withdrawal_amount(amount):
    """Withdrawal amount range check।"""
    try:
        amt = Decimal(str(amount))
    except InvalidOperation:
        raise ValidationError(_('বৈধ পরিমাণ দিন।'))

    if amt < MIN_WITHDRAWAL_BDT:
        raise ValidationError(_(f'সর্বনিম্ন উইথড্রয়াল {MIN_WITHDRAWAL_BDT} টাকা।'))
    if amt > MAX_WITHDRAWAL_BDT:
        raise ValidationError(_(f'সর্বোচ্চ উইথড্রয়াল {MAX_WITHDRAWAL_BDT} টাকা।'))
    return amt


def validate_reward_amount(value):
    """Reward amount non-negative check।"""
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(_('বৈধ reward পরিমাণ দিন।'))
    if d < 0:
        raise ValidationError(_('Reward পরিমাণ ঋণাত্মক হতে পারবে না।'))
    return d


def validate_percentage(value):
    """০–১০০ এর মধ্যে percentage।"""
    try:
        pct = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(_('বৈধ শতাংশ দিন।'))
    if not (Decimal('0') <= pct <= Decimal('100')):
        raise ValidationError(_('শতাংশ ০ থেকে ১০০-এর মধ্যে হতে হবে।'))
    return pct


# ── IP Validators ─────────────────────────────────────────────────

def validate_ip_address(ip: str) -> str:
    """IPv4/IPv6 format check।"""
    import ipaddress
    ip = ip.strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ValidationError(_(f'"{ip}" একটি বৈধ IP address নয়।'))
    return ip


def validate_ip_not_private(ip: str) -> str:
    """Private IP block করো।"""
    import ipaddress
    validated = validate_ip_address(ip)
    obj = ipaddress.ip_address(validated)
    if obj.is_private or obj.is_loopback or obj.is_link_local:
        raise ValidationError(_('Private IP address ব্যবহার করা যাবে না।'))
    return validated


def validate_cidr(cidr: str) -> str:
    """CIDR notation validate।"""
    import ipaddress
    cidr = cidr.strip()
    try:
        ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise ValidationError(_(f'"{cidr}" একটি বৈধ CIDR নয়।'))
    return cidr


# ── Click & Token Validators ──────────────────────────────────────

def validate_click_token(token: str) -> str:
    """Click token format — 64-char hex।"""
    token = token.strip()
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValidationError(_('Click token format ভুল।'))
    return token


def validate_postback_signature(payload: str, signature: str, secret: str) -> bool:
    """HMAC-SHA256 postback signature verify।"""
    if not all([payload, signature, secret]):
        return False
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── URL Validators ─────────────────────────────────────────────────

def validate_https_url(url: str) -> str:
    """URL অবশ্যই https হতে হবে।"""
    if not url:
        raise ValidationError(_('URL দিন।'))
    url = url.strip()
    if not url.startswith('https://'):
        raise ValidationError(_('URL অবশ্যই https:// দিয়ে শুরু হতে হবে।'))
    return url


def validate_tracking_url(url: str) -> str:
    """Tracking URL-এ required macros আছে কিনা check।"""
    url = url.strip()
    if '{click_id}' not in url and '{transaction_id}' not in url:
        raise ValidationError(
            _('Tracking URL-এ {click_id} বা {transaction_id} macro থাকতে হবে।')
        )
    return url


# ── File Validators ────────────────────────────────────────────────

def validate_image_file(file):
    """Image file type এবং size check।"""
    if file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(_(f'ফাইল সর্বোচ্চ {MAX_UPLOAD_SIZE_MB}MB হতে পারবে।'))
    content_type = getattr(file, 'content_type', '')
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(_('শুধুমাত্র JPEG, PNG, WebP ফরম্যাট গ্রহণযোগ্য।'))
    return file


# ── User & Account Validators ──────────────────────────────────────

BD_PHONE_RE = re.compile(r'^(?:\+?88)?01[3-9]\d{8}$')
PHONE_RE    = re.compile(r'^\+?[1-9]\d{6,14}$')


def validate_bd_phone(phone: str) -> str:
    """বাংলাদেশ phone number validate।"""
    phone = phone.strip().replace(' ', '').replace('-', '')
    if not BD_PHONE_RE.match(phone):
        raise ValidationError(_('বৈধ বাংলাদেশ মোবাইল নম্বর দিন।'))
    return phone


def validate_nid(nid: str) -> str:
    """Bangladesh NID — 10 বা 17 digit।"""
    nid = nid.strip().replace(' ', '')
    if not re.fullmatch(r'\d{10}|\d{17}', nid):
        raise ValidationError(_('NID অবশ্যই ১০ বা ১৭ সংখ্যার হতে হবে।'))
    return nid


# ── Offer Validators ──────────────────────────────────────────────

def validate_offer_dates(starts_at, expires_at):
    """অফারের তারিখ সংক্রান্ত নিয়মকানুন।"""
    from django.utils import timezone
    now = timezone.now()
    if starts_at and expires_at and starts_at >= expires_at:
        raise ValidationError(_('শেষ তারিখ শুরু তারিখের পরে হতে হবে।'))
    if expires_at and expires_at <= now:
        raise ValidationError(_('শেষ তারিখ ভবিষ্যতে হতে হবে।'))


def validate_cap_limit(limit: int) -> int:
    """Cap limit অবশ্যই positive।"""
    if not isinstance(limit, int) or limit < 1:
        raise ValidationError(_('Cap limit অবশ্যই ১ বা তার বেশি হতে হবে।'))
    return limit


# ── Payout Validators ─────────────────────────────────────────────

def validate_bkash_number(number: str) -> str:
    """bKash নম্বর validate।"""
    return validate_bd_phone(number)


def validate_nagad_number(number: str) -> str:
    """Nagad নম্বর validate।"""
    return validate_bd_phone(number)


def validate_bank_account(account: str) -> str:
    """Bank account number (basic check)।"""
    account = account.strip()
    if not re.fullmatch(r'[\d\-]{8,20}', account):
        raise ValidationError(_('বৈধ ব্যাংক অ্যাকাউন্ট নম্বর দিন।'))
    return account


# ── Security Validators ───────────────────────────────────────────

def validate_no_sql_injection(value: str) -> str:
    """Basic SQL injection pattern detect।"""
    patterns = [
        r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDROP\b|\bDELETE\b|\bUPDATE\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+|\bAND\b\s+\d+\s*=\s*\d+)",
    ]
    for pat in patterns:
        if re.search(pat, value, re.IGNORECASE):
            raise ValidationError(_('ইনপুটে অবৈধ অক্ষর পাওয়া গেছে।'))
    return value


def validate_no_xss(value: str) -> str:
    """Basic XSS pattern detect।"""
    patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe',
        r'<object',
    ]
    for pat in patterns:
        if re.search(pat, value, re.IGNORECASE):
            raise ValidationError(_('ইনপুটে অনুমোদিত নয় এমন কন্টেন্ট পাওয়া গেছে।'))
    return value


def validate_sub_id(value: str) -> str:
    """Sub-ID alphanumeric only।"""
    if value and not re.fullmatch(r'[a-zA-Z0-9_\-\.]{1,255}', value):
        raise ValidationError(_('Sub-ID-তে শুধু অক্ষর, সংখ্যা, _, - ব্যবহার করুন।'))
    return value
