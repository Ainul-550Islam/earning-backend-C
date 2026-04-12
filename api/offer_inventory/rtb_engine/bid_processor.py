# api/offer_inventory/rtb_engine/bid_processor.py
"""
RTB Bid Processor — OpenRTB 2.6 compatible bid processing.
Processes bid requests from SSPs/publishers in <100ms.
Selects winning offer based on eCPM, targeting, and availability.
"""
import uuid
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# RTB SLA — must respond within 100ms
RTB_TIMEOUT_MS = 100


@dataclass
class BidRequest:
    """OpenRTB 2.6 Bid Request (simplified)."""
    request_id   : str = field(default_factory=lambda: str(uuid.uuid4()))
    app_id       : str = ''
    publisher_id : str = ''
    user_id      : str = ''
    ip           : str = ''
    user_agent   : str = ''
    country      : str = ''
    device_type  : str = 'mobile'
    os           : str = ''
    os_version   : str = ''
    language     : str = 'en'
    floor_price  : Decimal = Decimal('0')    # Minimum bid (eCPM)
    ad_formats   : list = field(default_factory=lambda: ['banner', 'native'])
    lat          : float = 0.0
    lon          : float = 0.0
    timestamp    : float = field(default_factory=time.time)


@dataclass
class BidResponse:
    """OpenRTB 2.6 Bid Response."""
    request_id   : str = ''
    bid_id       : str = field(default_factory=lambda: str(uuid.uuid4()))
    offer_id     : str = ''
    offer_title  : str = ''
    creative_url : str = ''
    click_url    : str = ''
    ecpm         : Decimal = Decimal('0')
    currency     : str = 'BDT'
    win_notif_url: str = ''
    no_bid       : bool = False
    reason       : str = ''
    response_ms  : float = 0.0


class BidProcessor:
    """
    Core RTB bid processor.
    Receives bid request → selects best offer → returns bid response.
    Must complete in < 100ms.
    """

    @classmethod
    def process(cls, request: BidRequest) -> BidResponse:
        """Process a bid request and return a bid response."""
        start = time.monotonic()

        try:
            # 1. Validate request
            if not request.publisher_id:
                return BidResponse(
                    request_id=request.request_id,
                    no_bid=True, reason='missing_publisher_id'
                )

            # 2. Get eligible offers
            offers = cls._get_eligible_offers(request)
            if not offers:
                return BidResponse(
                    request_id=request.request_id,
                    no_bid=True, reason='no_eligible_offers'
                )

            # 3. Calculate eCPM for each offer
            from .ecpm_calculator import ECPMCalculator
            scored = ECPMCalculator.score_offers(offers, request)

            # 4. Filter by floor price
            eligible = [
                (offer, ecpm) for offer, ecpm in scored
                if ecpm >= request.floor_price
            ]
            if not eligible:
                return BidResponse(
                    request_id=request.request_id,
                    no_bid=True, reason='below_floor_price'
                )

            # 5. Select winner (highest eCPM)
            best_offer, best_ecpm = max(eligible, key=lambda x: x[1])

            # 6. Build response
            from django.conf import settings
            base_url = getattr(settings, 'SITE_URL', 'https://yourplatform.com')

            response = BidResponse(
                request_id   =request.request_id,
                offer_id     =str(best_offer.id),
                offer_title  =best_offer.title,
                creative_url =best_offer.image_url or '',
                click_url    =f'{base_url}/api/offer-inventory/rtb/click/?bid={{bid_id}}&offer={best_offer.id}&publisher={request.publisher_id}',
                ecpm         =best_ecpm,
                win_notif_url=f'{base_url}/api/offer-inventory/rtb/win/?bid={{bid_id}}',
                no_bid       =False,
            )

            response.response_ms = round((time.monotonic() - start) * 1000, 1)
            cls._log_bid(request, response)
            return response

        except Exception as e:
            logger.error(f'RTB bid error: {e}')
            return BidResponse(
                request_id=request.request_id,
                no_bid=True, reason=f'error:{str(e)[:50]}'
            )

    @staticmethod
    def _get_eligible_offers(request: BidRequest) -> list:
        """Get offers eligible for this bid request."""
        from api.offer_inventory.models import Offer
        from django.db.models import Q

        # Cache eligible offers per publisher+country (60s)
        cache_key = f'rtb:eligible:{request.publisher_id}:{request.country}:{request.device_type}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        qs = Offer.objects.filter(
            status='active'
        ).select_related('network', 'category').prefetch_related('caps')

        # Filter by device type
        if request.device_type == 'mobile':
            qs = qs.exclude(
                visibility_rules__rule_type='device',
                visibility_rules__operator='include',
                visibility_rules__values__contains=['desktop'],
            )

        offers = [o for o in qs[:50] if o.is_available]
        cache.set(cache_key, offers, 60)
        return offers

    @staticmethod
    def _log_bid(request: BidRequest, response: BidResponse):
        """Log bid for analytics."""
        from api.offer_inventory.models import BidLog
        try:
            BidLog.objects.create(
                request_id  =request.request_id,
                publisher_id=request.publisher_id,
                offer_id    =response.offer_id or None,
                ecpm        =response.ecpm,
                no_bid      =response.no_bid,
                response_ms =response.response_ms,
                country     =request.country,
                device_type =request.device_type,
            )
        except Exception:
            pass   # Non-critical — don't let logging break bidding
