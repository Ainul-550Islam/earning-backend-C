# api/offer_inventory/rtb_engine/dsp_connector.py
"""DSP Connector — Connect to external Demand-Side Platforms."""
import logging
import requests
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DSPConnector:
    """
    Connect to external DSPs for additional bid demand.
    Aggregates bids from multiple DSPs alongside internal offers.
    Compatible: Google AdX, AppLovin Exchange, Verizon Media.
    """

    @staticmethod
    def get_external_bids(request) -> list:
        """Collect bids from all configured DSPs."""
        from api.offer_inventory.models import DSPConfig
        dsps = DSPConfig.objects.filter(is_active=True)
        bids = []
        for dsp in dsps:
            bid = DSPConnector._bid_one(dsp, request)
            if bid:
                bids.append(bid)
        return bids

    @staticmethod
    def _bid_one(dsp, request) -> dict:
        """Send bid request to one DSP and collect response."""
        payload = {
            'id'       : request.request_id,
            'imp'      : [{'id': '1', 'banner': {'w': 320, 'h': 50}}],
            'site'     : {'id': request.app_id, 'publisher': {'id': request.publisher_id}},
            'device'   : {'ip': request.ip, 'ua': request.user_agent, 'geo': {'country': request.country}},
            'at'       : 2,    # Second-price auction
            'tmax'     : 80,   # Timeout ms
        }
        try:
            resp = requests.post(
                dsp.endpoint_url,
                json   =payload,
                headers={'Content-Type': 'application/json', 'x-openrtb-version': '2.6'},
                timeout=0.08,    # 80ms timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                seats = data.get('seatbid', [])
                if seats and seats[0].get('bid'):
                    bid = seats[0]['bid'][0]
                    return {
                        'dsp_id'    : str(dsp.id),
                        'dsp_name'  : dsp.name,
                        'price'     : Decimal(str(bid.get('price', 0))),
                        'ad_markup' : bid.get('adm', ''),
                        'is_external': True,
                    }
            elif resp.status_code == 204:
                pass   # No bid
        except Exception as e:
            logger.debug(f'DSP {dsp.name} bid error: {e}')
        return None

    @staticmethod
    def get_connected_dsps() -> list:
        """List all configured DSP connections."""
        from api.offer_inventory.models import DSPConfig
        return list(
            DSPConfig.objects.filter(is_active=True)
            .values('id', 'name', 'endpoint_url', 'is_active')
        )


# api/offer_inventory/rtb_engine/win_notifier.py
"""Win Notifier — Notify DSPs and record auction wins."""

class WinNotifier:
    """Handle win notification for RTB auctions."""

    @staticmethod
    def notify_win(bid_id: str, clearing_price: Decimal,
                    offer_id: str, publisher_id: str) -> bool:
        """Record a win and fire win notification URLs."""
        from api.offer_inventory.models import BidLog
        from django.db.models import F

        # Update bid log
        BidLog.objects.filter(request_id=bid_id).update(
            is_won         =True,
            clearing_price =clearing_price,
        )

        logger.info(
            f'RTB win: bid={bid_id} offer={offer_id} '
            f'publisher={publisher_id} price={clearing_price}'
        )
        return True

    @staticmethod
    def notify_loss(bid_id: str, reason: str = 'lost_auction') -> bool:
        """Record an auction loss."""
        from api.offer_inventory.models import BidLog
        BidLog.objects.filter(request_id=bid_id).update(
            is_won=False, loss_reason=reason
        )
        return True

    @staticmethod
    def get_win_rate(days: int = 7) -> dict:
        """Platform-wide win rate statistics."""
        from api.offer_inventory.models import BidLog
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        agg   = BidLog.objects.filter(created_at__gte=since).aggregate(
            total=Count('id'),
            won  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_won=True)),
            no_bid=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(no_bid=True)),
        )
        total = agg['total'] or 1
        return {
            'total_requests': agg['total'],
            'won'           : agg['won'],
            'no_bid'        : agg['no_bid'],
            'win_rate_pct'  : round(agg['won'] / total * 100, 1),
            'fill_rate_pct' : round((total - agg['no_bid']) / total * 100, 1),
            'days'          : days,
        }
