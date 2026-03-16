"""validators.py – Field and payload validation for the postback module."""
from django.core.exceptions import ValidationError

from .constants import (
    MAX_IP_WHITELIST_ENTRIES,
    MAX_PAYOUT_PER_POSTBACK,
    STANDARD_FIELD_LEAD_ID,
    STANDARD_FIELD_OFFER_ID,
    STANDARD_FIELD_USER_ID,
)


def validate_ip_whitelist(entries) -> None:
    """Validate a list of IP/CIDR whitelist entries."""
    from .utils.ip_checker import validate_ip_whitelist_entries
    if not isinstance(entries, list):
        raise ValidationError("IP whitelist must be a JSON array of strings.")
    if len(entries) > MAX_IP_WHITELIST_ENTRIES:
        raise ValidationError(
            f"IP whitelist cannot exceed {MAX_IP_WHITELIST_ENTRIES} entries."
        )
    errors = validate_ip_whitelist_entries(entries)
    if errors:
        raise ValidationError(f"Invalid whitelist entries: {'; '.join(errors)}")


def validate_field_mapping(mapping: dict) -> None:
    """
    Validate a network field-mapping dict.
    Must be a dict of {standard_field: network_field} string pairs.
    """
    if not isinstance(mapping, dict):
        raise ValidationError("Field mapping must be a JSON object.")
    for k, v in mapping.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValidationError(
                f"All field mapping keys and values must be strings. "
                f"Got key={k!r} value={v!r}."
            )
        if not k.strip() or not v.strip():
            raise ValidationError("Field mapping keys and values cannot be blank.")


def validate_payout_not_exceeds_cap(payout: float) -> None:
    if payout > MAX_PAYOUT_PER_POSTBACK:
        raise ValidationError(
            f"Payout of {payout} exceeds the maximum allowed per postback "
            f"({MAX_PAYOUT_PER_POSTBACK})."
        )


def validate_required_postback_fields(payload: dict, required_fields: list) -> list:
    """
    Check that all required_fields are present and non-empty in payload.
    Returns a list of missing field names.
    """
    missing = []
    for field in required_fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def validate_network_key_format(key: str) -> None:
    """Network keys must be alphanumeric + underscores/hyphens, 8-64 chars."""
    import re
    if not key:
        raise ValidationError("Network key cannot be empty.")
    if not re.fullmatch(r"[a-zA-Z0-9_\-]{8,64}", key):
        raise ValidationError(
            "Network key must be 8-64 characters and contain only "
            "letters, digits, underscores, and hyphens."
        )


def validate_reward_rules(rules: dict) -> None:
    """
    Validate the JSON reward_rules field on a NetworkPostbackConfig.
    Expected schema:
    {
        "offer_id": { "points": 100, "item_id": "<uuid>" },
        ...
    }
    """
    if not isinstance(rules, dict):
        raise ValidationError("Reward rules must be a JSON object.")
    for offer_id, rule in rules.items():
        if not isinstance(rule, dict):
            raise ValidationError(
                f"Rule for offer '{offer_id}' must be a JSON object."
            )
        points = rule.get("points")
        if points is not None:
            if not isinstance(points, int) or points < 0:
                raise ValidationError(
                    f"Rule for offer '{offer_id}': 'points' must be a non-negative integer."
                )
