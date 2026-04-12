# api/offer_inventory/rtb_engine/win_notifier.py
"""
Win Notifier — Handle RTB auction win/loss notifications.
Records auction results, fires win notice URLs, tracks fill rates.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class WinNotifier:
    """Notify DSPs and publishers of auction outcomes."""

    @staticmethod
    def notify_win(bid_id: str, clearing_price: Decimal,
                    offer_id: str = '', publisher_id: str = '') -> bool:
        """Record a win and fire win notification."""
        try:
            from api.offer_inventory.models import BidLog
            BidLog.objects.filter(request_id=bid_id).update(
                is_won        =True,
                clearing_price=clearing_price,
            )
            logger.info(
                f'RTB win: bid={bid_id} offer={offer_id} '
                f'publisher={publisher_id} price={clearing_price}'
            )
            return True
        except Exception as e:
            logger.error(f'Win notify error: {e}')
            return False

    @staticmethod
    def notify_loss(bid_id: str, reason: str = 'lost_auction') -> bool:
        """Record an auction loss."""
        try:
            from api.offer_inventory.models import BidLog
            BidLog.objects.filter(request_id=bid_id).update(
                is_won=False, loss_reason=reason
            )
            return True
        except Exception as e:
            logger.error(f'Loss notify error: {e}')
            return False

    @staticmethod
    def get_win_rate(publisher_id: str = None, days: int = 7) -> dict:
        """Win rate statistics."""
        from api.offer_inventory.models import BidLog
        from django.db.models import Count, Avg
        from django.db.models import Q

        since = timezone.now() - timedelta(days=days)
        qs    = BidLog.objects.filter(created_at__gte=since)
        if publisher_id:
            qs = qs.filter(publisher_id=publisher_id)

        agg = qs.aggregate(
            total =Count('id'),
            won   =Count('id', filter=Q(is_won=True)),
            no_bid=Count('id', filter=Q(no_bid=True)),
            avg_ecpm=Avg('ecpm'),
        )
        total = agg['total'] or 1
        return {
            'total_requests': agg['total'],
            'won'           : agg['won'],
            'no_bid'        : agg['no_bid'],
            'win_rate_pct'  : round((agg['won'] or 0) / total * 100, 1),
            'fill_rate_pct' : round((total - (agg['no_bid'] or 0)) / total * 100, 1),
            'avg_ecpm'      : round(float(agg['avg_ecpm'] or 0), 4),
            'days'          : days,
        }

    @staticmethod
    def get_hourly_fill_rate(publisher_id: str = None) -> list:
        """Hourly fill rate for the last 24 hours."""
        from api.offer_inventory.models import BidLog
        from django.db.models.functions import TruncHour
        from django.db.models import Count, Q

        since = timezone.now() - timedelta(hours=24)
        qs    = BidLog.objects.filter(created_at__gte=since)
        if publisher_id:
            qs = qs.filter(publisher_id=publisher_id)

        return list(
            qs.annotate(hour=TruncHour('created_at'))
            .values('hour')
            .annotate(
                requests=Count('id'),
                wins    =Count('id', filter=Q(is_won=True)),
            )
            .order_by('hour')
        )
