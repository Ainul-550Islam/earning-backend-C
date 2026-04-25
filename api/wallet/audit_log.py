# api/wallet/audit_log.py
"""
Immutable audit trail for all wallet admin actions.
Every admin operation is logged here: balance adjustments,
KYC approvals, wallet locks, fee changes, etc.

The audit log is IMMUTABLE — records are never updated or deleted.
"""
import logging
import json
from decimal import Decimal
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger("wallet.audit")


class AuditLogger:
    """
    Log all admin and system actions on wallets.
    Writes to AuditLog model + Python logger.
    """

    @staticmethod
    def log(
        action: str,
        user_id: int,
        target_id: int = None,
        target_type: str = "wallet",
        detail: str = "",
        before: dict = None,
        after: dict = None,
        ip_address: str = "",
        metadata: dict = None,
    ) -> None:
        """
        Log an admin/system action.

        action:      "wallet_locked", "kyc_approved", "admin_credit", etc.
        user_id:     The admin/system user performing the action.
        target_id:   The wallet/user/withdrawal being acted upon.
        target_type: "wallet", "user", "withdrawal", "kyc", "dispute"
        before:      State before the action (dict)
        after:       State after the action (dict)
        """
        # Log to Python logger (always works)
        logger.info(
            f"AUDIT | action={action} user={user_id} "
            f"target={target_type}:{target_id} detail={detail}"
        )

        # Write to database (best-effort)
        try:
            from .models.audit import AuditLog
            AuditLog.objects.create(
                action=action,
                performed_by_id=user_id,
                target_type=target_type,
                target_id=target_id,
                detail=detail,
                before_state=before or {},
                after_state=after or {},
                ip_address=ip_address,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"AuditLog DB write failed: {e}")

    @staticmethod
    def log_balance_change(wallet, old_balance: Decimal, new_balance: Decimal,
                           action: str, performed_by_id: int, reason: str = ""):
        """Convenience method for balance change logging."""
        AuditLogger.log(
            action=action,
            user_id=performed_by_id,
            target_id=wallet.id,
            target_type="wallet",
            detail=reason,
            before={"balance": str(old_balance)},
            after={"balance": str(new_balance), "delta": str(new_balance - old_balance)},
        )

    @staticmethod
    def log_admin_action(request, action: str, target_id: int,
                         target_type: str = "wallet", detail: str = ""):
        """Convenience method for admin view actions."""
        AuditLogger.log(
            action=action,
            user_id=request.user.id,
            target_id=target_id,
            target_type=target_type,
            detail=detail,
            ip_address=request.META.get("REMOTE_ADDR", ""),
        )

    @staticmethod
    def get_wallet_history(wallet_id: int, limit: int = 100):
        """Get audit history for a specific wallet."""
        try:
            from .models.audit import AuditLog
            return AuditLog.objects.filter(
                target_type="wallet", target_id=wallet_id
            ).order_by("-created_at")[:limit]
        except Exception:
            return []
