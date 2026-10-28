"""
NEW FILE — Centralized validation logic.

DRY FIX: `validate_flag_name` and `validate_rollout_percentage` already
existed in utils.py, but were FLOATING CODE — written, unit-testable, but
never called from any serializer or service, so invalid data could still
reach the database through the API. This module re-exports the same
checks as a single `FlagValidator` class and IS wired into the serializers
(see serializers/feature_flag_serializer.py and flag_variant_serializer.py).
"""
import re
from typing import Any


class FlagValidator:
    """Stateless validators for feature-flag-related fields."""

    NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_:-]+$')
    MAX_NAME_LENGTH = 255

    @classmethod
    def validate_name(cls, name: str) -> bool:
        """A flag/variant name must be non-empty, <=255 chars, and contain
        only letters, numbers, hyphens, underscores, or colons (no spaces)."""
        if not name or not isinstance(name, str):
            return False
        if len(name) > cls.MAX_NAME_LENGTH:
            return False
        return bool(cls.NAME_PATTERN.match(name))

    @staticmethod
    def validate_rollout_percentage(percentage: Any) -> bool:
        """Rollout percentage must be an int in [0, 100]."""
        if isinstance(percentage, bool):
            return False
        if not isinstance(percentage, int):
            return False
        return 0 <= percentage <= 100

    @staticmethod
    def validate_weight(weight: Any) -> bool:
        """Variant weight must be an int in [0, 100]."""
        if isinstance(weight, bool):
            return False
        if not isinstance(weight, int):
            return False
        return 0 <= weight <= 100

    @staticmethod
    def validate_date_range(start_date, end_date) -> bool:
        """If both dates are present, end must be strictly after start."""
        if start_date and end_date:
            return end_date > start_date
        return True

    @staticmethod
    def validate_sample_size(sample_size: Any) -> bool:
        """Sample size must be a positive integer."""
        return isinstance(sample_size, int) and sample_size > 0
