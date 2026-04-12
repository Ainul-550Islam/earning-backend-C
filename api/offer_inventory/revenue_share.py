# api/offer_inventory/revenue_share.py
"""
Revenue Share Manager.
Tracks and distributes revenue between platform, users, referrers, networks.
All math uses Decimal — zero float operations.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

P4 = Decimal('0.0001')


class RevenueShareManager:
    """
    Full revenue distribution lifecycle.
    """

    @classmethod
    @transaction.atomic
    def distribute(cls, conversion) -> dict:
        """
        Distribute revenue for an approved conversion.
        Returns breakdown dict.
        """
        from api.offer_inventory.finance_payment.revenue_calculator import RevenueCalculator
        from api.offer_inventory.models import UserReferral

        has_referral = UserReferral.objects.filter(referred=conversion.user).exists()
        breakdown    = RevenueCalculator.calculate(
            gross       =conversion.payout_amount,
            user        =conversion.user,
            has_referral=has_referral,
        )

        # Record RevenueShare
        cls._create_record(conversion, breakdown)

        return breakdown.as_dict()

    @staticmethod
    def _create_record(conversion, breakdown):
        from api.offer_inventory.models import RevenueShare
        RevenueShare.objects.get_or_create(
            conversion=conversion,
            defaults={
                'offer'        : conversion.offer,
                'gross_revenue': breakdown.gross_revenue,
                'platform_cut' : breakdown.platform_cut,
                'user_share'   : breakdown.net_to_user,
                'referral_share': breakdown.referral_commission,
            }
        )

    @staticmethod
    def get_platform_revenue(days: int = 30) -> Decimal:
        """Total platform profit over period."""
        from api.offer_inventory.models import RevenueShare
        from django.db.models import Sum
        from datetime import timedelta

        since  = timezone.now() - timedelta(days=days)
        result = RevenueShare.objects.filter(
            created_at__gte=since
        ).aggregate(total=Sum('platform_cut'))['total']
        return (result or Decimal('0')).quantize(P4)

    @staticmethod
    def get_user_revenue(user, days: int = 30) -> dict:
        """User's earnings breakdown."""
        from api.offer_inventory.models import RevenueShare, ReferralCommission
        from django.db.models import Sum
        from datetime import timedelta

        since     = timezone.now() - timedelta(days=days)
        offer_rev = RevenueShare.objects.filter(
            conversion__user=user, created_at__gte=since
        ).aggregate(total=Sum('user_share'))['total'] or Decimal('0')

        ref_rev = ReferralCommission.objects.filter(
            referrer=user, created_at__gte=since, is_paid=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return {
            'offer_earnings'    : float(offer_rev),
            'referral_earnings' : float(ref_rev),
            'total_earnings'    : float(offer_rev + ref_rev),
        }

    @staticmethod
    def get_network_revenue(network_id: str, days: int = 30) -> dict:
        """Revenue breakdown by network."""
        from api.offer_inventory.models import RevenueShare
        from django.db.models import Sum, Count
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        agg   = RevenueShare.objects.filter(
            offer__network_id=network_id, created_at__gte=since
        ).aggregate(
            gross   =Sum('gross_revenue'),
            platform=Sum('platform_cut'),
            users   =Sum('user_share'),
            referrals=Sum('referral_share'),
            count   =Count('id'),
        )
        return {k: float(v or 0) for k, v in agg.items()}

    @staticmethod
    def get_daily_breakdown(days: int = 7) -> list:
        """Daily revenue breakdown."""
        from api.offer_inventory.models import RevenueShare
        from django.db.models import Sum
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return list(
            RevenueShare.objects.filter(created_at__gte=since)
            .extra({'date': "DATE(created_at)"})
            .values('date')
            .annotate(
                gross   =Sum('gross_revenue'),
                platform=Sum('platform_cut'),
                users   =Sum('user_share'),
            )
            .order_by('date')
        )
