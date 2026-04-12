# =============================================================================
# promotions/leaderboard/advertiser_leaderboard.py
# Advertiser Leaderboard — Top spending advertisers, best ROI campaigns
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class AdvertiserLeaderboard:
    """Top advertisers by spend, conversions, and ROI."""
    CACHE_TTL = 600

    def get_top_advertisers(self, period: str = 'monthly', limit: int = 20) -> list:
        from api.promotions.models import Campaign, TaskSubmission
        cutoff = self._get_cutoff(period)
        cache_key = f'leaderboard:advertiser:{period}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        top = Campaign.objects.filter(
            created_at__gte=cutoff,
        ).values(
            'advertiser__id', 'advertiser__username'
        ).annotate(
            total_budget=Sum('total_budget'),
            campaign_count=Count('id'),
        ).order_by('-total_budget')[:limit]

        result = [
            {
                'rank': i + 1,
                'advertiser_id': t['advertiser__id'],
                'username': t['advertiser__username'],
                'total_budget': str(t['total_budget'] or Decimal('0')),
                'campaigns': t['campaign_count'],
            }
            for i, t in enumerate(top)
        ]
        cache.set(cache_key, result, timeout=self.CACHE_TTL)
        return result

    def get_top_campaigns(self, limit: int = 10) -> list:
        """Best performing campaigns on the platform."""
        from api.promotions.models import TaskSubmission
        from django.db.models import Q
        top = TaskSubmission.objects.values(
            'campaign__id', 'campaign__title', 'campaign__advertiser__username'
        ).annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
        ).filter(approved__gt=0).order_by('-approved')[:limit]
        return [
            {
                'rank': i + 1,
                'campaign_id': t['campaign__id'],
                'title': t['campaign__title'],
                'advertiser': t['campaign__advertiser__username'],
                'total_conversions': t['approved'],
                'quality_rate': round(t['approved'] / t['total'] * 100, 1) if t['total'] > 0 else 0,
            }
            for i, t in enumerate(top)
        ]

    def _get_cutoff(self, period: str):
        now = timezone.now()
        if period == 'monthly':
            return now.replace(day=1, hour=0, minute=0, second=0)
        elif period == 'weekly':
            return now - timezone.timedelta(days=7)
        return now.replace(day=1, month=1, hour=0, minute=0, second=0)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advertiser_leaderboard_view(request):
    period = request.query_params.get('period', 'monthly')
    lb = AdvertiserLeaderboard()
    return Response({
        'top_advertisers': lb.get_top_advertisers(period=period),
        'top_campaigns': lb.get_top_campaigns(),
    })
