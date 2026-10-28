# api/cms/validator.py
"""CMS-specific validation functions."""
import re
from decimal import Decimal
from typing import Optional, Tuple


def validate_subid(subid: str) -> Tuple[bool, str]:
    if not subid:
        return False, "subid is required"
    if not re.match(r'^[a-zA-Z0-9_\-]{1,100}$', subid):
        return False, "subid contains invalid characters"
    return True, ""


def validate_payout(payout_str: str, max_usd: float = 100.0) -> Tuple[bool, Optional[Decimal]]:
    try:
        amount = Decimal(str(payout_str))
        if amount <= 0:
            return False, None
        if float(amount) > max_usd:
            return False, None
        return True, amount
    except Exception:
        return False, None


def validate_lead_id(lead_id: str) -> bool:
    return bool(lead_id and len(lead_id) <= 200)


def validate_coin_amount(amount, min_val: float = 0, max_val: float = 1_000_000) -> bool:
    try:
        v = float(amount)
        return min_val < v <= max_val
    except Exception:
        return False


def validate_color_hex(color: str) -> bool:
    return bool(re.match(r'^#[0-9a-fA-F]{3,6}$', color))


def validate_url(url: str) -> bool:
    return bool(re.match(r'^https?://.+', url))


def validate_slug(slug: str) -> bool:
    return bool(re.match(r'^[a-z0-9\-]+$', slug))


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def validate_ip_address(ip: str) -> bool:
    ipv4 = r'^(\d{1,3}\.){3}\d{1,3}$'
    ipv6 = r'^[0-9a-fA-F:]+$'
    return bool(re.match(ipv4, ip) or re.match(ipv6, ip))


def validate_cpalead_postback(data: dict) -> Tuple[bool, list]:
    errors = []
    subid_ok, subid_err = validate_subid(data.get('subid', ''))
    if not subid_ok:
        errors.append(f"subid: {subid_err}")
    if not validate_lead_id(data.get('lead_id', '')):
        errors.append("lead_id: required, max 200 chars")
    payout_ok, _ = validate_payout(data.get('payout', '0'))
    if not payout_ok:
        errors.append("payout: must be a positive number <= $100")
    return len(errors) == 0, errors
