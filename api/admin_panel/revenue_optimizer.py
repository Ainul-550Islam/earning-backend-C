# api/admin_panel/revenue_optimizer.py
"""AI revenue optimization recommendations."""
from __future__ import annotations
import logging
from typing import Dict, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class RevenueOptimizer:
    """AI-powered revenue optimization recommendations."""

    @classmethod
    def get_optimization_suggestions(cls) -> List[Dict]:
        """Generate actionable revenue optimization suggestions."""
        suggestions = []
        today = timezone.now()

        # Check low-performing offers
        try:
            from api.promotions.models import Campaign, TaskSubmission
            from django.db.models import Count, Q
            last_7d = today - timedelta(days=7)
            low_offers = Campaign.objects.filter(
                status='active',
                created_at__lt=today - timedelta(days=3)
            ).annotate(
                subs=Count('tasksubmission', filter=Q(tasksubmission__created_at__gte=last_7d))
            ).filter(subs=0)[:10]
            for offer in low_offers:
                suggestions.append({
                    'type': 'low_performing_offer', 'priority': 'medium',
                    'title': f'Offer "{offer.title}" has 0 conversions in 7 days',
                    'action': 'Consider increasing payout or pausing',
                    'offer_id': offer.pk,
                })
        except Exception:
            pass

        # Check payout bottleneck
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Count
            pending_count = PayoutItem.objects.filter(status='QUEUED').count()
            if pending_count > 100:
                suggestions.append({
                    'type': 'payout_bottleneck', 'priority': 'high',
                    'title': f'{pending_count} withdrawals pending approval',
                    'action': 'Process bulk approvals to improve user retention',
                    'count': pending_count,
                })
        except Exception:
            pass

        # Check high-value inactive users
        try:
            from api.wallet.models import Wallet
            from django.db.models import Q
            high_balance_inactive = Wallet.objects.filter(
                current_balance__gt=100, is_locked=False,
                user__last_login__lt=today - timedelta(days=30)
            ).count()
            if high_balance_inactive > 0:
                suggestions.append({
                    'type': 'dormant_high_value', 'priority': 'medium',
                    'title': f'{high_balance_inactive} users with >৳100 balance are inactive 30+ days',
                    'action': 'Run re-engagement campaign with withdrawal incentive',
                    'count': high_balance_inactive,
                })
        except Exception:
            pass

        return suggestions

    @classmethod
    def get_revenue_forecast(cls, days: int = 7) -> Dict:
        """Simple revenue forecast based on trends."""
        try:
            from api.admin_panel.analytics import get_daily_revenue_trend
            trend = get_daily_revenue_trend(30)
            if not trend:
                return {'forecast': 0, 'confidence': 'low'}
            # Simple moving average
            amounts = [float(d.get('total') or 0) for d in trend[-7:]]
            avg = sum(amounts) / len(amounts) if amounts else 0
            forecast = avg * days
            return {
                'forecast_amount': round(forecast, 2),
                'period_days': days,
                'daily_avg': round(avg, 2),
                'confidence': 'medium',
                'currency': 'BDT',
            }
        except Exception as e:
            return {'error': str(e)}

    @classmethod
    def identify_revenue_leaks(cls) -> List[Dict]:
        """Find places where revenue is being lost."""
        leaks = []
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Count
            failed = PayoutItem.objects.filter(status='FAILED').count()
            if failed > 0:
                leaks.append({'type': 'failed_payouts', 'count': failed,
                               'action': 'Review and retry failed payouts'})
        except Exception:
            pass
        return leaks

revenue_optimizer = RevenueOptimizer()