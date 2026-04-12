import logging
import datetime
from django.db.models import Sum, Count
from django.utils import timezone
from ...models import Click, SmartLink

logger = logging.getLogger('smartlink.revenue_attribution')


class RevenueAttributionService:
    """
    Revenue attribution per SmartLink, publisher, offer, and geo.
    """

    def get_smartlink_revenue(self, smartlink: SmartLink, days: int = 30) -> dict:
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        agg = Click.objects.filter(
            smartlink=smartlink,
            is_converted=True,
            created_at__date__gte=cutoff,
        ).aggregate(
            total_revenue=Sum('payout'),
            total_conversions=Count('id'),
        )
        return {
            'revenue': float(agg['total_revenue'] or 0),
            'conversions': agg['total_conversions'] or 0,
        }

    def get_publisher_revenue(self, publisher, days: int = 30) -> dict:
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        sl_ids = SmartLink.objects.filter(publisher=publisher).values_list('pk', flat=True)
        agg = Click.objects.filter(
            smartlink_id__in=sl_ids,
            is_converted=True,
            created_at__date__gte=cutoff,
        ).aggregate(
            total_revenue=Sum('payout'),
            total_conversions=Count('id'),
        )
        return {
            'revenue': float(agg['total_revenue'] or 0),
            'conversions': agg['total_conversions'] or 0,
        }

    def get_revenue_by_offer(self, smartlink: SmartLink, days: int = 30) -> list:
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        return list(
            Click.objects.filter(
                smartlink=smartlink,
                is_converted=True,
                created_at__date__gte=cutoff,
            )
            .values('offer_id')
            .annotate(revenue=Sum('payout'), conversions=Count('id'))
            .order_by('-revenue')
        )

    def get_revenue_by_country(self, smartlink: SmartLink, days: int = 30) -> list:
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        return list(
            Click.objects.filter(
                smartlink=smartlink,
                is_converted=True,
                created_at__date__gte=cutoff,
            )
            .values('country')
            .annotate(revenue=Sum('payout'), conversions=Count('id'))
            .order_by('-revenue')[:50]
        )
