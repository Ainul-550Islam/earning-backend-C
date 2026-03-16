# api/admin_panel/services.py
"""
Business logic for admin panel. Move complex logic out of views.
"""
import logging
from typing import Dict, Any
from django.db.models import Sum, Count

logger = logging.getLogger(__name__)


class AdminPanelService:
    """Service for dashboard stats and admin operations."""

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Aggregate stats for admin dashboard."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            from api.wallet.models import Wallet
            wallet_stats = Wallet.objects.aggregate(
                total_balance=Sum('current_balance'),
                total_wallets=Count('id'),
            )
        except Exception:
            wallet_stats = {}
        return {
            "total_users": User.objects.count(),
            **wallet_stats,
        }
