# =============================================================================
# promotions/publisher/publisher_stats.py
# Publisher Statistics — EPC, CR, Top offers, Geographic performance
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class PublisherStats:
    """Advanced publisher analytics: EPC, geographic split, device split."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    def get_epc_by_campaign(self, days: int = 7) -> list:
        """EPC (Earnings Per Click) per campaign."""
        from api.promotions.models import PromotionTransaction, TaskSubmission
        cutoff = timezone.now() - timezone.timedelta(days=days)
        campaigns = TaskSubmission.objects.filter(
            user_id=self.user_id,
            created_at__gte=cutoff,
        ).values(
            'campaign__id', 'campaign__title'
        ).annotate(
            clicks=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
        )
        results = []
        for c in campaigns:
            earnings = PromotionTransaction.objects.filter(
                user_id=self.user_id,
                transaction_type='reward',
                created_at__gte=cutoff,
                metadata__campaign_id=c['campaign__id'],
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            epc = (earnings / c['clicks'] * 100).quantize(Decimal('0.0001')) if c['clicks'] > 0 else Decimal('0')
            results.append({
                'campaign_id': c['campaign__id'],
                'campaign_title': c['campaign__title'],
                'clicks': c['clicks'],
                'conversions': c['approved'],
                'cr_pct': round(c['approved'] / c['clicks'] * 100, 2) if c['clicks'] > 0 else 0,
                'earnings': str(earnings),
                'epc': str(epc),
            })
        return sorted(results, key=lambda x: Decimal(x['epc']), reverse=True)

    def get_referral_stats(self) -> dict:
        """Referral program performance."""
        from api.promotions.models import ReferralCommissionLog
        commissions = ReferralCommissionLog.objects.filter(referrer_id=self.user_id)
        total = commissions.aggregate(t=Sum('commission_amount'))['t'] or Decimal('0')
        count = commissions.count()
        return {
            'total_referrals': count,
            'total_commission': str(total),
            'referral_link': f'/ref/{self.user_id}/',
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_epc_view(request):
    stats = PublisherStats(user_id=request.user.id)
    days = int(request.query_params.get('days', 7))
    return Response({'epc_data': stats.get_epc_by_campaign(days=days)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_referral_stats_view(request):
    stats = PublisherStats(user_id=request.user.id)
    return Response(stats.get_referral_stats())
