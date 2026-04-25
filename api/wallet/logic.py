# api/wallet/logic.py
"""
Business logic layer — thin orchestration on top of services.
Views call logic.py → logic.py calls services → services call models.

This keeps views thin and services pure/testable.
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("wallet.logic")


class WalletLogic:
    """High-level wallet operations — orchestrates services + hooks + events."""

    @staticmethod
    def credit_from_earning(user_id: int, amount: Decimal, source_type: str,
                             source_id: str = "", country_code: str = "BD",
                             idempotency_key: str = "") -> dict:
        """
        Credit wallet from an earning event.
        Pipeline: validate → cap check → geo rate → tier bonus → credit → hooks → events
        """
        from .services.core.WalletService import WalletService
        from .services.earning.EarningCapService import EarningCapService
        from .services.cpalead.CPALeadService import CPALeadService
        from .hooks import wallet_hooks
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user   = User.objects.get(id=user_id)
        wallet = WalletService.get_or_create(user)

        # 1. Cap check
        allowed, remaining = EarningCapService.check(wallet, amount, source_type)
        if not allowed:
            return {"success": False, "error": "Daily earning cap reached", "remaining": float(remaining)}

        # 2. Apply GEO + tier multipliers
        geo_mult  = CPALeadService.get_geo_rate(country_code)
        tier_mult = CPALeadService.get_tier_multiplier(user)
        final     = (amount * geo_mult * tier_mult).quantize(Decimal("0.00000001"))

        # 3. Pre-hooks
        wallet_hooks.run_before("credit", wallet=wallet, amount=final, source_type=source_type)

        # 4. Credit
        txn = WalletService.credit(wallet, final, txn_type=source_type,
                                    description=f"Earning: {source_type} {source_id}",
                                    idempotency_key=idempotency_key,
                                    country_code=country_code)

        # 5. Post-hooks
        wallet_hooks.run_after("credit", wallet=wallet, amount=final, txn=txn)

        return {
            "success":        True,
            "txn_id":         str(txn.txn_id),
            "amount_credited": float(final),
            "original_amount": float(amount),
            "geo_multiplier":  float(geo_mult),
            "tier_multiplier": float(tier_mult),
            "balance_after":   float(txn.balance_after or 0),
        }

    @staticmethod
    def request_withdrawal(user_id: int, amount: Decimal, payment_method_id: int,
                            note: str = "", idempotency_key: str = "",
                            ip_address: str = "") -> dict:
        """
        Create withdrawal request.
        Pipeline: KYC check → fraud check → limit check → fee calc → create
        """
        from .services.core.WalletService import WalletService
        from .services.withdrawal.WithdrawalService import WithdrawalService
        from .services.withdrawal.WithdrawalLimitService import WithdrawalLimitService
        from .models.withdrawal import WithdrawalMethod
        from .hooks import wallet_hooks
        from django.contrib.auth import get_user_model

        user   = get_user_model().objects.get(id=user_id)
        wallet = WalletService.get_or_create(user)

        # KYC check
        from .services_extra import FraudDetectionService
        fraud = FraudDetectionService.assess_withdrawal_risk(user, wallet, amount)
        if not fraud["allowed"]:
            return {"success": False, "error": fraud["reason"]}

        # Limit check
        try:
            pm = WithdrawalMethod.objects.get(id=payment_method_id, user=user)
            WithdrawalLimitService.validate(wallet, amount, pm.method_type)
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Pre-hooks
        wallet_hooks.run_before("withdrawal", wallet=wallet, amount=amount)

        # Create
        wr = WithdrawalService.create(
            wallet=wallet, amount=amount, payment_method=pm,
            created_by=user, ip_address=ip_address,
            idempotency_key=idempotency_key, note=note,
        )

        # Post-hooks
        wallet_hooks.run_after("withdrawal", wallet=wallet, amount=amount, withdrawal=wr)

        return {
            "success":       True,
            "withdrawal_id": str(wr.withdrawal_id),
            "amount":        float(wr.amount),
            "fee":           float(wr.fee),
            "net_amount":    float(wr.net_amount),
            "status":        wr.status,
        }
