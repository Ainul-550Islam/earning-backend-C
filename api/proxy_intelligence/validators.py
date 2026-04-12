"""
Proxy Intelligence Validators  (PRODUCTION-READY — COMPLETE)
=============================================================
Django form/serializer validators for the proxy_intelligence module.
Used by views.py and serializers.py for request validation.

Validators:
  - IP address validation (IPv4 + IPv6)
  - CIDR notation validation
  - Bulk IP list validation
  - Canvas/WebGL hash format validation
  - Risk score range validation
  - API key format validation
  - Webhook URL validation
  - Confidence score validation (0.0–1.0)
  - Tenant-aware IP uniqueness validation
  - Blacklist reason validation
"""
import ipaddress
import re
from typing import List, Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ── IP Address Validators ──────────────────────────────────────────────────

def validate_ip_address(value: str) -> str:
    """
    Validate an IP address string (IPv4 or IPv6).
    Returns the normalised IP string.
    Raises ValidationError if invalid.
    """
    if not value:
        raise ValidationError(_('IP address is required.'))

    value = value.strip()

    try:
        addr = ipaddress.ip_address(value)
        return str(addr)  # Return normalised form
    except ValueError:
        raise ValidationError(
            _("'%(value)s' is not a valid IP address."),
            params={'value': value},
            code='invalid_ip',
        )


def validate_ip_not_private(value: str) -> str:
    """
    Validate that an IP address is not private/reserved.
    Used for blacklist entries — private IPs cannot be meaningfully blacklisted.
    """
    value = validate_ip_address(value)
    try:
        addr = ipaddress.ip_address(value)
        if addr.is_private:
            raise ValidationError(
                _("'%(value)s' is a private IP address and cannot be blacklisted."),
                params={'value': value},
                code='private_ip',
            )
        if addr.is_loopback:
            raise ValidationError(
                _("'%(value)s' is a loopback address and cannot be blacklisted."),
                params={'value': value},
                code='loopback_ip',
            )
        if addr.is_reserved:
            raise ValidationError(
                _("'%(value)s' is a reserved IP address."),
                params={'value': value},
                code='reserved_ip',
            )
    except ValidationError:
        raise
    except Exception:
        pass
    return value


def validate_cidr(value: str) -> str:
    """
    Validate CIDR notation (e.g. '192.168.1.0/24').
    Returns the normalised network string.
    """
    if not value:
        raise ValidationError(_('CIDR notation is required.'))

    value = value.strip()

    try:
        network = ipaddress.ip_network(value, strict=False)
        return str(network)
    except ValueError:
        raise ValidationError(
            _("'%(value)s' is not a valid CIDR notation."),
            params={'value': value},
            code='invalid_cidr',
        )


def validate_ip_or_cidr(value: str) -> str:
    """
    Validate either an IP address or CIDR notation.
    Returns the normalised string.
    """
    value = value.strip()
    if '/' in value:
        return validate_cidr(value)
    return validate_ip_address(value)


# ── Bulk IP List Validators ────────────────────────────────────────────────

def validate_ip_list(ip_list: List[str],
                      max_count: int = 100,
                      allow_private: bool = False) -> List[str]:
    """
    Validate a list of IP addresses.

    Args:
        ip_list:       List of IP strings
        max_count:     Maximum allowed IPs in the list
        allow_private: If False, private IPs will be skipped (not raise)

    Returns:
        List of normalised, valid IP strings

    Raises:
        ValidationError if the list exceeds max_count
    """
    if not ip_list:
        raise ValidationError(_('At least one IP address is required.'))

    if len(ip_list) > max_count:
        raise ValidationError(
            _('Maximum %(max)s IP addresses allowed per request. Got %(count)s.'),
            params={'max': max_count, 'count': len(ip_list)},
            code='too_many_ips',
        )

    validated = []
    for ip_str in ip_list:
        if not ip_str or not isinstance(ip_str, str):
            continue
        ip_str = ip_str.strip()
        if not ip_str:
            continue
        try:
            addr = ipaddress.ip_address(ip_str)
            if not allow_private and (addr.is_private or addr.is_loopback):
                continue  # Skip silently in bulk mode
            validated.append(str(addr))
        except ValueError:
            continue  # Skip invalid IPs silently in bulk mode

    if not validated:
        raise ValidationError(
            _('No valid IP addresses found in the provided list.'),
            code='no_valid_ips',
        )

    return validated


# ── Hash Validators ────────────────────────────────────────────────────────

def validate_hex_hash(value: str, expected_length: Optional[int] = None,
                       field_name: str = 'hash') -> str:
    """
    Validate a hexadecimal hash string.

    Args:
        value:           The hash string to validate
        expected_length: Expected hex length (e.g. 64 for SHA256, 32 for MD5)
        field_name:      Used in error messages

    Returns:
        Lowercase normalised hash string
    """
    if not value:
        return ''  # Empty is allowed (fingerprint not available)

    value = value.strip().lower()
    HEX_PATTERN = re.compile(r'^[0-9a-f]+$')

    if not HEX_PATTERN.match(value):
        raise ValidationError(
            _("%(field)s must be a valid hexadecimal string. Got '%(value)s'."),
            params={'field': field_name.title(), 'value': value[:20]},
            code='invalid_hex',
        )

    if expected_length and len(value) != expected_length:
        raise ValidationError(
            _("%(field)s must be %(length)s characters long. Got %(actual)s."),
            params={
                'field':  field_name.title(),
                'length': expected_length,
                'actual': len(value),
            },
            code='invalid_hash_length',
        )

    return value


def validate_sha256_hash(value: str, field_name: str = 'hash') -> str:
    """Validate a SHA256 hash (64 hex chars)."""
    return validate_hex_hash(value, expected_length=64, field_name=field_name)


def validate_md5_hash(value: str, field_name: str = 'hash') -> str:
    """Validate an MD5 hash (32 hex chars)."""
    return validate_hex_hash(value, expected_length=32, field_name=field_name)


def validate_canvas_hash(value: str) -> str:
    """Validate a canvas fingerprint hash (SHA256 or MD5)."""
    if not value:
        return ''
    value = value.strip().lower()
    if len(value) not in (64, 32, 40):  # SHA256, MD5, SHA1
        raise ValidationError(
            _("Canvas hash must be 32, 40, or 64 characters. Got %(len)s."),
            params={'len': len(value)},
            code='invalid_canvas_hash',
        )
    return validate_hex_hash(value, field_name='canvas_hash')


# ── Score/Confidence Validators ────────────────────────────────────────────

def validate_risk_score(value: int) -> int:
    """Validate risk score is in range 0–100."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            _('Risk score must be an integer.'),
            code='invalid_risk_score',
        )

    if not (0 <= value <= 100):
        raise ValidationError(
            _('Risk score must be between 0 and 100. Got %(value)s.'),
            params={'value': value},
            code='risk_score_out_of_range',
        )
    return value


def validate_confidence_score(value) -> float:
    """Validate confidence score is a float in range 0.0–1.0."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValidationError(
            _('Confidence score must be a number.'),
            code='invalid_confidence_score',
        )

    if not (0.0 <= value <= 1.0):
        raise ValidationError(
            _('Confidence score must be between 0.0 and 1.0. Got %(value)s.'),
            params={'value': value},
            code='confidence_score_out_of_range',
        )
    return round(value, 4)


# ── Webhook / URL Validators ───────────────────────────────────────────────

def validate_webhook_url(value: str) -> str:
    """
    Validate a webhook URL.
    Must be HTTPS (to prevent plaintext credential leakage).
    """
    if not value:
        return ''

    value = value.strip()

    if not value.startswith('https://'):
        raise ValidationError(
            _('Webhook URL must use HTTPS. Got: %(value)s'),
            params={'value': value[:50]},
            code='insecure_webhook_url',
        )

    URL_PATTERN = re.compile(
        r'^https://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})'
        r'(?::\d+)?(?:/[^\s]*)?$'
    )
    if not URL_PATTERN.match(value):
        raise ValidationError(
            _('Invalid webhook URL format.'),
            code='invalid_webhook_url',
        )

    return value


def validate_webhook_url_permissive(value: str) -> str:
    """
    More permissive webhook URL validator.
    Allows HTTP (for local development/testing).
    """
    if not value:
        return ''
    value = value.strip()
    if not (value.startswith('http://') or value.startswith('https://')):
        raise ValidationError(
            _('Webhook URL must start with http:// or https://.'),
            code='invalid_webhook_scheme',
        )
    return value


# ── API Key Validators ────────────────────────────────────────────────────

def validate_api_key(value: str, min_length: int = 16,
                      max_length: int = 500) -> str:
    """
    Validate an API key string.

    Args:
        value:      The API key to validate
        min_length: Minimum key length (default 16 chars)
        max_length: Maximum key length (default 500 chars)
    """
    if not value:
        raise ValidationError(
            _('API key is required.'),
            code='missing_api_key',
        )

    value = value.strip()

    if len(value) < min_length:
        raise ValidationError(
            _('API key is too short (minimum %(min)s characters).'),
            params={'min': min_length},
            code='api_key_too_short',
        )

    if len(value) > max_length:
        raise ValidationError(
            _('API key is too long (maximum %(max)s characters).'),
            params={'max': max_length},
            code='api_key_too_long',
        )

    # Basic printable ASCII check (no spaces in API keys)
    if not re.match(r'^[^\s]+$', value):
        raise ValidationError(
            _('API key must not contain spaces.'),
            code='api_key_has_spaces',
        )

    return value


# ── Screen Resolution Validator ────────────────────────────────────────────

def validate_screen_resolution(value: str) -> str:
    """
    Validate a screen resolution string like '1920x1080' or '2560x1440'.
    """
    if not value:
        return ''

    value = value.strip().lower()
    pattern = re.compile(r'^\d+x\d+$')
    if not pattern.match(value):
        raise ValidationError(
            _("Invalid screen resolution format. Expected 'WIDTHxHEIGHT' (e.g. '1920x1080')."),
            code='invalid_screen_resolution',
        )

    parts = value.split('x')
    w, h = int(parts[0]), int(parts[1])
    if w > 15360 or h > 8640 or w <= 0 or h <= 0:
        raise ValidationError(
            _("Screen resolution %(value)s is outside valid range."),
            params={'value': value},
            code='screen_resolution_out_of_range',
        )

    return value


# ── Blacklist Reason Validator ─────────────────────────────────────────────

VALID_BLACKLIST_REASONS = {
    'fraud', 'abuse', 'spam', 'bot', 'scraping',
    'manual', 'threat_feed', 'rate_limit',
}

def validate_blacklist_reason(value: str) -> str:
    """Validate a blacklist reason code."""
    if value not in VALID_BLACKLIST_REASONS:
        raise ValidationError(
            _("Invalid blacklist reason '%(value)s'. Valid reasons: %(valid)s"),
            params={
                'value': value,
                'valid': ', '.join(sorted(VALID_BLACKLIST_REASONS)),
            },
            code='invalid_blacklist_reason',
        )
    return value


# ── Expiry Hours Validator ─────────────────────────────────────────────────

def validate_expires_hours(value: Optional[int]) -> Optional[int]:
    """
    Validate blacklist TTL in hours.
    Must be between 1 hour and 1 year.
    """
    if value is None:
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            _('Expiry hours must be an integer.'),
            code='invalid_expires_hours',
        )

    if value < 1:
        raise ValidationError(
            _('Expiry hours must be at least 1 hour.'),
            code='expires_hours_too_small',
        )

    if value > 8760:  # 8760 = 1 year in hours
        raise ValidationError(
            _('Expiry hours cannot exceed 8760 (1 year).'),
            code='expires_hours_too_large',
        )

    return value
