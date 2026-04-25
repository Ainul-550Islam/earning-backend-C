# api/wallet/services/withdrawal/WithdrawalFeeService.py
"""
Calculate withdrawal fees per gateway and user tier.
Falls back to default constants when no DB row found.
"""
import logging
from decimal import Decimal

from ...models import WithdrawalFee
from ...constants import DEFAULT_FEE_PERCENT, TIER_FEE_DISCOUNT, GATEWAY_MIN

logger = logging.getLogger("wallet.service.withdrawal_fee")


class WithdrawalFeeService:

    @staticmethod
    def calculate(amount: Decimal, gateway: str, user) -> Decimal:
        """
        Calculate the fee for a withdrawal.
        Priority:
          1. DB row matching (gateway, user tier)
          2. DB row matching (gateway, ALL)
          3. Default: 2% with tier discount
        """
        amount = Decimal(str(amount))
        tier   = getattr(user, "tier", "FREE")

        # Try DB-configured fee first
        fee_config = (
            WithdrawalFee.objects.filter(gateway=gateway, tier=tier, is_active=True).first()
            or WithdrawalFee.objects.filter(gateway=gateway, tier="ALL", is_active=True).first()
        )

        if fee_config:
            fee = fee_config.calculate(amount)
        else:
            # Default: 2% with tier discount
            discount = TIER_FEE_DISCOUNT.get(tier, Decimal("1.00"))
            fee = (amount * DEFAULT_FEE_PERCENT / 100 * discount).quantize(Decimal("0.01"))
            min_fee = GATEWAY_MIN.get(gateway, Decimal("5"))
            fee = max(fee, Decimal("5"))  # minimum 5 BDT always

        # DIAMOND tier = 0 fee
        if tier == "DIAMOND":
            fee = Decimal("0")

        logger.debug(f"Fee: amount={amount} gateway={gateway} tier={tier} fee={fee}")
        return fee

    @staticmethod
    def get_fee_breakdown(amount: Decimal, gateway: str, user) -> dict:
        """Return full fee breakdown for display in UI before submission."""
        fee = WithdrawalFeeService.calculate(amount, gateway, user)
        net = amount - fee
        return {
            "amount":      float(amount),
            "fee":         float(fee),
            "net_amount":  float(net),
            "fee_percent": float(fee / amount * 100) if amount > 0 else 0,
            "gateway":     gateway,
            "tier":        getattr(user, "tier", "FREE"),
        }
