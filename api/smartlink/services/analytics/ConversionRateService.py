import logging
import datetime
from django.db.models import Sum, Count, Q
from django.utils import timezone
from ...models import Click, SmartLink

logger = logging.getLogger('smartlink.cr_service')


class ConversionRateService:
    """
    Calculate conversion rates at various granularities.
    CR = conversions / clicks × 100
    """

    def calculate_for_smartlink(self, smartlink: SmartLink, days: int = 7) -> float:
        """Overall CR for a SmartLink."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        agg = Click.objects.filter(
            smartlink=smartlink,
            created_at__date__gte=cutoff,
            is_fraud=False, is_bot=False,
        ).aggregate(
            clicks=Count('id'),
            conversions=Count('id', filter=Q(is_converted=True)),
        )
        clicks = agg['clicks'] or 0
        conversions = agg['conversions'] or 0
        return round(conversions / clicks * 100, 2) if clicks > 0 else 0.0

    def calculate_by_country(self, smartlink: SmartLink, days: int = 7) -> list:
        """CR broken down by country."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        rows = (
            Click.objects.filter(
                smartlink=smartlink,
                created_at__date__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .values('country')
            .annotate(
                clicks=Count('id'),
                conversions=Count('id', filter=Q(is_converted=True)),
            )
            .order_by('-conversions')
        )
        result = []
        for row in rows:
            c = row['clicks'] or 0
            conv = row['conversions'] or 0
            result.append({
                'country': row['country'],
                'clicks': c,
                'conversions': conv,
                'cr': round(conv / c * 100, 2) if c else 0,
            })
        return result

    def calculate_by_device(self, smartlink: SmartLink, days: int = 7) -> list:
        """CR broken down by device type."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        rows = (
            Click.objects.filter(
                smartlink=smartlink,
                created_at__date__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .values('device_type')
            .annotate(
                clicks=Count('id'),
                conversions=Count('id', filter=Q(is_converted=True)),
            )
        )
        result = []
        for row in rows:
            c = row['clicks'] or 0
            conv = row['conversions'] or 0
            result.append({
                'device_type': row['device_type'],
                'clicks': c,
                'conversions': conv,
                'cr': round(conv / c * 100, 2) if c else 0,
            })
        return result
