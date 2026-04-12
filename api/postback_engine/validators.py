"""
validators.py – Django model-level field validators for Postback Engine.
"""
import ipaddress
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_network_key_format(value: str):
    """Validate network_key is a URL-safe lowercase slug."""
    if not re.match(r'^[a-z0-9_-]{2,64}$', value):
        raise ValidationError(
            _("Network key must be lowercase alphanumeric with hyphens/underscores, 2–64 chars."),
            code="invalid_network_key",
        )


def validate_ip_whitelist(value):
    """Validate that ip_whitelist contains valid IPs and CIDRs."""
    if not isinstance(value, list):
        raise ValidationError(_("IP whitelist must be a list."))
    for entry in value:
        try:
            if "/" in str(entry):
                ipaddress.ip_network(str(entry), strict=False)
            else:
                ipaddress.ip_address(str(entry))
        except ValueError:
            raise ValidationError(
                _(f"Invalid IP/CIDR in whitelist: {entry!r}")
            )


def validate_field_mapping(value):
    """Validate field_mapping is a flat string→string dict."""
    if not isinstance(value, dict):
        raise ValidationError(_("Field mapping must be a dict."))
    for k, v in value.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValidationError(
                _("All field mapping keys and values must be strings.")
            )


def validate_reward_rules(value):
    """Validate reward_rules structure."""
    if not isinstance(value, dict):
        raise ValidationError(_("Reward rules must be a dict."))
    for offer_id, rule in value.items():
        if not isinstance(rule, dict):
            raise ValidationError(
                _(f"Reward rule for offer {offer_id!r} must be a dict.")
            )
        if "points" in rule and not isinstance(rule["points"], (int, float)):
            raise ValidationError(
                _(f"'points' in reward rule for {offer_id!r} must be a number.")
            )


def validate_required_postback_fields(
    required_fields: list,
    payload: dict,
    field_mapping: dict = None,
) -> list:
    """
    Validate that all required fields are present in the payload.
    Returns list of missing field names (empty = all present).
    """
    mapping = field_mapping or {}
    missing = []
    for field in required_fields:
        mapped = mapping.get(field, field)
        if not payload.get(mapped):
            missing.append(field)
    return missing
