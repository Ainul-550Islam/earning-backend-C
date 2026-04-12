import logging
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
import datetime
from ...models import SmartLink, SmartLinkDailyStat, SmartLinkStat, Click

logger = logging.getLogger('smartlink.analytics')


class SmartLinkAnalyticsService:
    """
    Query and aggregate analytics data for SmartLinks.
    Used by API viewsets and publisher dashboard.
    """

    def get_summary(self, smartlink: SmartLink, days: int = 30) -> dict:
        """
        Get summary stats for a SmartLink over the last N days.
        """
        cutoff = timezone.now().date() - datetime.timedelta(days=days)

        agg = SmartLinkDailyStat.objects.filter(
            smartlink=smartlink,
            date__gte=cutoff,
        ).aggregate(
            total_clicks=Sum('clicks'),
            total_unique_clicks=Sum('unique_clicks'),
            total_conversions=Sum('conversions'),
            total_revenue=Sum('revenue'),
            total_bot_clicks=Sum('bot_clicks'),
            total_fraud_clicks=Sum('fraud_clicks'),
        )

        clicks = agg['total_clicks'] or 0
        conversions = agg['total_conversions'] or 0
        revenue = float(agg['total_revenue'] or 0)

        return {
            'smartlink_id': smartlink.pk,
            'slug': smartlink.slug,
            'period_days': days,
            'clicks': clicks,
            'unique_clicks': agg['total_unique_clicks'] or 0,
            'conversions': conversions,
            'revenue': revenue,
            'epc': round(revenue / clicks, 4) if clicks > 0 else 0,
            'conversion_rate': round(conversions / clicks * 100, 2) if clicks > 0 else 0,
            'bot_clicks': agg['total_bot_clicks'] or 0,
            'fraud_clicks': agg['total_fraud_clicks'] or 0,
            'quality_rate': round(
                ((clicks - (agg['total_bot_clicks'] or 0) - (agg['total_fraud_clicks'] or 0)) / clicks * 100), 2
            ) if clicks > 0 else 100,
        }

    def get_daily_breakdown(self, smartlink: SmartLink, days: int = 30) -> list:
        """Get day-by-day breakdown of stats."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        return list(
            SmartLinkDailyStat.objects.filter(
                smartlink=smartlink,
                date__gte=cutoff,
            )
            .values('date', 'clicks', 'unique_clicks', 'conversions',
                    'revenue', 'epc', 'conversion_rate', 'top_country', 'top_device')
            .order_by('-date')
        )

    def get_geo_breakdown(self, smartlink: SmartLink, days: int = 30) -> list:
        """Get stats grouped by country."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        return list(
            SmartLinkStat.objects.filter(
                smartlink=smartlink,
                hour__date__gte=cutoff,
            )
            .values('country')
            .annotate(
                clicks=Sum('clicks'),
                unique_clicks=Sum('unique_clicks'),
                conversions=Sum('conversions'),
                revenue=Sum('revenue'),
            )
            .order_by('-clicks')[:50]
        )

    def get_device_breakdown(self, smartlink: SmartLink, days: int = 30) -> list:
        """Get stats grouped by device type."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        return list(
            SmartLinkStat.objects.filter(
                smartlink=smartlink,
                hour__date__gte=cutoff,
            )
            .values('device_type')
            .annotate(
                clicks=Sum('clicks'),
                unique_clicks=Sum('unique_clicks'),
                conversions=Sum('conversions'),
                revenue=Sum('revenue'),
            )
            .order_by('-clicks')
        )

    def get_publisher_totals(self, publisher, days: int = 30) -> dict:
        """Get aggregate stats for all SmartLinks owned by a publisher."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        sl_ids = SmartLink.objects.filter(publisher=publisher).values_list('pk', flat=True)

        agg = SmartLinkDailyStat.objects.filter(
            smartlink_id__in=sl_ids,
            date__gte=cutoff,
        ).aggregate(
            total_clicks=Sum('clicks'),
            total_unique_clicks=Sum('unique_clicks'),
            total_conversions=Sum('conversions'),
            total_revenue=Sum('revenue'),
        )

        clicks = agg['total_clicks'] or 0
        revenue = float(agg['total_revenue'] or 0)

        return {
            'publisher_id': publisher.pk,
            'period_days': days,
            'total_smartlinks': len(sl_ids),
            'clicks': clicks,
            'unique_clicks': agg['total_unique_clicks'] or 0,
            'conversions': agg['total_conversions'] or 0,
            'revenue': revenue,
            'epc': round(revenue / clicks, 4) if clicks > 0 else 0,
        }

    def rollup_hourly_stats(self, smartlink: SmartLink, hour: datetime.datetime):
        """
        Aggregate click records into SmartLinkStat for a given hour.
        Called by stat_rollup_tasks.
        """
        hour_start = hour.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + datetime.timedelta(hours=1)

        clicks_qs = Click.objects.filter(
            smartlink=smartlink,
            created_at__gte=hour_start,
            created_at__lt=hour_end,
        )

        # Group by country + device
        breakdown = clicks_qs.values('country', 'device_type').annotate(
            click_count=Count('id'),
            unique_count=Count('id', filter=Q(is_unique=True)),
            bot_count=Count('id', filter=Q(is_bot=True)),
            fraud_count=Count('id', filter=Q(is_fraud=True)),
            conversion_count=Count('id', filter=Q(is_converted=True)),
            revenue_sum=Sum('payout'),
        )

        for row in breakdown:
            clicks = row['click_count']
            revenue = float(row['revenue_sum'] or 0)
            conversions = row['conversion_count']

            SmartLinkStat.objects.update_or_create(
                smartlink=smartlink,
                hour=hour_start,
                country=row['country'],
                device_type=row['device_type'],
                defaults={
                    'clicks': clicks,
                    'unique_clicks': row['unique_count'],
                    'bot_clicks': row['bot_count'],
                    'fraud_clicks': row['fraud_count'],
                    'conversions': conversions,
                    'revenue': revenue,
                    'epc': round(revenue / clicks, 4) if clicks else 0,
                    'conversion_rate': round(conversions / clicks, 4) if clicks else 0,
                }
            )

        logger.debug(f"Hourly stats rolled up: [{smartlink.slug}] hour={hour_start}")
