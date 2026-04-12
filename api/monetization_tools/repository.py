"""
api/monetization_tools/repository.py
========================================
Data-access layer — wraps ORM queries so views and services
stay free of complex queryset logic.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional, List

from django.db.models import Q, Sum, Count, Avg, F
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================================================
# Ad Campaign Repository
# ===========================================================================

class AdCampaignRepository:

    @staticmethod
    def get_active(tenant=None):
        from .models import AdCampaign
        qs = AdCampaign.objects.filter(
            status='active',
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def increment_counters(campaign_id, impressions=0, clicks=0, conversions=0, spent=Decimal('0')):
        from .models import AdCampaign
        AdCampaign.objects.filter(id=campaign_id).update(
            total_impressions=F('total_impressions') + impressions,
            total_clicks=F('total_clicks') + clicks,
            total_conversions=F('total_conversions') + conversions,
            spent_budget=F('spent_budget') + spent,
        )


# ===========================================================================
# Offer Repository
# ===========================================================================

class OfferRepository:

    @staticmethod
    def get_available(tenant=None, country: str = None, device_type: str = None,
                      offer_type: str = None, offerwall_id=None):
        from .models import Offer
        now = timezone.now()
        qs  = Offer.objects.filter(
            status='active',
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        ).select_related('offerwall', 'offerwall__network')

        if tenant:
            qs = qs.filter(tenant=tenant)
        if offer_type:
            qs = qs.filter(offer_type=offer_type)
        if offerwall_id:
            qs = qs.filter(offerwall_id=offerwall_id)
        if country:
            qs = qs.filter(
                Q(target_countries=[]) | Q(target_countries__contains=[country.upper()])
            )
        if device_type:
            qs = qs.filter(
                Q(target_devices=[]) | Q(target_devices__contains=[device_type.lower()])
            )
        return qs.order_by('-is_featured', '-is_hot', '-point_value')

    @staticmethod
    def get_for_user(user, tenant=None):
        """Return offers not yet completed (approved) by this user."""
        from .models import Offer, OfferCompletion
        completed_offer_ids = OfferCompletion.objects.filter(
            user=user, status='approved'
        ).values_list('offer_id', flat=True)
        return OfferRepository.get_available(tenant=tenant).exclude(id__in=completed_offer_ids)


# ===========================================================================
# OfferCompletion Repository
# ===========================================================================

class OfferCompletionRepository:

    @staticmethod
    def get_pending():
        from .models import OfferCompletion
        return OfferCompletion.objects.filter(status='pending').select_related('user', 'offer')

    @staticmethod
    def get_for_user(user, status: str = None):
        from .models import OfferCompletion
        qs = OfferCompletion.objects.filter(user=user).select_related('offer')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')

    @staticmethod
    def today_count_for_user(user) -> int:
        from .models import OfferCompletion
        return OfferCompletion.objects.filter(
            user=user, created_at__date=timezone.now().date()
        ).count()

    @staticmethod
    def high_fraud_pending(threshold: int = 70):
        from .models import OfferCompletion
        return OfferCompletion.objects.filter(
            status='pending', fraud_score__gte=threshold
        )


# ===========================================================================
# Revenue Repository
# ===========================================================================

class RevenueRepository:

    @staticmethod
    def daily_totals(tenant=None, start: date = None, end: date = None):
        from .models import RevenueDailySummary
        qs = RevenueDailySummary.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.order_by('-date')

    @staticmethod
    def aggregate_totals(tenant=None, start: date = None, end: date = None) -> dict:
        qs = RevenueRepository.daily_totals(tenant, start, end)
        return qs.aggregate(
            total_revenue=Sum('total_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            avg_ecpm=Avg('ecpm'),
            avg_ctr=Avg('ctr'),
        )

    @staticmethod
    def top_networks_by_revenue(tenant=None, start: date = None, end: date = None, limit: int = 10):
        from .models import RevenueDailySummary
        qs = RevenueDailySummary.objects.filter(ad_network__isnull=False)
        if tenant:
            qs = qs.filter(tenant=tenant)
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return (
            qs.values('ad_network__display_name', 'ad_network__network_type')
            .annotate(total=Sum('total_revenue'))
            .order_by('-total')[:limit]
        )


# ===========================================================================
# Subscription Repository
# ===========================================================================

class SubscriptionRepository:

    @staticmethod
    def active_for_user(user):
        from .models import UserSubscription
        return UserSubscription.objects.filter(
            user=user, status__in=['trial', 'active']
        ).select_related('plan').first()

    @staticmethod
    def expiring_soon(hours: int = 24):
        from .models import UserSubscription
        now     = timezone.now()
        cutoff  = now + timezone.timedelta(hours=hours)
        return UserSubscription.objects.filter(
            status='active',
            current_period_end__lte=cutoff,
            current_period_end__gt=now,
            is_auto_renew=True,
        ).select_related('user', 'plan')

    @staticmethod
    def count_by_plan(tenant=None) -> list:
        from .models import UserSubscription
        qs = UserSubscription.objects.filter(status='active')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('plan__name').annotate(count=Count('id')).order_by('-count')
        )


# ===========================================================================
# Payment Repository
# ===========================================================================

class PaymentRepository:

    @staticmethod
    def get_by_gateway_ref(gateway: str, gateway_txn_id: str):
        from .models import PaymentTransaction
        return PaymentTransaction.objects.filter(
            gateway=gateway, gateway_txn_id=gateway_txn_id
        ).first()

    @staticmethod
    def recent_for_user(user, limit: int = 20):
        from .models import PaymentTransaction
        return PaymentTransaction.objects.filter(user=user).order_by('-initiated_at')[:limit]

    @staticmethod
    def failed_today(tenant=None):
        from .models import PaymentTransaction
        qs = PaymentTransaction.objects.filter(
            status='failed', initiated_at__date=timezone.now().date()
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


# ===========================================================================
# Leaderboard Repository
# ===========================================================================

class LeaderboardRepository:

    @staticmethod
    def top_n(scope: str, board_type: str, n: int = 50, period_label: str = None):
        from .models import LeaderboardRank
        qs = LeaderboardRank.objects.filter(
            scope=scope, board_type=board_type
        ).select_related('user')
        if period_label:
            qs = qs.filter(period_label=period_label)
        return qs.order_by('rank')[:n]

    @staticmethod
    def user_rank(user, scope: str, board_type: str, period_label: str = None):
        from .models import LeaderboardRank
        qs = LeaderboardRank.objects.filter(
            user=user, scope=scope, board_type=board_type
        )
        if period_label:
            qs = qs.filter(period_label=period_label)
        return qs.first()


# ===========================================================================
# ABTest Repository
# ===========================================================================

class ABTestRepository:

    @staticmethod
    def running(tenant=None):
        from .models import ABTest
        qs = ABTest.objects.filter(status='running')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def get_for_ad_unit(ad_unit_id):
        """Return running A/B tests that include the given ad_unit in their variants."""
        from .models import ABTest
        tests = ABTest.objects.filter(status='running')
        return [
            t for t in tests
            if any(str(v.get('ad_unit_id')) == str(ad_unit_id) for v in (t.variants or []))
        ]


# ===========================================================================
# PostbackLog Repository
# ===========================================================================

class PostbackRepository:

    @staticmethod
    def get_unprocessed(limit: int = 500):
        from .models import PostbackLog
        return PostbackLog.objects.filter(status='received').order_by('received_at')[:limit]

    @staticmethod
    def get_by_network_txn(network_name: str, txn_id: str):
        from .models import PostbackLog
        return PostbackLog.objects.filter(
            network_name=network_name, network_txn_id=txn_id
        ).first()

    @staticmethod
    def fraud_ips(threshold: int = 10, days: int = 1):
        from .models import PostbackLog
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return (
            PostbackLog.objects.filter(
                status__in=['rejected', 'fraud'], received_at__gte=cutoff
            )
            .values('source_ip')
            .annotate(count=Count('id'))
            .filter(count__gte=threshold)
            .order_by('-count')
        )

    @staticmethod
    def status_summary(tenant=None) -> dict:
        from .models import PostbackLog
        from django.db.models import Count
        qs = PostbackLog.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return dict(qs.values_list('status').annotate(count=Count('id')))


# ===========================================================================
# PayoutRepository
# ===========================================================================

class PayoutRepository:

    @staticmethod
    def pending(tenant=None):
        from .models import PayoutRequest
        qs = PayoutRequest.objects.filter(status='pending').select_related('user', 'payout_method')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('created_at')

    @staticmethod
    def for_user(user, status: str = None):
        from .models import PayoutRequest
        qs = PayoutRequest.objects.filter(user=user).select_related('payout_method')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')

    @staticmethod
    def total_paid_usd(tenant=None) -> 'Decimal':
        from .models import PayoutRequest
        from django.db.models import Sum
        from decimal import Decimal
        qs = PayoutRequest.objects.filter(status='paid')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.aggregate(t=Sum('net_amount'))['t'] or Decimal('0.00')

    @staticmethod
    def methods_for_user(user, verified_only: bool = False):
        from .models import PayoutMethod
        qs = PayoutMethod.objects.filter(user=user, is_active=True)
        if verified_only:
            qs = qs.filter(is_verified=True)
        return qs.order_by('-is_default', '-created_at')


# ===========================================================================
# ReferralRepository
# ===========================================================================

class ReferralRepository:

    @staticmethod
    def active_program(tenant=None):
        from .models import ReferralProgram
        from django.utils import timezone
        now = timezone.now()
        qs  = ReferralProgram.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        qs = qs.filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )
        return qs.first()

    @staticmethod
    def link_for_user(user, program):
        from .models import ReferralLink
        return ReferralLink.objects.filter(user=user, program=program, is_active=True).first()

    @staticmethod
    def commission_summary(user) -> dict:
        from .models import ReferralCommission
        from django.db.models import Sum, Count
        qs = ReferralCommission.objects.filter(referrer=user)
        return qs.aggregate(
            total_earned=Sum('commission_coins'),
            total_referrals=Count('referee', distinct=True),
            unpaid=Sum('commission_coins', filter=models.Q(is_paid=False)),
        )

    @staticmethod
    def top_referrers(tenant=None, limit: int = 20):
        from .models import ReferralCommission
        from django.db.models import Sum, Count
        qs = ReferralCommission.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return (
            qs.values('referrer__username', 'referrer_id')
              .annotate(total=Sum('commission_coins'), refs=Count('referee', distinct=True))
              .order_by('-total')[:limit]
        )


# ===========================================================================
# FraudAlertRepository
# ===========================================================================

class FraudAlertRepository:

    @staticmethod
    def open_for_user(user):
        from .models import FraudAlert
        return FraudAlert.objects.filter(user=user, resolution='open').order_by('-created_at')

    @staticmethod
    def critical_unresolved(tenant=None):
        from .models import FraudAlert
        qs = FraudAlert.objects.filter(severity='critical', resolution__in=['open', 'reviewing'])
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related('user').order_by('-created_at')

    @staticmethod
    def dashboard_stats(tenant=None) -> dict:
        from .models import FraudAlert
        from django.db.models import Count
        from django.utils import timezone
        qs = FraudAlert.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'open':              qs.filter(resolution='open').count(),
            'critical_open':     qs.filter(severity='critical', resolution='open').count(),
            'today':             qs.filter(created_at__date=timezone.now().date()).count(),
            'blocked_users':     qs.filter(user_blocked=True).values('user').distinct().count(),
        }


# ===========================================================================
# FlashSaleRepository
# ===========================================================================

class FlashSaleRepository:

    @staticmethod
    def live_now(tenant=None):
        from .models import FlashSale
        from django.utils import timezone
        now = timezone.now()
        qs  = FlashSale.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-multiplier')

    @staticmethod
    def best_multiplier(tenant=None, offer_type: str = None) -> 'Decimal':
        from decimal import Decimal
        qs = FlashSaleRepository.live_now(tenant).filter(
            sale_type__in=['offer_boost', 'double_points']
        )
        if offer_type:
            qs = qs.filter(
                models.Q(target_offer_types=[]) |
                models.Q(target_offer_types__contains=[offer_type])
            )
        result = qs.order_by('-multiplier').values_list('multiplier', flat=True).first()
        return result or Decimal('1.00')


# ===========================================================================
# CouponRepository
# ===========================================================================

class CouponRepository:

    @staticmethod
    def get_valid(code: str):
        from .models import Coupon
        from django.utils import timezone
        now = timezone.now()
        return Coupon.objects.filter(
            code__iexact=code, is_active=True
        ).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=now)
        ).filter(
            models.Q(max_uses=0) | models.Q(current_uses__lt=models.F('max_uses'))
        ).first()

    @staticmethod
    def usage_count(coupon, user) -> int:
        from .models import CouponUsage
        return CouponUsage.objects.filter(coupon=coupon, user=user).count()

    @staticmethod
    def expiring_soon(tenant=None, hours: int = 48):
        from .models import Coupon
        from django.utils import timezone
        from datetime import timedelta
        now    = timezone.now()
        cutoff = now + timedelta(hours=hours)
        qs = Coupon.objects.filter(is_active=True, valid_until__lte=cutoff, valid_until__gt=now)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


# ===========================================================================
# SegmentRepository
# ===========================================================================

class SegmentRepository:

    @staticmethod
    def active_segments(tenant=None):
        from .models import UserSegment
        qs = UserSegment.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('name')

    @staticmethod
    def user_segments(user):
        from .models import UserSegmentMembership
        from django.utils import timezone
        return UserSegmentMembership.objects.filter(
            user=user,
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=timezone.now())
        ).select_related('segment').values_list('segment__slug', flat=True)

    @staticmethod
    def add_user(segment, user, score: float = 0.0) -> bool:
        from .models import UserSegmentMembership
        from django.db.models import F
        _, created = UserSegmentMembership.objects.get_or_create(
            segment=segment, user=user,
            defaults={'tenant': segment.tenant, 'score': score},
        )
        if created:
            from .models import UserSegment
            UserSegment.objects.filter(pk=segment.pk).update(
                member_count=F('member_count') + 1
            )
        return created
