# api/payment_gateways/bonuses/LeaderboardEngine.py
# Publisher performance leaderboard and contest system
# Like CPAlead's publisher ranking and MaxBounty's performance contests

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class LeaderboardEngine:
    """
    Publisher performance leaderboard and contest management.

    Features:
        - Real-time earnings leaderboard (daily/weekly/monthly)
        - Publisher contests with prizes
        - Top performer badges
        - Earnings milestones
    """

    def get_leaderboard(self, period: str = 'monthly', limit: int = 20) -> list:
        """
        Get top publisher earnings leaderboard.

        Args:
            period: 'daily' | 'weekly' | 'monthly' | 'all_time'
            limit:  Max publishers to return

        Returns:
            list: Ranked publishers with earnings stats
        """
        from api.payment_gateways.tracking.models import Conversion
        from django.contrib.auth import get_user_model
        from django.db.models import Sum, Count

        User  = get_user_model()
        since = self._get_since(period)

        qs = Conversion.objects.filter(
            status='approved',
            created_at__gte=since,
        ).values('publisher__id','publisher__username','publisher__email').annotate(
            total_earnings  = Sum('payout'),
            total_conversions= Count('id'),
        ).order_by('-total_earnings')[:limit]

        ranked = []
        for i, row in enumerate(qs, 1):
            ranked.append({
                'rank':             i,
                'publisher_id':     row['publisher__id'],
                'username':         row['publisher__username'],
                'display_name':     self._obfuscate(row['publisher__username']),
                'total_earnings':   float(row['total_earnings'] or 0),
                'total_conversions':row['total_conversions'],
                'badge':            self._get_rank_badge(i),
            })

        return {
            'period':       period,
            'since':        since.date().isoformat(),
            'leaderboard':  ranked,
            'generated_at': timezone.now().isoformat(),
        }

    def get_my_rank(self, user) -> dict:
        """Get current user's rank in the leaderboard."""
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum, Count

        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)

        my_earnings = Conversion.objects.filter(
            publisher=user, status='approved', created_at__gte=month_start
        ).aggregate(e=Sum('payout'))['e'] or Decimal('0')

        # Count publishers with MORE earnings this month
        from django.contrib.auth import get_user_model
        better_count = Conversion.objects.filter(
            status='approved', created_at__gte=month_start
        ).values('publisher').annotate(
            total=Sum('payout')
        ).filter(total__gt=my_earnings).count()

        my_rank = better_count + 1

        return {
            'rank':           my_rank,
            'monthly_earnings': float(my_earnings),
            'badge':          self._get_rank_badge(my_rank),
            'percentile':     round(100 - (my_rank / max(1, my_rank + 10)) * 100, 1),
        }

    def _get_since(self, period: str):
        now = timezone.now()
        if period == 'daily':   return now - timedelta(days=1)
        if period == 'weekly':  return now - timedelta(weeks=1)
        if period == 'monthly': return now.replace(day=1, hour=0, minute=0, second=0)
        return now - timedelta(days=365 * 10)  # all time

    def _get_rank_badge(self, rank: int) -> str:
        if rank == 1:  return '🥇 #1 Top Publisher'
        if rank == 2:  return '🥈 #2'
        if rank == 3:  return '🥉 #3'
        if rank <= 10: return f'⭐ Top 10'
        if rank <= 50: return f'🌟 Top 50'
        return f'#{rank}'

    def _obfuscate(self, username: str) -> str:
        """Show only first 3 chars for privacy on public leaderboard."""
        if len(username) <= 3:
            return username
        return username[:3] + '***'
