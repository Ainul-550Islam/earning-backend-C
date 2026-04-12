"""
validation_engines/schema_validator.py
────────────────────────────────────────
Schema-level validation for PostbackEngine payloads.
Validates complete request schemas: required fields, types, formats, business rules.
Acts as the final gate before deduplication and conversion creation.

This wraps the Pydantic schemas.py into the validation_engines layer
and adds Django-ORM-based business rule validation.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from ..exceptions import SchemaValidationException, MissingRequiredFieldsException
from ..schemas import validate_postback_payload, validate_field_mapping, validate_webhook_payload

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Centralised schema validation for all incoming data.
    Wraps Pydantic models + adds business-rule checks.
    """

    def validate_postback(
        self,
        normalised: Dict[str, Any],
        network_key: str = "",
        strict: bool = False,
    ):
        """
        Validate a normalised postback payload against Pydantic schema.
        Raises SchemaValidationException on failure.
        Returns validated Pydantic model.

        strict=True: require ALL standard fields
        strict=False: only require network-specific required fields
        """
        if strict:
            required = ["lead_id", "offer_id", "payout"]
            missing = [f for f in required if not normalised.get(f)]
            if missing:
                raise MissingRequiredFieldsException(
                    f"Strict validation: missing {missing}",
                    missing_fields=missing,
                )
        return validate_postback_payload(normalised, network_key=network_key)

    def validate_field_mapping(self, mapping: dict):
        """Validate a field_mapping JSON from AdNetworkConfig."""
        return validate_field_mapping(mapping)

    def validate_webhook_payload(self, data: dict):
        """Validate an outbound webhook payload before delivery."""
        return validate_webhook_payload(data)

    def validate_network_config(self, config: dict) -> Tuple[bool, List[str]]:
        """
        Validate an AdNetworkConfig creation/update payload.
        Returns (is_valid, errors).
        """
        errors = []

        # Required fields
        required = ["network_key", "name", "network_type"]
        for field in required:
            if not config.get(field):
                errors.append(f"'{field}' is required.")

        # network_key format
        import re
        network_key = config.get("network_key", "")
        if network_key and not re.match(r'^[a-z0-9_\-]{2,64}$', network_key):
            errors.append(
                f"network_key '{network_key}' invalid. "
                "Must be lowercase alphanumeric with hyphens/underscores, 2-64 chars."
            )

        # IP whitelist format
        ip_whitelist = config.get("ip_whitelist", [])
        if ip_whitelist:
            import ipaddress
            for entry in ip_whitelist:
                try:
                    if "/" in str(entry):
                        ipaddress.ip_network(str(entry), strict=False)
                    else:
                        ipaddress.ip_address(str(entry))
                except ValueError:
                    errors.append(f"Invalid IP/CIDR in whitelist: {entry!r}")

        # Postback URL template
        template = config.get("postback_url_template", "")
        if template:
            from .macro_validator import macro_validator
            is_valid, issues = macro_validator.validate_template(template)
            if not is_valid:
                errors.extend(issues)

        # Reward rules
        reward_rules = config.get("reward_rules", {})
        if reward_rules:
            from ..schemas import validate_reward_rule
            for key, rule in reward_rules.items():
                try:
                    validate_reward_rule(rule if isinstance(rule, dict) else {"points": rule})
                except SchemaValidationException as exc:
                    errors.append(f"reward_rules[{key!r}]: {exc}")

        # Conversion window
        window = config.get("conversion_window_hours", 720)
        if not isinstance(window, int) or window < 0 or window > 8760:
            errors.append("conversion_window_hours must be 0-8760 (0 = no limit).")

        return len(errors) == 0, errors

    def validate_payout_range(
        self,
        payout: Decimal,
        min_payout: Decimal = Decimal("0"),
        max_payout: Decimal = Decimal("1000"),
    ) -> Tuple[bool, str]:
        """Validate payout is within expected range."""
        if payout < min_payout:
            return False, f"Payout {payout} below minimum {min_payout}."
        if payout > max_payout:
            return False, f"Payout {payout} exceeds maximum {max_payout}."
        return True, ""

    def validate_conversion_data(self, data: dict) -> Tuple[bool, List[str]]:
        """
        Validate all data needed for conversion creation.
        Called just before _create_conversion().
        """
        errors = []
        if not data.get("user_id") and not data.get("user"):
            errors.append("Conversion requires a resolved user.")
        if not data.get("network_id") and not data.get("network"):
            errors.append("Conversion requires a network.")
        payout = data.get("payout", Decimal("0"))
        is_valid, msg = self.validate_payout_range(Decimal(str(payout)))
        if not is_valid:
            errors.append(msg)
        return len(errors) == 0, errors


# Module-level singleton
schema_validator = SchemaValidator()
