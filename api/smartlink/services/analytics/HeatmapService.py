import logging
import datetime
from django.db.models import Sum, Count
from django.utils import timezone
from ...models import ClickHeatmap, SmartLink, Click

logger = logging.getLogger('smartlink.heatmap')


class HeatmapService:
    """
    Build and serve geo heatmap data per SmartLink.
    Data is aggregated by country and date.
    """

    def get_heatmap(self, smartlink: SmartLink, days: int = 30) -> list:
        """
        Get heatmap data for a SmartLink.
        Returns list of {country, clicks, conversions, revenue, epc} dicts.
        """
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        rows = (
            ClickHeatmap.objects.filter(
                smartlink=smartlink,
                date__gte=cutoff,
            )
            .values('country')
            .annotate(
                total_clicks=Sum('click_count'),
                total_unique=Sum('unique_click_count'),
                total_conversions=Sum('conversion_count'),
                total_revenue=Sum('revenue'),
            )
            .order_by('-total_clicks')
        )
        result = []
        for row in rows:
            clicks = row['total_clicks'] or 0
            revenue = float(row['total_revenue'] or 0)
            result.append({
                'country': row['country'],
                'clicks': clicks,
                'unique_clicks': row['total_unique'] or 0,
                'conversions': row['total_conversions'] or 0,
                'revenue': revenue,
                'epc': round(revenue / clicks, 4) if clicks else 0,
            })
        return result

    def build_heatmap_for_date(self, smartlink: SmartLink, date: datetime.date):
        """
        Aggregate click data into ClickHeatmap for a specific date.
        Called by heatmap_tasks.py.
        """
        from django.db.models import Q
        rows = (
            Click.objects.filter(
                smartlink=smartlink,
                created_at__date=date,
                is_bot=False,
            )
            .values('country')
            .annotate(
                click_count=Count('id'),
                unique_count=Count('id', filter=Q(is_unique=True)),
                conversion_count=Count('id', filter=Q(is_converted=True)),
                revenue=Sum('payout'),
            )
        )
        for row in rows:
            clicks = row['click_count'] or 0
            revenue = float(row['revenue'] or 0)
            ClickHeatmap.objects.update_or_create(
                smartlink=smartlink,
                country=row['country'],
                date=date,
                defaults={
                    'click_count': clicks,
                    'unique_click_count': row['unique_count'] or 0,
                    'conversion_count': row['conversion_count'] or 0,
                    'revenue': revenue,
                    'epc': round(revenue / clicks, 4) if clicks else 0,
                }
            )
        logger.debug(f"Heatmap built: [{smartlink.slug}] {date}")

    def get_top_countries(self, smartlink: SmartLink, limit: int = 10) -> list:
        """Get top N countries by clicks for a SmartLink (all time)."""
        return list(
            ClickHeatmap.objects.filter(smartlink=smartlink)
            .values('country')
            .annotate(total_clicks=Sum('click_count'))
            .order_by('-total_clicks')[:limit]
        )
