# api/admin_panel/leaderboard_engine.py
"""Real-time leaderboard calculation engine."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_TTL = 300  # 5 min


class LeaderboardEngine:
    """Calculate and cache leaderboards."""

    LEADERBOARD_TYPES = {
        'daily_earnings':    'Top earners today',
        'weekly_earnings':   'Top earners this week',
        'monthly_earnings':  'Top earners this month',
        'all_time_earnings': 'All-time top earners',
        'task_completions':  'Most tasks completed',
        'referrals':         'Top referrers',
        'streak':            'Longest daily streak',
    }

    @classmethod
    def get_leaderboard(cls, lb_type: str, limit: int = 50) -> List[Dict]:
        cache_key = f'leaderboard:{lb_type}:{limit}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = cls._calculate(lb_type, limit)
        cache.set(cache_key, result, LEADERBOARD_CACHE_TTL)
        return result

    @classmethod
    def _calculate(cls, lb_type: str, limit: int) -> List[Dict]:
        from django.db.models import Sum, Count
        now = timezone.now()
        try:
            if lb_type in ('daily_earnings', 'weekly_earnings', 'monthly_earnings', 'all_time_earnings'):
                cutoff = {
                    'daily_earnings':    now.replace(hour=0, minute=0, second=0),
                    'weekly_earnings':   now - timedelta(days=7),
                    'monthly_earnings':  now - timedelta(days=30),
                    'all_time_earnings': None,
                }.get(lb_type)
                from api.wallet.models import WalletTransaction
                qs = WalletTransaction.objects.filter(transaction_type='earning')
                if cutoff:
                    qs = qs.filter(created_at__gte=cutoff)
                return list(qs.values('wallet__user_id', 'wallet__user__username')
                             .annotate(total=Sum('amount'), count=Count('id'))
                             .order_by('-total')[:limit])

            elif lb_type == 'task_completions':
                from api.promotions.models import TaskSubmission
                cutoff = now - timedelta(days=30)
                return list(
                    TaskSubmission.objects.filter(created_at__gte=cutoff, status='approved')
                    .values('worker_id', 'worker__username')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:limit]
                )

            elif lb_type == 'referrals':
                from api.referral.models import Referral
                return list(
                    Referral.objects.values('referrer_id', 'referrer__username')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:limit]
                )

            elif lb_type == 'streak':
                from api.engagement.models import DailyCheckIn
                return list(
                    DailyCheckIn.objects.values('user_id', 'user__username')
                    .annotate(max_streak=__import__('django.db.models', fromlist=['Max']).Max('streak'))
                    .order_by('-max_streak')[:limit]
                )
        except Exception as e:
            logger.error(f"[LeaderboardEngine._calculate] {lb_type}: {e}")
        return []

    @classmethod
    def refresh_all(cls) -> Dict:
        """Refresh all leaderboard caches."""
        refreshed = []
        for lb_type in cls.LEADERBOARD_TYPES:
            try:
                cache.delete(f'leaderboard:{lb_type}:50')
                cls.get_leaderboard(lb_type, 50)
                refreshed.append(lb_type)
            except Exception as e:
                logger.error(f"[LeaderboardEngine] Refresh {lb_type}: {e}")
        return {'refreshed': refreshed}

    @classmethod
    def get_user_rank(cls, user_id: Any, lb_type: str = 'monthly_earnings') -> Dict:
        """Get user rank in a leaderboard."""
        lb = cls.get_leaderboard(lb_type, limit=1000)
        for i, entry in enumerate(lb):
            uid = entry.get('wallet__user_id') or entry.get('worker_id') or entry.get('user_id') or entry.get('referrer_id')
            if uid == user_id:
                return {'rank': i + 1, 'total': len(lb), 'entry': entry, 'lb_type': lb_type}
        return {'rank': None, 'total': len(lb), 'lb_type': lb_type}


leaderboard_engine = LeaderboardEngine()