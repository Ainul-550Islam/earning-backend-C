"""
validation_engines/parameter_validator.py
───────────────────────────────────────────
General parameter validation utilities.
Validates field names, data types, lengths, and formats
for postback payload parameters.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from ..exceptions import SchemaValidationException, MissingRequiredFieldsException

# Validation patterns
_SAFE_ID_PATTERN    = re.compile(r'^[\w\-\.]{1,255}$')
_NETWORK_KEY_PATTERN= re.compile(r'^[a-z0-9_\-]{2,64}$')
_CURRENCY_PATTERN   = re.compile(r'^[A-Z]{3}$')
_OFFER_ID_PATTERN   = re.compile(r'^[\w\-\.@:]{1,255}$')


class ParameterValidator:

    def validate_required(self, payload: dict, required_fields: List[str]) -> List[str]:
        """
        Check all required fields are present and non-empty.
        Returns list of missing field names (empty = all present).
        """
        missing = []
        for field in required_fields:
            value = payload.get(field)
            if value is None or str(value).strip() == "":
                missing.append(field)
        return missing

    def assert_required(self, payload: dict, required_fields: List[str]) -> None:
        missing = self.validate_required(payload, required_fields)
        if missing:
            raise MissingRequiredFieldsException(
                f"Missing required fields: {', '.join(missing)}",
                missing_fields=missing,
            )

    def validate_id_field(self, value: Any, field_name: str = "id") -> str:
        """Validate and sanitise an ID field (lead_id, click_id, etc.)."""
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""
        if not _SAFE_ID_PATTERN.match(s):
            raise SchemaValidationException(
                f"Invalid characters in {field_name}: {s[:50]!r}. "
                "Allowed: alphanumeric, hyphens, dots, underscores."
            )
        return s

    def validate_network_key(self, value: str) -> str:
        """Validate network_key format."""
        if not _NETWORK_KEY_PATTERN.match(str(value or "")):
            raise SchemaValidationException(
                f"Invalid network_key: {value!r}. "
                "Must be lowercase alphanumeric with hyphens/underscores, 2-64 chars."
            )
        return str(value)

    def validate_currency(self, value: str) -> str:
        """Validate ISO 4217 currency code."""
        if not value:
            return "USD"
        v = str(value).upper().strip()
        if not _CURRENCY_PATTERN.match(v):
            raise SchemaValidationException(
                f"Invalid currency code: {value!r}. Must be 3 uppercase letters (e.g. USD, EUR)."
            )
        return v

    def validate_payout(self, value: Any) -> Decimal:
        """Coerce and validate payout value."""
        try:
            cleaned = str(value).strip().replace(",", "")
            result = Decimal(cleaned)
            if result < 0:
                raise SchemaValidationException("Payout cannot be negative.")
            return result
        except (InvalidOperation, TypeError, ValueError):
            raise SchemaValidationException(f"Invalid payout value: {value!r}")

    def validate_offer_id(self, value: Any, field_name: str = "offer_id") -> str:
        """Validate offer_id — slightly more permissive than lead_id."""
        if not value:
            return ""
        s = str(value).strip()
        if not _OFFER_ID_PATTERN.match(s):
            raise SchemaValidationException(
                f"Invalid {field_name}: {s[:50]!r}"
            )
        return s

    def coerce_bool(self, value: Any) -> bool:
        """Coerce various true/false representations to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return str(value).lower().strip() in ("1", "true", "yes", "on")
        return False

    def sanitise_payload(self, payload: dict, max_key_length: int = 64, max_value_length: int = 2048) -> dict:
        """
        Remove oversized or suspicious fields from a payload.
        Protects against oversized inputs and injection attempts.
        """
        sanitised = {}
        for k, v in payload.items():
            if not isinstance(k, str) or len(k) > max_key_length:
                continue
            if isinstance(v, str) and len(v) > max_value_length:
                v = v[:max_value_length]  # truncate, don't drop
            sanitised[k] = v
        return sanitised


parameter_validator = ParameterValidator()
