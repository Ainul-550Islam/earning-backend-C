"""
Fee Calculator — Computes payout fees per gateway.

All amounts are Decimal. Never float.
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

from ..choices import PaymentGateway, FeeType
from ..constants import (
    DEFAULT_BKASH_FEE_PERCENT,
    DEFAULT_NAGAD_FEE_PERCENT,
    DEFAULT_ROCKET_FEE_PERCENT,
    DEFAULT_BANK_FLAT_FEE,
    MAX_FEE_AMOUNT,
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
)
from ..exceptions import FeeCalculationError

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


class FeeConfig:
    """
    Holds fee configuration for a single gateway.
    Supports FLAT, PERCENTAGE, and TIERED fee types.
    """

    def __init__(
        self,
        fee_type: str,
        flat_fee: Decimal = Decimal("0.00"),
        percent: Decimal = Decimal("0.00"),
        tiers: Optional[list[dict]] = None,
        max_fee: Decimal = MAX_FEE_AMOUNT,
        min_fee: Decimal = Decimal("0.00"),
    ) -> None:
        if fee_type not in FeeType.values:
            raise FeeCalculationError(
                f"Invalid fee_type '{fee_type}'. Valid: {FeeType.values}"
            )
        if not isinstance(flat_fee, Decimal) or not isinstance(percent, Decimal):
            raise FeeCalculationError("flat_fee and percent must be Decimal instances.")
        if percent < Decimal("0") or percent > Decimal("100"):
            raise FeeCalculationError("percent must be between 0 and 100.")
        if flat_fee < Decimal("0"):
            raise FeeCalculationError("flat_fee must not be negative.")

        self.fee_type = fee_type
        self.flat_fee = flat_fee
        self.percent = percent
        self.tiers = tiers or []
        self.max_fee = max_fee
        self.min_fee = min_fee

    def compute(self, gross_amount: Decimal) -> Decimal:
        """
        Compute the fee for a given gross_amount.

        Args:
            gross_amount: Pre-fee payout amount (Decimal).

        Returns:
            Fee amount (Decimal, rounded to 2dp, capped at max_fee).

        Raises:
            FeeCalculationError: On invalid input.
        """
        if not isinstance(gross_amount, Decimal):
            try:
                gross_amount = Decimal(str(gross_amount))
            except InvalidOperation as exc:
                raise FeeCalculationError(
                    f"Cannot convert gross_amount to Decimal: {exc}"
                ) from exc

        if gross_amount < Decimal("0"):
            raise FeeCalculationError(
                f"gross_amount must not be negative, got {gross_amount}."
            )

        if self.fee_type == FeeType.FLAT:
            fee = self.flat_fee

        elif self.fee_type == FeeType.PERCENTAGE:
            fee = (gross_amount * self.percent / Decimal("100")).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )

        elif self.fee_type == FeeType.TIERED:
            fee = self._compute_tiered(gross_amount)

        else:
            raise FeeCalculationError(
                f"Unhandled fee_type '{self.fee_type}'."
            )

        # Apply min/max caps
        fee = max(self.min_fee, fee)
        fee = min(self.max_fee, fee)
        fee = fee.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        logger.debug(
            "FeeConfig.compute: gross=%s type=%s fee=%s", gross_amount, self.fee_type, fee
        )
        return fee

    def _compute_tiered(self, gross_amount: Decimal) -> Decimal:
        """
        Compute tiered fee. Each tier dict: {min, max, percent, flat}.
        The first matching tier is used.
        """
        if not self.tiers:
            raise FeeCalculationError("TIERED fee_type requires at least one tier.")

        for tier in self.tiers:
            tier_min = Decimal(str(tier.get("min", "0")))
            tier_max = tier.get("max")
            tier_max = Decimal(str(tier_max)) if tier_max is not None else None

            in_range = gross_amount >= tier_min and (
                tier_max is None or gross_amount <= tier_max
            )
            if in_range:
                tier_percent = Decimal(str(tier.get("percent", "0")))
                tier_flat = Decimal(str(tier.get("flat", "0")))
                fee = (
                    (gross_amount * tier_percent / Decimal("100")) + tier_flat
                ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
                return fee

        raise FeeCalculationError(
            f"No matching tier found for gross_amount={gross_amount}."
        )


# ---------------------------------------------------------------------------
# Default Gateway Configs
# ---------------------------------------------------------------------------

DEFAULT_FEE_CONFIGS: dict[str, FeeConfig] = {
    PaymentGateway.BKASH: FeeConfig(
        fee_type=FeeType.PERCENTAGE,
        percent=DEFAULT_BKASH_FEE_PERCENT,
        max_fee=MAX_FEE_AMOUNT,
    ),
    PaymentGateway.NAGAD: FeeConfig(
        fee_type=FeeType.PERCENTAGE,
        percent=DEFAULT_NAGAD_FEE_PERCENT,
        max_fee=MAX_FEE_AMOUNT,
    ),
    PaymentGateway.ROCKET: FeeConfig(
        fee_type=FeeType.PERCENTAGE,
        percent=DEFAULT_ROCKET_FEE_PERCENT,
        max_fee=MAX_FEE_AMOUNT,
    ),
    PaymentGateway.BANK: FeeConfig(
        fee_type=FeeType.FLAT,
        flat_fee=DEFAULT_BANK_FLAT_FEE,
        max_fee=MAX_FEE_AMOUNT,
    ),
    PaymentGateway.MANUAL: FeeConfig(
        fee_type=FeeType.FLAT,
        flat_fee=Decimal("0.00"),
        max_fee=Decimal("0.00"),
    ),
}


class FeeCalculator:
    """
    Main entry point for fee calculation.

    Usage:
        calculator = FeeCalculator()
        result = calculator.calculate(gateway="BKASH", gross_amount=Decimal("1000.00"))
        # result = {"gross": 1000.00, "fee": 18.50, "net": 981.50}
    """

    def __init__(self, configs: Optional[dict[str, FeeConfig]] = None) -> None:
        self._configs = configs or DEFAULT_FEE_CONFIGS

    def calculate(self, *, gateway: str, gross_amount: Decimal) -> dict:
        """
        Calculate fee and net amount for a payout.

        Args:
            gateway:      PaymentGateway choice string.
            gross_amount: Pre-fee amount (Decimal).

        Returns:
            Dict: {"gross": Decimal, "fee": Decimal, "net": Decimal}

        Raises:
            FeeCalculationError: On unsupported gateway or invalid amount.
        """
        if not gateway or gateway not in PaymentGateway.values:
            raise FeeCalculationError(
                f"Unsupported gateway '{gateway}'. Valid: {PaymentGateway.values}"
            )

        if not isinstance(gross_amount, Decimal):
            try:
                gross_amount = Decimal(str(gross_amount))
            except InvalidOperation as exc:
                raise FeeCalculationError(str(exc)) from exc

        if gross_amount < MIN_PAYOUT_AMOUNT:
            raise FeeCalculationError(
                f"gross_amount {gross_amount} is below minimum {MIN_PAYOUT_AMOUNT}."
            )
        if gross_amount > MAX_PAYOUT_AMOUNT:
            raise FeeCalculationError(
                f"gross_amount {gross_amount} exceeds maximum {MAX_PAYOUT_AMOUNT}."
            )

        config = self._configs.get(gateway)
        if config is None:
            raise FeeCalculationError(
                f"No fee config for gateway '{gateway}'."
            )

        fee = config.compute(gross_amount)
        net = (gross_amount - fee).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        if net < Decimal("0.00"):
            raise FeeCalculationError(
                f"Net amount {net} is negative after fee {fee} for gross {gross_amount}."
            )

        result = {
            "gross": gross_amount,
            "fee": fee,
            "net": net,
            "gateway": gateway,
        }
        logger.debug("FeeCalculator.calculate: %s", result)
        return result

    def get_fee_summary(self, *, gateway: str) -> dict:
        """Return a human-readable fee summary for a gateway."""
        config = self._configs.get(gateway)
        if not config:
            return {"gateway": gateway, "description": "Unknown"}
        return {
            "gateway": gateway,
            "fee_type": config.fee_type,
            "flat_fee": str(config.flat_fee),
            "percent": str(config.percent),
            "max_fee": str(config.max_fee),
        }
