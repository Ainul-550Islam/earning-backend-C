# api/wallet/interactors.py
"""
Interactors — Clean Architecture application services.
Thin wrappers that coordinate use_cases + return HTTP-ready responses.

Interactors = Use Cases + HTTP response formatting.
Views call interactors. Interactors call use cases.

Usage:
    result = WalletInteractor.credit(request.user, amount=500, source_type="task")
    return Response(result)
"""
import logging
from decimal import Decimal
from rest_framework import status

logger = logging.getLogger("wallet.interactors")


class WalletInteractor:
    """High-level wallet operations returning HTTP-ready dicts."""

    @staticmethod
    def get_wallet(user) -> dict:
        """GET wallet for user."""
        from .selectors import wallet_get_for_user, wallet_balance_summary
        wallet = wallet_get_for_user(user=user)
        if not wallet:
            wallet, _ = __import__(
                "api.wallet.services.core.WalletService", fromlist=["WalletService"]
            ).WalletService.get_or_create(user)
        return {
            "success": True,
            "data": wallet_balance_summary(wallet=wallet),
        }

    @staticmethod
    def credit(user, *, amount: Decimal, source_type: str,
                source_id: str = "", idempotency_key: str = "",
                country_code: str = "BD") -> dict:
        """Credit a user's wallet."""
        from .use_cases import CreditWalletUseCase, CreditInput
        from .selectors import wallet_get_for_user

        wallet = wallet_get_for_user(user=user)
        if not wallet:
            return {"success": False, "error": "Wallet not found", "status_code": 404}

        uc = CreditWalletUseCase(inp=CreditInput(
            wallet_id=wallet.id,
            amount=Decimal(str(amount)),
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            country_code=country_code,
        ))
        out = uc.execute()
        return {
            "success":    out.success,
            "txn_id":     out.txn_id,
            "amount":     str(out.amount_credited),
            "balance":    str(out.balance_after),
            "error":      out.error,
            "status_code":200 if out.success else 400,
        }

    @staticmethod
    def withdraw(user, *, amount: Decimal, payment_method_id: int,
                  note: str = "", idempotency_key: str = "",
                  ip_address: str = "") -> dict:
        """Request a withdrawal."""
        from .use_cases import RequestWithdrawalUseCase, WithdrawalInput
        from .selectors import wallet_get_for_user

        wallet = wallet_get_for_user(user=user)
        if not wallet:
            return {"success": False, "error": "Wallet not found", "status_code": 404}

        uc = RequestWithdrawalUseCase(inp=WithdrawalInput(
            user_id=user.id,
            wallet_id=wallet.id,
            payment_method_id=payment_method_id,
            amount=Decimal(str(amount)),
            note=note,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
        ))
        out = uc.execute()
        return {
            "success":       out.success,
            "withdrawal_id": out.withdrawal_id,
            "amount":        str(out.amount),
            "fee":           str(out.fee),
            "net_amount":    str(out.net_amount),
            "status":        out.status,
            "error":         out.error,
            "status_code":   201 if out.success else 400,
        }

    @staticmethod
    def transfer(from_user, *, to_username: str, amount: Decimal, note: str = "") -> dict:
        """Transfer funds to another user."""
        from .use_cases import TransferFundsUseCase, TransferInput

        uc = TransferFundsUseCase(inp=TransferInput(
            from_user_id=from_user.id,
            to_username=to_username,
            amount=Decimal(str(amount)),
            note=note,
        ))
        out = uc.execute()
        return {
            "success":     out.success,
            "amount":      str(out.amount),
            "error":       out.error,
            "status_code": 200 if out.success else 400,
        }


class WithdrawalInteractor:
    """Admin withdrawal operations."""

    @staticmethod
    def approve(*, withdrawal_id: str, admin_user) -> dict:
        from .use_cases import ApproveWithdrawalUseCase
        uc = ApproveWithdrawalUseCase(
            withdrawal_id=withdrawal_id, admin_user=admin_user
        )
        return uc.execute()

    @staticmethod
    def reject(*, withdrawal_id: str, reason: str, admin_user) -> dict:
        from .selectors import withdrawal_get
        from .services.withdrawal.WithdrawalService import WithdrawalService
        wr = withdrawal_get(withdrawal_id=withdrawal_id)
        if not wr:
            return {"success": False, "error": "Not found"}
        try:
            WithdrawalService.reject(wr, reason=reason, by=admin_user)
            return {"success": True, "status": wr.status}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def complete(*, withdrawal_id: str, gateway_ref: str) -> dict:
        from .selectors import withdrawal_get
        from .services.withdrawal.WithdrawalService import WithdrawalService
        wr = withdrawal_get(withdrawal_id=withdrawal_id)
        if not wr:
            return {"success": False, "error": "Not found"}
        try:
            WithdrawalService.complete(wr, gateway_ref=gateway_ref)
            return {"success": True, "status": wr.status}
        except Exception as e:
            return {"success": False, "error": str(e)}
