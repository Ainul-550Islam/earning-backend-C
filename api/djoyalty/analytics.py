# api/djoyalty/analytics.py
"""
Djoyalty Analytics -- Business intelligence and reporting।
Customer analytics, points liability, campaign ROI, cohort analysis।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional
from django.db.models import Sum, Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class CustomerAnalytics:
    """Customer lifecycle and behavior analytics।"""

    @staticmethod
    def get_customer_ltv(customer) -> Decimal:
        """Calculate Customer Lifetime Value (total spend)।"""
        from .models.core import Txn
        result = Txn.objects.filter(customer=customer).aggregate(total=Sum('value'))
        return result['total'] or Decimal('0')

    @staticmethod
    def get_customer_avg_order_value(customer) -> Decimal:
        """Average order value for customer।"""
        from .models.core import Txn
        result = Txn.objects.filter(customer=customer).aggregate(avg=Avg('value'))
        return result['avg'] or Decimal('0')

    @staticmethod
    def get_purchase_frequency(customer, days: int = 90) -> int:
        """Number of purchases in last N days।"""
        from .models.core import Txn
        cutoff = timezone.now() - timedelta(days=days)
        return Txn.objects.filter(customer=customer, created_at__gte=cutoff).count()

    @staticmethod
    def get_retention_rate(tenant=None, cohort_month: int = None,
                            cohort_year: int = None) -> dict:
        """Calculate monthly retention rate."""
        from .models.core import Customer, Txn
        now = timezone.now()
        if not cohort_month:
            cohort_month = now.month - 1 or 12
        if not cohort_year:
            cohort_year = now.year if cohort_month != 12 else now.year - 1

        # Customers who joined in cohort month
        qs = Customer.objects.filter(
            created_at__year=cohort_year,
            created_at__month=cohort_month,
            is_active=True,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        cohort_size = qs.count()

        if cohort_size == 0:
            return {'cohort_size': 0, 'retained': 0, 'retention_rate': '0%'}

        # How many made a purchase the next month
        next_month = cohort_month % 12 + 1
        next_year = cohort_year if next_month > 1 else cohort_year + 1

        retained_ids = Txn.objects.filter(
            customer__in=qs,
            created_at__year=next_year,
            created_at__month=next_month,
        ).values_list('customer_id', flat=True).distinct()

        retained = len(set(retained_ids))
        rate = retained / cohort_size * 100

        return {
            'cohort_month': f'{cohort_year}-{cohort_month:02d}',
            'cohort_size': cohort_size,
            'retained': retained,
            'retention_rate': f'{rate:.1f}%',
        }

    @staticmethod
    def get_segment_distribution(tenant=None) -> dict:
        """Distribution of customers across RFM segments।"""
        try:
            from .models.ai_personalization import CustomerAIProfile
            qs = CustomerAIProfile.objects.all()
            if tenant:
                qs = qs.filter(customer__tenant=tenant)
            return dict(qs.values('rfm_segment').annotate(count=Count('id')).values_list('rfm_segment', 'count'))
        except Exception:
            return {}


class PointsAnalytics:
    """Points economics and liability analytics।"""

    @staticmethod
    def get_total_outstanding_liability(tenant=None) -> Decimal:
        """Total points outstanding (unredeemed) = liability।"""
        from .models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects.filter(balance__gt=0)
        if tenant:
            qs = qs.filter(tenant=tenant)
        result = qs.aggregate(total=Sum('balance'))
        return result['total'] or Decimal('0')

    @staticmethod
    def get_points_issued_this_month(tenant=None) -> Decimal:
        """Total points issued this month।"""
        from .models.points import PointsLedger
        now = timezone.now()
        qs = PointsLedger.objects.filter(
            txn_type='credit', is_reversed=False,
            created_at__year=now.year, created_at__month=now.month,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        result = qs.aggregate(total=Sum('points'))
        return result['total'] or Decimal('0')

    @staticmethod
    def get_points_redeemed_this_month(tenant=None) -> Decimal:
        """Total points redeemed this month।"""
        from .models.points import PointsLedger
        now = timezone.now()
        qs = PointsLedger.objects.filter(
            txn_type='debit', is_reversed=False,
            created_at__year=now.year, created_at__month=now.month,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        result = qs.aggregate(total=Sum('points'))
        return result['total'] or Decimal('0')

    @staticmethod
    def get_redemption_rate(tenant=None) -> str:
        """Points redemption rate = redeemed / issued × 100%।"""
        from .models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        totals = qs.aggregate(issued=Sum('lifetime_earned'), redeemed=Sum('lifetime_redeemed'))
        issued = totals['issued'] or Decimal('0')
        redeemed = totals['redeemed'] or Decimal('0')
        if issued == 0:
            return '0%'
        return f'{float(redeemed) / float(issued) * 100:.1f}%'

    @staticmethod
    def get_breakage_estimate(tenant=None) -> Decimal:
        """
        Estimate breakage (points that will never be redeemed)।
        Industry average: 10-30% of points issued are never redeemed।
        """
        from .models.points import LoyaltyPoints
        qs = LoyaltyPoints.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        outstanding = qs.aggregate(total=Sum('balance'))['total'] or Decimal('0')
        # Industry standard breakage assumption: 20%
        return outstanding * Decimal('0.20')

    @staticmethod
    def get_points_by_source(tenant=None, days: int = 30) -> dict:
        """Points issued breakdown by source in last N days।"""
        from .models.points import PointsLedger
        cutoff = timezone.now() - timedelta(days=days)
        qs = PointsLedger.objects.filter(
            txn_type='credit', is_reversed=False, created_at__gte=cutoff,
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return dict(
            qs.values('source').annotate(total=Sum('points')).values_list('source', 'total')
        )


class CampaignAnalytics:
    """Campaign performance analytics।"""

    @staticmethod
    def get_campaign_stats(campaign) -> dict:
        """Get comprehensive stats for a campaign।"""
        from .models.campaigns import CampaignParticipant

        participants = CampaignParticipant.objects.filter(campaign=campaign)
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'total_participants': participants.count(),
            'completed': participants.filter(status='completed').count(),
            'active': participants.filter(status='active').count(),
            'total_points_awarded': participants.aggregate(
                total=Sum('points_awarded')
            )['total'] or Decimal('0'),
            'start_date': campaign.start_date.isoformat() if campaign.start_date else None,
            'end_date': campaign.end_date.isoformat() if hasattr(campaign, 'end_date') and campaign.end_date else None,
        }


class OfferWallAnalytics:
    """OfferWall revenue and performance analytics।"""

    @staticmethod
    def get_offerwall_stats(offer_wall) -> dict:
        """Get stats for an offerwall।"""
        from .models.offerwall import OfferCompletion

        completions = OfferCompletion.objects.filter(offer_wall=offer_wall)
        return {
            'total_completions': completions.count(),
            'verified_completions': completions.filter(status='points_awarded').count(),
            'total_payout_usd': completions.filter(status='points_awarded').aggregate(
                total=Sum('advertiser_payout_received')
            )['total'] or Decimal('0'),
            'total_points_awarded': completions.filter(status='points_awarded').aggregate(
                total=Sum('points_awarded')
            )['total'] or Decimal('0'),
            'fraud_rate': (
                f"{completions.filter(is_flagged=True).count() / max(completions.count(), 1) * 100:.1f}%"
            ),
        }
