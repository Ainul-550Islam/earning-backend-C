# =============================================================================
# promotions/leaderboard/publisher_leaderboard.py
# Publisher Leaderboard — MaxBounty style top earner rankings
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


class PublisherLeaderboard:
    """
    Real-time publisher rankings:
    - Daily / Weekly / Monthly / All-time
    - Top earners, top converters
    - Publisher's own rank
    """
    CACHE_TTL = 300  # 5 minutes

    def get_leaderboard(self, period: str = 'monthly', limit: int = 50) -> dict:
        """Get top publishers for a period."""
        cache_key = f'leaderboard:publisher:{period}:{limit}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        cutoff = self._get_cutoff(period)
        result = self._build_leaderboard(cutoff, limit, period)
        cache.set(cache_key, result, timeout=self.CACHE_TTL)
        return result

    def get_my_rank(self, user_id: int, period: str = 'monthly') -> dict:
        """Get a publisher's own rank."""
        from api.promotions.models import PromotionTransaction
        cutoff = self._get_cutoff(period)
        my_earnings = PromotionTransaction.objects.filter(
            user_id=user_id,
            transaction_type='reward',
            created_at__gte=cutoff,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        better_count = PromotionTransaction.objects.filter(
            transaction_type='reward',
            created_at__gte=cutoff,
        ).values('user').annotate(
            total=Sum('amount')
        ).filter(total__gt=my_earnings).count()

        rank = better_count + 1
        return {
            'user_id': user_id,
            'rank': rank,
            'earnings': str(my_earnings),
            'period': period,
            'is_top_10': rank <= 10,
            'is_top_100': rank <= 100,
        }

    def _build_leaderboard(self, cutoff, limit: int, period: str) -> dict:
        from api.promotions.models import PromotionTransaction
        from django.contrib.auth import get_user_model
        User = get_user_model()

        top_users = PromotionTransaction.objects.filter(
            transaction_type='reward',
            created_at__gte=cutoff,
        ).values('user__id', 'user__username').annotate(
            earnings=Sum('amount'),
            conversions=Count('id'),
        ).order_by('-earnings')[:limit]

        entries = []
        for i, u in enumerate(top_users, start=1):
            entries.append({
                'rank': i,
                'user_id': u['user__id'],
                'username': u['user__username'],
                'earnings': str(u['earnings'] or Decimal('0')),
                'conversions': u['conversions'],
                'medal': {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, ''),
            })

        return {
            'period': period,
            'updated_at': timezone.now().isoformat(),
            'total_publishers': len(entries),
            'leaderboard': entries,
        }

    def _get_cutoff(self, period: str):
        now = timezone.now()
        if period == 'daily':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            return now - timezone.timedelta(days=7)
        elif period == 'monthly':
            return now.replace(day=1, hour=0, minute=0, second=0)
        elif period == 'yearly':
            return now.replace(month=1, day=1, hour=0, minute=0, second=0)
        else:  # all_time
            return timezone.datetime(2020, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def invalidate_cache():
        for period in ['daily', 'weekly', 'monthly', 'yearly', 'all_time']:
            cache.delete(f'leaderboard:publisher:{period}:50')


@api_view(['GET'])
@permission_classes([AllowAny])
def publisher_leaderboard_view(request):
    """GET /api/promotions/leaderboard/publishers/?period=monthly&limit=50"""
    period = request.query_params.get('period', 'monthly')
    limit = min(int(request.query_params.get('limit', 50)), 100)
    lb = PublisherLeaderboard()
    return Response(lb.get_leaderboard(period=period, limit=limit))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_rank_view(request):
    """GET /api/promotions/leaderboard/my-rank/?period=monthly"""
    period = request.query_params.get('period', 'monthly')
    lb = PublisherLeaderboard()
    return Response(lb.get_my_rank(user_id=request.user.id, period=period))
