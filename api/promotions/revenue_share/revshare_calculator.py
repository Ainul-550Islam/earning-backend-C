# =============================================================================
# promotions/revenue_share/revshare_calculator.py
# RevShare — Publisher earns % of user's spend (ongoing)
# Used for: iGaming, Dating, SaaS subscriptions
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class RevShareCalculator:
    """Calculate and process ongoing revenue share commissions."""

    def calculate_publisher_revshare(self, publisher_id: int, advertiser_id: int,
                                      user_revenue: Decimal, share_pct: Decimal,
                                      campaign_id: int = None, period: str = 'monthly') -> dict:
        """Calculate and award revshare for a billing period."""
        commission = (user_revenue * share_pct).quantize(Decimal('0.0001'))
        self._award_revshare(publisher_id, advertiser_id, commission, user_revenue, share_pct, campaign_id)
        return {
            'publisher_id':  publisher_id,
            'user_revenue':  str(user_revenue),
            'share_pct':     f'{float(share_pct * 100):.1f}%',
            'commission':    str(commission),
            'period':        period,
            'awarded_at':    timezone.now().isoformat(),
        }

    def get_publisher_revshare_stats(self, publisher_id: int, days: int = 30) -> dict:
        from api.promotions.models import PromotionTransaction
        cutoff = timezone.now() - timezone.timedelta(days=days)
        total = PromotionTransaction.objects.filter(
            user_id=publisher_id,
            transaction_type='reward',
            metadata__type='revshare',
            created_at__gte=cutoff,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return {
            'publisher_id':  publisher_id,
            'period_days':   days,
            'total_revshare': str(total),
            'model':         'RevShare (ongoing % of user spend)',
        }

    def _award_revshare(self, publisher_id, advertiser_id, commission, revenue, pct, campaign_id):
        from api.promotions.models import PromotionTransaction
        PromotionTransaction.objects.create(
            user_id=publisher_id,
            transaction_type='reward',
            amount=commission,
            status='completed',
            notes=f'RevShare: {float(pct*100):.1f}% of ${revenue}',
            metadata={
                'type': 'revshare', 'advertiser_id': advertiser_id,
                'campaign_id': campaign_id, 'revenue': str(revenue), 'pct': str(pct),
            },
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revshare_stats_view(request):
    calc = RevShareCalculator()
    return Response(calc.get_publisher_revshare_stats(
        publisher_id=request.user.id,
        days=int(request.query_params.get('days', 30)),
    ))
