"""
validation_engines/timestamp_validator.py
───────────────────────────────────────────
Timestamp validation for replay attack prevention.
"""
from __future__ import annotations
from django.utils import timezone
from ..exceptions import SignatureExpiredException, InvalidSignatureException
from ..constants import SIGNATURE_TOLERANCE_SECONDS


class TimestampValidator:

    def validate(self, timestamp_str: str, tolerance: int = None) -> float:
        """
        Validate that a Unix timestamp is within the allowed window.
        Raises SignatureExpiredException or InvalidSignatureException.
        Returns the timestamp as float on success.
        """
        tol = tolerance or SIGNATURE_TOLERANCE_SECONDS
        if not timestamp_str:
            return 0.0
        try:
            ts = float(str(timestamp_str).strip())
        except (ValueError, TypeError):
            raise InvalidSignatureException(f"Invalid timestamp format: {timestamp_str!r}")

        age = abs(timezone.now().timestamp() - ts)
        if age > tol:
            raise SignatureExpiredException(
                f"Timestamp is {age:.0f}s old (max {tol}s). Possible replay attack."
            )
        return ts

    def is_valid(self, timestamp_str: str, tolerance: int = None) -> bool:
        try:
            self.validate(timestamp_str, tolerance)
            return True
        except Exception:
            return False

    def is_too_old(self, timestamp_str: str, max_age_seconds: int) -> bool:
        try:
            ts = float(str(timestamp_str).strip())
            return abs(timezone.now().timestamp() - ts) > max_age_seconds
        except Exception:
            return True

    def current_timestamp(self) -> str:
        return str(int(timezone.now().timestamp()))


timestamp_validator = TimestampValidator()
