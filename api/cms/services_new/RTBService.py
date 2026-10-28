# api/cms/services_new/RTBService.py
"""RTB (Real-Time Bidding) Service — publisher-side RTB management. CMS owns this."""
import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.db.models import F, Sum, Count
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RTBService:

    @staticmethod
    def get_config() -> Optional[Any]:
        from api.cms.models_new.rtb import RTBConfig
        return RTBConfig.get_active()

    @staticmethod
    def get_ad_for_slot(slot_id: int, user_ip: str = '',
                         country: str = '', device: str = 'desktop') -> Dict:
        """
        Get the best RTB ad for a slot.
        CPAlead RTB: highest bid wins, must meet floor price.
        In production, this would call CPAlead's RTB endpoint.
        """
        from api.cms.models_new.rtb import RTBAdSlot, RTBBidLog
        import uuid, time

        try:
            slot = RTBAdSlot.objects.select_related('rtb_config').get(
                id=slot_id, is_active=True
            )
        except RTBAdSlot.DoesNotExist:
            return {'filled': False, 'reason': 'slot_not_found'}

        config = slot.rtb_config
        if not config.is_active:
            return {'filled': False, 'reason': 'config_inactive'}

        floor = float(slot.floor_price_usd or config.floor_price_cpc_usd)

        # In production: call CPAlead RTB API
        # For now: return CMS's CPAlead offerwall as fallback
        bid_id = uuid.uuid4().hex
        start = time.time()

        # Try to get CPAlead offers as "bids"
        try:
            from api.cms.services_new.CPALeadService import CPALeadService
            offers = CPALeadService._get_cached_offers(
                country=country, device=device, limit=5
            )
            if offers:
                best = offers[0]
                winning_bid = float(best.payout_usd)
                if winning_bid >= floor:
                    elapsed_ms = int((time.time() - start) * 1000)
                    RTBBidLog.objects.create(
                        ad_slot=slot, bid_request_id=bid_id,
                        winning_bid_usd=Decimal(str(winning_bid)),
                        num_bidders=len(offers), floor_price=floor,
                        ad_category='cpa', user_country=country,
                        device_type=device, was_filled=True,
                        response_ms=elapsed_ms,
                    )
                    RTBAdSlot.objects.filter(pk=slot_id).update(
                        impressions=F('impressions') + 1,
                        revenue_usd=F('revenue_usd') + Decimal(str(winning_bid)),
                    )
                    return {
                        'filled': True,
                        'bid_id': bid_id,
                        'winning_bid_usd': winning_bid,
                        'ad_type': 'offer',
                        'offer_title': best.title,
                        'offer_url': best.offer_url,
                        'icon_url': best.icon_url,
                        'response_ms': elapsed_ms,
                    }
        except Exception as e:
            logger.warning(f"[RTB] Offer fetch failed: {e}")

        # No fill
        RTBBidLog.objects.create(
            ad_slot=slot, bid_request_id=bid_id,
            num_bidders=0, floor_price=floor,
            user_country=country, device_type=device, was_filled=False,
        )
        return {'filled': False, 'reason': 'no_bid_above_floor', 'floor': floor}

    @staticmethod
    def get_publisher_stats(days: int = 30) -> Dict:
        """Get RTB publisher performance stats."""
        from api.cms.models_new.rtb import RTBConfig, RTBAdSlot, RTBBidLog
        from django.utils import timezone
        from datetime import timedelta

        config = RTBService.get_config()
        if not config:
            return {'error': 'No RTB config'}

        cutoff = timezone.now() - timedelta(days=days)
        slots = RTBAdSlot.objects.filter(rtb_config=config)
        bid_logs = RTBBidLog.objects.filter(
            ad_slot__in=slots, created_at__gte=cutoff
        )

        agg = bid_logs.aggregate(
            total_requests=Count('id'),
            filled=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(was_filled=True)),
            total_revenue=Sum('winning_bid_usd'),
            avg_response=__import__('django.db.models', fromlist=['Avg']).Avg('response_ms'),
        )
        fill_rate = 0
        if agg['total_requests']:
            fill_rate = round((agg['filled'] or 0) / agg['total_requests'] * 100, 2)

        total_impressions = slots.aggregate(s=Sum('impressions'))['s'] or 0
        total_revenue = float(slots.aggregate(s=Sum('revenue_usd'))['s'] or 0)
        ecpm = round(total_revenue / max(total_impressions, 1) * 1000, 4)

        return {
            'period_days': days,
            'config_name': config.name,
            'total_slots': slots.count(),
            'bid_requests': agg['total_requests'] or 0,
            'filled_bids': agg['filled'] or 0,
            'fill_rate_pct': fill_rate,
            'total_revenue_usd': float(agg['total_revenue'] or 0),
            'avg_response_ms': round(float(agg['avg_response'] or 0), 1),
            'total_impressions': total_impressions,
            'ecpm': ecpm,
            'slots': [{
                'name': s.name, 'type': s.slot_type,
                'impressions': s.impressions, 'clicks': s.clicks,
                'revenue_usd': float(s.revenue_usd),
                'ctr': s.ctr, 'ecpm': s.ecpm,
            } for s in slots],
        }

    @staticmethod
    def create_ad_slot(config_id: int, name: str, slot_type: str,
                        floor_price: float = 0.0,
                        page_location: str = '') -> Dict:
        from api.cms.models_new.rtb import RTBConfig, RTBAdSlot
        try:
            config = RTBConfig.objects.get(id=config_id)
        except RTBConfig.DoesNotExist:
            return {'success': False, 'error': 'Config not found'}
        slot = RTBAdSlot.objects.create(
            rtb_config=config, name=name, slot_type=slot_type,
            floor_price_usd=Decimal(str(floor_price)),
            page_location=page_location, is_active=True,
        )
        return {'success': True, 'slot_id': slot.id, 'name': slot.name}
