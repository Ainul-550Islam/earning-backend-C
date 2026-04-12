# api/offer_inventory/publisher_sdk/publisher_analytics.py
"""Publisher Analytics — Revenue and performance reporting for publishers."""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class PublisherAnalytics:
    """Full analytics suite for publishers."""

    @staticmethod
    def get_full_report(publisher_id: str, days: int = 30) -> dict:
        """Complete publisher revenue and performance report."""
        from api.offer_inventory.models import BidLog, PublisherRevenue
        from django.db.models import Count, Sum, Avg
        since = timezone.now() - timedelta(days=days)

        bids = BidLog.objects.filter(
            publisher_id=publisher_id, created_at__gte=since
        ).aggregate(
            total_requests=Count('id'),
            wins          =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_won=True)),
            avg_ecpm      =Avg('ecpm'),
            total_revenue =Sum('clearing_price'),
        )

        pub_share = (
            Decimal(str(bids['total_revenue'] or 0)) * Decimal('0.30')
        ).quantize(Decimal('0.01'))

        daily = PublisherAnalytics.get_daily_trend(publisher_id, days=min(days, 30))

        return {
            'publisher_id'  : publisher_id,
            'period_days'   : days,
            'bid_requests'  : bids['total_requests'] or 0,
            'impressions'   : bids['wins'] or 0,
            'fill_rate_pct' : round((bids['wins'] or 0) / max(bids['total_requests'] or 1, 1) * 100, 1),
            'avg_ecpm'      : round(float(bids['avg_ecpm'] or 0), 4),
            'gross_revenue' : float(bids['total_revenue'] or 0),
            'publisher_share': float(pub_share),
            'daily_trend'   : daily,
        }

    @staticmethod
    def get_daily_trend(publisher_id: str, days: int = 7) -> list:
        """Daily revenue trend for a publisher."""
        from api.offer_inventory.models import BidLog
        from django.db.models.functions import TruncDate
        from django.db.models import Count, Sum
        since = timezone.now() - timedelta(days=days)
        return list(
            BidLog.objects.filter(publisher_id=publisher_id, created_at__gte=since, is_won=True)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(impressions=Count('id'), revenue=Sum('clearing_price'))
            .order_by('date')
        )

    @staticmethod
    def get_top_earning_apps(publisher_id: str, days: int = 30) -> list:
        """Top earning apps for a publisher."""
        from api.offer_inventory.models import BidLog, PublisherApp
        from django.db.models import Sum, Count
        since = timezone.now() - timedelta(days=days)

        apps = list(
            BidLog.objects.filter(publisher_id=publisher_id, created_at__gte=since, is_won=True)
            .values('app_id')
            .annotate(revenue=Sum('clearing_price'), wins=Count('id'))
            .order_by('-revenue')[:10]
        )
        return apps
