"""
validation_engines/amount_validator.py
────────────────────────────────────────
Payout amount validation and sanitisation.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from ..exceptions import PayoutLimitExceededException, SchemaValidationException
from ..constants import MAX_PAYOUT_USD_PER_CONVERSION


class AmountValidator:

    def parse_and_validate(
        self,
        raw_value,
        max_value: Decimal = None,
        min_value: Decimal = Decimal("0"),
    ) -> Decimal:
        try:
            cleaned = str(raw_value).strip().replace(",", "")
            value = Decimal(cleaned)
        except (InvalidOperation, TypeError, ValueError):
            raise SchemaValidationException(f"Invalid payout value: {raw_value!r}")

        if value < min_value:
            raise SchemaValidationException(f"Payout {value} cannot be negative.")

        cap = max_value or Decimal(str(MAX_PAYOUT_USD_PER_CONVERSION))
        if value > cap:
            raise PayoutLimitExceededException(
                f"Payout {value} exceeds cap {cap}.",
                payout=value, limit=cap,
            )
        return value

    def is_valid(self, raw_value) -> bool:
        try:
            v = Decimal(str(raw_value).strip().replace(",", ""))
            return v >= 0
        except Exception:
            return False


amount_validator = AmountValidator()
