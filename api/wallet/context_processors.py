# api/wallet/context_processors.py
"""
Django template context processors.
Add wallet info to every template context.

settings.py TEMPLATES[0]["OPTIONS"]["context_processors"]:
    "api.wallet.context_processors.wallet_context",
"""
import logging
from decimal import Decimal

logger = logging.getLogger("wallet.context_processors")


def wallet_context(request):
    """
    Add wallet balance summary to every template context.
    Only for authenticated users.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        from .models.core import Wallet
        wallet = Wallet.objects.filter(user=request.user).first()
        if not wallet:
            return {}

        return {
            "wallet_balance":        wallet.current_balance,
            "wallet_available":      wallet.available_balance,
            "wallet_pending":        wallet.pending_balance,
            "wallet_bonus":          wallet.bonus_balance,
            "wallet_is_locked":      wallet.is_locked,
            "wallet_total_earned":   wallet.total_earned,
            "wallet_total_withdrawn":wallet.total_withdrawn,
            "wallet_currency":       wallet.currency or "BDT",
        }
    except Exception as e:
        logger.debug(f"wallet_context error: {e}")
        return {}


def wallet_notifications_context(request):
    """Add unread notification count to context."""
    if not request.user.is_authenticated:
        return {"unread_notifications": 0}
    try:
        from .models.notification import WalletNotification
        count = WalletNotification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return {"unread_wallet_notifications": count}
    except Exception:
        return {"unread_wallet_notifications": 0}
