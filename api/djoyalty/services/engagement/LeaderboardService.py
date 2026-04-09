# api/djoyalty/services/engagement/LeaderboardService.py
import logging
from django.db.models import Sum, F
from ...models.points import LoyaltyPoints

logger = logging.getLogger(__name__)

class LeaderboardService:
    @staticmethod
    def get_top_customers(tenant=None, limit: int = 10, period: str = 'all'):
        qs = LoyaltyPoints.objects.select_related('customer')
        if tenant:
            qs = qs.filter(tenant=tenant)
        if period == 'monthly':
            from django.utils import timezone
            from datetime import timedelta
            qs = qs.filter(customer__transactions__timestamp__gte=timezone.now() - timedelta(days=30))
        return qs.order_by('-lifetime_earned')[:limit].values(
            'customer__id', 'customer__code',
            'customer__firstname', 'customer__lastname',
            'balance', 'lifetime_earned',
        )
