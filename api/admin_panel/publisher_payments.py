# api/admin_panel/publisher_payments.py
"""Publisher payment history and reconciliation admin."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import timedelta

logger = logging.getLogger(__name__)


class PublisherPaymentsAdmin:
    """Admin control for publisher payment management."""

    @classmethod
    def get_publisher_earnings(cls, publisher_id: Any, days: int = 30) -> Dict:
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.wallet.models import WalletTransaction
            earnings = WalletTransaction.objects.filter(
                wallet__user_id=publisher_id,
                transaction_type='earning',
                created_at__gte=cutoff
            ).aggregate(total=Sum('amount'), count=Count('id'), avg=Avg('amount'))
            payouts = WalletTransaction.objects.filter(
                wallet__user_id=publisher_id,
                transaction_type='withdrawal',
                created_at__gte=cutoff
            ).aggregate(total=Sum('amount'), count=Count('id'))
            return {
                'publisher_id': publisher_id,
                'period_days': days,
                'total_earned': float(earnings['total'] or 0),
                'earning_transactions': earnings['count'] or 0,
                'avg_earning': float(earnings['avg'] or 0),
                'total_withdrawn': float(payouts['total'] or 0),
                'payout_transactions': payouts['count'] or 0,
                'net_balance': float(earnings['total'] or 0) - float(payouts['total'] or 0),
            }
        except Exception as e:
            return {'publisher_id': publisher_id, 'error': str(e)}

    @classmethod
    def reconcile_publisher(cls, publisher_id: Any, actor) -> Dict:
        """Reconcile publisher earnings vs actual payouts."""
        from api.admin_panel.INTEGRATION_SYSTEM.sync_manager import sync_manager
        result = sync_manager.sync_wallet_with_transactions(publisher_id)
        from api.admin_panel.models.activity import AdminActivity
        try:
            AdminActivity.log(actor=actor, action='reconcile_publisher',
                              model_name='User', object_id=str(publisher_id),
                              changes=result)
        except Exception:
            pass
        return result

    @classmethod
    def get_top_publishers(cls, limit: int = 20, days: int = 30) -> List[Dict]:
        """Top earning publishers."""
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.wallet.models import WalletTransaction
            return list(
                WalletTransaction.objects.filter(
                    transaction_type='earning', created_at__gte=cutoff
                ).values('wallet__user_id', 'wallet__user__username')
                .annotate(total=Sum('amount'), count=Count('id'))
                .order_by('-total')[:limit]
            )
        except Exception:
            return []

    @classmethod
    def hold_publisher_payments(cls, publisher_id: Any, reason: str, actor) -> Dict:
        """Put publisher payments on hold (fraud investigation)."""
        try:
            from api.wallet.models import Wallet
            Wallet.objects.filter(user_id=publisher_id).update(is_locked=True, locked_reason=reason)
            from api.payout_queue.models import PayoutItem
            held = PayoutItem.objects.filter(user_id=publisher_id, status='QUEUED').update(status='PROCESSING')
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='hold_publisher_payments',
                              model_name='Publisher', object_id=str(publisher_id),
                              changes={'reason': reason, 'held_payouts': held})
            return {'success': True, 'publisher_id': publisher_id, 'held_payouts': held}
        except Exception as e:
            return {'success': False, 'error': str(e)}


publisher_payments_admin = PublisherPaymentsAdmin()