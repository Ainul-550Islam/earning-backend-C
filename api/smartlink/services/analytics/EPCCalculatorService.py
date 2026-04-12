import logging
import datetime
from django.db.models import Sum, Count, Q
from django.utils import timezone
from ...models import Click, SmartLink, OfferPerformanceStat

logger = logging.getLogger('smartlink.epc_calculator')


class EPCCalculatorService:
    """
    Calculate Earnings Per Click (EPC) at various granularities:
    per SmartLink, per offer, per geo, per device, per time period.
    """

    def calculate_for_smartlink(self, smartlink: SmartLink, days: int = 7) -> float:
        """Calculate overall EPC for a SmartLink over the last N days."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        agg = Click.objects.filter(
            smartlink=smartlink,
            created_at__date__gte=cutoff,
            is_fraud=False,
            is_bot=False,
        ).aggregate(
            total_clicks=Count('id'),
            total_revenue=Sum('payout'),
        )
        clicks = agg['total_clicks'] or 0
        revenue = float(agg['total_revenue'] or 0)
        return round(revenue / clicks, 4) if clicks > 0 else 0.0

    def calculate_for_offer(self, offer_id: int, country: str = '',
                            device_type: str = '', days: int = 7) -> float:
        """Calculate EPC for a specific offer, optionally filtered by geo/device."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        qs = OfferPerformanceStat.objects.filter(
            offer_id=offer_id,
            date__gte=cutoff,
        )
        if country:
            qs = qs.filter(country=country)
        if device_type:
            qs = qs.filter(device_type=device_type)

        agg = qs.aggregate(
            total_clicks=Sum('clicks'),
            total_revenue=Sum('revenue'),
        )
        clicks = agg['total_clicks'] or 0
        revenue = float(agg['total_revenue'] or 0)
        return round(revenue / clicks, 4) if clicks > 0 else 0.0

    def calculate_geo_epc(self, smartlink: SmartLink, days: int = 7) -> list:
        """EPC broken down by country."""
        cutoff = timezone.now().date() - datetime.timedelta(days=days)
        rows = (
            Click.objects.filter(
                smartlink=smartlink,
                created_at__date__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .values('country')
            .annotate(clicks=Count('id'), revenue=Sum('payout'))
            .order_by('-revenue')
        )
        result = []
        for row in rows:
            c = row['clicks'] or 0
            r = float(row['revenue'] or 0)
            result.append({
                'country': row['country'],
                'clicks': c,
                'revenue': r,
                'epc': round(r / c, 4) if c else 0,
            })
        return result
