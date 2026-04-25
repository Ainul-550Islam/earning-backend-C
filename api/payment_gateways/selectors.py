# api/payment_gateways/selectors.py
# Read-only query selectors — clean architecture pattern
# Selectors encapsulate all DB read logic, keeping views/services thin.
# "Do not summarize or skip any logic. Provide the full code."

from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db.models import QuerySet, Sum, Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# GATEWAY SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class GatewaySelector:
    """All read queries for PaymentGateway model."""

    @staticmethod
    def get_all_active() -> QuerySet:
        """Return all active gateways ordered by sort_order."""
        from api.payment_gateways.models.core import PaymentGateway
        return PaymentGateway.objects.filter(status='active').order_by('sort_order')

    @staticmethod
    def get_deposit_gateways(region: str = None) -> QuerySet:
        """Return gateways that support deposits, optionally filtered by region."""
        from api.payment_gateways.models.core import PaymentGateway
        qs = PaymentGateway.objects.filter(status='active', supports_deposit=True)
        if region:
            qs = qs.filter(region=region.upper())
        return qs.order_by('sort_order')

    @staticmethod
    def get_withdrawal_gateways(region: str = None) -> QuerySet:
        """Return gateways that support withdrawals."""
        from api.payment_gateways.models.core import PaymentGateway
        qs = PaymentGateway.objects.filter(status='active', supports_withdrawal=True)
        if region:
            qs = qs.filter(region=region.upper())
        return qs.order_by('sort_order')

    @staticmethod
    def get_by_name(name: str):
        """Get gateway by name. Returns None if not found."""
        from api.payment_gateways.models.core import PaymentGateway
        try:
            return PaymentGateway.objects.get(name=name.lower())
        except PaymentGateway.DoesNotExist:
            return None

    @staticmethod
    def get_healthy_gateways() -> QuerySet:
        """Return gateways with healthy status."""
        from api.payment_gateways.models.core import PaymentGateway
        return PaymentGateway.objects.filter(
            status='active',
            health_status__in=('healthy', 'unknown'),
        )

    @staticmethod
    def get_bd_gateways() -> QuerySet:
        """Return Bangladesh-specific gateways."""
        return GatewaySelector.get_all_active().filter(region='BD')

    @staticmethod
    def get_global_gateways() -> QuerySet:
        """Return international gateways."""
        return GatewaySelector.get_all_active().filter(region__in=('GLOBAL', 'US'))

    @staticmethod
    def get_health_summary() -> Dict[str, str]:
        """Return {gateway_name: health_status} dict."""
        from api.payment_gateways.models.core import PaymentGateway
        return dict(
            PaymentGateway.objects.values_list('name', 'health_status')
        )


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class TransactionSelector:
    """All read queries for GatewayTransaction model."""

    @staticmethod
    def get_for_user(user, limit: int = None) -> QuerySet:
        """Get all transactions for a user, newest first."""
        from api.payment_gateways.models.core import GatewayTransaction
        qs = GatewayTransaction.objects.filter(user=user).order_by('-created_at')
        return qs[:limit] if limit else qs

    @staticmethod
    def get_completed_for_user(user) -> QuerySet:
        """Get completed transactions for a user."""
        from api.payment_gateways.models.core import GatewayTransaction
        return GatewayTransaction.objects.filter(
            user=user, status='completed'
        ).order_by('-created_at')

    @staticmethod
    def get_by_reference(reference_id: str):
        """Get transaction by reference ID."""
        from api.payment_gateways.models.core import GatewayTransaction
        try:
            return GatewayTransaction.objects.get(reference_id=reference_id)
        except GatewayTransaction.DoesNotExist:
            return None

    @staticmethod
    def get_today_stats(user=None) -> dict:
        """Get today's transaction aggregates."""
        from api.payment_gateways.models.core import GatewayTransaction
        qs = GatewayTransaction.objects.filter(
            created_at__date=timezone.now().date(),
            status='completed',
        )
        if user:
            qs = qs.filter(user=user)
        return qs.aggregate(
            deposits=Sum('amount', filter=Q(transaction_type='deposit')),
            withdrawals=Sum('amount', filter=Q(transaction_type='withdrawal')),
            count=Count('id'),
            total_fees=Sum('fee'),
        )

    @staticmethod
    def get_pending_count(user=None) -> int:
        """Count pending/processing transactions."""
        from api.payment_gateways.models.core import GatewayTransaction
        qs = GatewayTransaction.objects.filter(status__in=('pending', 'processing'))
        if user:
            qs = qs.filter(user=user)
        return qs.count()

    @staticmethod
    def get_failed_today() -> QuerySet:
        """Get failed transactions from today."""
        from api.payment_gateways.models.core import GatewayTransaction
        return GatewayTransaction.objects.filter(
            status='failed',
            created_at__date=timezone.now().date(),
        ).select_related('user').order_by('-created_at')

    @staticmethod
    def get_success_rate(gateway: str, days: int = 7) -> float:
        """Calculate success rate for a gateway over N days."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = timezone.now() - timedelta(days=days)
        qs    = GatewayTransaction.objects.filter(gateway=gateway, created_at__gte=since)
        total = qs.count()
        if not total:
            return 0.0
        success = qs.filter(status='completed').count()
        return round(success / total * 100, 2)

    @staticmethod
    def get_volume_by_gateway(days: int = 30) -> list:
        """Get transaction volume grouped by gateway."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = timezone.now() - timedelta(days=days)
        return list(
            GatewayTransaction.objects.filter(
                created_at__gte=since, status='completed'
            ).values('gateway').annotate(
                total=Sum('amount'),
                count=Count('id'),
                avg=Avg('amount'),
            ).order_by('-total')
        )

    @staticmethod
    def get_recent_for_admin(limit: int = 50) -> QuerySet:
        """Get recent transactions for admin dashboard."""
        from api.payment_gateways.models.core import GatewayTransaction
        return GatewayTransaction.objects.select_related('user').order_by('-created_at')[:limit]


# ══════════════════════════════════════════════════════════════════════════════
# DEPOSIT SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class DepositSelector:
    """All read queries for DepositRequest model."""

    @staticmethod
    def get_pending(user=None) -> QuerySet:
        """Get pending deposits."""
        from api.payment_gateways.models.deposit import DepositRequest
        qs = DepositRequest.objects.filter(status__in=('initiated', 'pending'))
        if user:
            qs = qs.filter(user=user)
        return qs.order_by('-initiated_at')

    @staticmethod
    def get_by_gateway_ref(gateway_ref: str):
        """Get deposit by gateway's reference number."""
        from api.payment_gateways.models.deposit import DepositRequest
        try:
            return DepositRequest.objects.get(gateway_ref=gateway_ref)
        except DepositRequest.DoesNotExist:
            return None

    @staticmethod
    def get_by_reference(reference_id: str):
        """Get deposit by internal reference ID."""
        from api.payment_gateways.models.deposit import DepositRequest
        try:
            return DepositRequest.objects.get(reference_id=reference_id)
        except DepositRequest.DoesNotExist:
            return None

    @staticmethod
    def get_stuck_pending(minutes: int = 15) -> QuerySet:
        """Get deposits stuck in pending state longer than N minutes."""
        from api.payment_gateways.models.deposit import DepositRequest
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return DepositRequest.objects.filter(
            status__in=('initiated', 'pending'),
            initiated_at__lte=cutoff,
        ).select_related('user')

    @staticmethod
    def get_today_total(user=None) -> Decimal:
        """Get total deposits completed today."""
        from api.payment_gateways.models.deposit import DepositRequest
        qs = DepositRequest.objects.filter(
            status='completed', completed_at__date=timezone.now().date()
        )
        if user:
            qs = qs.filter(user=user)
        return qs.aggregate(t=Sum('net_amount'))['t'] or Decimal('0')

    @staticmethod
    def get_for_user(user, status: str = None) -> QuerySet:
        """Get deposits for a user."""
        from api.payment_gateways.models.deposit import DepositRequest
        qs = DepositRequest.objects.filter(user=user).order_by('-initiated_at')
        if status:
            qs = qs.filter(status=status)
        return qs


# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class PayoutSelector:
    """All read queries for PayoutRequest model."""

    @staticmethod
    def get_pending_for_admin() -> QuerySet:
        """Get all pending payout requests for admin processing."""
        from api.payment_gateways.models.core import PayoutRequest
        return PayoutRequest.objects.filter(
            status='pending'
        ).select_related('user').order_by('created_at')

    @staticmethod
    def get_approved_unprocessed() -> QuerySet:
        """Get approved payouts not yet sent to gateway."""
        from api.payment_gateways.models.core import PayoutRequest
        return PayoutRequest.objects.filter(status='approved').order_by('created_at')

    @staticmethod
    def get_for_user(user) -> QuerySet:
        """Get all payouts for a user."""
        from api.payment_gateways.models.core import PayoutRequest
        return PayoutRequest.objects.filter(user=user).order_by('-created_at')

    @staticmethod
    def get_total_paid_to_user(user) -> Decimal:
        """Total amount paid out to a publisher."""
        from api.payment_gateways.models.core import PayoutRequest
        return PayoutRequest.objects.filter(
            user=user, status='completed'
        ).aggregate(t=Sum('net_amount'))['t'] or Decimal('0')

    @staticmethod
    def get_pending_amount() -> Decimal:
        """Total pending payout amount across all publishers."""
        from api.payment_gateways.models.core import PayoutRequest
        return PayoutRequest.objects.filter(
            status__in=('pending', 'approved')
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    @staticmethod
    def get_daily_payout_total(date=None) -> Decimal:
        """Total payouts processed on a given date."""
        from api.payment_gateways.models.core import PayoutRequest
        target = date or timezone.now().date()
        return PayoutRequest.objects.filter(
            status='completed',
            processed_at__date=target,
        ).aggregate(t=Sum('net_amount'))['t'] or Decimal('0')

    @staticmethod
    def get_fast_pay_eligible_users() -> QuerySet:
        """Get users eligible for Fast Pay."""
        from api.payment_gateways.publisher.models import PublisherProfile
        return PublisherProfile.objects.filter(
            is_fast_pay_eligible=True,
            status='active',
        ).select_related('user')


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISHER SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class PublisherSelector:
    """All read queries for publisher-related models."""

    @staticmethod
    def get_active() -> QuerySet:
        """Get all active publishers."""
        from api.payment_gateways.publisher.models import PublisherProfile
        return PublisherProfile.objects.filter(status='active').select_related('user')

    @staticmethod
    def get_by_user(user):
        """Get publisher profile for a user."""
        from api.payment_gateways.publisher.models import PublisherProfile
        try:
            return PublisherProfile.objects.get(user=user)
        except PublisherProfile.DoesNotExist:
            return None

    @staticmethod
    def get_top_earners(limit: int = 20, days: int = 30) -> list:
        """Get top earning publishers for leaderboard."""
        from api.payment_gateways.tracking.models import Conversion
        since = timezone.now() - timedelta(days=days)
        return list(
            Conversion.objects.filter(
                status='approved', created_at__gte=since
            ).values('publisher__id', 'publisher__username', 'publisher__email')
            .annotate(
                total_earnings=Sum('payout'),
                total_conversions=Count('id'),
            ).order_by('-total_earnings')[:limit]
        )

    @staticmethod
    def get_publishers_needing_kyc() -> QuerySet:
        """Publishers with pending KYC verification."""
        from api.payment_gateways.publisher.models import PublisherProfile
        try:
            from api.kyc.models import KYCProfile
            verified_ids = KYCProfile.objects.filter(
                status='approved'
            ).values_list('user_id', flat=True)
            return PublisherProfile.objects.filter(
                status='active'
            ).exclude(user_id__in=verified_ids)
        except ImportError:
            return PublisherProfile.objects.none()

    @staticmethod
    def get_earnings_summary(user) -> dict:
        """Get earnings summary for a publisher."""
        from api.payment_gateways.tracking.models import Conversion
        from django.utils import timezone
        today = timezone.now().date()
        month = today.replace(day=1)
        qs    = Conversion.objects.filter(publisher=user, status='approved')
        return {
            'today':    float(qs.filter(created_at__date=today).aggregate(t=Sum('payout'))['t'] or 0),
            'this_month': float(qs.filter(created_at__date__gte=month).aggregate(t=Sum('payout'))['t'] or 0),
            'all_time': float(qs.aggregate(t=Sum('payout'))['t'] or 0),
            'count':    qs.count(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# OFFER SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class OfferSelector:
    """All read queries for Offer model."""

    @staticmethod
    def get_active(limit: int = None) -> QuerySet:
        """Get all active offers ordered by EPC."""
        from api.payment_gateways.offers.models import Offer
        qs = Offer.objects.filter(status='active').order_by('-epc')
        return qs[:limit] if limit else qs

    @staticmethod
    def get_for_publisher(publisher, country: str = '', device: str = '') -> QuerySet:
        """Get offers available to a specific publisher."""
        from api.payment_gateways.offers.models import Offer
        qs = Offer.objects.filter(status='active').filter(
            Q(is_public=True) | Q(allowed_publishers=publisher)
        ).exclude(blocked_publishers=publisher)
        if country:
            qs = qs.filter(
                Q(target_countries=[]) | Q(target_countries__contains=[country.upper()])
            ).exclude(blocked_countries__contains=[country.upper()])
        if device:
            qs = qs.filter(
                Q(target_devices=[]) | Q(target_devices__contains=[device.lower()])
            )
        return qs.order_by('-epc')

    @staticmethod
    def get_by_id(offer_id: int):
        """Get offer by ID."""
        from api.payment_gateways.offers.models import Offer
        try:
            return Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return None

    @staticmethod
    def get_top_by_epc(limit: int = 10, offer_type: str = None) -> QuerySet:
        """Get top performing offers by EPC."""
        from api.payment_gateways.offers.models import Offer
        qs = Offer.objects.filter(status='active')
        if offer_type:
            qs = qs.filter(offer_type=offer_type)
        return qs.order_by('-epc')[:limit]

    @staticmethod
    def get_capping_soon(threshold: float = 0.80) -> list:
        """Get offers approaching their daily/total caps."""
        from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
        from api.payment_gateways.offers.models import Offer
        engine    = ConversionCapEngine()
        capping   = []
        offers_with_cap = Offer.objects.filter(
            status='active'
        ).filter(
            Q(daily_cap__isnull=False) | Q(total_cap__isnull=False)
        )
        for offer in offers_with_cap[:100]:
            status = engine.get_cap_status(offer)
            daily_pct = status.get('daily_pct_used', 0) or 0
            if daily_pct and daily_pct >= threshold * 100:
                capping.append({'offer': offer, 'pct_used': daily_pct})
        return capping


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSION SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class ConversionSelector:
    """All read queries for Conversion model."""

    @staticmethod
    def get_pending() -> QuerySet:
        """Get pending conversions awaiting approval."""
        from api.payment_gateways.tracking.models import Conversion
        return Conversion.objects.filter(status='pending').select_related('publisher', 'offer')

    @staticmethod
    def get_for_publisher(publisher, days: int = None) -> QuerySet:
        """Get approved conversions for a publisher."""
        from api.payment_gateways.tracking.models import Conversion
        qs = Conversion.objects.filter(publisher=publisher, status='approved')
        if days:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
        return qs.order_by('-created_at')

    @staticmethod
    def get_unpaid_for_publisher(publisher) -> QuerySet:
        """Get approved but unpaid conversions."""
        from api.payment_gateways.tracking.models import Conversion
        return Conversion.objects.filter(
            publisher=publisher, status='approved', publisher_paid=False
        )

    @staticmethod
    def get_today_count(publisher=None) -> int:
        """Count today's approved conversions."""
        from api.payment_gateways.tracking.models import Conversion
        qs = Conversion.objects.filter(
            status='approved', created_at__date=timezone.now().date()
        )
        if publisher:
            qs = qs.filter(publisher=publisher)
        return qs.count()

    @staticmethod
    def get_stats_by_country(publisher=None, days: int = 30) -> list:
        """Get conversion stats grouped by country."""
        from api.payment_gateways.tracking.models import Conversion
        since = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(status='approved', created_at__gte=since)
        if publisher:
            qs = qs.filter(publisher=publisher)
        return list(
            qs.values('country_code').annotate(
                count=Count('id'), revenue=Sum('payout')
            ).order_by('-count')[:20]
        )


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS SELECTORS
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsSelector:
    """Read queries for analytics and reporting."""

    @staticmethod
    def get_daily_revenue(days: int = 30) -> list:
        """Daily revenue for the past N days."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = timezone.now().date() - timedelta(days=days)
        return list(
            GatewayTransaction.objects.filter(
                status='completed',
                transaction_type='deposit',
                created_at__date__gte=since,
            ).values('created_at__date').annotate(
                revenue=Sum('net_amount'),
                count=Count('id'),
            ).order_by('created_at__date')
        )

    @staticmethod
    def get_gateway_comparison(days: int = 30) -> list:
        """Compare gateway performance metrics."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = timezone.now() - timedelta(days=days)
        return list(
            GatewayTransaction.objects.filter(created_at__gte=since).values(
                'gateway'
            ).annotate(
                total=Sum('amount'),
                success=Count('id', filter=Q(status='completed')),
                failed=Count('id', filter=Q(status='failed')),
                total_count=Count('id'),
                avg_amount=Avg('amount'),
                total_fees=Sum('fee'),
            ).order_by('-total')
        )

    @staticmethod
    def get_admin_dashboard_stats() -> dict:
        """Aggregate stats for admin dashboard."""
        from api.payment_gateways.models.core import GatewayTransaction, PayoutRequest
        today  = timezone.now().date()
        month  = today.replace(day=1)

        today_deposits  = GatewayTransaction.objects.filter(
            created_at__date=today, status='completed', transaction_type='deposit'
        ).aggregate(t=Sum('amount'), c=Count('id'))

        today_withdrawals = GatewayTransaction.objects.filter(
            created_at__date=today, status='completed', transaction_type='withdrawal'
        ).aggregate(t=Sum('amount'), c=Count('id'))

        pending_payouts = PayoutRequest.objects.filter(
            status__in=('pending', 'approved')
        ).aggregate(t=Sum('amount'), c=Count('id'))

        monthly_revenue = GatewayTransaction.objects.filter(
            created_at__date__gte=month, status='completed', transaction_type='deposit'
        ).aggregate(t=Sum('net_amount'))

        return {
            'today_deposits':         float(today_deposits['t'] or 0),
            'today_deposit_count':    today_deposits['c'] or 0,
            'today_withdrawals':      float(today_withdrawals['t'] or 0),
            'today_withdrawal_count': today_withdrawals['c'] or 0,
            'pending_payout_amount':  float(pending_payouts['t'] or 0),
            'pending_payout_count':   pending_payouts['c'] or 0,
            'monthly_revenue':        float(monthly_revenue['t'] or 0),
        }
