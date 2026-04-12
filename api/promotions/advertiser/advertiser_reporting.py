# =============================================================================
# promotions/advertiser/advertiser_reporting.py
# Advertiser Reporting — MaxBounty style real-time reporting
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class AdvertiserReporting:
    """
    Advertiser reports:
    - ROI per campaign
    - Conversion funnel
    - Publisher performance
    - Fraud rate
    - Geographic breakdown
    """

    def __init__(self, advertiser_id: int):
        self.advertiser_id = advertiser_id

    def get_advertiser_dashboard(self) -> dict:
        """Main advertiser dashboard summary."""
        from api.promotions.models import Campaign, TaskSubmission, PromotionTransaction
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        my_campaigns = Campaign.objects.filter(advertiser_id=self.advertiser_id)
        active_count = my_campaigns.filter(status='active').count()
        total_count = my_campaigns.count()

        # Total spend
        total_spend = PromotionTransaction.objects.filter(
            transaction_type='escrow_lock',
            metadata__advertiser_id=self.advertiser_id,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Conversions
        all_subs = TaskSubmission.objects.filter(campaign__advertiser_id=self.advertiser_id)
        total_conversions = all_subs.filter(status='approved').count()
        today_conversions = all_subs.filter(status='approved', updated_at__gte=today).count()
        pending_review = all_subs.filter(status='pending').count()

        # Fraud rate
        total_subs = all_subs.count()
        fraud_subs = all_subs.filter(status='rejected').count()
        fraud_rate = round(fraud_subs / total_subs * 100, 2) if total_subs > 0 else 0.0

        return {
            'advertiser_id': self.advertiser_id,
            'generated_at': now.isoformat(),
            'campaigns': {
                'total': total_count,
                'active': active_count,
                'pending_review': my_campaigns.filter(status='pending').count(),
                'paused': my_campaigns.filter(status='paused').count(),
            },
            'conversions': {
                'today': today_conversions,
                'total': total_conversions,
                'pending_review': pending_review,
                'fraud_rate_pct': fraud_rate,
            },
            'financials': {
                'total_spend': str(abs(total_spend)),
                'remaining_budget': str(self._get_remaining_budget()),
            },
        }

    def get_campaign_roi_report(self, campaign_id: int) -> dict:
        """ROI analysis for a specific campaign."""
        from api.promotions.models import Campaign, TaskSubmission, PromotionTransaction
        try:
            campaign = Campaign.objects.get(id=campaign_id, advertiser_id=self.advertiser_id)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found'}

        subs = TaskSubmission.objects.filter(campaign=campaign)
        approved = subs.filter(status='approved').count()
        rejected = subs.filter(status='rejected').count()
        pending = subs.filter(status='pending').count()
        total = subs.count()

        spend = PromotionTransaction.objects.filter(
            transaction_type='escrow_release',
            metadata__campaign_id=campaign_id,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        return {
            'campaign_id': campaign_id,
            'campaign_title': campaign.title,
            'status': campaign.status,
            'budget': {
                'total': str(campaign.total_budget),
                'spent': str(abs(spend)),
                'remaining': str(campaign.total_budget - abs(spend)),
                'utilization_pct': round(float(abs(spend) / campaign.total_budget * 100), 2) if campaign.total_budget > 0 else 0,
            },
            'conversions': {
                'total': total,
                'approved': approved,
                'rejected': rejected,
                'pending': pending,
                'approval_rate_pct': round(approved / total * 100, 2) if total > 0 else 0,
            },
            'cpa': str(abs(spend) / approved) if approved > 0 else '0.00',
        }

    def get_publisher_performance_for_campaign(self, campaign_id: int, limit: int = 20) -> list:
        """Which publishers are performing best for this campaign."""
        from api.promotions.models import TaskSubmission
        from django.db.models import F
        results = TaskSubmission.objects.filter(
            campaign_id=campaign_id,
            campaign__advertiser_id=self.advertiser_id,
        ).values(
            'user__id',
            'user__username',
        ).annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected')),
        ).order_by('-approved')[:limit]
        return [
            {
                'publisher_id': r['user__id'],
                'publisher': r['user__username'],
                'total_submissions': r['total'],
                'approved': r['approved'],
                'rejected': r['rejected'],
                'quality_rate': round(r['approved'] / r['total'] * 100, 1) if r['total'] > 0 else 0,
            }
            for r in results
        ]

    def _get_remaining_budget(self) -> Decimal:
        from api.promotions.models import Campaign
        campaigns = Campaign.objects.filter(advertiser_id=self.advertiser_id)
        return campaigns.aggregate(t=Sum('total_budget'))['t'] or Decimal('0')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advertiser_dashboard_view(request):
    reporting = AdvertiserReporting(advertiser_id=request.user.id)
    return Response(reporting.get_advertiser_dashboard())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_roi_view(request, campaign_id):
    reporting = AdvertiserReporting(advertiser_id=request.user.id)
    return Response(reporting.get_campaign_roi_report(campaign_id=campaign_id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_performance_view(request, campaign_id):
    reporting = AdvertiserReporting(advertiser_id=request.user.id)
    data = reporting.get_publisher_performance_for_campaign(
        campaign_id=campaign_id,
        limit=int(request.query_params.get('limit', 20)),
    )
    return Response({'publishers': data})
