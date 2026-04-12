# api/offer_inventory/analytics.py
"""
Real-time analytics service।
Click, Conversion, Revenue tracking।
"""
import logging
from decimal import Decimal
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import (
    Sum, Count, Avg, Q, F,
    ExpressionWrapper, DecimalField, FloatField
)
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OfferAnalytics:

    @staticmethod
    def get_summary(tenant=None, days: int = 7) -> dict:
        """Dashboard summary stats।"""
        from .models import DailyStat
        since = timezone.now().date() - timedelta(days=days)
        qs = DailyStat.objects.filter(date__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)

        agg = qs.aggregate(
            total_clicks=Sum('total_clicks'),
            total_conversions=Sum('total_conversions'),
            approved_conversions=Sum('approved_conversions'),
            total_revenue=Sum('total_revenue'),
            user_payouts=Sum('user_payouts'),
            platform_profit=Sum('platform_profit'),
            new_users=Sum('new_users'),
            fraud_attempts=Sum('fraud_attempts'),
        )
        clicks = agg['total_clicks'] or 0
        convs  = agg['approved_conversions'] or 0
        return {
            **{k: float(v or 0) for k, v in agg.items()},
            'cvr': round((convs / clicks * 100), 2) if clicks > 0 else 0,
            'epc': round(float(agg['total_revenue'] or 0) / clicks, 4) if clicks > 0 else 0,
            'period_days': days,
        }

    @staticmethod
    def get_offer_stats(offer_id: str, days: int = 30) -> dict:
        """Single offer performance।"""
        from .models import Click, Conversion
        since = timezone.now() - timedelta(days=days)

        clicks = Click.objects.filter(offer_id=offer_id, created_at__gte=since)
        convs  = Conversion.objects.filter(
            offer_id=offer_id, created_at__gte=since, status__name='approved'
        )

        click_count = clicks.count()
        conv_count  = convs.count()
        revenue_agg = convs.aggregate(total=Sum('payout_amount'))
        total_rev   = float(revenue_agg['total'] or 0)

        return {
            'offer_id'         : offer_id,
            'total_clicks'     : click_count,
            'unique_clicks'    : clicks.values('ip_address').distinct().count(),
            'total_conversions': conv_count,
            'cvr'              : round(conv_count / click_count * 100, 2) if click_count else 0,
            'total_revenue'    : total_rev,
            'epc'              : round(total_rev / click_count, 4) if click_count else 0,
            'fraud_clicks'     : clicks.filter(is_fraud=True).count(),
            'period_days'      : days,
        }

    @staticmethod
    def get_geo_breakdown(days: int = 7) -> list:
        """Country-wise click/conversion।"""
        from .models import Click
        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since)
            .exclude(country_code='')
            .values('country_code')
            .annotate(
                clicks=Count('id'),
                conversions=Count('conversion'),
                fraud_count=Count('id', filter=Q(is_fraud=True)),
            )
            .order_by('-clicks')[:20]
        )

    @staticmethod
    def get_device_breakdown(days: int = 7) -> list:
        """Device-wise stats।"""
        from .models import Click
        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since)
            .values('device_type')
            .annotate(count=Count('id'), converted=Count('conversion'))
            .order_by('-count')
        )

    @staticmethod
    def get_revenue_trend(tenant=None, days: int = 30) -> list:
        """Daily revenue trend।"""
        from .models import DailyStat
        since = timezone.now().date() - timedelta(days=days)
        qs = DailyStat.objects.filter(date__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values('date').annotate(
                revenue=Sum('total_revenue'),
                payouts=Sum('user_payouts'),
                profit =Sum('platform_profit'),
                clicks =Sum('total_clicks'),
                convs  =Sum('approved_conversions'),
            ).order_by('date')
        )

    @staticmethod
    def get_top_performers(metric: str = 'revenue', days: int = 7, limit: int = 10) -> list:
        """Top performing offers।"""
        from .models import Conversion
        since = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            created_at__gte=since, status__name='approved'
        ).values('offer__title', 'offer_id')

        if metric == 'revenue':
            return list(qs.annotate(value=Sum('payout_amount')).order_by('-value')[:limit])
        elif metric == 'conversions':
            return list(qs.annotate(value=Count('id')).order_by('-value')[:limit])
        return []

    @staticmethod
    def compute_network_epc(network_id: str, days: int = 7) -> Decimal:
        """Network EPC (Earnings Per Click)।"""
        from .models import Click, Conversion
        since = timezone.now() - timedelta(days=days)
        clicks = Click.objects.filter(offer__network_id=network_id, created_at__gte=since).count()
        revenue = Conversion.objects.filter(
            offer__network_id=network_id,
            created_at__gte=since,
            status__name='approved'
        ).aggregate(total=Sum('payout_amount'))['total'] or Decimal('0')

        if clicks == 0:
            return Decimal('0')
        return (Decimal(str(revenue)) / Decimal(str(clicks))).quantize(Decimal('0.0001'))


# ─────────────────────────────────────────────────────
# api/offer_inventory/reporting.py
# ─────────────────────────────────────────────────────

import csv
import io
from django.http import HttpResponse


class ReportExporter:
    """CSV/Excel report export।"""

    @staticmethod
    def export_conversions_csv(queryset) -> HttpResponse:
        """Conversion list → CSV।"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="conversions.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Offer', 'User', 'Status', 'Payout', 'Reward',
            'Country', 'Date', 'Transaction ID',
        ])
        for conv in queryset:
            writer.writerow([
                str(conv.id)[:8],
                conv.offer.title if conv.offer else '',
                conv.user.username if conv.user else '',
                conv.status.name if conv.status else '',
                conv.payout_amount,
                conv.reward_amount,
                conv.country_code,
                conv.created_at.strftime('%Y-%m-%d %H:%M'),
                conv.transaction_id,
            ])
        return response

    @staticmethod
    def export_withdrawals_csv(queryset) -> HttpResponse:
        """Withdrawal list → CSV।"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="withdrawals.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Reference', 'User', 'Amount', 'Fee', 'Net', 'Status', 'Provider', 'Date'])
        for wr in queryset:
            writer.writerow([
                wr.reference_no,
                wr.user.username if wr.user else '',
                wr.amount,
                wr.fee,
                wr.net_amount,
                wr.status,
                wr.payment_method.provider if wr.payment_method else '',
                wr.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
        return response

    @staticmethod
    def export_daily_stats_csv(queryset) -> HttpResponse:
        """Daily stats → CSV।"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="daily_stats.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Clicks', 'Unique Clicks', 'Conversions', 'Approved',
            'Revenue', 'Payouts', 'Profit', 'New Users', 'CVR%',
        ])
        for stat in queryset:
            writer.writerow([
                stat.date,
                stat.total_clicks,
                stat.unique_clicks,
                stat.total_conversions,
                stat.approved_conversions,
                stat.total_revenue,
                stat.user_payouts,
                stat.platform_profit,
                stat.new_users,
                stat.cvr,
            ])
        return response
