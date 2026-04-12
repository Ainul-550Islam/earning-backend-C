# api/offer_inventory/affiliate_advanced/sub_id_tracking.py
"""Sub-ID Tracking Analytics — Deep sub-affiliate attribution."""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class SubIDAnalytics:
    """Analytics for sub-ID tracking parameters (s1–s5)."""

    @staticmethod
    def get_performance(offer_id: str = None,
                         s1: str = None, days: int = 30) -> list:
        """Performance metrics grouped by sub-ID."""
        from api.offer_inventory.models import SubID
        from django.db.models import Count, Sum

        qs = SubID.objects.all()
        if offer_id:
            qs = qs.filter(offer_id=offer_id)
        if s1:
            qs = qs.filter(s1=s1)

        return list(
            qs.values('s1', 'offer__title')
            .annotate(
                clicks     =Count('clicks'),
                revenue    =Sum('revenue'),
            )
            .filter(clicks__gt=0)
            .order_by('-revenue')[:50]
        )

    @staticmethod
    def get_top_sub_ids(limit: int = 20) -> list:
        """Top performing sub-IDs by revenue."""
        from api.offer_inventory.models import SubID
        from django.db.models import Sum, Count
        return list(
            SubID.objects.values('s1')
            .annotate(revenue=Sum('revenue'), offers=Count('offer', distinct=True))
            .filter(revenue__gt=0)
            .order_by('-revenue')[:limit]
        )

    @staticmethod
    def attribute_revenue(sub_id_obj, amount: Decimal):
        """Add revenue to a sub-ID record."""
        from api.offer_inventory.models import SubID
        from django.db.models import F
        SubID.objects.filter(id=sub_id_obj.id).update(
            revenue=F('revenue') + amount
        )

    @staticmethod
    def get_sub_id_funnel(s1: str, days: int = 30) -> dict:
        """Full click-to-conversion funnel for a sub-ID."""
        from api.offer_inventory.models import Click, Conversion
        from django.db.models import Count, Sum
        since = timezone.now() - timedelta(days=days)
        clicks = Click.objects.filter(sub_id__s1=s1, created_at__gte=since)
        convs  = Conversion.objects.filter(
            click__sub_id__s1=s1,
            created_at__gte=since,
            status__name='approved',
        )
        click_cnt = clicks.count()
        conv_cnt  = convs.count()
        revenue   = convs.aggregate(t=Sum('payout_amount'))['t'] or Decimal('0')
        return {
            's1'          : s1,
            'clicks'      : click_cnt,
            'conversions' : conv_cnt,
            'cvr_pct'     : round(conv_cnt / max(click_cnt, 1) * 100, 2),
            'revenue'     : float(revenue),
            'epc'         : round(float(revenue) / max(click_cnt, 1), 4),
            'days'        : days,
        }
