"""
validation_engines/request_validator.py – Request validation pipeline.
"""
import ipaddress
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from ..exceptions import (
    IPNotWhitelistedException,
    InvalidSignatureException,
    MissingRequiredFieldsException,
    SchemaValidationException,
)

logger = logging.getLogger(__name__)


class RequestValidator:
    """
    Stateless request validation utilities.
    Each method raises an appropriate exception on failure.
    """

    def validate_ip_whitelist(self, source_ip: str, whitelist: list) -> bool:
        """
        Check if source_ip is within the allowed whitelist.
        Supports both exact IPs and CIDR ranges.
        """
        if not whitelist:
            return True  # empty whitelist = allow all
        if not source_ip:
            raise IPNotWhitelistedException("No source IP provided.")
        try:
            ip_obj = ipaddress.ip_address(source_ip)
            for entry in whitelist:
                if "/" in str(entry):
                    network = ipaddress.ip_network(str(entry), strict=False)
                    if ip_obj in network:
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(str(entry)):
                        return True
        except ValueError as exc:
            raise IPNotWhitelistedException(f"IP validation error: {exc}")
        raise IPNotWhitelistedException(
            f"IP {source_ip} not in whitelist."
        )

    def validate_required_fields(
        self, payload: dict, required_fields: list, field_mapping: dict = None
    ) -> bool:
        """
        Check all required fields are present in payload.
        Uses field_mapping to look up network-specific param names.
        """
        missing = []
        mapping = field_mapping or {}
        for field in required_fields:
            mapped = mapping.get(field, field)
            if not payload.get(mapped):
                missing.append(field)
        if missing:
            raise MissingRequiredFieldsException(
                f"Missing required fields: {', '.join(missing)}",
                missing_fields=missing,
            )
        return True

    def validate_payout(self, payout_raw) -> Decimal:
        """Parse and validate payout value."""
        try:
            value = Decimal(str(payout_raw))
            if value < 0:
                raise SchemaValidationException("Payout cannot be negative.")
            return value
        except (InvalidOperation, TypeError):
            raise SchemaValidationException(
                f"Invalid payout value: {payout_raw!r}"
            )

    def validate_timestamp(
        self, timestamp_str: str, tolerance_seconds: int = 300
    ) -> float:
        """
        Validate that timestamp is within the allowed replay window.
        Returns the timestamp as float.
        """
        from django.utils import timezone
        try:
            ts = float(timestamp_str)
        except (ValueError, TypeError):
            raise InvalidSignatureException("Invalid timestamp format.")

        age = abs(timezone.now().timestamp() - ts)
        if age > tolerance_seconds:
            raise InvalidSignatureException(
                f"Timestamp is {age:.0f}s old (max {tolerance_seconds}s)."
            )
        return ts

    def validate_network_key_format(self, network_key: str) -> bool:
        """Validate network_key is a valid URL-safe slug."""
        pattern = r'^[a-z0-9_-]{2,64}$'
        if not re.match(pattern, network_key):
            raise SchemaValidationException(
                f"Invalid network_key format: {network_key!r}. "
                "Must be lowercase alphanumeric with hyphens/underscores, 2-64 chars."
            )
        return True

    def validate_ip_format(self, ip: str) -> bool:
        """Validate IP address format (IPv4 or IPv6)."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            raise SchemaValidationException(f"Invalid IP address: {ip!r}")

    def validate_currency_code(self, currency: str) -> bool:
        """Validate 3-letter ISO 4217 currency code."""
        if not currency:
            return True
        if not re.match(r'^[A-Z]{3}$', currency.upper()):
            raise SchemaValidationException(
                f"Invalid currency code: {currency!r}. Must be 3 uppercase letters."
            )
        return True


# Module-level singleton
request_validator = RequestValidator()
