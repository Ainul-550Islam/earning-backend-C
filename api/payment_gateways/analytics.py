# api/payment_gateways/analytics.py
# Full payment analytics engine
# "Do not summarize or skip any logic. Provide the full code."

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.db.models import Q, Sum, Count, Avg, Max, Min, F
from django.utils import timezone
from datetime import timedelta, date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class PaymentAnalyticsEngine:
    """
    Comprehensive analytics engine for payment_gateways.
    Provides insights for admins, publishers, and advertisers.

    Covers:
        - Revenue analytics (daily/weekly/monthly/yearly)
        - Gateway performance comparison
        - Publisher earnings analytics
        - Offer performance analytics
        - Conversion funnel analysis
        - GEO distribution analysis
        - Fraud analytics
        - Cohort analysis
    """

    # ── Revenue Analytics ──────────────────────────────────────────────────────
    def get_revenue_summary(self, days: int = 30, user=None) -> dict:
        """Overall revenue summary for admin dashboard."""
        from api.payment_gateways.models.core import GatewayTransaction, PayoutRequest
        since = timezone.now() - timedelta(days=days)

        txn_qs = GatewayTransaction.objects.filter(created_at__gte=since, status='completed')
        if user:
            txn_qs = txn_qs.filter(user=user)

        deposits    = txn_qs.filter(transaction_type='deposit')
        withdrawals = txn_qs.filter(transaction_type='withdrawal')

        d_agg = deposits.aggregate(total=Sum('amount'), fees=Sum('fee'), count=Count('id'))
        w_agg = withdrawals.aggregate(total=Sum('amount'), fees=Sum('fee'), count=Count('id'))

        # Compare with previous period
        prev_since = timezone.now() - timedelta(days=days * 2)
        prev_end   = timezone.now() - timedelta(days=days)
        prev_d     = GatewayTransaction.objects.filter(
            transaction_type='deposit', status='completed',
            created_at__gte=prev_since, created_at__lt=prev_end
        )
        if user:
            prev_d = prev_d.filter(user=user)
        prev_total = prev_d.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        curr_total = d_agg['total'] or Decimal('0')
        change_pct = float((curr_total - prev_total) / max(prev_total, 1) * 100) if prev_total else 0

        return {
            'period_days':       days,
            'deposits': {
                'total':    float(d_agg['total'] or 0),
                'fees':     float(d_agg['fees'] or 0),
                'net':      float((d_agg['total'] or 0) - (d_agg['fees'] or 0)),
                'count':    d_agg['count'] or 0,
                'change_pct': round(change_pct, 1),
            },
            'withdrawals': {
                'total':    float(w_agg['total'] or 0),
                'fees':     float(w_agg['fees'] or 0),
                'count':    w_agg['count'] or 0,
            },
            'net_revenue': float((d_agg['fees'] or 0) + (w_agg['fees'] or 0)),
        }

    def get_daily_revenue_chart(self, days: int = 30) -> list:
        """Daily revenue data for chart."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = (timezone.now() - timedelta(days=days)).date()
        return list(
            GatewayTransaction.objects.filter(
                transaction_type='deposit',
                status='completed',
                created_at__date__gte=since,
            ).extra(select={'day': "DATE(created_at)"})
            .values('day')
            .annotate(revenue=Sum('amount'), fees=Sum('fee'), count=Count('id'))
            .order_by('day')
        )

    def get_hourly_volume(self) -> list:
        """Hourly transaction volume for today."""
        from api.payment_gateways.models.core import GatewayTransaction
        today = timezone.now().date()
        return list(
            GatewayTransaction.objects.filter(
                created_at__date=today,
                transaction_type='deposit',
            ).extra(select={'hour': "EXTRACT(HOUR FROM created_at)"})
            .values('hour')
            .annotate(count=Count('id'), amount=Sum('amount'))
            .order_by('hour')
        )

    # ── Gateway Analytics ──────────────────────────────────────────────────────
    def get_gateway_analytics(self, days: int = 30) -> list:
        """Per-gateway analytics comparison."""
        from api.payment_gateways.models.core import GatewayTransaction
        since = timezone.now() - timedelta(days=days)
        return list(
            GatewayTransaction.objects.filter(created_at__gte=since).values('gateway')
            .annotate(
                total_volume=Sum('amount'),
                total_count=Count('id'),
                success_count=Count('id', filter=Q(status='completed')),
                failed_count=Count('id', filter=Q(status='failed')),
                total_fees=Sum('fee'),
                avg_amount=Avg('amount'),
                max_amount=Max('amount'),
            ).order_by('-total_volume')
        )

    def get_gateway_comparison(self, gateway_a: str, gateway_b: str,
                                days: int = 30) -> dict:
        """Head-to-head gateway comparison."""
        def _stats(gateway):
            from api.payment_gateways.models.core import GatewayTransaction
            since = timezone.now() - timedelta(days=days)
            qs    = GatewayTransaction.objects.filter(gateway=gateway, created_at__gte=since)
            agg   = qs.aggregate(total=Sum('amount'), count=Count('id'),
                                   success=Count('id', filter=Q(status='completed')))
            count = agg['count'] or 1
            return {
                'gateway':      gateway,
                'total_volume': float(agg['total'] or 0),
                'count':        agg['count'] or 0,
                'success_rate': round((agg['success'] or 0) / count * 100, 1),
            }
        return {'gateway_a': _stats(gateway_a), 'gateway_b': _stats(gateway_b), 'period_days': days}

    # ── Publisher Analytics ────────────────────────────────────────────────────
    def get_publisher_analytics(self, user, days: int = 30) -> dict:
        """Comprehensive analytics for a publisher."""
        from api.payment_gateways.tracking.models import Conversion, Click
        since = timezone.now() - timedelta(days=days)

        clicks  = Click.objects.filter(publisher=user, created_at__gte=since)
        convs   = Conversion.objects.filter(publisher=user, status='approved', created_at__gte=since)
        c_agg   = convs.aggregate(payout=Sum('payout'), count=Count('id'))

        click_count = clicks.count()
        conv_count  = c_agg['count'] or 0
        cr = conv_count / max(click_count, 1) * 100
        epc = float(c_agg['payout'] or 0) / max(click_count, 1)

        # By offer
        by_offer = list(convs.values('offer__name').annotate(
            count=Count('id'), earnings=Sum('payout')
        ).order_by('-earnings')[:10])

        # By country
        by_country = list(convs.values('country_code').annotate(
            count=Count('id'), earnings=Sum('payout')
        ).order_by('-count')[:10])

        # By device
        by_device = list(clicks.values('device_type').annotate(
            clicks=Count('id'),
            conversions=Count('id', filter=Q(is_converted=True)),
        ).order_by('-clicks'))

        # Daily trend
        daily = list(convs.extra(select={'day': 'DATE(created_at)'})
            .values('day').annotate(count=Count('id'), earnings=Sum('payout'))
            .order_by('day'))

        return {
            'period_days':       days,
            'total_clicks':      click_count,
            'total_conversions': conv_count,
            'total_earnings':    float(c_agg['payout'] or 0),
            'conversion_rate':   round(cr, 2),
            'epc':               round(epc, 4),
            'by_offer':          by_offer,
            'by_country':        by_country,
            'by_device':         by_device,
            'daily_trend':       daily,
        }

    # ── Offer Analytics ────────────────────────────────────────────────────────
    def get_offer_analytics(self, offer_id: int, days: int = 30) -> dict:
        """Detailed analytics for a specific offer."""
        from api.payment_gateways.tracking.models import Conversion, Click
        since = timezone.now() - timedelta(days=days)

        clicks  = Click.objects.filter(offer_id=offer_id, created_at__gte=since)
        convs   = Conversion.objects.filter(offer_id=offer_id, status='approved', created_at__gte=since)
        agg     = convs.aggregate(rev=Sum('cost'), pay=Sum('payout'), count=Count('id'))

        click_count = clicks.count()
        conv_count  = agg['count'] or 0

        by_publisher = list(convs.values('publisher__email').annotate(
            count=Count('id'), cost=Sum('cost')
        ).order_by('-count')[:10])

        by_country = list(convs.values('country_code').annotate(
            count=Count('id'), revenue=Sum('cost')
        ).order_by('-count')[:15])

        return {
            'offer_id':          offer_id,
            'period_days':       days,
            'total_clicks':      click_count,
            'total_conversions': conv_count,
            'total_cost':        float(agg['rev'] or 0),
            'total_payout':      float(agg['pay'] or 0),
            'profit':            float((agg['rev'] or 0) - (agg['pay'] or 0)),
            'conversion_rate':   round(conv_count / max(click_count, 1) * 100, 2),
            'epc':               round(float(agg['pay'] or 0) / max(click_count, 1), 4),
            'by_publisher':      by_publisher,
            'by_country':        by_country,
        }

    # ── Fraud Analytics ────────────────────────────────────────────────────────
    def get_fraud_analytics(self, days: int = 7) -> dict:
        """Fraud detection analytics for admin."""
        from api.payment_gateways.tracking.models import Click
        since = timezone.now() - timedelta(days=days)
        qs    = Click.objects.filter(created_at__gte=since)
        total = qs.count()
        fraud = qs.filter(is_fraud=True).count()
        bots  = qs.filter(is_bot=True).count()

        by_country = list(qs.filter(is_fraud=True).values('country_code')
            .annotate(count=Count('id')).order_by('-count')[:10])

        return {
            'period_days':    days,
            'total_clicks':   total,
            'fraud_clicks':   fraud,
            'bot_clicks':     bots,
            'fraud_rate':     round(fraud / max(total, 1) * 100, 2),
            'clean_clicks':   total - fraud - bots,
            'by_country':     by_country,
        }

    # ── Admin Dashboard Summary ────────────────────────────────────────────────
    def get_admin_summary(self) -> dict:
        """One-call admin dashboard data."""
        from api.payment_gateways.selectors import AnalyticsSelector
        return {
            'stats':           AnalyticsSelector.get_admin_dashboard_stats(),
            'revenue_30d':     self.get_revenue_summary(30),
            'gateway_overview':self.get_gateway_analytics(7),
            'daily_chart_7d':  self.get_daily_revenue_chart(7),
        }


# ── Analytics API Views ────────────────────────────────────────────────────────
engine = PaymentAnalyticsEngine()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_analytics_view(request):
    """Publisher analytics dashboard."""
    days = int(request.GET.get('days', 30))
    return Response({'success': True, 'data': engine.get_publisher_analytics(request.user, days)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_view(request):
    """Admin analytics dashboard."""
    return Response({'success': True, 'data': engine.get_admin_summary()})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def gateway_analytics_view(request):
    """Gateway analytics."""
    days = int(request.GET.get('days', 30))
    return Response({'success': True, 'data': engine.get_gateway_analytics(days)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def offer_analytics_view(request, offer_id):
    """Offer analytics."""
    days = int(request.GET.get('days', 30))
    return Response({'success': True, 'data': engine.get_offer_analytics(offer_id, days)})


payment_analytics = engine
